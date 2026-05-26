"""
classifier.py
==============
Motore di classificazione allarmi con supporto KB storica e preferenze operatore.

Priorità regole:
  1. Preferenza operatore (operator_kb.json) → override assoluto
  2. KB storica (alarm_kb.json) → allarmi strutturali → TOLERABLE
  3. Regole business base (severity + topologia)
"""

import pandas as pd
import json
import os
import logging
from datetime import datetime
from filelock import FileLock
from .solutions import get_solution

logger = logging.getLogger(__name__)

# ── Percorsi KB ────────────────────────────────────────────────────────────────
_DATA_DIR    = os.path.join(os.path.dirname(__file__), '..', 'data')
ALARM_KB_PATH    = os.path.join(_DATA_DIR, 'alarm_kb.json')
OPERATOR_KB_PATH = os.path.join(_DATA_DIR, 'operator_kb.json')

# ── Cache in memoria (ricaricata se il file è più recente) ────────────────────
_alarm_kb_cache    = None
_alarm_kb_mtime    = 0
_operator_kb_cache = None
_operator_kb_mtime = 0

FILTERABILITY_THRESHOLD = 0.85
CHRONIC_DAYS            = 21


# ─────────────────────────────────────────────────────────────────────────────
#  Caricamento KB
# ─────────────────────────────────────────────────────────────────────────────

def _load_alarm_kb() -> dict:
    global _alarm_kb_cache, _alarm_kb_mtime
    if not os.path.exists(ALARM_KB_PATH):
        return {}
    lock = FileLock(ALARM_KB_PATH + ".lock")
    with lock:
        mtime = os.path.getmtime(ALARM_KB_PATH)
        if _alarm_kb_cache is None or mtime > _alarm_kb_mtime:
            try:
                with open(ALARM_KB_PATH, 'r', encoding='utf-8') as f:
                    _alarm_kb_cache = json.load(f)
                _alarm_kb_mtime = mtime
                logger.info("alarm_kb.json caricato: %d profili allarme",
                            len(_alarm_kb_cache.get('alarm_profiles', {})))
            except Exception as e:
                logger.error("Errore caricamento alarm_kb.json: %s", e)
                _alarm_kb_cache = {}
    return _alarm_kb_cache


def _load_operator_kb() -> dict:
    global _operator_kb_cache, _operator_kb_mtime
    if not os.path.exists(OPERATOR_KB_PATH):
        return _default_operator_kb()
    lock = FileLock(OPERATOR_KB_PATH + ".lock")
    with lock:
        mtime = os.path.getmtime(OPERATOR_KB_PATH)
        if _operator_kb_cache is None or mtime > _operator_kb_mtime:
            try:
                with open(OPERATOR_KB_PATH, 'r', encoding='utf-8') as f:
                    _operator_kb_cache = json.load(f)
                _operator_kb_mtime = mtime
            except Exception as e:
                logger.error("Errore caricamento operator_kb.json: %s", e)
                _operator_kb_cache = _default_operator_kb()
    return _operator_kb_cache


def _default_operator_kb() -> dict:
    return {
        "wizard_completed": False,
        "wizard_completed_at": None,
        "operator_rules": {},
        "new_alarm_history": [],
    }


def reload_kb():
    """Forza il ricaricamento delle KB (chiamato dopo aggiornamenti)."""
    global _alarm_kb_cache, _operator_kb_cache
    _alarm_kb_cache    = None
    _operator_kb_cache = None


# ─────────────────────────────────────────────────────────────────────────────
#  Funzione principale di classificazione
# ─────────────────────────────────────────────────────────────────────────────

