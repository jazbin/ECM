# STAR-CCM+ Maximum Static Preflight Audit — 2026-09-10

**Subject:** hp2170-rcr-v2-S3fix-tabs-on-sameFace.tbm (V2 RCR candidate, frozen baseline)
**Objective:** Maximum static STAR-CCM+ import compatibility preflight before releasing V3.
**Corpus:** Siemens cylindrical reference TBMs (`tbm_validation/in_StarCCM_bds/`) — branch `tbm-siemens-reference-corpus` (SHA `b0be477f19bf16eaff92eafd9f3ba07fb6f3152d`).
**V2 SHA-256:** `372c99026580732866708f0f45906caa74733a826e816fdf2d7de0b416ca0e3b`
**Date:** 2026-09-10

## Governing project objective

For this project, **we are not trying to reconstruct the physically realistic internal clearances of the cell**. We are trying to reproduce the already-defined **OpenFOAM–ECM reference model** in STAR-CCM+.

The OpenFOAM–ECM case is the reference definition for geometry and thermal coupling. Where the OpenFOAM model has ideal/shared contact, STAR should reproduce that condition as closely as its geometry engine permits. Artificial air gaps, liners, clearances, or contact imperfections must not be introduced merely to make the model more physically realistic.

Permanent requirement: `tbm_validation/OPENFOAM_ECM_EQUIVALENCE_TARGET.md`.

---

## Methodology

Every structural feature of V2 was compared field-by-field against the 4 STAR-install cylindrical reference TBMs (validationBattery, testTBM, LiIonSpiral, tutorialCylindricalCell) and against the BDS-origin references (HE18650, HP18650-DIST, HP18650-RCR25deg). Discrepancies were classified as:

- **CHANGE_REQUIRED** — evidence from (a) STAR reference corpus AND (b) runtime log points to a consumed field; fix warranted.
- **SAFE_DIFFERENCE** — confirmed structural pattern in BDS-generated vs STAR-install files; do not change.
- **UNRESOLVED_NONBLOCKING** — mixed references or unknown correct value; no runtime evidence linking to failure; do not change without explicit authorization.
- **VALID_MODEL_VERSION_DIFFERENCE** — known format-version split between BDS-generated and STAR-install-generated files; expected, not a bug.

---

## Discrepancy Table

| # | Section | Field / Feature | V2 Value | STAR-install refs | BDS refs | Classification | Action |
|---|---|---|---|---|---|---|---|
| 1 | General Electrolyte SIMMOD | `Transport Number sets` | absent | 0 (all 4) | absent | CHANGE_REQUIRED | Added in V3 |
| 2 | SIMMOD block count / names | `m_dModelVersion` | 3 | 6 (all 4) | 3 | VALID_MODEL_VERSION_DIFFERENCE | None |
| 3 | SIMMOD structure | Dual `Distributed` blocks | class=Thermal + class=IET | 1 or 2 (mixed) | 2 (HP18650-DIST template) | SAFE_DIFFERENCE | None |
| 4 | MODELMAP | `IET = RCRTable 3D` | RCRTable 3D | varies | — | VALID (RCR requirement) | None |
| 5 | MODELMAP | `Thermal = Distributed` | Distributed | varies | — | VALID (distributed requirement) | None |
| 6 | Detailed Builder | `m_dSepFeedLength_mm` | 0 | 10 (all 4) | 0 (HE18650, HP18650-DIST) | UNRESOLVED_NONBLOCKING | None |
| 7 | Detailed Builder | `m_dSepTailLength_mm` | 0 | 85 (all 4) | 0 (HE18650, HP18650-DIST) | UNRESOLVED_NONBLOCKING | None |
| 8 | Detailed Builder | `m_dOffsetPosAvg` | 0.5 | 0.5 | mixed | PASS (already correct in V4) | None |
| 9 | Detailed Builder | `+Electrode m_dS3` | 5 | 5 | mixed | PASS (fixed V1→V2) | None |
| 10 | Package | `m_dintDiameter` | 20.6274 | varies (cell-specific) | — | PASS | None |
| 11 | Package | `m_dextHeight` | 70.02 | varies (cell-specific) | — | PASS | None |
| 12 | Builder geometry | `m_bOnly1D` | 0 (all blocks) | 0 (active blocks) | mixed | PASS (fixed V2→V3-base) | None |
| 13 | DataSheet | name, capacity, height | hp2170NCA / 5.0 / 70.02 | cell-specific | — | PASS (fixed in V4) | None |
| 14 | RCR data | 3 temperature sets | present | cell-specific | — | VALID (AE data protected) | None |
| 15 | REPORT block | JR diameter / height / capacity | stale values | cell-specific | stale | UNRESOLVED_NONBLOCKING | 4 WARNs in validator |
| 16 | Tab topology | same-face, +/- on top | same-face | varies | — | VALID (project requirement) | None |
| 17 | JR OD | `m_dJellyrollThickness_mm` | 19.25 | cell-specific | — | REFERENCE_MODEL_TARGET_RESOLVED / STAR_FEASIBILITY_PENDING | Exact target 20.6274 mm; test variants created 2026-09-10 |

---

## Finding 1 (CHANGE_REQUIRED) — Transport Number sets

**Field:** `Transport Number sets` inside the `General Electrolyte` SIMMOD block.
**V2 value:** absent.
**All 4 STAR-install refs:** present, value `0`.
**BDS-origin refs (HE18650, HP18650-DIST, source TBM):** absent.

