"""Tests for domain knowledge vocabulary — semantic channel descriptions."""

from __future__ import annotations

import pytest


# ── Basic lookup ───────────────────────────────────────────────────────


class TestVocabularyLookup:
    def test_known_channel_has_entry(self):
        """WOB (0117) returns entry with correct canonical."""
        from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry
        entry = get_vocabulary_entry("0117")
        assert entry is not None
        assert entry["canonical"] == "wob"

    def test_unknown_channel_returns_none(self):
        """WITS 9999 returns None."""
        from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry
        assert get_vocabulary_entry("9999") is None

    def test_has_vocabulary_true(self):
        """has_vocabulary returns True for known WITS ID."""
        from mpd_overwatch.knowledge.vocabulary import has_vocabulary
        assert has_vocabulary("0117") is True

    def test_has_vocabulary_false(self):
        """has_vocabulary returns False for unknown WITS ID."""
        from mpd_overwatch.knowledge.vocabulary import has_vocabulary
        assert has_vocabulary("9999") is False

    def test_all_vocabulary_ids_returns_list(self):
        """all_vocabulary_ids returns a non-empty list of strings."""
        from mpd_overwatch.knowledge.vocabulary import all_vocabulary_ids
        ids = all_vocabulary_ids()
        assert isinstance(ids, list)
        assert len(ids) > 0
        assert all(isinstance(wid, str) for wid in ids)


# ── Schema compliance ──────────────────────────────────────────────────


REQUIRED_FIELDS = {
    "canonical",
    "mnemonic",
    "units",
    "physics_domain",
    "index_type",
    "what_it_measures",
    "physical_phenomenon",
    "trust_conditions",
    "common_misinterpretations",
}


class TestSchemaCompliance:
    def test_all_entries_have_required_fields(self):
        """Every entry has all required fields, none are None."""
        from mpd_overwatch.knowledge.vocabulary import (
            get_vocabulary_entry, all_vocabulary_ids,
        )
        for wid in all_vocabulary_ids():
            entry = get_vocabulary_entry(wid)
            assert entry is not None, f"Entry for {wid} is None"
            for field_name in REQUIRED_FIELDS:
                assert field_name in entry, (
                    f"Entry {wid} ({entry.get('canonical', '?')}) "
                    f"missing field: {field_name}"
                )
                assert entry[field_name] is not None, (
                    f"Entry {wid} ({entry.get('canonical', '?')}) "
                    f"has None value for: {field_name}"
                )

    def test_physics_domain_is_enum(self):
        """physics_domain should be a PhysicsDomain enum member."""
        from mpd_overwatch.knowledge.dossier import PhysicsDomain
        from mpd_overwatch.knowledge.vocabulary import (
            get_vocabulary_entry, all_vocabulary_ids,
        )
        for wid in all_vocabulary_ids():
            entry = get_vocabulary_entry(wid)
            assert isinstance(entry["physics_domain"], PhysicsDomain), (
                f"Entry {wid}: physics_domain is not PhysicsDomain enum"
            )

    def test_index_type_is_enum(self):
        """index_type should be an IndexType enum member."""
        from mpd_overwatch.knowledge.dossier import IndexType
        from mpd_overwatch.knowledge.vocabulary import (
            get_vocabulary_entry, all_vocabulary_ids,
        )
        for wid in all_vocabulary_ids():
            entry = get_vocabulary_entry(wid)
            assert isinstance(entry["index_type"], IndexType), (
                f"Entry {wid}: index_type is not IndexType enum"
            )

    def test_common_misinterpretations_is_list(self):
        """common_misinterpretations should be a list of strings."""
        from mpd_overwatch.knowledge.vocabulary import (
            get_vocabulary_entry, all_vocabulary_ids,
        )
        for wid in all_vocabulary_ids():
            entry = get_vocabulary_entry(wid)
            mis = entry["common_misinterpretations"]
            assert isinstance(mis, list), (
                f"Entry {wid}: common_misinterpretations is not a list"
            )
            assert len(mis) > 0, (
                f"Entry {wid}: common_misinterpretations is empty"
            )
            assert all(isinstance(m, str) for m in mis), (
                f"Entry {wid}: common_misinterpretations contains non-strings"
            )


