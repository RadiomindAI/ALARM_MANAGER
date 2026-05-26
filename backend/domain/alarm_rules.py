# domain/alarm_rules.py
import yaml
from pathlib import Path
from config.settings import settings

class AlarmThresholds:
    def __init__(self):
        self.filterability_threshold = 0.85
        self.chronic_days = 21
        self.wizard_max_alarms = 50
        self.load()

    def load(self):
        p = settings.base_dir / "config" / "thresholds.yml"
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "kb" in data:
                    t = data["kb"]
                    self.filterability_threshold = float(t.get("filterability_threshold", self.filterability_threshold))
                    self.chronic_days = int(t.get("chronic_days", self.chronic_days))
                    self.wizard_max_alarms = int(t.get("wizard_max_alarms", self.wizard_max_alarms))
        except Exception:
            pass

alarm_thresholds = AlarmThresholds()
