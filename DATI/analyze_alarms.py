"""
Alarm Analysis Script
Analizza lo storico allarmi (20 giorni) e gli allarmi attivi.
Output: JSON per la dashboard web
"""
import pandas as pd
import os
import json
import warnings
from collections import defaultdict
from datetime import datetime

warnings.filterwarnings("ignore")

BASE = r"c:\Users\10294484\Desktop\AI DEMO\ALARM MANAGER\DATI"
HIST_DIR = os.path.join(BASE, "fm-history-20daysALL")
ACTIVE_FILE = os.path.join(BASE, "fm-active-Alarm Monitor-20052026.xlsx")
OUTPUT_JSON = os.path.join(BASE, "alarm_analysis.json")

# Colonne chiave per l'analisi
KEY_COLS = [
    'ME', 'Alarm Code Name', 'Alarm Code', 'Alarm Severity',
    'Occurrence Time', 'Specific Problem', 'Resource Type',
    'Ack State', 'Clear State', 'ME Level', 'Repeat Count',
    'Alarm Type', 'MOC', 'ME ID'
]

def safe_read(filepath, label=""):
    print(f"  Reading {label or os.path.basename(filepath)}...")
    try:
        df = pd.read_excel(filepath, engine='openpyxl')
        # Keep only columns that exist
        cols = [c for c in KEY_COLS if c in df.columns]
        df = df[cols]
        print(f"    -> {len(df)} rows, {len(df.columns)} cols")
        return df
    except Exception as e:
        print(f"    ERROR: {e}")
        return pd.DataFrame()

def load_all_history():
    print("\n=== LOADING HISTORY FILES ===")
    dfs = []
    # Load numbered files
    for i in range(1, 20):
        fname = f"fm-history-20daysALL-{i}.xlsx"
        fpath = os.path.join(HIST_DIR, fname)
        if os.path.exists(fpath):
            df = safe_read(fpath, fname)
            if not df.empty:
                dfs.append(df)
    # Load base file
    base_hist = os.path.join(HIST_DIR, "fm-history-20daysALL.xlsx")
    if os.path.exists(base_hist):
        df = safe_read(base_hist, "fm-history-20daysALL.xlsx")
        if not df.empty:
            dfs.append(df)

    if not dfs:
        print("No history data loaded!")
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    print(f"\nTotal history rows loaded: {len(combined)}")
    return combined

def load_active():
    print("\n=== LOADING ACTIVE ALARMS ===")
    df = safe_read(ACTIVE_FILE, "Active Alarms")
    return df

def parse_datetime(series):
    """Try to parse datetime columns"""
    try:
        return pd.to_datetime(series, errors='coerce')
    except:
        return series

