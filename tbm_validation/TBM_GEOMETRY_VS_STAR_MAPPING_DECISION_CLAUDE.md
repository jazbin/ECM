# TBM Geometry vs STAR Mapping Decision

**Date:** 2026-09-23
**Branch:** claude/openfoam-star-equivalence-2026-09-17
**Evidence base (read-only):** `OPENFOAM_GEOMETRY_TOPOLOGY_TARGET.md`, `TBM_EXISTING_STEP_TOPOLOGY_AUDIT.md`, `TBM_GEOMETRY_DOF_MATRIX.md`, `STAR_CLIENT_EQUIVALENCE_TEST_PLAN.md`, `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`, `artifacts/equivalence/robert_s0/README_FOR_ROBERT.md`. No new B-Rep analysis performed; no canonical ledger modified.

---

## Classification table

| Mismatch | Class | Reason | S0 evidence needed | TBM change required now? |
|---|---|---|---|---|
| JR OD mismatch | **A** | JR OD 17.88 mm vs OF 20.63 mm: ~25% less cross-sectional area → ~25% wrong JR thermal mass. No STAR Region/material/interface mapping compensates for a wrong thermal mass. This is the only confirmed-A item independent of S0 outcome. | None — A regardless of S0 | YES (RAD-C field identification). Defer actual TBM regeneration until after S0-B to avoid regenerating a geometry that may also need contact-topology corrections. |
| Can ID/OD mismatch | **A** (ID) / **D** (OD) | Can ID = 18.0 mm drives the 0.059504-mm radial gap; OF target requires Can ID = JR OD = 20.627 mm (zero-gap contact). The OD mismatch (20.9 vs 21.09 mm) changes outer BC area by <1% — not operator-relevant. Operative Can-ID control is still OPEN (RAD-A unrun); exact-contact feasibility (generated JR OD = generated Can ID) has not been tested. F-series failure was caused by JR OD >> available Can OD (~18 mm) — an invalid radial combination, not a test of zero clearance; JR OD = Can ID construction remains OPEN. RAD-A is required to identify the Can-ID field and test exact-contact constructibility. | S0-B (if STAR bridges the gap, RAD-A becomes dimensional cleanup; if not, RAD-A and exact-contact test are the geometry route). RAD-A needed regardless of S0-B outcome. | YES for RAD-A (field identification + exact-contact feasibility). Can OD: NO. |
| Mandrel + annular JR | **C** | Mandrel-JR contact is a coincident cylindrical face (OD = JR inner radius = 3.000 mm). Whether STAR builds a thermal interface there is unknown. If S0-B confirms interface and S0-C confirms thermal material independence → **B** (assign Mandrel JR properties + ideal coupling + include in heat-source zone; Mandrel has no documented electrical role so S0-C path should be unencumbered). If no interface built → **A** (remove Mandrel to restore full-solid JR). | S0-A (Mandrel Region volume vs STEP 1840.9 mm³ confirms no clipping), S0-B (Mandrel↔Jellyroll interface), S0-C (Mandrel thermal material assignable without electrical side-effect) | NO — pending S0-B/C |
| 13-solid decomposition | **C** | Reducing 13 STAR Regions to 3 effective thermal zones requires per-region electrical/thermal independence (S0-C) and bottom-stack path suppression (S0-D). If both pass → **B** (material + interface mapping achieves 3-zone thermal operator without geometry change). If either fails → assess which bodies force geometry change. | S0-C, S0-D | NO |
| JR/Can radial gap | **C** | 0.059504-mm gap; S0-B item 1 (Can↔Jellyroll interface) addresses the STAR-side route — if STAR builds a gap-tolerant interface → **B** (set contact resistance to zero). If STAR does not bridge it, a TBM geometry route may also exist: Can-ID operative control is still OPEN (RAD-A), and generated JR OD = generated Can ID has never been isolated and tested (F-series failure was JR OD >> available Can OD — an invalid radial combination, not a test of zero clearance). Both routes remain in play. | S0-B (Can↔Jellyroll interface — exists? type? contact resistance settable?). RAD-A (Can-ID control identification) is needed regardless of S0-B outcome. | NO — S0-B and RAD-A inform each other; neither gates the other |
| Mirrored end stacks | **C** | Bottom stack has no OF target domain. Option D (explicit interface resistance at Can-JR bottom + thermal path suppression of bottom hardware) is the planned reduction. Requires S0-D to confirm path suppression is feasible while preserving −Tab Parts electrical role. If S0-D passes → **B**. If S0-D fails → **A** (bottom geometry change required). | S0-D (D1–D4 suppression mechanisms; −Tab chain must stay electrically intact) | NO — pending S0-D |
| Localized Root contact | **C→A** | Audit confirms zero recovered common-face area at Root-JR tangent contact. Even with zero contact resistance, if the Root-JR interface area is negligible the heat path from JR to the Cap-material zone is thermally severed — no material mapping fixes that. S0-B is the deciding evidence. If STAR builds a meaningful full-face interface at Root-JR → **B** achievable. If interface area is negligible → **A** (full-area contact geometry required). | S0-B (+Tab Root↔Jellyroll interface: does it exist? what area/type does STAR assign?) | UNKNOWN — depends on S0-B |
| Missing full-area JR top contact | **C→A** | Same root cause as localized Root contact. OF requires full-disc ideal contact at JR top (area 3.325×10⁻⁴ m²); T06 provides only the Root bridge; Stem and all larger bodies are 0.022–0.159 mm from JR top. Quantitative equivalence cannot be achieved if STAR's Root-JR interface area is much smaller than the OF disc area. | S0-B (same as above — Root-JR interface area is the key number) | UNKNOWN — depends on S0-B |
| Missing integral Can bottom | **C→A** | No Can bottom disc in T06; OF's full-disc bottom interface (area 3.325×10⁻⁴ m², explicit resistance 6.015×10⁻⁷ m²·K/W) has no geometric equivalent. Option D needs a hookable Can-JR interface at the bottom. Viable paths: (a) radial Can-JR interface from S0-B (apply resistance to its bottom portion); (b) −Tab Root-JR bottom interface if it has contact area. If S0-B shows both paths have negligible area → **A** (Can bottom disc required). | S0-B (Can↔Jellyroll and −Tab Root↔Jellyroll interfaces), S0-D (interface resistance settable at those contacts?) | UNKNOWN — depends on S0-B and S0-D |
| Thin EndPlate vs OpenFOAM Cap | **B** | Top stack (Root→Stem→Washer→Post→EndPlate) can be assigned Cap material properties (k=(0.01,0.01,0.1), ρ=1447.2, c_p=500). The aggregate thermal resistance and capacitance of the chain differ from OF's single 4.678-mm thick Cap disc, but that is a quantitative question resolved by Test A, not a topology blocker. Conditioned on S0-C passing (electrical role retained with near-insulating thermal material). | S0-C (can EndPlate/Post/Washer retain +Tab Parts electrical role while carrying Cap-equivalent thermal conductivity?) | NO |
| Can/EndPlate overlap | **C** | S0-A directly tests whether STAR clips the 5.272 mm³ per-end volumetric Can-EndPlate overlap when building Regions. If clipped → **D** (not operator-relevant; STAR resolves it). If preserved → **B** (EndPlate thermal volume is small; material mapping absorbs the overlap without significant operator error). | S0-A (EndPlate Region volume vs STEP volume 20.414 mm³; Can Region volume vs STEP 6202 mm³) | NO |
| Overlapping/filled Can STEP body | **C** | S0-A tests whether STAR auto-booleans the Can body's overlap with JR-occupied radial space. If STAR clips to non-overlapping sub-volumes → **B** (piecewise material assignment to the resulting sub-volumes is sufficient). If overlap is preserved in the computational Region → **A** (3-way piecewise split within a single body is not standard STAR; requires separate geometry bodies). | S0-A (Can Region volume; does STAR produce a separate JR-coincident sub-region from the Can body?) | UNKNOWN — depends on S0-A |
| Symmetric JR axial placement | **D** | After valid end-stack and contact-interface mapping (Option D for bottom, Cap-material for top), the 2.445-mm symmetric Can overhang vs OF's 0.23132-mm asymmetric bottom does not independently affect the thermal operator. The relevant physics are fully captured by the contact-interface strategy. | None | NO |

