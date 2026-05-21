"""
build_history_db.py
====================
Unifica i 20 file Excel di storico allarmi (fm-history-20daysALL/) in un
unico database Parquet normalizzato (history_db.parquet).

Eseguire UNA VOLTA prima di avviare il backend.
Esecuzione successiva: aggiunge solo file non ancora processati.

Uso:
    cd "c:\\Users\\10294484\\Desktop\\AI DEMO\\ALARM MANAGER\\DATI"
    python build_history_db.py
"""

import pandas as pd
import ipaddress
import os
import sys
import json
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

# Fix encoding on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Percorsi ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
HIST_DIR    = os.path.join(BASE_DIR, "fm-history-20daysALL")
OUTPUT_PAR  = os.path.join(BASE_DIR, "history_db.parquet")
TRACKER_FILE = os.path.join(BASE_DIR, ".processed_files.json")

# ── Colonne da mantenere (adattato ai nomi reali nei file) ───────────────────
WANTED_COLS = {
    # nome originale nel file          → nome normalizzato
    'ME':                               'ME',
    'ME IP':                            'ME_IP',
    'Alarm Code Name':                  'Alarm_Code_Name',
    'Alarm Code':                       'Alarm_Code',
    'Alarm Severity':                   'Alarm_Severity',
    'Occurrence Time':                  'Occurrence_Time',
    'Specific Problem':                 'Specific_Problem',
    'Ack State':                        'Ack_State',
    'Clear State':                      'Clear_State',
    'ME Level':                         'ME_Level',
    'Repeat Count':                     'Repeat_Count',
    'Alarm Type':                       'Alarm_Type',
    'MOC':                              'MOC',
    'ME ID':                            'ME_ID',
    'Resource Type':                    'Resource_Type',
}

DEDUP_KEYS = ['ME', 'Alarm_Code_Name', 'Occurrence_Time']


def get_subnet_28(ip_str):
    try:
        net = ipaddress.IPv4Network(f"{ip_str}/28", strict=False)
        return str(net)
    except Exception:
        return None


def load_tracker():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, 'r') as f:
            return json.load(f)
    return {"processed": []}


def save_tracker(tracker):
    with open(TRACKER_FILE, 'w') as f:
        json.dump(tracker, f, indent=2)


def normalize_df(df, source_file):
    """Normalizza un DataFrame grezzo da Excel."""
    # Rinomina le colonne che esistono
    rename_map = {orig: norm for orig, norm in WANTED_COLS.items() if orig in df.columns}
    df = df.rename(columns=rename_map)

    # Tieni solo le colonne normalizzate che esistono
    keep = [c for c in WANTED_COLS.values() if c in df.columns]
    df = df[keep].copy()

    # ME: stringa, escludi quelli che iniziano con "X"
    if 'ME' in df.columns:
        df['ME'] = df['ME'].astype(str).str.strip()
        df = df[~df['ME'].str.startswith('X', na=False)].copy()

    # ME_IP: stringa
    if 'ME_IP' in df.columns:
        df['ME_IP'] = df['ME_IP'].astype(str).str.strip()
        df['Subnet_28'] = df['ME_IP'].apply(get_subnet_28)

    # Alarm_Code_Name: stringa pulita
    if 'Alarm_Code_Name' in df.columns:
        df['Alarm_Code_Name'] = df['Alarm_Code_Name'].astype(str).str.strip()

    # Alarm_Severity: uppercase
    if 'Alarm_Severity' in df.columns:
        df['Alarm_Severity'] = df['Alarm_Severity'].astype(str).str.strip().str.upper()

    # Occurrence_Time: datetime
    if 'Occurrence_Time' in df.columns:
        df['Occurrence_Time'] = pd.to_datetime(df['Occurrence_Time'], errors='coerce')

    # Repeat_Count: intero
    if 'Repeat_Count' in df.columns:
        df['Repeat_Count'] = pd.to_numeric(df['Repeat_Count'], errors='coerce').fillna(0).astype(int)

    # Tracciabilità
    df['source_file'] = os.path.basename(source_file)

    return df


