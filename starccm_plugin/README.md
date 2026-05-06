# ECM Coupler for STAR-CCM+ — Standalone Pack

Couples an external electrochemical model (ECM) to STAR-CCM+ using the same
binary protocol as the validated OpenFOAM `ecmCoupler` functionObject.

**Validated against:** 18650/2170 NCA cell, 3600 s CCCV profile, T RMSE < 0.33°C

---

## Quick Start (Windows 10)

### 1. Prerequisites

- STAR-CCM+ (any recent version with Java macro support)
- Python 3.9+ — install from https://python.org (tick "Add to PATH")
- Required Python packages:
  ```
  pip install numpy pandas
  ```

### 2. Pack layout

```
ecm_coupler_starccm/
├── macro/
│   ├── EcmCouplerMacro.java    ← load this in STAR-CCM+
│   └── EcmBinaryIO.java        ← must be in the same folder
├── ecm/
│   ├── ecm_coupler.py          ← ECM orchestrator (run by macro)
│   ├── ecm_io.py               ← binary protocol
│   ├── ecm_step.py             ← per-step physics
│   ├── mock_ecm_backend.py
│   ├── mock_model.py
│   ├── params.csv              ← NCA cell parameters
│   └── electrical_inputs_from_validation.csv   ← current profile [A vs t]
└── README.md
```

Copy the entire `ecm/` folder next to your `.sim` file before running.

### 3. One-time setup in STAR-CCM+

Wire the heat source once; it persists in the `.sim` file:

1. **Create a field function**
   - Tools → Field Functions → New Scalar
   - Name: `ecmQdot_field`
   - Definition: `$ecmQdot_W_m3`

2. **Apply to the battery region**
   - Regions → jellyRoll → Physics Values → Volumetric Heat Source
   - Method: Field Function → `ecmQdot_field`

### 4. Configure the macro

Open `macro/EcmCouplerMacro.java` and edit the **CONFIG block** at the top:

| Constant | Default | Notes |
|---|---|---|
| `REGION_NAME` | `"jellyRoll"` | Match your STAR tree region name |
| `QPARAM_NAME` | `"ecmQdot_W_m3"` | Global parameter name |
| `ECM_DIR` | `"ecm"` | Folder containing ecm_coupler.py (relative to .sim file) |
| `PYTHON_EXE` | `"python"` | Full path if python not on PATH |
| `ALPHA` | `1.0` | Under-relaxation (1.0 = none) |
| `N_STEPS` | `36000` | Steps to run (= endTime / deltaT) |

### 5. Run

- Tools → Macros → Run Macro → select `macro/EcmCouplerMacro.java`
- **Do NOT press the Run button** — the macro drives the solver loop

---

## How It Works

Each timestep the macro:

1. `iter.step(1)` — advances STAR-CCM+ one timestep
2. Reads `T_avg` via a VolumeAverageReport
3. Interpolates `current_A` from `electrical_inputs_from_validation.csv` at the current sim time
4. Writes `ecm/ecm_in.bin` (v2 binary, N=1, nInputs=1 with current_A)
5. Launches `python ecm/ecm_coupler.py` (subprocess, blocks)
6. Reads `qVol [W/m3]` from `ecm/ecm_out.bin`
7. Sets `ScalarGlobalParameter ecmQdot_W_m3 = qVol`

---

## Customising the Current Profile

Replace `ecm/electrical_inputs_from_validation.csv` with your own profile.
The file must have two unquoted columns:

```
time,current_A
0,0
11,0
100,5.0
200,10.3
...
3600,0
```

Current is linearly interpolated between rows.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `region not found` | Wrong `REGION_NAME` | Check STAR tree spelling |
| `ecm_out.bin not ready` | Python not on PATH | Set full path in `PYTHON_EXE` |
| `ModuleNotFoundError: numpy` | Packages not installed | `pip install numpy pandas` |
| Q stays at 0 | CSV not found or wrong column names | Check `ECM_DIR` path; columns must be `time`, `current_A` (unquoted) |
| stepId mismatch warnings | Stale `.bin` files from previous run | Delete `ecm/*.bin` and `ecm/ecm_state.json` before re-running |

---

## ECM Parameters

ECM parameters are in `ecm/params.csv` (NCA 18650/2170 cell, 5.05 Ah nominal).
Columns: `Q_Ah, T_degC, OCV_V, R0_Ohm, R1_Ohm, C1_F, R2_Ohm, C2_F, DUDT_V_per_K`

To use your own cell chemistry, replace `params.csv` with matching column names.
