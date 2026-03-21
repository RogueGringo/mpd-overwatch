"""Tests for the File Manager page — LAS header parsing and index detection."""
import pytest
from mpd_overwatch.dashboard.file_manager import parse_las_header, detect_index_type

# Use a real LAS file from the example data
LAS_FILE = (
    "OILFIELD_DRILLING_DATA_EXAMPLE_FILES/EDR_DATA/LAS_Depth/"
    "CLIENT3_Start_2025_Jul_17 10-21_End_2025_Jul_17 19-21_1760143723100.las"
)


@pytest.mark.skipif(
    not __import__("os").path.exists(LAS_FILE),
    reason="Test LAS file not available",
)
def test_parse_las_header():
    info = parse_las_header(LAS_FILE)
    assert "well_name" in info
    assert "curve_count" in info
    assert info["curve_count"] > 100
    assert "curve_names" in info
    assert isinstance(info["curve_names"], list)


@pytest.mark.skipif(
    not __import__("os").path.exists(LAS_FILE),
    reason="Test LAS file not available",
)
def test_detect_index_type():
    info = parse_las_header(LAS_FILE)
    idx_type = detect_index_type(info)
    assert idx_type in ("depth", "time")
