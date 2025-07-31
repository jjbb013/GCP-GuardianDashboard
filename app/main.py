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
from .config import settings
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

def check_vm_traffic_job():
    """The main job to be scheduled."""
    logging.info("Scheduler running: Checking GCP VM traffic...")
    
    db: Session = next(get_db())
    
    try:
        # 1. Get traffic data from GCP
        traffic_gb = gcp_service.get_vm_egress_traffic_gb()
        logging.info(f"Current VM egress traffic: {traffic_gb:.4f} GB")
        
        # 2. Log traffic data to the database
        crud.create_traffic_log(db, traffic_gb=traffic_gb)
        logging.info("Traffic data logged to database.")
        
        # 3. Check if traffic exceeds the threshold
        if traffic_gb > settings.TRAFFIC_THRESHOLD_GB:
            logging.warning(
                f"Traffic threshold exceeded! "
                f"Current: {traffic_gb:.4f} GB, "
                f"Threshold: {settings.TRAFFIC_THRESHOLD_GB} GB"
            )
            
            # 4. Shut down the VM
            gcp_service.shutdown_vm()
            
            # 5. Log the shutdown action
            crud.create_action_log(
                db,
                action_type="AUTO_SHUTDOWN",
                reason=f"Threshold exceeded ({traffic_gb:.4f} GB > {settings.TRAFFIC_THRESHOLD_GB} GB)"
            )
            logging.info("Shutdown action logged to database.")
        else:
            logging.info("Traffic is within the threshold.")
            
    except Exception as e:
        logging.error(f"An error occurred during the job execution: {e}", exc_info=True)
    finally:
        db.close()

def monthly_restart_job():
    """
    Checks if the VM was automatically shut down in the previous month
    and restarts it if so. Runs on the 1st of every month.
    """
    logging.info("Scheduler running: Monthly check for auto-restart...")
    db: Session = next(get_db())
    try:
        last_shutdown = crud.get_last_shutdown_action(db)
        if last_shutdown and last_shutdown.action_type == "AUTO_SHUTDOWN":
            # Check if the shutdown was in the previous month
            now = datetime.utcnow()
            last_shutdown_time = last_shutdown.timestamp.replace(tzinfo=None) # Make it naive for comparison
            
            # Correctly identify the previous month, handling year boundaries
            previous_month = now.month - 1 if now.month > 1 else 12
            previous_month_year = now.year if now.month > 1 else now.year - 1

            if last_shutdown_time.year == previous_month_year and last_shutdown_time.month == previous_month:
                 logging.info(f"VM was auto-shutdown last month ({previous_month_year}-{previous_month}). Initiating auto-restart.")
                 gcp_service.start_vm()
                 crud.create_action_log(
                     db,
                     action_type="AUTO_RESTART",
                     reason="Monthly restart after auto-shutdown"
                 )
            else:
                logging.info("VM was not auto-shutdown in the previous month. No action needed.")
        else:
            logging.info("No previous auto-shutdown found. No action needed.")
    except Exception as e:
        logging.error(f"An error occurred during the monthly restart job: {e}", exc_info=True)
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
    # Schedule the hourly traffic check
    scheduler.add_job(check_vm_traffic_job, 'interval', hours=1)
    logging.info(f"Hourly traffic check job scheduled for VM '{settings.GCP_VM_INSTANCE_ID}'.")
    # Schedule the monthly restart check
    scheduler.add_job(monthly_restart_job, 'cron', day=1, hour=1) # Run at 1 AM on the 1st day of the month
    logging.info("Monthly auto-restart job scheduled.")
    scheduler.start()
    
    # 3. Schedule the initial check to run shortly after startup
    # This prevents blocking the server startup if the initial GCP call is slow or times out.
    from datetime import datetime, timedelta
    scheduler.add_job(check_vm_traffic_job, 'date', run_date=datetime.now() + timedelta(seconds=5))
    logging.info("Initial traffic check scheduled to run in 5 seconds.")


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

# --- Dashboard Routes ---
@app.get("/api/v1/dashboard/status", response_model=schemas.VmStatus, tags=["Dashboard"])
async def get_dashboard_status(current_user: schemas.User = Depends(auth.get_current_user)):
    """
    Returns the current status of the monitored VM. Requires authentication.
    """
    # Run synchronous, blocking I/O operations in a separate thread pool
    vm_status = await run_in_threadpool(gcp_service.get_vm_status)
    current_traffic = await run_in_threadpool(gcp_service.get_vm_egress_traffic_gb)
    
    threshold = settings.TRAFFIC_THRESHOLD_GB
    
    usage_percent = 0
    if threshold > 0:
        usage_percent = round((current_traffic / threshold) * 100, 2)

    return schemas.VmStatus(
        instance_name=settings.GCP_VM_INSTANCE_ID,
        status=vm_status,
        current_traffic_gb=round(current_traffic, 4),
        traffic_threshold_gb=threshold,
        traffic_usage_percent=usage_percent,
    )

# --- VM Action Routes ---
@app.post("/api/v1/vm/shutdown", tags=["Actions"], status_code=status.HTTP_202_ACCEPTED)
async def shutdown_vm_manual(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_user)
):
    """
    Manually shuts down the VM. Requires authentication.
    """
    logging.info(f"Manual shutdown requested by user '{current_user.username}'.")
    gcp_service.shutdown_vm()
    crud.create_action_log(
        db,
        action_type="MANUAL_SHUTDOWN",
        reason=f"Requested by user {current_user.username}"
    )
    return {"message": "VM shutdown initiated."}


@app.post("/api/v1/vm/start", tags=["Actions"], status_code=status.HTTP_202_ACCEPTED)
async def start_vm_manual(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_user)
):
    """
    Manually starts the VM. Requires authentication.
    """
    logging.info(f"Manual start requested by user '{current_user.username}'.")
    gcp_service.start_vm()
    crud.create_action_log(
        db,
        action_type="MANUAL_START",
        reason=f"Requested by user {current_user.username}"
    )
    return {"message": "VM start initiated."}

# --- Log Routes ---
@app.get("/api/v1/logs/actions", response_model=list[schemas.ActionLog], tags=["Logs"])
async def read_action_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(auth.get_current_user)
):
    """
    Retrieves a list of action logs. Requires authentication.
    """
    logs = crud.get_action_logs(db, skip=skip, limit=limit)
    return logs
