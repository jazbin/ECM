# Geometry Campaign — Case Matrix

**Date:** 2026-09-23
**Purpose:** Identify the best achievable TBM geometry relative to the OpenFOAM thermal operator target before any STAR physics work begins.
**Method:** TBM-to-STEP conversion only. Robert opens each TBM in BDS, exports STEP, measures key dimensions, and reports the table. No STAR import, no physics.
**Baseline:** T06_TARGET_AXIAL_SURPLUS_2p00.tbm. SHA-256: 433a8162b6f02bbc0a5781bc7f789345adaecf8bd2b9d5ac7bd6199ed8fb6f71

---

## Baseline dimensions (T06 STEP-confirmed)

| Quantity | T06 value | OF target | Gap |
|---|---|---|---|
| JR OD | 17.881 mm | 20.6274 mm | −2.746 mm |
| Can ID | 18.000 mm | 20.6274 mm | −2.627 mm |
| Can OD | 20.90 mm | 21.09 mm | −0.19 mm |
| JR↔Can radial gap | 0.0595 mm | 0 mm | +0.0595 mm |
| Mandrel OD | ~6 mm | 0 (none) | +6 mm |
| Can height | ~70 mm | 65.34 mm | +4.66 mm |
| JR height | 65.11 mm | 65.11 mm | 0 (SATISFIED) |
| JR-to-Can-top | 2.445 mm | 0 mm | +2.445 mm |
| JR-to-Can-bottom | 2.445 mm | 0.231 mm | +2.214 mm |

---

## Controlling TBM fields (BUILDER + Package sections of T06)

| Field | T06 value | Candidate controls | Evidence |
|---|---|---|---|
| `m_dJellyrollThickness_mm` | 17.9 | JR OD | CONFIRMED August class; T06-class transfer OPEN |
| `Package m_dintDiameter` | 20.9 | Can ID | OPEN (HYPOTHESIS — candidate field identified from Siemens corpus) |
| `Package m_dextDiameter` | 21.0 | Can OD | SUPPORTED (August data, RMAP-2) |
| `m_dMandrelThickness_mm` | 6.0 | Mandrel OD | OPEN |
| `Package m_dextHeight` | 70.0 | Can height | OPEN |
| `Package m_dintHeight` | 65.11 | Internal cavity height | OPEN |
| `m_dSepFeedLength_mm` | 10 | End-stack spacing | OPEN (plausible per Siemens corpus) |
| `m_dSepTailLength_mm` | 85 | End-stack spacing | OPEN (plausible per Siemens corpus) |
| `m_dElectrodeOverlapAtEnd_mm` | 40 | End-stack extent | OPEN |

---

## Case matrix

### RADIAL family — 3 TBMs

| Case | TBM filename | Field changed | From | To | GEO req. | Hypothesis under test | Discriminating result |
|---|---|---|---|---|---|---|---|
| RAD-A | GC_RAD_A_can_id_probe.tbm | `Package m_dintDiameter` | 20.9 | 19.0 | GEO-002 | RMAP-3: m_dintDiameter controls Can ID | Can ID shifts from 18mm toward 19mm (operative) OR stays at 18mm (inoperative / JR-driven) |
| RAD-B | GC_RAD_B_can_od_probe.tbm | `Package m_dextDiameter` | 21.0 | 22.0 | GEO-003 | RMAP-2: m_dextDiameter controls Can OD | Can OD shifts from 20.9mm toward 22mm (operative) |
| RAD-C | GC_RAD_C_jr_od_probe.tbm | `m_dJellyrollThickness_mm` | 17.9 | 19.0 | GEO-001 | RMAP-1: m_dJellyrollThickness_mm controls JR OD; T06-class transfer | JR OD shifts from 17.881mm toward 19mm |

**Necessity:** All three are single-variable, non-redundant. RAD-A and RAD-C both probe the JR-to-Can radial relationship but via different fields; together they resolve whether Can ID tracks JR OD or is independently controlled. RAD-B is independent of both.

### AXIAL/END family — 4 TBMs

