# domain/pm_rules.py
import yaml
from pathlib import Path
from config.settings import settings

class PMThresholds:
    def __init__(self):
        self.rsl_fading = -63.0
        self.rsl_nominal = -60.0
        self.xpi_critical = 20.0
        self.xpi_warning = 25.0
        self.mse_interference = -35.0
        self.delta_if_cable = 0.8
        self.downshift_warning = 0
        self.load()

    def load(self):
        p = settings.base_dir / "config" / "thresholds.yml"
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "pm_radio" in data:
                    t = data["pm_radio"]
                    self.rsl_fading = float(t.get("rsl_fading_threshold_dbm", self.rsl_fading))
                    self.rsl_nominal = float(t.get("rsl_nominal_threshold_dbm", self.rsl_nominal))
                    self.xpi_critical = float(t.get("xpi_critical_threshold_db", self.xpi_critical))
                    self.xpi_warning = float(t.get("xpi_warning_threshold_db", self.xpi_warning))
                    self.mse_interference = float(t.get("mse_interference_threshold_db", self.mse_interference))
                    self.delta_if_cable = float(t.get("delta_if_cable_threshold_dbm", self.delta_if_cable))
                    self.downshift_warning = int(t.get("downshift_warning_seconds", self.downshift_warning))
        except Exception:
            pass

pm_thresholds = PMThresholds()
