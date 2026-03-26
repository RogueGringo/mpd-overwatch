# tests/test_shadow_tables.py
import pytest
import numpy as np
from mpd_overwatch.data.shadow_tables import (
    COMPUTED_CHANNELS, write_shadow_sql, build_computed_channel,
)
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


def test_computed_channels_registry():
    assert "ecd_computed" in COMPUTED_CHANNELS
    assert COMPUTED_CHANNELS["ecd_computed"]["witsid_base"] == 9001


def test_build_computed_channel():
    times = np.array(["2025-07-03T21:34:48", "2025-07-03T21:35:00"], dtype="datetime64[s]")
    depths = np.array([850.4, 851.0])
    values = np.array([12.5, 12.6])
    cf = build_computed_channel("ecd_computed", times, depths, values)
    assert cf.wits_id == "9001"
    assert cf.source == "COMPUTED"
    assert cf.units == "ppg"
    assert cf.n_points == 2


def test_write_shadow_sql(tmp_path):
    times = np.array(["2025-07-03T21:34:48", "2025-07-03T21:35:00"], dtype="datetime64[s]")
    depths = np.array([850.4, 851.0])
    values = np.array([12.5, 12.6])
    cf = build_computed_channel("ecd_computed", times, depths, values)

    outpath = tmp_path / "computed.sql"
    write_shadow_sql({"ecd_computed": cf}, outpath)

    content = outpath.read_text()
    assert 'CREATE TABLE IF NOT EXISTS public."T9001"' in content
    assert "INSERT INTO public.idtable" in content
    assert "COPY" in content
    assert "12.5" in content
