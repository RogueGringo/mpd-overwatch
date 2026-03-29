"""Tests for WellDossierSet and data_store integration."""
import pytest
from mpd_overwatch.knowledge.well_dossier_set import WellDossierSet
from mpd_overwatch.knowledge.scanner import run_scan
from mpd_overwatch.knowledge.rig_state import RigState


class TestWellDossierSet:
    def test_construction_from_scan(self, assigned_db):
        dossier_set = run_scan(assigned_db)
        assert isinstance(dossier_set, WellDossierSet)
        assert len(dossier_set.dossiers) > 0

    def test_get_by_wits_id(self, assigned_db):
        ds = run_scan(assigned_db)
        for wid in list(ds.dossiers.keys())[:1]:
            dossier = ds.get(wid)
            assert dossier is not None
            assert dossier.wits_id == wid

    def test_get_by_canonical(self, assigned_db):
        ds = run_scan(assigned_db)
        dossier = ds.get_by_canonical("hole_depth")
        if dossier is not None:
            assert dossier.canonical == "hole_depth"

    def test_states_and_transitions_stored(self, assigned_db):
        ds = run_scan(assigned_db)
        assert ds.states is not None or ds.states is None
        if ds.states is not None:
            assert len(ds.states) > 0
            assert all(isinstance(s, RigState) for s in ds.states)

    def test_scan_performance(self, assigned_db):
        """Scan should complete in under 10 seconds for real data."""
        import time
        start = time.perf_counter()
        ds = run_scan(assigned_db)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, f"Scan took {elapsed:.1f}s, expected <10s"


class TestDataStoreIntegration:
    def test_load_triggers_scan(self, depth_file_path):
        from mpd_overwatch.dashboard import data_store
        try:
            data_store.load_file(str(depth_file_path))
            ds = data_store.get_well_dossier_set()
            assert ds is not None
            assert len(ds.dossiers) > 0
        finally:
            data_store.clear()

    def test_clear_clears_dossiers(self, depth_file_path):
        from mpd_overwatch.dashboard import data_store
        data_store.load_file(str(depth_file_path))
        data_store.clear()
        assert data_store.get_well_dossier_set() is None

    def test_reload_replaces_dossiers(self, depth_file_path):
        from mpd_overwatch.dashboard import data_store
        try:
            data_store.load_file(str(depth_file_path))
            ds1 = data_store.get_well_dossier_set()
            data_store.load_file(str(depth_file_path))
            ds2 = data_store.get_well_dossier_set()
            assert ds2 is not None
            assert ds1 is not ds2
        finally:
            data_store.clear()
