"""Tests for analysis layer format (.mow)."""

import json
import time
import zipfile
import numpy as np
import pytest

from mpd_overwatch.data.analysis_layers import AnalysisLayer, AnalysisChain


class TestAnalysisLayer:
    """Test individual layer creation."""

    def test_create_layer(self):
        layer = AnalysisLayer(
            layer_id="001_ingest",
            layer_type="ingest",
            inputs={"filepath": "/path/to/well.las"},
            outputs={"channels": 12, "rows": 6736},
            context={"operator": "Chevron", "well": "REV GF"},
            value_term="Raw Data Captured",
            value_description="12 channels ingested from LAS file",
        )
        assert layer.layer_id == "001_ingest"
        assert layer.duration_ms is None  # Not yet timed

    def test_layer_to_dict(self):
        layer = AnalysisLayer(
            layer_id="002_map",
            layer_type="channel_mapping",
            inputs={"channels": ["SPP", "APRS"]},
            outputs={"mapped": {"SPP": "spp", "APRS": "apwd"}},
        )
        d = layer.to_dict()
        assert d["layer_id"] == "002_map"
        assert isinstance(d["created_at"], str)

    def test_layer_from_dict(self):
        d = {
            "layer_id": "003",
            "layer_type": "pointcloud",
            "created_at": "2026-03-24T10:00:00",
            "duration_ms": 150,
            "depends_on": ["002"],
            "inputs": {},
            "outputs": {"n_points": 80000},
            "context": {},
            "value_term": "test",
            "value_description": "test desc",
        }
        layer = AnalysisLayer.from_dict(d)
        assert layer.layer_id == "003"
        assert layer.duration_ms == 150


class TestAnalysisChain:
    """Test chain assembly and .mow save/load."""

    def _make_chain(self):
        chain = AnalysisChain(well_name="TEST WELL")
        chain.add_layer(AnalysisLayer(
            layer_id="001_ingest",
            layer_type="ingest",
            inputs={"file": "test.las"},
            outputs={"channels": 5},
            value_term="Data Ingested",
        ))
        chain.add_layer(AnalysisLayer(
            layer_id="002_map",
            layer_type="channel_mapping",
            depends_on=["001_ingest"],
            inputs={"channels": 5},
            outputs={"mapped": 4},
            value_term="Channels Mapped",
        ))
        return chain

    def test_add_layers(self):
        chain = self._make_chain()
        assert len(chain.layers) == 2

    def test_save_mow(self, tmp_path):
        chain = self._make_chain()
        mow_path = tmp_path / "test.mow"
        chain.save(mow_path)
        assert mow_path.exists()
        # .mow is a zip file
        assert zipfile.is_zipfile(str(mow_path))

    def test_mow_contains_manifest(self, tmp_path):
        chain = self._make_chain()
        mow_path = tmp_path / "test.mow"
        chain.save(mow_path)
        with zipfile.ZipFile(str(mow_path), "r") as zf:
            assert "manifest.json" in zf.namelist()

    def test_mow_contains_layer_meta(self, tmp_path):
        chain = self._make_chain()
        mow_path = tmp_path / "test.mow"
        chain.save(mow_path)
        with zipfile.ZipFile(str(mow_path), "r") as zf:
            names = zf.namelist()
            assert "layers/001_ingest/meta.json" in names
            assert "layers/002_map/meta.json" in names

    def test_roundtrip(self, tmp_path):
        chain = self._make_chain()
        mow_path = tmp_path / "test.mow"
        chain.save(mow_path)
        loaded = AnalysisChain.load(mow_path)
        assert loaded.well_name == "TEST WELL"
        assert len(loaded.layers) == 2
        assert loaded.layers[0].layer_id == "001_ingest"
        assert loaded.layers[1].depends_on == ["001_ingest"]

    def test_add_array_data(self, tmp_path):
        chain = AnalysisChain(well_name="ARRAY TEST")
        chain.add_layer(AnalysisLayer(
            layer_id="001",
            layer_type="test",
            inputs={},
            outputs={"shape": [100, 4]},
        ))
        chain.add_array("001", "points", np.random.rand(100, 4))
        mow_path = tmp_path / "array_test.mow"
        chain.save(mow_path)
        loaded = AnalysisChain.load(mow_path)
        arr = loaded.get_array("001", "points")
        assert arr is not None
        assert arr.shape == (100, 4)
