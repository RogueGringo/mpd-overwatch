"""End-to-end integration test for the pipeline command.

Uses a real SQL EDR dump file from DATA_TYPES_for_System_Use_EXAMPLES.
Skips if example data directory is not present.
"""

from pathlib import Path

import pytest

# Resolve relative to the project root (one level above tests/)
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "DATA_TYPES_for_System_Use_EXAMPLES"


def _find_small_sql():
    """Find the smallest depth SQL file in the examples directory."""
    if not EXAMPLES_DIR.exists():
        return None
    sql_files = [
        f for f in EXAMPLES_DIR.rglob("*.sql")
        if "_timedata_" not in f.name
    ]
    if not sql_files:
        return None
    return min(sql_files, key=lambda p: p.stat().st_size)


SMALL_SQL = _find_small_sql()


@pytest.mark.skipif(SMALL_SQL is None, reason="No example SQL files found")
class TestPipelineE2E:
    """End-to-end pipeline test with real data."""

    def test_pipeline_runs_successfully(self, tmp_path):
        """Full pipeline on a real SQL EDR dump should complete without error."""
        from mpd_overwatch.cli import main

        result = main([
            "pipeline", str(SMALL_SQL),
            "--output-dir", str(tmp_path),
            "--no-plots",  # Don't require kaleido for CI
        ])
        assert result == 0
