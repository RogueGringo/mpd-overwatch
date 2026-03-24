# tests/test_landing.py
"""Tests for landing page layout."""

import pytest
from dash import html


class TestLandingLayout:
    """Landing page renders without error and has expected components."""

    def test_landing_renders(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        assert isinstance(layout, html.Div)

    def test_landing_has_hero_section(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        text = _extract_text(layout)
        assert "MPD COMMAND" in text

    def test_landing_has_mission_cards(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        text = _extract_text(layout)
        assert "Analyze a Well" in text
        assert "Engineering Proof" in text
        assert "Analysis Engines" in text
        assert "Platform Capabilities" in text

    def test_landing_has_proof_badges(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        text = _extract_text(layout)
        assert "ENGINES" in text
        assert "V&V" in text

    def test_landing_has_engine_status_strip(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        text = _extract_text(layout)
        assert "Pressure & Flow" in text or "HYDRAULICS" in text.upper()

    def test_landing_mission_cards_link_to_correct_routes(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        from dash import dcc
        layout = landing_layout()
        links = _find_links(layout)
        hrefs = [link.href for link in links]
        assert "/files" in hrefs
        assert "/formulas" in hrefs
        assert "/engines" in hrefs
        assert "/capabilities" in hrefs

    def test_landing_no_sidebar_class(self):
        """Landing layout should NOT contain a sidebar element."""
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        assert isinstance(layout, html.Div)


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


def _find_links(component, depth=0):
    """Recursively find all dcc.Link components."""
    from dash import dcc
    if depth > 20:
        return []
    links = []
    if isinstance(component, dcc.Link):
        links.append(component)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                links.extend(_find_links(child, depth + 1))
        elif hasattr(children, "children"):
            links.extend(_find_links(children, depth + 1))
    return links
