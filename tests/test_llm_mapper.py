"""Tests for llm_mapper — prompt builder, response parser, unit validator."""

from __future__ import annotations

import json
import pytest

from unittest.mock import MagicMock

from mpd_overwatch.data.llm_mapper import (
    build_mapping_prompt,
    cache_key,
    extract_las_sections,
    get_system_prompt,
    llm_map_channels,
    load_cached_mapping,
    parse_llm_response,
    save_cached_mapping,
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

    def test_preamble_before_code_fence(self):
        """JSON with LLM preamble text before code fence is handled."""
        payload = {"mappings": [
            {"mnemonic": "GR", "canonical": "gamma_ray", "confidence": 0.9},
        ]}
        raw = f"Here are the mappings:\n```json\n{json.dumps(payload)}\n```"
        result = parse_llm_response(raw)
        assert "GR" in result
        assert result["GR"]["canonical"] == "gamma_ray"

    def test_non_numeric_confidence(self):
        """Non-numeric confidence doesn't crash, defaults to 0.0."""
        payload = {"mappings": [
            {"mnemonic": "GR", "canonical": "gamma_ray", "confidence": "high"},
        ]}
        result = parse_llm_response(json.dumps(payload))
        assert "GR" in result
        assert result["GR"]["confidence"] == 0.0

    def test_confidence_clamped(self):
        """Confidence values are clamped to [0.0, 1.0]."""
        payload = {"mappings": [
            {"mnemonic": "GR", "canonical": "gamma_ray", "confidence": 5.0},
        ]}
        result = parse_llm_response(json.dumps(payload))
        assert result["GR"]["confidence"] == 1.0


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


# ---------------------------------------------------------------------------
# TestMappingCache
# ---------------------------------------------------------------------------

class TestMappingCache:
    """Test per-operator mapping cache."""

    def test_cache_key_deterministic(self):
        curves = ["DEPT", "GRC", "SPPA", "HKLD"]
        key1 = cache_key("Schlumberger", "Noble Energy", curves)
        key2 = cache_key("Schlumberger", "Noble Energy", curves)
        assert key1 == key2

    def test_cache_key_differs_by_service_company(self):
        curves = ["DEPT", "GRC", "SPPA"]
        key1 = cache_key("Schlumberger", "Noble Energy", curves)
        key2 = cache_key("Halliburton", "Noble Energy", curves)
        assert key1 != key2

    def test_cache_key_differs_by_curve_set(self):
        key1 = cache_key("Schlumberger", "Noble", ["DEPT", "GRC"])
        key2 = cache_key("Schlumberger", "Noble", ["DEPT", "GRC", "SPPA"])
        assert key1 != key2

    def test_cache_key_order_independent(self):
        key1 = cache_key("S", "O", ["B", "A", "C"])
        key2 = cache_key("S", "O", ["C", "A", "B"])
        assert key1 == key2

    def test_cache_key_case_insensitive(self):
        key1 = cache_key("Schlumberger", "Noble", ["DEPT"])
        key2 = cache_key("SCHLUMBERGER", "noble", ["dept"])
        assert key1 == key2

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path
        )
        mapping = {
            "GRC": {"canonical": "gamma_ray", "confidence": 0.95},
            "SPPA": {"canonical": "spp", "confidence": 0.90},
        }
        key = "test_key_abc123"
        save_cached_mapping(key, mapping)
        loaded = load_cached_mapping(key)
        assert loaded == mapping

    def test_load_returns_none_for_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path
        )
        assert load_cached_mapping("nonexistent") is None

    def test_load_returns_none_for_corrupt_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path)
        (tmp_path / "bad.json").write_text("{truncated", encoding="utf-8")
        assert load_cached_mapping("bad") is None

    def test_load_returns_none_for_non_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path)
        (tmp_path / "arr.json").write_text("[1, 2, 3]", encoding="utf-8")
        assert load_cached_mapping("arr") is None


# ---------------------------------------------------------------------------
# TestLlmMapChannels
# ---------------------------------------------------------------------------

