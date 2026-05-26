# api/alarms.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.alarm_service import alarm_service

router = APIRouter(tags=["Alarms FM"])

@router.post("/upload")
async def upload_alarms(files: list[UploadFile] = File(...)):
    """
    Upload di file Excel multipli di allarmi (FM).
    Elabora tutti i file, aggiorna lo storico e restituisce il triage combinato.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nessun file fornito per il caricamento.")
    return await alarm_service.process_uploads(files)

@router.get("/alarms-status")
def alarms_status():
    """
    Restituisce i metadati sullo stato del DB allarmi (righe totali, data min/max).
    """
    return alarm_service.get_status()

@router.get("/alarms/status")
def alarms_status_specular():
    """
    Endpoint speculare per allineamento con le chiamate del frontend.
    """
    return alarms_status()

@router.get("/history/ne/{me_name}")
def get_ne_history(me_name: str):
    """
    Restituisce lo storico degli allarmi per il NE richiesto e il suo partner remoto.
    """
    return alarm_service.get_ne_history(me_name)
