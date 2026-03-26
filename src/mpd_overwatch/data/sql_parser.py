"""SQL EDR dump file parser — streaming, line-by-line, no SQL engine."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from mpd_overwatch.data.sql_models import ChannelFrame, ChannelSummary, WellDatabase

logger = logging.getLogger(__name__)

# Filename patterns
_DEPTH_PATTERN = re.compile(
    r"^([\d.]+)_(\d+)\.sql$"
)
_TIME_PATTERN = re.compile(
    r"^([\d.]+)_timedata_(\d+)\.sql$"
)


class SQLDumpParser:
    """Parse PostgreSQL pg_dump files from UMS EDR systems."""

    def _detect_source(self, filepath: str) -> Tuple[str, int, bool]:
        """Extract source IP, epoch_ms, and is_time_file from filename."""
        name = Path(filepath).name
        m = _TIME_PATTERN.match(name)
        if m:
            return m.group(1), int(m.group(2)), True
        m = _DEPTH_PATTERN.match(name)
        if m:
            return m.group(1), int(m.group(2)), False
        raise ValueError(f"Cannot parse source from filename: {name}")

    def _is_time_file(self, filepath: str) -> bool:
        return "_timedata_" in Path(filepath).name

    def parse_file(self, filepath: str) -> WellDatabase:
        """Auto-detect file type and parse accordingly."""
        if self._is_time_file(filepath):
            raise NotImplementedError("Time files require parse_pair()")
        return self._parse_depth_file(filepath)

    def _parse_depth_file(self, filepath: str) -> WellDatabase:
        """Parse depth-indexed file with idtable + T-tables."""
        ip, epoch, _ = self._detect_source(filepath)
        ts = datetime.utcfromtimestamp(epoch / 1000).isoformat() + "Z"

        idtable_rows: List[Dict[str, Any]] = []
        ttable_data: Dict[str, Tuple[np.ndarray, ...]] = {}  # wits_id -> arrays

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # Detect COPY blocks
                if line.startswith("COPY public.idtable "):
                    col_names = self._parse_copy_columns(line)
                    idtable_rows = self._read_copy_block(f, col_names)
                elif line.startswith('COPY public."T'):
                    wits_id = self._extract_ttable_witsid(line)
                    if wits_id:
                        ttable_data[wits_id] = self._read_ttable_block(f)

        # Build idtable lookup: witsid -> metadata dict
        id_lookup: Dict[str, Dict[str, Any]] = {}
        for row in idtable_rows:
            wid = str(row.get("witsid", "")).strip()
            if wid:
                id_lookup[wid] = row

        # Build ChannelFrames
        channels: Dict[str, ChannelFrame] = {}
        computed: Dict[str, ChannelFrame] = {}
        for wid, (times, depths, values, hides) in ttable_data.items():
            if len(values) == 0:
                continue
            meta = id_lookup.get(wid, {})
            cf = self._build_channel_frame(wid, meta, times, depths, values, hides)
            # Separate computed (witsid >= 9001) from raw
            if wid.isdigit() and int(wid) >= 9001:
                computed[wid] = cf
            else:
                channels[wid] = cf

        return WellDatabase(
            source_ip=ip, dump_epoch=epoch, dump_timestamp=ts,
            channels=channels, computed=computed,
        )

    def _parse_copy_columns(self, copy_line: str) -> List[str]:
        """Extract column names from COPY ... (col1, col2, ...) FROM stdin;"""
        m = re.search(r"\(([^)]+)\)", copy_line)
        if not m:
            return []
        return [c.strip() for c in m.group(1).split(",")]

    def _read_copy_block(self, f, col_names: List[str]) -> List[Dict[str, Any]]:
        """Read tab-separated rows until \\. terminator."""
        rows = []
        for line in f:
            stripped = line.rstrip("\n\r")
            if stripped == "\\.":
                break
            if not stripped:
                continue
            parts = stripped.split("\t")
            row = {}
            for i, name in enumerate(col_names):
                if i < len(parts):
                    val = parts[i]
                    row[name] = val if val != "\\N" else None
                else:
                    row[name] = None
            rows.append(row)
        return rows

    def _extract_ttable_witsid(self, copy_line: str) -> Optional[str]:
        """Extract WITS ID from COPY public."T0121" ..."""
        m = re.search(r'"T(\d+)"', copy_line)
        return m.group(1) if m else None

    def _read_ttable_block(self, f) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Read T-table COPY block into arrays: (time, depth, value, hide)."""
        times, depths, values, hides = [], [], [], []
        for line in f:
            stripped = line.rstrip("\n\r")
            if stripped == "\\.":
                break
            if not stripped:
                continue
            parts = stripped.split("\t")
            if len(parts) < 5:
                continue
            # parts: id, timedate, depth, value, hide
            try:
                t = np.datetime64(parts[1]) if parts[1] != "\\N" else np.datetime64("NaT")
            except ValueError:
                t = np.datetime64("NaT")
            try:
                d = float(parts[2]) if parts[2] != "\\N" else float("nan")
            except ValueError:
                d = float("nan")
            try:
                v = float(parts[3]) if parts[3] != "\\N" else float("nan")
            except ValueError:
                v = float("nan")  # non-numeric text value
            try:
                h = int(parts[4]) if parts[4] != "\\N" else 0
            except ValueError:
                h = 0
            times.append(t)
            depths.append(d)
            values.append(v)
            hides.append(h)

        return (
            np.array(times, dtype="datetime64[s]"),
            np.array(depths, dtype=np.float64),
            np.array(values, dtype=np.float64),
            np.array(hides, dtype=np.int8),
        )

    @staticmethod
    def _normalize_log_by(raw: Optional[str]) -> str:
        """Normalize idtable.logby to 'depth', 'time', or 'unknown'."""
        if raw is None:
            return "unknown"
        raw = raw.strip().lower()
        if raw == "depth":
            return "depth"
        if raw == "time":
            return "time"
        if raw == "0" or raw == "":
            return "unknown"
        # Positive numeric values -> depth (sample interval)
        try:
            val = float(raw)
            return "depth" if val > 0 else "unknown"
        except ValueError:
            return "unknown"

    @staticmethod
    def _parse_changelog(raw: Optional[str]) -> Dict[int, Dict[str, float]]:
        """Parse idtable.changelog JSON into {epoch: {bias, scale, depthoffset}}."""
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        result = {}
        for key, entry in data.items():
            try:
                epoch = int(key)
            except ValueError:
                continue
            cal = {}
            for field_name in ("bias", "scale", "depthoffset"):
                if field_name in entry:
                    try:
                        cal[field_name] = float(entry[field_name])
                    except (ValueError, TypeError):
                        pass
            if cal:
                result[epoch] = cal
        return result

    def _build_channel_frame(
        self, wits_id: str, meta: Dict[str, Any],
        times: np.ndarray, depths: np.ndarray,
        values: np.ndarray, hides: np.ndarray,
    ) -> ChannelFrame:
        """Build ChannelFrame from idtable metadata + T-table arrays."""
        def _float(val, default=0.0):
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def _int(val, default=0):
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        return ChannelFrame(
            wits_id=wits_id,
            db_id=_int(meta.get("id")),
            mnemonic=str(meta.get("mnemonic", wits_id) or wits_id).strip(),
            description=str(meta.get("description", "") or "").strip(),
            units=str(meta.get("units", "") or "").strip(),
            source=str(meta.get("source", "WITS") or "WITS").strip(),
            bias=_float(meta.get("bias")),
            scale=_float(meta.get("scale"), 1.0),
            depth_offset=_float(meta.get("depthoffset")),
            log_by=self._normalize_log_by(meta.get("logby")),
            changelog=self._parse_changelog(meta.get("changelog")),
            time=times,
            depth=depths,
            value=values,
            hide=hides,
            min_y=_float(meta.get("miny")),
            max_y=_float(meta.get("maxy")),
            dp=_int(meta.get("dp"), 2),
            line_color=str(meta.get("linecolor", "0000ff") or "0000ff"),
        )