def analyze(hist_df, active_df):
    print("\n=== ANALYZING ===")
    results = {}

    # === HISTORY ANALYSIS ===
    if 'Occurrence Time' in hist_df.columns:
        hist_df['Occurrence Time'] = parse_datetime(hist_df['Occurrence Time'])

    # --- Frequency analysis by Alarm Code Name ---
    if 'Alarm Code Name' in hist_df.columns:
        freq = hist_df['Alarm Code Name'].value_counts().reset_index()
        freq.columns = ['alarm_code_name', 'total_occurrences']
        
        # Add severity info
        if 'Alarm Severity' in hist_df.columns:
            sev_map = hist_df.groupby('Alarm Code Name')['Alarm Severity'].agg(
                lambda x: x.value_counts().index[0] if len(x) > 0 else 'Unknown'
            ).reset_index()
            sev_map.columns = ['alarm_code_name', 'main_severity']
            freq = freq.merge(sev_map, on='alarm_code_name', how='left')
        
        # Add ME count (how many distinct NEs have this alarm)
        if 'ME' in hist_df.columns:
            me_count = hist_df.groupby('Alarm Code Name')['ME'].nunique().reset_index()
            me_count.columns = ['alarm_code_name', 'affected_ne_count']
            freq = freq.merge(me_count, on='alarm_code_name', how='left')
        
        # Filterability score: high occurrence + many NEs = likely filterable
        freq['filterability_score'] = (
            freq['total_occurrences'].rank(pct=True) * 0.6 +
            freq.get('affected_ne_count', pd.Series([0]*len(freq))).rank(pct=True) * 0.4
        ).round(3)
        
        # Label: filterable if score > 0.7 or occurrences > threshold
        threshold = freq['total_occurrences'].quantile(0.75)
        freq['filterable_candidate'] = (
            (freq['total_occurrences'] >= threshold) | 
            (freq['filterability_score'] >= 0.7)
        )
        
        results['top_alarms'] = freq.head(100).to_dict(orient='records')
        results['filterable_candidates'] = freq[freq['filterable_candidate']].head(50).to_dict(orient='records')
        results['total_unique_alarm_types'] = int(freq['alarm_code_name'].nunique())
        results['total_history_events'] = int(len(hist_df))
        results['threshold_occurrences'] = int(threshold)
    
    # --- Severity distribution ---
    if 'Alarm Severity' in hist_df.columns:
        sev_dist = hist_df['Alarm Severity'].value_counts().to_dict()
        results['severity_distribution'] = {str(k): int(v) for k, v in sev_dist.items()}
    
    # --- ME Level distribution ---
    if 'ME Level' in hist_df.columns:
        mel_dist = hist_df['ME Level'].value_counts().head(20).to_dict()
        results['me_level_distribution'] = {str(k): int(v) for k, v in mel_dist.items()}
    
    # --- Resource Type distribution ---
    if 'Resource Type' in hist_df.columns:
        rt_dist = hist_df['Resource Type'].value_counts().head(20).to_dict()
        results['resource_type_distribution'] = {str(k): int(v) for k, v in rt_dist.items()}

    # --- Temporal analysis: by day ---
    if 'Occurrence Time' in hist_df.columns:
        hist_df['date'] = hist_df['Occurrence Time'].dt.date
        daily = hist_df.groupby('date').size().reset_index()
        daily.columns = ['date', 'count']
        daily['date'] = daily['date'].astype(str)
        daily = daily.sort_values('date')
        results['daily_trend'] = daily.to_dict(orient='records')

    # --- Top NEs (most alarmed) ---
    if 'ME' in hist_df.columns:
        top_ne = hist_df['ME'].value_counts().head(30).reset_index()
        top_ne.columns = ['ne', 'alarm_count']
        results['top_ne'] = top_ne.to_dict(orient='records')
    
    # --- Repeat Count analysis ---
    if 'Repeat Count' in hist_df.columns:
        high_repeat = hist_df[pd.to_numeric(hist_df['Repeat Count'], errors='coerce') > 1]
        if len(high_repeat) > 0 and 'Alarm Code Name' in high_repeat.columns:
            rep_analysis = high_repeat.groupby('Alarm Code Name').agg(
                total_repeats=('Repeat Count', lambda x: pd.to_numeric(x, errors='coerce').sum()),
                occurrences=('Alarm Code Name', 'count')
            ).reset_index().sort_values('total_repeats', ascending=False).head(30)
            results['high_repeat_alarms'] = rep_analysis.to_dict(orient='records')

    # === ACTIVE ALARMS ANALYSIS ===
    if not active_df.empty:
        results['active_total'] = int(len(active_df))
        
        if 'Alarm Severity' in active_df.columns:
            act_sev = active_df['Alarm Severity'].value_counts().to_dict()
            results['active_severity'] = {str(k): int(v) for k, v in act_sev.items()}
        
        if 'Alarm Code Name' in active_df.columns:
            act_top = active_df['Alarm Code Name'].value_counts().head(30).reset_index()
            act_top.columns = ['alarm_code_name', 'count']
            results['active_top_alarms'] = act_top.to_dict(orient='records')

            # Cross-reference: active alarms that are filterable candidates
            if 'filterable_candidates' in results:
                filterable_names = {a['alarm_code_name'] for a in results['filterable_candidates']}
                act_top['is_filterable'] = act_top['alarm_code_name'].isin(filterable_names)
                results['active_filterable'] = act_top[act_top['is_filterable']].to_dict(orient='records')
        
        if 'ME' in active_df.columns:
            act_ne = active_df['ME'].value_counts().head(20).reset_index()
            act_ne.columns = ['ne', 'alarm_count']
            results['active_top_ne'] = act_ne.to_dict(orient='records')
        
        if 'Ack State' in active_df.columns:
            ack_dist = active_df['Ack State'].value_counts().to_dict()
            results['active_ack_distribution'] = {str(k): int(v) for k, v in ack_dist.items()}

    results['generated_at'] = datetime.now().isoformat()
    return results

def main():
    print("=" * 60)
    print("ALARM ANALYSIS STARTED")
    print("=" * 60)
    
    hist_df = load_all_history()
    active_df = load_active()
    
    if hist_df.empty:
        print("ERROR: No history data!")
        return
    
    # Print some stats
    print("\n=== QUICK STATS ===")
    print(f"History records: {len(hist_df)}")
    if 'Alarm Code Name' in hist_df.columns:
        print(f"Unique alarm types: {hist_df['Alarm Code Name'].nunique()}")
    if 'ME' in hist_df.columns:
        print(f"Unique NEs: {hist_df['ME'].nunique()}")
    if 'Alarm Severity' in hist_df.columns:
        print(f"Severity distribution:\n{hist_df['Alarm Severity'].value_counts()}")
    
    results = analyze(hist_df, active_df)
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n=== DONE ===")
    print(f"Results saved to: {OUTPUT_JSON}")
    print(f"Top filterable candidates: {len(results.get('filterable_candidates', []))}")
    print(f"Total history events: {results.get('total_history_events', 0)}")
    
    # Print top 10 filterable
    print("\n--- TOP 10 FILTERABLE CANDIDATES ---")
    for a in results.get('filterable_candidates', [])[:10]:
        print(f"  {a.get('alarm_code_name','?')}: {a.get('total_occurrences','?')} occurrences, score={a.get('filterability_score','?')}")

if __name__ == "__main__":
    main()
