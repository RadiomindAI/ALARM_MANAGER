# api/kb.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from schemas.alarms import WizardPayload, UpdateRulePayload
from services.kb_service import kb_service

# Import rebuild_kb_full from core
try:
    from core.ingestion import rebuild_kb_full
except ImportError:
    def rebuild_kb_full(): pass

router = APIRouter(tags=["Knowledge Base"])

@router.post("/operator-kb/init")
def wizard_init(payload: WizardPayload):
    """
    Salva le preferenze del wizard iniziale nella KB operatore.
    """
    rules_saved = kb_service.init_operator_rules(payload.rules)
    return {"status": "ok", "rules_saved": rules_saved}

@router.get("/operator-kb")
def get_operator_kb():
    """
    Restituisce la Knowledge Base dell'operatore (regole personalizzate ed overrides).
    """
    return kb_service.get_operator_kb()

@router.post("/operator-kb/update")
def update_operator_rule(payload: UpdateRulePayload):
    """
    Aggiorna o crea una singola regola personalizzata per un allarme.
    """
    return kb_service.update_operator_rule(
        alarm_code_name=payload.alarm_code_name,
        operator_action=payload.operator_action,
        note=payload.note,
        new_alarm_entry=payload.new_alarm_entry
    )

@router.post("/kb/rebuild")
def trigger_kb_rebuild(background_tasks: BackgroundTasks):
    """
    Innesca il rebuild completo della KB in background per evitare timeout HTTP.
    """
    background_tasks.add_task(rebuild_kb_full)
    return {"status": "processing", "message": "KB rebuild completo in corso in background."}

@router.get("/kb/stats")
def kb_stats():
    """
    Restituisce statistiche aggregate sulla Knowledge Base storica (top allarmi, siti a rischio).
    """
    return kb_service.get_kb_stats()
