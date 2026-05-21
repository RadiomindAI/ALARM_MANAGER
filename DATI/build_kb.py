"""
build_kb.py
============
Genera la Knowledge Base (alarm_kb.json) a partire dal Parquet storico.
Deve essere eseguito DOPO build_history_db.py.

Uso:
    cd "c:\\Users\\10294484\\Desktop\\AI DEMO\\ALARM MANAGER\\DATI"
    python build_kb.py
"""

import pandas as pd
import numpy as np
import os
import sys
import json
import warnings
from datetime import datetime
from collections import defaultdict

warnings.filterwarnings("ignore")

# Fix encoding on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# -- Percorsi ------------------------------------------------------------------
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PARQUET_PATH  = os.path.join(BASE_DIR, "history_db.parquet")
OUTPUT_DIR    = os.path.join(BASE_DIR, "..", "backend", "data")
OUTPUT_KB     = os.path.join(OUTPUT_DIR, "alarm_kb.json")

# -- Parametri -----------------------------------------------------------------
FILTERABILITY_THRESHOLD = 0.85   # Soglia alzata
CHRONIC_DAYS            = 21     # Allarme cronico se presente > 21 giorni
STRUCTURAL_MIN_ME       = 10     # Strutturale se su >= 10 NE distinti


def compute_filterability_scores(alarm_stats_list):
    """
    Calcola il filterability score usando il rank percentile,
    identico all'approccio del file analyze_alarms.py originale.
    Score 0-1: piu' alto = piu' strutturale/filtrabile.
    """
    import pandas as pd
    df = pd.DataFrame(alarm_stats_list)
    if df.empty:
        return {}

    occ_rank = df['total_occurrences'].rank(pct=True)
    me_rank  = df['affected_me_count'].rank(pct=True)
    df['filterability_score'] = (occ_rank * 0.6 + me_rank * 0.4).round(4)

    return dict(zip(df['alarm_code_name'], df['filterability_score']))


def suggest_action(main_severity, filterability_score, is_structural):
    """Suggerisce l'azione predefinita in base a score e severita'."""
    if is_structural:
        return "TOLERABLE", "Allarme strutturale: presente su molti NE con alta frequenza"
    sev = str(main_severity).upper()
    if sev in ('CRITICAL', 'MAJOR'):
        return "ESCALATE", "Allarme {} non strutturale".format(sev)
    if sev == 'MINOR':
        return "MONITOR", "Allarme MINOR non strutturale"
    return "TOLERABLE", "Allarme WARNING/bassa priorita'"


