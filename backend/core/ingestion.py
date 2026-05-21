"""
ingestion.py
=============
Legge il file Excel giornaliero, normalizza, classifica e aggiorna lo storico.
"""

import pandas as pd
import ipaddress
import os
import json
import logging
from datetime import datetime
from .classifier import classify_alarms, reload_kb

logger = logging.getLogger(__name__)

# ── Percorsi ──────────────────────────────────────────────────────────────────
_BACKEND_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR       = os.path.join(_BACKEND_DIR, 'data')
_DATI_DIR       = os.path.join(_BACKEND_DIR, '..', 'DATI')
PARQUET_PATH    = os.path.join(_DATI_DIR, 'history_db.parquet')
ALARM_KB_PATH   = os.path.join(_DATA_DIR, 'alarm_kb.json')
OPERATOR_KB_PATH = os.path.join(_DATA_DIR, 'operator_kb.json')


# ─────────────────────────────────────────────────────────────────────────────
#  Utility
# ─────────────────────────────────────────────────────────────────────────────

def get_subnet_28(ip_str: str) -> str | None:
    try:
        net = ipaddress.IPv4Network(f"{ip_str}/28", strict=False)
        return str(net)
    except Exception:
        return None

def _ip_offset(ip_str: str) -> int:
    try:
        return int(ipaddress.IPv4Address(ip_str))
    except:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
#  Aggiornamento incrementale dello storico
# ─────────────────────────────────────────────────────────────────────────────

def _update_history(daily_df: pd.DataFrame):
    """
    Appende i nuovi record del file giornaliero al Parquet storico.
    Normalizza i nomi colonna per compatibilità con il Parquet.
    Poi aggiorna alarm_kb.json in modo incrementale.
    """
    # Mappa colonne daily → colonne Parquet
    col_map = {
        'ME':              'ME',
        'ME IP':           'ME_IP',
        'Alarm Code Name': 'Alarm_Code_Name',
        'Alarm Code':      'Alarm_Code',
        'Alarm Severity':  'Alarm_Severity',
        'Occurrence Time': 'Occurrence_Time',
        'Specific Problem':'Specific_Problem',
        'Ack State':       'Ack_State',
        'Clear State':     'Clear_State',
        'ME Level':        'ME_Level',
        'Repeat Count':    'Repeat_Count',
        'Alarm Type':      'Alarm_Type',
        'MOC':             'MOC',
        'ME ID':           'ME_ID',
    }

    # Crea subset normalizzato
    new_rows = daily_df.rename(columns=col_map).copy()
    keep_cols = list(col_map.values())
    keep_cols = [c for c in keep_cols if c in new_rows.columns]
    new_rows = new_rows[keep_cols]

    # Aggiungi Subnet_28 se ME_IP disponibile
    if 'ME_IP' in new_rows.columns:
        new_rows['Subnet_28'] = new_rows['ME_IP'].astype(str).apply(get_subnet_28)

    new_rows['source_file'] = f'daily_{datetime.now().strftime("%Y%m%d")}'

    # Parse datetime
    if 'Occurrence_Time' in new_rows.columns:
        new_rows['Occurrence_Time'] = pd.to_datetime(new_rows['Occurrence_Time'], errors='coerce')

    DEDUP_KEYS = ['ME', 'Alarm_Code_Name', 'Occurrence_Time']

    try:
        if os.path.exists(PARQUET_PATH):
            existing = pd.read_parquet(PARQUET_PATH)
            combined = pd.concat([existing, new_rows], ignore_index=True)
        else:
            os.makedirs(os.path.dirname(PARQUET_PATH), exist_ok=True)
            combined = new_rows

        dedup_keys_exist = [k for k in DEDUP_KEYS if k in combined.columns]
        if dedup_keys_exist:
            combined = combined.drop_duplicates(subset=dedup_keys_exist, keep='first')

        combined.to_parquet(PARQUET_PATH, index=False, engine='pyarrow', compression='snappy')
        logger.info("Storico aggiornato: %d record totali", len(combined))

        # Aggiornamento incrementale KB
        _update_kb_incremental(new_rows, combined)

    except Exception as e:
        logger.error("Errore aggiornamento storico: %s", e)


