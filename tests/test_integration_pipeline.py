# tests/test_integration_pipeline.py
import os
import pytest

LAS_FILE = "OILFIELD_DRILLING_DATA_EXAMPLE_FILES/EDR_DATA/LAS_Depth/CLIENT3_Start_2025_Jul_17 10-21_End_2025_Jul_17 19-21_1760143723100.las"


@pytest.mark.skipif(not os.path.exists(LAS_FILE), reason="Test LAS file not available")
class TestFullPipeline:

    def test_las_to_channel_map(self):
        """Open LAS -> parse header -> classify channels -> produce ChannelMap."""
        from mpd_overwatch.dashboard.file_manager import parse_las_header
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry, classify_channels

        info = parse_las_header(LAS_FILE)
        assert info["curve_count"] > 100

        registry = ChannelRegistry()
        tiers = classify_channels(info["curve_names"], registry)
        assert len(tiers) == info["curve_count"]
        core_count = sum(1 for t in tiers.values() if t.value == "core")
        assert core_count >= 1

    def test_engine_wrapper_produces_result(self):
        """Engine wrapper returns EngineeringResult with complete metadata."""
        from mpd_overwatch.core.engine_wrappers import compute_ecd
        from mpd_overwatch.core.engineering_result import EngineeringResult

        result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
        assert isinstance(result, EngineeringResult)
        assert result.value > 0
        assert len(result.inputs) == 3
        assert result.method.equation != ""
        assert result.validity != ""

    def test_tooltip_renders_from_result(self):
        """EngineeringResult renders as a Dash component."""
        from dash import html
        from mpd_overwatch.core.engine_wrappers import compute_ecd
        from mpd_overwatch.components.tooltip import render_engineering_value

        result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
        component = render_engineering_value(result)
        assert isinstance(component, html.Div)

    def test_computation_log_traces_result(self, tmp_path):
        """ComputationLog serializes EngineeringResult."""
        from mpd_overwatch.computation_log import ComputationLog
        from mpd_overwatch.core.engine_wrappers import compute_ecd

        log = ComputationLog(log_dir=str(tmp_path))
        result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
        log.result(result)

        with open(log.filepath) as f:
            content = f.read()
        assert "ECD" in content
        assert "HYDRAULICS" in content
        assert "Bourgoyne" in content

    def test_existing_tests_still_pass(self):
        """Verify core engine tests are unaffected."""
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-k", "hydraulics or geomechanics or pore_pressure or formation_damage", "-q"],
            capture_output=True, text=True, cwd="C:/JTOD1/mpd-overwatch"
        )
        assert result.returncode == 0
