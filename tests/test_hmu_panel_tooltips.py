import pytest


def test_hmu_no_demo_generator_import():
    """HMU panel must not import demo_generator."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.hmu_panel")
    with open(source.origin) as f:
        content = f.read()
    assert "demo_generator" not in content


def test_hmu_uses_engine_wrapper_for_ecd():
    """HMU panel must not compute ECD inline — must call engine_wrappers."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.hmu_panel")
    with open(source.origin) as f:
        content = f.read()
    assert "compute_ecd" in content
    # No inline ECD formula
    assert "current_bhp_psi / (0.052" not in content
