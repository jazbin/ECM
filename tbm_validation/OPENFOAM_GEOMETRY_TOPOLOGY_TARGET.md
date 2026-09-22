# OpenFOAM Geometry and Topology Target

**Status:** authoritative geometry target for TBM equivalence
**Reference case:** `cases/wedge_2170`
**Authority order:** raw `polyMesh`, `regionProperties`, and `0/*/T` files outrank all narrative summaries.

## Normalized geometry

Coordinates use the OpenFOAM axis `z`; the cylindrical axis is `(0,0,z)` and the centre is `(0,0)` in every transverse plane.

| Domain | Radial geometry | Axial range (mm) | Height (mm) | Neighbours |
|---|---:|---:|---:|---|
| JellyRoll | solid cylinder, radius 10.31368; OD 20.62736; no central void | 0.23132 to 65.34130 | 65.11000 | Can radially and at bottom; Cap at top |
| Can (`shell_rotated`) | outer radius 10.545; inner radius 10.31368 above the bottom; OD 21.09; ID 20.62736; radial wall 0.23132 | 0 to 65.34130 | 65.34130 | JR radial/bottom; Cap at top rim |
| Can bottom | solid disc to radius 10.545 | 0 to 0.23132 | 0.23132 | JR over the central disc area |
| Cap | solid top disc, radius 10.545; OD 21.09 | 65.34130 to 70.02000 | 4.67870 | JR over central disc area; Can over annulus |

The Can has no top wall independent of the Cap. The Cap is top-only and is not mirrored at the bottom.

## Required interface topology

Areas below are direct polygon-face sums from the paired raw boundary patches. The ideal-cylinder values differ slightly because the mesh represents circles with planar polygon faces; the mesh areas are the operator-relevant values.

| Interface | Geometry | Raw mesh area (m²) | Gap | Thermal resistance in `0/*/T` |
|---|---|---:|---:|---|
| JR ↔ Can radial | coincident cylindrical surfaces at `r=10.31368 mm`, `z=0.23132..65.34130 mm` | 0.00421395331 | 0 | none; coupled ideal contact |
| JR ↔ Can bottom | coincident planar discs at `z=0.23132 mm`, `r=0..10.31368 mm` | 0.000332483456 | 0 | explicit layer: thickness `6.01519461276695e-7 m`, kappa `1 W/(m K)` |
| JR ↔ Cap top | coincident planar discs at `z=65.34130 mm`, `r=0..10.31368 mm` | 0.000332483456 | 0 | none; coupled ideal contact |
| Can ↔ Cap | coincident **planar annulus** at `z=65.34130 mm`, `r=10.31368..10.545 mm` | 0.0000150814413 | 0 | none; coupled ideal contact |

The previous description of Can ↔ Cap as a negligible axial band is incorrect. The raw face coordinates and paired 36-face patches prove a planar annular interface.

All three physical regions meet without a geometric gap. `mappedWall` is the mesh-coupling mechanism; the paired patches occupy the same geometric interfaces. Radiation is disabled on every internal interface.

For the bottom interface, the input layer gives area-specific resistance `6.01519461276695e-7 m² K/W`. Using the discrete patch area gives approximately `0.001809 K/W`; this is the resistance encoded by the actual boundary field and is not the separately documented 5.4 K/W value.

## Contact graph

```text
                     full central disc
              JellyRoll ─────────────── Cap (top only)
                  │                         │
      radial wall │                         │ planar annulus
                  │                         │
                  └──────── Can ────────────┘
                           │
                 full bottom-disc contact
```

The target operator therefore requires all of the following simultaneously:

- full-area JR top contact to a 4.67870-mm top Cap;
- full-area JR bottom contact to the 0.23132-mm Can bottom, with the explicit thin thermal-resistance layer;
- zero-gap radial JR-to-Can contact;
- a top planar Can-to-Cap annulus;
- no bottom Cap domain.

## Domains and gaps that do not exist

The OpenFOAM region list contains exactly `jellyRoll_rotated`, `shell_rotated`, and `cap_rotated`. It has no separate:

- Mandrel domain;
- central hole;
- bottom Cap domain;
- Washer;
- EndPlate;
- Internal Post;
- Tab Root thermal domain;
- Tab Stem thermal domain;
- free axial air-gap region.

Any TBM-generated auxiliary solid can reproduce this operator only if it is removed, merged into the appropriate three-domain partition without changing the interfaces, or shown to be excluded from the STAR thermal operator. That equivalence has not been established by geometry alone.

## Evidence trace

- Region membership: `constant/regionProperties`.
- Extents and radii: `constant/{jellyRoll_rotated,shell_rotated,cap_rotated}/polyMesh/points`.
- Interface names, face counts, and ranges: the three `polyMesh/boundary` files.
- Interface areas: direct integration of the raw `polyMesh/faces` polygons using the raw points.
- Contact resistance and coupling: `0/{jellyRoll_rotated,shell_rotated,cap_rotated}/T`.
