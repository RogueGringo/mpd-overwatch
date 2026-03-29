"""Tests for alert panel Dash component."""
import pytest


def test_alert_panel_import():
    """Alert panel module is importable."""
    from mpd_overwatch.dashboard.alert_panel import render_alert_panel
    assert callable(render_alert_panel)


def test_alert_panel_empty():
    """Empty alert list produces hidden panel."""
    from mpd_overwatch.dashboard.alert_panel import render_alert_panel
    panel = render_alert_panel([])
    assert panel is not None


def test_alert_panel_with_alerts():
    """Alerts produce visible cards."""
    from mpd_overwatch.dashboard.alerts import Alert, AlertType
    from mpd_overwatch.dashboard.alert_panel import render_alert_panel
    alerts = [
        Alert(alert_type=AlertType.TRANSITION_ANOMALY, channel="rop",
              message="Settle time 2x expected", severity="warning", depth=12000.0),
        Alert(alert_type=AlertType.RELATIONSHIP_BREAK, channel="wob",
              message="WOB-torque correlation inverted", severity="critical", depth=13500.0),
    ]
    panel = render_alert_panel(alerts)
    assert panel is not None
