"""Tests for rig state machine — bimodal detection, block motion, state classification."""

from __future__ import annotations

import numpy as np
import pytest


# ── RigState enum ──────────────────────────────────────────────────

class TestRigStateEnum:
    def test_has_ten_states(self):
        from mpd_overwatch.knowledge.rig_state import RigState
        assert len(RigState) == 10

    def test_expected_members(self):
        from mpd_overwatch.knowledge.rig_state import RigState
        expected = {
            "DRILLING", "SLIDING", "CONNECTION", "CIRCULATING",
            "TRIPPING", "STATIC", "REAMING", "BACKREAMING_DOWN",
            "WASHING", "UNKNOWN",
        }
        actual = {m.name for m in RigState}
        assert actual == expected


# ── StateTransition dataclass ──────────────────────────────────────

class TestStateTransition:
    def test_construction(self):
        from mpd_overwatch.knowledge.rig_state import RigState, StateTransition
        t = StateTransition(
            from_state=RigState.DRILLING,
            to_state=RigState.CONNECTION,
            index=1500,
            depth=10250.0,
            time=3600.0,
        )
        assert t.from_state == RigState.DRILLING
        assert t.to_state == RigState.CONNECTION
        assert t.index == 1500
        assert t.depth == 10250.0
        assert t.time == 3600.0


# ── Bimodal threshold detection ───────────────────────────────────

class TestBimodalThreshold:
    def test_clear_bimodal_finds_valley(self):
        """Two well-separated clusters → threshold between them."""
        from mpd_overwatch.knowledge.rig_state import find_bimodal_threshold
        rng = np.random.RandomState(42)
        low = rng.normal(50, 5, 500)
        high = rng.normal(500, 20, 500)
        data = np.concatenate([low, high])
        threshold = find_bimodal_threshold(data)
        # Threshold should fall between the two cluster means
        assert 80 < threshold < 400

    def test_unimodal_falls_back_to_median(self):
        """Single-mode data → fallback to median."""
        from mpd_overwatch.knowledge.rig_state import find_bimodal_threshold
        data = np.random.RandomState(42).normal(100, 5, 1000)
        threshold = find_bimodal_threshold(data)
        # Should be close to median (~100)
        assert 85 < threshold < 115

    def test_all_zeros_returns_zero(self):
        from mpd_overwatch.knowledge.rig_state import find_bimodal_threshold
        data = np.zeros(100)
        assert find_bimodal_threshold(data) == 0.0

    def test_empty_returns_zero(self):
        from mpd_overwatch.knowledge.rig_state import find_bimodal_threshold
        data = np.array([])
        assert find_bimodal_threshold(data) == 0.0


# ── Block motion classification ───────────────────────────────────

class TestBlockMotion:
    def test_positive_derivative_is_up(self):
        from mpd_overwatch.knowledge.rig_state import classify_block_motion
        # Steadily increasing position = block going UP
        block = np.linspace(0, 100, 200)
        motion = classify_block_motion(block)
        # Most samples should be UP (allowing first sample edge case)
        up_count = np.sum(motion == "UP")
        assert up_count > len(motion) * 0.8

    def test_negative_derivative_is_down(self):
        from mpd_overwatch.knowledge.rig_state import classify_block_motion
        # Steadily decreasing position = block going DOWN
        block = np.linspace(100, 0, 200)
        motion = classify_block_motion(block)
        down_count = np.sum(motion == "DOWN")
        assert down_count > len(motion) * 0.8

    def test_flat_is_static(self):
        from mpd_overwatch.knowledge.rig_state import classify_block_motion
        block = np.full(200, 50.0)
        motion = classify_block_motion(block)
        static_count = np.sum(motion == "STATIC")
        assert static_count == len(motion)


# ── State detection: core scenarios ───────────────────────────────