---

## Key questions

**Q1 — Can Mandrel + annular JR behave as one OpenFOAM JR while electrical/RCR semantics remain valid?**

Thermally YES, conditioned on three things: (a) both bodies assigned JR material properties, (b) STAR builds a Mandrel-JR cylindrical interface that can be set to ideal coupling (S0-B), (c) Mandrel is included in the heat-source zone to match OF's uniform-JR heat assignment. Mandrel has no documented electrical role and is not a Core or Tab Part, so S0-C's electrical/thermal independence question is likely unencumbered for this body. Electrical and RCR semantics reside entirely in the JellyRoll Region and remain unaffected.

**Q2 — Can the top stack reproduce the OpenFOAM full-disc Cap operator despite localized JR contact?**

UNLIKELY without geometry change at current Root geometry. The audit confirms zero recovered common-face area at +Tab Root-JR contact; Stem and all larger bodies are 0.022–0.159 mm from JR. Even if Root-JR contact resistance is set to zero, heat transfer from JR to the Cap-material zone is bottlenecked by the Root contact area, which is expected to be much smaller than the OF full-disc area (3.325×10⁻⁴ m²). S0-B is the deciding evidence: if STAR builds a full-face planar interface at Root-JR despite the zero STEP common-face area, **B** is achievable; otherwise this is **A** and full-area top contact geometry is required.

