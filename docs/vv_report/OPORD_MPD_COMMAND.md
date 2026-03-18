# OPERATIONS ORDER
## MPD OVERWATCH - FIELD DEPLOYMENT

> OPERATIONAL PLANNING DOCUMENT. Describes mission, execution concept,
> and force structure. Dollar values in Section 3c are illustrative
> computations using stated assumptions, not measured production data.

```
CLASSIFICATION:  PROPRIETARY - DISTRIBUTION LIMITED
ORIGINATOR:      B. JONES / OPERATIONS DEVELOPMENT
FOR:             A. HENSLEY / COMMANDING
DTG:             172026ZMAR26
REFERENCES:      IADC UBO/MPD MANUAL 2011
                 SPE FORMATION DAMAGE SERIES (BENNION 1998)
                 VALOR ENERGY RESEARCH SERIES VE-1 THROUGH VE-5
                 FIELD DATA: [REDACTED] DELAWARE BASIN WOLFCAMP OPS
```

---

## 1. SITUATION

### a. Area of Operations

Delaware Basin, Permian. Wolfcamp A/B target intervals. 10,400-10,700 ft TVD.
Pore pressure gradient: 0.55-0.65 psi/ft (overpressured). Fracture gradient: 0.80-0.90 psi/ft.
Operating window: 4.8 ppg EMW. Narrowing in depleted infill corridors.

4,000+ horizontal wells drilled annually. Current standard: conventional overbalanced
drilling at 13+ ppg. No MPD. No pressure management beyond static mud weight selection.

### b. Opposing Forces

Operator perception: MPD = expensive equipment rental. Decision metric: cost per day.
Competing services: commodity providers racing to the lowest bid. No differentiation
on outcomes. No quantification of formation damage. No completion optimization from
drilling data. The opposition is not another MPD company. The opposition is the status quo.

### c. Friendly Forces

**TF-COMMAND (This Element):**
- Allen Hensley: 30 years MPD operations. Former Noble Offshore principal consultant.
  Global deployment experience. Reputation: tier-zero in the discipline.
- Blake Jones: MWD operations. Software development. Cognitive profile: WMI 122 (93rd %ile),
  executive planning SS=120, arithmetic reasoning SS=15 (95th %ile). Builder of systems.
- MPD Overwatch Platform: 62 files, 26,569 lines. 28/28 V&V benchmarks A+. pip install -e .
  14 interactive displays. Sheaf topology anomaly detection. Real data validated.

**Supporting:**
- Gregory Hood: Valor Energy executive. Industry relationships. Capital access.
- Research base: 5 co-authored technical documents establishing MPD production enhancement theory.
- Field data archive: Multi-well LAS/EDR/MWD dataset spanning multiple operators and service companies.

---

## 2. MISSION

Establish MPD as a quantifiable production enhancement technology on land.
Replace cost-based procurement with value-based engagement.
Deliver measurable EUR uplift on every well.
Build a compounding analytical asset that improves with each deployment.

---

## 3. EXECUTION

### a. Concept of Operations

**Phase I: Intelligence Preparation**
- Load offset well data into MPD Command
- Compute formation damage profile under conventional drilling parameters
- Quantify production impact: skin factor, PI reduction, EUR loss
- Generate client-specific value proposal with traceable arithmetic

**Phase II: Initial Contact**
- Present the arithmetic, not the equipment
- Lead with: "What is your current overbalance in the pay zone?"
- Follow with: "Here is what that overbalance costs you in barrels"
- Close with: "Here is what we compute for your specific well at current oil prices"

**Phase III: Field Deployment**
- MPD operations with integrated data acquisition
- Real-time coherence monitoring (sheaf topology)
- APWD/gamma/ROP/flow correlation for completion optimization
- Connection management via computed SBP sequences

**Phase IV: Post-Well Analysis**
- Compare predicted vs actual production
- Calibrate transport maps with field results
- Generate value-delivered report for the operator
- Use calibrated model for next well proposal

**Phase V: Market Position**
- Each well strengthens the analytical model
- Each successful prediction builds reputation
- Each calibrated transport map is proprietary intelligence
- The system gets smarter. The competition stays static.

### b. Scheme of Maneuver

