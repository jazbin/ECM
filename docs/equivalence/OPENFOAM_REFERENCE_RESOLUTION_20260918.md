# OpenFOAM Reference Resolution — Heat Source and Bottom Contact Resistance

Date: 2026-09-18
Purpose: resolve the two open OpenFOAM-side inconsistencies flagged before involving
Robert/STAR — (1) heat-source split vs. documented split, (2) bottom contact resistance
vs. documented `Rtherm_jroll_base`. Per instruction: **do not leave both** interpretations
standing; pick the authoritative one with evidence.

## 1. Heat-source split: 100% JellyRoll is authoritative

Executable-code audit, three independent points in the coupling chain:

- `src/ecmFvOptions/ecmHeatSources/ecmHeatSources.C` — applies the `ecmQdot` field directly
  as a volumetric source (`eqn.source()[celli] -= qVol[celli]*mesh_.V()[celli];`) with no
  fraction/split coefficient anywhere in the file.
- `python/ecm_coupling_wrapper.py` — grepped for `f_jroll`/`f_cap`/`f_can`/`fraction`/`split`:
  zero matches. No split logic exists on the Python side of the coupling either.
- `src/ecmCouplingFunctionObjects/ecmCoupler/ecmCoupler.C` — divides `totalPower` by `sumV`,
  the cell-volume sum of the **JellyRoll zone only**, to get a uniform W/m³ deposition. There
  is no reference to Can or Cap cell zones in this function object at all.

Conclusion: the documented `f_jroll=0.966, f_cap=0.034, f_can=0` split
(`docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md`) was never implemented in the
executable path. It appears to have been a design intent captured in documentation that the
code never picked up. **The actual, running reference is 100% Q → JellyRoll.** This is what
STAR must be made to reproduce — not the documented split.

Action: `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md`'s split fractions should
be treated as stale/aspirational, not authoritative, pending an explicit decision to implement
a split in code (out of scope here).

## 2. Bottom contact resistance: production near-ideal contact is authoritative

Two divergent case configurations exist for the `jellyRoll_rotated_to_shell_rotated_bottom`
coupled patch (`compressible::turbulentTemperatureRadCoupledMixed`, `kappaMethod solidThermo`,
with `thicknessLayers`/`kappaLayers` giving an added contact resistance R = t/(k·A)):

| Case | `thicknessLayers` (m) | `kappaLayers` (W/m·K) | Patch area A (m²) | R = t/(kA) (K/W) |
|---|---|---|---|---|
| `cases/wedge_2170` (production) | 6.01519461276695e-07 | 1 | 3.3417e-4 | **1.800e-03** |
| `cases/wedge_2170_constant_heat_rtherm` | 1.804785e-03 | 1 | 3.3417e-4 | **5.4007** |

Patch area from `checkMesh -allGeometry` on `jellyRoll_rotated_to_shell_rotated_bottom`
(432 faces, non-closed patch, bounding box radius 0.01031368 m — the full JR bottom-face
disk, A = πr² = 3.3417e-4 m²).

The `_rtherm` case's R = 5.4007 K/W matches the documented `Rtherm_jroll_base =
5.40067678 K/W` to 4 significant figures — i.e. that case and that document describe the
same (now-superseded) design point. The production case's R ≈ 1.8 mΩ·K/W is three orders
of magnitude smaller — effectively ideal/zero contact.

**Chronology** (file mtimes, no git history available for these untracked case files):
- `cases/wedge_2170/0/jellyRoll_rotated/T` (production, near-ideal contact): 2026-04-27 10:28
- `cases/wedge_2170_constant_heat_rtherm/run.log`: 2026-04-29 07:48
- `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md` (documents 5.4 K/W):
  2026-04-29 12:06, ~4.3h after the rtherm run

So the rtherm case + its documentation were built together on 2026-04-29, two days *after*
the production near-ideal-contact case already existed on 2026-04-27. The rtherm case reads
as a since-abandoned exploratory variant (calibrated contact resistance), not a correction
applied back to production.

**Policy confirmation**: the governing requirement doc
(`tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md`, dated 2026-09-10, five months later
than both case variants) states explicitly:

> "Default thermal contact/interface resistance is zero, matching ideal contact in the
> OpenFOAM reference." / "If an interface/contact resistance is needed later for calibration
> or sensitivity work, it must be introduced explicitly as an interface model/parameter, not
> implicitly by creating a geometric air gap."

This is the most recent and most explicit statement of intent in the repository, and it
matches the production case's near-ideal contact, not the rtherm case's 5.4 K/W.

Conclusion: **the production `cases/wedge_2170` near-ideal contact (R≈1.8 mΩ·K/W) is
authoritative.** `Rtherm_jroll_base = 5.40067678 K/W` is stale documentation describing an
abandoned calibration variant, not the current reference. It should not be used as a STAR
target.

## Net effect on the qualification case

`cases/wedge_2170_thermal_qualification` (cloned from production `cases/wedge_2170`) already
uses the correct, resolved operator on both counts:
- 100% Q → JellyRoll (via `scalarSemiImplicitSource`, uniform in the JR cell zone)
- Production near-ideal bottom contact (unmodified `thicknessLayers`/`kappaLayers` from the
  production case, R≈1.8 mΩ·K/W)

No further case changes are required for items 1–2; this document formalizes what was already
built.

## Addendum — `wallHeatFlux` function object found inconsistent with energy conservation

While building the clean reference CSV export (`cases/wedge_2170_thermal_qualification/export_clean_reference_csv.py`),
a `wallHeatFlux`+`surfaceFieldValue(areaIntegrate)` function-object pair on the two
`externalWallHeatFluxTemperature` patches (`shell_outerSurface_rotated`, `capOuterSurface_rotated`)
was found to over-report boundary heat loss by a factor of ~8 relative to energy conservation:
integrating it over the 100–300s relaxation window gives −656J, while the (independently,
~1% hand-calc-validated) stored-energy trace only decreases by 80.5J over the same window.
The reported `total_boundary_heat_loss_J_cumulative` column in the exported CSV is therefore
derived from conservation closure (`Q_in_cumulative − stored_energy`), not from the raw
`wallHeatFlux` integral, which is retained in the CSV only as
`wallheatflux_raw_W_DIAGNOSTIC_ONLY`. Root cause not diagnosed (candidate: how `wallHeatFlux`
reconstructs flux for a mixed/Robin-type `externalWallHeatFluxTemperature` BC vs. the
solver's own applied convective flux) — flagged for follow-up, not blocking any of the 5
items requested this session.
