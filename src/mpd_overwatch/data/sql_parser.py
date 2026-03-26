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

    def _parse_time_file(
        self, filepath: str
    ) -> Tuple[Dict[str, List[Tuple[datetime, float]]], Dict[str, Dict[str, Any]]]:
        """Parse time-indexed file. Returns (channel_data, witsidcfg).

        channel_data: {wits_id: [(datetime, float_value), ...]}
        witsidcfg: {wits_id: {"description": str, "lc": str, "min": float, "max": float}}
        """
        channel_data: Dict[str, List[Tuple[datetime, float]]] = {}
        witsidcfg: Dict[str, Dict[str, Any]] = {}

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("COPY public.witsidcfg "):
                    col_names = self._parse_copy_columns(line)
                    rows = self._read_copy_block(f, col_names)
                    for row in rows:
                        wid = str(row.get("witsid", "")).strip()
                        if wid:
                            witsidcfg[wid] = row
                elif line.startswith("COPY public.timedata "):
                    self._read_timedata_block(f, channel_data)

        return channel_data, witsidcfg

    def _read_timedata_block(
        self, f, channel_data: Dict[str, List[Tuple[datetime, float]]]
    ) -> None:
        """Read timedata COPY block, pivoting to per-channel time series."""
        for line in f:
            stripped = line.rstrip("\n\r")
            if stripped == "\\.":
                break
            if not stripped:
                continue
            # Format: timestamp\trealtime_csv
            parts = stripped.split("\t", 1)
            if len(parts) < 2:
                continue
            try:
                ts = datetime.strptime(parts[0].strip(), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            realtime = parts[1]
            for token in realtime.split(","):
                eq_pos = token.find("=")
                if eq_pos < 0:
                    continue
                wid = token[:eq_pos].strip()
                val_str = token[eq_pos + 1:].strip()
                try:
                    val = float(val_str)
                except ValueError:
                    val = float("nan")
                if wid not in channel_data:
                    channel_data[wid] = []
                channel_data[wid].append((ts, val))

    def parse_pair(self, depth_file: str, time_file: str) -> WellDatabase:
        """Parse depth + time companion files and merge."""
        db = self._parse_depth_file(depth_file)
        time_data, witsidcfg = self._parse_time_file(time_file)

        for wid, ts_list in time_data.items():
            if not ts_list:
                continue
            times = np.array([t for t, _ in ts_list], dtype="datetime64[s]")
            values = np.array([v for _, v in ts_list], dtype=np.float64)

            # Get depth from WITS 0108 at matching timestamps
            depth_channel = time_data.get("0108", [])
            depth_lookup = {t: v for t, v in depth_channel}
            depths = np.array(
                [depth_lookup.get(t, float("nan")) for t, _ in ts_list],
                dtype=np.float64,
            )
            hides = np.zeros(len(ts_list), dtype=np.int8)

            if wid in db.channels:
                # Merge: concatenate with existing T-table data
                existing = db.channels[wid]
                existing.time = np.concatenate([existing.time, times])
                existing.depth = np.concatenate([existing.depth, depths])
                existing.value = np.concatenate([existing.value, values])
                existing.hide = np.concatenate([existing.hide, hides])
                # Sort by time
                order = np.argsort(existing.time)
                existing.time = existing.time[order]
                existing.depth = existing.depth[order]
                existing.value = existing.value[order]
                existing.hide = existing.hide[order]
            else:
                # Time-only channel
                cfg = witsidcfg.get(wid, {})
                cf = ChannelFrame(
                    wits_id=wid, db_id=0,
                    mnemonic=str(cfg.get("description", wid) or wid),
                    description=str(cfg.get("description", "") or ""),
                    units="", source="TIMEONLY",
                    bias=0.0, scale=1.0, depth_offset=0.0, log_by="time",
                    time=times, depth=depths, value=values, hide=hides,
                    min_y=float(cfg.get("min", 0) or 0),
                    max_y=float(cfg.get("max", 0) or 0),
                    line_color=str(cfg.get("lc", "0000ff") or "0000ff"),
                )
                db.channels[wid] = cf

        return db

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


def scan_for_sql_files(dirpath: str) -> List[Dict[str, Any]]:
    """Scan directory tree for .sql dump files, group by IP."""
    p = Path(dirpath)
    if not p.is_dir():
        return []
    results = []
    seen: set[str] = set()
    for f in p.rglob("*.sql"):
        resolved = str(f.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        stat = f.stat()
        is_time = "_timedata_" in f.name
        results.append({
            "path": resolved,
            "name": f.name,
            "size_mb": stat.st_size / (1024 * 1024),
            "parent": str(f.parent.relative_to(p)) if f.parent != p else ".",
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "is_time_file": is_time,
        })
    return sorted(results, key=lambda r: r["path"])


def ingest(source: str, **kwargs) -> WellDatabase:
    """Universal entry point.

    source can be:
    - File path ending in .sql   -> SQLDumpParser.parse_file()
    - Directory path             -> scan for .sql pairs, parse newest
    """
    parser = SQLDumpParser()
    p = Path(source)

    if p.is_file() and p.suffix.lower() == ".sql":
        if parser._is_time_file(source):
            # Time-only file — parse with limited metadata
            time_data, cfg = parser._parse_time_file(source)
            ip, epoch, _ = parser._detect_source(source)
            ts = datetime.utcfromtimestamp(epoch / 1000).isoformat() + "Z"
            db = WellDatabase(source_ip=ip, dump_epoch=epoch, dump_timestamp=ts)
            # Build minimal ChannelFrames from time data
            depth_channel = time_data.get("0108", [])
            depth_lookup = {t: v for t, v in depth_channel}
            for wid, ts_list in time_data.items():
                if not ts_list:
                    continue
                times = np.array([t for t, _ in ts_list], dtype="datetime64[s]")
                values = np.array([v for _, v in ts_list], dtype=np.float64)
                depths = np.array(
                    [depth_lookup.get(t, float("nan")) for t, _ in ts_list],
                    dtype=np.float64,
                )
                meta = cfg.get(wid, {})
                db.channels[wid] = ChannelFrame(
                    wits_id=wid, db_id=0,
                    mnemonic=str(meta.get("description", wid) or wid),
                    description=str(meta.get("description", "") or ""),
                    units="", source="TIMEONLY",
                    bias=0.0, scale=1.0, depth_offset=0.0, log_by="time",
                    time=times,
                    depth=depths,
                    value=values,
                    hide=np.zeros(len(ts_list), dtype=np.int8),
                )
            return db
        else:
            return parser.parse_file(source)

    if p.is_dir():
        sql_files = scan_for_sql_files(source)
        if not sql_files:
            raise FileNotFoundError(f"No .sql files found in {source}")
        # Group by IP, find depth+time pairs
        depth_files = [f for f in sql_files if not f["is_time_file"]]
        time_files = [f for f in sql_files if f["is_time_file"]]
        if not depth_files:
            # Only time files available
            newest = max(time_files, key=lambda f: f["modified"])
            return ingest(newest["path"])
        # Pick newest depth file
        newest_depth = max(depth_files, key=lambda f: f["modified"])
        # Find matching time file by IP
        try:
            ip, _, _ = parser._detect_source(newest_depth["path"])
        except ValueError:
            return parser.parse_file(newest_depth["path"])
        matching_time = [
            f for f in time_files
            if ip in f["name"]
        ]
        if matching_time:
            return parser.parse_pair(newest_depth["path"], matching_time[0]["path"])
        return parser.parse_file(newest_depth["path"])

    raise ValueError(f"Cannot ingest from: {source}")
