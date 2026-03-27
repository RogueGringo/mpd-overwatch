"""Tests for Layer 3 — interactive investigation query handlers."""
import numpy as np
import pytest
from mpd_overwatch.dashboard.investigation import (
    point_query, channel_query, interval_query,
)
from mpd_overwatch.knowledge.scanner import run_scan


class TestPointQuery:
    def test_returns_context_at_depth(self, assigned_db):
        ds = run_scan(assigned_db)
        depth_range = assigned_db.depth_range()
        mid = (depth_range[0] + depth_range[1]) / 2
        result = point_query(assigned_db, ds, depth=mid)
        assert result is not None
        assert "depth" in result
        assert "state" in result
        assert "channels" in result
        assert len(result["channels"]) > 0

    def test_out_of_range_depth(self, assigned_db):
        ds = run_scan(assigned_db)
        result = point_query(assigned_db, ds, depth=999999.0)
        assert result is not None

    def test_returns_health_status(self, assigned_db):
        ds = run_scan(assigned_db)
        depth_range = assigned_db.depth_range()
        mid = (depth_range[0] + depth_range[1]) / 2
        result = point_query(assigned_db, ds, depth=mid)
        # Channels should have health info if profiles exist
        for ch in result.get("channels", []):
            assert "value" in ch


class TestChannelQuery:
    def test_returns_full_dossier(self, assigned_db):
        ds = run_scan(assigned_db)
        result = channel_query(ds, canonical="hole_depth")
        assert result is not None
        assert "identity" in result
        assert "state_profiles" in result

    def test_unknown_channel(self, assigned_db):
        ds = run_scan(assigned_db)
        result = channel_query(ds, canonical="nonexistent_channel")
        assert result is None or result.get("found") is False


class TestIntervalQuery:
    def test_returns_interval_summary(self, assigned_db):
        ds = run_scan(assigned_db)
        depth_range = assigned_db.depth_range()
        mid = (depth_range[0] + depth_range[1]) / 2
        result = interval_query(
            assigned_db, ds,
            start_depth=mid - 500,
            end_depth=mid + 500,
        )
        assert result is not None
        assert "state_timeline" in result
        assert "channel_summaries" in result

    def test_narrow_interval(self, assigned_db):
        ds = run_scan(assigned_db)
        depth_range = assigned_db.depth_range()
        mid = (depth_range[0] + depth_range[1]) / 2
        result = interval_query(assigned_db, ds, start_depth=mid, end_depth=mid + 10)
        assert result is not None

    def test_no_crash_empty_interval(self, assigned_db):
        ds = run_scan(assigned_db)
        result = interval_query(assigned_db, ds, start_depth=0, end_depth=1)
        assert result is not None
