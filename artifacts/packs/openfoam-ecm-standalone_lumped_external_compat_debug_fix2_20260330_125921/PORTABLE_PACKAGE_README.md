# Portable Package

This repository can be exported as a self-contained OpenFOAM + ECM bundle for
other workstations.

What the portable bundle contains:
- buildable OpenFOAM source under `src/`
- ECM runtime Python under the package root and `ecm/`
- clean CHT cases:
  - `cases/lumped_solid`
  - `cases/distributed_solid`
- selected docs and validation/report tools

What it does not contain:
- old run logs, reports, and validation artifacts
- stale runtime state such as `ecm_state.json` or `ecm_last_good.bin`
- prior time directories and post-processing outputs
- machine-specific build outputs

## Prerequisites

- OpenFOAM v2506 environment available on the target workstation
- `wmake`
- Python 3 with:
  - `numpy`
  - `pandas`
- Standard case meshing tools used by the included `Allrun` scripts

## ECM Data Contract

The packaged root ECM path is designed for the external `ecm_step.py` contract.

The backend accepts either:
- an external lookup-table `params.csv` with columns:
  - `Q_Ah`
  - `T_degC`
  - `R0_Ohm`
  - `R_Ohm_1`
  - `R_Ohm_2`
  - `C_F_1`
  - `C_F_2`
- or the older packaged SOC-style table:
  - `SOC`
  - `OCV_V`
  - `R0_Ohm`
  - `R1_Ohm`
  - `R2_Ohm`
  - `tau1_s`
  - `tau2_s`
  - `gamma_hyst_V`

Required `cellprops.csv` columns:
  - `capacity_Ah`
  - `T_ref_degC`

If a SOC-style `params.csv` is supplied, `ecm_backend.py` expands it into a
synthetic `(Q_Ah, T_degC)` lookup table before calling the external
`ecm_step.py`. This keeps the existing packaged `params.csv` usable while still
matching the external module's expected interface.

## Build On The Target Workstation

From the package root:

```bash
./build_portable.sh
```

This bootstrap script loads a common OpenFOAM environment automatically when
possible and then runs:

```bash
./Allwmake
```

This builds:
- `libecmCouplingFunctionObjects.so`
- `libecmPatchFields.so`
- `chtMultiRegionSolidFoam`

The case `Allrun` scripts prefer package-local `.openfoam/bin` and
`.openfoam/lib` if they exist after the build, but they no longer assume a
`/workspace` path.

## Runtime Diagnostics

Each packaged `Allrun` script now prints two paths before the solver starts:
- the solver log
- the ECM wrapper diagnostic log

The ECM diagnostic log captures:
- backend selection and resolved file paths
- Python executable and working directory
- persistent daemon launch details
- parameter and cell-property CSV column names seen by the backend
- explicit external-schema compatibility errors when the wrong `params.csv` is used
- full backend startup exceptions and tracebacks

If a packaged run fails during ECM startup, return both logs.

## Run The Packaged Cases

Lumped:

```bash
cd cases/lumped_solid
./Allrun --reset-ecm
```

Distributed:

```bash
cd cases/distributed_solid
./Allrun --reset-ecm
```

## Switching Modes

The package is intended to be robust to a mode switch driven by case
configuration, not shell-environment changes. The execution path should stay the
same; only case settings such as `couplingMode` or mapping/backend options
should differ.

## Rebuild The Portable Export

From the original repository:

```bash
tools/create_portable_package.sh
```

That script writes a clean export directory and a `.tar.gz` archive under
`artifacts/packs/`.
