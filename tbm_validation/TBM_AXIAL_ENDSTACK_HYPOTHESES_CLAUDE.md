# TBM Axial and End-Stack Hypotheses — Independent Audit

These hypotheses are analysis input only. They do not modify or supersede `TBM_HYPOTHESIS_LEDGER.md`.

## Hypotheses

| ID | Hypothesis | Status | Confidence | Evidence and limit |
|---|---|---|---|---|
| AXIAL-001 | Successful H/T construction places the Can symmetrically about the JR axial midpoint. | CONFIRMED for existing cases | high | H: JR 0..57, Can -6.5..63.5. T: JR 0..65.11, Can -2.445..67.555. Both have equal top/bottom overhang. Control law outside these cases remains unknown. |
| AXIAL-002 | Can axial height and end positions are independent of tab surplus within each H/T family. | CONFIRMED | high | Can height is 70 mm and EndPlate outer positions are invariant across all successful cases in each family. |
| AXIAL-003 | Both-side surplus changes partition the space inside a fixed end envelope rather than translating the full stack. | CONFIRMED | high | T01→T06: Root/Stem grow, Washer moves outward, Post shortens, and EndPlate stays fixed. H11/H12 show the same construction pattern. |
| AXIAL-004 | T06/T07/T08 share a full-geometry plateau, not merely a Tab Stem bounding-box plateau. | CONFIRMED | high | Every measured extent, volume, pair distance, and contact relationship is identical. |
| AXIAL-005 | One-sided H changes are masked by the unchanged large opposite-side/control surplus or by a coupled clamp. | SUPPORTED | high | H01-H04 retain negative +8 mm; H05-H08 retain positive +9 mm; all eight geometries are identical. Pure per-polarity independent extrusion is refuted. |
| AXIAL-006 | The one-sided masking rule is specifically `max(pos,neg)`. | OPEN | low | Max, another combined quantity, saturation, or non-consumption of the isolated geometry field all predict the observed H results. Existing cases cannot distinguish them. |
| AXIAL-007 | T06 saturation is caused solely by an intrinsic maximum Root/Stem length. | OPEN | low | Plateau is consistent, but the simultaneous minimum Post length and fixed envelope provide competing explanations. |
| AXIAL-008 | T06 saturation is caused solely by collision with Washer/Post/EndPlate. | OPEN | low | Internal interfaces meet but do not overlap; available data do not reveal whether a collision constraint, minimum Post length, or Builder clamp is active. |
| AXIAL-009 | T06 saturation is caused by the fixed package/end-space envelope, possibly combined with a minimum Post length or maximum Root/Stem extent. | SUPPORTED | medium | EndPlate and Can remain fixed while Post shortens through T06, then the entire internal partition freezes. Evidence favours a constrained envelope but cannot identify the Siemens rule. |
| ENDSTACK-001 | Both ends have a continuous localized solid path from JR to Can/end closure. | CONFIRMED | high | JR touches Root; Root touches Stem; Stem touches Washer; Washer touches Post; Post touches EndPlate; EndPlate overlaps Can in all 17 cases. |
| ENDSTACK-002 | A positive full-area axial gap separates JR from all generated end solids. | REFUTED | high | Root touches JR on both ends in every successful STEP. There is no completely empty separating slab. |
| ENDSTACK-003 | The substantial end bodies directly contact JR as required by the OpenFOAM operator. | REFUTED | high | Stem, Washer, Post, and EndPlate all have positive minimum distance from JR. Only the small Root touches; the recovered Root common-face area is zero. |
| ENDSTACK-004 | Current Builder topology is top/bottom symmetric. | CONFIRMED | high | Every direct JR distance and every adjacency in the end chain is symmetric to numerical precision. |
| ENDSTACK-005 | A TBM control can suppress the bottom stack while retaining an OpenFOAM-equivalent top Cap. | NOT YET CHARACTERIZED | low | No successful returned STEP demonstrates top-only topology. Candidate fields must first be identified offline, then tested at runtime. |
| CONTACT-001 | T06 has a true JR↔Can radial clearance. | CONFIRMED | high | Exact minimum distance 0.0595040936 mm; Boolean common volume zero. |
| CONTACT-002 | Root contact is equivalent to a finite full-face thermal interface. | REFUTED as full-face; finite local area OPEN | high / low | Distance is zero, but Boolean common volume and recovered common-face area are zero. Geometry proves touch, not an operator-equivalent contact area. |
| CONTACT-003 | Can and EndPlate merely touch at the package end. | REFUTED | high | Each EndPlate overlaps Can by 5.272108319 mm³ in every successful case. |
| CONTACT-004 | The current Can/EndPlate construction can represent the OpenFOAM planar Can↔Cap annulus without topology change. | OPEN, currently unsupported | low | OpenFOAM has coincident zero-volume interface; current STEP has volumetric overlap and mirrored plates. Production radial changes could alter the overlap but cannot be assumed to fix topology. |

## T06 saturation assessment

The evidence supports a combination of fixed package/end-space envelope and an internal Builder limit. It does not distinguish among:

- an intrinsic Root/Stem maximum;
- a minimum permissible Internal-Post length;
- collision/contact logic at Washer/Post/EndPlate;
- another Builder-controlled axial clamp;
- a compound rule using more than one of these.

T06 is therefore a good **frozen identification baseline**, because larger inputs add no geometry and T06 imports successfully. It is not evidence that its end topology is production-correct.

## What T06 freezes

- JR nominal height 65.11 mm and its axial origin;
- 70-mm Can envelope centred around the JR;
- both 0.059504-mm EndPlates and their 5.272108-mm³ overlaps with Can;
- the symmetric localized contact chains;
- saturated Root/Stem extents, Washer positions, and 1.163016-mm Posts;
- 13-solid authored topology.

## What remains mismatched

- positive radial JR/Can clearance;
- annular JR plus Mandrel instead of a full solid JR;
- no integral Can bottom wall;
- localized Root bridges instead of full-area top and bottom contacts;
- mirrored bottom EndPlate and auxiliary stack;
- top EndPlate much thinner and closer to the package end than the OpenFOAM Cap;
- volumetric Can-EndPlate overlap instead of a planar annular interface.

## Canonical campaign gaps

The current canonical campaign is incomplete because it promotes the radial gate as the primary remaining geometry problem. RAD-A/B/C can identify three diametric mappings, but they do not test axial placement, end-envelope partition, top-only versus mirrored topology, full-area JR end contacts, integral Can bottom construction, Mandrel removal, or Can-EndPlate overlap. Those are independent operator-level DOFs.
