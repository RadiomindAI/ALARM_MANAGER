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
from filelock import FileLock
from .classifier import classify_alarms, reload_kb

logger = logging.getLogger(__name__)

# ── Percorsi ──────────────────────────────────────────────────────────────────
_BACKEND_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR       = os.path.join(_BACKEND_DIR, 'data')
_DATI_DIR       = os.path.join(_BACKEND_DIR, '..', 'DATI')
PARQUET_PATH    = os.path.join(_DATI_DIR, 'history_db.parquet')
ALARM_KB_PATH   = os.path.join(_DATA_DIR, 'alarm_kb.json')
OPERATOR_KB_PATH = os.path.join(_DATA_DIR, 'operator_kb.json')

def get_alarms_status() -> dict:
    """
    Restituisce metadati sullo stato del Parquet Allarmi (FM) per la UI.
    """
    if not os.path.exists(PARQUET_PATH):
        return {
            'available':  False,
            'total_rows': 0,
            'date_from':  None,
            'date_to':    None,
        }

    try:
        lock = FileLock(PARQUET_PATH + ".lock")
        with lock:
            df = pd.read_parquet(PARQUET_PATH)

        date_from = None
        date_to   = None
        if 'Occurrence_Time' in df.columns:
            valid = pd.to_datetime(df['Occurrence_Time'], errors='coerce').dropna()
            if not valid.empty:
                date_from = str(valid.min().date())
                date_to   = str(valid.max().date())

        return {
            'available':  True,
            'total_rows': len(df),
            'date_from':  date_from,
            'date_to':    date_to,
        }
    except Exception as e:
        logger.error("Errore lettura status Alarmi: %s", e)
        return {
            'available':  False,
            'total_rows': 0,
            'date_from':  None,
            'date_to':    None,
            'error':      str(e),
        }


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

    parquet_lock = FileLock(PARQUET_PATH + ".lock")
    with parquet_lock:
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
    kb_lock = FileLock(ALARM_KB_PATH + ".lock")
    with kb_lock:
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


