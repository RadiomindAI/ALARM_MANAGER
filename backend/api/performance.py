# api/performance.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Optional
from services.pm_service import pm_service

router = APIRouter(tags=["Performance MW"])

@router.post("/upload-performance")
async def upload_performance(files: list[UploadFile] = File(...)):
    """
    Carica i file Excel di Performance (PM) e li accoda al Parquet storico con deduplica.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nessun file fornito per il caricamento.")
    return await pm_service.process_uploads(files)

@router.post("/upload/performance")
async def upload_performance_alias1(files: list[UploadFile] = File(...)):
    return await upload_performance(files)

@router.post("/upload/pm")
async def upload_performance_alias2(files: list[UploadFile] = File(...)):
    return await upload_performance(files)

@router.get("/performance/status")
def performance_status():
    """
    Restituisce i metadati sullo stato del DB Performance (righe, date, conteggio siti).
    """
    return pm_service.get_status()

@router.get("/pm/status")
def pm_status_specular():
    """
    Endpoint speculare per ottenere lo status PM cacheato.
    """
    return performance_status()

@router.get("/performance/{site_name}")
def get_performance(
    site_name: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    freq_ghz: float = 13.0
):
    """
    Esegue l'analisi delle performance completa per il sito radio richiesto.
    """
    return pm_service.analyze_site(site_name, date_from, date_to, freq_ghz)

@router.get("/pm/site/{site_name}")
def get_raw_pm_for_site(site_name: str):
    """
    Restituisce i record PM grezzi per il sito specificato.
    """
    if not pm_service.is_available():
         return []
    from core.pm_ingestion import get_pm_for_site
    import pandas as pd
    df = get_pm_for_site(site_name)
    if df is None or (hasattr(df, 'empty') and df.empty):
        return []
    
    records = df.to_dict(orient="records")
    for record in records:
        for k, v in record.items():
            if isinstance(v, pd.Timestamp) or hasattr(v, 'isoformat'):
                record[k] = v.isoformat()
            elif pd.isna(v):
                record[k] = None
    return records
