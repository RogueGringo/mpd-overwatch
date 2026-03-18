# docs/vv_report - Document Index

## Verified (real data, real equations)

| File | Content | Data Source |
|------|---------|-------------|
| `MPD_Overwatch_Report_REAL.html` | Interactive report with field data charts and V&V table | [REDACTED] Delaware Basin well, 42,034 MWD points |
| `chart_07_real_well_pressure.png` | Pressure profile computed on real survey TVD | Real LAS survey data |
| `chart_08_overbalance.png` | Overbalance comparison along real wellbore | Real LAS survey data |
| `chart_09_skin_sensitivity.png` | Skin factor curve from Hawkins equation | Published equation, stated inputs |
| `_real_well_computed.csv` | Computed pressure values at each survey station | Real survey + stated MW assumptions |

## Vision Documents (narrative, not computed analysis)

| File | Content | Notice |
|------|---------|--------|
| `03_THE_CRAFT.md` | Operational philosophy: rental vs engineering | Zone examples are illustrative |
| `04_THE_MARKET.md` | Market size from public sources | Per-well values are illustrative |
| `05_THE_FUTURE.md` | Calibration and learning architecture | Describes intended capability |
| `MPD_Command_Technical_Review.md` | Technical walkthrough with equation demonstrations | Mix of verified and illustrative |
| `OPORD_MPD_COMMAND.md` | Operational briefing format | Narrative document |

## Removed (contained fabricated values presented as analysis)

The following files were removed because they presented synthetic/demo data as
computed analysis without adequate labeling:

- `01_THE_NUMBERS.md` - fabricated production and economic values
- `02_THE_PROBLEM.md` - fabricated dollar claims
- `Executive_Summary_for_Allen_Hensley.md` - referenced old structure
- `MPD_Command_VV_Report.md` - referenced old directory structure
- `MPD_Overwatch_Report.html` - fabricated $11.1M / 74x ROI values
- `chart_01` through `chart_06` - based on synthetic demo well data

These capabilities exist in the platform. The equations are verified (28/28 A+).
But the specific dollar values require well-specific inputs that were not provided.
The platform computes results from real data. It does not fabricate them.
