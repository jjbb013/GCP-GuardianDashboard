from sqlalchemy.orm import Session
from typing import Optional, List
from . import database, schemas

# --- Server State CRUD ---

def get_server(db: Session, server_id: str) -> Optional[database.Server]:
    """Retrieves the state of a single server by its ID."""
    return db.query(database.Server).filter(database.Server.id == server_id).first()

def get_or_create_server(db: Session, server_id: str) -> database.Server:
    """Retrieves a server's state or creates it if it doesn't exist."""
    db_server = get_server(db, server_id)
    if not db_server:
        db_server = database.Server(id=server_id)
        db.add(db_server)
        db.commit()
        db.refresh(db_server)
    return db_server

def update_server_state(db: Session, server_id: str, server_update: schemas.ServerStateCreate) -> database.Server:
    """Updates a server's state."""
    db_server = get_or_create_server(db, server_id)
    update_data = server_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_server, key, value)
    db.commit()
    db.refresh(db_server)
    return db_server

def get_all_auto_shutdown_servers(db: Session) -> List[database.Server]:
    """Retrieves all servers that are marked as auto-shutdown."""
    return db.query(database.Server).filter(database.Server.auto_shutdown_active == True).all()


# --- Log CRUD ---

def create_traffic_log(db: Session, server_id: str, traffic_gb: float):
    """Creates a new traffic log entry for a specific server."""
    db_log = database.TrafficLog(server_id=server_id, traffic_gb=traffic_gb)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def create_action_log(db: Session, server_id: str, action_type: str, reason: str):
    """Creates a new action log entry for a specific server."""
    db_log = database.ActionLog(server_id=server_id, action_type=action_type, reason=reason)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_action_logs(db: Session, server_id: Optional[str] = None, skip: int = 0, limit: int = 100):
    """
    Retrieves a list of action logs, most recent first.
    Can be filtered by server_id.
    """
    query = db.query(database.ActionLog)
    if server_id:
        query = query.filter(database.ActionLog.server_id == server_id)
    return query.order_by(database.ActionLog.timestamp.desc()).offset(skip).limit(limit).all()

def get_last_shutdown_action(db: Session, server_id: str):
    """Retrieves the most recent shutdown action log for a specific server."""
    return db.query(database.ActionLog)\
        .filter(database.ActionLog.server_id == server_id)\
        .filter(database.ActionLog.action_type.like('%SHUTDOWN%'))\
        .order_by(database.ActionLog.timestamp.desc())\
        .first()
