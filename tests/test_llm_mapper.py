"""Tests for llm_mapper — prompt builder, response parser, unit validator."""

from __future__ import annotations

import json
import pytest

from mpd_overwatch.data.llm_mapper import (
    build_mapping_prompt,
    get_system_prompt,
    parse_llm_response,
    validate_mapping,
    _get_canonical_targets,
    _MAX_CURVE_LINES,
)
from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry


# ---------------------------------------------------------------------------
# TestBuildMappingPrompt
# ---------------------------------------------------------------------------

class TestBuildMappingPrompt:
    """Tests for build_mapping_prompt()."""

    def test_prompt_contains_mnemonic(self):
        """Curve mnemonics appear in the built prompt."""
        well = ["WELL.  Test Well 1"]
        curves = ["GRC  .API   : Gamma Ray Corrected"]
        prompt = build_mapping_prompt(well, curves)
        assert "GRC" in prompt

    def test_prompt_contains_well_context(self):
        """Well section lines appear in the prompt."""
        well = ["WELL.  Permian Basin #7"]
        curves = ["SPP .psi : Standpipe Pressure"]
        prompt = build_mapping_prompt(well, curves)
        assert "Permian Basin #7" in prompt

    def test_prompt_contains_json_keyword(self):
        """The system prompt asks for JSON output."""
        prompt = get_system_prompt()
        assert "JSON" in prompt

    def test_empty_well_section(self):
        """Empty well section should not crash."""
        curves = ["GRC  .API   : Gamma Ray Corrected"]
        prompt = build_mapping_prompt([], curves)
        assert "GRC" in prompt

    def test_truncation_at_max_curve_lines(self):
        """Curve lines beyond _MAX_CURVE_LINES are truncated."""
        curves = [f"CURVE_{i} .unit : desc {i}" for i in range(200)]
        prompt = build_mapping_prompt([], curves)
        # Should contain the first curve but not the last
        assert "CURVE_0" in prompt
        assert "CURVE_199" not in prompt
        # Should mention truncation
        assert "truncated" in prompt.lower() or "more" in prompt.lower()


# ---------------------------------------------------------------------------
# TestParseLlmResponse
# ---------------------------------------------------------------------------

class TestParseLlmResponse:
    """Tests for parse_llm_response()."""

    def test_valid_json(self):
        """Standard JSON response is parsed correctly."""
        payload = {
            "mappings": [
                {"mnemonic": "GRC", "canonical": "gamma_ray", "confidence": 0.95},
                {"mnemonic": "SPP", "canonical": "spp", "confidence": 0.99},
            ]
        }
        result = parse_llm_response(json.dumps(payload))
        assert "GRC" in result
        assert result["GRC"]["canonical"] == "gamma_ray"
        assert result["GRC"]["confidence"] == 0.95
        assert result["SPP"]["canonical"] == "spp"

    def test_markdown_fenced_json(self):
        """JSON wrapped in ```json ... ``` fences is handled."""
        payload = {
            "mappings": [
                {"mnemonic": "HKLD", "canonical": "hookload", "confidence": 0.9},
            ]
        }
        raw = f"```json\n{json.dumps(payload)}\n```"
        result = parse_llm_response(raw)
        assert "HKLD" in result
        assert result["HKLD"]["canonical"] == "hookload"

    def test_garbage_input_returns_empty(self):
        """Completely garbled text returns an empty dict."""
        result = parse_llm_response("I don't know what you're asking")
        assert result == {}

    def test_invalid_canonical_set_to_none(self):
        """Canonical names not in the target list become None."""
        payload = {
            "mappings": [
                {"mnemonic": "XYZ", "canonical": "bogus_channel_name", "confidence": 0.8},
            ]
        }
        result = parse_llm_response(json.dumps(payload))
        assert "XYZ" in result
        assert result["XYZ"]["canonical"] is None

    def test_mnemonic_uppercased(self):
        """Mnemonics are normalized to uppercase."""
        payload = {
            "mappings": [
                {"mnemonic": "grc", "canonical": "gamma_ray", "confidence": 0.85},
            ]
        }
        result = parse_llm_response(json.dumps(payload))
        assert "GRC" in result


# ---------------------------------------------------------------------------
# TestValidateMapping
# ---------------------------------------------------------------------------

class TestValidateMapping:
    """Tests for validate_mapping()."""

    def test_compatible_unit_accepted(self):
        """GRC with API unit maps to gamma_ray — compatible."""
        registry = ChannelRegistry()
        assert validate_mapping("GRC", "gamma_ray", "API", registry) is True

    def test_incompatible_unit_rejected(self):
        """GRC with API unit should NOT map to spp (pressure channel)."""
        registry = ChannelRegistry()
        assert validate_mapping("GRC", "spp", "API", registry) is False

    def test_empty_unit_accepted(self):
        """Empty/missing unit is inconclusive — accept the mapping."""
        registry = ChannelRegistry()
        assert validate_mapping("GRC", "gamma_ray", "", registry) is True

    def test_unknown_canonical_accepted(self):
        """Unknown canonical channel not in unit table — inconclusive, accept."""
        registry = ChannelRegistry()
        assert validate_mapping("XYZ", "some_unknown_channel", "psi", registry) is True


# ---------------------------------------------------------------------------
# TestGetCanonicalTargets
# ---------------------------------------------------------------------------

class TestGetCanonicalTargets:
    """Tests for _get_canonical_targets()."""

    def test_contains_registry_channels(self):
        """All default registry channels appear in target list."""
        targets = _get_canonical_targets()
        assert "gamma_ray" in targets
        assert "spp" in targets
        assert "hookload" in targets

    def test_contains_extra_targets(self):
        """Extra targets like depth_md and tvd appear."""
        targets = _get_canonical_targets()
        assert "depth_md" in targets
        assert "tvd" in targets
        assert "toolface" in targets

    def test_sorted_and_unique(self):
        """Target list is sorted and has no duplicates."""
        targets = _get_canonical_targets()
        assert targets == sorted(set(targets))
