"""
MPD Command - Zone Intelligence Engine
=======================================

Analyzes drilling data along the lateral to classify depth intervals into
zone types and generate completion recommendations.  Based on the MPD-MWD
Data Protocols document.

Architecture
------------
1. **BaselineCalculator** - computes moving-average baselines for gamma,
   APWD, SPP, ROP from offset-well data or the initial lateral section.
2. **ZoneFlagAlgorithm** - slides a window along the lateral evaluating
   multi-channel deviation from baseline, then classifies each interval.
3. **CompletionAdvisor** - converts flagged zones into stage-level
   completion design recommendations.
4. **ZoneIntelligenceEngine** - orchestrator that wires the above together
   and produces a structured summary report.

Usage::

    engine = ZoneIntelligenceEngine()
    report = engine.analyze(drilling_data, baseline_data=offset_data)
    for zone in report.zones:
        print(zone.short_label())
    for rec in report.recommendations:
        print(rec.summary_line())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from mpd_overwatch.data.models import (
    CompletionRecommendation,
    DivertStrategy,
    DrillingData,
    ZoneClassification,
    ZoneFlag,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration defaults (all can be overridden at construction time)
# ---------------------------------------------------------------------------

@dataclass
class ZoneConfig:
    """Tunable thresholds for the zone-flagging algorithm.

    All deviation thresholds are expressed as multiples of the baseline
    standard deviation unless noted otherwise.
    """

    # Baseline window (number of depth samples for rolling average)
    baseline_window: int = 50

    # Zone evaluation window (number of depth samples per zone interval)
    zone_window: int = 25

    # Minimum zone length in feet before a flag is emitted
    min_zone_length_ft: float = 50.0

    # --- Gamma ray thresholds ---
    gamma_low_sigma: float = -1.0       # below this = "low gamma" (reservoir)
    gamma_high_sigma: float = 1.5       # above this = shale/non-reservoir

    # --- APWD thresholds (sigma from baseline) ---
    apwd_high_sigma: float = 1.5        # elevated pressure
    apwd_low_sigma: float = -1.5        # depleted pressure
    apwd_fluctuation_sigma: float = 2.0 # window std-dev threshold for instability

    # --- ROP thresholds ---
    rop_spike_sigma: float = 2.0        # rapid increase
    rop_drop_sigma: float = -1.5        # slowdown

    # --- Flow discrepancy ---
    flow_disc_loss_pct: float = -5.0    # negative = losses
    flow_disc_gain_pct: float = 5.0     # positive = gains / influx

    # --- Choke pressure trend ---
    choke_rising_psi_per_ft: float = 0.05   # positive slope = rising
    choke_falling_psi_per_ft: float = -0.05 # negative slope = falling

    # --- Torque ---
    torque_spike_sigma: float = 2.0

    # --- Confidence weighting ---
    # Each criterion that matches adds to the raw score; confidence is
    # raw_score / max_possible_score, clamped to [0, 1].
    weight_gamma: float = 1.0
    weight_apwd: float = 1.5
    weight_rop: float = 1.0
    weight_flow: float = 1.5
    weight_choke: float = 1.0
    weight_torque: float = 0.8

    # --- Completion defaults ---
    default_cluster_count: int = 5
    default_cluster_spacing_ft: float = 40.0
    default_proppant_per_cluster_lbs: float = 50_000.0
    default_pump_rate_bpm: float = 80.0


# ---------------------------------------------------------------------------
# 1.  Baseline Calculator
# ---------------------------------------------------------------------------

class BaselineCalculator:
    """Compute rolling-average baselines and standard deviations for key channels."""

    def __init__(self, window: int = 50) -> None:
        self.window = window

    def compute(
        self,
        data: DrillingData,
        offset_data: Optional[DrillingData] = None,
    ) -> pd.DataFrame:
        """Return a DataFrame with baseline means and sigmas for each channel.

        If *offset_data* is provided, global mean/std are taken from the
        offset well and the rolling baseline is still computed on the
        subject well (useful for detecting deviations from an established
        norm).

        Columns produced::

            gamma_ray_mean, gamma_ray_std,
            apwd_mean, apwd_std,
            spp_mean, spp_std,
            rop_mean, rop_std,
            torque_mean, torque_std,
            choke_pressure_mean, choke_pressure_std,
            flow_discrepancy (raw %)
        """
        channels = {
            "gamma_ray": data.gamma_ray,
            "apwd": data.apwd,
            "spp": data.spp,
            "rop": data.rop,
            "torque": data.torque,
            "choke_pressure": data.choke_pressure,
        }

        df = pd.DataFrame({"depth_md": data.depth_md})

        for name, arr in channels.items():
            series = pd.Series(arr, dtype=np.float64)

            if offset_data is not None:
                offset_arr = getattr(offset_data, name, None)
                if offset_arr is not None and len(offset_arr) > 0:
                    global_mean = float(np.nanmean(offset_arr))
                    global_std = float(np.nanstd(offset_arr))
                    if global_std == 0:
                        global_std = 1.0
                else:
                    global_mean = float(np.nanmean(arr))
                    global_std = float(np.nanstd(arr)) or 1.0
            else:
                global_mean = None
                global_std = None

            if global_mean is not None:
                # Offset-derived baseline: constant across the well
                df[f"{name}_mean"] = global_mean
                df[f"{name}_std"] = global_std
            else:
                # No offset data: use the full-dataset statistics as the
                # baseline so that local anomalies are *not* absorbed into
                # their own rolling average.  This assumes anomalous
                # intervals are a minority of the lateral.
                full_mean = float(np.nanmean(arr))
                full_std = float(np.nanstd(arr))
                if full_std == 0:
                    full_std = 1.0
                df[f"{name}_mean"] = full_mean
                df[f"{name}_std"] = full_std

        # Flow discrepancy (percentage)
        df["flow_discrepancy"] = data.flow_discrepancy

        return df


# ---------------------------------------------------------------------------
# 2.  Zone Flagging Algorithm
# ---------------------------------------------------------------------------

class ZoneFlagAlgorithm:
    """Evaluate depth intervals against multi-channel criteria and assign
    zone classifications."""

    def __init__(self, config: ZoneConfig) -> None:
        self.cfg = config

    def flag_zones(
        self,
        data: DrillingData,
        baseline: pd.DataFrame,
    ) -> List[ZoneFlag]:
        """Slide a window along the lateral and classify each interval.

        Parameters
        ----------
        data : DrillingData
        baseline : DataFrame
            Output of :meth:`BaselineCalculator.compute`.

        Returns
        -------
        list of ZoneFlag
        """
        n = data.n_points
        if n == 0:
            return []

        step = max(1, self.cfg.zone_window // 2)  # 50 % overlap
        zones: List[ZoneFlag] = []

        i = 0
        while i < n:
            j = min(i + self.cfg.zone_window, n)

            # Skip if the interval is too short
            interval_len = float(data.depth_md[j - 1] - data.depth_md[i])
            if interval_len < self.cfg.min_zone_length_ft and j < n:
                i += step
                continue

            zone = self._evaluate_interval(data, baseline, i, j)
            if zone is not None:
                zones.append(zone)

            i += step

        # Merge adjacent zones of the same type
        zones = self._merge_adjacent(zones)

        return zones

    # -- interval evaluation ------------------------------------------------

    def _evaluate_interval(
        self,
        data: DrillingData,
        bl: pd.DataFrame,
        i: int,
        j: int,
    ) -> Optional[ZoneFlag]:
        """Classify a single depth interval [i, j)."""
        sl = slice(i, j)
        cfg = self.cfg

        # ------ Extract interval statistics ------
        gamma_vals = data.gamma_ray[sl]
        apwd_vals = data.apwd[sl]
        rop_vals = data.rop[sl]
        torque_vals = data.torque[sl]
        choke_vals = data.choke_pressure[sl]
        depth_vals = data.depth_md[sl]

        gamma_avg = float(np.nanmean(gamma_vals))
        apwd_avg = float(np.nanmean(apwd_vals))
        rop_avg = float(np.nanmean(rop_vals))
        flow_disc = float(np.nanmean(bl["flow_discrepancy"].iloc[i:j]))

        # Baseline means / stds for the interval midpoint
        mid = (i + j) // 2
        gamma_bl_mean = float(bl["gamma_ray_mean"].iloc[mid])
        gamma_bl_std = float(bl["gamma_ray_std"].iloc[mid]) or 1.0
        apwd_bl_mean = float(bl["apwd_mean"].iloc[mid])
        apwd_bl_std = float(bl["apwd_std"].iloc[mid]) or 1.0
        rop_bl_mean = float(bl["rop_mean"].iloc[mid])
        rop_bl_std = float(bl["rop_std"].iloc[mid]) or 1.0
        torque_bl_mean = float(bl["torque_mean"].iloc[mid])
        torque_bl_std = float(bl["torque_std"].iloc[mid]) or 1.0

        # Sigma deviations
        gamma_sigma = (gamma_avg - gamma_bl_mean) / gamma_bl_std
        apwd_sigma = (apwd_avg - apwd_bl_mean) / apwd_bl_std
        rop_sigma = (rop_avg - rop_bl_mean) / rop_bl_std
        torque_sigma = (float(np.nanmean(torque_vals)) - torque_bl_mean) / torque_bl_std
        apwd_window_std = float(np.nanstd(apwd_vals))

        # Choke pressure trend (linear slope psi/ft)
        choke_trend = self._linear_slope(depth_vals, choke_vals)

        # ------ Score each criterion ------
        scores: Dict[str, float] = {}

        # Gamma
        if gamma_sigma <= cfg.gamma_low_sigma:
            scores["gamma_low"] = cfg.weight_gamma
        elif gamma_sigma >= cfg.gamma_high_sigma:
            scores["gamma_high"] = cfg.weight_gamma

        # APWD
        if apwd_sigma >= cfg.apwd_high_sigma:
            scores["apwd_high"] = cfg.weight_apwd
        elif apwd_sigma <= cfg.apwd_low_sigma:
            scores["apwd_low"] = cfg.weight_apwd
        if apwd_window_std / apwd_bl_std >= cfg.apwd_fluctuation_sigma:
            scores["apwd_fluct"] = cfg.weight_apwd * 0.5

        # ROP
        if rop_sigma >= cfg.rop_spike_sigma:
            scores["rop_spike"] = cfg.weight_rop
        elif rop_sigma <= cfg.rop_drop_sigma:
            scores["rop_drop"] = cfg.weight_rop

        # Flow discrepancy
        if flow_disc <= cfg.flow_disc_loss_pct:
            scores["flow_loss"] = cfg.weight_flow
        elif flow_disc >= cfg.flow_disc_gain_pct:
            scores["flow_gain"] = cfg.weight_flow

        # Choke pressure
        if choke_trend >= cfg.choke_rising_psi_per_ft:
            scores["choke_rising"] = cfg.weight_choke
        elif choke_trend <= cfg.choke_falling_psi_per_ft:
            scores["choke_falling"] = cfg.weight_choke

        # Torque
        if torque_sigma >= cfg.torque_spike_sigma:
            scores["torque_spike"] = cfg.weight_torque

        # ------ Classify ------
        classification, notes = self._classify(scores, gamma_sigma, apwd_sigma)
        max_possible = sum([
            cfg.weight_gamma, cfg.weight_apwd * 1.5,
            cfg.weight_rop, cfg.weight_flow,
            cfg.weight_choke, cfg.weight_torque,
        ])
        raw_score = sum(scores.values())
        confidence = min(1.0, raw_score / max_possible) if max_possible > 0 else 0.0

        # For NORMAL zones with low confidence, skip emitting
        if classification == ZoneClassification.NORMAL and confidence < 0.15:
            classification = ZoneClassification.NORMAL

        top_md = float(data.depth_md[i])
        bot_md = float(data.depth_md[j - 1])
        top_tvd = float(data.depth_tvd[i]) if not np.isnan(data.depth_tvd[i]) else top_md
        bot_tvd = float(data.depth_tvd[j - 1]) if not np.isnan(data.depth_tvd[j - 1]) else bot_md

        return ZoneFlag(
            top_md=top_md,
            bottom_md=bot_md,
            top_tvd=top_tvd,
            bottom_tvd=bot_tvd,
            classification=classification,
            confidence=confidence,
            gamma_avg=gamma_avg,
            apwd_avg=apwd_avg,
            rop_avg=rop_avg,
            flow_discrepancy_pct=flow_disc,
            choke_trend=choke_trend,
            notes=notes,
        )

    def _classify(
        self,
        scores: Dict[str, float],
        gamma_sigma: float,
        apwd_sigma: float,
    ) -> Tuple[ZoneClassification, str]:
        """Determine the zone type from the scored criteria."""
        s = set(scores.keys())

        # HIGH_POTENTIAL: low gamma + stable/high APWD
        if "gamma_low" in s and "apwd_low" not in s and "apwd_fluct" not in s:
            return (
                ZoneClassification.HIGH_POTENTIAL,
                "Low gamma (reservoir quality) with stable/elevated APWD -- "
                "high-quality pay, minimal damage expected with MPD.",
            )

        # OVERPRESSURED: elevated APWD + rising choke
        if "apwd_high" in s and "choke_rising" in s:
            return (
                ZoneClassification.OVERPRESSURED,
                "Elevated APWD with rising choke pressure -- overpressured zone. "
                "MPD choke management critical to maintain wellbore stability.",
            )

        # FRACTURED: flow discrepancy + ROP spike + APWD drop
        if ("flow_loss" in s or "flow_gain" in s) and "rop_spike" in s:
            return (
                ZoneClassification.FRACTURED,
                "Flow discrepancy with ROP spike -- natural fracture network "
                "likely. Expect fluid losses or gains. Diversion recommended "
                "during completion.",
            )

        # Also flag FRACTURED on choke + flow even without ROP
        if ("flow_loss" in s or "flow_gain" in s) and "choke_rising" in s:
            return (
                ZoneClassification.FRACTURED,
                "Flow discrepancy coincident with rising choke pressure -- "
                "fractured interval. Requires diversion strategy for completion.",
            )

        # DEPLETED: APWD below baseline + low ROP
        if "apwd_low" in s and "rop_drop" in s:
            return (
                ZoneClassification.DEPLETED,
                "APWD below baseline with reduced ROP -- depleted zone. "
                "Consider reducing or skipping stimulation.",
            )
        if "apwd_low" in s:
            return (
                ZoneClassification.DEPLETED,
                "APWD below baseline -- likely depleted zone. "
                "Evaluate offset production before allocating proppant.",
            )

        # UNSTABLE: torque spikes + APWD fluctuation
        if "torque_spike" in s and "apwd_fluct" in s:
            return (
                ZoneClassification.UNSTABLE,
                "Torque anomaly with APWD fluctuation -- borehole instability. "
                "Maintain ECD within narrow window.",
            )
        if "torque_spike" in s:
            return (
                ZoneClassification.UNSTABLE,
                "Torque spikes detected -- potential borehole instability "
                "or tight-hole conditions.",
            )

        # OVERPRESSURED (APWD high alone)
        if "apwd_high" in s:
            return (
                ZoneClassification.OVERPRESSURED,
                "Elevated APWD -- possible overpressure. Monitor choke.",
            )

        return (ZoneClassification.NORMAL, "Within baseline bounds.")

    def _merge_adjacent(self, zones: List[ZoneFlag]) -> List[ZoneFlag]:
        """Merge consecutive zones that share the same classification."""
        if len(zones) <= 1:
            return zones

        merged: List[ZoneFlag] = [zones[0]]
        for z in zones[1:]:
            prev = merged[-1]
            if (
                z.classification == prev.classification
                and (z.top_md - prev.bottom_md) < self.cfg.min_zone_length_ft
            ):
                # Extend the previous zone
                merged[-1] = ZoneFlag(
                    top_md=prev.top_md,
                    bottom_md=z.bottom_md,
                    top_tvd=prev.top_tvd,
                    bottom_tvd=z.bottom_tvd,
                    classification=prev.classification,
                    confidence=max(prev.confidence, z.confidence),
                    gamma_avg=(prev.gamma_avg + z.gamma_avg) / 2.0,
                    apwd_avg=(prev.apwd_avg + z.apwd_avg) / 2.0,
                    rop_avg=(prev.rop_avg + z.rop_avg) / 2.0,
                    flow_discrepancy_pct=(
                        prev.flow_discrepancy_pct + z.flow_discrepancy_pct
                    ) / 2.0,
                    choke_trend=(prev.choke_trend + z.choke_trend) / 2.0,
                    notes=prev.notes,
                )
            else:
                merged.append(z)
        return merged

    @staticmethod
    def _linear_slope(x: np.ndarray, y: np.ndarray) -> float:
        """OLS slope of y vs x, ignoring NaNs."""
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() < 2:
            return 0.0
        xm = x[mask]
        ym = y[mask]
        xbar = np.mean(xm)
        denom = np.sum((xm - xbar) ** 2)
        if denom == 0:
            return 0.0
        return float(np.sum((xm - xbar) * (ym - np.mean(ym))) / denom)


# ---------------------------------------------------------------------------
# 3.  Completion Recommendation Generator
# ---------------------------------------------------------------------------

class CompletionAdvisor:
    """Generate stage-level completion recommendations from flagged zones."""

    def __init__(self, config: ZoneConfig) -> None:
        self.cfg = config

    def recommend(self, zones: List[ZoneFlag]) -> List[CompletionRecommendation]:
        """Produce a :class:`CompletionRecommendation` for each zone.

        Rules
        -----
        - **HIGH_POTENTIAL**: standard or increased cluster density, full
          proppant allocation, higher pump rate.
        - **OVERPRESSURED**: standard clusters, standard proppant,
          moderate pump rate.  Note elevated BHP.
        - **DEPLETED**: reduce cluster count, reduce proppant, possible
          skip if confidence is high.
        - **FRACTURED**: standard clusters, add diversion, reduce pump
          rate to limit screenout risk.
        - **UNSTABLE**: reduce cluster count, reduce proppant, note
          borehole condition.
        - **NORMAL**: baseline design.
        """
        recs: List[CompletionRecommendation] = []
        for stage_num, zone in enumerate(zones, start=1):
            rec = self._build_recommendation(stage_num, zone)
            recs.append(rec)
        return recs

    def _build_recommendation(
        self, stage_num: int, zone: ZoneFlag
    ) -> CompletionRecommendation:
        cfg = self.cfg
        cls = zone.classification

        # Start from defaults
        clusters = cfg.default_cluster_count
        spacing = cfg.default_cluster_spacing_ft
        proppant = cfg.default_proppant_per_cluster_lbs
        rate = cfg.default_pump_rate_bpm
        divert = DivertStrategy.NONE
        skip = False
        notes_parts: List[str] = []

        if cls == ZoneClassification.HIGH_POTENTIAL:
            # Increase density for best-quality rock
            clusters = cfg.default_cluster_count + 1
            spacing = zone.length_md / max(clusters + 1, 1)
            proppant = cfg.default_proppant_per_cluster_lbs * 1.15
            rate = cfg.default_pump_rate_bpm * 1.05
            notes_parts.append(
                "High-potential pay: increased cluster density, +15% proppant."
            )

        elif cls == ZoneClassification.OVERPRESSURED:
            # Standard design, flag elevated pressure
            clusters = cfg.default_cluster_count
            spacing = cfg.default_cluster_spacing_ft
            rate = cfg.default_pump_rate_bpm * 0.95
            notes_parts.append(
                "Overpressured zone: standard design, monitor ISIP closely. "
                "Reduced pump rate to manage pressure."
            )

        elif cls == ZoneClassification.DEPLETED:
            if zone.confidence >= 0.6:
                skip = True
                notes_parts.append(
                    "High-confidence depleted zone: recommend skipping stimulation. "
                    "Proppant allocated to higher-value stages."
                )
            else:
                clusters = max(2, cfg.default_cluster_count - 2)
                proppant = cfg.default_proppant_per_cluster_lbs * 0.5
                spacing = zone.length_md / max(clusters + 1, 1)
                notes_parts.append(
                    "Depleted zone: reduced clusters and proppant (-50%). "
                    "Re-evaluate with offset production data."
                )

        elif cls == ZoneClassification.FRACTURED:
            # Diversion is critical; slightly reduce rate to avoid screenout
            divert = DivertStrategy.COMPOSITE
            rate = cfg.default_pump_rate_bpm * 0.90
            proppant = cfg.default_proppant_per_cluster_lbs * 0.9
            notes_parts.append(
                "Fractured zone: composite diversion recommended. "
                "Reduced pump rate (-10%) and proppant (-10%) to manage losses."
            )

        elif cls == ZoneClassification.UNSTABLE:
            clusters = max(3, cfg.default_cluster_count - 1)
            proppant = cfg.default_proppant_per_cluster_lbs * 0.85
            spacing = zone.length_md / max(clusters + 1, 1)
            notes_parts.append(
                "Unstable borehole: reduced clusters and proppant (-15%). "
                "Monitor treating pressures for near-wellbore tortuosity."
            )

        else:  # NORMAL
            spacing = cfg.default_cluster_spacing_ft
            notes_parts.append("Normal zone: baseline completion design.")

        # Place stage boundaries at zone transitions (implied by per-zone recs)
        notes_parts.append(
            f"Stage boundary at {zone.top_md:.0f} ft MD (zone transition)."
        )

        return CompletionRecommendation(
            zone=zone,
            stage_number=stage_num,
            cluster_count=clusters,
            cluster_spacing_ft=spacing,
            proppant_per_cluster_lbs=proppant,
            pump_rate_bpm=rate,
            diversion_strategy=divert,
            skip_stage=skip,
            notes=" ".join(notes_parts),
        )


# ---------------------------------------------------------------------------
# 4.  Zone Summary Report
# ---------------------------------------------------------------------------

@dataclass
class ZoneSummaryReport:
    """Structured output of the zone intelligence analysis."""

    zones: List[ZoneFlag] = field(default_factory=list)
    recommendations: List[CompletionRecommendation] = field(default_factory=list)
    baseline_df: Optional[pd.DataFrame] = None
    summary_stats: Dict[str, float] = field(default_factory=dict)

    def to_dataframe(self) -> pd.DataFrame:
        """Flat DataFrame of flagged zones for display / export."""
        rows = []
        for z in self.zones:
            rows.append({
                "top_md": z.top_md,
                "bottom_md": z.bottom_md,
                "top_tvd": z.top_tvd,
                "bottom_tvd": z.bottom_tvd,
                "length_ft": z.length_md,
                "classification": z.classification.value,
                "confidence": z.confidence,
                "gamma_avg": z.gamma_avg,
                "apwd_avg": z.apwd_avg,
                "rop_avg": z.rop_avg,
                "flow_disc_pct": z.flow_discrepancy_pct,
                "choke_trend": z.choke_trend,
                "notes": z.notes,
            })
        return pd.DataFrame(rows)

    def recommendations_dataframe(self) -> pd.DataFrame:
        """Flat DataFrame of completion recommendations."""
        rows = []
        for r in self.recommendations:
            rows.append({
                "stage": r.stage_number,
                "top_md": r.zone.top_md,
                "bottom_md": r.zone.bottom_md,
                "classification": r.zone.classification.value,
                "clusters": r.cluster_count,
                "spacing_ft": r.cluster_spacing_ft,
                "proppant_per_cluster_lbs": r.proppant_per_cluster_lbs,
                "total_proppant_lbs": r.total_proppant_lbs,
                "pump_rate_bpm": r.pump_rate_bpm,
                "diversion": r.diversion_strategy.value,
                "skip": r.skip_stage,
                "notes": r.notes,
            })
        return pd.DataFrame(rows)

    def text_report(self) -> str:
        """Human-readable multi-line report string."""
        lines: List[str] = []
        lines.append("=" * 72)
        lines.append("  ZONE INTELLIGENCE REPORT")
        lines.append("=" * 72)
        lines.append("")

        # Summary statistics
        total_lateral = self.summary_stats.get("total_lateral_ft", 0)
        lines.append(f"Total lateral analyzed: {total_lateral:.0f} ft")
        lines.append(f"Zones identified: {len(self.zones)}")
        class_counts: Dict[str, int] = {}
        for z in self.zones:
            class_counts[z.classification.value] = (
                class_counts.get(z.classification.value, 0) + 1
            )
        for cls_name, count in sorted(class_counts.items()):
            lines.append(f"  {cls_name}: {count}")
        lines.append("")

        # Zone details
        lines.append("-" * 72)
        lines.append("  FLAGGED ZONES")
        lines.append("-" * 72)
        for z in self.zones:
            lines.append(f"  {z.short_label()}")
            lines.append(f"    Gamma={z.gamma_avg:.1f} API  APWD={z.apwd_avg:.0f} psi  "
                         f"ROP={z.rop_avg:.1f} ft/hr  FlowDisc={z.flow_discrepancy_pct:+.1f}%")
            if z.notes:
                lines.append(f"    {z.notes}")
            lines.append("")

        # Completion recommendations
        lines.append("-" * 72)
        lines.append("  COMPLETION RECOMMENDATIONS")
        lines.append("-" * 72)
        total_proppant = 0.0
        for r in self.recommendations:
            lines.append(f"  {r.summary_line()}")
            if not r.skip_stage:
                total_proppant += r.total_proppant_lbs
        lines.append("")
        lines.append(f"  Total proppant: {total_proppant / 1_000_000:.2f} MM lbs")
        lines.append(f"  Active stages: "
                     f"{sum(1 for r in self.recommendations if not r.skip_stage)}"
                     f" / {len(self.recommendations)}")
        lines.append("=" * 72)

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class ZoneIntelligenceEngine:
    """Top-level orchestrator: baseline -> flag -> recommend -> report.

    Parameters
    ----------
    config : ZoneConfig, optional
        Override default thresholds.
    """

    def __init__(self, config: Optional[ZoneConfig] = None) -> None:
        self.config = config or ZoneConfig()
        self._baseline_calc = BaselineCalculator(window=self.config.baseline_window)
        self._flagger = ZoneFlagAlgorithm(self.config)
        self._advisor = CompletionAdvisor(self.config)

    def analyze(
        self,
        data: DrillingData,
        baseline_data: Optional[DrillingData] = None,
    ) -> ZoneSummaryReport:
        """Run the full zone-intelligence pipeline.

        Parameters
        ----------
        data : DrillingData
            Subject well drilling data (lateral section).
        baseline_data : DrillingData, optional
            Offset well data for baseline computation.

        Returns
        -------
        ZoneSummaryReport
        """
        if data.n_points == 0:
            return ZoneSummaryReport()

        # 1. Compute baselines
        baseline_df = self._baseline_calc.compute(data, offset_data=baseline_data)

        # 2. Flag zones
        zones = self._flagger.flag_zones(data, baseline_df)

        # 3. Generate completion recommendations
        recommendations = self._advisor.recommend(zones)

        # 4. Summary stats
        total_lateral = float(data.depth_md[-1] - data.depth_md[0])
        summary_stats = {
            "total_lateral_ft": total_lateral,
            "n_zones": float(len(zones)),
            "n_high_potential": sum(
                1 for z in zones if z.classification == ZoneClassification.HIGH_POTENTIAL
            ),
            "n_fractured": sum(
                1 for z in zones if z.classification == ZoneClassification.FRACTURED
            ),
            "n_depleted": sum(
                1 for z in zones if z.classification == ZoneClassification.DEPLETED
            ),
            "total_proppant_lbs": sum(
                r.total_proppant_lbs for r in recommendations if not r.skip_stage
            ),
        }

        return ZoneSummaryReport(
            zones=zones,
            recommendations=recommendations,
            baseline_df=baseline_df,
            summary_stats=summary_stats,
        )
