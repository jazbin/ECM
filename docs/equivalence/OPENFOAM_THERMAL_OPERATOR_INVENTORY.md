# OpenFOAM Reference Thermal Operator Inventory

**Date:** 2026-09-17
**Source case:** `cases/wedge_2170` (chtMultiRegionSolidFoam, OpenFOAM 2506). Machine-readable form: `data/equivalence/openfoam_thermal_operator.json`.

Governing PDE (per `tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md`):

ρ(x) c_p(x) ∂T/∂t = ∇·(K(x)∇T) + q(x,t)

with region-wise ρ, c_p, K and a single ECM-driven volumetric source q confined to JellyRoll.

## 1.1 Geometry inventory (exact, from `constant/{region}/polyMesh/points` bounding boxes)

| Domain | Radius (mm) | z-range (mm) | Height (mm) | Volume (mm³) | Shape |
|---|---|---|---|---|---|
| JellyRoll | 10.31368 | 0.23132 – 65.3413 | 65.11 | 21758.289 | solid cylinder |
| Can (shell) | 10.545 (outer) | 0.0 – 65.3413 | 65.3413 | 1067.764 | radial wall (t=0.23132mm, r 10.31368–10.545) + solid bottom disc (r 0–10.545, z 0–0.23132) |
| Cap | 10.545 | 65.3413 – 70.02 | 4.6787 | 1634.437 | solid disc, full radius |

Can OD = 21.09 mm, Can ID = JR OD = 20.6274 mm — matches the project's stated radial target exactly (`OPENFOAM_ECM_EQUIVALENCE_TARGET.md`). No central void/mandrel-equivalent volume exists in the OpenFOAM reference — the JellyRoll region is a single homogeneous anisotropic solid cylinder with no internal subdivision.

Contact areas (full 360°, computed from the radii/heights above):
- JR↔Can radial: 2π·(0.0103137 m)·(0.0651 m) ≈ 4.219×10⁻³ m²
- JR↔Can bottom (=Can bottom disc top face): π·(0.0103137 m)² ≈ 3.341×10⁻⁴ m²
- JR↔Cap: π·(0.0103137 m)² ≈ 3.341×10⁻⁴ m² (JR top face, same radius)
- Can↔Cap: annulus 2π·r·dr is not applicable — the Can/Cap boundary is the Can's top rim contacting the Cap's outer cylindrical face at r=10.545mm over a negligible axial band; treated as a shared coincident face in the mesh (`shell_rotated_to_cap_rotated` patch exists but its exact area was not separately extracted — low priority, does not affect the mapping conclusions below).
- External exposed area: Can outer wall + Cap outer face, mesh-reported at 3024 + 612 wedge faces respectively (`constant/polyMesh/boundary`).

## 1.2 Thermal properties (verbatim from `thermophysicalProperties`, not collapsed to scalar k)

| Domain | ρ (kg/m³) | c_p | k_r (W/mK) | k_θ (W/mK) | k_z (W/mK) |
|---|---|---|---|---|---|
| JellyRoll | 2660.7 | tabulated: (250K,835.55) (500K,1585.55) J/kgK — linear, ≈980+3·(T−298.15K) J/kgK | 1.4 | 1.4 | 29 |
| Can | 8000 | 500 J/kgK (constant) | 16 (isotropic) | 16 | 16 |
| Cap | 1447.2 | 500 J/kgK (constant) | 0.01 | 0.01 | 0.1 |

JellyRoll and Cap use `heSolidThermo` with cylindrical `coordinateSystem` (axis 0 0 1) and anisotropic transport (`tabulatedAnIso` / `constAnIso`) — the full (r,θ,z) tensor is preserved, not scalarised. Can uses `constIso` (isotropic 16 W/mK, physically reasonable for a metal can).

## 1.3 Internal interfaces (from boundary-condition files, `0/{region}/T`)

| Interface | Type | Contact resistance |
|---|---|---|
| JR ↔ Can, radial | `turbulentTemperatureRadCoupledMixed` | none specified → ideal contact |
| JR ↔ Can, bottom | `turbulentTemperatureRadCoupledMixed` | **explicit**: thicknessLayers=6.015×10⁻⁷ m, kappaLayers=1 — small but nonzero; does not reconcile numerically with the documented `Rtherm_jroll_base=5.4 K/W` (see `SOURCE_INVENTORY.md`) |
| JR ↔ Cap | `turbulentTemperatureRadCoupledMixed` | none specified → ideal contact |
| Can ↔ Cap | `turbulentTemperatureRadCoupledMixed` | none specified → ideal contact |

Radiation (`qr`) is `none` on every coupled interface. The project's ideal-contact default (per `OPENFOAM_ECM_EQUIVALENCE_TARGET.md`) holds for 3 of 4 interfaces exactly; the JR/Can bottom interface carries a small explicit resistance that is present in the file but whose numeric provenance is unconfirmed.

## 1.4 External boundary conditions

| Patch | Region | Type | h (W/m²K) | T_amb (K) |
|---|---|---|---|---|
| `shell_outerSurface_rotated` | Can | `externalWallHeatFluxTemperature` (coefficient mode) | 160 | 298.15 |
| `capOuterSurface_rotated` | Cap | `externalWallHeatFluxTemperature` (coefficient mode) | 160 | 298.15 |

Identical convective coefficient and ambient on both exposed surfaces; no fixed-T, no additional radiation BC, no symmetry/adiabatic patch (the wedge front/back patches are geometric `wedge` type for the axisymmetric slice, not physical BCs). No explicit time dependence on either h or T_amb.

## 1.5 Heat-source mapping

- All ECM heat is deposited **only** in `jellyRoll_rotated`, via the custom `ecmHeatSource` fvOption acting on field `h` (enthalpy), volumetric field `ecmQdot`.
- `selectionMode all` → **uniform deposition across every JR cell**; there is **no** axial or radial sub-zoning within JellyRoll. `couplingMode lumped` / `lumpedOutput totalPower` confirms a single scalar total-power value is spread uniformly over the whole JR volume per ECM coupling step.
- Can and Cap receive **zero** direct heat in the executable case (no `fvOptions` file exists for either region) — this contradicts the `f_cap=0.034` figure documented elsewhere; see discrepancy #1 in `SOURCE_INVENTORY.md`.
- The ECM state (current, SOC, RCR response) is computed by an external Python process (`python/ecm_coupling_wrapper.py`, `--backend ecm-step`) driven by `constant/electrical_inputs_from_validation.csv`, communicating via a persistent JSON pipe. Whether reversible/entropic heat is included is internal to that backend and was not audited here (would require reading the Python ECM implementation, out of scope for the OpenFOAM-side operator reconstruction).
- Mathematically: q(x,t) = Q_total(t) / V_JR for x ∈ Ω_JR, q(x,t) = 0 for x ∈ Ω_Can ∪ Ω_Cap, where Q_total(t) is the lumped ECM total power output at coupling step t.

## Reconstruction status: PARTIAL

Geometry, material tensors, external BCs, 3 of 4 interfaces, and the heat-source spatial mapping are fully and exactly reconstructed from repository files. Two items remain open (heat-split documentation conflict, base-contact-resistance value mismatch) and one item (reversible heat inside the Python ECM backend) is out of scope for this OpenFOAM-file-level reconstruction. None of these open items were resolved by invented values.
