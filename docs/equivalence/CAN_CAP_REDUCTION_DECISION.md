EXACT PIECEWISE UNION SUPPORTED

# Can/Cap Reduction Decision

**Date:** 2026-09-17

## Checklist against repository evidence (`cases/wedge_2170`)

| Test | Result | Evidence |
|---|---|---|
| 1. Identical thermal material properties? | **NO** | Can: ρ=8000, c_p=500 (const), k=16 isotropic. Cap: ρ=1447.2, c_p=500 (const), k=(0.01,0.01,0.1) anisotropic. Densities differ by 5.5×, conductivities differ by 160–1600× and Can is isotropic while Cap is strongly anisotropic. |
| 2. Identical conductivity formulation? | **NO** | Can uses `constIso` (scalar). Cap uses `constAnIso` (full cylindrical tensor). |
| 3. Ideal/no-resistance contact between them? | **YES** | `shell_rotated_to_cap_rotated` / `cap_rotated_to_shell_rotated` patches: `turbulentTemperatureRadCoupledMixed`, no `thicknessLayers`/`kappaLayers` block → ideal contact. |
| 4. No interface-specific heat source? | **YES** | No `fvOptions` in `cap_rotated` or `shell_rotated`; all heat enters via JellyRoll only. |
| 5. No interface-specific BC? | **YES** | Both `T` files show only the coupled patch + the region's own external convective wall; nothing interface-specific. |
| 6. Geometrically contiguous union? | **YES** | Can spans z 0–65.3413mm, Cap spans z 65.3413–70.02mm, both full radius 10.545mm at the shared face — contiguous, no gap, no overlap (confirmed from exact `polyMesh/points` bounding boxes). |

Because test 1 and 2 fail, **deleting the Cap geometry and adjusting Can's ρ/c_p/k to some volume-weighted average is explicitly NOT an exact reduction** — this is precisely the "approximate homogenization" case the governing task calls out and prohibits assuming without derivation. A single averaged conductivity cannot reproduce two materials whose axial conductivity differs by 290× (29 W/mK region-adjacent JR vs Can k_z=16 vs Cap k_z=0.1) while occupying geometrically distinct, differently-shaped volumes (Can wraps JR radially + a thin bottom disc; Cap is a full-radius end disc with no bottom counterpart).

Tests 3–6 pass, which is exactly the condition stated in the governing prompt for an **exact piecewise union**: one STAR assembly/part may represent `Can portion → Can properties, Cap portion → Cap properties` joined by an ideal internal interface, and this is mathematically equivalent to the two-region OpenFOAM operator over the union geometry, even if STAR's GUI shows it as a single region/part.

## Conclusion

**EXACT PIECEWISE UNION SUPPORTED.** A merged STAR "Can+Cap" body/region is acceptable **only if** it carries two distinct material zones (piecewise ρ, c_p, K matching Can and Cap respectively) joined by a zero-resistance internal interface at z=65.3413mm (JR-aligned), reproducing the exact geometric split. A single homogeneous-material merge is **not** supported by this evidence and must not be proposed as equivalent without an explicit, separately-derived and documented homogenization argument (none exists in the repository).

This decision feeds directly into Phase 4 (`BDS_TO_OPENFOAM_THERMAL_MAPPING.md`): since BDS/T06 exports a **single** "Can" solid spanning the full axial extent (see `T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`), that single BDS body must itself be treated as requiring a piecewise material assignment (Can-equivalent properties for the z-range that maps to Ω_Can, Cap-equivalent properties for the z-range that maps to Ω_Cap) rather than one uniform material.
