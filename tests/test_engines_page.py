"""Tests for engine overview page."""

import pytest
from dash import html


class TestEnginesLayout:
    """Engine overview page renders with all 12 engines."""

    def test_engines_page_renders(self):
        from mpd_overwatch.dashboard.engines import engines_layout
        layout = engines_layout()
        assert isinstance(layout, html.Div)

    def test_all_12_engines_present(self):
        from mpd_overwatch.dashboard.engines import engines_layout
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        layout = engines_layout()
        text = _extract_text(layout)
        for engine in ENGINE_REGISTRY:
            assert engine["display_name"] in text, f"Missing: {engine['display_name']}"

    def test_engine_status_header(self):
        from mpd_overwatch.dashboard.engines import engines_layout
        layout = engines_layout()
        text = _extract_text(layout)
        assert "ENGINE" in text.upper()

    def test_log_panel_present(self):
        from mpd_overwatch.dashboard.engines import engines_layout
        layout = engines_layout()
        text = _extract_text(layout)
        assert "LOG" in text.upper()

    def test_register_callbacks_exists(self):
        from mpd_overwatch.dashboard.engines import register_engines_callbacks
        assert callable(register_engines_callbacks)


def _extract_text(component, depth=0):
    """Recursively extract text content from Dash components."""
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
