from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- User Schemas ---
class User(BaseModel):
    username: str

# --- Server Schemas ---
class Server(BaseModel):
    id: str
    name: str

class ServerStateBase(BaseModel):
    id: str
    warning_sent_month: Optional[str] = None
    shutdown_month: Optional[str] = None
    auto_shutdown_active: bool = False

class ServerStateCreate(ServerStateBase):
    pass

class ServerState(ServerStateBase):
    class Config:
        from_attributes = True

# --- Log Schemas ---
class ActionLogBase(BaseModel):
    server_id: str
    action_type: str
    reason: Optional[str] = None

class ActionLogCreate(ActionLogBase):
    pass

class ActionLog(ActionLogBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# --- VM Status Schemas ---
class VmStatus(BaseModel):
    server_id: str
    instance_name: str
    status: str
    current_traffic_gb: float
    traffic_threshold_gb: float
    traffic_usage_percent: float
