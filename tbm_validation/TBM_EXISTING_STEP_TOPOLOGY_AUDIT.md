# Existing Successful STEP Topology Audit

**Scope:** all 17 successful Robert-returned H/T STEP files in `in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip`.
**Method:** direct OCCT B-Rep transfer, optimal untessellated bounding boxes, volume properties, `BRepExtrema_DistShapeShape`, and targeted Boolean common operations. Units are millimetres and mm³. No screenshot measurement is used.

The successful population is exactly H01-H08, H11-H13, T01, T04-T08. Every file contains the same 13 authored solids:

`Mandrel`, `Jellyroll`, `Can`, and positive/negative `Tab Root`, `Tab Stem`, `Washer`, `EndPlate`, and `Internal-Post`.

## T06 body inventory

The STEP axis is global Y. Bounding boxes include the STEP tolerance envelope of approximately ±0.00001 mm; nominal planar coordinates are stated in the text where useful.

| Body | Axial min..max (mm) | Radial extent (mm) | Volume (mm³) | Minimum distance to JR (mm) | Minimum distance to Can (mm) |
|---|---:|---:|---:|---:|---:|
| Mandrel | -0.000010..65.110010 | radius 3.000000 | 1840.941879 | 0 (tangent) | 6.000000 |
| Jellyroll | -0.000010..65.110010 | radii 3.000000..8.940496; OD 17.880992 | 14509.172189 | — | 0.059504 |
| Can | -2.445010..67.555010 | radii 9.000000..10.450000; ID 18.0, OD 20.9 | 6202.053677 | 0.059504 | — |
| + Tab Root | 65.100918..65.177232 | max radius 3.146486 | 0.007101 | 0 | 5.853514 |
| + Tab Stem | 65.165723..66.275422 | max radius 3.134904 | 0.067594 | 0.058150 | 5.864616 |
| - Tab Root | -0.060531..0.002381 | max radius 8.816060 | 0.006143 | 0 | 0.179889 |
| - Tab Stem | -1.163269..-0.057877 | max radius 8.805268 | 0.047398 | 0.058150 | 0.191150 |
| + Washer | 66.272986..66.332510 | max radius 8.940496 | 14.942384 | 1.162996 | 0.059504 |
| - Washer | -1.222510..-1.162986 | max radius 8.940496 | 14.942401 | 1.162996 | 0.059504 |
| + Internal-Post | 66.332490..67.495506 | radius 1.500000 | 8.220734 | 1.935073 | 7.500000 |
| - Internal-Post | -2.385506..-1.222490 | radius 1.500000 | 8.220734 | 1.935073 | 7.500000 |
| + EndPlate | 67.495486..67.555010 | max radius 10.450000 | 20.414056 | 2.385496 | 0; overlap |
| - EndPlate | -2.445010..-2.385486 | max radius 10.450000 | 20.414056 | 2.385496 | 0; overlap |

The generated Can is a 70-mm annular tube with 1.45-mm radial thickness. It does not contain an OpenFOAM-like solid bottom disc. A 0.059504-mm EndPlate closes each end and overlaps the Can by `5.272108319 mm³` per end.

## Exact axial relationship tables

`TOUCHING` means exact minimum distance zero and zero common volume. `POSITIVE GAP` reports the exact whole-solid minimum distance. No JR overlap was found for any end component. The nearest end solid is always the Tab Root, which touches the JR; the Mandrel also touches the annular JR along its inner boundary but is not an end-stack component.

### Positive/top end

