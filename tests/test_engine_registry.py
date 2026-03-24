"""Tests for ENGINE_REGISTRY data integrity and helper functions."""

import pytest


class TestEngineRegistryData:
    """ENGINE_REGISTRY has all 12 engines with required fields."""

    def test_registry_has_12_engines(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        assert len(ENGINE_REGISTRY) == 12

    def test_all_engines_have_required_fields(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        required = {"id", "display_name", "effect", "method", "attribution", "tier", "route", "import_path", "sub_engines", "vv_grade"}
        for engine in ENGINE_REGISTRY:
            missing = required - set(engine.keys())
            assert not missing, f"Engine {engine.get('display_name', '?')} missing: {missing}"

    def test_unique_ids(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        ids = [e["id"] for e in ENGINE_REGISTRY]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"

    def test_unique_display_names(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        names = [e["display_name"] for e in ENGINE_REGISTRY]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_valid_tiers(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        valid = {"CLASSICAL", "NOVEL", "INFRA"}
        for engine in ENGINE_REGISTRY:
            assert engine["tier"] in valid, f"{engine['display_name']} has invalid tier {engine['tier']}"

    def test_tier_counts(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        tiers = [e["tier"] for e in ENGINE_REGISTRY]
        assert tiers.count("CLASSICAL") == 6
        assert tiers.count("NOVEL") == 3
        assert tiers.count("INFRA") == 3

    def test_classical_engines_have_routes(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        for engine in ENGINE_REGISTRY:
            if engine["tier"] == "CLASSICAL":
                assert engine["route"] is not None, f"{engine['display_name']} missing route"
                assert engine["route"].startswith("/"), f"{engine['display_name']} route must start with /"

    def test_novel_engines_have_routes(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        for engine in ENGINE_REGISTRY:
            if engine["tier"] == "NOVEL":
                assert engine["route"] is not None, f"{engine['display_name']} missing route"

    def test_sub_engines_are_lists(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        for engine in ENGINE_REGISTRY:
            assert isinstance(engine["sub_engines"], list), f"{engine['display_name']} sub_engines must be list"
            assert len(engine["sub_engines"]) >= 1, f"{engine['display_name']} must have at least 1 sub-engine"


class TestEngineStatusChecks:
    """Engine health check functions work correctly."""

    def test_get_engine_status_returns_valid_state(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY, get_engine_status
        engine = ENGINE_REGISTRY[0]  # Hydraulics — should be importable
        status = get_engine_status(engine)
        assert status in ("online", "error", "degraded", "offline")

    def test_hydraulics_engine_is_online(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY, get_engine_status
        hydraulics = [e for e in ENGINE_REGISTRY if e["display_name"] == "Pressure & Flow"][0]
        assert get_engine_status(hydraulics) == "online"

    def test_get_all_statuses_returns_dict(self):
        from mpd_overwatch.dashboard.engine_registry import get_all_statuses
        statuses = get_all_statuses()
        assert isinstance(statuses, dict)
        assert len(statuses) == 12

    def test_get_engines_by_tier(self):
        from mpd_overwatch.dashboard.engine_registry import get_engines_by_tier
        classical = get_engines_by_tier("CLASSICAL")
        assert len(classical) == 6
        novel = get_engines_by_tier("NOVEL")
        assert len(novel) == 3
        infra = get_engines_by_tier("INFRA")
        assert len(infra) == 3


class TestTierColors:
    """Tier color mappings are defined."""

    def test_tier_colors_defined(self):
        from mpd_overwatch.dashboard.engine_registry import TIER_COLORS
        assert "CLASSICAL" in TIER_COLORS
        assert "NOVEL" in TIER_COLORS
        assert "INFRA" in TIER_COLORS
        assert TIER_COLORS["CLASSICAL"] == "#00d4ff"
        assert TIER_COLORS["NOVEL"] == "#c084fc"
        assert TIER_COLORS["INFRA"] == "#ffd700"
