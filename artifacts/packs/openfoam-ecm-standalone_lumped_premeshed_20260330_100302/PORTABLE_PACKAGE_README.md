# Portable Package

This repository can be exported as a self-contained OpenFOAM + ECM bundle for
other workstations.

What the portable bundle contains:
- buildable OpenFOAM source under `src/`
- ECM runtime Python under the package root and `ecm/`
- one clean pre-meshed CHT test case:
  - `cases/lumped_solid`
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
- Standard OpenFOAM runtime tools

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

The included `cases/lumped_solid` case is pre-meshed. `Allrun` will therefore
skip mesh generation on first use unless you remove the shipped `polyMesh`
directories or run `Allclean`.

## Run The Packaged Case

Lumped:

```bash
cd cases/lumped_solid
./Allrun --reset-ecm
```

After building, you can also run the solver directly from the case directory if
your OpenFOAM environment and library paths are already set correctly.

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
