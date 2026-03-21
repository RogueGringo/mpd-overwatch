import os
import tempfile
import pytest
from mpd_overwatch.computation_log import ComputationLog, get_log, init_log
from mpd_overwatch.core.engineering_result import (
    EngineeringResult, EngineeringInput, Method, Provenance,
)


def test_log_creates_file(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    assert os.path.exists(log.filepath)
    assert log.filepath.endswith(".log")


def test_log_filename_format(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    basename = os.path.basename(log.filepath)
    assert basename.startswith("mpd_overwatch_")
    assert basename.endswith(".log")


def test_session_writes_category(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.session("Test session message")
    with open(log.filepath) as f:
        content = f.read()
    assert "[SESSION]" in content
    assert "Test session message" in content


def test_file_category(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.file("Opened test.las")
    with open(log.filepath) as f:
        content = f.read()
    assert "[FILE]" in content


def test_result_logs_engineering_result(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    er = EngineeringResult(
        label="ECD", value=13.35, unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method("Bourgoyne Eq 4.72", "Applied Drilling Eng", "MW + AFP/(0.052*TVD)"),
        inputs=[
            EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED),
            EngineeringInput("AFP", 847, "psi", Provenance.MODELED, source="Fanning"),
            EngineeringInput("TVD", 10500, "ft", Provenance.SURVEY),
        ],
    )
    log.result(er)
    with open(log.filepath) as f:
        content = f.read()
    assert "ECD" in content
    assert "13.35" in content
    assert "MW = 11.8 ppg [MEASURED]" in content
    assert "AFP = 847" in content
    assert "Bourgoyne" in content


def test_topology_category(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.topology("Eigenvalues: l1=0.031, l2=0.289")
    with open(log.filepath) as f:
        content = f.read()
    assert "[TOPOLOGY]" in content


def test_warning_and_error(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.warning("Out of range input")
    log.error("Computation failed")
    with open(log.filepath) as f:
        content = f.read()
    assert "[WARNING]" in content
    assert "[ERROR]" in content


def test_singleton_init_and_get(tmp_path):
    init_log(log_dir=str(tmp_path))
    log = get_log()
    assert log is not None
    log.session("singleton test")
    with open(log.filepath) as f:
        content = f.read()
    assert "singleton test" in content


def test_log_entry_has_timestamp(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.session("timestamp check")
    with open(log.filepath) as f:
        line = f.readlines()[-1]
    # Format: [YYYY-MM-DD HH:MM:SS.mmm]
    assert line.startswith("[20")
    assert "]" in line
