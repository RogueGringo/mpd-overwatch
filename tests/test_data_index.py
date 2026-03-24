"""Tests for central data index."""

import json
import pytest

from mpd_overwatch.data.data_index import DataIndex


class TestDataIndex:
    """Test central file indexing."""

    def test_init_creates_directory(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        assert (tmp_path / "data").is_dir()
        assert (tmp_path / "data" / "manifest.json").exists()

    def test_register_file(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "test.las"
        src.write_text("~VERSION\n VERS.  2.0\n~WELL\n WELL. TEST\n~CURVES\n~A\n")
        entry = idx.register(str(src), metadata={"well_name": "TEST"})
        assert entry["well_name"] == "TEST"
        assert entry["file_hash"] is not None

    def test_register_copies_file(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "test.las"
        src.write_text("~VERSION\n VERS.  2.0\n")
        entry = idx.register(str(src))
        stored = tmp_path / "data" / "files" / entry["stored_name"]
        assert stored.exists()

    def test_list_entries(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "a.las"
        src.write_text("~V\n")
        idx.register(str(src), metadata={"well_name": "A"})
        entries = idx.list_entries()
        assert len(entries) == 1
        assert entries[0]["well_name"] == "A"

    def test_lookup_by_hash(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "a.las"
        src.write_text("~V\n")
        entry = idx.register(str(src))
        found = idx.lookup(entry["file_hash"])
        assert found is not None
        assert found["file_hash"] == entry["file_hash"]

    def test_no_duplicate_registration(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "a.las"
        src.write_text("~V\nidentical content\n")
        idx.register(str(src))
        idx.register(str(src))
        assert len(idx.list_entries()) == 1

    def test_get_stored_path(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "a.las"
        src.write_text("~V\ncontent\n")
        entry = idx.register(str(src))
        stored_path = idx.get_stored_path(entry["file_hash"])
        assert stored_path is not None
        assert stored_path.exists()

    def test_persistence_across_instances(self, tmp_path):
        root = tmp_path / "data"
        idx1 = DataIndex(root=root)
        src = tmp_path / "a.las"
        src.write_text("~V\n")
        idx1.register(str(src), metadata={"well_name": "A"})
        idx2 = DataIndex(root=root)
        assert len(idx2.list_entries()) == 1
