import os
from pathlib import Path

class Config:
    """Loads configuration from environment variables."""
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
    GCP_VM_INSTANCE_ID = os.getenv("GCP_VM_INSTANCE_ID")
    GCP_VM_ZONE = os.getenv("GCP_VM_ZONE")
    GCP_SERVICE_ACCOUNT_CREDENTIALS = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS")
    
    TRAFFIC_THRESHOLD_GB = float(os.getenv("TRAFFIC_THRESHOLD_GB", 100))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/gcp_guardian.db")

    # For Phase 2
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    
    # JWT Settings
    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Instantiate the config
settings = Config()

# Basic validation
required_vars = [
    "GCP_PROJECT_ID",
    "GCP_VM_INSTANCE_ID",
    "GCP_VM_ZONE",
    "GCP_SERVICE_ACCOUNT_CREDENTIALS",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "SECRET_KEY",
]

missing_vars = [var for var in required_vars if not getattr(settings, var)]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
