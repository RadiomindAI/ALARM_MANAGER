# api/audit.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

# Import log_feedback from core.audit
try:
    from core.audit import log_feedback
except ImportError:
    def log_feedback(*a, **kw): pass

router = APIRouter(tags=["Audit Logs"])

class AuditLogPayload(BaseModel):
    event_type: str
    alarm_code_name: Optional[str] = None
    operator_action: Optional[str] = None
    note: Optional[str] = ""

@router.post("/audit/log")
def log_audit_feedback(payload: AuditLogPayload):
    """
    Registra un evento di feedback o azione operatore nel file di audit log.
    """
    log_feedback(
        event_type=payload.event_type,
        alarm_code_name=payload.alarm_code_name,
        operator_action=payload.operator_action,
        note=payload.note
    )
    return {"status": "ok", "message": "Azione operatore registrata correttamente."}

@router.get("/audit/log")
def get_audit_log():
    """
    Restituisce la cronologia degli eventi di audit (feedback_log.json).
    """
    import os, json
    from core.audit import FEEDBACK_LOG_PATH
    if os.path.exists(FEEDBACK_LOG_PATH):
        try:
            with open(FEEDBACK_LOG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"events": []}
    return {"events": []}
