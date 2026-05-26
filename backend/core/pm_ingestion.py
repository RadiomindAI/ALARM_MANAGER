"""
pm_ingestion.py
================
Gestione dello storico dati Performance Management (PM) ZTE.
Speculare a ingestion.py per gli allarmi.

Flusso:
  1. process_pm_excel(file_path) → aggiunge i dati al Parquet storico pm_history.parquet
  2. get_pm_for_site(site_name)  → restituisce il DataFrame filtrato per quel sito
  3. get_pm_status()             → metadati sullo stato del DB (per la UI)
"""

import os
import logging
from datetime import datetime
from filelock import FileLock

import pandas as pd

logger = logging.getLogger(__name__)

# ── Percorsi ──────────────────────────────────────────────────────────────────
_BACKEND_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATI_DIR     = os.path.join(_BACKEND_DIR, '..', 'DATI')
PM_PARQUET    = os.path.join(_DATI_DIR, 'pm_history.parquet')

# Chiavi di deduplicazione — stesso record se stesso sito, modem e finestra temporale
PM_DEDUP_KEYS = ['ME', 'PM Checkpoint', 'Begin Time']

# Colonne PM ZTE attese (tollerante: ne usa quante ne trova)
PM_EXPECTED_COLS = [
    'ME', 'ME IP', 'PM Checkpoint', 'Begin Time', 'End Time',
    'Mean Received Signal Level(dBm)',
    'Mean XPI(dB)',
    'Mean MSE(dB)',
    'ES(s)',
    'Neighbor ME',
    'Max IF Rx Power(dBm)',
    'Min IF Rx Power(dBm)',
    'Mean IF Rx Power(dBm)',
    'Max IF Tx Power(dBm)',
    'Min IF Tx Power(dBm)',
    'Mean IF Tx Power(dBm)',
    'Max MSE(dB)',
    'Min MSE(dB)',
]


# ─────────────────────────────────────────────────────────────────────────────
#  Validazione
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_PM_COLS = ['ME', 'PM Checkpoint', 'Begin Time']


