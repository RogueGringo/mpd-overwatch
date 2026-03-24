"""End-to-end integration test for the pipeline command.

Uses a real LAS file from DATA_TYPES_for_System_Use_EXAMPLES.
Skips if example data directory is not present.
"""

from pathlib import Path

import pytest

# Resolve relative to the project root (one level above tests/)
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "DATA_TYPES_for_System_Use_EXAMPLES"


def _find_small_las():
    """Find the smallest LAS file in the examples directory."""
    if not EXAMPLES_DIR.exists():
        return None
    las_files = list(EXAMPLES_DIR.rglob("*.las")) + list(EXAMPLES_DIR.rglob("*.LAS"))
    if not las_files:
        return None
    return min(las_files, key=lambda p: p.stat().st_size)


SMALL_LAS = _find_small_las()


@pytest.mark.skipif(SMALL_LAS is None, reason="No example LAS files found")
class TestPipelineE2E:
    """End-to-end pipeline test with real data."""

    def test_pipeline_produces_mow(self, tmp_path):
        """Full pipeline on a real LAS file should produce a .mow archive."""
        from mpd_overwatch.cli import main

        result = main([
            "pipeline", str(SMALL_LAS),
            "--output-dir", str(tmp_path),
            "--no-llm",    # Don't require LM Studio for CI
            "--no-plots",  # Don't require kaleido for CI
        ])
        assert result == 0

        mow_files = list(tmp_path.glob("*.mow"))
        assert len(mow_files) >= 1
