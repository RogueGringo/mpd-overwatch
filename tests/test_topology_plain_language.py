import pytest


def test_topology_uses_plain_language_names():
    """Topology page must use operational names, not technical."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.topology")
    with open(source.origin) as f:
        content = f.read()
    assert "Channel Agreement" in content
    assert "Agreement Strength" in content


def test_atft_uses_plain_language_names():
    """ATFT page must use operational names."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.atft_analysis")
    with open(source.origin) as f:
        content = f.read()
    assert "Routing Confidence" in content
    assert "demo_generator" not in content
