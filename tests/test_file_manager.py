"""Tests for the File Manager page — SQL header parsing and index detection."""
import pytest
from mpd_overwatch.dashboard.file_manager import detect_index_type


def test_detect_index_type_always_dual():
    """SQL EDR dumps always contain both time and depth — dual index."""
    assert detect_index_type({}) == "dual"
    assert detect_index_type({"start_unit": "ft"}) == "dual"
    assert detect_index_type({"start_unit": "s"}) == "dual"
