# config/settings.py
import os
from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache

class Settings(BaseSettings):
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    
    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"
        
    @property
    def dati_dir(self) -> Path:
        # Fallback dynamic path search
        dati_p = self.base_dir.parent / "DATI"
        if not dati_p.exists():
            dati_p = self.base_dir / "DATI"
        if not dati_p.exists():
            dati_p = Path("DATI")
        return dati_p.resolve()
        
    @property
    def upload_dir(self) -> Path:
        return self.base_dir / "uploads"
        
    @property
    def frontend_dist(self) -> Path:
        return self.base_dir.parent / "frontend" / "dist"

    # Derived paths (KB files)
    @property
    def alarm_kb_path(self) -> Path:
        return self.data_dir / "alarm_kb.json"

    @property
    def operator_kb_path(self) -> Path:
        return self.data_dir / "operator_kb.json"

    @property
    def parquet_alarms_path(self) -> Path:
        return self.dati_dir / "history_db.parquet"

    @property
    def parquet_pm_path(self) -> Path:
        return self.dati_dir / "pm_history.parquet"

    # App Config
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    pm_cache_ttl_seconds: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