class TestLlmMapChannels:
    """Test the full orchestration pipeline (LLM call mocked)."""

    def test_returns_mapping_from_llm(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path)
        llm_response = json.dumps({
            "mappings": [
                {"mnemonic": "DEPT", "canonical": "depth_md", "confidence": 0.99},
                {"mnemonic": "GRC", "canonical": "gamma_ray", "confidence": 0.95},
                {"mnemonic": "SPPA", "canonical": "spp", "confidence": 0.90},
            ]
        })
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=llm_response))]
        mock_client.chat.completions.create.return_value = mock_completion
        result = llm_map_channels(
            well_lines=["SRVC.  Schlumberger: SERVICE COMPANY", "COMP.  Noble: COMPANY"],
            curve_lines=["DEPT.FT  : Depth", "GRC .API : Calibrated Gamma", "SPPA.PSI : Standpipe Pressure"],
            curve_units={"DEPT": "FT", "GRC": "API", "SPPA": "PSI"},
            service_company="Schlumberger", operator="Noble", client=mock_client,
        )
        assert result["DEPT"]["canonical"] == "depth_md"
        assert result["GRC"]["canonical"] == "gamma_ray"
        assert result["SPPA"]["canonical"] == "spp"

    def test_uses_cache_on_second_call(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path)
        llm_response = json.dumps({"mappings": [{"mnemonic": "GR", "canonical": "gamma_ray", "confidence": 0.9}]})
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=llm_response))]
        mock_client.chat.completions.create.return_value = mock_completion
        kwargs = dict(well_lines=["SRVC. Pason: SVC"], curve_lines=["GR.API : Gamma Ray"],
                      curve_units={"GR": "API"}, service_company="Pason", operator="EOG", client=mock_client)
        result1 = llm_map_channels(**kwargs)
        assert mock_client.chat.completions.create.call_count == 1
        result2 = llm_map_channels(**kwargs)
        assert mock_client.chat.completions.create.call_count == 1  # NOT 2
        assert result1 == result2

    def test_validation_rejects_bad_unit_mapping(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path)
        llm_response = json.dumps({"mappings": [{"mnemonic": "GRC", "canonical": "spp", "confidence": 0.8}]})
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=llm_response))]
        mock_client.chat.completions.create.return_value = mock_completion
        result = llm_map_channels(well_lines=[], curve_lines=["GRC .API : Calibrated Gamma"],
                                  curve_units={"GRC": "API"}, service_company="SLB", operator="Test", client=mock_client)
        assert result["GRC"]["canonical"] is None

    def test_graceful_failure_when_llm_unreachable(self, tmp_path, monkeypatch):
        monkeypatch.setattr("mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path)
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")
        result = llm_map_channels(well_lines=[], curve_lines=["GR.API : Gamma"],
                                  curve_units={"GR": "API"}, service_company="", operator="", client=mock_client)
        assert result == {}

    def test_low_confidence_rejected(self, tmp_path, monkeypatch):
        """Mappings below confidence_threshold get canonical set to None."""
        monkeypatch.setattr("mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path)
        llm_response = json.dumps({"mappings": [
            {"mnemonic": "GR", "canonical": "gamma_ray", "confidence": 0.3},
        ]})
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=llm_response))]
        mock_client.chat.completions.create.return_value = mock_completion
        result = llm_map_channels(well_lines=[], curve_lines=["GR.API : Gamma"],
                                  curve_units={"GR": "API"}, service_company="X", operator="Y", client=mock_client)
        assert result["GR"]["canonical"] is None

    def test_skip_cache_forces_llm_call(self, tmp_path, monkeypatch):
        """skip_cache=True bypasses cache and calls LLM again."""
        monkeypatch.setattr("mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path)
        llm_response = json.dumps({"mappings": [
            {"mnemonic": "GR", "canonical": "gamma_ray", "confidence": 0.9},
        ]})
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=llm_response))]
        mock_client.chat.completions.create.return_value = mock_completion
        kwargs = dict(well_lines=[], curve_lines=["GR.API : Gamma"],
                      curve_units={"GR": "API"}, service_company="A", operator="B", client=mock_client)
        llm_map_channels(**kwargs)
        assert mock_client.chat.completions.create.call_count == 1
        llm_map_channels(**kwargs, skip_cache=True)
        assert mock_client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# TestExtractLasSections
# ---------------------------------------------------------------------------

class TestExtractLasSections:
    """Test extraction of ~W and ~C raw lines from LAS text."""

    def test_extracts_well_and_curve_sections(self):
        las_text = """~VERSION INFORMATION
VERS.  2.0 : CWLS LOG ASCII STANDARD
~WELL INFORMATION
COMP.  Noble Energy: COMPANY
SRVC.  Schlumberger: SERVICE COMPANY
~CURVE INFORMATION
DEPT.FT  : Measured Depth
GRC .API : Calibrated Gamma
~ASCII DATA
100.0  55.3
"""
        well_lines, curve_lines = extract_las_sections(las_text)
        assert any("Noble" in l for l in well_lines)
        assert any("GRC" in l for l in curve_lines)
        assert not any("100.0" in l for l in curve_lines)

    def test_handles_missing_sections(self):
        las_text = "~A\n100.0 200.0\n"
        well_lines, curve_lines = extract_las_sections(las_text)
        assert well_lines == []
        assert curve_lines == []
