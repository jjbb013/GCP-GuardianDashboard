import logging
from typing import Optional
from datetime import datetime, timedelta
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
from .notifications import send_bark_notification

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize FastAPI app
app = FastAPI(
    title="GCP Guardian",
    description="A service to monitor GCP VM traffic and prevent cost overruns.",
    version="2.1.0" # Version bump for new features
)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# --- Background Jobs ---

def check_server_traffic_and_alert(db: Session, server: ServerConfig):
    """
    Checks traffic for a single server, sends alerts, and performs auto-shutdown if needed.
    """
    try:
        logging.info(f"Checking traffic for server: {server.name} ({server.id})")
        
        # Get server state from DB or create it
        db_server = crud.get_or_create_server(db, server_id=server.id)
        
        # Fetch traffic data
        traffic_gb = gcp_service.get_vm_egress_traffic_gb(server)
        logging.info(f"[{server.id}] Current egress traffic: {traffic_gb:.4f} GB")
        crud.create_traffic_log(db, server_id=server.id, traffic_gb=traffic_gb)

        # Calculate usage percentage
        usage_percent = (traffic_gb / settings.TRAFFIC_THRESHOLD_GB) * 100
        current_month = datetime.utcnow().strftime("%Y-%m")

        # Reset monthly flags if a new month has started
        if db_server.warning_sent_month != current_month:
            db_server.warning_sent_month = None
        if db_server.shutdown_month != current_month:
            db_server.shutdown_month = None
        
        # --- Shutdown Logic (95%) ---
        if usage_percent >= settings.SHUTDOWN_THRESHOLD_PERCENT and db_server.shutdown_month != current_month:
            logging.warning(
                f"[{server.id}] Shutdown threshold reached! "
                f"Usage: {usage_percent:.2f}% ({traffic_gb:.4f} GB)"
            )
            gcp_service.shutdown_vm(server)
            reason = f"Shutdown threshold reached ({usage_percent:.2f}%)"
            crud.create_action_log(db, server_id=server.id, action_type="AUTO_SHUTDOWN", reason=reason)
            send_bark_notification(
                title=f"VM Auto-Shutdown: {server.name}",
                body=f"Traffic reached {usage_percent:.2f}%. The VM has been automatically shut down to prevent further costs."
            )
            # Update server state in DB
            db_server.shutdown_month = current_month
            db_server.auto_shutdown_active = True

        # --- Warning Logic (75%) ---
        elif usage_percent >= settings.WARNING_THRESHOLD_PERCENT and db_server.warning_sent_month != current_month:
            logging.warning(
                f"[{server.id}] Warning threshold reached! "
                f"Usage: {usage_percent:.2f}% ({traffic_gb:.4f} GB)"
            )
            reason = f"Warning threshold reached ({usage_percent:.2f}%)"
            crud.create_action_log(db, server_id=server.id, action_type="TRAFFIC_WARNING", reason=reason)
            send_bark_notification(
                title=f"Traffic Warning: {server.name}",
                body=f"Monthly traffic usage has reached {usage_percent:.2f}%. Please monitor usage."
            )
            # Update server state in DB
            db_server.warning_sent_month = current_month
        
        else:
            logging.info(f"[{server.id}] Traffic usage ({usage_percent:.2f}%) is within normal parameters.")

        db.commit()

    except Exception as e:
        logging.error(f"An error occurred while checking server {server.id}: {e}", exc_info=True)
        db.rollback()

def check_all_servers_traffic_job():
    """The main job to be scheduled, iterates through all configured servers."""
    logging.info("Scheduler running: Checking traffic for all configured servers...")
    db: Session = next(get_db())
    try:
        for server in settings.SERVERS:
            check_server_traffic_and_alert(db, server)
    finally:
        db.close()

