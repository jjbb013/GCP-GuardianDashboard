import logging
from datetime import timedelta, datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from . import crud, schemas, auth
from .config import settings, ServerConfig
from .database import init_db, get_db
from .gcp_service import gcp_service

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize FastAPI app
app = FastAPI(
    title="GCP Guardian",
    description="A service to monitor GCP VM traffic and prevent cost overruns.",
    version="2.0.0"
)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

def _check_traffic_for_server(db: Session, server: ServerConfig):
    """Logic to check traffic for a single server."""
    try:
        logging.info(f"Checking traffic for server: {server.name} ({server.id})")
        traffic_gb = gcp_service.get_vm_egress_traffic_gb(server)
        logging.info(f"[{server.id}] Current egress traffic: {traffic_gb:.4f} GB")
        
        crud.create_traffic_log(db, server_id=server.id, traffic_gb=traffic_gb)
        
        if traffic_gb > settings.TRAFFIC_THRESHOLD_GB:
            logging.warning(
                f"[{server.id}] Traffic threshold exceeded! "
                f"Current: {traffic_gb:.4f} GB, Threshold: {settings.TRAFFIC_THRESHOLD_GB} GB"
            )
            gcp_service.shutdown_vm(server)
            crud.create_action_log(
                db,
                server_id=server.id,
                action_type="AUTO_SHUTDOWN",
                reason=f"Threshold exceeded ({traffic_gb:.4f} GB > {settings.TRAFFIC_THRESHOLD_GB} GB)"
            )
        else:
            logging.info(f"[{server.id}] Traffic is within the threshold.")
    except Exception as e:
        logging.error(f"An error occurred while checking server {server.id}: {e}", exc_info=True)

def check_all_servers_traffic_job():
    """The main job to be scheduled, iterates through all configured servers."""
    logging.info("Scheduler running: Checking traffic for all configured servers...")
    db: Session = next(get_db())
    try:
        for server in settings.SERVERS:
            _check_traffic_for_server(db, server)
    finally:
        db.close()

def _check_restart_for_server(db: Session, server: ServerConfig):
    """Logic to check for monthly restart for a single server."""
    try:
        logging.info(f"Monthly check for auto-restart for server: {server.name} ({server.id})")
        last_shutdown = crud.get_last_shutdown_action(db, server_id=server.id)
        if last_shutdown and last_shutdown.action_type == "AUTO_SHUTDOWN":
            now = datetime.utcnow()
            last_shutdown_time = last_shutdown.timestamp.replace(tzinfo=None)
            
            previous_month = now.month - 1 if now.month > 1 else 12
            previous_month_year = now.year if now.month > 1 else now.year - 1

            if last_shutdown_time.year == previous_month_year and last_shutdown_time.month == previous_month:
                 logging.info(f"[{server.id}] VM was auto-shutdown last month. Initiating auto-restart.")
                 gcp_service.start_vm(server)
                 crud.create_action_log(
                     db,
                     server_id=server.id,
                     action_type="AUTO_RESTART",
                     reason="Monthly restart after auto-shutdown"
                 )
            else:
                logging.info(f"[{server.id}] VM was not auto-shutdown in the previous month.")
        else:
            logging.info(f"[{server.id}] No previous auto-shutdown found.")
    except Exception as e:
        logging.error(f"An error occurred during monthly restart check for server {server.id}: {e}", exc_info=True)

def all_servers_monthly_restart_job():
    """Checks all servers for potential monthly restart."""
    logging.info("Scheduler running: Monthly check for auto-restart for all servers...")
    db: Session = next(get_db())
    try:
        for server in settings.SERVERS:
            _check_restart_for_server(db, server)
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    """
    Actions to be performed on application startup.
    - Initialize the database.
    - Schedule the recurring job.
    - Run the job immediately once.
    """
    logging.info("GCP Guardian service starting up...")
    
    # 1. Initialize the database
    logging.info("Initializing database...")
    init_db()
    logging.info("Database initialized.")
    
    # 2. Schedule the jobs
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_all_servers_traffic_job, 'interval', hours=1)
    logging.info(f"Hourly traffic check job scheduled for all {len(settings.SERVERS)} servers.")
    scheduler.add_job(all_servers_monthly_restart_job, 'cron', day=1, hour=1)
    logging.info("Monthly auto-restart job scheduled for all servers.")
    scheduler.start()
    
    # 3. Schedule the initial check to run shortly after startup
    from datetime import datetime, timedelta
    scheduler.add_job(check_all_servers_traffic_job, 'date', run_date=datetime.now() + timedelta(seconds=5))
    logging.info("Initial traffic check for all servers scheduled to run in 5 seconds.")


