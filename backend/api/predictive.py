# api/predictive.py
from fastapi import APIRouter
from services.predictive_service import predictive_service

router = APIRouter(tags=["Predictive Maintenance"])

@router.get("/predictive/report")
def get_predictive_report():
    """
    Rileva e genera i rischi di manutenzione predittiva in tempo reale (PdM Engine).
    """
    return predictive_service.get_realtime_report()
