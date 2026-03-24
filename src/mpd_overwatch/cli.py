"""MPD Overwatch - Command Line Interface.

Usage:
    mpd-overwatch serve              Start the dashboard (default port 8050)
    mpd-overwatch vv                 Run V&V benchmark suite
    mpd-overwatch report <las_file>  Generate HTML report from a LAS file
    mpd-overwatch analyze <dir>      Analyze all LAS files in a directory
    mpd-overwatch info               Show platform version and hardware
    mpd-overwatch map <las_file>     Map LAS curve mnemonics using local LLM
    mpd-overwatch pipeline <las_file> Run full analysis pipeline on a LAS file
"""

import argparse
import logging
import sys

from mpd_overwatch import __version__
from mpd_overwatch.logging_config import setup_logging


def main(argv=None):
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mpd-overwatch",
        description="Managed Pressure Drilling computation platform.",
    )
    parser.add_argument(
        "--version", action="version", version=f"mpd-overwatch {__version__}"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity (default: INFO)",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # serve
    p_serve = sub.add_parser("serve", help="Start the dashboard web server")
    p_serve.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    p_serve.add_argument("--no-debug", action="store_true", help="Disable debug mode")

    # vv
    sub.add_parser("vv", help="Run verification & validation benchmarks")

    # report
    p_report = sub.add_parser("report", help="Generate HTML report from LAS file")
    p_report.add_argument("las_file", help="Path to LAS file")
    p_report.add_argument("-o", "--output", default="report.html", help="Output HTML path")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze all LAS files in directory")
    p_analyze.add_argument("directory", help="Directory containing LAS files")

    # info
    sub.add_parser("info", help="Show platform version and detected hardware")

    # map
    p_map = sub.add_parser("map", help="Map LAS curve mnemonics using local LLM")
    p_map.add_argument("las_file", help="Path to LAS file")
    p_map.add_argument("--base-url", default="http://localhost:1234/v1",
                        help="LM Studio API URL (default: http://localhost:1234/v1)")
    p_map.add_argument("--model", default="local-model", help="Model name")
    p_map.add_argument("--no-cache", action="store_true", help="Skip cache lookup")

    # pipeline
    p_pipe = sub.add_parser("pipeline", help="Run full analysis pipeline on a LAS file")
    p_pipe.add_argument("las_file", help="Path to LAS file")
    p_pipe.add_argument("--output-dir", default=".", help="Output directory for .mow and PNGs")
    p_pipe.add_argument("--base-url", default="http://localhost:1234/v1",
                         help="LM Studio API URL")
    p_pipe.add_argument("--model", default="liquid/lfm2.5-1.2b",
                         help="LLM model for channel characterization")
    p_pipe.add_argument("--no-llm", action="store_true",
                         help="Skip LLM characterization, use deterministic mapping only")
    p_pipe.add_argument("--no-plots", action="store_true",
                         help="Skip PNG export")

    args = parser.parse_args(argv)
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "serve":
        return _cmd_serve(args, logger)
    elif args.command == "vv":
        return _cmd_vv(logger)
    elif args.command == "report":
        return _cmd_report(args, logger)
    elif args.command == "analyze":
        return _cmd_analyze(args, logger)
    elif args.command == "info":
        return _cmd_info(logger)
    elif args.command == "map":
        return _cmd_map(args, logger)
    elif args.command == "pipeline":
        return _cmd_pipeline(args, logger)

    return 0


def _cmd_serve(args, logger):
    """Start the Dash dashboard via the launcher."""
    logger.info("Starting MPD Overwatch dashboard on %s:%d", args.host, args.port)
    try:
        from mpd_overwatch.launcher import launch
        log_level = "DEBUG" if not args.no_debug else "INFO"
        launch(port=args.port, host=args.host, log_level=log_level)
    except ImportError as e:
        logger.error("Dashboard dependencies not available: %s", e)
        return 1
    return 0


def _cmd_vv(logger):
    """Run V&V benchmarks."""
    logger.info("Running V&V benchmark suite...")
    try:
        from mpd_overwatch.vv.runner import run_all_benchmarks
        report = run_all_benchmarks()
        print(report.get("summary_text", ""))
        passed = report["total_passed"]
        total = report["total_tests"]
        if passed == total:
            logger.info("V&V PASS: %d/%d benchmarks, Grade %s", passed, total, report["overall_grade"])
            return 0
        else:
            logger.error("V&V FAIL: %d/%d benchmarks passed", passed, total)
            return 1
    except Exception as e:
        logger.error("V&V failed: %s", e)
        return 1


def _cmd_report(args, logger):
    """Generate HTML report from a LAS file using MPD Operations intent."""
    import os
    if not os.path.exists(args.las_file):
        logger.error("File not found: %s", args.las_file)
        return 1

    logger.info("Loading %s", args.las_file)
    try:
        from mpd_overwatch.data.las_parser import LASParser
        from mpd_overwatch.core.engine_wrappers import (
            compute_ecd,
            compute_mse,
        )
        from mpd_overwatch.report_generator import generate_full_report

        parser = LASParser()
        result = parser.parse(args.las_file)
        df = result.to_dataframe()
        logger.info("Loaded %d rows, %d columns", len(df), len(df.columns))

        # Build well header from LAS metadata
        well_header = {
            "well_name": getattr(result, "well_name", None) or os.path.basename(args.las_file),
            "source_file": args.las_file,
        }
        try:
            las_meta = result.metadata if hasattr(result, "metadata") else {}
            for k, v in las_meta.items():
                well_header[k] = v
        except Exception:
            pass

        # Auto-select MPD Operations channels and compute results
        results = []
        channel_map = {col: df[col].values for col in df.columns}

        # ECD: requires mw, afp, tvd columns (try common aliases)
        def _col(candidates):
            for c in candidates:
                if c in channel_map:
                    return c
            return None

        mw_col  = _col(["mw", "mud_weight", "MW", "MUD_WEIGHT"])
        afp_col = _col(["afp", "annular_friction_pressure", "AFP", "ann_pres"])
        tvd_col = _col(["depth_tvd", "tvd", "TVD", "TVDSS"])

        if mw_col and afp_col and tvd_col:
            mw_arr  = channel_map[mw_col]
            afp_arr = channel_map[afp_col]
            tvd_arr = channel_map[tvd_col]
            # Use mid-point of arrays
            mid = len(mw_arr) // 2
            try:
                ecd_res = compute_ecd(
                    float(mw_arr[mid]),
                    float(afp_arr[mid]),
                    float(tvd_arr[mid]),
                )
                results.append(ecd_res)
            except Exception as e:
                logger.debug("ECD computation skipped: %s", e)

        # MSE: requires wob, rpm, torque, rop, bit_size columns
        wob_col    = _col(["wob", "WOB", "weight_on_bit"])
        rpm_col    = _col(["rpm", "RPM", "rotary_speed"])
        torque_col = _col(["torque", "TORQUE", "rot_torque"])
        rop_col    = _col(["rop", "ROP", "rate_of_penetration"])
        bs_col     = _col(["bit_size", "BS", "BIT_SIZE", "bit_diameter"])

        if wob_col and rpm_col and torque_col and rop_col and bs_col:
            mid = len(channel_map[wob_col]) // 2
            try:
                mse_res = compute_mse(
                    float(channel_map[wob_col][mid]),
                    float(channel_map[rpm_col][mid]),
                    float(channel_map[torque_col][mid]),
                    float(channel_map[rop_col][mid]),
                    float(channel_map[bs_col][mid]),
                )
                results.append(mse_res)
            except Exception as e:
                logger.debug("MSE computation skipped: %s", e)

        logger.info("Computed %d engineering results", len(results))

        html_str = generate_full_report(
            results=results,
            well_header=well_header,
            output_path=args.output,
        )
        print(f"Report written: {args.output}")
        print(f"  Well: {well_header['well_name']}")
        print(f"  Data points: {len(df)}, columns: {len(df.columns)}")
        print(f"  Engineering results: {len(results)}")
    except Exception as e:
        logger.error("Failed to process %s: %s", args.las_file, e)
        return 1
    return 0


def _cmd_analyze(args, logger):
    """Batch-analyze all LAS files in a directory; generate one HTML report per file."""
    import os
    import glob
    if not os.path.isdir(args.directory):
        logger.error("Directory not found: %s", args.directory)
        return 1

    las_files = glob.glob(os.path.join(args.directory, "**", "*.las"), recursive=True)
    las_files += glob.glob(os.path.join(args.directory, "**", "*.LAS"), recursive=True)
    las_files = sorted(set(las_files))
    logger.info("Found %d LAS files in %s", len(las_files), args.directory)

    from mpd_overwatch.data.las_parser import LASParser
    from mpd_overwatch.core.engine_wrappers import compute_ecd, compute_mse
    from mpd_overwatch.report_generator import generate_full_report

    parser = LASParser()
    loaded = 0
    reports = 0

    for f in las_files:
        try:
            result = parser.parse(f)
            df = result.to_dataframe()
            if len(df) <= 5:
                continue
            loaded += 1
            print(f"  {os.path.basename(f)}: {len(df)} rows, {len(df.columns)} cols")

            # Build well header
            stem = os.path.splitext(os.path.basename(f))[0]
            well_header = {
                "well_name": getattr(result, "well_name", None) or stem,
                "source_file": f,
            }

            # Auto-compute MPD operations results
            eng_results = []
            channel_map = {col: df[col].values for col in df.columns}

            def _col(candidates):
                for c in candidates:
                    if c in channel_map:
                        return c
                return None

            mw_col  = _col(["mw", "mud_weight", "MW", "MUD_WEIGHT"])
            afp_col = _col(["afp", "annular_friction_pressure", "AFP", "ann_pres"])
            tvd_col = _col(["depth_tvd", "tvd", "TVD", "TVDSS"])

            if mw_col and afp_col and tvd_col:
                mid = len(channel_map[mw_col]) // 2
                try:
                    eng_results.append(compute_ecd(
                        float(channel_map[mw_col][mid]),
                        float(channel_map[afp_col][mid]),
                        float(channel_map[tvd_col][mid]),
                    ))
                except Exception as e:
                    logger.debug("ECD skipped for %s: %s", stem, e)

            wob_col    = _col(["wob", "WOB", "weight_on_bit"])
            rpm_col    = _col(["rpm", "RPM", "rotary_speed"])
            torque_col = _col(["torque", "TORQUE", "rot_torque"])
            rop_col    = _col(["rop", "ROP", "rate_of_penetration"])
            bs_col     = _col(["bit_size", "BS", "BIT_SIZE", "bit_diameter"])

            if wob_col and rpm_col and torque_col and rop_col and bs_col:
                mid = len(channel_map[wob_col]) // 2
                try:
                    eng_results.append(compute_mse(
                        float(channel_map[wob_col][mid]),
                        float(channel_map[rpm_col][mid]),
                        float(channel_map[torque_col][mid]),
                        float(channel_map[rop_col][mid]),
                        float(channel_map[bs_col][mid]),
                    ))
                except Exception as e:
                    logger.debug("MSE skipped for %s: %s", stem, e)

            out_html = os.path.join(args.directory, f"{stem}_report.html")
            generate_full_report(
                results=eng_results,
                well_header=well_header,
                output_path=out_html,
            )
            reports += 1
            logger.info("Report: %s (%d results)", out_html, len(eng_results))

        except Exception as e:
            logger.debug("Failed to load %s: %s", f, e)

    print(f"\nLoaded {loaded}/{len(las_files)} files, generated {reports} HTML reports.")
    return 0


def _cmd_info(logger):
    """Show platform info, hardware, GPU capabilities and channel budget."""
    print(f"MPD Overwatch v{__version__}")
    print()

    # Hardware / compute backend
    try:
        from mpd_overwatch.pointcloud.hardware import detect_compute_backend
        hw = detect_compute_backend()
        print(f"Compute backend: {hw['backend']}")
        if hw.get("gpu_name"):
            print(f"GPU:             {hw['gpu_name']}")
        if hw.get("gpu_memory_gb"):
            print(f"GPU memory:      {hw['gpu_memory_gb']:.1f} GB")
        if hw.get("cuda_version"):
            print(f"CUDA version:    {hw['cuda_version']}")
        if hw.get("gpu_compute_capability"):
            print(f"Compute cap.:    {hw['gpu_compute_capability']}")
        print(f"CPU cores:       {hw['cpu_cores']}")
        print(f"RAM:             {hw['ram_gb']:.1f} GB")
    except Exception as e:
        print(f"Hardware detection: {e}")

    # Channel budget (from channel registry)
    print()
    try:
        from mpd_overwatch.core.engine_wrappers import (
            compute_ecd, compute_mse, compute_hydrostatic,
            compute_bhp_static, compute_bhp_dynamic, compute_annular_velocity,
            compute_ucs, compute_brittleness, compute_d_exponent,
            compute_eaton_pore_pressure, compute_skin_factor,
            compute_productivity_index,
        )
        wrappers = [
            "compute_ecd", "compute_mse", "compute_hydrostatic",
            "compute_bhp_static", "compute_bhp_dynamic", "compute_annular_velocity",
            "compute_ucs", "compute_brittleness", "compute_d_exponent",
            "compute_eaton_pore_pressure", "compute_skin_factor",
            "compute_productivity_index",
        ]
        print(f"Engine wrappers: {len(wrappers)} available")
        for w in wrappers:
            print(f"  {w}")
    except Exception as e:
        print(f"Engine wrappers: {e}")

    # Channel registry tier summary
    print()
    try:
        from mpd_overwatch.core.abstraction_layers import CHANNEL_REGISTRY
        tier_counts: dict = {}
        for entry in CHANNEL_REGISTRY.values():
            tier = getattr(entry, "tier", "unknown")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        total_channels = sum(tier_counts.values())
        print(f"Channel registry: {total_channels} channels")
        for tier, count in sorted(tier_counts.items(), key=lambda x: str(x[0])):
            print(f"  Tier {tier}: {count} channels")
    except Exception as e:
        print(f"Channel registry: {e}")

    # V&V summary
    print()
    try:
        from mpd_overwatch.vv.runner import run_all_benchmarks
        r = run_all_benchmarks()
        print(f"V&V: {r['total_passed']}/{r['total_tests']} pass, Grade {r['overall_grade']}")
    except Exception as e:
        print(f"V&V: {e}")

    return 0


def _cmd_map(args, logger):
    """Map LAS curve mnemonics using local LLM (LM Studio)."""
    import os
    if not os.path.exists(args.las_file):
        logger.error("File not found: %s", args.las_file)
        return 1

    try:
        from mpd_overwatch.data.llm_mapper import (
            extract_las_sections,
            parse_curve_metadata,
            parse_well_metadata,
            llm_map_channels,
            get_llm_client,
        )
    except ImportError as e:
        logger.error("LLM mapping requires: pip install mpd-overwatch[llm]  (%s)", e)
        return 1

    try:
        from pathlib import Path
        raw_text = Path(args.las_file).read_text(encoding="utf-8", errors="replace")
        well_lines, curve_lines = extract_las_sections(raw_text)

        if not curve_lines:
            logger.error("No ~C (curve) section found in %s", args.las_file)
            return 1

        curve_names, curve_units = parse_curve_metadata(curve_lines)
        well = parse_well_metadata(well_lines)
        service_company = well.get("SRVC", "")
        operator = well.get("COMP", "")

        print(f"File: {os.path.basename(args.las_file)}")
        print(f"Service Company: {service_company or '(unknown)'}")
        print(f"Operator: {operator or '(unknown)'}")
        print(f"Curves: {len(curve_names)}")
        print()

        client = get_llm_client(base_url=args.base_url)
        if client is None:
            return 1

        mapping = llm_map_channels(
            well_lines=well_lines,
            curve_lines=curve_lines,
            curve_units=curve_units,
            service_company=service_company,
            operator=operator,
            client=client,
            model=args.model,
            skip_cache=args.no_cache,
        )

        if not mapping:
            logger.error("LLM mapping failed. Is LM Studio running?")
            return 1

        mapped_count = sum(1 for e in mapping.values() if e.get("canonical"))
        print(f"Mapped: {mapped_count}/{len(mapping)} channels")
        print()
        print(f"{'MNEMONIC':<20} {'CANONICAL':<25} {'CONF':>5}  {'UNIT':<10}")
        print("-" * 65)

        for mnemonic, entry in mapping.items():
            canonical = entry.get("canonical") or "(unmapped)"
            confidence = entry.get("confidence", 0.0)
            unit = curve_units.get(mnemonic, "")
            marker = "+" if entry.get("canonical") else " "
            print(f"{marker} {mnemonic:<18} {canonical:<25} {confidence:>4.0%}  {unit:<10}")

        return 0
    except Exception as exc:
        logger.error("Failed to map %s: %s", args.las_file, exc)
        return 1


def _cmd_pipeline(args, logger):
    """Run full analysis pipeline on a LAS file."""
    import time as _time
    from pathlib import Path

    filepath = args.las_file
    if not Path(filepath).exists():
        logger.error("File not found: %s", filepath)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # --- Register in central data index ---
        from mpd_overwatch.data.data_index import DataIndex
        data_index = DataIndex()
        idx_entry = data_index.register(filepath)
        logger.info("Indexed as %s", idx_entry["file_hash"])

        # --- Layer 1: Ingest ---
        t0 = _time.perf_counter()
        from mpd_overwatch.dashboard.data_store import load_file
        header_info = load_file(filepath)
        ingest_ms = int((_time.perf_counter() - t0) * 1000)

        logger.info("Loaded %s: %d curves, %d rows",
                     header_info["well_name"],
                     header_info["curve_count"],
                     header_info["row_count"])

        from mpd_overwatch.data.analysis_layers import AnalysisLayer, AnalysisChain
        chain = AnalysisChain(
            well_name=header_info.get("well_name", ""),
            metadata={"source": filepath, "operator": header_info.get("company", "")},
        )
        chain.add_layer(AnalysisLayer(
            layer_id="001_ingest",
            layer_type="ingest",
            duration_ms=ingest_ms,
            inputs={"filepath": filepath},
            outputs={
                "curve_count": header_info["curve_count"],
                "row_count": header_info["row_count"],
                "well_name": header_info["well_name"],
            },
            context={"operator": header_info.get("company", "")},
            value_term="Raw Data Captured",
            value_description=(
                f"{header_info['curve_count']} channels, "
                f"{header_info['row_count']} rows ingested from LAS"
            ),
        ))

        # --- Layer 2: Channel Characterization ---
        characterizations = []
        if not args.no_llm:
            t0 = _time.perf_counter()
            try:
                from mpd_overwatch.data.channel_characterizer import characterize_channels
                from mpd_overwatch.dashboard.data_store import (
                    get_curve_names, get_curve_units, get_curve_descriptions,
                )
                curve_names = get_curve_names()
                curve_units = get_curve_units()
                curve_descs = get_curve_descriptions()
                channels = [
                    {"name": n, "unit": curve_units.get(n, ""), "description": curve_descs.get(n, "")}
                    for n in curve_names
                ]
                # Detect index type
                strt_unit = header_info.get("curve_units", {}).get(
                    curve_names[0] if curve_names else "", "")
                index_type = "time" if strt_unit.lower() in ("s", "sec", "min", "hr") else "depth"

                characterizations = characterize_channels(
                    channels, index_type=index_type,
                    base_url=args.base_url, model=args.model,
                )
                char_ms = int((_time.perf_counter() - t0) * 1000)
                logger.info("Characterized %d channels in %.1fs",
                            len(characterizations), char_ms / 1000)

                chain.add_layer(AnalysisLayer(
                    layer_id="002_characterize",
                    layer_type="channel_characterization",
                    depends_on=["001_ingest"],
                    duration_ms=char_ms,
                    inputs={"channel_count": len(channels), "index_type": index_type},
                    outputs={"characterized": len(characterizations)},
                    value_term="Channels Classified",
                    value_description=(
                        f"{len(characterizations)} channels classified by physics domain, "
                        "index geometry, and MPD relevance"
                    ),
                ))
            except Exception as e:
                logger.warning("Channel characterization failed: %s", e)

        # --- Layer 3: Channel Mapping ---
        t0 = _time.perf_counter()
        from mpd_overwatch.dashboard.data_store import get_channel_data, apply_llm_mapping
        channel_data = get_channel_data()

        mapping = None
        if not args.no_llm:
            try:
                mapping = apply_llm_mapping(filepath)
            except Exception:
                pass

        from mpd_overwatch.dashboard.data_store import build_selected_channel_map
        from mpd_overwatch.config import MNEMONIC_MAP

        selections = []
        for name in channel_data:
            canonical = None
            if mapping and name in mapping:
                canonical = mapping[name]
            elif name in MNEMONIC_MAP:
                canonical = MNEMONIC_MAP[name]
            if canonical:
                selections.append({
                    "vendor_mnemonic": name,
                    "canonical": canonical,
                    "selected": True,
                })

        if selections:
            canonical_data = build_selected_channel_map(selections)
        else:
            canonical_data = {}

        map_ms = int((_time.perf_counter() - t0) * 1000)
        chain.add_layer(AnalysisLayer(
            layer_id="003_map",
            layer_type="channel_mapping",
            depends_on=["001_ingest"],
            duration_ms=map_ms,
            inputs={"raw_channels": len(channel_data)},
            outputs={"mapped_channels": len(canonical_data)},
            value_term="Channels Mapped",
            value_description=(
                f"{len(canonical_data)} of {len(channel_data)} channels "
                "mapped to canonical names"
            ),
        ))
        logger.info("Mapped %d / %d channels", len(canonical_data), len(channel_data))

        # --- Layer 4: PointCloud4D ---
        if len(canonical_data) >= 2:
            t0 = _time.perf_counter()
            try:
                from mpd_overwatch.pointcloud.ingestion import ingest_dataframe
                import pandas as pd

                df = pd.DataFrame(canonical_data)
                depth_col = "depth_md" if "depth_md" in df.columns else df.columns[0]
                pc = ingest_dataframe(
                    df, depth_col=depth_col,
                    well_name=header_info.get("well_name", ""),
                    metadata={"source": filepath},
                )
                pc_ms = int((_time.perf_counter() - t0) * 1000)

                chain.add_layer(AnalysisLayer(
                    layer_id="004_pointcloud",
                    layer_type="pointcloud",
                    depends_on=["003_map"],
                    duration_ms=pc_ms,
                    inputs={"channels": len(canonical_data)},
                    outputs={"n_points": pc.n_points, "n_channels": pc.n_channels},
                    value_term="Point Cloud Constructed",
                    value_description=(
                        f"{pc.n_points:,} points across {pc.n_channels} channels "
                        "in normalized 4D space"
                    ),
                ))
                chain.add_array("004_pointcloud", "points", pc.points)

                pc.save(output_dir / "pointcloud")
                logger.info("PointCloud4D: %d points, %d channels", pc.n_points, pc.n_channels)
            except Exception as e:
                logger.warning("PointCloud4D construction failed: %s", e)
                pc = None
        else:
            pc = None
            logger.warning("Too few channels (%d) for point cloud", len(canonical_data))

        # --- PNG Export ---
        if not args.no_plots:
            try:
                from mpd_overwatch.core.plot_factory import (
                    plot_raw_channels,
                    plot_channel_characterization,
                    plot_coherence_log,
                    export_figure_png,
                )
                plots_dir = output_dir / "plots"
                plots_dir.mkdir(parents=True, exist_ok=True)

                if canonical_data:
                    fig = plot_raw_channels(canonical_data)
                    export_figure_png(fig, plots_dir / "01_raw_channels.png")
                    logger.info("Exported 01_raw_channels.png")

                if characterizations:
                    fig = plot_channel_characterization(characterizations)
                    export_figure_png(fig, plots_dir / "02_channel_classification.png")
                    logger.info("Exported 02_channel_classification.png")

            except Exception as e:
                logger.warning("Plot export failed: %s", e)

        # --- Save .mow archive ---
        mow_name = header_info.get("well_name", "analysis").replace(" ", "_")
        mow_path = output_dir / f"{mow_name}.mow"
        chain.save(mow_path)
        logger.info("Saved analysis chain: %s (%d layers)", mow_path, len(chain.layers))

        # --- Summary ---
        print(f"\n{'='*60}")
        print(f"  PIPELINE COMPLETE: {header_info.get('well_name', filepath)}")
        print(f"{'='*60}")
        for layer in chain.layers:
            ms = f" ({layer.duration_ms}ms)" if layer.duration_ms else ""
            print(f"  [{layer.layer_id}] {layer.value_term}{ms}")
        print(f"\n  Archive: {mow_path}")
        if not args.no_plots:
            print(f"  Plots:   {output_dir / 'plots'}/")
        print(f"{'='*60}\n")

        return 0

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
