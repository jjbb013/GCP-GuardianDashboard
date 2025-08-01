import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file before anything else
load_dotenv()

@dataclass
class ServerConfig:
    """Holds configuration for a single GCP server instance."""
    id: str
    project_id: str
    instance_name: str
    zone: str
    sa_key: str  # Base64 encoded service account key
    
    @property
    def name(self) -> str:
        """Returns the instance name as the default name."""
        return self.instance_name

class Config:
    """Loads configuration from environment variables."""
    
    def __init__(self):
        # Common settings
        self.TRAFFIC_THRESHOLD_GB = float(os.getenv("TRAFFIC_THRESHOLD_GB", 100))
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/gcp_guardian.db")
        
        # Auth settings
        self.ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
        self.ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.ALGORITHM = os.getenv("ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

        # Load server configurations
        self.SERVERS: List[ServerConfig] = self._load_servers()
        
        self._validate()

    def _load_servers(self) -> List[ServerConfig]:
        """Dynamically loads server configurations from environment variables."""
        servers = []
        i = 1
        while True:
            # A server is defined by the presence of its project ID
            project_id = os.getenv(f"GCP_SERVER_{i}_PROJECT_ID")
            if not project_id:
                break  # No more servers found

            instance_name = os.getenv(f"GCP_SERVER_{i}_VM_INSTANCE_NAME")
            zone = os.getenv(f"GCP_SERVER_{i}_VM_ZONE")
            sa_key = os.getenv(f"GCP_SERVER_{i}_SA_KEY")

            if not all([instance_name, zone, sa_key]):
                raise ValueError(
                    f"Incomplete configuration for server {i}. "
                    "VM_INSTANCE_NAME, VM_ZONE, and SA_KEY are required."
                )
            
            # Use a simple, predictable ID based on the index
            server_id = f"server-{i}"

            servers.append(ServerConfig(
                id=server_id,
                project_id=project_id,
                instance_name=instance_name,
                zone=zone,
                sa_key=sa_key
            ))
            i += 1
        
        return servers

    def _validate(self):
        """Validates that all required configuration is present."""
        required_common_vars = [
            "ADMIN_USERNAME",
            "ADMIN_PASSWORD",
            "SECRET_KEY",
        ]
        missing_vars = [var for var in required_common_vars if not getattr(self, var)]
        if missing_vars:
            raise ValueError(f"Missing required common environment variables: {', '.join(missing_vars)}")

        if not self.SERVERS:
            raise ValueError("No server configurations found. Please define at least one server in your .env file using the format GCP_SERVER_1_PROJECT_ID, etc.")

    def get_server(self, server_id: str) -> Optional[ServerConfig]:
        """Retrieves a server configuration by its ID."""
        for server in self.SERVERS:
            if server.id == server_id:
                return server
        return None

# Instantiate the config
settings = Config()
