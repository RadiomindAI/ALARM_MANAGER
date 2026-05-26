# tests/test_pm_rules.py
import pytest
from domain.pm_rules import pm_thresholds

def test_pm_thresholds_loading():
    """Verifica che le soglie PM vengano caricate correttamente dal file YAML o abbiano i default corretti."""
    assert pm_thresholds.rsl_fading == -63.0
    assert pm_thresholds.rsl_nominal == -60.0
    assert pm_thresholds.xpi_critical == 20.0
    assert pm_thresholds.xpi_warning == 25.0
    assert pm_thresholds.mse_interference == -35.0
    assert pm_thresholds.delta_if_cable == 0.8
    assert pm_thresholds.downshift_warning == 0
