"""Tests for formation damage engine. Source: Bennion 1998, Hawkins 1956."""

import pytest
from mpd_overwatch.core.formation_damage import skin_factor, productivity_index


class TestSkinFactor:
    """S = (k/kd - 1) * ln(rd/rw). Source: Hawkins, AIME, 1956."""

    def test_standard(self):
        result = skin_factor(k=100, k_d=20, r_d=1.0, r_w=0.354)
        expected = (100 / 20 - 1) * 2.718281828 ** 0  # need ln
        import math
        expected = (100 / 20 - 1) * math.log(1.0 / 0.354)
        assert result == pytest.approx(expected, rel=1e-4)

    def test_no_damage(self):
        """When rd = rw, skin = 0."""
        result = skin_factor(k=100, k_d=50, r_d=0.354, r_w=0.354)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_severe_damage(self):
        """High k/kd ratio = high skin."""
        result = skin_factor(k=100, k_d=1, r_d=2.0, r_w=0.354)
        assert result > 100  # severe damage


class TestProductivityIndex:
    """PI = kh / (141.2 * Bo * mu * (ln(re/rw) + S)). Source: Darcy radial flow."""

    def test_with_skin(self):
        result = productivity_index(k=10, h=50, Bo=1.2, mu=1.5, r_e=1000, r_w=0.354, S=5)
        assert result > 0
        assert result < 1  # should be small for tight rock

    def test_undamaged_higher_than_damaged(self):
        pi_damaged = productivity_index(k=10, h=50, Bo=1.2, mu=1.5, r_e=1000, r_w=0.354, S=5)
        pi_clean = productivity_index(k=10, h=50, Bo=1.2, mu=1.5, r_e=1000, r_w=0.354, S=0)
        assert pi_clean > pi_damaged
