# services/predictive_service.py
import sys
import logging
from pathlib import Path
from config.settings import settings
from repositories.json_repo import load_json
from repositories.parquet_repo import ParquetRepository

logger = logging.getLogger(__name__)

class PredictiveService:
    def __init__(self):
        root_dir = str(settings.base_dir.parent)
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
            
        try:
            import prediction_report_generator
            self._report_engine = prediction_report_generator
        except ImportError as e:
            logger.error("Impossibile importare prediction_report_generator: %s", e)
            self._report_engine = None

    def get_realtime_report(self) -> dict:
        """
        Rileva e genera i rischi di manutenzione predittiva in tempo reale.
        """
        if not self._report_engine:
            raise RuntimeError("prediction_report_generator non configurato nel backend.")

        csv_path = settings.base_dir.parent / "final_predictions.csv"
        md_path = settings.base_dir.parent / "PREDICTION_REPORT.md"

        # Rigenera le predizioni reali e il report in tempo reale
        self._report_engine.generate_predictions_csv(str(csv_path))
        self._report_engine.generate_report(str(csv_path), str(md_path))

        # Leggi le predizioni generate dal CSV
        predictions = []
        if csv_path.exists():
            import pandas as pd
            df_pred = pd.read_csv(csv_path)
            predictions = df_pred.to_dict(orient="records")

        # Leggi il report markdown generato
        markdown_content = ""
        if md_path.exists():
            with open(md_path, "r", encoding="utf-8") as f:
                markdown_content = f.read()

        return {
            "status": "success",
            "predictions": predictions,
            "markdown": markdown_content
        }

# Istanza singleton
predictive_service = PredictiveService()
