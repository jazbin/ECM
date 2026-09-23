# ECM Equivalence Contradictions and Stale Claims

**Date:** 2026-09-23
**Branch:** claude/openfoam-star-equivalence-2026-09-17
**Purpose:** Document every known contradiction between source documents, every stale claim whose basis has been updated by new evidence, and every assertion that requires resolution before it can be used as a design input. Listed most-consequential first.

Format: `ID | Claim A (source) | Claim B (source) | Stronger evidence | Canonical resolution | Files to update`

---

## C01 — f_cap: 0 (executable) vs 0.034 (documentation)

**Claim A:** f_cap = 0.034 (fraction of ECM heat deposited in Cap domain) — sourced from some project documentation; referenced in `openfoam_thermal_operator.json` field `heat_source.documented_vs_implemented_conflict`.

**Claim B:** f_cap = 0 in the actual OF executable case — no `fvOptions` source on `cap_rotated`; 100% of ECM heat in `jellyRoll_rotated` only — confirmed by reading `fvOptions` files in `cases/wedge_2170`.

**Stronger evidence:** Claim B (OF executable case). The raw `fvOptions` file is highest-authority evidence per skill evidence order.

**Canonical resolution:** 0% Cap heat is the operative OF design. Test A and Test D in STAR must use 0% Cap heat, not 0.034. Claim A may be from an earlier design iteration or documentation error. Do NOT average or blend.

**Consequence if unresolved:** STAR Test D comparison based on 0.034 would compare against a non-existent OF configuration, making validation meaningless.

**Files to update:** `docs/equivalence/OPENFOAM_THERMAL_OPERATOR_INVENTORY.md` (mark documented 0.034 as SUPERSEDED); `data/equivalence/openfoam_thermal_operator.json` (add `canonical_value: 0`); relevant Test D design instructions must specify 0% Cap.

---

## C02 — Rtherm_base documented vs computed

**Claim A:** Rtherm_base = 5.4 K/W — documented in early project files and thermal operator inventory as the bottom interface resistance value.

**Claim B:** Rtherm_base ≈ 1.8×10⁻³ K/W — computed from the actual OF `thicknessLayers` and `kappaLayers` values: thicknessLayers = 6.015×10⁻⁷ m, kappaLayers = 1 W/mK → R_specific = 6.015×10⁻⁷ m²K/W; for the full-disc JR-bottom area (3.325×10⁻⁴ m²) → R_total = 6.015×10⁻⁷ / 3.325×10⁻⁴ ≈ 1.81×10⁻³ K/W.

**Stronger evidence:** Claim B (computed from OF case files). `0/jellyRoll_rotated/T` bottom patch is highest authority.

**Canonical resolution:** R_specific = 6.015×10⁻⁷ m²K/W is the correct value to apply in STAR. The 5.4 K/W value is either per-unit-area confusion, per-cell confusion, or refers to a different interface. Do NOT use 5.4 K/W in S0-D resistance setting.

**Consequence if unresolved:** Factor of ~3000 error in bottom interface resistance → wrong bottom T-gradient, wrong axial T distribution.

**Files to update:** `docs/equivalence/OPENFOAM_THERMAL_OPERATOR_INVENTORY.md`; any S0-D or Option D instructions that name Rtherm_base should specify R_specific = 6.015×10⁻⁷ m²K/W explicitly.

---

## C03 — Can↔Cap interface geometry: "cylindrical band" vs "planar annulus"

**Claim A:** Can↔Cap interface described as a cylindrical axial band (Can outer wall meets Cap side wall) — appeared in early narrative descriptions of the OF geometry.

**Claim B:** Can↔Cap interface is a planar annulus at z=65.3413 mm, r=10.31368..10.545 mm — confirmed by reading `shell_rotated/polyMesh/points` and `cap_rotated/polyMesh/points`; documented as CORRECTED in `OPENFOAM_GEOMETRY_TOPOLOGY_TARGET.md`.

**Stronger evidence:** Claim B (raw mesh coordinates). This is already documented as corrected.

**Canonical resolution:** Planar annulus at z=65.3413 mm is correct. Any S0-A or Test A instruction that describes this interface must specify planar annulus geometry.

**Consequence if unresolved:** Designing STAR region mapping around a cylindrical band interface would produce wrong Can↔Cap coupling topology.

**Files to update:** Already corrected in `OPENFOAM_GEOMETRY_TOPOLOGY_TARGET.md`; verify no other document still uses "cylindrical band."

---

## C04 — F-series failure interpretation: "zero clearance impossible" vs "invalid radial combination"

**Claim A:** F-series failure proves that STAR/BDS cannot build JR OD = Can ID geometry; zero-clearance construction is impossible in BDS. This claim was stated during session 2026-09-17 before correction.

