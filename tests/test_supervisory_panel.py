import pytest


def test_supervisory_no_financial_kpis():
    """Supervisory panel must have no financial KPIs."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.supervisory_panel")
    with open(source.origin) as f:
        content = f.read()
    assert "npt_cost" not in content
    assert "drill_savings" not in content
    assert "production_value" not in content
    assert "oil_price" not in content
    assert "rig_rate" not in content
    assert "demo_generator" not in content
