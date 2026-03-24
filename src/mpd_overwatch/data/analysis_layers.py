"""Analysis Layer Format (.mow) -- layered computation provenance.

Every computation step becomes an AnalysisLayer with timing, provenance,
context, and dimensionalized value.  An AnalysisChain bundles layers into
a zip-based ``.mow`` (MPD Overwatch) archive.

Archive structure::

    manifest.json
    layers/
        001_ingest/
            meta.json
        002_map/
            meta.json
        003_pointcloud/
            meta.json
            points.npy
        ...
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class AnalysisLayer:
    """A single computation step with full provenance.

    Parameters
    ----------
    layer_id : str
        Unique identifier (e.g. "001_ingest").
    layer_type : str
        Category (e.g. "ingest", "channel_mapping", "pointcloud",
        "topology", "coherence", "anomalies", "zones", "routing").
    depends_on : list of str
        Layer IDs this layer depends on.
    inputs : dict
        What data/parameters fed into this computation.
    outputs : dict
        What this computation produced.
    context : dict
        Human-machine-data context (operator, well, intent).
    value_term : str
        Non-mathematical platformable term for what this layer means.
    value_description : str
        Expanded description of the dimensionalized value.
    created_at : str
        ISO timestamp of when this layer was computed.
    duration_ms : int or None
        Computation time in milliseconds.
    """

    layer_id: str
    layer_type: str
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    value_term: str = ""
    value_description: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "layer_type": self.layer_type,
            "created_at": self.created_at,
            "duration_ms": self.duration_ms,
            "depends_on": self.depends_on,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "context": self.context,
            "value_term": self.value_term,
            "value_description": self.value_description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AnalysisLayer:
        return cls(
            layer_id=d["layer_id"],
            layer_type=d["layer_type"],
            depends_on=d.get("depends_on", []),
            inputs=d.get("inputs", {}),
            outputs=d.get("outputs", {}),
            context=d.get("context", {}),
            value_term=d.get("value_term", ""),
            value_description=d.get("value_description", ""),
            created_at=d.get("created_at", ""),
            duration_ms=d.get("duration_ms"),
        )


class AnalysisChain:
    """Ordered collection of AnalysisLayers, saved as a .mow archive.

    Parameters
    ----------
    well_name : str
        Well identifier.
    metadata : dict
        Arbitrary chain-level metadata.
    """

    def __init__(
        self,
        well_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.well_name = well_name
        self.metadata = metadata or {}
        self.layers: List[AnalysisLayer] = []
        self._arrays: Dict[str, Dict[str, np.ndarray]] = {}

    def add_layer(self, layer: AnalysisLayer) -> None:
        self.layers.append(layer)

    def add_array(self, layer_id: str, name: str, arr: np.ndarray) -> None:
        """Attach a numpy array to a layer (for binary data like point clouds)."""
        self._arrays.setdefault(layer_id, {})[name] = arr

    def get_array(self, layer_id: str, name: str) -> Optional[np.ndarray]:
        return self._arrays.get(layer_id, {}).get(name)

    def save(self, path) -> None:
        """Save the chain as a .mow (zip) archive."""
        path = Path(path)
        with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as zf:
            # Manifest
            manifest = {
                "well_name": self.well_name,
                "metadata": self.metadata,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "layer_count": len(self.layers),
                "layer_ids": [layer.layer_id for layer in self.layers],
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))

            # Layers
            for layer in self.layers:
                prefix = f"layers/{layer.layer_id}"
                zf.writestr(f"{prefix}/meta.json",
                            json.dumps(layer.to_dict(), indent=2, default=str))

                # Attached arrays
                if layer.layer_id in self._arrays:
                    for arr_name, arr in self._arrays[layer.layer_id].items():
                        buf = io.BytesIO()
                        np.save(buf, arr)
                        zf.writestr(f"{prefix}/{arr_name}.npy", buf.getvalue())

    @classmethod
    def load(cls, path) -> AnalysisChain:
        """Load a chain from a .mow (zip) archive."""
        path = Path(path)
        chain = cls()

        with zipfile.ZipFile(str(path), "r") as zf:
            # Manifest
            manifest = json.loads(zf.read("manifest.json"))
            chain.well_name = manifest.get("well_name", "")
            chain.metadata = manifest.get("metadata", {})

            # Layers
            for layer_id in manifest.get("layer_ids", []):
                prefix = f"layers/{layer_id}"
                meta_path = f"{prefix}/meta.json"
                if meta_path in zf.namelist():
                    meta = json.loads(zf.read(meta_path))
                    chain.add_layer(AnalysisLayer.from_dict(meta))

                # Load arrays
                for name in zf.namelist():
                    if name.startswith(f"{prefix}/") and name.endswith(".npy"):
                        arr_name = name.split("/")[-1].replace(".npy", "")
                        buf = io.BytesIO(zf.read(name))
                        chain.add_array(layer_id, arr_name, np.load(buf))

        return chain
