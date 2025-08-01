from sqlalchemy.orm import Session
from typing import Optional
from . import database

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
