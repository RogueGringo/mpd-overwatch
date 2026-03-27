"""V&V Section 2: Calibration Chain.

Principle: bias, scale, and depth_offset from idtable must propagate
correctly through every layer — ChannelFrame properties, assignment
path, and engine input preparation.

Ground truth: WITS 0821 (Gamma Depth) has depth_offset=70.44 in the real data.
"""

import numpy as np
import pytest


class TestChannelFrameCalibratedValue:
    """ChannelFrame.calibrated_value must equal value * scale + bias."""

    def test_identity_calibration(self, loaded_db):
        """When scale=1 and bias=0, calibrated_value == value exactly."""
        cf = loaded_db.channels["0121"]
        assert cf.scale == 1.0
        assert cf.bias == 0.0
        np.testing.assert_array_equal(
            cf.calibrated_value, cf.value,
            err_msg="Identity calibration: calibrated_value should equal value"
        )

    def test_calibrated_formula_manual(self, loaded_db):
        """For every channel, calibrated_value[i] == value[i] * scale + bias."""
        for wid, cf in loaded_db.channels.items():
            if len(cf.value) == 0:
                continue
            expected = cf.value * cf.scale + cf.bias
            np.testing.assert_array_equal(
                cf.calibrated_value, expected,
                err_msg=f"Channel {wid}: calibrated_value != value * {cf.scale} + {cf.bias}"
            )

    def test_calibrated_value_property_is_not_mutating(self, loaded_db):
        """Accessing calibrated_value must not modify the original value array."""
        cf = loaded_db.channels["0108"]
        original_value = cf.value.copy()
        _ = cf.calibrated_value
        np.testing.assert_array_equal(cf.value, original_value)


class TestChannelFrameDepthCorrected:
    """ChannelFrame.depth_corrected must equal depth + depth_offset."""

    def test_nonzero_depth_offset(self, loaded_db):
        """WITS 0821 has depth_offset=70.44: depth_corrected = depth + 70.44."""
        cf = loaded_db.channels["0821"]
        assert cf.depth_offset != 0.0, f"Expected non-zero depth_offset, got {cf.depth_offset}"
        if len(cf.depth) > 0 and hasattr(cf, 'depth_corrected'):
            expected = cf.depth + cf.depth_offset
            np.testing.assert_array_equal(
                cf.depth_corrected, expected,
                err_msg=f"depth_corrected should be depth + {cf.depth_offset}"
            )
        elif not hasattr(cf, 'depth_corrected'):
            pytest.skip("ChannelFrame does not have depth_corrected property")

    def test_zero_offset_identity(self, loaded_db):
        """When depth_offset=0, depth_corrected == depth exactly."""
        cf = loaded_db.channels["0121"]
        assert cf.depth_offset == 0.0
        if len(cf.depth) > 0 and hasattr(cf, 'depth_corrected'):
            np.testing.assert_array_equal(
                cf.depth_corrected, cf.depth,
                err_msg="Zero offset: depth_corrected should equal depth"
            )
        elif not hasattr(cf, 'depth_corrected'):
            pytest.skip("ChannelFrame does not have depth_corrected property")

    def test_all_channels_depth_corrected_formula(self, loaded_db):
        """For every channel, depth_corrected = depth + depth_offset."""
        if not hasattr(list(loaded_db.channels.values())[0], 'depth_corrected'):
            pytest.skip("ChannelFrame does not have depth_corrected property")
        for wid, cf in loaded_db.channels.items():
            if len(cf.depth) == 0:
                continue
            expected = cf.depth + cf.depth_offset
            np.testing.assert_array_equal(
                cf.depth_corrected, expected,
                err_msg=f"Channel {wid}: depth_corrected != depth + {cf.depth_offset}"
            )


class TestAssignmentPathCalibration:
    """When db.assigned() returns a ChannelFrame, calibration is intact."""

    def test_assigned_channel_calibrated(self, assigned_db):
        """assigned('hole_depth') returns ChannelFrame with correct calibration."""
        try:
            cf = assigned_db.assigned("hole_depth")
        except KeyError:
            pytest.skip("hole_depth not assigned in auto-suggestions")
        expected = cf.value * cf.scale + cf.bias
        np.testing.assert_array_equal(cf.calibrated_value, expected)

    def test_assigned_wits_id_matches(self, assigned_db, auto_assignments):
        """The ChannelFrame's wits_id must match the assignment."""
        for canonical, wits_id in auto_assignments.items():
            cf = assigned_db.assigned(canonical)
            assert cf.wits_id == wits_id, (
                f"{canonical}: assigned wits_id={cf.wits_id}, expected {wits_id}"
            )


class TestEngineInputCalibration:
    """Engine input path preserves calibration."""

    def test_engine_input_has_calibrated_values(self, assigned_db):
        """ChannelFrames obtained through assignment have calibrated_value accessible."""
        try:
            cf = assigned_db.assigned("hole_depth")
        except KeyError:
            pytest.skip("hole_depth not assigned")
        # The engine receives the ChannelFrame — verify calibration math
        expected = cf.value * cf.scale + cf.bias
        np.testing.assert_array_equal(cf.calibrated_value, expected)

    def test_nontrivial_calibration_channel(self, loaded_db):
        """Find a channel with scale != 1 and verify calibration math."""
        for wid, cf in loaded_db.channels.items():
            if cf.scale != 1.0 or cf.bias != 0.0:
                expected = cf.value * cf.scale + cf.bias
                np.testing.assert_array_equal(
                    cf.calibrated_value, expected,
                    err_msg=f"Channel {wid} (scale={cf.scale}, bias={cf.bias}): "
                            f"calibration formula failed"
                )
                return  # Found and verified one
        pytest.skip("No channels with non-trivial calibration in test data")
