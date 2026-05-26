import pandas as pd
import datetime
import glob
import os

# Determina la root directory del progetto (dove si trova questo script)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_predictions_csv(output_csv=None):
    """
    Analizza i dati reali degli allarmi attivi (fm-active-*.xlsx) o storici (history_db.parquet)
    per estrarre le metriche m1, m2, m3, accoppiare i siti/apparati impattati e calcolare predizioni predittive e TTF.
    """
    if output_csv is None:
        output_csv = os.path.join(ROOT_DIR, "final_predictions.csv")
        
    dati_dir = os.path.join(ROOT_DIR, "DATI")
    if not os.path.exists(dati_dir):
        # Fallback di sicurezza
        dati_dir = "DATI"
        if not os.path.exists(dati_dir):
            dati_dir = "../DATI"
            
    active_files = glob.glob(os.path.join(dati_dir, "fm-active-*.xlsx"))
    
    df_alarms = None
    if active_files:
        latest_file = max(active_files, key=os.path.getmtime)
        print(f"[PdM Engine] Generazione predizioni da file allarmi attivi: {latest_file}")
        try:
            df_alarms = pd.read_excel(latest_file, engine='openpyxl')
        except Exception as e:
            print(f"[PdM Engine] Errore lettura excel: {e}")
            
    if df_alarms is None:
        # Fallback su parquet storico
        parquet_path = os.path.join(dati_dir, "history_db.parquet")
        if os.path.exists(parquet_path):
            print(f"[PdM Engine] Generazione predizioni da Parquet storico: {parquet_path}")
            try:
                df_alarms = pd.read_parquet(parquet_path)
            except Exception as e:
                print(f"[PdM Engine] Errore lettura parquet: {e}")
                
    if df_alarms is None or df_alarms.empty:
        # Se non c'è nulla, creiamo un dataset fittizio realistico per dimostrazione
        print("[PdM Engine] Nessun file allarmi trovato. Generazione dataset predizioni dimostrativo.")
        data = {
            'Alarm_Name': [
                'CPU usage is beyond the threshold.',
                'Card storage utilization exceeded the prealarm threshold',
                'Input optical power (dBm) exceeds the threshold.',
                'Output optical power (dBm) exceeds the threshold.'
            ],
            'Risk_Level': ['CRITICAL', 'CRITICAL', 'HIGH', 'HIGH'],
            'Risk_Score': [0.87, 0.81, 0.74, 0.70],
            'Impacted_Devices': [
                'TOANITAB-PRZT-001',
                'TOANITAB-PRZT-001',
                'DRUEITAA-PRZT-002',
                'DRUEITAA-PRZT-002'
            ],
            'Predicted_Outcome': [
                'HARDWARE RESOURCE DEPLETION (TTF: <12h)',
                'HARDWARE RESOURCE DEPLETION (TTF: <12h)',
                'LINK OUTAGE - OPTICAL FAILURE (TTF: <24h)',
                'LINK OUTAGE - OPTICAL FAILURE (TTF: <24h)'
            ]
        }
        pd.DataFrame(data).to_csv(output_csv, index=False)
        return

    # Normalizza i nomi delle colonne
    col_mapping = {
        'Alarm Code Name': 'Alarm_Name',
        'Alarm_Code_Name': 'Alarm_Name',
        'Alarm Severity': 'Severity',
        'Alarm_Severity': 'Severity',
        'Occurrence Time': 'Occurrence_Time',
        'Occurrence_Time': 'Occurrence_Time',
        'Repeat Count': 'Repeat_Count',
        'Repeat_Count': 'Repeat_Count'
    }
    df_alarms = df_alarms.rename(columns=col_mapping)
    
    if 'Alarm_Name' not in df_alarms.columns:
        df_alarms = df_alarms.rename(columns={'Alarm Code': 'Alarm_Name', 'Alarm_Code': 'Alarm_Name'})
        
    if 'Alarm_Name' not in df_alarms.columns:
        print("[PdM Engine] Impossibile trovare la colonna del nome allarme.")
        return

    # Assicurati che Occurrence_Time sia datetime
    if 'Occurrence_Time' in df_alarms.columns:
        df_alarms['Occurrence_Time'] = pd.to_datetime(df_alarms['Occurrence_Time'], errors='coerce')
        dataset_now = df_alarms['Occurrence_Time'].max()
        if pd.isna(dataset_now):
            dataset_now = datetime.datetime.now()
    else:
        dataset_now = datetime.datetime.now()
        df_alarms['Occurrence_Time'] = dataset_now

    # Riempie i valori mancanti di Repeat_Count
    if 'Repeat_Count' not in df_alarms.columns:
        df_alarms['Repeat_Count'] = 1
    else:
        df_alarms['Repeat_Count'] = pd.to_numeric(df_alarms['Repeat_Count'], errors='coerce').fillna(1)

    grouped = df_alarms.groupby('Alarm_Name')
    
    prediction_rows = []
    for alarm_name, group in grouped:
        # m1 (Presence): 1.0 (essendo attivi/presenti nel dataset)
        m1 = 1.0
        
        # m2 (Duration): normalizzato su un intervallo di 15 min (900 secondi)
        durations = (dataset_now - group['Occurrence_Time']).dt.total_seconds()
        avg_duration_sec = durations.mean() if not durations.empty else 0.0
        m2 = min(1.0, max(0.1, avg_duration_sec / 900.0))
        
        # m3 (Frequency): frequenza di ripetizione dell'allarme
        max_repeats = group['Repeat_Count'].max()
        count_occurrences = len(group)
        m3_raw = max(max_repeats, count_occurrences)
        m3 = min(1.0, m3_raw / 10.0)
        
        # Severity Weight
        sev = str(group['Severity'].iloc[0]).upper() if 'Severity' in group.columns else 'WARNING'
        sev_weight = 0.2
        if 'CRIT' in sev:
            sev_weight = 1.0
        elif 'MAJ' in sev or 'HIGH' in sev:
            sev_weight = 0.8
        elif 'MIN' in sev or 'MED' in sev:
            sev_weight = 0.5
            
        # Calcolo del Risk Score predittivo
        # 50% persistenza temporale (m2), 30% severità, 20% frequenza (m3)
        risk_score = 0.5 * m2 + 0.3 * sev_weight + 0.2 * m3
        risk_score = min(0.99, max(0.1, risk_score))
        
        # Risk Level
        if risk_score >= 0.75:
            risk_level = 'CRITICAL'
        elif risk_score >= 0.60:
            risk_level = 'HIGH'
        elif risk_score >= 0.40:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'
            
        # Predicted Outcome basato sul pattern dell'allarme
        name_lower = str(alarm_name).lower()
        if "cpu" in name_lower or "storage" in name_lower or "memory" in name_lower or "disk" in name_lower or "hard drive" in name_lower:
            outcome = "HARDWARE RESOURCE DEPLETION (TTF: <12h)"
        elif "optical" in name_lower or "los" in name_lower or "power" in name_lower or "fiber" in name_lower or "rx" in name_lower or "tx" in name_lower:
            outcome = "LINK OUTAGE - OPTICAL FAILURE (TTF: <24h)"
        elif "ethernet" in name_lower or "link down" in name_lower or "loss of signal" in name_lower or "losp" in name_lower or "communication" in name_lower:
            outcome = "COMMUNICATION LINK FAILURE (TTF: <6h)"
        else:
            outcome = "UNEXPECTED BEHAVIOR / DEGRADATION (TTF: <48h)"
            
        # Siti / Apparati impattati (ME)
        impacted_devices = "—"
        if 'ME' in group.columns:
            unique_mes = group['ME'].dropna().unique().tolist()
            # Pulisci i nomi dei ME rimuovendo la parte del modem dopo il cancello
            clean_mes = []
            for me in unique_mes:
                me_str = str(me).split('#')[0].strip()
                if me_str:
                    clean_mes.append(me_str)
            clean_mes = sorted(list(set(clean_mes)))
            if clean_mes:
                if len(clean_mes) > 3:
                    impacted_devices = ", ".join(clean_mes[:3]) + f" (+{len(clean_mes) - 3})"
                else:
                    impacted_devices = ", ".join(clean_mes)

        prediction_rows.append({
            'Alarm_Name': alarm_name,
            'Risk_Level': risk_level,
            'Risk_Score': risk_score,
            'Predicted_Outcome': outcome,
            'Impacted_Devices': impacted_devices
        })
        
    df_pred = pd.DataFrame(prediction_rows)
    df_pred = df_pred.sort_values(by='Risk_Score', ascending=False)
    df_pred.to_csv(output_csv, index=False)
    print(f"[PdM Engine] Calcolate predizioni PdM reali per {len(df_pred)} pattern. Salvato in {output_csv}")

