# api/session.py
from fastapi import APIRouter
from services.kb_service import kb_service
from services.alarm_service import alarm_service

router = APIRouter(tags=["Session Management"])

@router.get("/first-launch")
def first_launch():
    """
    Chiamato al primo avvio del frontend per verificare se mostrare il wizard iniziale.
    """
    return kb_service.get_first_launch_status()

@router.get("/last-session")
def get_last_session():
    """
    Recupera l'ultima analisi del triage effettuata (salvata in sessione persistente).
    """
    return alarm_service.get_last_session()

@router.delete("/last-session")
def clear_last_session():
    """
    Cancella l'analisi del triage salvata nella sessione corrente.
    """
    return alarm_service.clear_last_session()
