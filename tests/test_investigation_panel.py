"""Tests for investigation panel Dash component."""
import pytest


def test_investigation_panel_import():
    """Investigation panel module is importable."""
    from mpd_overwatch.dashboard.investigation_panel import render_investigation_panel
    assert callable(render_investigation_panel)


def test_investigation_panel_no_dossier():
    """No dossier -> empty panel."""
    from mpd_overwatch.dashboard.investigation_panel import render_investigation_panel
    panel = render_investigation_panel(None, None)
    assert panel is not None


def test_render_point_result():
    """Point query result renders as structured card."""
    from mpd_overwatch.dashboard.investigation_panel import render_point_result
    result = {
        "depth": 10000.0,
        "state": "drilling",
        "channels": [
            {"canonical": "rop", "value": 85.0, "units": "ft/hr",
             "health": {"status": "normal", "detail": "Within DRILLING range"}},
        ],
        "transitions_nearby": [],
    }
    card = render_point_result(result)
    assert card is not None


def test_render_channel_result():
    """Channel query result renders dossier summary."""
    from mpd_overwatch.dashboard.investigation_panel import render_channel_result
    result = {
        "found": True,
        "identity": {"canonical": "rop", "wits_id": "0113", "units": "ft/hr",
                      "physics_domain": "MECHANICAL", "index_type": "BRIDGES_BOTH"},
        "operational_meaning": {"what_it_measures": "Drilling rate"},
        "state_profiles": {"DRILLING": {"range": [20, 150], "trend": "flat",
                                         "informative": True}},
        "relationships": [],
        "artifacts": [],
    }
    card = render_channel_result(result)
    assert card is not None
