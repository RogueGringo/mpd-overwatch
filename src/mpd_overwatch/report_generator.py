"""MPD Overwatch — Report Generator

Provides 5 export functions consumed by the CLI and (future) dashboard buttons:

  generate_full_report        — Full well HTML report, all EngineeringResults
  generate_subsegment_report  — Depth-range filtered HTML report
  export_current_view         — Single dashboard tab HTML snapshot
  export_channel_data         — CSV channel dump
  export_audit_trail          — Wrap a .log file in styled HTML

All HTML reports:
  * Use dark-theme inline CSS (standalone, no external deps)
  * Include MPD Overwatch branding header
  * Expand tooltip content (method/equation/inputs) as appendix sections
  * Embed a generation timestamp
"""

from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from mpd_overwatch.core.engineering_result import EngineeringResult

# ---------------------------------------------------------------------------
# CSS shared by all HTML exports
# ---------------------------------------------------------------------------

_CSS = """
:root {
    --bg:      #0d1117;
    --surface: #161b22;
    --border:  #30363d;
    --accent:  #58a6ff;
    --green:   #3fb950;
    --amber:   #d29922;
    --red:     #f85149;
    --text:    #c9d1d9;
    --muted:   #8b949e;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    padding: 2rem;
}
h1 { color: var(--accent); font-size: 1.6rem; margin-bottom: 0.25rem; }
h2 { color: var(--accent); font-size: 1.2rem; margin: 1.5rem 0 0.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; }
h3 { color: var(--text); font-size: 1rem; margin: 1rem 0 0.3rem; }
.brand { color: var(--muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
.meta { color: var(--muted); font-size: 0.8rem; }
.tag {
    display: inline-block;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.1rem 0.5rem;
    font-size: 0.75rem;
    margin-left: 0.5rem;
    color: var(--muted);
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0 1rem;
}
th {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 0.4rem 0.75rem;
    text-align: left;
    color: var(--muted);
    font-weight: 600;
    font-size: 0.8rem;
}
td {
    border: 1px solid var(--border);
    padding: 0.4rem 0.75rem;
    vertical-align: top;
}
tr:nth-child(even) td { background: #111820; }
.value { font-weight: 700; color: var(--accent); }
.unit  { color: var(--muted); margin-left: 0.3rem; font-size: 0.85rem; }
.eq    { font-family: 'Courier New', monospace; background: var(--surface); border: 1px solid var(--border); padding: 0.2rem 0.5rem; border-radius: 3px; font-size: 0.85rem; }
.validity { color: var(--green); font-size: 0.8rem; }
.section-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
}
.depth-range {
    background: var(--surface);
    border-left: 3px solid var(--amber);
    padding: 0.5rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.9rem;
}
pre {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1rem;
    font-family: 'Courier New', monospace;
    font-size: 0.82rem;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    color: var(--green);
}
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _esc(s: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(s))


def _prov_tag(prov) -> str:
    return f'<span class="tag">{_esc(prov.value)}</span>'


def _results_table_rows(results: List[EngineeringResult]) -> str:
    """Build <tbody> rows for the results summary table."""
    rows = []
    for r in results:
        validity_cell = (
            f'<span class="validity">{_esc(r.validity)}</span>' if r.validity else ""
        )
        rows.append(
            f"<tr>"
            f"<td>{_esc(r.label)}</td>"
            f"<td><span class='value'>{_esc(str(r.value))}</span>"
            f"<span class='unit'>{_esc(r.unit)}</span></td>"
            f"<td>{_prov_tag(r.provenance)}</td>"
            f"<td>{_esc(r.method.name)}</td>"
            f"<td>{validity_cell}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _appendix_sections(results: List[EngineeringResult]) -> str:
    """Generate appendix HTML with full equation traces for each result."""
    sections = []
    for r in results:
        inputs_rows = ""
        for inp in r.inputs:
            inputs_rows += (
                f"<tr>"
                f"<td>{_esc(inp.name)}</td>"
                f"<td><span class='value'>{_esc(str(inp.value))}</span>"
                f" <span class='unit'>{_esc(inp.unit)}</span></td>"
                f"<td>{_prov_tag(inp.provenance)}</td>"
                f"<td>{_esc(inp.source)}</td>"
                f"</tr>"
            )
        inputs_table = (
            f"<table><thead><tr>"
            f"<th>Parameter</th><th>Value</th><th>Provenance</th><th>Source</th>"
            f"</tr></thead><tbody>{inputs_rows}</tbody></table>"
            if r.inputs else "<p class='meta'>No inputs recorded.</p>"
        )

        extra = ""
        if r.cross_check:
            extra += f"<p><strong>Cross-check:</strong> {_esc(r.cross_check)}</p>"
        if r.sensitivity:
            extra += f"<p><strong>Sensitivity:</strong> {_esc(r.sensitivity)}</p>"
        if r.implication:
            extra += f"<p><strong>Implication:</strong> {_esc(r.implication)}</p>"
        if r.plain_explanation:
            extra += f"<p><strong>Plain English:</strong> {_esc(r.plain_explanation)}</p>"
        if r.threshold_green:
            extra += f"<p><strong>Green:</strong> {_esc(r.threshold_green)}</p>"
        if r.threshold_amber:
            extra += f"<p><strong>Amber:</strong> {_esc(r.threshold_amber)}</p>"
        if r.threshold_red:
            extra += f"<p><strong>Red:</strong> {_esc(r.threshold_red)}</p>"

        sections.append(
            f"<div class='section-box'>"
            f"<h3>{_esc(r.label)}"
            f" <span class='unit'>[{_esc(r.unit)}]</span></h3>"
            f"<p><strong>Method:</strong> {_esc(r.method.name)}"
            f" &mdash; <em>{_esc(r.method.reference)}</em></p>"
            f"<p><strong>Equation:</strong> "
            f"<code class='eq'>{_esc(r.method.equation)}</code></p>"
            f"<p><strong>Validity envelope:</strong> "
            f"<span class='validity'>{_esc(r.validity or 'Not specified')}</span></p>"
            f"<h4 style='margin-top:0.75rem;color:var(--muted);font-size:0.85rem;'>Inputs</h4>"
            f"{inputs_table}"
            f"{extra}"
            f"</div>"
        )
    return "\n".join(sections)


def _html_page(title: str, body_content: str) -> str:
    """Wrap body content in a full, standalone dark-theme HTML page."""
    return (
        f"<!DOCTYPE html>\n"
        f"<html lang='en'>\n"
        f"<head>\n"
        f"<meta charset='UTF-8'>\n"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"<title>{_esc(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        f"</head>\n"
        f"<body>\n"
        f"{body_content}\n"
        f"</body>\n"
        f"</html>"
    )


def _well_header_html(well_header: dict) -> str:
    """Render a simple well info block."""
    if not well_header:
        return ""
    rows = "".join(
        f"<tr><td style='color:var(--muted);'>{_esc(k)}</td>"
        f"<td>{_esc(str(v))}</td></tr>"
        for k, v in well_header.items()
    )
    return (
        f"<table style='width:auto;margin-bottom:1.5rem;'>"
        f"<tbody>{rows}</tbody></table>"
    )


def _results_section(results: List[EngineeringResult]) -> str:
    """Summary table + appendix for a list of EngineeringResults."""
    table_rows = _results_table_rows(results)
    summary = (
        f"<h2>Computed Results</h2>"
        f"<table>"
        f"<thead><tr>"
        f"<th>Parameter</th><th>Value</th><th>Provenance</th>"
        f"<th>Method</th><th>Validity</th>"
        f"</tr></thead>"
        f"<tbody>{table_rows}</tbody>"
        f"</table>"
    )
    appendix = (
        f"<h2>Appendix — Equation Traces</h2>"
        f"{_appendix_sections(results)}"
    )
    return summary + appendix


# ---------------------------------------------------------------------------
# Public API — 5 export functions
# ---------------------------------------------------------------------------

def generate_full_report(
    results: List[EngineeringResult],
    well_header: dict,
    output_path: str,
) -> str:
    """Generate a full-well HTML report covering all provided EngineeringResults.

    Parameters
    ----------
    results:
        List of EngineeringResult objects from engine wrappers.
    well_header:
        Dict of well meta-data (e.g. ``{"well_name": "A-01", "company": "Acme"}``).
    output_path:
        Filesystem path to write the HTML file.

    Returns
    -------
    str
        The HTML string (also written to *output_path*).
    """
    well_name = well_header.get("well_name", "Unknown Well")
    title = f"MPD Overwatch — Full Well Report: {well_name}"

    body = (
        f"<h1>MPD Overwatch</h1>"
        f"<p class='brand'>Managed Pressure Drilling — Full Well Report</p>"
        f"<p class='meta'>Generated: {_timestamp()}</p>"
        f"<h2>Well Information</h2>"
        f"{_well_header_html(well_header)}"
        f"{_results_section(results)}"
    )
    html_str = _html_page(title, body)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html_str)
    return html_str


def generate_subsegment_report(
    results: List[EngineeringResult],
    well_header: dict,
    depth_range: Tuple[float, float],
    output_path: str,
) -> str:
    """Generate a depth-range scoped HTML report.

    Parameters
    ----------
    results:
        Engineering results relevant to the depth segment.
    well_header:
        Well meta-data dict.
    depth_range:
        Tuple ``(top_ft, bottom_ft)`` measured depth.
    output_path:
        Filesystem path for the output HTML.

    Returns
    -------
    str
        The HTML string.
    """
    well_name = well_header.get("well_name", "Unknown Well")
    top_ft, bot_ft = depth_range
    top_fmt = f"{top_ft:,.0f}"
    bot_fmt = f"{bot_ft:,.0f}"
    title = f"MPD Overwatch — Subsegment Report: {top_fmt}–{bot_fmt} ft MD"

    depth_banner = (
        f"<div class='depth-range'>"
        f"<strong>Depth Range:</strong> {top_fmt} ft MD — {bot_fmt} ft MD"
        f"</div>"
    )

    body = (
        f"<h1>MPD Overwatch</h1>"
        f"<p class='brand'>Managed Pressure Drilling — Subsegment Report</p>"
        f"<p class='meta'>Generated: {_timestamp()}</p>"
        f"<h2>Well Information</h2>"
        f"{_well_header_html(well_header)}"
        f"{depth_banner}"
        f"{_results_section(results)}"
    )
    html_str = _html_page(title, body)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html_str)
    return html_str


def export_current_view(
    tab_name: str,
    results: List[EngineeringResult],
    output_path: str,
) -> str:
    """Export a single dashboard tab as a standalone HTML file.

    Parameters
    ----------
    tab_name:
        Name of the tab being exported (e.g. ``"Hydraulics"``).
    results:
        Engineering results displayed in that tab.
    output_path:
        Filesystem path for the output HTML.

    Returns
    -------
    str
        The HTML string.
    """
    title = f"MPD Overwatch — {tab_name} View"

    body = (
        f"<h1>MPD Overwatch</h1>"
        f"<p class='brand'>Managed Pressure Drilling — Tab Export: "
        f"<strong>{_esc(tab_name)}</strong></p>"
        f"<p class='meta'>Generated: {_timestamp()}</p>"
        f"{_results_section(results)}"
    )
    html_str = _html_page(title, body)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html_str)
    return html_str


def export_channel_data(
    channel_map: Dict[str, "np.ndarray"],
    format: str,  # noqa: A002
    output_path: str,
    well_header: Optional[dict] = None,
) -> str:
    """Export channel data to CSV.

    Parameters
    ----------
    channel_map:
        Dict mapping canonical channel names to numpy arrays of equal length.
    format:
        ``"csv"`` (only supported format).
    output_path:
        Destination file path.
    well_header:
        Optional well meta-data (reserved for future use).

    Returns
    -------
    str
        The path of the written file (*output_path*).
    """
    format = format.lower().strip()
    if format != "csv":
        raise ValueError(f"Unsupported format: {format!r}. Only 'csv' is supported.")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    import pandas as pd
    df = pd.DataFrame(channel_map)
    df.to_csv(output_path, index=False)

    return output_path


def export_audit_trail(
    log_filepath: str,
    output_path: str,
) -> str:
    """Wrap a computation log file in a styled, standalone HTML page.

    Parameters
    ----------
    log_filepath:
        Path to the .log file produced by the computation log module.
    output_path:
        Destination HTML path.

    Returns
    -------
    str
        The path of the written HTML file.
    """
    try:
        with open(log_filepath, encoding="utf-8", errors="replace") as fh:
            raw_log = fh.read()
    except FileNotFoundError:
        raw_log = f"[ERROR] Log file not found: {log_filepath}"

    title = "MPD Overwatch — Audit Trail"
    body = (
        f"<h1>MPD Overwatch</h1>"
        f"<p class='brand'>Managed Pressure Drilling — Computation Audit Trail</p>"
        f"<p class='meta'>Generated: {_timestamp()}"
        f" &mdash; Source: {_esc(os.path.basename(log_filepath))}</p>"
        f"<h2>Log Contents</h2>"
        f"<pre>{_esc(raw_log)}</pre>"
    )
    html_str = _html_page(title, body)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html_str)
    return output_path
