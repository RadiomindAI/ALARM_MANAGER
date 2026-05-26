# tests/test_alarm_rules.py
import pytest
from domain.alarm_rules import alarm_thresholds

def test_alarm_thresholds_loading():
    """Verifica che le soglie di classificazione allarmi e KB vengano caricate correttamente o abbiano i default giusti."""
    assert alarm_thresholds.filterability_threshold == 0.85
    assert alarm_thresholds.chronic_days == 21
    assert alarm_thresholds.wizard_max_alarms == 50
