# services/pm_service.py
import logging
import pandas as pd
from typing import Optional
from pathlib import Path
from fastapi import UploadFile, HTTPException
from config.settings import settings
from repositories.parquet_repo import ParquetRepository
from repositories.json_repo import load_json
from services.troubleshooting_service import troubleshooting_service
from utils.files import safe_save, cleanup_upload
from utils.cache import TTLCache

# Import PM opzionale
try:
    from core.pm_ingestion import process_pm_excel, get_pm_for_site, get_pm_status
    _PM_AVAILABLE = True
except Exception:
    _PM_AVAILABLE = False

logger = logging.getLogger(__name__)

class PMService:
    def __init__(self):
        # Inizializza il repository Parquet per le performance
        # La chiave di dedup previene l'aggiunta di duplicati (ME + PM Checkpoint + Begin Time)
        self._repo = ParquetRepository(
            settings.parquet_pm_path,
            dedup_keys=["ME", "PM Checkpoint", "Begin Time"]
        )
        # Inizializza cache per lo status PM
        self._status_cache = TTLCache(ttl_seconds=settings.pm_cache_ttl_seconds)

    def is_available(self) -> bool:
        return _PM_AVAILABLE

    async def process_uploads(self, files: list[UploadFile]) -> dict:
        """
        Salva i file Excel di performance caricati in modo sicuro, li elabora
        e li inserisce in modalità append+dedup nel database Parquet.
        """
        if not self.is_available():
            raise HTTPException(status_code=500, detail="Il modulo PM (pm_ingestion) non è disponibile nel backend.")

        total_inserted = 0
        processed_files = []
        
        for file in files:
            # Salva temporaneamente con UUID
            temp_path = safe_save(file, settings.upload_dir, prefix="pm_")
            try:
                # Carica l'excel in un DataFrame
                df = pd.read_excel(temp_path, engine="openpyxl")
                
                # Inserisci le righe tramite il repository Parquet
                added = self._repo.append(df)
                total_inserted += added
                processed_files.append(file.filename)
            except Exception as e:
                logger.error("Errore durante l'elaborazione del file PM %s: %s", file.filename, e)
                raise HTTPException(
                    status_code=400,
                    detail=f"Errore durante la lettura o il salvataggio del file '{file.filename}': {str(e)}"
                )
            finally:
                cleanup_upload(temp_path)

        # Invalida la cache dello status PM per forzare l'aggiornamento dei metadati
        self._status_cache.invalidate()

        return {
            "status": "success",
            "message": f"Caricamento completato. Elaborati {len(files)} file PM. Aggiunti {total_inserted} nuovi record.",
            "processed_files": processed_files,
            "added_records": total_inserted
        }

    def get_status(self) -> dict:
        """
        Restituisce i metadati sul DB PM, usando la cache a TTL di 5 minuti.
        """
        if not self.is_available():
            return {"available": False, "message": "Modulo PM non disponibile"}
            
        def _load_status():
            status = self._repo.get_status(date_col="Begin Time")
            # Aggiungi conteggio siti unici
            df = self._repo.read()
            if df is not None and not df.empty and "ME" in df.columns:
                unique_mes = df["ME"].dropna().unique()
                clean_sites = set(str(me).split("#")[0].strip() for me in unique_mes)
                status["unique_sites_count"] = len(clean_sites)
            else:
                status["unique_sites_count"] = 0
            return status

        return self._status_cache.get(_load_status)

    def analyze_site(self, site_name: str, date_from: Optional[str] = None, date_to: Optional[str] = None, freq_ghz: float = 13.0) -> dict:
        """
        Esegue l'analisi completa per un determinato sito dal Parquet storico.
        """
        if not self.is_available():
            raise HTTPException(status_code=500, detail="Il modulo PM non è configurato.")

        # Carica il DataFrame per il sito (include anche il remoto se presente nel DB)
        # get_pm_for_site gestisce la ricerca topologica in SITI RIMASTI.xlsx per accoppiare Sito A e Sito B
        df = get_pm_for_site(site_name)
        if df is None or (hasattr(df, 'empty') and df.empty):
            return {
                "available": False,
                "message": f"Nessun dato PM trovato per '{site_name}'. Caricare prima un file PM."
            }

        # Filtra le date se specificato
        if date_from or date_to:
            try:
                df = df.copy()
                df['Begin Time'] = pd.to_datetime(df['Begin Time'])
                if date_from:
                    dt_from = pd.to_datetime(date_from).date()
                    df = df[df['Begin Time'].dt.date >= dt_from]
                if date_to:
                    dt_to = pd.to_datetime(date_to).date()
                    df = df[df['Begin Time'].dt.date <= dt_to]
            except Exception as ex:
                logger.error("Errore durante il filtraggio per date %s - %s: %s", date_from, date_to, ex)

            if df.empty:
                range_str = f"dal {date_from}" if date_from else ""
                if date_to:
                    range_str += f" al {date_to}"
                return {
                    "available": False,
                    "message": f"Nessun dato PM trovato per '{site_name}' nell'intervallo {range_str}."
                }

        try:
            # Esegue l'analisi tramite il troubleshooting_service (hot-reload rimosso!)
            result = troubleshooting_service.analyze_site(df, site_name)
            result["available"] = True
            
            # Integrazione meteo opzionale
            try:
                from core.weather_service import geocode_city, fetch_weather, correlate_weather_with_degradation
                windows = result.get("degradation_windows", [])
                if windows:
                    # Estrae il nome città (prima parte del nome sito prima del trattino)
                    city_candidate = site_name.split("-")[0].strip()
                    coords = geocode_city(city_candidate)
                    if coords:
                        # Estrai il range di date corretto per l'API meteo
                        dates = []
                        for w in windows:
                            try:
                                dates.append(pd.to_datetime(w["start"]))
                                dates.append(pd.to_datetime(w["end"]))
                            except Exception:
                                pass
                        if dates:
                            min_date = min(dates).strftime("%Y-%m-%d")
                            max_date = max(dates).strftime("%Y-%m-%d")
                            weather_data = fetch_weather(coords["lat"], coords["lon"], min_date, max_date)
                            if weather_data:
                                # Correla le performance degradate con il vento/pioggia rilevato
                                correlations = correlate_weather_with_degradation(weather_data, windows)
                                # Aggiungi informazioni geografiche necessarie al frontend
                                correlations["location"] = {
                                    "name": coords["name"],
                                    "region": coords["region"]
                                }
                                result["weather_correlation"] = correlations
                                result["weather_correlations"] = correlations
                                result["weather_data_available"] = True

                                # Aggiorna le conclusioni in tempo reale con i dati meteo
                                summary = correlations.get("summary_text", "")
                                if summary:
                                    new_conclusions = []
                                    replaced = False
                                    for line in result.get("conclusion", []):
                                        # Rimuove/sostituisce i suggerimenti di controllo manuale con la risposta reale
                                        if any(x in line for x in ["Esclusione Ambientale", "Controllare se l'orario", "Se è pioggia"]):
                                            if not replaced:
                                                new_conclusions.append(f"🤖 ANALISI METEO AUTOMATICA: {summary}")
                                                replaced = True
                                        else:
                                            new_conclusions.append(line)
                                    if not replaced:
                                        new_conclusions.append(f"🤖 ANALISI METEO AUTOMATICA: {summary}")
                                    result["conclusion"] = new_conclusions
            except Exception as w_err:
                logger.warning("Integrazione meteo fallita durante l'analisi del sito %s: %s", site_name, w_err)

            # Funzione di pulizia ricorsiva per sostituire NaN/Inf con None per la serializzazione JSON
            def _sanitize_json(val):
                import math
                if isinstance(val, dict):
                    return {k: _sanitize_json(v) for k, v in val.items()}
                elif isinstance(val, list):
                    return [_sanitize_json(x) for x in val]
                elif isinstance(val, float):
                    if math.isnan(val) or math.isinf(val):
                        return None
                    return val
                elif pd.isna(val):
                    return None
                return val

            return _sanitize_json(result)
        except Exception as e:
            logger.error("Errore durante l'analisi del sito %s: %s", site_name, e)
            raise HTTPException(status_code=500, detail=f"Errore durante l'analisi: {str(e)}")

# Istanza singleton
pm_service = PMService()