# ── Zero numerics rule ─────────────────────────────────────────────────


FORBIDDEN_NUMERIC_KEYS = {
    "range", "min", "max", "threshold", "limit",
    "default", "typical_value", "nominal",
}


class TestZeroNumerics:
    def test_zero_numeric_values_in_vocabulary(self):
        """No entry has numeric fields like range, threshold, min, max."""
        from mpd_overwatch.knowledge.vocabulary import (
            get_vocabulary_entry, all_vocabulary_ids,
        )
        for wid in all_vocabulary_ids():
            entry = get_vocabulary_entry(wid)
            for key in entry:
                assert key not in FORBIDDEN_NUMERIC_KEYS, (
                    f"Entry {wid} ({entry['canonical']}) has forbidden "
                    f"numeric key: {key}"
                )


# ── Coverage of WITS_SUGGESTIONS ──────────────────────────────────────


class TestWitsCoverage:
    def test_covers_all_wits_suggestions(self):
        """Every WITS ID in WITS_SUGGESTIONS has a vocabulary entry."""
        from mpd_overwatch.data.engine_manifest import WITS_SUGGESTIONS
        from mpd_overwatch.knowledge.vocabulary import has_vocabulary
        missing = []
        for wid in WITS_SUGGESTIONS:
            if not has_vocabulary(wid):
                missing.append(f"{wid} ({WITS_SUGGESTIONS[wid]})")
        assert missing == [], (
            f"Missing vocabulary for WITS IDs: {missing}"
        )


# ── Domain knowledge checks ───────────────────────────────────────────


class TestDomainKnowledge:
    def test_rop_has_connection_artifact_knowledge(self):
        """ROP (0113) misinterpretations mention connection/pipe/artifact."""
        from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry
        entry = get_vocabulary_entry("0113")
        assert entry is not None
        mis_text = " ".join(entry["common_misinterpretations"]).lower()
        assert any(
            word in mis_text for word in ("connection", "pipe", "artifact")
        ), (
            f"ROP misinterpretations should mention connection artifacts: "
            f"{entry['common_misinterpretations']}"
        )

    def test_flow_in_trust_conditions(self):
        """flow_in (0130) trust conditions mention pump."""
        from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry
        entry = get_vocabulary_entry("0130")
        assert entry is not None
        assert "pump" in entry["trust_conditions"].lower(), (
            f"flow_in trust_conditions should mention pump: "
            f"{entry['trust_conditions']}"
        )

    def test_hookload_measures_weight(self):
        """hookload (0114) what_it_measures mentions weight or load."""
        from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry
        entry = get_vocabulary_entry("0114")
        assert entry is not None
        text = entry["what_it_measures"].lower()
        assert any(w in text for w in ("weight", "load")), (
            f"hookload what_it_measures should mention weight: {text}"
        )

    def test_annular_pressure_mentions_downhole(self):
        """annular_pressure (0419) what_it_measures mentions downhole."""
        from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry
        entry = get_vocabulary_entry("0419")
        assert entry is not None
        text = entry["what_it_measures"].lower()
        assert "downhole" in text, (
            f"annular_pressure what_it_measures should mention downhole: {text}"
        )

    def test_spp_physical_phenomenon_mentions_friction(self):
        """standpipe_pressure (0121) physical_phenomenon mentions friction."""
        from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry
        entry = get_vocabulary_entry("0121")
        assert entry is not None
        text = entry["physical_phenomenon"].lower()
        assert "friction" in text, (
            f"SPP physical_phenomenon should mention friction: {text}"
        )