def monthly_restart_job():
    """
    On the 1st of the month, restarts all VMs that were auto-shutdown.
    """
    logging.info("Scheduler running: Monthly check for auto-restart for all servers...")
    db: Session = next(get_db())
    restarted_servers = []
    try:
        servers_to_restart = crud.get_all_auto_shutdown_servers(db)
        if not servers_to_restart:
            logging.info("No servers found that were previously auto-shutdown. No action needed.")
            return

        logging.info(f"Found {len(servers_to_restart)} servers to restart: {[s.id for s in servers_to_restart]}")
        
        for db_server in servers_to_restart:
            server_config = settings.get_server(db_server.id)
            if server_config:
                try:
                    logging.info(f"[{server_config.id}] Initiating monthly auto-restart.")
                    gcp_service.start_vm(server_config)
                    crud.create_action_log(
                        db,
                        server_id=server_config.id,
                        action_type="AUTO_RESTART",
                        reason="Monthly restart after auto-shutdown"
                    )
                    db_server.auto_shutdown_active = False
                    restarted_servers.append(server_config.name)
                except Exception as e:
                    logging.error(f"Failed to restart server {server_config.id}: {e}", exc_info=True)
            else:
                logging.warning(f"Server with ID '{db_server.id}' found in DB for restart but not in current config. Skipping.")
        
        db.commit()

        if restarted_servers:
            send_bark_notification(
                title="Monthly VM Restart Complete",
                body=f"Successfully restarted {len(restarted_servers)} VMs: {', '.join(restarted_servers)}"
            )

    except Exception as e:
        logging.error(f"An error occurred during the monthly restart job: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    """
    Actions to be performed on application startup.
    """
    logging.info("GCP Guardian service starting up...")
    
    # 1. Initialize the database
    logging.info("Initializing database...")
    init_db()
    logging.info("Database initialized.")
    
    # 2. Schedule the jobs
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(check_all_servers_traffic_job, 'interval', hours=1)
    logging.info(f"Hourly traffic check job scheduled for all {len(settings.SERVERS)} servers.")
    # Cron: At 12:00 on day 1 of every month
    scheduler.add_job(monthly_restart_job, 'cron', day=1, hour=12)
    logging.info("Monthly auto-restart job scheduled.")
    scheduler.start()
    
    # 3. Schedule the initial check to run shortly after startup
    scheduler.add_job(check_all_servers_traffic_job, 'date', run_date=datetime.now() + timedelta(seconds=10))
    logging.info("Initial traffic check for all servers scheduled to run in 10 seconds.")


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}

# --- API Routes (unchanged from here) ---

# --- Auth Routes ---
@app.post("/api/v1/auth/login", response_model=schemas.Token, tags=["Auth"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user_authenticated = (form_data.username == settings.ADMIN_USERNAME and 
                          form_data.password == settings.ADMIN_PASSWORD)
    if not user_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": settings.ADMIN_USERNAME}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Server and Dashboard Routes ---
@app.get("/api/v1/servers", response_model=list[schemas.Server], tags=["Servers"])
async def get_servers_list(current_user: schemas.User = Depends(auth.get_current_user)):
    return [{"id": s.id, "name": s.name} for s in settings.SERVERS]

@app.get("/api/v1/servers/{server_id}/status", response_model=schemas.VmStatus, tags=["Dashboard"])
async def get_dashboard_status(server_id: str, current_user: schemas.User = Depends(auth.get_current_user)):
    server = settings.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    vm_status = await run_in_threadpool(gcp_service.get_vm_status, server)
    current_traffic = await run_in_threadpool(gcp_service.get_vm_egress_traffic_gb, server)
    
    # Use the main threshold for display purposes
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
    server = settings.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    
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
    server = settings.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    await run_in_threadpool(gcp_service.start_vm, server)
    crud.create_action_log(
        db,
        server_id=server.id,
        action_type="MANUAL_START",
        reason=f"Requested by user {current_user.username}"
    )
    return {"message": f"VM start initiated for server {server.id}."}

# --- Notification Routes ---
@app.post("/api/v1/notifications/test-bark", tags=["Notifications"], status_code=status.HTTP_200_OK)
async def test_bark_notification(scenario: Optional[str] = None, current_user: schemas.User = Depends(auth.get_current_user)):
    """
    Sends a test notification to the configured Bark URL.
    Can simulate different scenarios using the 'scenario' query parameter.
    """
    logging.info(f"Test Bark notification requested by user '{current_user.username}' with scenario: {scenario}")
    if not settings.BARK_URL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BARK_URL is not configured in the .env file."
        )

    title = "Test Notification"
    body = f"This is a generic test message from GCP Guardian Dashboard, triggered by {current_user.username}."
    
    # Use the first configured server for realistic mock data
    first_server = settings.SERVERS[0] if settings.SERVERS else None

    if scenario == "warning" and first_server:
        title = f"[SIMULATED] Traffic Warning: {first_server.name}"
        body = f"Monthly traffic usage has reached {settings.WARNING_THRESHOLD_PERCENT + 3.5:.2f}%. Please monitor usage."
    elif scenario == "shutdown" and first_server:
        title = f"[SIMULATED] VM Auto-Shutdown: {first_server.name}"
        body = f"Traffic reached {settings.SHUTDOWN_THRESHOLD_PERCENT + 1.2:.2f}%. The VM has been automatically shut down to prevent further costs."

    await run_in_threadpool(send_bark_notification, title=title, body=body)
    
    return {"message": f"Test notification for scenario '{scenario or 'default'}' sent successfully."}

# --- Log Routes ---
@app.get("/api/v1/logs/actions", response_model=list[schemas.ActionLog], tags=["Logs"])
async def read_action_logs(
    server_id: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_user)
):
    logs = crud.get_action_logs(db, server_id=server_id, skip=skip, limit=limit)
    return logs
