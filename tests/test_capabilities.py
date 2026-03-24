# tests/test_capabilities.py
"""Tests for capabilities page."""

import pytest
from dash import html


class TestCapabilitiesLayout:
    """Capabilities page renders with all expected sections."""

    def test_capabilities_renders(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        assert isinstance(layout, html.Div)

    def test_has_role_cards(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert "MPD Engineer" in text
        assert "Drilling Engineer" in text
        assert "Completions Engineer" in text
        assert "Reservoir Engineer" in text
        assert "Well Control" in text
        assert "Technical Leadership" in text

    def test_has_whats_unique_section(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert "Physics Consistency" in text
        assert "Pattern Discovery" in text or "Data Shape Discovery" in text

    def test_has_engine_inventory(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert "CLASSICAL" in text
        assert "NOVEL" in text
        assert "INFRA" in text or "INFRASTRUCTURE" in text

    def test_has_vendor_badges(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert "PASON" in text
        assert "SLB" in text or "HALLIBURTON" in text

    def test_vendor_count_from_mnemonic_map(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        from mpd_overwatch.config import MNEMONIC_MAP
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert str(len(MNEMONIC_MAP)) in text


def _extract_text(component, depth=0):
    if depth > 20:
        return ""
    texts = []
    if isinstance(component, str):
        texts.append(component)
    elif hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            texts.append(children)
        elif isinstance(children, list):
            for child in children:
                texts.append(_extract_text(child, depth + 1))
    return " ".join(texts)