**Claim B:** F-series failure was caused by JR OD (20.6274 mm) >> available Can OD (~18 mm from inherited D00 m_dRepCanXDim value) — an invalid radial combination unrelated to zero-clearance; JR OD = Can ID exact-contact has NEVER been isolated and tested. OPEN.

**Stronger evidence:** Claim B (analysis of F-series input TBM values; F-series xlsx error sequence: "JR OD > Can ID; Can ID set to JR OD" → "Can Thickness is -ve"). Corrected and committed in `TBM_GEOMETRY_VS_STAR_MAPPING_DECISION_CLAUDE.md` (commit f2d5504).

**Canonical resolution:** H004-3 (exact-contact constructibility) remains OPEN LOW. F-series provides no evidence about this hypothesis. Do not state that S0-B is the only route to radial equivalence. RAD-D2 tests H004-3.

**Consequence if unresolved:** If zero-clearance is incorrectly declared impossible, RAD-D2 and the geometry route to radial equivalence are incorrectly dropped from the campaign.

**Files to update:** `TBM_GEOMETRY_VS_STAR_MAPPING_DECISION_CLAUDE.md` (already corrected in f2d5504); `TBM_HYPOTHESIS_LEDGER.md` H004-3 entry (confirm OPEN LOW is retained); any future Robert package instructions must not state F-series proves zero-clearance failure.

---

## C05 — Coverage percentage (83.7%) based on non-final radial dimensions

**Claim A:** BDS-to-OpenFOAM thermal coverage percentages (83.7% for JR, etc.) appear in `BDS_TO_OPENFOAM_THERMAL_MAPPING.md` and early documentation, suggesting meaningful volumetric equivalence.

**Claim B:** These percentages were computed using T06's wrong JR OD (17.88 mm) and wrong Can ID/OD. With correct dimensions (JR OD = 20.6274 mm), the annular JR volume and JR+Mandrel volumes change substantially. The percentages are not decision-driving until geometry is corrected.

**Stronger evidence:** Claim B. The STEP audit and `TBM_GEOMETRY_DOF_MATRIX.md` confirm T06 dimensions are far from OF targets.

**Canonical resolution:** Do not cite coverage percentages as evidence of thermal equivalence. They are internal sizing calculations based on stale dimensions. Revisit after GEO-001/002/005 are resolved.

**Files to update:** Add a warning note to `BDS_TO_OPENFOAM_THERMAL_MAPPING.md` that coverage percentages are stale and non-decision-driving pending RAD corrections.

---

## C06 — S0-B interface existence vs S0-B quantitative area

**Claim A:** S0-B instructions in `README_FOR_ROBERT.md` ask Robert to report whether each of 14 Region-pair interfaces EXISTS and its type. This is the current S0 package as prepared.

**Claim B:** For Root↔JR interfaces (TOP-013, TOP-014, STAR-010, STAR-011), existence alone is insufficient — the critical question for equivalence is whether STAR assigns a quantitative interface AREA close to the full-disc target (3.325×10⁻⁴ m²). A Root-JR interface of negligible area (even if it exists) cannot reproduce the OF full-disc operator.

**Stronger evidence:** Claim B. STEP B-Rep confirms zero common-face area; STAR may build a different area; the area is the deciding evidence for C→A trigger (TOP-013/014).

**Canonical resolution:** Before dispatching S0 package, add explicit area reporting request for at minimum the four Root↔JR and Root↔JR-bottom interface pairs. The current S0 package is incomplete for these items. This is the most operationally urgent outstanding item in the current S0 package.

**Consequence if unresolved:** Robert returns a binary exists/not-exists answer for Root-JR interfaces; we cannot determine whether the area is large enough to reproduce the OF operator; we must send a second Robert round to ask for areas.

**Files to update:** `artifacts/equivalence/robert_s0/README_FOR_ROBERT.md` (add area reporting requirement for Root-JR pairs before dispatching).

---

## C07 — NEXTSESSION stale items (V3 preflight + JR OD pair)

**Claim A:** `NEXTSESSION` file (as of 2026-09-10 state) describes "V3 preflight + JR OD test pair pending from Robert" as the immediate next step.

**Claim B:** Robert's Sep-16 return superseded these pending items. The F-series JR OD test was received and analyzed. V3 preflight context (if it referred to something else) has been overtaken by the Sep-16 results and the current S0 + RAD campaign plan.

**Stronger evidence:** Claim B. Sep-16 return is newest evidence; NEXTSESSION file pre-dates it.

**Canonical resolution:** `NEXTSESSION` must be rewritten to reflect current state: S0 package prepared (not yet dispatched), RAD-A/B/C/D defined, F-series analysis complete, H007/RMAP-1 confirmed.