class TestDetectStates:
    def _make_drilling_data(self, n=200):
        """Pumps ON, rotation ON, block going DOWN."""
        return {
            "flow_in": np.full(n, 800.0),
            "rpm": np.full(n, 120.0),
            "block_position": np.linspace(100, 0, n),
        }

    def _make_static_data(self, n=200):
        """Pumps OFF, rotation OFF, block STATIC."""
        return {
            "flow_in": np.full(n, 0.0),
            "rpm": np.full(n, 0.0),
            "block_position": np.full(n, 50.0),
        }

    def test_drilling_state(self):
        """Pumps + rotation + block down → DRILLING."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_states
        d = self._make_drilling_data()
        states = detect_states(d["flow_in"], d["rpm"], d["block_position"])
        # Majority should be DRILLING
        drilling_frac = np.sum(states == RigState.DRILLING) / len(states)
        assert drilling_frac > 0.7

    def test_static_state(self):
        """All off/static → STATIC."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_states
        d = self._make_static_data()
        states = detect_states(d["flow_in"], d["rpm"], d["block_position"])
        static_frac = np.sum(states == RigState.STATIC) / len(states)
        assert static_frac > 0.7

    def test_connection_up_down_reversal(self):
        """TRIPPING with UP→DOWN reversal → reclassified as CONNECTION."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_states
        n = 300
        flow_in = np.zeros(n)
        rpm = np.zeros(n)
        # block goes UP then DOWN (pipe out then pipe back in = connection)
        block = np.concatenate([
            np.linspace(50, 90, 100),     # UP
            np.full(100, 90),              # brief STATIC at top
            np.linspace(90, 50, 100),      # DOWN
        ])
        states = detect_states(flow_in, rpm, block, min_state_samples=10)
        conn_count = np.sum(states == RigState.CONNECTION)
        assert conn_count > 0, "Should detect CONNECTION from UP→DOWN reversal"

    def test_sliding_with_wob(self):
        """Pumps ON, no rotation, block down, WOB present → SLIDING."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_states
        # Mix of high and near-zero WOB so bimodal threshold can separate them
        n = 200
        flow_in = np.full(n, 800.0)
        rpm = np.zeros(n)
        block = np.linspace(100, 0, n)
        # First half: high WOB (should stay SLIDING)
        # Second half: near-zero WOB (would become WASHING)
        wob = np.concatenate([np.full(100, 25.0), np.full(100, 0.5)])
        states = detect_states(flow_in, rpm, block, min_state_samples=10, wob=wob)
        # First half should be mostly SLIDING
        sliding_first_half = np.sum(states[:100] == RigState.SLIDING)
        assert sliding_first_half > 50

    def test_washing_near_zero_wob(self):
        """Pumps ON, no rotation, block down, near-zero WOB → WASHING."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_states
        # Mix of high and near-zero WOB so bimodal threshold can separate them
        n = 200
        flow_in = np.full(n, 800.0)
        rpm = np.zeros(n)
        block = np.linspace(100, 0, n)
        # First half: high WOB, second half: near-zero WOB
        wob = np.concatenate([np.full(100, 25.0), np.full(100, 0.5)])
        states = detect_states(flow_in, rpm, block, min_state_samples=10, wob=wob)
        # Second half (near-zero WOB) should be mostly WASHING
        washing_second_half = np.sum(states[100:] == RigState.WASHING)
        assert washing_second_half > 50

    def test_missing_channels_unknown(self):
        """All channels None → UNKNOWN."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_states
        states = detect_states(None, None, None)
        assert len(states) == 0 or all(s == RigState.UNKNOWN for s in states)


# ── Fallback channels ─────────────────────────────────────────────