**Evidence:**
Robert's runtime log from the V1 RCR candidate test (2026-09-09) explicitly reported:
> "Transport Number sets not found in the file, defaulting to 0."

This confirms the STAR-CCM+ importer actively reads and logs this field. Value 0 is correct — it matches what STAR defaulted to anyway. No physics impact.

**Implementation:** `insert_after_first()` inserts `\tTransport Number sets\t=\t0\t!\n` after the anchor `INL(Kevin_L_Gering)_EC:DMC_Transport# m_dR6` in the `General Electrolyte` SIMMOD block. Implemented in `tools/generate_tbm_v4_candidate.py` and `tools/generate_tbm_test_variants.py`. The RCR candidate generator (`tools/generate_tbm_rcr_candidate.py`) picks up the fix from the updated V4/v3 base.

**Result:** V3 has `Transport Number sets = 0` present; validator check `transport_number_sets` → PASS.

---

## Findings 2–5 (SAFE / VALID)

### Model version split (`m_dModelVersion`)

BDS-generated files use `m_dModelVersion = 3`; all 4 STAR-install files use `6`. This is a known format-version difference between BDS and the STAR-install file generator. It is not a bug. The importer handles both versions. **Do not change.**

### Dual Distributed block

V2 (and its HP18650-DIST template) contains two SIMMOD blocks named `Distributed`: one with `class='Thermal'` (active, selected by MODELMAP) and one with `class='IET'` (inactive catalog entry). This pattern is present in the template and consistent with how BDS-generated distributed-mode TBMs are structured. STAR-install files may or may not share the pattern; the MODELMAP correctly selects only the Thermal block. **SAFE_DIFFERENCE — do not change.**

### MODELMAP selectors

`IET = RCRTable 3D` and `Thermal = Distributed` are the project-required model selections. These are physically correct for the 2170 NCA RCR distributed configuration. They differ from STAR-install references only because those references use different electrochemical models. **VALID — do not change.**

---

## Findings 6–7 (UNRESOLVED_NONBLOCKING) — Separator feed/tail lengths

`m_dSepFeedLength_mm = 0` and `m_dSepTailLength_mm = 0` in V2. STAR-install refs use 10/85. HE18650 and HP18650-DIST (BDS-origin) use 0. The correct values for the 2170 NCA cell are not known from About-Energy characterisation data. No runtime error has been linked to these fields. **Do not change without explicit AE data or Siemens confirmation.**

---

## Final validator result

| Version | FAIL | WARN | INFO | PASS |
|---|---|---|---|---|
| V2 (baseline) | 0 | 5 | 14 | 36 |
| V3 (preflight) | 0 | 4 | 14 | 37 |

V3 achieves the maximum reachable preflight quality given current available reference data. The 4 remaining WARNs are all UNRESOLVED items with no runtime evidence linking them to a STAR import failure.

---

## Conclusion and freeze statement

**V3 is the maximum static preflight candidate.** One CHANGE_REQUIRED item was identified and implemented (Transport Number sets = 0). All other discrepancies are either safe differences from the BDS/STAR-install format split or unresolved non-blockers without runtime evidence.

**All RCR candidate TBM changes are frozen pending Robert's runtime result on V3.**

Client package: `out/hp2170NCA-RCR-STAR-final-preflight-20260910.zip`
Client TBM: `hp2170NCA-RCR-distributed-final-preflight.tbm` (byte-identical to V3, SHA `91cb8f8a...`)

---

## Addendum — JR OD reference-model target (2026-09-10)

The OpenFOAM–ECM `wedge_2170` geometry establishes the **reference-model target**, not a realistic manufactured-cell clearance. The project objective is to reproduce this OpenFOAM–ECM case in STAR-CCM+, so the geometry should retain its ideal-contact assumptions.

**Evidence:** `cases/wedge_2170/constant/jellyRoll_rotated/polyMesh/points` places the jelly-roll outer boundary at approximately the package/can inner radius, corresponding to JR OD ≈ `20.6274 mm = Package m_dintDiameter`. The OpenFOAM thermal model therefore has zero radial gap between the JR outer face and can inner face. The `19.25 mm` value in the current TBM creates a `1.3774 mm` diametral gap with no equivalent in the reference model.

**Reference-model target value:** `20.6274 mm` (= can ID), representing zero radial gap / ideal JR-can contact. This is the desired STAR value subject only to STAR winding/CAD feasibility.

**Thermal-interface rule:** ideal contact / zero contact resistance is the default because that is the reference model. If interface resistance is needed later, it must be introduced explicitly as a controlled interface parameter rather than implicitly via a geometric air gap.

**Test package:** `out/hp2170NCA-JR-OD-test-20260910.zip`

| Variant | Input JR OD | Rationale |
|---|---|---|
| `hp2170-jr-perfect_contact_20p6274.tbm` | 20.6274 mm | Preferred target: exact OpenFOAM-equivalent zero-gap geometry; may trigger STAR feasibility guard |
| `hp2170-jr-safe_20p55.tbm` | 20.55 mm | CAD-feasibility probe/fallback only; not the preferred model geometry |

Decision:
- If `perfect_contact` succeeds and topology is sane → use `20.6274 mm` in the final RCR candidate.
- If exact equality is rejected by STAR but `20.55 mm` succeeds → treat `20.55 mm` only as a STAR CAD workaround and configure/verify the interface so the thermal coupling remains equivalent to the OpenFOAM ideal-contact condition. Do not interpret the finite clearance as a physical air gap.

The previous `19.25 mm` value is retired for the final OpenFOAM-equivalent model.
