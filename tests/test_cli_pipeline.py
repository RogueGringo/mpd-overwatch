"""Tests for the pipeline CLI command."""

import pytest

from mpd_overwatch.cli import main


class TestPipelineCLI:
    """Test pipeline subcommand argument parsing."""

    def test_pipeline_no_args_prints_help(self, capsys):
        """Pipeline without las_file should show error."""
        with pytest.raises(SystemExit) as exc:
            main(["pipeline"])
        assert exc.value.code == 2  # argparse error

    def test_pipeline_help(self, capsys):
        """Pipeline --help should succeed."""
        with pytest.raises(SystemExit) as exc:
            main(["pipeline", "--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "pipeline" in captured.out.lower() or "Pipeline" in captured.out

    def test_pipeline_nonexistent_file(self, tmp_path):
        """Pipeline with nonexistent file should return error code."""
        result = main(["pipeline", str(tmp_path / "nope.las")])
        assert result != 0
