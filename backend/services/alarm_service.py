# services/alarm_service.py
import logging
import pandas as pd
from typing import Optional
from pathlib import Path
from fastapi import UploadFile, HTTPException
from config.settings import settings
from repositories.parquet_repo import ParquetRepository
from repositories.json_repo import load_json, save_json
from utils.files import safe_save, cleanup_upload

# Import core ingestion functions
from core.ingestion import process_excel, load_topology_db, get_alarms_status

logger = logging.getLogger(__name__)

class AlarmService:
    def __init__(self):
        # Inizializza il repository Parquet per gli allarmi storici
        self._repo = ParquetRepository(
            settings.parquet_alarms_path,
            dedup_keys=["ME", "Alarm Code Name", "Occurrence Time"]
        )
        self._session_path = settings.data_dir / "last_session.json"
        self._operator_kb_path = settings.operator_kb_path
        self._alarm_kb_path = settings.alarm_kb_path

    def _default_operator_kb(self) -> dict:
        return {
            "wizard_completed": False,
            "wizard_completed_at": None,
            "operator_rules": {},
            "new_alarm_history": [],
        }

    async def process_uploads(self, files: list[UploadFile]) -> dict:
        """
        Elabora in modo sicuro i file allarmi caricati, ricalcola il triage
        e aggiorna la sessione temporanea.
        """
        combined_alarms = []
        combined_new_alarms = []

        for file in files:
            temp_path = safe_save(file, settings.upload_dir, prefix="fm_")
            try:
                results = process_excel(str(temp_path))
                combined_alarms.extend(results.get('alarms', []))
                combined_new_alarms.extend(results.get('new_alarms', []))
            except ValueError as ve:
                logger.warning("Validazione fallita per %s: %s", file.filename, ve)
                raise HTTPException(status_code=400, detail=f"Errore in {file.filename}: {str(ve)}")
            except Exception as e:
                logger.error("Errore elaborazione file %s: %s", file.filename, e, exc_info=True)
                raise HTTPException(status_code=500, detail=f"Errore interno elaborando {file.filename}")
            finally:
                cleanup_upload(temp_path)

        # Deduplica i risultati combinati per chiave univoca
        seen = set()
        deduped_alarms = []
        for a in combined_alarms:
            key = (a.get('ME'), a.get('Alarm Code Name'), a.get('Occurrence Time'))
            if key not in seen:
                seen.add(key)
                deduped_alarms.append(a)

        # Ricalcola le statistiche aggregate
        total_stats = {
            'total': len(deduped_alarms),
            'new_alarms_count': sum(1 for a in deduped_alarms if a.get('Is_New_Alarm') and a.get('Action') in ('ESCALATE', 'MONITOR', 'INVESTIGATE')),
            'categories': {
                'Tolerable':              sum(1 for a in deduped_alarms if a.get('Action') == 'TOLERABLE'),
                'Monitor':                sum(1 for a in deduped_alarms if a.get('Action') == 'MONITOR'),
                'Escalate':               sum(1 for a in deduped_alarms if a.get('Action') == 'ESCALATE'),
                'Investigate':            sum(1 for a in deduped_alarms if a.get('Action') == 'INVESTIGATE'),
                'Chronic_Feedback_Needed': sum(1 for a in deduped_alarms if a.get('Is_Chronic')),
                'Structural':             sum(1 for a in deduped_alarms if a.get('Is_Structural')),
                'New':                    sum(1 for a in deduped_alarms if a.get('Is_New_Alarm') and a.get('Action') in ('ESCALATE', 'MONITOR', 'INVESTIGATE')),
            }
        }

        seen_new = set()
        deduped_new = []
        for a in combined_new_alarms:
            key = (a.get('ME'), a.get('Alarm Code Name'), a.get('Occurrence Time'))
            if key not in seen_new:
                seen_new.add(key)
                deduped_new.append(a)

        final_results = {
            'stats':      total_stats,
            'alarms':     deduped_alarms,
            'new_alarms': deduped_new,
        }

        # Salva la sessione
        save_json(self._session_path, final_results)
        return {"status": "success", "data": final_results}

    def get_status(self) -> dict:
        return self._repo.get_status(date_col="Occurrence Time")

    def get_last_session(self) -> dict:
        data = load_json(self._session_path)
        return {"available": bool(data), "data": data}

    def clear_last_session(self) -> dict:
        self._session_path.unlink(missing_ok=True)
        return {"status": "ok"}

    def get_ne_history(self, me_name: str) -> dict:
        """
        Recupera lo storico e suggerisce soluzioni per l'NE richiesto ed il suo partner remoto.
        """
        df = self._repo.read()
        if df is None or df.empty:
            return {"error": "Storico allarmi non disponibile"}
            
        if 'ME' not in df.columns:
            return {"error": "Colonna ME mancante nello storico"}

        me_df = df[df['ME'] == me_name].copy()
        remote_me = None
        remote_df = pd.DataFrame()

        # Carica topologia per accoppiamento
        db_partner, _, _, _, _ = load_topology_db()
        me_ip = None
        if 'ME_IP' in me_df.columns and len(me_df) > 0:
            me_ip = me_df['ME_IP'].dropna().iloc[0]

        partner_ip = db_partner.get(me_ip) if me_ip else None
        if partner_ip:
            remote_df = df[df['ME_IP'] == partner_ip].copy()
            if len(remote_df) > 0:
                remote_me = remote_df['ME'].iloc[0]
        else:
            # Fallback subnet
            subnet = None
            if 'Subnet_28' in me_df.columns and len(me_df) > 0:
                subnet = me_df['Subnet_28'].dropna().iloc[0]
            if subnet:
                subnet_df = df[df['Subnet_28'] == subnet]
                other_mes = subnet_df[subnet_df['ME'] != me_name]['ME'].unique()
                if len(other_mes) > 0:
                    remote_me = other_mes[0]
                    remote_df = df[df['ME'] == remote_me].copy()

        def format_df(d):
            if len(d) == 0: return []
            if 'Occurrence_Time' in d.columns:
                d = d.sort_values(by='Occurrence_Time', ascending=False)
            elif 'Occurrence Time' in d.columns:
                d = d.sort_values(by='Occurrence Time', ascending=False)
            d = d.head(150)
            res = []
            for _, r in d.iterrows():
                name = r.get("Alarm_Code_Name", r.get("Alarm Code Name", ""))
                sev = r.get("Alarm_Severity", r.get("Alarm Severity", ""))
                t = r.get("Occurrence_Time", r.get("Occurrence Time", ""))
                res.append({
                    "Alarm_Code_Name": str(name),
                    "Alarm_Severity": str(sev),
                    "Occurrence_Time": str(t),
                })
            return res

        local_alarms = format_df(me_df)
        remote_alarms = format_df(remote_df)
        
        local_codes = set([a['Alarm_Code_Name'] for a in local_alarms])
        remote_codes = set([a['Alarm_Code_Name'] for a in remote_alarms])
        
        solutions = []
        if local_codes & remote_codes:
            solutions.append("Allarmi simmetrici rilevati: Possibile problema di propagazione o degrado tratta.")
        if any(c in local_codes or c in remote_codes for c in ["MW_LOF", "MW_BER_SD", "R_LOS", "Fiber Break", "Loss of Signal"]):
            solutions.append("Verificare allineamento parabole e interferenze (LOF/BER/LOS rilevati).")
        if not solutions:
            solutions.append("Verificare alimentazione, porte ottiche e power locale/remota.")

        return {
            "local_me": me_name,
            "local_alarms": local_alarms,
            "remote_me": remote_me,
            "remote_alarms": remote_alarms,
            "suggested_solutions": solutions
        }

# Istanza singleton
alarm_service = AlarmService()
