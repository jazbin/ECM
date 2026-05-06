# lumped

Reference case for a cylindrical cell with pure conduction using lumped ECM
coupling. This case is prepared for UNV mesh import.

## Expected workflow (snappyHexMesh)
1. Ensure `constant/triSurface/cellFull.stl` is present.
2. Run `./Allmesh` to build the multi-region mesh (snappyHexMesh + splitMeshRegions).
3. Add region-specific initial and boundary fields in `0.orig/`.
4. Configure solver settings in `system/` and run the solver.

## Expected workflow (UNV import)
1. Drop the UNV file in this folder.
2. Run `./Allrun.pre` to import the mesh.
3. Define regions/cellZones as needed for a CHT setup.
4. Add region-specific initial and boundary fields in `0.orig/`.
5. Configure solver settings in `system/` and run the solver.

## Notes
- This repo requires CHT-related setups; align any configuration with the
  simplest applicable `chtMultiRegionSimpleFoam` tutorial.
- `Allrun.pre` expects exactly one `.unv` file in the case root.
