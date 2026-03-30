"""Tests for stand detection from block_position data."""

from __future__ import annotations

import numpy as np
import pytest

from mpd_overwatch.knowledge.stand_detector import Stand, detect_stands, detect_stands_from_db
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


# ── Helpers ──────────────────────────────────────────────────────────


def _make_block_position(n_stands: int = 3, samples_per_stand: int = 100,
                         stand_stroke_ft: float = 90.0,
                         connection_samples: int = 30) -> np.ndarray:
    """Build a synthetic block_position trace with clear drilling cycles.

    Each stand: block goes DOWN by stand_stroke_ft over samples_per_stand,
    then UP by stand_stroke_ft over connection_samples (connection).
    """
    segments = []
    pos = 100.0  # starting block height

    for _ in range(n_stands):
        # Drilling down
        drill = np.linspace(pos, pos - stand_stroke_ft, samples_per_stand)
        segments.append(drill)
        pos -= stand_stroke_ft

        # Connection up (back to original height)
        conn = np.linspace(pos, pos + stand_stroke_ft, connection_samples)
        segments.append(conn)
        pos += stand_stroke_ft

    return np.concatenate(segments)


def _make_depth(block_pos: np.ndarray, start_depth: float = 5000.0) -> np.ndarray:
    """Build a monotonically increasing depth array.

    Depth increases proportionally to cumulative downward block movement.
    """
    n = len(block_pos)
    # Simple monotonic increase — each sample adds ~0.3 ft
    return np.linspace(start_depth, start_depth + n * 0.3, n)


def _make_channel_frame(wits_id: str, mnemonic: str, values: np.ndarray,
                        depth: np.ndarray = None, units: str = "ft") -> ChannelFrame:
    """Build a minimal ChannelFrame for testing."""
    n = len(values)
    if depth is None:
        depth = np.linspace(5000, 5000 + n * 0.3, n)
    return ChannelFrame(
        wits_id=wits_id,
        db_id=int(wits_id),
        mnemonic=mnemonic,
        description=mnemonic,
        units=units,
        source="WITS",
        bias=0.0,
        scale=1.0,
        depth_offset=0.0,
        log_by="time",
        value=values,
        depth=depth,
        time=np.arange(0, n, dtype="int64").astype("datetime64[s]"),
        hide=np.zeros(n, dtype=np.int8),
    )


# ── Tests ────────────────────────────────────────────────────────────


class TestDetectStandsBasic:
    """test_detect_stands_basic — synthetic block_position with 3 clear cycles."""

    def test_detects_three_stands(self):
        block_pos = _make_block_position(n_stands=3)
        depth = _make_depth(block_pos)
        stands = detect_stands(block_pos, depth)

        assert len(stands) == 3, f"Expected 3 stands, got {len(stands)}"

    def test_stand_numbers_sequential(self):
        block_pos = _make_block_position(n_stands=3)
        depth = _make_depth(block_pos)
        stands = detect_stands(block_pos, depth)

        for i, s in enumerate(stands):
            assert s.stand_number == i + 1

    def test_stands_have_positive_duration(self):
        block_pos = _make_block_position(n_stands=3)
        depth = _make_depth(block_pos)
        stands = detect_stands(block_pos, depth)

        for s in stands:
            assert s.duration_samples > 0
            assert s.index_end > s.index_start

    def test_stands_depth_increases(self):
        block_pos = _make_block_position(n_stands=3)
        depth = _make_depth(block_pos)
        stands = detect_stands(block_pos, depth)

        for s in stands:
            assert s.depth_end > s.depth_start, (
                f"Stand {s.stand_number}: depth should increase"
            )


class TestDetectStandsMinLength:
    """test_detect_stands_min_length — short cycles filtered out."""

    def test_short_cycles_filtered(self):
        """Stands with depth change < min_stand_length should be rejected."""
        # Create a mix of real stands and tiny oscillations
        block_pos = _make_block_position(n_stands=3, stand_stroke_ft=90.0)
        depth = _make_depth(block_pos)
        stands_normal = detect_stands(block_pos, depth, min_stand_length=20.0)

        # Now set a very high threshold — nothing should pass
        stands_strict = detect_stands(block_pos, depth, min_stand_length=9999.0)
        assert len(stands_strict) == 0

    def test_min_length_filters_noise(self):
        """Small oscillations (< 5 ft depth change) should not be detected."""
        # Create tiny oscillations — block moves only 2 ft per cycle
        block_pos = _make_block_position(n_stands=5, stand_stroke_ft=2.0,
                                         samples_per_stand=20,
                                         connection_samples=10)
        depth = _make_depth(block_pos)
        stands = detect_stands(block_pos, depth, min_stand_length=20.0)

        assert len(stands) == 0, "Tiny oscillations should be filtered out"


