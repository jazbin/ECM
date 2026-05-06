# Wedge 2170 — OpenFOAM ECM Coupling Package

3D cylindrical 2170 battery cell thermal simulation with external electrochemical model (ECM) coupling.

## Package Structure

```
wedge_2170_ecm_pack/
├── Allwmake                         ← compile all libraries and solver
├── src/
│   ├── ecmCouplingFunctionObjects/  ← ecmCoupler functionObject (libecmCouplingFunctionObjects.so)
│   ├── ecmFvOptions/                ← ecmHeatSource fvOption     (libecmFvOptions.so)
│   ├── ecmPatchFields/              ← custom patch fields         (libecmPatchFields.so)
│   └── chtMultiRegionSolidFoam/    ← modified CHT solver         (chtMultiRegionSolidFoam)
├── lib/                             ← compiled libraries (created by Allwmake)
├── bin/                             ← compiled solver   (created by Allwmake)
├── python/
│   ├── ecm_coupling_wrapper.py      ← main ECM ↔ CFD bridge (persistent-pipe mode)
│   ├── ecm_backend.py               ← backend abstraction (mock / vendor-cli / ecm-step)
│   ├── ecm_step.py                  ← electrochemical step model (RC + hysteresis)
│   ├── ecm_io.py                    ← binary I/O protocol (v1/v2 header)
│   ├── mock_ecm_backend.py          ← lightweight mock for testing
│   ├── params.csv                   ← NCA 4680 lookup table (Q_Ah × T_degC)
│   ├── cellprops.csv                ← cell properties (capacity, surface area)
│   └── requirements.txt             ← Python dependencies
└── cases/
    └── wedge_2170/
        ├── Allrun                   ← run script
        ├── 0/                       ← initial conditions (T fields)
        ├── constant/                ← mesh + material properties
        └── system/                  ← solver settings + ECM coupling config
```

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| OpenFOAM | v2506 | Must be sourced before build and run |
| Python | 3.8+ | Must be on PATH as `python3` |
| numpy | any | `pip install -r python/requirements.txt` |
| pandas | any | included above |

## Quick Start

### 1. Build

Source OpenFOAM, then from the package root:

```bash
source /path/to/OpenFOAM-v2506/etc/bashrc
./Allwmake
```

This compiles all four targets and places outputs in `lib/` and `bin/`.

### 2. Install Python dependencies

```bash
pip install -r python/requirements.txt
```

### 3. Run

```bash
cd cases/wedge_2170
./Allrun
```

Solver output is logged to `cases/wedge_2170/logs/run_<timestamp>.log`.

## Case Overview

| Parameter | Value |
|-----------|-------|
| Geometry | 2170 cylindrical cell (R=10.545 mm, H=70.02 mm) |
| Solver | chtMultiRegionSolidFoam (solids-only CHT) |
| Regions | jellyRoll_rotated, shell_rotated, cap_rotated |
| Simulation time | 0 – 1200 s |
| Timestep | 0.05 s |
| Write interval | every 100 s |
| ECM mode | lumped, persistentPipe, every 5th CFD step |
| Discharge current | 5 A |

## Material Properties (from caseSettings specifications)

| Region | ρ (kg/m³) | k_rr (W/mK) | k_zz (W/mK) | Cp (J/kgK) |
|--------|----------:|------------:|------------:|------------|
| JellyRoll | 2660.7 | 1.4 | 29 | 980 + 3·(T−298.15) |
| Shell/Can | 8000 | 16 | 16 | 500 (const) |
| Cap | 1447.2 | 0.01 | 0.1 | 500 (const) |

## ECM Coupling Architecture

```
OpenFOAM (chtMultiRegionSolidFoam)
  └─ ecmCoupler functionObject (every timestep)
       ├─ extracts volume-averaged T from jellyRoll_rotated cellZone
       ├─ writes ecm/ecm_in.json
       ├─ calls python3 ../../python/ecm_coupling_wrapper.py (persistent pipe)
       │     └─ ecm_step.py  (2D RC ECM, params.csv lookup table)
       │          returns: Q_gen [W]
       └─ reads ecm/ecm_out.json → maps to ecmQdot [W/m³] with relaxation=0.5
            └─ ecmHeatSource fvOption applies -ecmQdot*V to enthalpy equation
```

## Restart

The case uses `startFrom latestTime`. To restart from the latest written time:

```bash
cd cases/wedge_2170
./Allrun
```

The ECM wrapper state is persisted in `ecm/ecm_state.json`. To start fresh:

```bash
rm -f ecm/ecm_state.json ecm/ecm_last_good.bin
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `libecmCouplingFunctionObjects.so: cannot open` | Library not found | Verify `./Allwmake` completed; check `lib/` |
| `chtMultiRegionSolidFoam: command not found` | Binary not on PATH | `Allrun` sets PATH automatically from package root |
| `python3: No module named pandas` | Missing Python deps | `pip install -r python/requirements.txt` |
| ECM wrapper silent / no heat | `ecm_state.json` stale | Delete it and rerun |
