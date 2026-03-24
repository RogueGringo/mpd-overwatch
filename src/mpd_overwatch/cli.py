"""MPD Overwatch - Command Line Interface.

Usage:
    mpd-overwatch serve              Start the dashboard (default port 8050)
    mpd-overwatch vv                 Run V&V benchmark suite
    mpd-overwatch report <las_file>  Generate HTML report from a LAS file
    mpd-overwatch analyze <dir>      Analyze all LAS files in a directory
    mpd-overwatch info               Show platform version and hardware
    mpd-overwatch map <las_file>     Map LAS curve mnemonics using local LLM
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


if __name__ == "__main__":
    sys.exit(main())
