# MW Alarm Manager — Refactor Backend File per File

> Documento tecnico di riferimento per il refactoring progressivo del backend FastAPI del progetto MW Alarm Manager.
> Ogni file è descritto con: stato attuale, problemi rilevati, struttura proposta, responsabilità e note di migrazione.

---

## Contesto e Obiettivi

Il backend attuale è organizzato in un `main.py` monolitico + cartella `core/` con moduli di media granularità. Il progetto è funzionante ma mostra i segnali tipici della fase di crescita: logica applicativa negli endpoint, euristiche inline, dipendenze circolari latenti, e assenza di test automatici sulle funzioni critiche.

**Obiettivi del refactoring:**
- Separare nettamente API, servizi, dominio, repository e configurazione
- Rendere la logica di dominio testabile indipendentemente dagli endpoint HTTP
- Centralizzare le soglie tecniche e le regole operative in configurazione versionata
- Mantenere compatibilità API completa: zero breaking changes sul frontend

**Strategia:** refactoring incrementale, file per file, preservando comportamento. Non è una riscrittura.

---

## Struttura Target

```
backend/
├── main.py                         ← Solo app, middleware, scheduler, mount frontend
├── api/
│   ├── __init__.py
│   ├── alarms.py                   ← Endpoint FM alarms
│   ├── performance.py              ← Endpoint PM / analisi sito
│   ├── kb.py                       ← Endpoint Knowledge Base
│   ├── predictive.py               ← Endpoint PdM engine
│   ├── session.py                  ← Endpoint last-session, first-launch
│   └── audit.py                    ← Endpoint audit log
├── services/
│   ├── __init__.py
│   ├── alarm_service.py            ← Orchestrazione upload allarmi FM
│   ├── pm_service.py               ← Orchestrazione upload e analisi PM
│   ├── kb_service.py               ← Gestione KB allarmi e KB operatore
│   ├── predictive_service.py       ← PdM engine wrapper
│   └── troubleshooting_service.py  ← Wrapper WorkflowMWTroubleshootingZTE
├── domain/
│   ├── __init__.py
│   ├── alarm_rules.py              ← Logica classificazione pura (senza I/O)
│   ├── pm_rules.py                 ← Logica downshift, stats, conclusioni
│   ├── topology.py                 ← Autodetect siti, pairing locale/remoto
│   └── outcomes.py                 ← Matrice diagnostica, getoutcome
├── repositories/
│   ├── __init__.py
│   ├── parquet_repo.py             ← Lettura/scrittura Parquet (alarms + PM)
│   ├── json_repo.py                ← loadjson / savejson + file lock
│   └── excel_repo.py               ← Lettura file Excel con validazione
├── schemas/
│   ├── __init__.py
│   ├── alarms.py                   ← AlarmRule, WizardPayload, UpdateRulePayload
│   ├── performance.py              ← PerformanceResult, SiteStats
│   ├── kb.py                       ← KBStats, KBProfile
│   └── common.py                   ← StatusResponse, HealthResponse
├── config/
│   ├── settings.py                 ← Pydantic Settings (env vars, paths)
│   └── thresholds.yml              ← Soglie tecniche versionabili
├── utils/
│   ├── sanitize.py                 ← sanitize_data (NaN/Inf → None)
│   ├── files.py                    ← Safe file upload, nomi randomizzati
│   └── cache.py                    ← TTLCache generico
├── core/                           ← Moduli esistenti (da svuotare progressivamente)
│   ├── classifier.py
│   ├── ingestion.py
│   ├── pmingestion.py
│   ├── audit.py
│   ├── solutions.py
│   └── weatherservice.py
└── tests/
    ├── test_alarm_rules.py
    ├── test_pm_rules.py
    ├── test_topology.py
    ├── test_kb_service.py
    └── test_api_alarms.py
```

---

## Refactoring File per File

---

### 1. `main.py` — Attuale (monolitico) → Orchestratore leggero

**Stato attuale:** ~400+ righe. Contiene definizioni di endpoint, modelli Pydantic, logica helper (`loadjson`, `savejson`, `defaultoperatorkb`, `getstructuralalarmsforwizard`), setup CORS, scheduler APScheduler, mount frontend statico.

**Problemi:**
- Logica applicativa mista a configurazione infrastrutturale
- Modelli Pydantic definiti inline invece che in `schemas/`
- Helper (`loadjson`, `savejson`) replicati anche in `core/`
- Funzione `getstructuralalarmsforwizard` è logica di servizio, non routing

