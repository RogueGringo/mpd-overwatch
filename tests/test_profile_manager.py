import json
import pytest
from mpd_overwatch.dashboard.profile_manager import (
    save_profile, load_profile, find_matching_profile, list_profiles,
)


def test_save_and_load_profile(tmp_path):
    profile = {
        "profile_name": "Test Profile",
        "key": {"service_company": "H&P", "data_provider": "Pason", "rig_id": "566"},
        "intent": "MPD Operations",
        "channels": [
            {"vendor_mnemonic": "Hook", "canonical": "hookload", "unit": "klb",
             "range_min": 0, "range_max": 600},
        ],
        "custom_aliases": {"Casing Press": "casing_pressure"},
    }
    save_profile(profile, profiles_dir=str(tmp_path))
    loaded = load_profile("Test Profile", profiles_dir=str(tmp_path))
    assert loaded["profile_name"] == "Test Profile"
    assert loaded["key"]["rig_id"] == "566"
    assert len(loaded["channels"]) == 1


def test_find_matching_profile(tmp_path):
    profile = {
        "profile_name": "H&P 566",
        "key": {"service_company": "H&P", "data_provider": "Pason", "rig_id": "566"},
        "intent": "MPD Operations",
        "channels": [],
        "custom_aliases": {},
    }
    save_profile(profile, profiles_dir=str(tmp_path))
    match = find_matching_profile("H&P", "Pason", "566", profiles_dir=str(tmp_path))
    assert match is not None
    assert match["profile_name"] == "H&P 566"


def test_no_matching_profile(tmp_path):
    match = find_matching_profile("Unknown", "Unknown", "999", profiles_dir=str(tmp_path))
    assert match is None


def test_list_profiles(tmp_path):
    for i in range(3):
        save_profile({
            "profile_name": f"Profile {i}",
            "key": {"service_company": "Co", "data_provider": "P", "rig_id": str(i)},
            "intent": "Custom", "channels": [], "custom_aliases": {},
        }, profiles_dir=str(tmp_path))
    profiles = list_profiles(profiles_dir=str(tmp_path))
    assert len(profiles) == 3