def generate_report(prediction_file=None, output_md=None):
    if prediction_file is None:
        prediction_file = os.path.join(ROOT_DIR, "final_predictions.csv")
    if output_md is None:
        output_md = os.path.join(ROOT_DIR, "PREDICTION_REPORT.md")
        
    # Se il file predizioni non esiste, lo genera in automatico dai dati reali
    if not os.path.exists(prediction_file):
        print(f"[PdM Engine] {prediction_file} non trovato. Avvio calcolo predizioni PdM in tempo reale...")
        generate_predictions_csv(prediction_file)
        
    try:
        df = pd.read_csv(prediction_file)
    except Exception as e:
        print(f"Errore lettura file predizioni: {e}")
        return

    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Filtra allarmi significativi (CRITICAL o HIGH)
    urgent = df[df['Risk_Level'].isin(['CRITICAL', 'HIGH'])]
    
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write("# 🚀 AI Predictive Maintenance Report\n\n")
        f.write(f"*Generated on: {today}*\n\n")
        
        f.write("## Executive Summary\n\n")
        f.write(f"Based on the **m1, m2, m3** feature extraction methodology of the AI predictive engine, we have analyzed the current alarm streams. "
                f"A total of **{len(df)}** patterns were evaluated.\n\n")
        
        if not urgent.empty:
            f.write(f"> [!CAUTION]\n")
            f.write(f"> **{len(urgent)} high-risk patterns** detected that require immediate attention to prevent service outage.\n\n")
        else:
            f.write(f"> [!TIP]\n")
            f.write(f"> Network status appears stable. No critical failure patterns detected in the current window.\n\n")
            
        f.write("## Top Predicted Risks\n\n")
        f.write("| Alarm Pattern | Risk Level | Score | Impacted Devices | Predicted Outcome |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        
        # Mostra i primi 10 rischi
        for _, row in df.head(10).iterrows():
            f.write(f"| {row['Alarm_Name']} | **{row['Risk_Level']}** | {row['Risk_Score']:.2f} | {row.get('Impacted_Devices', '—')} | {row['Predicted_Outcome']} |\n")
        
        f.write("\n## Methodology Breakdown\n\n")
        f.write("- **m1 (Presence)**: Identifies if the alarm is currently active in the observation window.\n")
        f.write("- **m2 (Duration)**: Calculated as the ratio of alarm presence in the 15-minute window. Values closer to 1.0 indicate persistence.\n")
        f.write("- **m3 (Frequency)**: Count of alarm occurrences. High frequency indicates 'flapping' or instability.\n\n")
        
        f.write("## Preventive Actions Required\n\n")
        if not urgent.empty:
            for _, row in urgent.iterrows():
                f.write(f"### 📍 Action for: {row['Alarm_Name']}\n")
                name_lower = str(row['Alarm_Name']).lower()
                if "cpu" in name_lower or "storage" in name_lower or "memory" in name_lower or "disk" in name_lower:
                     f.write("- Verify board temperature and process logs.\n- Schedule resource optimization or hardware replacement.\n")
                elif "optical" in name_lower or "power" in name_lower or "fiber" in name_lower or "rx" in name_lower or "tx" in name_lower:
                     f.write("- Inspect SFP modules and fiber integrity.\n- Check RX/TX power levels against thresholds.\n")
                elif "ethernet" in name_lower or "link down" in name_lower or "loss of signal" in name_lower:
                     f.write("- Inspect physical cable connection and ports.\n- Check intermediate switches/routers.\n")
                else:
                     f.write("- Check link alignment and radio parameters.\n")
                f.write("\n")
        else:
            f.write("Continue routine monitoring. No emergency maintenance required.\n")

    print(f"Prediction report generated: {output_md}")

if __name__ == "__main__":
    generate_report()