**Files to update:** `/workspace/NEXTSESSION` — full rewrite required.

---

## C08 — GEO-009/010 symmetric axial placement classified D vs classification as OPEN

**Claim A:** `TBM_GEOMETRY_VS_STAR_MAPPING_DECISION_CLAUDE.md` classifies "Symmetric JR axial placement" as **D** — not operator-relevant after valid end-stack mapping.

**Claim B:** `ECM_EQUIVALENCE_MASTER_MATRIX.md` GEO-009/010 are classified OPEN because the JR bottom is at z=0 in T06 vs z=0.23132 mm in OF, and the Can bottom is at -2.445 mm vs z=0 in OF. This asymmetry is not just about the end-stack strategy — it determines whether the bottom Interface condition (IFC-002 at z=0.23132 mm) can be physically placed.

**Stronger evidence:** Claim B has more nuance. The D classification in the decision document assumed valid end-stack mapping; but if GEO-006 (Can bottom disc) is required, the axial placement matters for that disc's position.

**Canonical resolution:** Symmetric axial placement is D AFTER GEO-006 (Can bottom disc) and IFC-002 (explicit resistance) are confirmed achievable via Option D or geometry. If Option D fails for the bottom (no hookable interface), axial placement becomes relevant to provide the correct z=0.23132 mm interface position. Retain as OPEN in the master matrix until GEO-006 path is confirmed.

**Files to update:** Decision document footnote; confirm no document treats axial placement as settled when GEO-006 is still OPEN.

---

## C09 — OF transient reference data: "stale" vs "available"

**Claim A:** Some session notes describe the OF thermal transient reference data at `cases/wedge_2170_thermal_qualification/reference_thermal_transient.csv` as needing regeneration; it may be stale.

**Claim B:** `STAR_CLIENT_EQUIVALENCE_TEST_PLAN.md` Phase 6 describes this case as "the clean reference case" and does not explicitly flag the CSV as stale.

**Stronger evidence:** Neither claim has definitive force without checking the CSV timestamp vs. last case modification. The file may be current.

**Canonical resolution:** Before Test A comparison baseline is needed, verify `reference_thermal_transient.csv` was generated from the current `cases/wedge_2170_thermal_qualification` case (compare git log of case files vs CSV timestamp). This is a pre-Test-A action, not urgent now.

**Files to update:** Add verification step to Test A setup checklist.

---

## C10 — Two-mode architecture: CORRECTED (prior framing "OF is lumped" was wrong)

**Prior incorrect framing (removed):** Earlier drafts characterized OpenFOAM as lumped-only and STAR distributed 3D RCR as an additional capability layered on top. This was wrong.

**Confirmed two-mode architecture from repository evidence:**

OpenFOAM has two distinct ECM coupling modes, both present in the repository:

**OF Lumped mode:** `couplingMode lumped` (`lumpedOutput totalPower`) — present in `cases/wedge_2170/system/controlDict` and `cases/validation_lumped_paramset_21p09x70p02/system/controlDict`. Single scalar ECM state (`state.q_ah`, `state.v_rc`, `state.hysteresis`). External Python wrapper `ecm_coupling_wrapper.py --backend ecm-step`. Uniform heat deposition across all JR cells. No spatial sub-partitioning.

**OF Distributed mode:** `couplingMode elementWise` — present in `cases/validation_distributed_paramset_21p09x70p02/system/controlDict`. 18 spatial ECM partitions (axial6 × radial3 from `mapping_table_axial6_radial3_2170mesh.csv`), each with independent `q_ah`, `v_rc`, `hysteresis` state. Heat generation varies ~10× between partitions (`prev_qvol_by_ecmid`: central ~957 kW/m³, outer-edge ~16 MW/m³). `ECM_DISTRIBUTED_ELECTRICAL_MODE=parallel2rc`. Spatial state field `stField ecmST`.

**STAR requirement — unchanged:** The final STAR workflow must support BOTH native 0D/lumped whole-cell RCR (LUMP track) AND native distributed 3D RCR (ELEC/DIST track). Neither is subordinate to the other.

**Canonical resolution:** The master matrix now has an explicit LUMP family (7 requirements) for the lumped track and separate ELEC/DIST families (17 requirements) for the distributed track. Test A-LUMP / Test D-LUMP cover lumped equivalence. Tests B/C/D cover distributed equivalence. When citing an "OF reference," always specify which case and which coupling mode.

**Files updated:** `ECM_EQUIVALENCE_MASTER_MATRIX.md` (LUMP section added; DIST section updated with confirmed elementWise evidence; SRC-004/005 corrected to specify per-track); `ECM_EXPERIMENT_COVERAGE_MATRIX.md` (OF reference cases table added; Test A-LUMP / Test D-LUMP added).