class TestFallbackChannels:
    def test_spp_fallback_for_flow_in(self):
        """When flow_in is None, SPP substitutes for pump detection."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_states
        n = 200
        rpm = np.full(n, 120.0)
        block = np.linspace(100, 0, n)
        spp = np.full(n, 3000.0)  # high SPP → pumps ON
        states = detect_states(None, rpm, block, min_state_samples=10, spp=spp)
        # With pumps ON + rotation + block down → should get DRILLING
        drilling_frac = np.sum(states == RigState.DRILLING) / len(states)
        assert drilling_frac > 0.5


# ── Hysteresis ─────────────────────────────────────────────────────

class TestHysteresis:
    def test_single_sample_spike_does_not_flip(self):
        """A single-sample anomaly shouldn't cause a state change."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_states
        n = 200
        flow_in = np.full(n, 800.0)
        rpm = np.full(n, 120.0)
        block = np.linspace(100, 0, n)
        # Inject single-sample zero in flow_in mid-sequence
        flow_in[100] = 0.0
        states = detect_states(flow_in, rpm, block, min_state_samples=30)
        # Should remain DRILLING throughout (hysteresis prevents flip)
        drilling_frac = np.sum(states == RigState.DRILLING) / len(states)
        assert drilling_frac > 0.9


# ── Real data integration ─────────────────────────────────────────

class TestRealData:
    @pytest.mark.skipif(
        not pytest.importorskip("mpd_overwatch.data.sql_parser", reason="parser needed"),
        reason="sql_parser not available",
    )
    def test_detects_multiple_states(self, assigned_db):
        """Real data must contain at least 3 distinct rig states."""
        from mpd_overwatch.knowledge.rig_state import detect_states, RigState

        db = assigned_db
        # Try to get channels via assignments
        flow_in = None
        rpm = None
        block_pos = None
        wob = None
        spp = None
        torque = None

        for canonical, wits_id in db.assignments.items():
            cn = canonical.lower()
            if wits_id not in db.channels:
                continue
            cf = db.channels[wits_id]
            if "flow" in cn and "in" in cn:
                flow_in = cf.calibrated_value
            elif cn in ("rpm", "rotary_rpm"):
                rpm = cf.calibrated_value
            elif "block" in cn and "pos" in cn:
                block_pos = cf.calibrated_value
            elif cn in ("wob", "weight_on_bit"):
                wob = cf.calibrated_value
            elif cn in ("spp", "standpipe_pressure"):
                spp = cf.calibrated_value
            elif cn in ("torque", "surface_torque"):
                torque = cf.calibrated_value

        states = detect_states(
            flow_in, rpm, block_pos,
            min_state_samples=10,
            wob=wob, spp=spp, torque=torque,
        )
        unique_states = set(states)
        unique_states.discard(RigState.UNKNOWN)
        assert len(unique_states) >= 3, (
            f"Expected >= 3 distinct states, got {unique_states}"
        )


# ── Transition detection ──────────────────────────────────────────

class TestTransitions:
    def test_finds_boundaries(self):
        """State changes produce transitions at the right indices."""
        from mpd_overwatch.knowledge.rig_state import (
            RigState, StateTransition, detect_transitions,
        )
        # Manually construct a state sequence with known boundaries
        states = np.array(
            [RigState.DRILLING] * 50
            + [RigState.STATIC] * 50
            + [RigState.CIRCULATING] * 50,
        )
        transitions = detect_transitions(states)
        assert len(transitions) == 2
        assert transitions[0].from_state == RigState.DRILLING
        assert transitions[0].to_state == RigState.STATIC
        assert transitions[0].index == 50
        assert transitions[1].from_state == RigState.STATIC
        assert transitions[1].to_state == RigState.CIRCULATING
        assert transitions[1].index == 100

    def test_no_transitions_in_uniform(self):
        """Uniform state sequence → no transitions."""
        from mpd_overwatch.knowledge.rig_state import RigState, detect_transitions
        states = np.array([RigState.DRILLING] * 100)
        transitions = detect_transitions(states)
        assert len(transitions) == 0


# ── Package exports ────────────────────────────────────────────────

class TestRigStateExports:
    def test_importable_from_knowledge(self):
        from mpd_overwatch.knowledge.rig_state import (
            RigState,
            StateTransition,
            find_bimodal_threshold,
            classify_block_motion,
            detect_states,
            detect_transitions,
        )
        assert RigState is not None
        assert StateTransition is not None
        assert callable(find_bimodal_threshold)
        assert callable(classify_block_motion)
        assert callable(detect_states)
        assert callable(detect_transitions)
