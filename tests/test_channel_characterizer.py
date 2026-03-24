"""Tests for domain-enhanced channel characterizer."""

import json
import pytest

from mpd_overwatch.data.channel_characterizer import (
    build_characterization_prompt,
    parse_characterization_response,
    batch_channels,
    PHYSICS_DOMAINS,
    INDEX_RELATIONSHIPS,
)


class TestPhysicsDomains:
    """Verify domain and relationship enums are defined."""

    def test_domains_defined(self):
        assert "formation" in PHYSICS_DOMAINS
        assert "mechanical" in PHYSICS_DOMAINS
        assert "hydraulic" in PHYSICS_DOMAINS
        assert "flow" in PHYSICS_DOMAINS
        assert "control" in PHYSICS_DOMAINS
        assert "survey" in PHYSICS_DOMAINS

    def test_index_relationships_defined(self):
        assert "time-native" in INDEX_RELATIONSHIPS
        assert "depth-native" in INDEX_RELATIONSHIPS
        assert "bridges-both" in INDEX_RELATIONSHIPS


class TestBuildPrompt:
    """Test prompt construction for channel characterization."""

    def test_prompt_contains_channels(self):
        channels = [
            {"name": "Ann.psi", "unit": "psi", "description": "Annular Pressure"},
            {"name": "ROP", "unit": "ft/hr", "description": "Rate of Penetration"},
        ]
        prompt = build_characterization_prompt(channels, index_type="time")
        assert "Ann.psi" in prompt
        assert "ROP" in prompt
        assert "psi" in prompt

    def test_prompt_includes_index_type(self):
        channels = [{"name": "GR", "unit": "API", "description": "Gamma Ray"}]
        prompt = build_characterization_prompt(channels, index_type="depth")
        assert "depth" in prompt.lower()

    def test_prompt_requests_json(self):
        channels = [{"name": "SPP", "unit": "psi", "description": "Standpipe Pressure"}]
        prompt = build_characterization_prompt(channels, index_type="time")
        assert "json" in prompt.lower() or "JSON" in prompt


class TestParseResponse:
    """Test parsing of LLM characterization responses."""

    def test_parses_valid_json(self):
        raw = json.dumps({"channels": [
            {
                "name": "Ann.psi",
                "physics_domain": "hydraulic",
                "index_relationship": "time-native",
                "mpd_relevance": "primary",
            }
        ]})
        result = parse_characterization_response(raw)
        assert len(result) == 1
        assert result[0]["physics_domain"] == "hydraulic"

    def test_parses_json_in_code_fence(self):
        raw = "```json\n" + json.dumps({"channels": [
            {
                "name": "ROP",
                "physics_domain": "mechanical",
                "index_relationship": "bridges-both",
                "mpd_relevance": "primary",
            }
        ]}) + "\n```"
        result = parse_characterization_response(raw)
        assert len(result) == 1
        assert result[0]["name"] == "ROP"

    def test_returns_empty_on_garbage(self):
        result = parse_characterization_response("this is not json at all")
        assert result == []

    def test_validates_domain_values(self):
        raw = json.dumps({"channels": [
            {
                "name": "X",
                "physics_domain": "invalid_domain",
                "index_relationship": "time-native",
                "mpd_relevance": "primary",
            }
        ]})
        result = parse_characterization_response(raw)
        assert result[0]["physics_domain"] == "unknown"


class TestBatchChannels:
    """Test channel batching for throughput."""

    def test_batch_size_10(self):
        channels = [{"name": f"CH{i}", "unit": "psi", "description": f"Channel {i}"}
                     for i in range(25)]
        batches = batch_channels(channels, batch_size=10)
        assert len(batches) == 3
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 5

    def test_single_batch(self):
        channels = [{"name": "A", "unit": "psi", "description": "test"}]
        batches = batch_channels(channels, batch_size=10)
        assert len(batches) == 1
        assert len(batches[0]) == 1