def process_file(filepath):
    fname = os.path.basename(filepath)
    print(f"  >> Leggo {fname}...", end=' ', flush=True)
    try:
        df = pd.read_excel(filepath, engine='openpyxl')
        df = normalize_df(df, filepath)
        print(f"→ {len(df):,} righe")
        return df
    except Exception as e:
        print(f"→ ERRORE: {e}")
        return pd.DataFrame()


def get_all_history_files():
    files = []
    # File numerati 1..19
    for i in range(1, 20):
        f = os.path.join(HIST_DIR, f"fm-history-20daysALL-{i}.xlsx")
        if os.path.exists(f):
            files.append(f)
    # File base
    base = os.path.join(HIST_DIR, "fm-history-20daysALL.xlsx")
    if os.path.exists(base):
        files.append(base)
    return files


def main():
    print("=" * 65)
    print("  BUILD HISTORY DB — Normalizzazione Storico Allarmi")
    print("=" * 65)
    print(f"  Output: {OUTPUT_PAR}")
    print()

    tracker = load_tracker()
    all_files = get_all_history_files()
    already_done = set(tracker["processed"])

    # Determina quali file processare
    to_process = [f for f in all_files if os.path.basename(f) not in already_done]
    if not to_process:
        print("[OK] Tutti i file gia' processati. history_db.parquet e' aggiornato.")
        return

    print(f"[INFO] File da processare: {len(to_process)} / {len(all_files)}")
    print()

    new_dfs = []
    for fp in to_process:
        df = process_file(fp)
        if not df.empty:
            new_dfs.append(df)
            tracker["processed"].append(os.path.basename(fp))

    if not new_dfs:
        print("[ERRORE] Nessun dato caricato.")
        return

    new_data = pd.concat(new_dfs, ignore_index=True)
    print(f"\n  Nuovi record caricati: {len(new_data):,}")

    # Rimuovi duplicati interni ai nuovi dati
    dedup_keys_exist = [k for k in DEDUP_KEYS if k in new_data.columns]
    if dedup_keys_exist:
        before = len(new_data)
        new_data = new_data.drop_duplicates(subset=dedup_keys_exist, keep='first')
        removed = before - len(new_data)
        if removed:
            print(f"  Duplicati rimossi (nuovi): {removed:,}")

    # Se esiste già un Parquet, unisci
    if os.path.exists(OUTPUT_PAR):
        print(f"\n  [INFO] Parquet esistente trovato, unisco...")
        existing = pd.read_parquet(OUTPUT_PAR)
        combined = pd.concat([existing, new_data], ignore_index=True)
        if dedup_keys_exist:
            before = len(combined)
            combined = combined.drop_duplicates(subset=dedup_keys_exist, keep='first')
            removed = before - len(combined)
            if removed:
                print(f"  Duplicati rimossi (merged): {removed:,}")
        combined.to_parquet(OUTPUT_PAR, index=False, engine='pyarrow', compression='snappy')
        final_df = combined
    else:
        new_data.to_parquet(OUTPUT_PAR, index=False, engine='pyarrow', compression='snappy')
        final_df = new_data

    save_tracker(tracker)

    # ── Statistiche finali ──────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  [OK] COMPLETATO")
    print(f"{'='*65}")
    print(f"  Totale record nel DB: {len(final_df):,}")
    if 'ME' in final_df.columns:
        print(f"  NE unici:             {final_df['ME'].nunique():,}")
    if 'Alarm_Code_Name' in final_df.columns:
        print(f"  Tipi di allarme:      {final_df['Alarm_Code_Name'].nunique():,}")
    if 'Occurrence_Time' in final_df.columns:
        valid_times = final_df['Occurrence_Time'].dropna()
        if not valid_times.empty:
            print(f"  Periodo coperto:      {valid_times.min().date()} → {valid_times.max().date()}")
    if 'Alarm_Severity' in final_df.columns:
        sev = final_df['Alarm_Severity'].value_counts()
        print(f"\n  Distribuzione severita':")
        for s, n in sev.items():
            print(f"    {s:<12}: {n:>10,}")
    print(f"\n  File salvato: {OUTPUT_PAR}")
    print(f"  Dimensione:   {os.path.getsize(OUTPUT_PAR)/1024/1024:.1f} MB")
    print()
    print("  --> Ora esegui: python build_kb.py")
    print()


if __name__ == "__main__":
    main()