**Refactoring proposto:**

```python
# main.py — DOPO il refactoring
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api import alarms, performance, kb, predictive, session, audit
from config.settings import settings
from core.ingestion import rebuild_kb_full

app = FastAPI(title="Alarm Manager API", version="2.1")

# CORS
app.add_middleware(CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Router
app.include_router(alarms.router,      prefix="/api")
app.include_router(performance.router, prefix="/api")
app.include_router(kb.router,          prefix="/api")
app.include_router(predictive.router,  prefix="/api")
app.include_router(session.router,     prefix="/api")
app.include_router(audit.router,       prefix="/api")

# Scheduler
scheduler = BackgroundScheduler()

@app.on_event("startup")
def startup():
    scheduler.add_job(rebuild_kb_full, CronTrigger(hour=2, minute=0),
                      id="nightly_kb_rebuild", replace_existing=True)
    scheduler.start()

@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()

# Frontend statico
if settings.frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dist / "assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    from fastapi.responses import FileResponse
    path = settings.frontend_dist / full_path
    return FileResponse(path if path.is_file() else settings.frontend_dist / "index.html")
```

**Linee risultanti: ~50.** Tutta la logica va nei moduli dedicati.

---

### 2. `config/settings.py` — NUOVO

**Motivo:** oggi i path assoluti, le variabili d'ambiente e le costanti sono sparsi tra `main.py`, `core/classifier.py`, `core/ingestion.py` e `core/pmingestion.py`. Ogni modulo calcola `BACKEND_DIR`, `DATA_DIR`, `DATI_DIR` in modo indipendente.

**Contenuto proposto:**

```python
# config/settings.py
from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache

class Settings(BaseSettings):
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    dati_dir: Path = base_dir / ".." / "DATI"
    upload_dir: Path = base_dir / "uploads"
    frontend_dist: Path = base_dir / ".." / "frontend" / "dist"

    # Derived paths (KB files)
    @property
    def alarm_kb_path(self) -> Path:
        return self.data_dir / "alarmkb.json"

    @property
    def operator_kb_path(self) -> Path:
        return self.data_dir / "operatorkb.json"

    @property
    def parquet_alarms_path(self) -> Path:
        return self.dati_dir / "historydb.parquet"

    @property
    def parquet_pm_path(self) -> Path:
        return self.dati_dir / "pmhistory.parquet"

    # App
    cors_origins: list[str] = ["http://localhost:5173"]
    pm_cache_ttl_seconds: int = 300
    filterability_threshold: float = 0.85
    chronic_days: int = 21
    wizard_max_alarms: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

**Note di migrazione:** sostituire tutti i `BACKEND_DIR`, `DATA_DIR`, `DATI_DIR` hardcodati con `settings.xxx`. Nessuna breaking change.

---

### 3. `config/thresholds.yml` — NUOVO

**Motivo:** nel `WorkflowMWTroubleshootingZTE.py` le soglie tecniche (`RSL < -63`, `XPI < 20`, `MSE < -35`, `delta_IF > 0.8`, `CHRONIC_DAYS = 21`, `FILTERABILITY_THRESHOLD = 0.85`) sono costanti inline. Ogni modifica richiede di toccare il codice sorgente.

```yaml
# config/thresholds.yml
# Soglie tecniche per analisi PM radio ZTE — versionare con il codice

pm_radio:
  rsl_fading_threshold_dbm: -63.0      # RSL sotto cui si diagnostica fading climatico
  rsl_nominal_threshold_dbm: -60.0     # RSL nominale atteso
  xpi_critical_threshold_db: 20.0      # XPI sotto cui si diagnostica disallineamento XPIC
  xpi_warning_threshold_db: 25.0       # XPI di attenzione
  mse_interference_threshold_db: -35.0 # MSE sotto cui si diagnostica interferenza esterna
  delta_if_cable_threshold_dbm: 0.8    # Delta IF sopra cui si diagnostica anomalia cavo/connettori
  downshift_warning_seconds: 0         # Qualsiasi downshift ACM è considerato rilevante

kb:
  filterability_threshold: 0.85        # Score minimo per classificare allarme come strutturale
  chronic_days: 21                     # Giorni dopo i quali un allarme diventa "cronico"
  wizard_max_alarms: 50                # Max allarmi presentati nel wizard iniziale

