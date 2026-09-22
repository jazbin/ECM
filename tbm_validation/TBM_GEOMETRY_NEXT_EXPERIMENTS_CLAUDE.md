# Complete-Geometry Next Experiments — Independent Recommendation

This recommendation does not modify `TBM_NEXT_EXPERIMENTS.md` and does not authorize TBM generation. It ranks experiments by information value for reproducing the complete OpenFOAM geometry/topology operator.

## Decision on RAD-A/B/C

**PARTLY.** Keep the three isolated radial questions and their T06 baseline, but do not treat RAD-A/B/C as a sufficient immediate production campaign. They resolve Can ID, Can OD, and JR OD only. A diameter-correct 13-solid cell would still have the wrong central topology, axial contacts, bottom construction, mirrored end stack, and Can-EndPlate overlap.

No additional surplus tests should precede them. T01-T08 already establish the internal axial response through the full T06 plateau.

## Information-value ranking

| Rank | Unknown DOF | Why it limits equivalence | Best next evidence |
|---:|---|---|---|
| 1 | top/bottom end topology and full-area JR contacts | Current geometry has localized Root bridges, two EndPlates, and no integral Can bottom; this changes the operator even with perfect diameters | offline identify candidate Builder/PCD topology fields, then one isolated end-topology STEP test |
| 2 | central void / Mandrel suppression | Current JR is annular and separated into Mandrel + JR; OpenFOAM has one full cylinder | use existing valid no-/different-Mandrel reference as donor, then one isolated STEP test |
| 3 | axial Can/end-envelope control | T06 has symmetric 2.445-mm overhangs; OpenFOAM has 0.23132-mm bottom structure, JR flush at the Can-wall top, and a 4.67870-mm top Cap | isolated external-envelope height test from T06, measuring every axial interface |
| 4 | Can ID and radial gap | determines Can wall thickness and JR radial contact | RAD-A, followed by exact-contact setting only after mapping is known |
| 5 | Can OD | required external diameter and Can-Cap radial extent | RAD-B |
| 6 | JR OD | required full target volume and zero radial gap | RAD-C |
| 7 | Can-EndPlate overlap persistence | current 5.272108-mm³ overlap is not the OpenFOAM planar annulus | measure automatically in every returned STEP; isolate only if it persists after topology/radial changes |

The first three rank above radial tuning because failure to control them makes an OpenFOAM-equivalent three-domain partition impossible regardless of diameter accuracy.

## Offline work before using Robert capacity

1. Search existing TBMs and Siemens reference variants for fields/configurations that change Mandrel existence and polarity-specific EndPlate/Washer/Post creation. Record only candidates with a known successful import lineage.
2. Reconcile the August one-field TBM deltas with its returned STEP measurements to strengthen the priors for `m_dRepCanXDim/YDim`, `m_dintDiameter`, and `m_dJellyrollThickness_mm`.
3. Define one standard STEP measurement sheet for every future return: 13-body name check, JR/Can radii, Mandrel volume, axial extents, JR distances, Can-EndPlate overlap, and top/bottom contact graph.

These steps do not require STAR and prevent spending runs on fields whose existing evidence already answers the question.

## Recommended minimum next Robert campaign

Use T06 as the frozen root/import baseline. Change one causal field or one coherent topology configuration per case.

| Order | Test | Single question | Required return |
|---:|---|---|---|
| 1 | GEO-END | Can a known-valid candidate configuration remove the bottom auxiliary stack or produce a top-only Cap while retaining import? | import result + STEP; full top/bottom body/contact graph |
| 2 | GEO-MANDREL | Can a known-valid reference-derived Mandrel configuration produce one full JR domain without a separate central solid/void? | import result + STEP; Mandrel/JR radii and volumes |
| 3 | GEO-AXIAL | What does the isolated external package-height/envelope driver change: Can ends, EndPlates, Posts, or JR placement? | import result + STEP; all axial extents and JR distances |
| 4 | RAD-A | Does package `m_dintDiameter` control Can ID on T06? | Can ID/OD and JR OD |
| 5 | RAD-B | Do REPORT `m_dRepCanXDim/YDim` control Can OD, or are they regenerated? | Can ID/OD and JR OD |
| 6 | RAD-C | Does `m_dJellyrollThickness_mm` control JR OD on T06? | JR OD and unchanged Can dimensions |

This six-return tranche is the minimum campaign that addresses the complete target while preserving one-factor interpretation. GEO-END and GEO-MANDREL require offline candidate selection first; do not invent or send those TBMs until a valid reference-backed control is identified.

After these six results:

1. construct a positive-clearance production candidate using the identified radial controls and the best available topology controls;
2. measure the entire contact graph and Can-EndPlate overlap, not only diameters;
3. only then attempt exact JR/Can radial contact;
4. proceed to thermal material/operator tuning only after the geometry partition is either equivalent or its deliberate deviations are documented.

## What existing T01-T08 already answer

- both-side surplus changes Root/Stem, moves Washer, and shortens Post;
- Can, EndPlate, and JR positions remain fixed within the T family;
- top and bottom responses are symmetric;
- all internal geometry plateaus by T06;
- more surplus than T06 has zero geometry information value.

No new axial-surplus sweep is recommended.

## Campaign falsifiers

- If no reference-backed configuration can remove the Mandrel/central subdivision, exact three-domain equivalence may be unavailable through TBM alone.
- If GEO-END cannot break mirrored topology or create full-area JR end contacts, a geometry-equivalent TBM may be unavailable even when radial dimensions match.
- If GEO-AXIAL changes only the outer envelope while preserving centred JR placement, a separate axial-placement/topology control remains necessary.
- If RAD fields change multiple radii together, the radial mapping must be reformulated before a production candidate.