```
FIELD DATA             COMPUTATION            VALUE PROOF
   |                      |                      |
   v                      v                      v
LAS/EDR/MWD  ------>  4D Pointcloud  ------> Proposal
   |                      |                      |
   v                      v                      v
233 stations         5,500 points             $10.9M
27 curves            11 channels              68:1 ROI
21,095 ft MD         4-layer analysis         140K BOE
   |                      |                      |
   v                      v                      v
[REDACTED]           Sheaf Laplacian          "Show me
Delaware Basin       Coherence: 0.998          another."
Wolfcamp A           4 anomalies detected
```

### c. Key Computations (Field Data)

From [REDACTED] well, Delaware Basin, 21,095 ft MD, 10,617 ft TVD, 10,132 ft lateral:

```
PRESSURE AT TD (10,617 ft TVD):

  Pore pressure:     5,533 psi  (10.0 ppg EMW)
  Fracture gradient: 8,771 psi  (15.9 ppg EMW)
  Operating window:  3,238 psi  (5.9 ppg)

  Conventional BHP:  7,177 psi  (at 13.0 ppg)
  MPD BHP:           6,665 psi  (at 11.8 ppg + 150 SBP)

  Overbalance conv:  1,644 psi
  Overbalance MPD:   1,131 psi
  Reduction:         31%

FORMATION DAMAGE COMPUTATION:

  Skin (conventional): S = (k/kd - 1) x ln(rd/rw)
    k = 0.1 md, kd = 0.02 md (80% reduction from invasion)
    rd = 0.8 ft, rw = 0.354 ft
    S = 3.26

  Skin (MPD): S = (k/kd - 1) x ln(rd/rw)
    k = 0.1 md, kd = 0.09 md (10% reduction)
    rd = 0.4 ft, rw = 0.354 ft
    S = 0.014

  Skin reduction: 99.6%

PRODUCTIVITY INDEX:

  PI = kh / (141.2 x Bo x mu x (ln(re/rw) + S))
  k=0.1md, h=200ft, Bo=1.25, mu=0.8cp, re=1000ft, rw=0.354ft

  PI (conv, S=3.26): 0.0126 STB/d/psi
  PI (MPD, S=0.014): 0.0178 STB/d/psi
  Improvement: 40.8%

WELL TRAJECTORY:

  Surface to KOP:    0 - 1,943 ft MD (vertical)
  Build section:     1,943 - 10,963 ft MD (0 to 89.7 deg)
  Lateral:           10,963 - 21,095 ft MD (10,132 ft)
  Max DLS:           12.7 deg/100ft
  Landing TVD:       10,478 ft
  Lateral avg TVD:   10,568 ft
```

---

## 4. SUSTAINMENT

### Calibration Cycle

Each deployment refines the analytical model:

```
Well 1:   Literature-based coefficients. Wide uncertainty bands.
Well 5:   Basin-calibrated transport maps. Tighter predictions.
Well 20:  Proprietary formation behavior database.
          Prediction accuracy that operators trust for real-time decisions.
Well 100: Market position secured by data advantage no competitor can replicate.
```

### Technology Evolution

The division bell rings for those who see measurement as cost rather than investment.
The data exists in every LAS file on every well already drilled. The equations are published.
The computation is verified at A+ precision.

What has been missing is the integration: the craft of connecting what the well tells you
while drilling to what the well delivers in production. The bridge between the choke
manifold and the decline curve. Between the APWD sensor and the EUR.

That bridge is now built. 62 files. 26,569 lines. 28 verified equations.
A sheaf Laplacian that detects when the physics breaks before any threshold alarm fires.
A 4D point cloud that treats every measurement as a point in a mathematical space
where proximity means physical relationship and distance means anomaly.

Those who build their operations on this foundation adapt.
Those who compete on rental rates wait for the market to move past them.

The adaptive shape their reality.

---

## 5. COMMAND AND SIGNAL

### Command

A. Hensley - operational authority and client engagement
B. Jones - platform development and analytical support
G. Hood - strategic direction and capital

### Signal

Platform access: `START_HERE.bat` -> `http://127.0.0.1:8050`
V&V evidence: `docs/vv_report/`
Field data: `DATA_TYPES_for_System_Use_EXAMPLES/`
Source: `src/mpd_overwatch/` (62 files, 26,569 lines)

---

```
ACKNOWLEDGE RECEIPT.
EXECUTE ON ORDER.
```
