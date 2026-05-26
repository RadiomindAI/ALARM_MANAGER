"""
build_pm_history_db.py
======================
Unifica i grandi file Excel dello storico PM (Performance Management)
nella cartella "Performance Management-History 1 mese" in un unico database Parquet
normalizzato e deduplicato (pm_history.parquet).

Ottimizzato per gestire file Excel di grandi dimensioni senza saturare la RAM
tramite il caricamento selettivo delle sole colonne utili.

Uso:
    cd "c:\\Users\\10294484\\Desktop\\AI DEMO\\ALARM MANAGER\\DATI"
    python build_pm_history_db.py
"""

import os
import sys
import json
import warnings
import pandas as pd
from datetime import datetime
from filelock import FileLock

warnings.filterwarnings("ignore")

# Configura l'encoding corretto per la console Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Percorsi ──────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
HIST_DIR      = os.path.join(BASE_DIR, "Performance Management-History 1 mese")
OUTPUT_PAR    = os.path.join(BASE_DIR, "pm_history.parquet")
TRACKER_FILE  = os.path.join(BASE_DIR, ".processed_pm_files.json")

# Chiavi per la deduplicazione
PM_DEDUP_KEYS = ['ME', 'PM Checkpoint', 'Begin Time']

# Colonne PM ZTE attese
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

REQUIRED_PM_COLS = ['ME', 'PM Checkpoint', 'Begin Time']


def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"processed": []}


def save_tracker(tracker):
    with open(TRACKER_FILE, 'w') as f:
        json.dump(tracker, f, indent=2)


def _normalize_pm_df(df: pd.DataFrame, filepath: str) -> pd.DataFrame:
    """Normalizza e pulisce un DataFrame PM grezzo da Excel."""
    df = df.copy()

    # Rimuovi eventuali NE che iniziano con 'X'
    if 'ME' in df.columns:
        df['ME'] = df['ME'].astype(str).str.strip()
        df = df[~df['ME'].str.startswith('X', na=False)].copy()

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

    # Tracciabilità del file sorgente e data caricamento
    df['source_file'] = os.path.basename(filepath)
    df['_source_date'] = datetime.now().strftime('%Y%m%d')

    return df


def process_large_excel(filepath: str) -> pd.DataFrame:
    fname = os.path.basename(filepath)
    print(f"\n  >> Avvio elaborazione di {fname}...", flush=True)
    
    # 1. Rileva le colonne reali del file Excel caricando 0 righe (velocissimo, consumo RAM = 0)
    try:
        header_df = pd.read_excel(filepath, nrows=0, engine='openpyxl')
        existing_cols = list(header_df.columns)
    except Exception as e:
        print(f"     [ERRORE] Impossibile leggere intestazione del file: {e}")
        return pd.DataFrame()

    # 2. Seleziona solo le colonne utili ed esistenti per ottimizzare l'uso della RAM
    cols_to_use = [
        c for c in existing_cols 
        if c in PM_EXPECTED_COLS or 'Working Time of RX' in c
    ]
    
    # Verifica colonne obbligatorie
    missing_required = [c for c in REQUIRED_PM_COLS if c not in cols_to_use]
    if missing_required:
        print(f"     [ERRORE] Colonne obbligatorie mancanti: {missing_required}. File saltato.")
        return pd.DataFrame()

    print(f"     Colonne utili trovate: {len(cols_to_use)} / {len(existing_cols)}")
    print(f"     Caricamento dati in corso (questo potrebbe richiedere un minuto)...", end='', flush=True)

    # 3. Carica il DataFrame completo ma filtrato sulle colonne per salvare RAM
    try:
        df = pd.read_excel(filepath, usecols=cols_to_use, engine='openpyxl')
        print(f" completato! ({len(df):,} righe caricate)")
    except Exception as e:
        print(f"\n     [ERRORE] Caricamento fallito: {e}")
        return pd.DataFrame()

    # 4. Normalizzazione
    print(f"     Normalizzazione e pulizia dei dati...", end='', flush=True)
    df = _normalize_pm_df(df, filepath)
    print(f" completata.")
    
    return df


