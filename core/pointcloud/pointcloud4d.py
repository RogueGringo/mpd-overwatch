"""PointCloud4D -- the universal data representation for drilling data.

Every measurement becomes a point in 4-dimensional space:

    P_i = (t_i, z_i, c_i, v_i)

where
    t  = normalised time      [0, 1]
    z  = normalised depth      [0, 1]
    c  = channel index         (integer, treated as categorical)
    v  = normalised value      [0, 1]

The raw physical values are stored in parallel arrays so that the original
data can always be reconstructed losslessly.

This representation turns heterogeneous drilling tables into a single
mathematical object that topological tools (sheaf Laplacians, Vietoris-Rips
complexes, persistent homology) can directly consume.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

from .channel_registry import ChannelRegistry


# ---------------------------------------------------------------------------
# Core data structure
# ---------------------------------------------------------------------------

@dataclass
class PointCloud4D:
    """4-dimensional point cloud representation of drilling data.

    Parameters
    ----------
    points : np.ndarray
        Shape ``(N, 4)`` array with columns ``[t, z, c, v]``.
    raw_values : np.ndarray
        Shape ``(N,)`` -- original physical measurement values.
    raw_times : np.ndarray
        Shape ``(N,)`` -- original timestamps (seconds from epoch).
    raw_depths : np.ndarray
        Shape ``(N,)`` -- original measured depths (ft MD).
    channel_ids : np.ndarray
        Shape ``(N,)`` -- integer channel IDs (same data as ``points[:, 2]``).
    registry : ChannelRegistry
        Channel metadata used for normalisation / denormalisation.
    well_name : str
        Human-readable well identifier.
    metadata : dict
        Arbitrary metadata (file path, operator name, spud date, ...).
    """

    points: np.ndarray
    raw_values: np.ndarray
    raw_times: np.ndarray
    raw_depths: np.ndarray
    channel_ids: np.ndarray
    registry: ChannelRegistry
    well_name: str = ""
    metadata: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        n = self.points.shape[0]
        for name, arr in [
            ("raw_values", self.raw_values),
            ("raw_times", self.raw_times),
            ("raw_depths", self.raw_depths),
            ("channel_ids", self.channel_ids),
        ]:
            if arr.shape[0] != n:
                raise ValueError(
                    f"{name} length ({arr.shape[0]}) does not match "
                    f"points length ({n})"
                )
        if self.points.ndim != 2 or self.points.shape[1] != 4:
            raise ValueError(
                f"points must have shape (N, 4), got {self.points.shape}"
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def n_points(self) -> int:
        """Total number of points in the cloud."""
        return self.points.shape[0]

    @property
    def n_channels(self) -> int:
        """Number of distinct channels present."""
        return len(np.unique(self.channel_ids))

    @property
    def depth_range(self) -> Tuple[float, float]:
        """(min, max) measured depth in physical units (ft)."""
        if self.n_points == 0:
            return (0.0, 0.0)
        return (float(np.nanmin(self.raw_depths)), float(np.nanmax(self.raw_depths)))

    @property
    def time_range(self) -> Tuple[float, float]:
        """(min, max) timestamps in physical units (seconds from epoch)."""
        if self.n_points == 0:
            return (0.0, 0.0)
        return (float(np.nanmin(self.raw_times)), float(np.nanmax(self.raw_times)))

    @property
    def unique_channel_ids(self) -> np.ndarray:
        """Sorted array of unique channel IDs present in the cloud."""
        return np.unique(self.channel_ids)

    # ------------------------------------------------------------------
    # Factory: from DataFrame
    # ------------------------------------------------------------------

    @classmethod
    def from_dataframe(
        cls,
        df: "pd.DataFrame",
        depth_col: str,
        time_col: Optional[str] = None,
        channel_map: Optional[Dict[str, str]] = None,
        registry: Optional[ChannelRegistry] = None,
        well_name: str = "",
        metadata: Optional[dict] = None,
    ) -> "PointCloud4D":
        """Build a PointCloud4D from a wide-format pandas DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            One row per sample; one column per measurement channel.
        depth_col : str
            Column containing measured depth (ft MD).
        time_col : str, optional
            Column containing timestamps.  If ``None``, synthetic
            monotonic time is generated from the row index.
        channel_map : dict, optional
            ``{column_name: canonical_channel_name}``.  Unmapped columns
            are attempted via ``registry.mnemonic_to_channel``.
        registry : ChannelRegistry, optional
            Uses default registry if not provided.
        well_name : str
            Well identifier.
        metadata : dict, optional
            Extra metadata.

        Returns
        -------
        PointCloud4D
        """
        if not _HAS_PANDAS:
            raise ImportError("pandas is required for from_dataframe()")

        if registry is None:
            registry = ChannelRegistry()
        if channel_map is None:
            channel_map = {}
        if metadata is None:
            metadata = {}

        # ---- resolve depths ----
        depths = df[depth_col].values.astype(np.float64)
        depth_min, depth_max = np.nanmin(depths), np.nanmax(depths)
        depth_span = depth_max - depth_min if depth_max > depth_min else 1.0

        # ---- resolve times ----
        if time_col is not None and time_col in df.columns:
            times = df[time_col].values.astype(np.float64)
        else:
            times = np.arange(len(df), dtype=np.float64)
        time_min, time_max = np.nanmin(times), np.nanmax(times)
        time_span = time_max - time_min if time_max > time_min else 1.0

        # ---- identify data columns ----
        skip_cols = {depth_col}
        if time_col is not None:
            skip_cols.add(time_col)

        all_points: List[np.ndarray] = []
        all_raw_values: List[np.ndarray] = []
        all_raw_times: List[np.ndarray] = []
        all_raw_depths: List[np.ndarray] = []
        all_channel_ids: List[np.ndarray] = []

        for col in df.columns:
            if col in skip_cols:
                continue

            # Resolve to canonical channel id
            canonical = channel_map.get(col)
            try:
                if canonical:
                    cid = registry.mnemonic_to_channel(canonical)
                else:
                    cid = registry.mnemonic_to_channel(col)
            except KeyError:
                warnings.warn(
                    f"Column {col!r} could not be mapped to a channel; skipping."
                )
                continue

            values = df[col].values.astype(np.float64)
            valid = ~np.isnan(values)
            n_valid = valid.sum()
            if n_valid == 0:
                continue

            v_raw = values[valid]
            d_raw = depths[valid]
            t_raw = times[valid]

            t_norm = (t_raw - time_min) / time_span
            z_norm = (d_raw - depth_min) / depth_span
            c_arr = np.full(n_valid, cid, dtype=np.float64)
            v_norm = np.array(
                [registry.normalize_value(cid, v) for v in v_raw],
                dtype=np.float64,
            )

            pts = np.column_stack([t_norm, z_norm, c_arr, v_norm])
            all_points.append(pts)
            all_raw_values.append(v_raw)
            all_raw_times.append(t_raw)
            all_raw_depths.append(d_raw)
            all_channel_ids.append(np.full(n_valid, cid, dtype=np.int32))

        if not all_points:
            return cls(
                points=np.empty((0, 4), dtype=np.float64),
                raw_values=np.empty(0, dtype=np.float64),
                raw_times=np.empty(0, dtype=np.float64),
                raw_depths=np.empty(0, dtype=np.float64),
                channel_ids=np.empty(0, dtype=np.int32),
                registry=registry,
                well_name=well_name,
                metadata=metadata,
            )

        return cls(
            points=np.vstack(all_points),
            raw_values=np.concatenate(all_raw_values),
            raw_times=np.concatenate(all_raw_times),
            raw_depths=np.concatenate(all_raw_depths),
            channel_ids=np.concatenate(all_channel_ids),
            registry=registry,
            well_name=well_name,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Reconstruction: to DataFrame
    # ------------------------------------------------------------------

    def to_dataframe(self) -> "pd.DataFrame":
        """Reconstruct a wide-format DataFrame with physical values.

        Returns a DataFrame indexed by ``(time, depth)`` with one column
        per channel (using canonical names).

        Returns
        -------
        pd.DataFrame
        """
        if not _HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")

        import pandas as pd

        records: Dict[Tuple[float, float], Dict[str, float]] = {}
        for i in range(self.n_points):
            key = (float(self.raw_times[i]), float(self.raw_depths[i]))
            cid = int(self.channel_ids[i])
            cname = self.registry.lookup_id(cid).name
            if key not in records:
                records[key] = {"time": key[0], "depth": key[1]}
            records[key][cname] = float(self.raw_values[i])

        df = pd.DataFrame(list(records.values()))
        if "depth" in df.columns:
            df = df.sort_values("depth").reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Slicing
    # ------------------------------------------------------------------

    def _slice(self, mask: np.ndarray) -> "PointCloud4D":
        """Return a new PointCloud4D containing only the points where *mask*
        is True."""
        return PointCloud4D(
            points=self.points[mask].copy(),
            raw_values=self.raw_values[mask].copy(),
            raw_times=self.raw_times[mask].copy(),
            raw_depths=self.raw_depths[mask].copy(),
            channel_ids=self.channel_ids[mask].copy(),
            registry=self.registry,
            well_name=self.well_name,
            metadata=dict(self.metadata),
        )

    def slice_by_depth(self, top_md: float, bottom_md: float) -> "PointCloud4D":
        """Return a sub-cloud restricted to ``[top_md, bottom_md]`` ft MD.

        Parameters
        ----------
        top_md, bottom_md : float
            Depth window in physical units (ft measured depth).

        Returns
        -------
        PointCloud4D
        """
        mask = (self.raw_depths >= top_md) & (self.raw_depths <= bottom_md)
        return self._slice(mask)

    def slice_by_time(self, t0: float, t1: float) -> "PointCloud4D":
        """Return a sub-cloud restricted to ``[t0, t1]`` seconds from epoch.

        Parameters
        ----------
        t0, t1 : float
            Time window in physical units.

        Returns
        -------
        PointCloud4D
        """
        mask = (self.raw_times >= t0) & (self.raw_times <= t1)
        return self._slice(mask)

    def slice_by_channel(
        self, channel_names_or_ids: Sequence[Union[str, int]]
    ) -> "PointCloud4D":
        """Return a sub-cloud restricted to specific channels.

        Parameters
        ----------
        channel_names_or_ids : sequence of str or int
            Channel canonical names or integer IDs.

        Returns
        -------
        PointCloud4D
        """
        ids: set = set()
        for item in channel_names_or_ids:
            if isinstance(item, int):
                ids.add(item)
            else:
                ids.add(self.registry.name_to_id(item))
        mask = np.isin(self.channel_ids, list(ids))
        return self._slice(mask)

    # ------------------------------------------------------------------
    # Channel vector extraction
    # ------------------------------------------------------------------

    def channel_vector_at(
        self, depth: float, time_tolerance: float = np.inf
    ) -> np.ndarray:
        """Return a vector of all channel values at a given depth.

        If multiple time samples exist at that depth, the sample closest
        in time to the median is used unless *time_tolerance* is finite,
        in which case all samples within the tolerance are averaged.

        Parameters
        ----------
        depth : float
            Target measured depth (ft).
        time_tolerance : float
            Maximum time difference (seconds) for sample inclusion.

        Returns
        -------
        np.ndarray
            1-D array of length ``n_channels_in_registry`` with NaN for
            channels not present at this depth.
        """
        unique_ids = sorted(set(int(c) for c in self.registry._channels.keys()))
        vec = np.full(len(unique_ids), np.nan, dtype=np.float64)
        id_to_pos = {cid: idx for idx, cid in enumerate(unique_ids)}

        # Find closest depth row(s)
        depth_diffs = np.abs(self.raw_depths - depth)
        min_diff = np.min(depth_diffs)
        # Accept depths within 0.5 ft of the closest match
        depth_mask = depth_diffs <= min_diff + 0.5

        if not np.any(depth_mask):
            return vec

        subset_cids = self.channel_ids[depth_mask]
        subset_vals = self.raw_values[depth_mask]
        subset_times = self.raw_times[depth_mask]

        if np.isfinite(time_tolerance):
            median_time = np.median(subset_times)
            time_mask = np.abs(subset_times - median_time) <= time_tolerance
            subset_cids = subset_cids[time_mask]
            subset_vals = subset_vals[time_mask]

        for cid in np.unique(subset_cids):
            pos = id_to_pos.get(int(cid))
            if pos is not None:
                vals = subset_vals[subset_cids == cid]
                vec[pos] = np.nanmean(vals)

        return vec

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def channel_stats(self) -> Dict[str, Dict[str, float]]:
        """Per-channel summary statistics over physical (raw) values.

        Returns
        -------
        dict
            ``{channel_name: {"mean", "std", "min", "max", "n_points"}}``.
        """
        stats: Dict[str, Dict[str, float]] = {}
        for cid in self.unique_channel_ids:
            mask = self.channel_ids == cid
            vals = self.raw_values[mask]
            cname = self.registry.lookup_id(int(cid)).name
            stats[cname] = {
                "mean": float(np.nanmean(vals)),
                "std": float(np.nanstd(vals)),
                "min": float(np.nanmin(vals)),
                "max": float(np.nanmax(vals)),
                "n_points": int(mask.sum()),
            }
        return stats

    def correlation_matrix(self) -> np.ndarray:
        """Pearson correlation matrix between channels.

        Channels are aligned by depth (nearest-neighbour interpolation).
        Returns an ``(n_channels, n_channels)`` array; channel order
        follows ``unique_channel_ids``.

        Returns
        -------
        np.ndarray
            Shape ``(n_channels, n_channels)``.
        """
        uids = list(self.unique_channel_ids)
        n_ch = len(uids)
        if n_ch < 2:
            return np.ones((n_ch, n_ch), dtype=np.float64)

        # Build per-channel depth->value arrays and align on common depth grid
        channel_depths: Dict[int, np.ndarray] = {}
        channel_values: Dict[int, np.ndarray] = {}
        for cid in uids:
            mask = self.channel_ids == cid
            sort_idx = np.argsort(self.raw_depths[mask])
            channel_depths[cid] = self.raw_depths[mask][sort_idx]
            channel_values[cid] = self.raw_values[mask][sort_idx]

        # Common depth grid: union of all unique depths
        all_depths = np.unique(self.raw_depths)

        # Interpolate each channel onto the common grid
        interp_matrix = np.full((len(all_depths), n_ch), np.nan, dtype=np.float64)
        for j, cid in enumerate(uids):
            interp_matrix[:, j] = np.interp(
                all_depths,
                channel_depths[cid],
                channel_values[cid],
                left=np.nan,
                right=np.nan,
            )

        # Drop rows with any NaN
        valid_rows = ~np.any(np.isnan(interp_matrix), axis=1)
        clean = interp_matrix[valid_rows]

        if clean.shape[0] < 2:
            return np.full((n_ch, n_ch), np.nan, dtype=np.float64)

        return np.corrcoef(clean, rowvar=False)

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        dr = self.depth_range
        channels = []
        for cid in sorted(self.unique_channel_ids):
            try:
                channels.append(self.registry.lookup_id(int(cid)).name)
            except KeyError:
                channels.append(f"ch_{cid}")
        ch_str = ", ".join(channels[:6])
        if len(channels) > 6:
            ch_str += f", ... ({len(channels)} total)"
        return (
            f"PointCloud4D("
            f"well={self.well_name!r}, "
            f"n_points={self.n_points:,}, "
            f"n_channels={self.n_channels}, "
            f"depth=[{dr[0]:.1f}, {dr[1]:.1f}] ft, "
            f"channels=[{ch_str}]"
            f")"
        )

    def __len__(self) -> int:
        return self.n_points