| Successful cases | JR axial min..max | Nearest end solid | JR→Root | JR→Stem | JR→Washer | JR→Post | JR→EndPlate | JR→Can |
|---|---:|---|---|---|---|---|---|---|---|
| H01-H08, H13 | -0.000010..57.000010 | +Root | TOUCHING | POSITIVE GAP 0.159525 | POSITIVE GAP 3.190496 | POSITIVE GAP 3.579455 | POSITIVE GAP 6.440496 | POSITIVE GAP 0.059504, radial |
| H11 | -0.000010..57.000010 | +Root | TOUCHING | POSITIVE GAP 0.035000 | POSITIVE GAP 0.700000 | POSITIVE GAP 1.681323 | POSITIVE GAP 6.440496 | POSITIVE GAP 0.059504, radial |
| H12 | -0.000010..57.000010 | +Root | TOUCHING | POSITIVE GAP 0.100000 | POSITIVE GAP 2.000000 | POSITIVE GAP 2.547853 | POSITIVE GAP 6.440496 | POSITIVE GAP 0.059504, radial |
| T01 | -0.000010..65.110010 | +Root | TOUCHING | POSITIVE GAP 0.022250 | POSITIVE GAP 0.445000 | POSITIVE GAP 1.582569 | POSITIVE GAP 2.385496 | POSITIVE GAP 0.059504, radial |
| T04 | -0.000010..65.110010 | +Root | TOUCHING | POSITIVE GAP 0.035000 | POSITIVE GAP 0.700000 | POSITIVE GAP 1.681323 | POSITIVE GAP 2.385496 | POSITIVE GAP 0.059504, radial |
| T05 | -0.000010..65.110010 | +Root | TOUCHING | POSITIVE GAP 0.050000 | POSITIVE GAP 1.000000 | POSITIVE GAP 1.836450 | POSITIVE GAP 2.385496 | POSITIVE GAP 0.059504, radial |
| T06-T08 | -0.000010..65.110010 | +Root | TOUCHING | POSITIVE GAP 0.058150 | POSITIVE GAP 1.162996 | POSITIVE GAP 1.935073 | POSITIVE GAP 2.385496 | POSITIVE GAP 0.059504, radial |

### Negative/bottom end

| Successful cases | JR axial min..max | Nearest end solid | JR→Root | JR→Stem | JR→Washer | JR→Post | JR→EndPlate | JR→Can |
|---|---:|---|---|---|---|---|---|---|---|
| H01-H08, H13 | -0.000010..57.000010 | -Root | TOUCHING | POSITIVE GAP 0.159525 | POSITIVE GAP 3.190496 | POSITIVE GAP 3.579455 | POSITIVE GAP 6.440496 | POSITIVE GAP 0.059504, radial |
| H11 | -0.000010..57.000010 | -Root | TOUCHING | POSITIVE GAP 0.035000 | POSITIVE GAP 0.700000 | POSITIVE GAP 1.681323 | POSITIVE GAP 6.440496 | POSITIVE GAP 0.059504, radial |
| H12 | -0.000010..57.000010 | -Root | TOUCHING | POSITIVE GAP 0.100000 | POSITIVE GAP 2.000000 | POSITIVE GAP 2.547853 | POSITIVE GAP 6.440496 | POSITIVE GAP 0.059504, radial |
| T01 | -0.000010..65.110010 | -Root | TOUCHING | POSITIVE GAP 0.022250 | POSITIVE GAP 0.445000 | POSITIVE GAP 1.582569 | POSITIVE GAP 2.385496 | POSITIVE GAP 0.059504, radial |
| T04 | -0.000010..65.110010 | -Root | TOUCHING | POSITIVE GAP 0.035000 | POSITIVE GAP 0.700000 | POSITIVE GAP 1.681323 | POSITIVE GAP 2.385496 | POSITIVE GAP 0.059504, radial |
| T05 | -0.000010..65.110010 | -Root | TOUCHING | POSITIVE GAP 0.050000 | POSITIVE GAP 1.000000 | POSITIVE GAP 1.836450 | POSITIVE GAP 2.385496 | POSITIVE GAP 0.059504, radial |
| T06-T08 | -0.000010..65.110010 | -Root | TOUCHING | POSITIVE GAP 0.058150 | POSITIVE GAP 1.162996 | POSITIVE GAP 1.935073 | POSITIVE GAP 2.385496 | POSITIVE GAP 0.059504, radial |

Top and bottom distances are symmetric to numerical precision in every successful case.

## Is there an empty axial gap?