def get_pm_history_files():
    if not os.path.exists(HIST_DIR):
        print(f"[ERRORE] Cartella non trovata: {HIST_DIR}")
        return []
    
    # Cerca tutti i file .xlsx nella cartella
    files = [
        os.path.join(HIST_DIR, f) 
        for f in os.listdir(HIST_DIR) 
        if f.endswith('.xlsx') and not f.startswith('~$')
    ]
    # Ordina alfabeticamente
    files.sort()
    return files


def main():
    print("=" * 65)
    print("  BUILD PM HISTORY DB — Caricamento Ottimizzato Storico PM")
    print("=" * 65)
    print(f"  Cartella Storico: {HIST_DIR}")
    print(f"  Parquet Output:   {OUTPUT_PAR}")
    print()

    history_files = get_pm_history_files()
    if not history_files:
        print("[ERRORE] Nessun file Excel trovato nella cartella dello storico.")
        return

    tracker = load_tracker()
    already_done = set(tracker.get("processed", []))
    
    to_process = [f for f in history_files if os.path.basename(f) not in already_done]
    
    if not to_process:
        print("[OK] Tutti i file storici sono già stati processati.")
        print(f"     Il database Parquet {OUTPUT_PAR} è aggiornato.")
        return

    print(f"[INFO] File totali trovati: {len(history_files)}")
    print(f"[INFO] File da elaborare:   {len(to_process)}")
    
    lock = FileLock(OUTPUT_PAR + ".lock")
    
    for filepath in to_process:
        df = process_large_excel(filepath)
        if df.empty:
            continue
        
        fname = os.path.basename(filepath)
        
        with lock:
            print(f"     Salvataggio nel database Parquet...", end='', flush=True)
            if os.path.exists(OUTPUT_PAR):
                try:
                    existing = pd.read_parquet(OUTPUT_PAR)
                    combined = pd.concat([existing, df], ignore_index=True)
                except Exception as e:
                    print(f"\n     [WARNING] Database esistente corrotto o illeggibile: {e}. Si ricrea da zero.")
                    combined = df
            else:
                combined = df
            
            # Deduplica su ME, PM Checkpoint e Begin Time
            dedup_keys_exist = [k for k in PM_DEDUP_KEYS if k in combined.columns]
            if dedup_keys_exist:
                before = len(combined)
                combined = combined.drop_duplicates(subset=dedup_keys_exist, keep='first')
                removed = before - len(combined)
                if removed > 0:
                    print(f" ({removed:,} record duplicati rimossi)", end='')
            
            combined.to_parquet(OUTPUT_PAR, index=False, engine='pyarrow', compression='snappy')
            print(" completato!")
            
        # Aggiorna il tracker
        tracker["processed"].append(fname)
        save_tracker(tracker)

    # ── Statistiche finali ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  [OK] PROCESSO DI CARICAMENTO COMPLETATO")
    print("=" * 65)
    
    if os.path.exists(OUTPUT_PAR):
        with lock:
            final_df = pd.read_parquet(OUTPUT_PAR)
            
        print(f"  Totale record nel database PM: {len(final_df):,}")
        if 'ME' in final_df.columns:
            print(f"  Siti (ME) unici profilati:     {final_df['ME'].nunique():,}")
        if 'Begin Time' in final_df.columns:
            valid_times = final_df['Begin Time'].dropna()
            if not valid_times.empty:
                print(f"  Periodo storico coperto:       {valid_times.min().date()} → {valid_times.max().date()}")
        print(f"  File salvato:                  {OUTPUT_PAR}")
        print(f"  Dimensione:                    {os.path.getsize(OUTPUT_PAR)/1024/1024:.1f} MB")
    else:
        print("  [WARNING] Nessun database Parquet è stato generato o salvato.")
    print()


if __name__ == "__main__":
    main()
