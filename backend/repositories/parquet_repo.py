# repositories/parquet_repo.py
import pandas as pd
import logging
from pathlib import Path
from filelock import FileLock

logger = logging.getLogger(__name__)

class ParquetRepository:
    def __init__(self, path: Path, dedup_keys: list[str] = None):
        self.path = path
        self.dedup_keys = dedup_keys or []
        self._lock_path = str(path) + ".lock"

    def read(self) -> pd.DataFrame | None:
        """
        Legge in modo sicuro il file Parquet usando un FileLock.
        """
        if not self.path.exists():
            return None
        lock = FileLock(self._lock_path)
        with lock:
            try:
                return pd.read_parquet(self.path)
            except Exception as e:
                logger.error("Errore durante la lettura del file Parquet %s: %s", self.path, e)
                return None

    def append(self, new_rows: pd.DataFrame) -> int:
        """
        Aggiunge nuove righe al file Parquet con deduplica e salvataggio sicuro via FileLock.
        Ritorna il numero esatto di righe aggiunte.
        """
        if new_rows is None or new_rows.empty:
            return 0
            
        lock = FileLock(self._lock_path)
        with lock:
            try:
                existing = None
                if self.path.exists():
                    try:
                        existing = pd.read_parquet(self.path)
                    except Exception as e:
                        logger.error("Errore lettura file Parquet preesistente: %s", e)
                
                # Unisce i record
                combined = pd.concat([existing, new_rows], ignore_index=True) if existing is not None else new_rows.copy()
                
                # Esegue la deduplica se configurata
                before_len = len(combined)
                actual_keys = [k for k in self.dedup_keys if k in combined.columns]
                if actual_keys:
                    combined = combined.drop_duplicates(subset=actual_keys, keep="first")
                    
                added = len(combined) - (len(existing) if existing is not None else 0)
                
                # Salva su disco
                self.path.parent.mkdir(parents=True, exist_ok=True)
                combined.to_parquet(self.path, index=False, engine="pyarrow", compression="snappy")
                logger.info("Parquet '%s' aggiornato con successo: %d righe totali (+%d nuove)", self.path.name, len(combined), added)
                return max(0, added)
            except Exception as e:
                logger.error("Errore durante la scrittura del file Parquet %s: %s", self.path, e)
                return 0

    def filter_by_site(self, site_name: str, col: str = "ME") -> pd.DataFrame | None:
        """
        Filtra i dati leggendo dal Parquet per un determinato sito.
        """
        df = self.read()
        if df is None or df.empty:
            return None
        mask = df[col].astype(str).str.contains(site_name, na=False, regex=False)
        result = df[mask].copy()
        return result if not result.empty else None

    def get_status(self, date_col: str = "Occurrence Time") -> dict:
        """
        Restituisce metadati sullo stato del DB Parquet (conteggio righe, data min/max).
        """
        df = self.read()
        if df is None or df.empty:
            return {"available": False, "total_rows": 0}
            
        date_from = date_to = None
        # Verifica se la colonna della data è presente o se dobbiamo provare chiavi alternative
        actual_date_col = date_col if date_col in df.columns else ("Occurrence_Time" if "Occurrence_Time" in df.columns else ("Begin Time" if "Begin Time" in df.columns else None))
        
        if actual_date_col:
            try:
                valid = pd.to_datetime(df[actual_date_col], errors="coerce").dropna()
                if not valid.empty:
                    date_from = str(valid.min().date())
                    date_to = str(valid.max().date())
            except Exception as ex:
                logger.error("Errore estrazione date dallo status Parquet: %s", ex)
                
        return {
            "available": True,
            "total_rows": len(df),
            "date_from": date_from,
            "date_to": date_to
        }