def _update_kb_incremental(new_rows: pd.DataFrame, full_df: pd.DataFrame):
    """
    Aggiornamento leggero della KB: solo i profili toccati dai nuovi dati.
    """
    try:
        if not os.path.exists(ALARM_KB_PATH):
            return

        with open(ALARM_KB_PATH, 'r', encoding='utf-8') as f:
            kb = json.load(f)

        alarm_profiles = kb.get('alarm_profiles', {})
        me_profiles    = kb.get('me_profiles', {})
        threshold      = kb.get('filterability_threshold', 0.85)

        max_occ = max((v['total_occurrences'] for v in alarm_profiles.values()), default=1)
        max_me  = max((v['affected_me_count']  for v in alarm_profiles.values()), default=1)

        # Aggiorna solo i tipi di allarme presenti nel file giornaliero
        if 'Alarm_Code_Name' in new_rows.columns:
            for alarm_name in new_rows['Alarm_Code_Name'].dropna().unique():
                if alarm_name not in alarm_profiles:
                    # Allarme NUOVO: crea profilo minimo
                    alarm_profiles[alarm_name] = {
                        'total_occurrences':   0,
                        'affected_me_count':   0,
                        'main_severity':       'UNKNOWN',
                        'filterability_score': 0.0,
                        'is_structural':       False,
                        'chronic_me_list':     [],
                        'suggested_action':    'INVESTIGATE',
                        'suggested_reason':    'Allarme mai visto nello storico',
                    }

                # Aggiorna con conteggi dal full_df
                if 'Alarm_Code_Name' in full_df.columns:
                    subset = full_df[full_df['Alarm_Code_Name'] == alarm_name]
                    total_occ   = len(subset)
                    affected_me = subset['ME'].nunique() if 'ME' in subset.columns else 0
                    main_sev    = (
                        subset['Alarm_Severity'].value_counts().index[0]
                        if 'Alarm_Severity' in subset.columns and len(subset) > 0
                        else alarm_profiles[alarm_name].get('main_severity', 'UNKNOWN')
                    )
                    max_occ = max(max_occ, total_occ)
                    max_me  = max(max_me,  affected_me)
                    score   = round(
                        0.6 * (total_occ / max_occ) + 0.4 * (affected_me / max_me), 4
                    )
                    is_structural = score >= threshold and affected_me >= 10

                    alarm_profiles[alarm_name].update({
                        'total_occurrences':   total_occ,
                        'affected_me_count':   affected_me,
                        'main_severity':       str(main_sev),
                        'filterability_score': score,
                        'is_structural':       is_structural,
                    })

        # Aggiorna ME profiles per i NE nel file giornaliero
        if 'ME' in new_rows.columns:
            for me_name in new_rows['ME'].dropna().unique():
                if 'ME' in full_df.columns:
                    me_g = full_df[full_df['ME'] == me_name]
                    total = len(me_g)
                    unique_types = me_g['Alarm_Code_Name'].nunique() if 'Alarm_Code_Name' in me_g.columns else 0
                    top_alarm = None
                    if 'Alarm_Code_Name' in me_g.columns and total > 0:
                        top_alarm = me_g['Alarm_Code_Name'].value_counts().index[0]
                    me_profiles[me_name] = {
                        'total_alarms_20d':    total,
                        'unique_alarm_types':  unique_types,
                        'top_alarm':           top_alarm,
                        'risk_score':          min(total / 500, 1.0),
                        'chronic_alarm_count': me_profiles.get(me_name, {}).get('chronic_alarm_count', 0),
                        'chronic_alarm_types': me_profiles.get(me_name, {}).get('chronic_alarm_types', []),
                    }

        kb['alarm_profiles'] = alarm_profiles
        kb['me_profiles']    = me_profiles
        kb['last_updated']   = datetime.now().isoformat()
        kb['total_events']   = len(full_df)

        with open(ALARM_KB_PATH, 'w', encoding='utf-8') as f:
            json.dump(kb, f, ensure_ascii=False, indent=2, default=str)

        # Invalida cache in memoria del classifier
        reload_kb()
        logger.info("alarm_kb.json aggiornato incrementalmente")

    except Exception as e:
        logger.error("Errore aggiornamento KB incrementale: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point principale
# ─────────────────────────────────────────────────────────────────────────────

def process_excel(file_path: str) -> dict:
    # 1. Leggi Excel
    df = pd.read_excel(file_path, engine='openpyxl')

    # 2. Filtro ME che iniziano con "X"
    if 'ME' in df.columns:
        df['ME'] = df['ME'].astype(str).str.strip()
        df = df[~df['ME'].str.startswith('X', na=False)].copy()

    # 3. Topology Pairing — device-type aware
    #    NR9250   (P2P):  2 IPs/subnet → ip[0]=Local(A),  ip[1]=Remote(B)
    #    ER2020E  (Eband):4 IPs/subnet → ip[0,1]=Local(A),ip[2,3]=Remote(B)
    #    Multiband/other: fallback progressivo
    if 'ME IP' in df.columns:
        df['ME IP'] = df['ME IP'].astype(str).str.strip()
        df['Subnet_28'] = df['ME IP'].apply(get_subnet_28)

        topology_map = {}   # ip → Topology_Role string
        link_type_map = {}  # ip → Link_Type string

        for subnet, group in df.groupby('Subnet_28'):
            if not subnet:
                continue
            unique_ips = sorted(
                [ip for ip in group['ME IP'].unique() if ip and ip != 'nan'],
                key=lambda x: _ip_offset(x)   # ordina per offset nella /28
            )
            n = len(unique_ips)

            if n == 2:
                # NR9250 standard P2P
                topology_map[unique_ips[0]] = 'Local (Site A)'
                topology_map[unique_ips[1]] = 'Remote (Site B)'
                for ip in unique_ips:
                    link_type_map[ip] = 'NR9250'

            elif n == 4:
                # Eband ER2020E: +1,+2 = Local; +3,+4 = Remote
                topology_map[unique_ips[0]] = 'Local (Site A)'
                topology_map[unique_ips[1]] = 'Local (Site A)'
                topology_map[unique_ips[2]] = 'Remote (Site B)'
                topology_map[unique_ips[3]] = 'Remote (Site B)'
                for ip in unique_ips:
                    link_type_map[ip] = 'ER2020E'

            elif n == 1:
                topology_map[unique_ips[0]] = 'Standalone'
                link_type_map[unique_ips[0]] = 'Unknown'

            else:
                # Multiband o configurazione non standard → numerazione progressiva
                for idx, ip in enumerate(unique_ips):
                    if idx == 0:
                        topology_map[ip] = 'Local (Site A)'
                    elif idx == 1:
                        topology_map[ip] = 'Remote (Site B)'
                    else:
                        topology_map[ip] = f'Node {idx + 1}'
                    link_type_map[ip] = 'Multiband'

        df['Topology_Role'] = df['ME IP'].map(topology_map).fillna('Unknown')
        df['Link_Type']     = df['ME IP'].map(link_type_map).fillna('Unknown')

    # 4. Parse timestamp
    if 'Occurrence Time' in df.columns:
        df['Occurrence Time'] = pd.to_datetime(df['Occurrence Time'], errors='coerce')

    # 5. Classificazione con KB + preferenze operatore
    results_df = classify_alarms(df)

    # 6. Aggiorna storico in background (non bloccante)
    try:
        _update_history(df)
    except Exception as e:
        logger.warning("Aggiornamento storico fallito (non critico): %s", e)

    # 7. Formatta output per il frontend
    if 'Occurrence Time' in results_df.columns:
        results_df['Occurrence Time'] = results_df['Occurrence Time'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # Colonne da inviare al frontend
    columns_to_keep = [
        'Action', 'Is_Chronic', 'Is_New_Alarm', 'Is_Structural', 'Operator_Override',
        'Suggested_Solution', 'ME', 'Topology_Role', 'ME IP', 'Link_Type',
        'Alarm Code Name', 'Alarm Severity', 'Occurrence Time'
    ]
    # Serializzazione JSON-safe
    results_df = results_df.fillna('')
    if 'Suggested_Solution' in results_df.columns:
        results_df['Suggested_Solution'] = results_df['Suggested_Solution'].apply(
            lambda x: x if isinstance(x, list) else []
        )

    all_records = results_df.to_dict(orient='records')
    records = []
    for r in all_records:
        frontend_rec = {c: r.get(c, '') for c in columns_to_keep}
        frontend_rec['Raw_Data'] = {k: str(v) for k, v in r.items() if str(v) != ''}
        records.append(frontend_rec)

    # Separa nuovi allarmi
    new_alarms = [r for r in records if r.get('Is_New_Alarm') and r.get('Action') in ('ESCALATE', 'MONITOR', 'INVESTIGATE')]

    # Statistiche
    stats = {
        'total':   len(records),
        'new_alarms_count': len(new_alarms),
        'categories': {
            'Tolerable':              sum(1 for r in records if r.get('Action') == 'TOLERABLE'),
            'Monitor':                sum(1 for r in records if r.get('Action') == 'MONITOR'),
            'Escalate':               sum(1 for r in records if r.get('Action') == 'ESCALATE'),
            'Investigate':            sum(1 for r in records if r.get('Action') == 'INVESTIGATE'),
            'Chronic_Feedback_Needed': sum(1 for r in records if r.get('Is_Chronic')),
            'Structural':             sum(1 for r in records if r.get('Is_Structural')),
            'New':                    len(new_alarms),
        }
    }

    return {
        'stats':      stats,
        'alarms':     records,
        'new_alarms': new_alarms,
    }