@app.get("/health", tags=["System"])
def health_check():
    """
    Health check endpoint to verify that the service is running.
    """
    return {"status": "ok"}

# --- API Routes ---

# --- Auth Routes ---
@app.post("/api/v1/auth/login", response_model=schemas.Token, tags=["Auth"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Logs in the admin user and returns a JWT token.
    """
    logging.info(f"Login attempt for user: '{form_data.username}'")
    
    # For debugging: Check if settings are loaded correctly.
    # Be careful not to log sensitive data in production.
    logging.debug(f"Comparing with stored username: '{settings.ADMIN_USERNAME}'")
    
    user_authenticated = (form_data.username == settings.ADMIN_USERNAME and 
                          form_data.password == settings.ADMIN_PASSWORD)

    if not user_authenticated:
        logging.warning(f"Authentication failed for user: '{form_data.username}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logging.info(f"User '{form_data.username}' authenticated successfully.")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": settings.ADMIN_USERNAME}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

import os

# --- Server and Dashboard Routes ---
@app.get("/api/v1/servers", response_model=list[schemas.Server], tags=["Servers"])
async def get_servers_list(current_user: schemas.User = Depends(auth.get_current_user)):
    """Returns a list of all configured servers."""
    # --- Forceful Debugging ---
    print("\n" + "="*50)
    print("--- DEBUG: Inside get_servers_list Endpoint ---")
    
    print("\n[1] Raw Environment Variables Found:")
    found_vars = False
    for key, value in os.environ.items():
        if key.startswith("GCP_SERVER_"):
            # Mask sensitive SA_KEY
            val_to_print = f"{value[:10]}...{value[-10:]}" if "SA_KEY" in key and len(value) > 20 else value
            print(f"  - {key}: {val_to_print}")
            found_vars = True
    if not found_vars:
        print("  - None found.")

    print(f"\n[2] Total servers loaded by config loader: {len(settings.SERVERS)}")
    print("="*50 + "\n")
    # --- End Debugging ---

    return [{"id": s.id, "name": s.name} for s in settings.SERVERS]

@app.get("/api/v1/servers/{server_id}/status", response_model=schemas.VmStatus, tags=["Dashboard"])
async def get_dashboard_status(server_id: str, current_user: schemas.User = Depends(auth.get_current_user)):
    """Returns the current status of a specific monitored VM."""
    server = settings.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    vm_status = await run_in_threadpool(gcp_service.get_vm_status, server)
    current_traffic = await run_in_threadpool(gcp_service.get_vm_egress_traffic_gb, server)
    
    threshold = settings.TRAFFIC_THRESHOLD_GB
    usage_percent = round((current_traffic / threshold) * 100, 2) if threshold > 0 else 0

    return schemas.VmStatus(
        server_id=server.id,
        instance_name=server.instance_name,
        status=vm_status,
        current_traffic_gb=round(current_traffic, 4),
        traffic_threshold_gb=threshold,
        traffic_usage_percent=usage_percent,
    )

# --- VM Action Routes ---
@app.post("/api/v1/servers/{server_id}/shutdown", tags=["Actions"], status_code=status.HTTP_202_ACCEPTED)
async def shutdown_vm_manual(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_user)
):
    """Manually shuts down a specific VM."""
    server = settings.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    
    logging.info(f"Manual shutdown for server '{server.id}' requested by user '{current_user.username}'.")
    await run_in_threadpool(gcp_service.shutdown_vm, server)
    crud.create_action_log(
        db,
        server_id=server.id,
        action_type="MANUAL_SHUTDOWN",
        reason=f"Requested by user {current_user.username}"
    )
    return {"message": f"VM shutdown initiated for server {server.id}."}

@app.post("/api/v1/servers/{server_id}/start", tags=["Actions"], status_code=status.HTTP_202_ACCEPTED)
async def start_vm_manual(
    server_id: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_user)
):
    """Manually starts a specific VM."""
    server = settings.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    logging.info(f"Manual start for server '{server.id}' requested by user '{current_user.username}'.")
    await run_in_threadpool(gcp_service.start_vm, server)
    crud.create_action_log(
        db,
        server_id=server.id,
        action_type="MANUAL_START",
        reason=f"Requested by user {current_user.username}"
    )
    return {"message": f"VM start initiated for server {server.id}."}

# --- Log Routes ---
@app.get("/api/v1/logs/actions", response_model=list[schemas.ActionLog], tags=["Logs"])
async def read_action_logs(
    server_id: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_user)
):
    """Retrieves action logs, optionally filtered by server_id."""
    logs = crud.get_action_logs(db, server_id=server_id, skip=skip, limit=limit)
    return logs