def validate_pm_structure(df: pd.DataFrame) -> bool:
    missing = [c for c in REQUIRED_PM_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"File PM malformato. Colonne obbligatorie mancanti: {missing}"
        )
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  Aggiornamento storico PM
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_pm_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizza e pulisce un DataFrame PM grezzo da Excel."""
    df = df.copy()

    # Rimuovi eventuali NE che iniziano con 'X' (stessa logica allarmi)
    if 'ME' in df.columns:
        df['ME'] = df['ME'].astype(str).str.strip()
        df = df[~df['ME'].str.startswith('X', na=False)]

    # Parse datetime
    for col in ['Begin Time', 'End Time']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # Converti numeri
    numeric_cols = [
        'Mean Received Signal Level(dBm)', 'Mean XPI(dB)', 'Mean MSE(dB)', 'ES(s)',
        'Max IF Rx Power(dBm)', 'Min IF Rx Power(dBm)', 'Mean IF Rx Power(dBm)',
        'Max IF Tx Power(dBm)', 'Min IF Tx Power(dBm)', 'Mean IF Tx Power(dBm)',
        'Max MSE(dB)', 'Min MSE(dB)',
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Colonne 'Working Time of RX ...' → numeriche
    rx_cols = [c for c in df.columns if 'Working Time of RX' in c]
    for col in rx_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Tag sorgente
    df['_source_date'] = datetime.now().strftime('%Y%m%d')

    return df


def process_pm_excel(file_path: str) -> dict:
    """
    Legge un file Excel PM ZTE, lo normalizza e aggiorna pm_history.parquet.

    Returns dict con:
      rows_added, total_rows, date_from, date_to, sites_found
    """
    logger.info("PM ingestion: lettura %s", file_path)
    df = pd.read_excel(file_path, engine='openpyxl')
    validate_pm_structure(df)
    df = _normalize_pm_df(df)

    rows_before = 0
    os.makedirs(_DATI_DIR, exist_ok=True)

    lock = FileLock(PM_PARQUET + ".lock")
    with lock:
        if os.path.exists(PM_PARQUET):
            try:
                existing = pd.read_parquet(PM_PARQUET)
                rows_before = len(existing)
                combined = pd.concat([existing, df], ignore_index=True)
            except Exception as e:
                logger.warning("Parquet PM corrotto, si ricrea: %s", e)
                combined = df
        else:
            combined = df

        # Dedup
        dedup_keys = [k for k in PM_DEDUP_KEYS if k in combined.columns]
        if dedup_keys:
            combined = combined.drop_duplicates(subset=dedup_keys, keep='first')

        combined.to_parquet(PM_PARQUET, index=False, engine='pyarrow', compression='snappy')
    rows_added = len(combined) - rows_before

    logger.info("PM storico aggiornato: %d record totali (+%d)", len(combined), rows_added)

    # Statistiche per la risposta
    date_from = None
    date_to   = None
    if 'Begin Time' in combined.columns:
        valid_dates = combined['Begin Time'].dropna()
        if not valid_dates.empty:
            date_from = str(valid_dates.min().date())
            date_to   = str(valid_dates.max().date())

    sites_found = sorted(combined['ME'].dropna().unique().tolist()) if 'ME' in combined.columns else []

    return {
        'rows_added':   rows_added,
        'total_rows':   len(combined),
        'date_from':    date_from,
        'date_to':      date_to,
        'sites_found':  sites_found,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Lettura per sito
# ─────────────────────────────────────────────────────────────────────────────

def get_pm_for_site(site_name: str) -> pd.DataFrame:
    """
    Restituisce il DataFrame PM per un sito (filtra per match parziale su ME).
    Include anche i record del sito remoto (stesso link) cercando via IP subnet /28.

    Returns:
        DataFrame filtrato, o DataFrame vuoto se il Parquet non esiste.
    """
    if not os.path.exists(PM_PARQUET):
        logger.warning("pm_history.parquet non trovato")
        return pd.DataFrame()

    try:
        lock = FileLock(PM_PARQUET + ".lock")
        with lock:
            df = pd.read_parquet(PM_PARQUET)
    except Exception as e:
        logger.error("Errore lettura Parquet PM: %s", e)
        return pd.DataFrame()

    if 'ME' not in df.columns:
        return pd.DataFrame()

    # Cerca il sito locale (match parziale case-insensitive)
    mask_local = df['ME'].astype(str).str.contains(site_name, case=False, na=False, regex=False)
    df_local   = df[mask_local]

    if df_local.empty:
        logger.info("Nessun dato PM per sito '%s'", site_name)
        return pd.DataFrame()

    # Cerca il sito remoto via database topologia esatta o subnet /28 fallback
    df_remote = pd.DataFrame()
    if 'ME IP' in df.columns and not df_local.empty:
        local_ips = df_local['ME IP'].dropna().unique()
        partner_ip = None
        
        try:
            from .ingestion import load_topology_db
            ip_to_partner, _, _, _, _ = load_topology_db()
            for lip in local_ips:
                lip_clean = str(lip).strip()
                if lip_clean in ip_to_partner:
                    partner_ip = ip_to_partner[lip_clean]
                    break
        except Exception as e:
            logger.warning("Impossibile caricare il database topologico per PM: %s", e)
            
        if partner_ip:
            mask_remote = (df['ME IP'].astype(str).str.strip() == str(partner_ip).strip()) & ~mask_local
            df_remote = df[mask_remote]
            if not df_remote.empty:
                logger.info("Sito remoto per PM trovato tramite topologia fisica (IP partner: %s)", partner_ip)
            
        # Fallback se non trovato tramite topologia fisica
        if df_remote.empty and len(local_ips) > 0:
            local_ip_sample = str(local_ips[0])
            try:
                import ipaddress
                net = ipaddress.IPv4Network(f"{local_ip_sample}/28", strict=False)
                net_int    = int(net.network_address)
                net_mask   = int(net.netmask)

                def in_subnet(ip_str):
                    try:
                        return (int(ipaddress.IPv4Address(str(ip_str))) & net_mask) == net_int
                    except Exception:
                        return False

                mask_subnet = df['ME IP'].astype(str).apply(in_subnet)
                mask_remote = mask_subnet & ~mask_local
                df_remote   = df[mask_remote]
                if not df_remote.empty:
                    logger.info("Sito remoto per PM trovato tramite fallback subnet /28")
            except Exception as e:
                logger.debug("Subnet lookup fallita: %s", e)

    # Combina locale + remoto
    result = pd.concat([df_local, df_remote], ignore_index=True)
    logger.info("PM per '%s': %d record locali + %d remoti",
                site_name, len(df_local), len(df_remote))
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Status DB
# ─────────────────────────────────────────────────────────────────────────────

def get_pm_status() -> dict:
    """
    Restituisce metadati sullo stato del Parquet PM per la UI.
    """
    if not os.path.exists(PM_PARQUET):
        return {
            'available':  False,
            'total_rows': 0,
            'date_from':  None,
            'date_to':    None,
            'sites':      [],
        }

    try:
        lock = FileLock(PM_PARQUET + ".lock")
        with lock:
            df = pd.read_parquet(PM_PARQUET)

        date_from = None
        date_to   = None
        if 'Begin Time' in df.columns:
            valid = df['Begin Time'].dropna()
            if not valid.empty:
                date_from = str(valid.min().date())
                date_to   = str(valid.max().date())

        sites = sorted(df['ME'].dropna().unique().tolist()) if 'ME' in df.columns else []

        return {
            'available':  True,
            'total_rows': len(df),
            'date_from':  date_from,
            'date_to':    date_to,
            'sites':      sites,
        }
    except Exception as e:
        logger.error("Errore lettura status PM: %s", e)
        return {
            'available':  False,
            'total_rows': 0,
            'date_from':  None,
            'date_to':    None,
            'sites':      [],
            'error':      str(e),
        }