| Case | TBM filename | Field(s) changed | From | To | GEO req. | Hypothesis under test | Discriminating result |
|---|---|---|---|---|---|---|---|
| AX-A | GC_AX_A_can_height_probe.tbm | `Package m_dextHeight`, `Package m_dintHeight` | 70, 65.11 | 75, 70 | GEO-010, GEO-013, GEO-014 | Package height fields control Can axial envelope | Can height changes from ~70mm; JR-to-Can-end distances change |
| AX-B | GC_AX_B_sep_tail_zero.tbm | `m_dSepTailLength_mm` | 85 | 0 | GEO-009, GEO-016, GEO-021 | Separator tail drives bottom-end-stack height; setting to 0 reduces bottom stack | JR-to-Can-bottom distance changes OR T06 saturation confirmed insensitive to tail |
| AX-C | GC_AX_C_sep_feed_zero.tbm | `m_dSepFeedLength_mm` | 10 | 0 | GEO-009, GEO-013, GEO-021 | Separator feed drives top-end-stack height; isolates feed from tail | JR-to-Can-top distance changes OR confirmed insensitive to feed (vs tail in AX-B) |
| AX-D | GC_AX_D_end_overlap_probe.tbm | `m_dElectrodeOverlapAtEnd_mm` | 40 | 80 | GEO-009, GEO-017 | Electrode overlap at end drives Root/Stem axial extent; can extend to reduce end void | End-stack extent increases OR T06 saturation confirmed insensitive (envelope-limited) |

**Necessity:** AX-A is the only direct test of Can height controllability. AX-B and AX-C are both needed: they isolate the two separator length fields independently (a combined 0/0 test cannot attribute any effect). AX-D is needed to confirm whether saturation is envelope-limited or end-overlap-limited; the result distinguishes the two competing AXIAL-009 explanations.

### CENTRAL family — 1 TBM

| Case | TBM filename | Field changed | From | To | GEO req. | Hypothesis under test | Discriminating result |
|---|---|---|---|---|---|---|---|
| CEN-A | GC_CEN_A_mandrel_zero.tbm | `m_dMandrelThickness_mm` | 6.0 | 0.0 | GEO-005, GEO-015 | Setting Mandrel thickness to zero suppresses the Mandrel body, producing a solid JR to axis | STEP has no Mandrel body (suppressed) OR Mandrel present but smaller OR Mandrel unchanged (field inoperative) |

**Necessity:** Single test covers the full range of possible outcomes. If zero is not achievable, the result still confirms whether the field is operative and identifies the minimum achievable Mandrel OD.

---

## Redundancy evaluation

No cases are redundant:
- RAD-A and RAD-C probe the same quantity (Can ID) from different field angles; only by testing both can we determine whether Can ID is JR-OD-driven or Package-field-driven.
- AX-B and AX-C change different fields (tail vs. feed); they are not interchangeable.
- AX-A and AX-B/C target different aspects of the axial problem (total Can height vs. end-stack partition within the envelope).
- AX-D is a separate hypothesis (electrode overlap limit vs. envelope limit).

**Total: 8 TBMs. Within the authorised 8–12 range.**

---

## Pre-dispatch expected outcomes (Gate 10)

| Case | Expected result | Revision trigger |
|---|---|---|
| RAD-A | Can ID unchanged at ~18mm: m_dintDiameter is inoperative; Can ID follows JR OD. OR Can ID shifts: m_dintDiameter IS operative. Either outcome is actionable. | Update RMAP-3 hypothesis on return |
| RAD-B | Can OD increases proportionally (m_dextDiameter operative). Small deviation from 1:1 expected. | Update RMAP-2 / GEO-003 status on return |
| RAD-C | JR OD shifts toward 19mm (August class result transfers to T06 class). | Update GEO-001 / RMAP-1 status; establish T06 scale factor |
| AX-A | Can height changes from ~70mm toward ~75mm. JR-to-Can-end distances may change symmetrically (AXIAL-001 predicts symmetric if changed at all). | Update AXIAL-001, GEO-010, GEO-013 status on return |
| AX-B | End-stack geometry unchanged (T06 saturation is robust to separator tail); or bottom stack reduces. | Refine AXIAL-009 hypothesis on return |
| AX-C | End-stack geometry unchanged (as AX-B); confirms field isolation. | Same as AX-B; compare AX-B vs AX-C deltas |
| AX-D | End-stack unchanged: confirms envelope is the saturation cause (AXIAL-009 pack envelope explanation). OR stack extends: overlap-limited. | Distinguish AXIAL-009 competing explanations |
| CEN-A | Mandrel body absent from STEP: m_dMandrelThickness_mm = 0 suppresses the domain. Most likely outcome given BDS builder logic. | Update GEO-005 / GEO-015 status; if absent, confirm JR is solid to axis |
