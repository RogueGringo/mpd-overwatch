"""V&V Section 0: Data Architecture Correctness.

Principle: Zero measurement data crosses the browser boundary.
All numpy arrays stay server-side in WellDatabase.
Only Dict[str, str] assignments travel through dcc.Store.
"""

import json
import re
from pathlib import Path

import pytest


_DASHBOARD_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "mpd_overwatch" / "dashboard"
)

_SRC_DIR = (
    Path(__file__).resolve().parent.parent / "src"
)

# Old canonical names that must NOT appear as channel-map keys
_OLD_CANONICAL_NAMES = {
    "depth_md", "spp", "apwd", "tvd", "mud_weight",
}

# Analysis page files that render data
_ANALYSIS_PAGES = [
    "hydraulics.py",
    "pore_pressure.py",
    "geomechanics.py",
    "formation_damage.py",
    "well_overview.py",
    "supervisory_panel.py",
    "hmu_panel.py",
    "topology.py",
    "persistent_homology_page.py",
    "atft_analysis.py",
]


class TestNoBrowserSerializedArrays:
    """No code should import the deleted serialize/deserialize_channel_map."""

    def test_no_serialize_channel_map_imports(self):
        """Grep all .py files under src/ for serialize_channel_map imports."""
        hits = []
        for py_file in _SRC_DIR.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                if "serialize_channel_map" in line and "deprecated" not in line.lower():
                    hits.append(f"{py_file.relative_to(_SRC_DIR)}:{i}: {line.strip()}")
        assert hits == [], (
            f"Found {len(hits)} references to deleted serialize_channel_map:\n"
            + "\n".join(hits)
        )

    def test_no_deserialize_channel_map_imports(self):
        """Grep all .py files under src/ for deserialize_channel_map imports."""
        hits = []
        for py_file in _SRC_DIR.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                if "deserialize_channel_map" in line and "deprecated" not in line.lower():
                    hits.append(f"{py_file.relative_to(_SRC_DIR)}:{i}: {line.strip()}")
        assert hits == [], (
            f"Found {len(hits)} references to deleted deserialize_channel_map:\n"
            + "\n".join(hits)
        )


class TestAllPagesUseServerSideData:
    """Every analysis page must call get_well_database(), not receive arrays."""

    @pytest.mark.parametrize("page_file", _ANALYSIS_PAGES)
    def test_page_imports_get_well_database(self, page_file):
        """Each analysis page must import get_well_database from data_store."""
        filepath = _DASHBOARD_DIR / page_file
        if not filepath.exists():
            pytest.skip(f"{page_file} not found")
        text = filepath.read_text(encoding="utf-8", errors="ignore")
        assert "get_well_database" in text, (
            f"{page_file} does not reference get_well_database — "
            "may be accessing data through browser store instead of server-side"
        )

    @pytest.mark.parametrize("page_file", _ANALYSIS_PAGES)
    def test_page_does_not_deserialize_arrays(self, page_file):
        """No analysis page should call deserialize_channel_map."""
        filepath = _DASHBOARD_DIR / page_file
        if not filepath.exists():
            pytest.skip(f"{page_file} not found")
        text = filepath.read_text(encoding="utf-8", errors="ignore")
        assert "deserialize_channel_map" not in text, (
            f"{page_file} still uses deserialize_channel_map — "
            "must migrate to server-side WellDatabase pattern"
        )


class TestStoreSize:
    """The channel-map dcc.Store must carry only lightweight assignments."""

    def test_assignments_json_size_under_10kb(self, assigned_db):
        """Serialized assignments dict must be < 10KB."""
        assignments = dict(assigned_db.assignments)
        json_str = json.dumps(assignments)
        size_bytes = len(json_str.encode("utf-8"))
        assert size_bytes < 10_000, (
            f"Assignments JSON is {size_bytes} bytes — "
            f"should be < 10,000. Contains {len(assignments)} entries."
        )

    def test_assignments_values_are_strings(self, assigned_db):
        """Every value in assignments must be a string (WITS ID), not a list/array."""
        for canonical, wits_id in assigned_db.assignments.items():
            assert isinstance(wits_id, str), (
                f"Assignment {canonical} -> {type(wits_id).__name__} "
                f"(expected str WITS ID, got {wits_id!r})"
            )


class TestCanonicalNameConsistency:
    """Analysis pages must use new canonical names, not old ones."""

    @pytest.mark.parametrize("page_file", _ANALYSIS_PAGES)
    def test_no_old_canonical_keys(self, page_file):
        """No analysis page should use old canonical names as channel keys."""
        filepath = _DASHBOARD_DIR / page_file
        if not filepath.exists():
            pytest.skip(f"{page_file} not found")
        text = filepath.read_text(encoding="utf-8", errors="ignore")
        hits = []
        for old_name in _OLD_CANONICAL_NAMES:
            # Match quoted uses like channel_map["depth_md"] or _get("spp")
            # but NOT comments or label text strings
            pattern = rf'["\']({re.escape(old_name)})["\']'
            for m in re.finditer(pattern, text):
                # Get the line for context
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                line = text[line_start:line_end].strip()
                # Skip if it's in a display string or color theme lookup
                if any(kw in line.lower() for kw in ("label", "title", "header", "description", "text=", "colors[")):
                    continue
                hits.append(f"  {old_name}: {line}")
        assert hits == [], (
            f"{page_file} uses old canonical name(s) as channel keys:\n"
            + "\n".join(hits)
        )
