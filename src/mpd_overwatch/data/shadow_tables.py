"""Shadow table write-back — persist computed results as T-tables."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np

from mpd_overwatch.data.sql_models import ChannelFrame


COMPUTED_CHANNELS: Dict[str, Dict] = {
    "ecd_computed":       {"witsid_base": 9001, "units": "ppg",   "description": "Equivalent Circulating Density"},
    "pore_pressure_grad": {"witsid_base": 9002, "units": "ppg",   "description": "Pore Pressure Gradient"},
    "frac_gradient":      {"witsid_base": 9003, "units": "ppg",   "description": "Fracture Gradient"},
    "mse":                {"witsid_base": 9004, "units": "psi",   "description": "Mechanical Specific Energy"},
    "fd_index":           {"witsid_base": 9005, "units": "ratio", "description": "Formation Damage Index"},
    "swab_surge":         {"witsid_base": 9006, "units": "ppg",   "description": "Swab/Surge Pressure"},
    "hole_cleaning":      {"witsid_base": 9007, "units": "ratio", "description": "Hole Cleaning Efficiency"},
}


def build_computed_channel(
    name: str,
    times: np.ndarray,
    depths: np.ndarray,
    values: np.ndarray,
) -> ChannelFrame:
    """Build a ChannelFrame for a computed result."""
    spec = COMPUTED_CHANNELS[name]
    witsid = str(spec["witsid_base"])
    return ChannelFrame(
        wits_id=witsid,
        db_id=0,
        mnemonic=name.upper(),
        description=spec["description"],
        units=spec["units"],
        source="COMPUTED",
        bias=0.0,
        scale=1.0,
        depth_offset=0.0,
        log_by="depth",
        time=times,
        depth=depths,
        value=values,
        hide=np.zeros(len(values), dtype=np.int8),
    )


def write_shadow_sql(
    computed_channels: Dict[str, ChannelFrame],
    output_path: Path,
) -> None:
    """Write computed channels as a pg_dump-compatible .sql file."""
    lines = [
        "-- MPD Overwatch computed channels",
        "-- Can be loaded with: psql -f <this_file> <database>",
        "",
    ]

    for name, cf in computed_channels.items():
        table_name = f"T{cf.wits_id}"

        # CREATE TABLE
        lines.append(f'CREATE TABLE IF NOT EXISTS public."{table_name}" (')
        lines.append("    id integer NOT NULL,")
        lines.append("    timedate timestamp without time zone,")
        lines.append("    depth double precision,")
        lines.append("    value text,")
        lines.append("    hide smallint")
        lines.append(");")
        lines.append("")

        # INSERT INTO idtable
        lines.append(
            f"INSERT INTO public.idtable (witsid, mnemonic, description, units, "
            f"source, bias, scale, depthoffset, logby) VALUES ("
            f"'{cf.wits_id}', '{cf.mnemonic}', '{cf.description}', "
            f"'{cf.units}', 'COMPUTED', 0, 1, 0, 'depth');"
        )
        lines.append("")

        # COPY data
        lines.append(
            f'COPY public."{table_name}" (id, timedate, depth, value, hide) FROM stdin;'
        )
        for i in range(cf.n_points):
            t = str(cf.time[i]).replace("T", " ")
            d = f"{cf.depth[i]:.6f}"
            v = f"{cf.value[i]}"
            h = str(cf.hide[i])
            lines.append(f"{i+1}\t{t}\t{d}\t{v}\t{h}")
        lines.append("\\.")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