def rebuild_kb_full() -> dict:
    """
    Ricalcola da zero la Knowledge Base (alarm_kb.json) a partire dall'intero storico.
    Identico a build_kb.py ma eseguibile programmaticamente dal server API.
    Aggiunge metadati per tracciare lo stato dell'ultimo rebuild completo.
    """
    logger.info("Avvio rebuild completo della KB...")
    if not os.path.exists(PARQUET_PATH):
        logger.warning("File storico Parquet non trovato a %s", PARQUET_PATH)
        return {"status": "error", "message": "Storico non disponibile"}

    try:
        # 1. Carica il Parquet con lock
        parquet_lock = FileLock(PARQUET_PATH + ".lock")
        with parquet_lock:
            df = pd.read_parquet(PARQUET_PATH)

        if df.empty:
            logger.warning("Storico allarmi vuoto.")
            return {"status": "error", "message": "Storico vuoto"}

        if 'Occurrence_Time' in df.columns:
            df['Occurrence_Time'] = pd.to_datetime(df['Occurrence_Time'], errors='coerce')

        # Calcola date range
        valid_times = df['Occurrence_Time'].dropna() if 'Occurrence_Time' in df.columns else pd.Series([])
        if not valid_times.empty:
            date_min = valid_times.min()
            date_max = valid_times.max()
            history_days = max(1, (date_max - date_min).days)
        else:
            date_min = date_max = None
            history_days = 20

        total_events = len(df)
        unique_mes = df['ME'].nunique() if 'ME' in df.columns else 0
        unique_alarms = df['Alarm_Code_Name'].nunique() if 'Alarm_Code_Name' in df.columns else 0

        # -- Profili Allarme --
        alarm_stats = []
        for alarm_name, g in df.groupby('Alarm_Code_Name', sort=False):
            total_occ = len(g)
            affected_me = g['ME'].nunique() if 'ME' in g.columns else 0
            main_sev = (
                g['Alarm_Severity'].value_counts().index[0]
                if 'Alarm_Severity' in g.columns and len(g) > 0
                else 'UNKNOWN'
            )

            # Allarmi cronici
            chronic_mes = []
            if 'Occurrence_Time' in g.columns and 'ME' in g.columns:
                for me_name, me_g in g.groupby('ME'):
                    valid = me_g['Occurrence_Time'].dropna()
                    if len(valid) > 0:
                        day_span = (valid.max() - valid.min()).days
                        if day_span >= 21: # CHRONIC_DAYS
                            chronic_mes.append(me_name)

            alarm_stats.append({
                'alarm_code_name': alarm_name,
                'total_occurrences': total_occ,
                'affected_me_count': affected_me,
                'main_severity': str(main_sev),
                'chronic_me_list': chronic_mes[:50],
            })

        # Calcola score di filtrabilità
        stats_df = pd.DataFrame(alarm_stats)
        scores_map = {}
        if not stats_df.empty:
            occ_rank = stats_df['total_occurrences'].rank(pct=True)
            me_rank = stats_df['affected_me_count'].rank(pct=True)
            stats_df['filterability_score'] = (occ_rank * 0.6 + me_rank * 0.4).round(4)
            scores_map = dict(zip(stats_df['alarm_code_name'], stats_df['filterability_score']))

        alarm_profiles = {}
        for a in alarm_stats:
            score = scores_map.get(a['alarm_code_name'], 0.0)
            is_structural = (
                score >= 0.85 and # FILTERABILITY_THRESHOLD
                a['affected_me_count'] >= 10 # STRUCTURAL_MIN_ME
            )
            
            # Suggest action
            if is_structural:
                suggested_action = "TOLERABLE"
                suggested_reason = "Allarme strutturale: presente su molti NE con alta frequenza"
            else:
                sev = str(a['main_severity']).upper()
                if sev in ('CRITICAL', 'MAJOR'):
                    suggested_action = "ESCALATE"
                    suggested_reason = f"Allarme {sev} non strutturale"
                elif sev == 'MINOR':
                    suggested_action = "MONITOR"
                    suggested_reason = "Allarme MINOR non strutturale"
                else:
                    suggested_action = "TOLERABLE"
                    suggested_reason = "Allarme WARNING/bassa priorità"

            alarm_profiles[a['alarm_code_name']] = {
                'total_occurrences': a['total_occurrences'],
                'affected_me_count': a['affected_me_count'],
                'main_severity': a['main_severity'],
                'filterability_score': score,
                'is_structural': is_structural,
                'chronic_me_list': a['chronic_me_list'],
                'suggested_action': suggested_action,
                'suggested_reason': suggested_reason,
            }

        structural_count = sum(1 for v in alarm_profiles.values() if v['is_structural'])

        # -- Profili NE --
        me_profiles = {}
        if 'ME' in df.columns:
            for me_name, me_g in df.groupby('ME'):
                total_alarms = len(me_g)
                unique_types = me_g['Alarm_Code_Name'].nunique() if 'Alarm_Code_Name' in me_g.columns else 0

                # Allarmi cronici (stesso tipo per >=21 giorni)
                chronic_types = []
                if 'Alarm_Code_Name' in me_g.columns and 'Occurrence_Time' in me_g.columns:
                    for aname, ag in me_g.groupby('Alarm_Code_Name'):
                        valid = ag['Occurrence_Time'].dropna()
                        if len(valid) > 0 and (valid.max() - valid.min()).days >= 21: # CHRONIC_DAYS
                            chronic_types.append(aname)

                top_alarm = None
                if 'Alarm_Code_Name' in me_g.columns and len(me_g) > 0:
                    top_alarm = me_g['Alarm_Code_Name'].value_counts().index[0]

                critical_count = 0
                if 'Alarm_Severity' in me_g.columns:
                    critical_count = int((me_g['Alarm_Severity'].str.upper() == 'CRITICAL').sum())

                risk_raw = (
                    min(total_alarms / 500, 1.0) * 0.4 +
                    min(len(chronic_types) / 5, 1.0) * 0.3 +
                    min(critical_count / 50, 1.0) * 0.3
                )
                risk_score = round(risk_raw, 4)

                me_profiles[me_name] = {
                    'total_alarms_20d': total_alarms,
                    'unique_alarm_types': unique_types,
                    'chronic_alarm_types': chronic_types[:20],
                    'chronic_alarm_count': len(chronic_types),
                    'top_alarm': top_alarm,
                    'risk_score': risk_score,
                }

        # 2. Carica/Crea KB JSON completo
        kb = {
            'generated_at': datetime.now().isoformat(),
            'last_rebuild_at': datetime.now().isoformat(),
            'last_rebuild_status': 'SUCCESS',
            'history_days': history_days,
            'date_from': str(date_min.date()) if date_min else None,
            'date_to': str(date_max.date()) if date_max else None,
            'total_events': total_events,
            'unique_mes': unique_mes,
            'unique_alarm_types': unique_alarms,
            'filterability_threshold': 0.85,
            'structural_alarm_count': structural_count,
            'alarm_profiles': alarm_profiles,
            'me_profiles': me_profiles,
        }

        # Salva con lock
        kb_lock = FileLock(ALARM_KB_PATH + ".lock")
        with kb_lock:
            with open(ALARM_KB_PATH, 'w', encoding='utf-8') as f:
                json.dump(kb, f, ensure_ascii=False, indent=2, default=str)

        # Invalida la cache del classificatore
        reload_kb()
        logger.info("rebuild_kb_full completato con successo.")
        return {"status": "success", "total_events": total_events, "unique_mes": unique_mes}

    except Exception as e:
        logger.error("Errore durante il rebuild completo della KB: %s", e, exc_info=True)
        # Tenta di salvare lo stato fallito se possibile
        try:
            if os.path.exists(ALARM_KB_PATH):
                kb_lock = FileLock(ALARM_KB_PATH + ".lock")
                with kb_lock:
                    with open(ALARM_KB_PATH, 'r', encoding='utf-8') as f:
                        kb = json.load(f)
                    kb['last_rebuild_status'] = f'FAILED: {str(e)}'
                    kb['last_rebuild_failed_at'] = datetime.now().isoformat()
                    with open(ALARM_KB_PATH, 'w', encoding='utf-8') as f:
                        json.dump(kb, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass
        return {"status": "error", "message": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point principale
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = ['ME', 'ME IP', 'Alarm Code Name', 'Alarm Severity', 'Occurrence Time']

def validate_excel_structure(df: pd.DataFrame) -> bool:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"File malformato. Colonne mancanti: {missing}")
    return True

def load_topology_db() -> tuple[dict, dict, dict, dict, dict]:
    """
    Carica il file SITI RIMASTI.xlsx ed estrae la topologia esatta dei link.
    Ritorna:
        - ip_to_partner: {ip: partner_ip}
        - ip_to_role: {ip: 'Local (Site A)' | 'Remote (Site B)'}
        - ip_to_link_type: {ip: str}
        - ip_to_link_name: {ip: str}
        - ip_to_macroarea: {ip: str}
    """
    ip_to_partner = {}
    ip_to_role = {}
    ip_to_link_type = {}
    ip_to_link_name = {}
    ip_to_macroarea = {}
    
    topo_path = os.path.join(_DATI_DIR, 'SITI RIMASTI.xlsx')
    if not os.path.exists(topo_path):
        logger.warning("File topologia SITI RIMASTI.xlsx non trovato, fallback su euristica subnet.")
        return ip_to_partner, ip_to_role, ip_to_link_type, ip_to_link_name, ip_to_macroarea
        
    try:
        import re
        # 1. Carica Link Information per accoppiamenti fisici, ruoli e tipi link
        df_topo = pd.read_excel(topo_path, sheet_name='TOPO_Link_Information', skiprows=2)
        
        def extract_ip(name_str):
            if not isinstance(name_str, str):
                return None
            match = re.search(r'\(([\d\.]+)\)', name_str)
            return match.group(1) if match else None
            
        for _, row in df_topo.iterrows():
            src_name = row.get('Source ME Name')
            dst_name = row.get('Destination ME Name')
            res_type = str(row.get('Resource Type', 'NR9250'))
            
            src_ip = extract_ip(src_name)
            dst_ip = extract_ip(dst_name)
            
            if src_ip and dst_ip:
                ip_to_partner[src_ip] = dst_ip
                ip_to_partner[dst_ip] = src_ip
                
                ip_to_role[src_ip] = 'Local (Site A)'
                ip_to_role[dst_ip] = 'Remote (Site B)'
                
                # Normalizza tipo link per visualizzazione
                ltype = 'ER2020E' if 'EBAND' in str(src_name).upper() or 'EBAND' in str(dst_name).upper() else res_type
                ip_to_link_type[src_ip] = ltype
                ip_to_link_type[dst_ip] = ltype
                
        # 2. Carica ME e Group Information per Link Name e Macroarea
        df_me = pd.read_excel(topo_path, sheet_name='TOPO_ME_Information', skiprows=2)
        df_group = pd.read_excel(topo_path, sheet_name='TOPO_Group_Information', skiprows=2)
        
        # Mappa Resource Name (Link Name) -> Node Location in Group Information
        group_to_loc = {}
        for _, row in df_group.iterrows():
            g_name = row.get('Resource Name')
            loc = row.get('Node Location')
            if isinstance(g_name, str) and isinstance(loc, str):
                group_to_loc[g_name.strip()] = loc.strip()
                
        # Per ciascun ME IP in ME Information, estrai Link Name e Macroarea
        for _, row in df_me.iterrows():
            me_ip = row.get('IP Address')
            parent_g = row.get('Parent Group')
            if isinstance(me_ip, str) and me_ip.strip():
                ip = me_ip.strip()
                if isinstance(parent_g, str) and parent_g.strip():
                    link_name = parent_g.strip()
                    ip_to_link_name[ip] = link_name
                    
                    loc = group_to_loc.get(link_name)
                    if loc:
                        macroarea = loc.split('-')[0].strip()
                        ip_to_macroarea[ip] = macroarea
                    else:
                        ip_to_macroarea[ip] = 'Sconosciuta'
                else:
                    ip_to_link_name[ip] = 'N/A'
                    ip_to_macroarea[ip] = 'Sconosciuta'
                    
        logger.info("Caricata topologia da SITI RIMASTI.xlsx: %d link e %d ME mappati.", len(df_topo), len(ip_to_link_name))
    except Exception as e:
        logger.error("Errore caricamento topologia da SITI RIMASTI.xlsx: %s", e)
        
    return ip_to_partner, ip_to_role, ip_to_link_type, ip_to_link_name, ip_to_macroarea


def process_excel(file_path: str) -> dict:
    # 1. Leggi Excel
    df = pd.read_excel(file_path, engine='openpyxl')
    
    validate_excel_structure(df)

    # 2. Filtro ME che iniziano con "X"
    if 'ME' in df.columns:
        df['ME'] = df['ME'].astype(str).str.strip()
        df = df[~df['ME'].str.startswith('X', na=False)].copy()

    # 3. Topology Pairing — hybrid database + device-type aware subnet fallback
    if 'ME IP' in df.columns:
        df['ME IP'] = df['ME IP'].astype(str).str.strip()
        df['Subnet_28'] = df['ME IP'].apply(get_subnet_28)

        # Carica il database topologico esatto
        db_partner, db_role, db_link_type, db_link_name, db_macroarea = load_topology_db()

        topology_map = {}   # ip → Topology_Role string
        link_type_map = {}  # ip → Link_Type string
        link_name_map = {}  # ip → Link_Name string
        macroarea_map = {}  # ip → Macroarea string

        # Identifica gli IP unici nel file giornaliero
        all_unique_ips = [ip for ip in df['ME IP'].unique() if ip and ip != 'nan']

        # Prima passata: assegna tramite database esatto (SITI RIMASTI.xlsx)
        for ip in all_unique_ips:
            if ip in db_role:
                topology_map[ip] = db_role[ip]
                link_type_map[ip] = db_link_type.get(ip, 'NR9250')
            if ip in db_link_name:
                link_name_map[ip] = db_link_name[ip]
                macroarea_map[ip] = db_macroarea.get(ip, 'Sconosciuta')

        # Seconda passata: per gli IP non coperti (2.7% di fallback), usa l'euristica delle subnet
        unmapped_ips = [ip for ip in all_unique_ips if ip not in topology_map]

        if unmapped_ips:
            unmapped_df = df[df['ME IP'].isin(unmapped_ips)]
            for subnet, group in unmapped_df.groupby('Subnet_28'):
                if not subnet:
                    continue
                unique_ips = sorted(
                    [ip for ip in group['ME IP'].unique() if ip and ip != 'nan'],
                    key=lambda x: _ip_offset(x)   # ordina per offset nella /28
                )
                n = len(unique_ips)

                if n == 2:
                    topology_map[unique_ips[0]] = 'Local (Site A)'
                    topology_map[unique_ips[1]] = 'Remote (Site B)'
                    for ip in unique_ips:
                        link_type_map[ip] = 'NR9250'
                        link_name_map[ip] = f"Link Fallback Subnet {subnet}"
                        macroarea_map[ip] = 'Sconosciuta'

                elif n == 4:
                    topology_map[unique_ips[0]] = 'Local (Site A)'
                    topology_map[unique_ips[1]] = 'Local (Site A)'
                    topology_map[unique_ips[2]] = 'Remote (Site B)'
                    topology_map[unique_ips[3]] = 'Remote (Site B)'
                    for ip in unique_ips:
                        link_type_map[ip] = 'ER2020E'
                        link_name_map[ip] = f"Link Fallback Subnet {subnet}"
                        macroarea_map[ip] = 'Sconosciuta'

                elif n == 1:
                    topology_map[unique_ips[0]] = 'Local (Site A)'
                    link_type_map[unique_ips[0]] = 'NR9250'
                    link_name_map[unique_ips[0]] = f"Link Fallback Subnet {subnet}"
                    macroarea_map[unique_ips[0]] = 'Sconosciuta'

                else:
                    for idx, ip in enumerate(unique_ips):
                        if idx == 0:
                            topology_map[ip] = 'Local (Site A)'
                        elif idx == 1:
                            topology_map[ip] = 'Remote (Site B)'
                        else:
                            topology_map[ip] = f'Node {idx + 1}'
                        link_type_map[ip] = 'Multiband'
                        link_name_map[ip] = f"Link Fallback Subnet {subnet}"
                        macroarea_map[ip] = 'Sconosciuta'

        df['Topology_Role'] = df['ME IP'].map(topology_map).fillna('Unknown')
        df['Link_Type']     = df['ME IP'].map(link_type_map).fillna('Unknown')
        df['Link_Name']     = df['ME IP'].map(link_name_map).fillna('N/A')
        df['Macroarea']     = df['ME IP'].map(macroarea_map).fillna('Sconosciuta')

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
        'Alarm Code Name', 'Alarm Severity', 'Occurrence Time', 'Link_Name', 'Macroarea'
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