**Top:** no completely empty separating slab exists. The +Tab Root touches JR and touches the +Tab Stem. The chain continues by touching through Washer and Internal-Post to EndPlate. However, the Root is a small localized body: the +Stem itself is 0.02225–0.159525 mm from JR depending on case, and Washer/Post/EndPlate are farther away. Most of the JR top face therefore lacks OpenFOAM-like full-area Cap contact.

**Bottom:** the same conclusion holds symmetrically. The -Tab Root provides a localized solid bridge, while the Stem and every substantial downstream body have positive direct distance from JR. There is no OpenFOAM-like full-area JR-to-solid-Can-bottom interface.

The STEP files contain solids only; they do not author an air domain. Geometry therefore proves void space around the localized bridge, not a meshed free-air thermal region. The zero-distance Root relationship also has zero Boolean common volume and zero recovered common-face area, so a finite thermal contact area must not be assumed without a targeted contact-area check or STAR-side topology evidence.

## What changes across cases

| Quantity | Exact observation |
|---|---|
| JR height/position | H cases: nominal `0..57 mm`; T cases: nominal `0..65.11 mm`. Invariant within each family. |
| Can geometry | OD 20.9, ID 18.0, height 70 mm in every successful H/T case. It is centred about the JR: H overhang 6.5 mm per end; T overhang 2.445 mm per end. |
| Mandrel/JR radial topology | invariant across all 17: 3-mm-radius Mandrel plus annular JR. |
| EndPlate positions | invariant within H and within T; surplus does not move the outer end closure. |
| H01-H08, H13 | all 13 bodies are geometrically identical across all measured extents, volumes, distances, and contacts despite different hashes. |
| H11/H12 | both-side changes alter Root/Stem extent, Washer position, and Post length. H11 and H12 are distinct from each other and the saturated H group. |
| T01→T04→T05→T06 | Root/Stem grow; Washer moves away from JR; the Post inner end follows Washer and the Post shortens; the Post outer end and EndPlate remain fixed. The stack does not translate rigidly. |
| T06/T07/T08 | exact full-geometry plateau across every measured solid and contact relationship. |

## H-series masking

Inputs show that H01-H04 vary positive surplus from 0 to 2 mm while negative surplus stays at +8 mm; H05-H08 vary negative surplus from 0 to 2 mm while positive surplus stays at +9 mm. Exact geometry is unchanged in both sequences and matches H13 (+4/+3 mm).

The narrow supported interpretation is that one-sided changes below the unchanged large opposite-side/control setting do not alter generated geometry. Existing results are consistent with all of these mechanisms and do not distinguish them:

- opposite-side maximum dominates a coupled axial construction;
- a max/combined quantity is clamped at a geometric plateau;
- the Builder ignores the isolated field for geometry while still using a coupled validation quantity.

Pure independent per-polarity extrusion is refuted. An intrinsic plateau alone is insufficient to explain H11/H12 unless the plateau input is a coupled quantity, because both-side 0.70 and 2.00 mm do change geometry.

## T06 as baseline and mismatch to OpenFOAM

T06 remains a stable importable baseline for further identification because its full generated geometry is insensitive to additional surplus through T08. It fixes the 13-solid topology, 65.11-mm JR height, 70-mm symmetric Can envelope, end-chain contacts, and saturated internal stack partition.

It is not geometrically equivalent to OpenFOAM:

- JR OD 17.880992 vs 20.62736 mm;
- Can OD 20.9 vs 21.09 mm;
- Can ID 18.0 vs 20.62736 mm;
- 0.059504-mm radial gap vs zero-gap radial contact;
- annular JR plus Mandrel vs full solid JR;
- mirrored end stacks vs top-only Cap;
- localized Root contact vs full-area JR top and bottom contacts;
- 0.059504-mm EndPlate vs 4.67870-mm top Cap;
- annular Can tube plus overlapping EndPlates vs radial Can wall with integral solid bottom and a separate top Cap;
- Can-EndPlate overlap 5.272108 mm³ per end vs coincident, non-overlapping Can-Cap annulus.