pdm:
  risk_weights:
    duration: 0.50                     # Peso metrica m2 (persistenza temporale)
    severity: 0.30                     # Peso metrica severità
    frequency: 0.20                    # Peso metrica m3 (frequenza)
  risk_thresholds:
    critical: 0.75
    high: 0.60
    medium: 0.40
  window_seconds: 900                  # Finestra temporale normalizzazione m2 (15 min)
```

**Note di migrazione:** caricare con `yaml.safe_load` all'avvio via `Settings` e iniettare nelle funzioni di dominio come parametro, non come costante globale.

---

### 4. `repositories/json_repo.py` — NUOVO (consolidamento)

**Stato attuale:** `loadjson` e `savejson` con FileLock sono definiti **due volte**: in `main.py` e implicitamente anche in `core/classifier.py` (che usa direttamente `open` + FileLock). Stessa logica duplicata.

**Refactoring proposto:**

```python
# repositories/json_repo.py
import json, os, logging
from pathlib import Path
from filelock import FileLock
from typing import Any

logger = logging.getLogger(__name__)

def load_json(path: Path | str, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default if default is not None else {}
    lock = FileLock(str(path) + ".lock")
    with lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Errore lettura %s: %s", path, e)
            return default if default is not None else {}

def save_json(path: Path | str, data: Any) -> bool:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock")
    with lock:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            logger.error("Errore scrittura %s: %s", path, e)
            return False
```

**Note di migrazione:** sostituire tutte le occorrenze di `loadjson`/`savejson` locali con import da qui. Rimuovere le implementazioni duplicate.

---

### 5. `repositories/parquet_repo.py` — NUOVO (consolidamento)

**Stato attuale:** la logica di lettura/scrittura Parquet è inline in `core/ingestion.py` e `core/pmingestion.py` con dedup logic inclusa. Difficile da testare e da riusare.

**Refactoring proposto:**

```python
# repositories/parquet_repo.py
import pandas as pd
import logging
from pathlib import Path
from filelock import FileLock

logger = logging.getLogger(__name__)

class ParquetRepository:
    def __init__(self, path: Path, dedup_keys: list[str] = None):
        self.path = path
        self.dedup_keys = dedup_keys or []
        self._lock = FileLock(str(path) + ".lock")

    def read(self) -> pd.DataFrame | None:
        if not self.path.exists():
            return None
        with self._lock:
            try:
                return pd.read_parquet(self.path)
            except Exception as e:
                logger.error("Errore lettura parquet %s: %s", self.path, e)
                return None

    def append(self, new_rows: pd.DataFrame) -> int:
        """Aggiunge righe con dedup. Ritorna il numero di righe aggiunte."""
        with self._lock:
            try:
                existing = self.read()
                combined = pd.concat([existing, new_rows], ignore_index=True) \
                           if existing is not None else new_rows.copy()
                before = len(combined)
                actual_keys = [k for k in self.dedup_keys if k in combined.columns]
                if actual_keys:
                    combined = combined.drop_duplicates(subset=actual_keys, keep="first")
                added = len(combined) - (len(existing) if existing is not None else 0)
                self.path.parent.mkdir(parents=True, exist_ok=True)
                combined.to_parquet(self.path, index=False, engine="pyarrow", compression="snappy")
                logger.info("Parquet aggiornato: %d record totali (+%d nuovi)", len(combined), added)
                return max(0, added)
            except Exception as e:
                logger.error("Errore scrittura parquet %s: %s", self.path, e)
                return 0

    def filter_by_site(self, site_name: str, col: str = "ME") -> pd.DataFrame | None:
        df = self.read()
        if df is None or df.empty:
            return None
        mask = df[col].astype(str).str.contains(site_name, na=False, regex=False)
        result = df[mask].copy()
        return result if not result.empty else None

    def get_status(self, date_col: str = "OccurrenceTime") -> dict:
        df = self.read()
        if df is None:
            return {"available": False, "total_rows": 0}
        date_from = date_to = None
        if date_col in df.columns:
            valid = pd.to_datetime(df[date_col], errors="coerce").dropna()
            if not valid.empty:
                date_from, date_to = str(valid.min().date()), str(valid.max().date())
        return {"available": True, "total_rows": len(df),
                "date_from": date_from, "date_to": date_to}
```

**Note di migrazione:** istanziare `ParquetRepository` nei service layer, passando path e dedup_keys da `settings`. I moduli `core/ingestion.py` e `core/pmingestion.py` continuano a funzionare durante la migrazione, poi vengono svuotati progressivamente.

---

### 6. `repositories/excel_repo.py` — NUOVO

**Stato attuale:** `pd.read_excel` viene chiamato direttamente in più punti (ingestion, pmingestion, WorkflowMWTroubleshootingZTE). Nessuna validazione centralizzata del contenuto.

**Refactoring proposto:**

```python
# repositories/excel_repo.py
import pandas as pd
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

REQUIRED_ALARM_COLS = {"Alarm Code Name", "Alarm Severity", "Occurrence Time", "ME"}
REQUIRED_PM_COLS    = {"ME", "ME IP", "PM Checkpoint", "Begin Time"}

def read_alarm_excel(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl")
    missing = REQUIRED_ALARM_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Colonne mancanti nel file allarmi: {missing}")
    return df

def read_pm_excel(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl")
    missing = REQUIRED_PM_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Colonne mancanti nel file PM: {missing}")
    return df
```

**Note di migrazione:** usare queste funzioni nei service layer. Le eccezioni `ValueError` vengono già gestite negli endpoint (`except ValueError as ve → HTTP 400`).

---

### 7. `utils/files.py` — NUOVO (sicurezza upload)

**Stato attuale:** in `main.py` i file vengono salvati con `file.filename` originale in `uploads/`. Nessuna sanificazione del nome, nessun controllo dimensione, nessun cleanup.

**Refactoring proposto:**

```python
# utils/files.py
import uuid, shutil, logging
from pathlib import Path
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)
MAX_UPLOAD_MB = 50

def safe_save(upload: UploadFile, dest_dir: Path, prefix: str = "") -> Path:
    """Salva un file upload con nome randomizzato. Ritorna il path salvato."""
    # Controllo MIME / estensione
    if not upload.filename or not upload.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400,
            detail=f"Formato non supportato: {upload.filename}. Usa .xls o .xlsx")
    # Nome sicuro randomizzato
    ext = Path(upload.filename).suffix.lower()
    safe_name = f"{prefix}{uuid.uuid4().hex}{ext}"
    dest = dest_dir / safe_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Controllo dimensione (50 MB max)
    size = 0
    with open(dest, "wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413,
                    detail=f"File troppo grande (max {MAX_UPLOAD_MB} MB)")
            out.write(chunk)
    logger.info("File salvato: %s (%d KB)", dest, size // 1024)
    return dest

def cleanup_upload(path: Path):
    try:
        path.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Cleanup fallito per %s: %s", path, e)
```

**Note di migrazione:** sostituire tutti i blocchi `with open(filepath, "wb") as buffer: shutil.copyfileobj(file.file, buffer)` in `main.py` con `safe_save(file, settings.upload_dir)`.

---

### 8. `utils/cache.py` — NUOVO (TTL Cache generica)

**Stato attuale:** esiste già una cache artigianale per PM status in `main.py`:
```python
pm_status_cache = {"data": None, "ts": 0}
def get_cached_pm_status():
    now = time.time()
    if pm_status_cache["data"] is None or now - pm_status_cache["ts"] > 300:
        ...
```
Non è riusabile, non è type-safe, non è testabile.

**Refactoring proposto:**

```python
# utils/cache.py
import time
from typing import Any, Callable

class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._data: Any = None
        self._ts: float = 0.0

    def get(self, loader: Callable) -> Any:
        now = time.time()
        if self._data is None or (now - self._ts) > self._ttl:
            self._data = loader()
            self._ts = now
        return self._data

    def invalidate(self):
        self._data = None
        self._ts = 0.0
```

**Uso:**
```python
_pm_cache = TTLCache(ttl_seconds=settings.pm_cache_ttl_seconds)

def get_cached_pm_status() -> dict:
    return _pm_cache.get(lambda: get_pm_status())
```

---

### 9. `schemas/` — NUOVO (modelli Pydantic centralizzati)

**Stato attuale:** i modelli Pydantic (`AlarmRule`, `WizardPayload`, `UpdateRulePayload`) sono definiti inline in `main.py`. Le risposte non hanno schema formale.

**Refactoring proposto:**

```python
# schemas/alarms.py
from pydantic import BaseModel
from typing import Optional, Literal

ActionType = Literal["TRASCURABILE", "MONITORA", "SCALA", "INVESTIGATE"]

class AlarmRule(BaseModel):
    alarm_code_name: str
    operator_action: ActionType
    note: Optional[str] = None

class WizardPayload(BaseModel):
    rules: list[AlarmRule]

class UpdateRulePayload(BaseModel):
    alarm_code_name: str
    operator_action: ActionType
    note: Optional[str] = None
    new_alarm_entry: Optional[dict] = None

# schemas/common.py
class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    message: str
    alarm_kb_exists: bool
    operator_kb_exists: bool
```

---

### 10. `api/alarms.py` — Router allarmi FM

**Stato attuale:** gli endpoint `/api/upload`, `/api/last-session`, `/api/alarms-status` sono in `main.py` insieme a tutto il resto.

**Refactoring proposto:**

```python
# api/alarms.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from services.alarm_service import AlarmService
from schemas.common import StatusResponse

router = APIRouter(tags=["Alarms FM"])
_service = AlarmService()

@router.post("/upload")
async def upload_alarms(files: list[UploadFile] = File(...)):
    return await _service.process_uploads(files)

@router.get("/alarms-status")
def alarms_status():
    return _service.get_status()

@router.get("/last-session")
def get_last_session():
    return _service.get_last_session()

@router.delete("/last-session")
def clear_last_session():
    return _service.clear_last_session()
```

Gli endpoint rimangono **identici** per il frontend. Solo la logica si sposta nel service.

---

### 11. `api/performance.py` — Router Performance MW

**Stato attuale:** `getperformance` in `main.py` importa `WorkflowMWTroubleshootingZTE` con `importlib.reload` ad ogni chiamata (per evitare caching del modulo). Questo è un workaround rischioso.

**Refactoring proposto:**

```python
# api/performance.py
from fastapi import APIRouter
from typing import Optional
from services.pm_service import PMService

router = APIRouter(tags=["Performance MW"])
_service = PMService()

@router.post("/upload-performance")
async def upload_performance(files: list[UploadFile] = File(...)):
    return await _service.process_uploads(files)

@router.get("/performance/status")
def performance_status():
    return _service.get_status()

@router.get("/performance/{site_name}")
def get_performance(site_name: str,
                    date_from: Optional[str] = None,
                    date_to: Optional[str] = None,
                    freq_ghz: float = 13.0):
    return _service.analyze_site(site_name, date_from, date_to, freq_ghz)
```

Il `importlib.reload` va rimosso: il modulo `WorkflowMWTroubleshootingZTE` deve essere importato una volta all'avvio tramite `troubleshooting_service.py`.

---

### 12. `services/alarm_service.py` — NUOVO

**Stato attuale:** la logica di "upload → salvataggio → classificazione → sessione → nuovi allarmi" è inline nell'endpoint `/api/upload`.

**Struttura proposta:**

```python
# services/alarm_service.py
class AlarmService:
    def __init__(self):
        self._repo = ParquetRepository(settings.parquet_alarms_path, DEDUP_KEYS)
        self._session_path = settings.data_dir / "last_session.json"

    async def process_uploads(self, files: list[UploadFile]) -> dict:
        all_alarms, all_new = [], []
        for file in files:
            path = safe_save(file, settings.upload_dir, prefix="fm_")
            try:
                results = process_excel(str(path))  # core/ingestion esistente
                all_alarms.extend(results.get("alarms", []))
                all_new.extend(results.get("new_alarms", []))
            finally:
                cleanup_upload(path)   # ← cleanup automatico
        combined = {"alarms": all_alarms, "new_alarms": all_new, ...}
        save_json(self._session_path, combined)
        return {"status": "success", "data": combined}

    def get_status(self) -> dict:
        return self._repo.get_status()

    def get_last_session(self) -> dict:
        data = load_json(self._session_path)
        return {"available": bool(data), "data": data}

    def clear_last_session(self):
        self._session_path.unlink(missing_ok=True)
        return {"status": "ok"}
```

---

### 13. `core/classifier.py` — Riduzione responsabilità

**Stato attuale:** fa tutto: carica KB, gestisce cache in-memory, classifica riga per riga con priorità operatore > KB > regole base. È il modulo più critico e attualmente non ha test.

**Refactoring:**
- Separare la **logica di classificazione pura** (la funzione `row_eval`) in `domain/alarm_rules.py`
- Mantenere in `core/classifier.py` solo il caricamento KB con cache e l'applicazione bulk
- Testare `domain/alarm_rules.py` indipendentemente dall'I/O

```python
# domain/alarm_rules.py — logica pura, zero I/O, testabile
def classify_single_alarm(
    alarm_name: str,
    severity: str,
    occurrence_time,
    topology_role: str,
    known_alarm_names: set[str],
    alarm_profiles: dict,
    operator_rules: dict,
    chronic_days: int = 21,
    dataset_now = None,
) -> tuple[str, bool, bool, bool, bool, list | None]:
    """
    Ritorna: (action, is_chronic, is_new, is_structural, operator_override, solution)
    Pura funzione — nessun I/O, nessuna dipendenza esterna.
    """
    ...
```

Questo permette di scrivere test come:
```python
# tests/test_alarm_rules.py
def test_escalate_critical():
    action, *_ = classify_single_alarm("CPU usage", "CRITICAL", ...)
    assert action == "ESCALATE"

def test_operator_override_tolerable():
    action, *_, override = classify_single_alarm(
        "CPU usage", "CRITICAL", ...,
        operator_rules={"CPU usage": {"operator_action": "TRASCURABILE"}}
    )
    assert action == "TOLERABLE"
    assert override is True
```

---

### 14. `domain/pm_rules.py` — Logica diagnosi radio isolata

**Stato attuale:** `build_conclusions`, `analyze_site_stats`, `compute_downshift_column`, `extract_degradation_windows`, `get_outcome` sono tutti in `WorkflowMWTroubleshootingZTE.py` (file autonomo), non in `core/`. Sono funzioni eccellenti ma non testabili in isolamento facilmente.

**Refactoring:**
- Spostare le soglie da costanti hardcoded a parametri con default da `thresholds.yml`
- Creare `domain/pm_rules.py` come facade delle funzioni pure
- `WorkflowMWTroubleshootingZTE.py` resta per il CLI e il PPTX standalone, ma le funzioni di analisi vengono importate da `domain/pm_rules.py`

```python
# domain/pm_rules.py
from dataclasses import dataclass
from config.settings import settings
import yaml

def load_thresholds() -> dict:
    p = settings.base_dir / "config" / "thresholds.yml"
    with open(p) as f:
        return yaml.safe_load(f)

@dataclass
class PMThresholds:
    rsl_fading: float = -63.0
    rsl_nominal: float = -60.0
    xpi_critical: float = 20.0
    mse_interference: float = -35.0
    delta_if_cable: float = 0.8

    @classmethod
    def from_config(cls) -> "PMThresholds":
        t = load_thresholds().get("pm_radio", {})
        return cls(
            rsl_fading=t.get("rsl_fading_threshold_dbm", cls.rsl_fading),
            ...
        )
```

---

### 15. `core/audit.py` → `services/audit_service.py`

**Stato attuale:** `core/audit.py` è già ben separato (solo ~25 righe). L'unico miglioramento è spostarlo in `services/` per coerenza architetturale e usare `json_repo.py` invece di `open` diretto.

**Migrazione:** semplice copia + refactoring degli import. Nessuna breaking change.

---

## Piano di Migrazione Incrementale

Il refactoring può avvenire in 5 sprint da 2-3 giorni ciascuno, senza interrompere il funzionamento:

| Sprint | File toccati | Rischio | Verificabile con |
|--------|-------------|---------|-----------------|
| 1 | `config/settings.py`, `config/thresholds.yml` | Basso | Avvio app senza errori |
| 2 | `repositories/json_repo.py`, `repositories/parquet_repo.py` | Basso | Upload + status funzionanti |
| 3 | `utils/files.py`, `utils/cache.py`, `schemas/` | Basso | Upload sicuro + /health |
| 4 | `api/`, `services/` (svuota `main.py`) | Medio | Tutti gli endpoint esistenti |
| 5 | `domain/alarm_rules.py`, `domain/pm_rules.py` + test | Medio | Suite test green |

**Regola aurea:** ogni sprint lascia il sistema funzionante e deployabile. I `core/` esistenti restano attivi durante la transizione e vengono svuotati solo quando il relativo service/domain è stabile e testato.

---

*Fine documento refactoring backend*
