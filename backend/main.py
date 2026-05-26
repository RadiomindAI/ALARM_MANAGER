# main.py
"""
main.py
========
FastAPI lightweight orchestrator for Alarm Manager.
"""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api import alarms_router, performance_router, kb_router, predictive_router, session_router, audit_router
from config.settings import settings

# Import rebuild_kb_full safely
try:
    from core.ingestion import rebuild_kb_full
except ImportError:
    def rebuild_kb_full(): pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alarm Manager API", version="2.1 (Modular)")

# CORS Setup
cors_origins_env = os.getenv("CORS_ORIGINS")
if cors_origins_env:
    origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    origins = settings.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrazione Router API
app.include_router(alarms_router, prefix="/api")
app.include_router(performance_router, prefix="/api")
app.include_router(kb_router, prefix="/api")
app.include_router(predictive_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(audit_router, prefix="/api")

# APScheduler Setup
scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup_event():
    # Schedula rebuild completo KB alle 02:00 ogni notte
    scheduler.add_job(
        rebuild_kb_full,
        trigger=CronTrigger(hour=2, minute=0),
        id="nightly_kb_rebuild",
        name="Rebuild completo notturno KB allarmi",
        replace_existing=True
    )
    scheduler.start()
    logger.info("APScheduler avviato con successo. Rebuild KB schedulato ogni notte alle 02:00.")

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logger.info("APScheduler arrestato.")

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "message": "Alarm Manager Backend v2.1 (Modular & Secure)",
        "alarm_kb_exists": settings.alarm_kb_path.exists(),
        "operator_kb_exists": settings.operator_kb_path.exists(),
    }

# Crea le cartelle persistenti all'avvio
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)

# Servire Frontend React in produzione
if settings.frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dist / "assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        path = settings.frontend_dist / full_path
        if path.is_file():
            return FileResponse(path)
        return FileResponse(settings.frontend_dist / "index.html")