**Q3 — Can S0-D reproduce the bottom full-disc JR↔Can path, or does missing contact area force geometry change?**

Unresolvable without S0-B first. Option D requires an interface hook on which to place the contact resistance (6.015×10⁻⁷ m²·K/W). In T06 there is no Can bottom disc and the radial gap means no direct Can-JR bottom face. The only candidate hooks are: (a) the radial Can-JR interface at the bottom of the Can wall (exists only if S0-B shows gap bridgeable); (b) a −Tab Root-JR interface at the JR bottom face (only if S0-B shows meaningful contact area). If S0-B shows both have negligible or zero area, Option D has no hook and a Can bottom disc is required (A). If either hook exists, S0-D then tests whether the resistance can be placed there while suppressing the metallic bottom-hardware shortcut.

**Q4 — Can STAR couple the radial JR/Can surfaces across the existing 0.059504-mm gap equivalently?**

Unknown. S0-B item 1 (Can↔Jellyroll interface) addresses the STAR-side route — whether STAR builds a gap-tolerant interface across the 0.059504-mm gap. A TBM geometry route also remains open: operative Can-ID control has not been identified (RAD-A unrun) and generated JR OD = generated Can ID has never been tested in isolation. F-series failure established that JR OD >> available Can OD fails; it does not establish that zero-clearance construction is impossible. Both routes must be pursued.

---

## Sequencing decision

**S0 before GEO/RAD: YES**

S0-C/D determine whether the 13-solid material-mapping reduction is achievable without topology changes — if those fail, scope of geometry corrections expands immediately. S0-B addresses one route to zero radial coupling (STAR gap-tolerant interface); RAD-A addresses the parallel TBM geometry route (Can-ID field identification + exact-contact feasibility). S0 and RAD-A are not strictly ordered relative to each other; S0 is prioritized because it uses the already-prepared T06 package (no new TBM generation) and its C/D answers are prerequisites for the full equivalence test plan regardless of the radial question. Running GEO/RAD geometry variations before S0-C/D return risks designing them against a Region/material mapping that S0 proves infeasible.

---

## Deferred geometry tests

| Test | Deferred until | Reason for deferral |
|---|---|---|
| RAD-C: JR OD field identification | After S0 | Confirmed A; but regenerating geometry before S0-B may produce a variant that also needs contact-topology fixes — combine into one package |
| RAD-A: Can ID field identification + exact-contact feasibility | After S0 (parallel route to S0-B) | Can-ID operative control is OPEN; exact-contact (JR OD = Can ID) has not been tested; F-series did not isolate this. RAD-A is needed regardless of S0-B outcome — either as geometry route (if S0-B negative) or dimensional correction (if S0-B positive). |
| RAD-B: Can OD field identification | Low priority | <1% BC area effect (D); fold into RAD-A/C package |
| Full-area top contact geometry test | After S0-B Root-JR result | Only needed if S0-B shows negligible Root-JR interface area (C→A trigger) |
| Can bottom disc geometry test | After S0-B and S0-D | Only needed if both gap and Root-JR hooks prove insufficient for Option D |
| Axial asymmetry/envelope correction | After end-stack mapping decision | D classification — not independently needed unless Option D bottom strategy requires it |
| Offline Root-JR contact area check (existing STEP) | Can run now — no Robert needed | Targeted B-Rep check on Root-JR common edge/face; prepares interpretation of S0-B; does not require new TBM generation |

---

## Next Robert package

Contingent on S0 return:

**RAD-A package (parallel to S0, send after S0 dispatched):** Can-ID field identification + exact-contact feasibility probe (JR OD = Can ID). Does not depend on S0-B result. Can be combined with RAD-C (JR OD) and RAD-B (Can OD) in one geometry package.

**After S0 returns — Path 1 (S0-B: gap unbridgeable AND Root contacts negligible):** Add top-contact geometry (full-disc cap body) + Can bottom disc to the RAD-A/C package if not yet sent, or as a follow-on geometry package.

**After S0 returns — Path 2 (S0-B: gap bridgeable AND Root/bottom contacts viable, S0-C/D pass):** Send Test A thermal operator package — material/interface mapping per `BDS_TO_OPENFOAM_THERMAL_MAPPING.md` Option D, existing T06 geometry unmodified. RAD-A/C still required for JR OD and Can-ID dimensional correction but can run in parallel.

**After S0 returns — Path 3 (mixed):** Targeted geometry correction for failing items only, combined with RAD-A/C.
