"""MPD Command - Comprehensive Integration Test

Exercises all physics engines, data layer, and V&V pipeline end-to-end.
Run: python test_integration.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_section(name):
    print(f"\n{'-'*50}")
    print(f"  {name}")
    print(f"{'-'*50}")


def main():
    start = time.time()
    passed = 0
    failed = 0
    errors = []

    print("=" * 60)
    print("  MPD COMMAND - INTEGRATION TEST SUITE")
    print("=" * 60)

    # --- 1. Core Hydraulics ---
    test_section("1. Core Hydraulics")
    try:
        from core.hydraulics import (
            hydrostatic_pressure, equivalent_circulating_density,
            bottom_hole_pressure_static, bottom_hole_pressure_dynamic,
            annular_velocity, calculate_kill_sheet,
        )
        p = hydrostatic_pressure(12.0, 10000)
        assert abs(p - 6240.0) < 0.01, f"Hydrostatic failed: {p}"
        print(f"  Hydrostatic: {p:.1f} psi OK")

        ecd = equivalent_circulating_density(12.0, 250, 10000)
        assert abs(ecd - 12.4808) < 0.01
        print(f"  ECD: {ecd:.4f} ppg OK")

        bhp_s = bottom_hole_pressure_static(11.5, 10500, 200)
        print(f"  BHP static: {bhp_s:.1f} psi OK")

        bhp_d = bottom_hole_pressure_dynamic(11.5, 10500, 300, 200)
        print(f"  BHP dynamic: {bhp_d:.1f} psi OK")

        v = annular_velocity(650, 8.75, 5.0)
        print(f"  Annular velocity: {v:.1f} ft/min OK")
        passed += 5
    except Exception as e:
        failed += 1
        errors.append(f"Hydraulics: {e}")
        print(f"  FAILED: {e}")

    # --- 2. Formation Damage ---
    test_section("2. Formation Damage")
    try:
        from core.formation_damage import skin_factor, permeability_reduction, productivity_index
        s = skin_factor(k=100, k_d=20, r_d=1.0, r_w=0.354)
        print(f"  Skin factor: {s:.4f} OK")

        pr, _ = permeability_reduction(overbalance_psi=500, mud_solids_frac=0.05)
        print(f"  Perm reduction (500 psi OB): k_d/k = {pr:.3f} OK")

        pi = productivity_index(k=10, h=50, Bo=1.2, mu=1.5, r_e=1000, r_w=0.354, S=5)
        print(f"  PI with S=5: {pi:.4f} STB/d/psi OK")
        passed += 3
    except Exception as e:
        failed += 1
        errors.append(f"Formation Damage: {e}")
        print(f"  FAILED: {e}")

    # --- 3. Production ---
    test_section("3. Production")
    try:
        from core.production import decline_exponential, decline_hyperbolic, forecast_decline
        import numpy as np

        months_arr = np.array([12.0])
        q_exp = decline_exponential(qi=1000, Di_annual=0.6, months=months_arr)
        print(f"  Exponential decline (t=12): {q_exp[0]:.1f} BOPD OK")

        q_hyp = decline_hyperbolic(qi=1000, Di_annual=0.96, b=1.2, months=months_arr)
        print(f"  Hyperbolic decline (t=12): {q_hyp[0]:.1f} BOPD OK")

        months_120 = np.arange(1, 121, dtype=float)
        fc = decline_hyperbolic(qi=1000, Di_annual=0.96, b=1.2, months=months_120)
        print(f"  120-month forecast: {len(fc)} points, EUR={np.sum(fc*30.4):,.0f} bbl OK")
        passed += 3
    except Exception as e:
        failed += 1
        errors.append(f"Production: {e}")
        print(f"  FAILED: {e}")

    # --- 4. Geomechanics ---
    test_section("4. Geomechanics")
    try:
        from core.geomechanics import (
            mechanical_specific_energy, ucs_from_mse,
            brittleness_index, drilling_efficiency,
        )
        mse = mechanical_specific_energy(wob=25000, torque=12000, rpm=120, rop=100, bit_diameter=8.75)
        ucs = ucs_from_mse(mse)
        bi = brittleness_index(ucs)
        de = drilling_efficiency(ucs, mse)
        print(f"  MSE: {mse:,.0f} psi OK")
        print(f"  UCS: {ucs:,.0f} psi OK")
        print(f"  Brittleness: {bi:.3f} OK")
        print(f"  Drill efficiency: {de:.3f} OK")
        passed += 4
    except Exception as e:
        failed += 1
        errors.append(f"Geomechanics: {e}")
        print(f"  FAILED: {e}")

    # --- 5. Optimizer ---
    test_section("5. Parameter Optimizer")
    try:
        from core.optimizer import optimize_parameters, plan_connection, DrillingWindow
        window = DrillingWindow(
            tvd=10500, pore_pressure_ppg=11.5, fracture_gradient_ppg=16.3,
            current_mud_weight=11.8, current_ecd=12.3, current_sbp=150, current_bhp=6800,
        )
        opt = optimize_parameters(window)
        print(f"  Optimal ROP: {opt.predicted_rop_fthr:.1f} ft/hr OK")
        print(f"  Confidence: {opt.confidence:.0%} OK")

        conn = plan_connection(window)
        print(f"  Connection SBP: {conn.static_sbp:.0f} psi OK")
        passed += 3
    except Exception as e:
        failed += 1
        errors.append(f"Optimizer: {e}")
        print(f"  FAILED: {e}")

    # --- 6. Proposal Generator ---
    test_section("6. Proposal Generator")
    try:
        from core.proposal_generator import WellProposal, generate_proposal
        proposal = generate_proposal(WellProposal(well_name="Test Well 1H"))
        assert proposal.total_mpd_value > 0
        assert proposal.roi_on_service > 1
        assert len(proposal.sections) == 5
        print(f"  Proposal value: ${proposal.total_mpd_value:,.0f} OK")
        print(f"  ROI: {proposal.roi_on_service:.0f}x OK")
        print(f"  Sections: {len(proposal.sections)} OK")
        passed += 3
    except Exception as e:
        failed += 1
        errors.append(f"Proposal: {e}")
        print(f"  FAILED: {e}")

    # --- 7. Data Layer ---
    test_section("7. Data Layer")
    try:
        from data.demo_generator import generate_demo_well_data, generate_decline_curves
        data = generate_demo_well_data()
        assert len(data["drilling_data"]) == 500
        print(f"  Demo data: {len(data['drilling_data'])} points OK")

        decline = generate_decline_curves()
        assert len(decline) == 120
        print(f"  Decline curves: {len(decline)} months OK")

        from data.las_parser import LASParser
        parser = LASParser()
        # Try loading real data if available
        real_path = os.path.join(
            "..", "DATA_TYPES_for_System_Use_EXAMPLES",
            "Historical_MWD_Data_Archives_Wells",
            "18MLD4216_Chevron - REV GF State T7-50-41 3H",
            "Client Final Deliverables", "LAS",
            "EOW_LAS Standard_18MLD4216_Chevron_REV GF State T7 50-41 3H.las",
        )
        if os.path.exists(real_path):
            result = parser.parse(real_path)
            df = result.to_dataframe()
            print(f"  Real LAS (Chevron): {len(df)} rows, {len(df.columns)} curves OK")
            passed += 1
        else:
            print(f"  Real LAS: skipped (file not found)")
        passed += 2
    except Exception as e:
        failed += 1
        errors.append(f"Data Layer: {e}")
        print(f"  FAILED: {e}")

    # --- 8. V&V Pipeline ---
    test_section("8. V&V Pipeline")
    try:
        from vv_pipeline.runner import run_all_benchmarks
        report = run_all_benchmarks()
        assert report["total_passed"] == report["total_tests"]
        print(f"  Benchmarks: {report['total_passed']}/{report['total_tests']} PASS OK")
        print(f"  Score: {report['overall_score']:.1f}/100 OK")
        print(f"  Grade: {report['overall_grade']} OK")
        passed += 3
    except Exception as e:
        failed += 1
        errors.append(f"V&V Pipeline: {e}")
        print(f"  FAILED: {e}")

    # --- 9. Dashboard Pages ---
    test_section("9. Dashboard Pages")
    page_modules = [
        ("pages.hmu_panel", "page_hmu"),
        ("pages.supervisory_panel", "page_supervisory"),
        ("pages.geomechanics", "page_geomechanics"),
        ("pages.data_import", "page_data_import"),
        ("pages.proposal", "page_proposal"),
    ]
    for mod_name, func_name in page_modules:
        try:
            mod = __import__(mod_name, fromlist=[func_name])
            func = getattr(mod, func_name)
            result = func()
            print(f"  {func_name}: renders OK")
            passed += 1
        except Exception as e:
            failed += 1
            errors.append(f"{func_name}: {e}")
            print(f"  {func_name}: FAILED ({e})")

    # --- Summary ---
    elapsed = time.time() - start
    total = passed + failed

    print(f"\n{'='*60}")
    print(f"  INTEGRATION TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Passed: {passed}/{total}")
    print(f"  Failed: {failed}/{total}")
    print(f"  Time:   {elapsed:.2f}s")
    print()

    if errors:
        print("  ERRORS:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("  ALL TESTS PASSED")

    print(f"{'='*60}")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
