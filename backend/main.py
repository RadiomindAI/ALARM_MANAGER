"""
main.py
========
FastAPI backend per Alarm Manager.
Nuovi endpoint: first-launch, operator-kb, kb/stats
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import shutil
import json
import logging
import pandas as pd
from datetime import datetime

from core.ingestion import process_excel
from core.audit import log_feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alarm Manager API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Percorsi ──────────────────────────────────────────────────────────────────
UPLOAD_DIR       = "uploads"
DATA_DIR         = "data"
ALARM_KB_PATH    = os.path.join(DATA_DIR, "alarm_kb.json")
OPERATOR_KB_PATH = os.path.join(DATA_DIR, "operator_kb.json")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR,   exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Utility KB
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path: str, default: dict) -> dict:
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Errore lettura %s: %s", path, e)
    return default


def _save_json(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _default_operator_kb() -> dict:
    return {
        "wizard_completed": False,
        "wizard_completed_at": None,
        "operator_rules": {},
        "new_alarm_history": [],
    }


def _get_structural_alarms_for_wizard() -> list:
    """Restituisce i top allarmi strutturali per il wizard."""
    kb = _load_json(ALARM_KB_PATH, {})
    alarm_profiles = kb.get('alarm_profiles', {})
    threshold      = kb.get('filterability_threshold', 0.85)
    operator_kb    = _load_json(OPERATOR_KB_PATH, _default_operator_kb())
    already_set    = set(operator_kb.get('operator_rules', {}).keys())

    structural = [
        {
            'alarm_code_name':   name,
            'filterability_score': p.get('filterability_score', 0),
            'total_occurrences': p.get('total_occurrences', 0),
            'affected_me_count': p.get('affected_me_count', 0),
            'main_severity':     p.get('main_severity', ''),
            'suggested_action':  p.get('suggested_action', 'TOLERABLE'),
            'suggested_reason':  p.get('suggested_reason', ''),
            'already_classified': name in already_set,
        }
        for name, p in alarm_profiles.items()
        if p.get('filterability_score', 0) >= threshold
    ]
    structural.sort(key=lambda x: x['filterability_score'], reverse=True)
    return structural[:50]  # Max 50 nel wizard


# ─────────────────────────────────────────────────────────────────────────────
#  Modelli Pydantic
# ─────────────────────────────────────────────────────────────────────────────

class AlarmRule(BaseModel):
    alarm_code_name: str
    operator_action: str   # TRASCURABILE | MONITORA | SCALA
    note: Optional[str] = ""


class WizardPayload(BaseModel):
    rules: list[AlarmRule]


class UpdateRulePayload(BaseModel):
    alarm_code_name: str
    operator_action: str
    note: Optional[str] = ""
    new_alarm_entry: Optional[dict] = None   # info aggiuntive per nuovi allarmi


# ─────────────────────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "message": "Alarm Manager Backend v2.0",
        "alarm_kb_exists": os.path.exists(ALARM_KB_PATH),
        "operator_kb_exists": os.path.exists(OPERATOR_KB_PATH),
    }


@app.get("/api/first-launch")
def first_launch():
    """
    Chiamato al primo avvio del frontend.
    Restituisce:
      - wizard_completed: bool
      - structural_alarms: lista allarmi per il wizard
      - kb_available: se la KB è stata generata
    """
    operator_kb = _load_json(OPERATOR_KB_PATH, _default_operator_kb())
    kb_available = os.path.exists(ALARM_KB_PATH)

    structural_alarms = []
    if kb_available and not operator_kb.get('wizard_completed', False):
        structural_alarms = _get_structural_alarms_for_wizard()

    return {
        "wizard_completed": operator_kb.get('wizard_completed', False),
        "kb_available":     kb_available,
        "structural_alarms": structural_alarms,
    }


@app.post("/api/operator-kb/init")
def wizard_init(payload: WizardPayload):
    """Salva le preferenze del wizard iniziale."""
    operator_kb = _load_json(OPERATOR_KB_PATH, _default_operator_kb())

    for rule in payload.rules:
        operator_kb['operator_rules'][rule.alarm_code_name] = {
            'operator_action': rule.operator_action,
            'note':            rule.note or '',
            'set_at':          datetime.now().isoformat(),
        }

    operator_kb['wizard_completed']    = True
    operator_kb['wizard_completed_at'] = datetime.now().isoformat()
    _save_json(OPERATOR_KB_PATH, operator_kb)

    # Invalida cache classifier
    from core.classifier import reload_kb
    reload_kb()
    
    log_feedback(
        event_type="wizard_completed",
        rules_count=len(payload.rules)
    )

    return {"status": "ok", "rules_saved": len(payload.rules)}


@app.get("/api/operator-kb")
def get_operator_kb():
    """Restituisce la KB operatore completa."""
    return _load_json(OPERATOR_KB_PATH, _default_operator_kb())


@app.post("/api/operator-kb/update")
def update_operator_rule(payload: UpdateRulePayload):
    """Aggiorna una singola regola operatore (es. da pannello nuovi allarmi)."""
    operator_kb = _load_json(OPERATOR_KB_PATH, _default_operator_kb())

    operator_kb['operator_rules'][payload.alarm_code_name] = {
        'operator_action': payload.operator_action,
        'note':            payload.note or '',
        'set_at':          datetime.now().isoformat(),
    }

    # Registra nella history se è un nuovo allarme
    if payload.new_alarm_entry:
        history = operator_kb.get('new_alarm_history', [])
        entry = {
            'alarm_code_name':  payload.alarm_code_name,
            'first_seen':       datetime.now().isoformat(),
            'operator_action':  payload.operator_action,
            'solution_applied': payload.new_alarm_entry.get('solution_applied', ''),
            'resolved':         payload.new_alarm_entry.get('resolved', False),
            'note':             payload.note or '',
        }
        history.append(entry)
        operator_kb['new_alarm_history'] = history

    _save_json(OPERATOR_KB_PATH, operator_kb)

    from core.classifier import reload_kb
    reload_kb()
    
    log_feedback(
        event_type="new_alarm_classified" if payload.new_alarm_entry else "alarm_reclassified",
        alarm_code_name=payload.alarm_code_name,
        operator_action=payload.operator_action,
        note=payload.note or ''
    )

    return {"status": "ok", "alarm": payload.alarm_code_name, "action": payload.operator_action}


@app.get("/api/kb/stats")
def kb_stats():
    """Statistiche KB per la dashboard frontend."""
    kb = _load_json(ALARM_KB_PATH, {})
    if not kb:
        return {"available": False, "message": "KB non ancora generata. Esegui build_kb.py"}

    alarm_profiles = kb.get('alarm_profiles', {})
    me_profiles    = kb.get('me_profiles',    {})
    threshold      = kb.get('filterability_threshold', 0.85)

    structural     = [(n, p) for n, p in alarm_profiles.items() if p.get('is_structural')]
    top_structural = sorted(structural, key=lambda x: x[1].get('filterability_score', 0), reverse=True)[:20]
    top_risk_me    = sorted(me_profiles.items(), key=lambda x: x[1].get('risk_score', 0), reverse=True)[:20]

    operator_kb    = _load_json(OPERATOR_KB_PATH, _default_operator_kb())

    return {
        "available":             True,
        "generated_at":          kb.get('generated_at'),
        "last_updated":          kb.get('last_updated'),
        "history_days":          kb.get('history_days', 0),
        "date_from":             kb.get('date_from'),
        "date_to":               kb.get('date_to'),
        "total_events":          kb.get('total_events', 0),
        "unique_mes":            kb.get('unique_mes', 0),
        "unique_alarm_types":    kb.get('unique_alarm_types', 0),
        "structural_alarm_count": kb.get('structural_alarm_count', 0),
        "filterability_threshold": threshold,
        "top_structural_alarms": [
            {
                "name":               n,
                "score":              p.get('filterability_score', 0),
                "occurrences":        p.get('total_occurrences', 0),
                "affected_me":        p.get('affected_me_count', 0),
                "severity":           p.get('main_severity', ''),
                "operator_classified": n in operator_kb.get('operator_rules', {}),
            }
            for n, p in top_structural
        ],
        "top_risk_ne": [
            {
                "name":          n,
                "risk_score":    p.get('risk_score', 0),
                "total_alarms":  p.get('total_alarms_20d', 0),
                "chronic_count": p.get('chronic_alarm_count', 0),
                "top_alarm":     p.get('top_alarm', ''),
            }
            for n, p in top_risk_me
        ],
        "wizard_completed": operator_kb.get('wizard_completed', False),
        "operator_rules_count": len(operator_kb.get('operator_rules', {})),
    }

@app.get("/api/history/ne/{me_name}")
def get_ne_history(me_name: str):
    """Restituisce lo storico degli allarmi per il NE richiesto e il suo corrispondente remoto."""
    try:
        parquet_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DATI", "history_db.parquet")
        if not os.path.exists(parquet_path):
            return {"error": "Storico non disponibile"}
        
        df = pd.read_parquet(parquet_path)
        
        if 'ME' not in df.columns:
            return {"error": "Colonna ME mancante nello storico"}
            
        me_df = df[df['ME'] == me_name].copy()
        
        # Trova la subnet e il remoto
        subnet = None
        if 'Subnet_28' in me_df.columns and len(me_df) > 0:
            subnet = me_df['Subnet_28'].dropna().iloc[0]
            
        remote_me = None
        remote_df = pd.DataFrame()
        
        if subnet:
            subnet_df = df[df['Subnet_28'] == subnet]
            other_mes = subnet_df[subnet_df['ME'] != me_name]['ME'].unique()
            if len(other_mes) > 0:
                remote_me = other_mes[0]
                remote_df = df[df['ME'] == remote_me].copy()
        
        def format_df(d):
            if len(d) == 0: return []
            if 'Occurrence_Time' in d.columns:
                d = d.sort_values(by='Occurrence_Time', ascending=False)
            d = d.head(150)
            res = []
            for _, r in d.iterrows():
                res.append({
                    "Alarm_Code_Name": str(r.get("Alarm_Code_Name", "")),
                    "Alarm_Severity": str(r.get("Alarm_Severity", "")),
                    "Occurrence_Time": str(r.get("Occurrence_Time", "")),
                })
            return res
            
        local_alarms = format_df(me_df)
        remote_alarms = format_df(remote_df)
        
        local_codes = set([a['Alarm_Code_Name'] for a in local_alarms])
        remote_codes = set([a['Alarm_Code_Name'] for a in remote_alarms])
        
        solutions = []
        if local_codes & remote_codes:
            solutions.append("Allarmi simmetrici rilevati: Possibile problema di propagazione o degrado tratta.")
        if "MW_LOF" in local_codes or "MW_LOF" in remote_codes or "MW_BER_SD" in local_codes or "R_LOS" in local_codes:
            solutions.append("Verificare allineamento parabole e interferenze (LOF/BER/LOS rilevati).")
        if not solutions:
            solutions.append("Verificare alimentazione, porte ottiche e power locale/remota.")
            
        return {
            "local_me": me_name,
            "local_alarms": local_alarms,
            "remote_me": remote_me,
            "remote_alarms": remote_alarms,
            "suggested_solutions": solutions
        }
        
    except Exception as e:
        logger.error(f"Errore caricamento history per {me_name}: {e}")
        return {"error": str(e)}

@app.post("/api/upload")
async def upload_alarms(file: UploadFile = File(...)):
    """Upload file Excel giornaliero: classifica + aggiorna storico."""
    if not file.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail="Solo file Excel (.xlsx/.xls) supportati.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        results = process_excel(file_path)
        return {"status": "success", "data": results}
    except ValueError as ve:
        logger.warning("Validazione fallita: %s", ve)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Errore elaborazione file: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Errore interno durante l'elaborazione del file.")

# ── Servire Frontend React (Deploy) ──────────────────────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(path):
            return FileResponse(path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
