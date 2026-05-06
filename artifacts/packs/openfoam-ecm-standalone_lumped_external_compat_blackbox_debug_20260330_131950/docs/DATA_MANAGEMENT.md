# Data Management

## Large files
Use Git LFS or DVC for large meshes and outputs. Recommended patterns:
- Meshes: `*.msh`, `*.stl`, `*.eMesh`
- Field outputs: `postProcessing/`, large time directories

## Archiving
- Compress and archive old cases using tar.
- Keep input files (0/, constant/, system/) with the archive.

## Provenance
- Store run manifests next to outputs.
- Include git commit, OpenFOAM version, and environment details.