def classify_alarms(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica il DataFrame di allarmi e aggiunge le colonne:
      - Action:             ESCALATE / MONITOR / TOLERABLE / INVESTIGATE
      - Is_Chronic:         bool (allarme vecchio >21gg)
      - Is_New_Alarm:       bool (mai visto nello storico)
      - Is_Structural:      bool (allarme strutturale da KB)
      - Operator_Override:  bool (classificato dall'operatore)
      - Suggested_Solution: list[str] | None
    """
    alarm_kb    = _load_alarm_kb()
    operator_kb = _load_operator_kb()

    alarm_profiles  = alarm_kb.get('alarm_profiles', {})
    operator_rules  = operator_kb.get('operator_rules', {})

    # Data di riferimento per calcolo età allarmi
    if 'Occurrence Time' in df.columns and not df['Occurrence Time'].dropna().empty:
        dataset_now = df['Occurrence Time'].max()
    else:
        dataset_now = datetime.now()

    # Set di nomi allarmi presenti nello storico (per Is_New_Alarm)
    known_alarm_names = set(alarm_profiles.keys())

    def row_eval(row):
        alarm_name = str(row.get('Alarm Code Name', '')).strip()
        severity   = str(row.get('Alarm Severity',  '')).strip().upper()
        topology   = str(row.get('Topology_Role',   ''))
        occ_time   = row.get('Occurrence Time')

        action           = 'INVESTIGATE'
        is_chronic       = False
        is_new_alarm     = alarm_name not in known_alarm_names
        is_structural    = False
        operator_override = False
        suggested_solution = None

        # ── 1. Controllo cronicità (allarme vecchio >21gg) ────────────────────
        if pd.notnull(occ_time):
            age_days = (dataset_now - occ_time).days
            if age_days >= CHRONIC_DAYS:
                is_chronic = True

        # ── 2. Preferenza operatore (override assoluto) ────────────────────────
        if alarm_name in operator_rules:
            op_action = operator_rules[alarm_name].get('operator_action', '').upper()
            if op_action in ('TRASCURABILE', 'IGNORE'):
                action = 'TOLERABLE'
            elif op_action in ('SCALA', 'ESCALATE'):
                action = 'ESCALATE'
                suggested_solution = get_solution(alarm_name)
            elif op_action in ('MONITORA', 'MONITOR'):
                action = 'MONITOR'
                suggested_solution = get_solution(alarm_name)
            operator_override = True
            return action, is_chronic, is_new_alarm, is_structural, operator_override, suggested_solution

        # ── 3. KB storica: allarme strutturale → TOLERABLE ────────────────────
        if alarm_name in alarm_profiles:
            profile = alarm_profiles[alarm_name]
            if profile.get('is_structural', False):
                is_structural = True
                action = 'TOLERABLE'
                return action, is_chronic, is_new_alarm, is_structural, operator_override, suggested_solution

        # ── 4. Regole business base ────────────────────────────────────────────
        if is_chronic:
            # Allarme cronico ma non strutturale: teniamo l'azione ma abbasso
            # la priorità rispetto a uno recente della stessa severity
            action = 'TOLERABLE'
        elif severity == 'CRITICAL':
            action = 'ESCALATE'
        elif severity == 'MAJOR':
            action = 'ESCALATE'
        elif severity == 'MINOR':
            action = 'MONITOR'
        elif severity == 'WARNING':
            action = 'TOLERABLE'
        else:
            action = 'TOLERABLE'

        # ── 5. Propagazione RF: Remote Site B con allarme RX → abbassa priorità
        if topology == 'Remote (Site B)' and 'RX' in alarm_name.upper():
            if action == 'ESCALATE':
                action = 'MONITOR'

        # ── 6. Aggiungi soluzione per allarmi che richiedono attenzione ─────────
        if action in ('ESCALATE', 'MONITOR') or is_new_alarm:
            suggested_solution = get_solution(alarm_name)

        return action, is_chronic, is_new_alarm, is_structural, operator_override, suggested_solution

    # ── Applica la funzione ────────────────────────────────────────────────────
    results = df.apply(row_eval, axis=1, result_type='expand')
    results.columns = ['Action', 'Is_Chronic', 'Is_New_Alarm', 'Is_Structural',
                       'Operator_Override', 'Suggested_Solution']
    df = pd.concat([df, results], axis=1)

    # ── Ordinamento: prima Escalate, poi Monitor, poi Tolerable ───────────────
    sort_map = {'ESCALATE': 0, 'INVESTIGATE': 1, 'MONITOR': 2, 'TOLERABLE': 3}
    df['_SortKey'] = df['Action'].map(sort_map).fillna(4)
    df = df.sort_values(
        by=['Is_New_Alarm', '_SortKey', 'Is_Chronic', 'Occurrence Time'],
        ascending=[False, True, True, False]
    )
    df = df.drop(columns=['_SortKey'])

    return df
