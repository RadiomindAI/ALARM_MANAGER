# repositories/json_repo.py
import json
import logging
from pathlib import Path
from filelock import FileLock
from typing import Any

logger = logging.getLogger(__name__)

def load_json(path: Path | str, default: Any = None) -> Any:
    """
    Carica in modo sicuro un file JSON utilizzando un FileLock concorrente.
    """
    path = Path(path)
    if not path.exists():
        return default if default is not None else {}
        
    lock_path = str(path) + ".lock"
    lock = FileLock(lock_path)
    with lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Errore durante la lettura del file JSON %s: %s", path, e)
            return default if default is not None else {}

def save_json(path: Path | str, data: Any) -> bool:
    """
    Salva in modo sicuro dati in formato JSON utilizzando un FileLock concorrente.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    lock_path = str(path) + ".lock"
    lock = FileLock(lock_path)
    with lock:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            logger.error("Errore durante la scrittura del file JSON %s: %s", path, e)
            return False
