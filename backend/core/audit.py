import os
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BACKEND_DIR, 'data')
FEEDBACK_LOG_PATH = os.path.join(_DATA_DIR, 'feedback_log.json')

def log_feedback(event_type: str, **kwargs):
    """
    Registra un evento di feedback umano nel log persistente.
    """
    try:
        if os.path.exists(FEEDBACK_LOG_PATH):
            with open(FEEDBACK_LOG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {"events": []}
            
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
        }
        event.update(kwargs)
        
        data["events"].append(event)
        
        with open(FEEDBACK_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"Errore scrittura audit log: {e}")
