OpenFOAM ECM coupling debug pack (lumped_solid)

Contains
- Source code:
  - src/chtMultiRegionSolidFoam/ (custom solids-only multi-region solver)
  - src/ecmCouplingFunctionObjects/ (ecmCoupler functionObject)
- Test case (dictionaries only, no mesh/heavy data):
  - cases/lumped_solid/{system,constant,0,Allrun,Allclean,Allmesh}
  - excluded intentionally: constant/*/polyMesh, triSurface, extendedFeatureEdgeMesh, postProcessing, time dirs >0
- Tooling (report/diagnostics):
  - tools/generate_lumped_report.py
  - ecm/* and ecm_backend.py/ecm_coupling_wrapper.py

Bug context
- In transient solids-only runs with positive volumetric heat source (ecmQdot > 0),
  some cells (incl. jellyRoll<->shell/cap interface-adjacent) cool below initial/externalWall T.
- Interface-average temperature from surfaceFieldValue decreases over time; both sides match.

Primary suspect
- Solid energy equation in src/chtMultiRegionSolidFoam/solid/solveSolid.H may be missing a transient term
  (ddt) vs the reference OpenFOAM multi-region solid energy equation.

Reproduction note
- This pack does not include the geometry or mesh. You can still review dictionaries and source.
