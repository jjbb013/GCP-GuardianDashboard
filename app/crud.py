from sqlalchemy.orm import Session
from . import database

def create_traffic_log(db: Session, traffic_gb: float):
    """Creates a new traffic log entry."""
    db_log = database.TrafficLog(traffic_gb=traffic_gb)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def create_action_log(db: Session, action_type: str, reason: str):
    """Creates a new action log entry."""
    db_log = database.ActionLog(action_type=action_type, reason=reason)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_action_logs(db: Session, skip: int = 0, limit: int = 100):
    """Retrieves a list of action logs, most recent first."""
    return db.query(database.ActionLog).order_by(database.ActionLog.timestamp.desc()).offset(skip).limit(limit).all()

def get_last_shutdown_action(db: Session):
    """Retrieves the most recent shutdown action log."""
    return db.query(database.ActionLog)\
        .filter(database.ActionLog.action_type.like('%SHUTDOWN%'))\
        .order_by(database.ActionLog.timestamp.desc())\
        .first()
