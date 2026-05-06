# Binary IO protocol (v1)

All integers are **little-endian**.

## Header (fixed, 44 bytes)

- `char magic[8]` : ASCII `ECMIOv1` (exactly 7 chars + 1 padding byte). This implementation writes `b"ECMIOv1\0"`.
- `uint32 fileType` : 1 = input (OpenFOAM→ECM), 2 = output (ECM→OpenFOAM)
- `uint32 version` : 1
- `uint32 N` : number of coupled mesh cells (OpenFOAM FV cells)
- `double time` : simulation time
- `double deltaT` : timestep size
- `uint32 keyMode` : 0 = globalCellId (recommended; identifies mesh cells), 1 = localCellId (serial-only; identifies mesh cells)
- `uint32 nInputs` : number of scalar electrical inputs that follow

## Electrical inputs section (variable length)

Repeated `nInputs` times:

- `uint32 nameLen`
- `bytes[nameLen] name` : UTF-8 (no null terminator)
- `double value`

## Records section

Repeated `N` times:

### Input record
- `int32 key`
- `double T` : temperature [K]

### Output record
- `int32 key`
- `double qVol` : volumetric heat generation [W/m^3]

## Notes on keys

Keys identify **mesh cells** (OpenFOAM control volumes) inside the coupled `cellZone`. They do **not** identify physical battery cells. The external ECM is assumed to represent a battery cell (or module) and returns heat distributed over mesh cells.

## Atomic write convention

Writers must:
- write to `*.tmp`
- `rename()` to final `*.bin` name

This prevents partial reads.

## Contract governance

This file is the IO contract. Any changes should be versioned and reflected in
`MY_CODEX_BEST_PRACTICES_RULES.txt`, and validated with a parser check per
`docs/TEST_PLAN.md`.