def main():
    print("=" * 65)
    print("  BUILD KB -- Generazione Knowledge Base Allarmi")
    print("=" * 65)

    if not os.path.exists(PARQUET_PATH):
        print("ERRORE: {} non trovato.".format(PARQUET_PATH))
        print("   Esegui prima: python build_history_db.py")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("  Carico {}...".format(PARQUET_PATH), end=' ', flush=True)
    df = pd.read_parquet(PARQUET_PATH)
    print("-> {} record".format(len(df)))

    if 'Occurrence_Time' in df.columns:
        df['Occurrence_Time'] = pd.to_datetime(df['Occurrence_Time'], errors='coerce')

    # -- Periodo storico -------------------------------------------------------
    valid_times = df['Occurrence_Time'].dropna() if 'Occurrence_Time' in df.columns else pd.Series([])
    if not valid_times.empty:
        date_min = valid_times.min()
        date_max = valid_times.max()
        history_days = max(1, (date_max - date_min).days)
    else:
        date_min = date_max = None
        history_days = 20

    total_events = len(df)
    unique_mes    = df['ME'].nunique() if 'ME' in df.columns else 0
    unique_alarms = df['Alarm_Code_Name'].nunique() if 'Alarm_Code_Name' in df.columns else 0

    print("  Periodo: {} -> {} ({} giorni)".format(
        date_min.date() if date_min else '?',
        date_max.date() if date_max else '?',
        history_days))
    print("  NE unici: {} | Tipi allarme: {}".format(unique_mes, unique_alarms))

    # -- Profili per tipo di allarme -------------------------------------------
    print("\n  Calcolo profili allarmi...", flush=True)

    alarm_stats = []
    for alarm_name, g in df.groupby('Alarm_Code_Name', sort=False):
        total_occ    = len(g)
        affected_me  = g['ME'].nunique() if 'ME' in g.columns else 0
        main_sev     = (
            g['Alarm_Severity'].value_counts().index[0]
            if 'Alarm_Severity' in g.columns and len(g) > 0
            else 'UNKNOWN'
        )

        # Allarmi cronici per ME: span temporale >= 21 giorni
        chronic_mes = []
        if 'Occurrence_Time' in g.columns and 'ME' in g.columns:
            for me_name, me_g in g.groupby('ME'):
                valid = me_g['Occurrence_Time'].dropna()
                if len(valid) > 0:
                    day_span = (valid.max() - valid.min()).days
                    if day_span >= CHRONIC_DAYS:
                        chronic_mes.append(me_name)

        alarm_stats.append({
            'alarm_code_name': alarm_name,
            'total_occurrences': total_occ,
            'affected_me_count': affected_me,
            'main_severity': str(main_sev),
            'chronic_me_list': chronic_mes[:50],
        })

    # Calcola score di filtrabilita' con rank percentile
    scores_map = compute_filterability_scores(alarm_stats)

    alarm_profiles = {}
    for a in alarm_stats:
        score = scores_map.get(a['alarm_code_name'], 0.0)
        is_structural = (
            score >= FILTERABILITY_THRESHOLD and
            a['affected_me_count'] >= STRUCTURAL_MIN_ME
        )
        suggested_action, suggested_reason = suggest_action(
            a['main_severity'], score, is_structural
        )

        alarm_profiles[a['alarm_code_name']] = {
            'total_occurrences':   a['total_occurrences'],
            'affected_me_count':   a['affected_me_count'],
            'main_severity':       a['main_severity'],
            'filterability_score': score,
            'is_structural':       is_structural,
            'chronic_me_list':     a['chronic_me_list'],
            'suggested_action':    suggested_action,
            'suggested_reason':    suggested_reason,
        }

    structural_count = sum(1 for v in alarm_profiles.values() if v['is_structural'])
    print("  Allarmi strutturali (score>={}, ME>={}): {}".format(
        FILTERABILITY_THRESHOLD, STRUCTURAL_MIN_ME, structural_count))


    # -- Profili per NE --------------------------------------------------------
    print("  Calcolo profili NE...", flush=True)
    me_profiles = {}

    if 'ME' in df.columns:
        for me_name, me_g in df.groupby('ME'):
            total_alarms  = len(me_g)
            unique_types  = me_g['Alarm_Code_Name'].nunique() if 'Alarm_Code_Name' in me_g.columns else 0

            # Allarmi cronici (stesso tipo per >=21 giorni)
            chronic_types = []
            if 'Alarm_Code_Name' in me_g.columns and 'Occurrence_Time' in me_g.columns:
                for aname, ag in me_g.groupby('Alarm_Code_Name'):
                    valid = ag['Occurrence_Time'].dropna()
                    if len(valid) > 0 and (valid.max() - valid.min()).days >= CHRONIC_DAYS:
                        chronic_types.append(aname)

            # Top allarme
            top_alarm = None
            if 'Alarm_Code_Name' in me_g.columns and len(me_g) > 0:
                top_alarm = me_g['Alarm_Code_Name'].value_counts().index[0]

            # Conta CRITICAL
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
                'total_alarms_20d':    total_alarms,
                'unique_alarm_types':  unique_types,
                'chronic_alarm_types': chronic_types[:20],
                'chronic_alarm_count': len(chronic_types),
                'top_alarm':           top_alarm,
                'risk_score':          risk_score,
            }

    print("  NE profilati: {}".format(len(me_profiles)))

    # -- Salva output ----------------------------------------------------------
    kb = {
        'generated_at':            datetime.now().isoformat(),
        'history_days':            history_days,
        'date_from':               str(date_min.date()) if date_min else None,
        'date_to':                 str(date_max.date()) if date_max else None,
        'total_events':            total_events,
        'unique_mes':              unique_mes,
        'unique_alarm_types':      unique_alarms,
        'filterability_threshold': FILTERABILITY_THRESHOLD,
        'structural_alarm_count':  structural_count,
        'alarm_profiles':          alarm_profiles,
        'me_profiles':             me_profiles,
    }

    with open(OUTPUT_KB, 'w', encoding='utf-8') as f:
        json.dump(kb, f, ensure_ascii=False, indent=2, default=str)

    size_mb = os.path.getsize(OUTPUT_KB) / 1024 / 1024
    print("\n" + "=" * 65)
    print("  [OK] COMPLETATO")
    print("=" * 65)
    print("  KB salvata:           {}".format(OUTPUT_KB))
    print("  Dimensione:           {:.2f} MB".format(size_mb))
    print("  Allarmi strutturali:  {} / {}".format(structural_count, unique_alarms))
    print("  NE profilati:         {}".format(len(me_profiles)))
    print()

    # Top 10 strutturali
    structural = sorted(
        [(n, p) for n, p in alarm_profiles.items() if p['is_structural']],
        key=lambda x: x[1]['filterability_score'], reverse=True
    )
    print("  TOP ALLARMI STRUTTURALI (soglia {:.0f}%):".format(FILTERABILITY_THRESHOLD * 100))
    for name, prof in structural[:10]:
        print("    [{:.0f}%] {} NE | {} | {}".format(
            prof['filterability_score'] * 100,
            prof['affected_me_count'],
            prof['main_severity'],
            name[:60]
        ))
    print()
    print("  --> Ora avvia il backend: uvicorn main:app --reload")
    print()


if __name__ == "__main__":
    main()
