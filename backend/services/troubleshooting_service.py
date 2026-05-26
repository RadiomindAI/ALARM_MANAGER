# services/troubleshooting_service.py
import sys
from pathlib import Path
from config.settings import settings

class TroubleshootingService:
    def __init__(self):
        root_dir = str(settings.base_dir.parent)
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
            
        # Importa una volta sola all'inizializzazione del servizio
        try:
            import WorkflowMWTroubleshootingZTE
            self._analyzer = WorkflowMWTroubleshootingZTE
        except ImportError as e:
            raise RuntimeError(f"Impossibile importare WorkflowMWTroubleshootingZTE: {e}")

    def analyze_site(self, df, site_name: str) -> dict:
        """
        Esegue l'analisi sul dataframe filtrato per il sito richiesto.
        """
        if df is None or (hasattr(df, 'empty') and df.empty):
            return {"error": f"Nessun dato PM disponibile per l'analisi del sito {site_name}"}
        return self._analyzer.analyze_and_return(df, site_name_filter=site_name)

troubleshooting_service = TroubleshootingService()
