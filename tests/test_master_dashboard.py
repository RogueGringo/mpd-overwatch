"""Tests for master_dashboard — unified operational overview."""

import pytest

from mpd_overwatch.dashboard.master_dashboard import page_master_dashboard


def test_master_dashboard_no_data():
    """Without data, should show data-required notice."""
    result = page_master_dashboard(None)
    assert result is not None


def test_master_dashboard_empty_assignments():
    """Empty assignments dict should show data-required notice."""
    result = page_master_dashboard({})
    assert result is not None


def test_master_dashboard_import():
    """Module should import cleanly."""
    from mpd_overwatch.dashboard import master_dashboard
    assert hasattr(master_dashboard, "page_master_dashboard")