class TestDetectStandsEmpty:
    """test_detect_stands_empty — empty array returns empty list."""

    def test_empty_arrays(self):
        stands = detect_stands(np.array([]), np.array([]))
        assert stands == []

    def test_too_short_arrays(self):
        stands = detect_stands(np.array([1.0, 2.0]), np.array([100.0, 101.0]))
        assert stands == []


class TestDetectStandsFlat:
    """test_detect_stands_flat — constant block position yields no stands."""

    def test_constant_block_position(self):
        n = 500
        block_pos = np.full(n, 50.0)
        depth = np.linspace(5000, 8000, n)
        stands = detect_stands(block_pos, depth)

        assert len(stands) == 0, "Constant block position should yield no stands"

    def test_noisy_flat(self):
        """Small random noise around a constant should not produce stands."""
        rng = np.random.RandomState(42)
        n = 500
        block_pos = np.full(n, 50.0) + rng.randn(n) * 0.01
        depth = np.linspace(5000, 8000, n)
        stands = detect_stands(block_pos, depth)

        # Any detected "stands" from noise would be tiny and filtered out
        # by the min_stand_length default (20 ft depth change required)
        # But flat velocity means no sign crossings either
        assert len(stands) == 0


class TestDetectStandsFromDb:
    """test_detect_stands_from_db — WellDatabase with block_position channel."""

    def test_with_block_position_channel(self):
        """Database with block_position assignment should detect stands."""
        block_pos = _make_block_position(n_stands=3)
        depth = _make_depth(block_pos)

        # WITS 0109 = block_position in the vocabulary
        bp_cf = _make_channel_frame("0109", "BLKPOS", block_pos, depth=depth)
        # WITS 0108 = hole_depth
        hd_cf = _make_channel_frame("0108", "DEPTHOLE",
                                    depth, depth=depth, units="ft")

        db = WellDatabase(
            source_ip="test",
            dump_epoch=0,
            dump_timestamp="test",
            channels={"0109": bp_cf, "0108": hd_cf},
            assignments={"block_position": "0109", "hole_depth": "0108"},
        )

        stands = detect_stands_from_db(db)
        assert len(stands) == 3

    def test_without_block_position(self):
        """Database without block_position should return empty list."""
        n = 100
        depth = np.linspace(5000, 8000, n)
        hd_cf = _make_channel_frame("0108", "DEPTHOLE", depth, depth=depth)

        db = WellDatabase(
            source_ip="test",
            dump_epoch=0,
            dump_timestamp="test",
            channels={"0108": hd_cf},
            assignments={"hole_depth": "0108"},
        )

        stands = detect_stands_from_db(db)
        assert stands == []

    def test_empty_database(self):
        """Empty database should return empty list."""
        db = WellDatabase(
            source_ip="test",
            dump_epoch=0,
            dump_timestamp="test",
        )

        stands = detect_stands_from_db(db)
        assert stands == []

    def test_stand_fields_populated(self):
        """All Stand dataclass fields must be populated with sane values."""
        block_pos = _make_block_position(n_stands=2)
        depth = _make_depth(block_pos)

        bp_cf = _make_channel_frame("0109", "BLKPOS", block_pos, depth=depth)
        hd_cf = _make_channel_frame("0108", "DEPTHOLE",
                                    depth, depth=depth, units="ft")

        db = WellDatabase(
            source_ip="test",
            dump_epoch=0,
            dump_timestamp="test",
            channels={"0109": bp_cf, "0108": hd_cf},
            assignments={"block_position": "0109", "hole_depth": "0108"},
        )

        stands = detect_stands_from_db(db)
        assert len(stands) > 0

        for s in stands:
            assert isinstance(s.stand_number, int)
            assert s.stand_number > 0
            assert isinstance(s.depth_start, float)
            assert isinstance(s.depth_end, float)
            assert isinstance(s.block_start, float)
            assert isinstance(s.block_end, float)
            assert isinstance(s.index_start, int)
            assert isinstance(s.index_end, int)
            assert isinstance(s.duration_samples, int)
            assert s.duration_samples > 0
