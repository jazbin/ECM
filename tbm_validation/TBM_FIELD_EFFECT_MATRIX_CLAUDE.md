# TBM Field → Observable Effect Matrix — Independent Reconstruction
**Date:** 2026-09-22
**Scope:** Fields that have been directly tested via Robert runtime or STEP geometry measurement.
Legend: ✓ tested | – not tested | REFUTED = changes do not affect observable | MASKED = downstream failure prevented reaching this observable

## Primary observable: E004 (Electrode Root 1 extrusion failure)

| TBM field | Tested range | Effect on E004 | Evidence event | Notes |
|---|---|---|---|---|
| Mandrel thickness (m_dMandrelThickness_mm) | 0 → nonzero | Upstream of E004: E003 first | R001→R002 | Fix mandrel to reach E004; E004 is downstream |
| Tab enable flags (+/- tab on/off) | enabled vs disabled | NO EFFECT | R002–R004 | E004 survives tab-disable |
| Tab vertical orientation (standard vs same-face) | both orientations | NO EFFECT | R003–R004 | E004 survives orientation swap |
| m_bOnly1D (SIMMOD blocks) | nonzero → 0 | NO EFFECT on E004 | R004 | Clears m_bOnly1D warning; E004 unchanged |
| Transport number set count | fixed to 0 | NO EFFECT on E004 | R005 | Clears transport-number warning; E004 unchanged |
| +Electrode m_dS3 | 0 → 5mm | NO EFFECT | R005 | S3=5; E004 unchanged; H004-1 REFUTED |
| JR OD (m_dJellyrollThickness_mm in Detailed Builder) | 19.25 → 20.6274mm | NO EFFECT on E004 | R005 | Exact Can-ID contact; E004 unchanged |
| Package m_dintHeight | 65.11 → 65.21 and 65.81mm | NO EFFECT | R007 ROOT_A/B | +0.10mm and +0.70mm pkg height; E004 unchanged; H004-6 REFUTED |
| +Electrode Tab m_dLength_mm (pos surplus = tab − elec_width) | 0 to +2mm surplus; working cell | EFFECT: zero surplus (pos only) PASS when neg=+8mm | R008-H01–H04 | Single-polarity zero/small surplus does not trigger E004 alone |
| -Electrode Tab m_dLength_mm (neg surplus = tab − elec_width) | 0 to +2mm surplus; working cell | EFFECT: zero surplus (neg only) PASS when pos=+9mm | R008-H05–H08 | Single-polarity zero/small surplus does not trigger E004 alone |
| Both tab lengths (combined surplus) | 0, +0.10, +0.70, +2.00mm; working cell | CRITICAL EFFECT: threshold between +0.10mm and +0.70mm per polarity | R008-H09–H12 | H09(0,0)=FAIL; H10(0.1,0.1)=FAIL; H11(0.7,0.7)=PASS |
| Both tab lengths in target axial stack | 0, +0.10, +0.70, +1.00, +2.00, +5.00, +9/+8mm | CRITICAL EFFECT: same threshold confirmed in different axial geometry | R008-T02–T08 | T02(0)=FAIL; T03(0.1)=FAIL; T04(0.7)=PASS; T05–T08=PASS |
| Asymmetric surplus (pos positive, neg slightly negative) | pos=+0.89, neg=-0.11mm | PASS despite neg<0 | R008-T01 | Suggests max-surplus or combined criterion, not strict per-polarity floor |
| Large negative surplus (both negative) | pos=-4.11, neg=-5.11mm | FAIL E004 | R008-T09 (= R005 reproduction) | Consistent with H007; not a separate mechanism |
| m_dSepFeedLength_mm | 0/0 → 10/85; in production TBM | PENDING (R006 not received) | R006 | BLOCKED; H004-5 unresolved |
| m_dSepFeedLength_mm | 10 → 0; in F04 (full 2170) | MASKED — F04 fails on radial blocker first | R008-F05 | Cannot test feed/tail effect in F-series |

## Secondary observable: Radial geometry blocker ("Can Thickness is -ve")

| TBM field | Tested range | Effect | Evidence | Notes |
|---|---|---|---|---|
| Package m_dextDiameter | 21 → 21.09mm (F-series) | Required for 2170 geometry | STEP spec | Not independently varied |
| Package m_dintDiameter | 20.9 → 20.6274mm (F-series) | When combined with 2170 electrode widths, STAR-computed JR OD > Can ID → FAIL | R008-F01–F09 | Exact same m_dintDiameter value (20.6274) does not fail in H/T series because those series use working-cell electrode widths |
| m_dJellyrollThickness_mm (Builder) | 17.9 → 20.6274mm (F-series) | Combined with above change: triggers "JR OD > Can ID" warning then "Can Thickness -ve" | R008-F01–F09 | STAR appears to compute JR OD from wound electrode geometry, not from m_dJellyrollThickness_mm directly |
| Electrode widths (physical neg/pos) | 56/57mm → 64.11/65.11mm (working→F-series) | CRITICAL: larger electrode widths produce STAR-computed JR OD that overflows Can ID | Inferred from F-series failure pattern | The actual wound geometry of 2170 electrodes may not fit in the stated package dimensions |
| Package m_dextDiameter (F-series) | 21.09mm; not varied | — | — | Potential fix: enlarge to accommodate actual JR OD |

## STEP geometry observable: Tab Stem bounding-box top-Y (saturation)

| TBM field | Tested range | Effect | Evidence | Notes |
|---|---|---|---|---|
| Both tab lengths (target axial stack) | +0.89 (T01) → +0.70 → +1.00 → +2.00 → +5.00 → +9/+8mm | MONOTONIC INCREASE from T01→T06; SATURATION at T06 | STEP B-Rep measurement (T01–T08) | T06=T07=T08 top-Y = 66.275mm; T01=65.557mm |
| +Ve Tab Stem top-Y saturation surplus | ~2mm input surplus | Saturation value | Measured | Inputs ≥ 2mm produce identical geometry regardless of input value |

## Fields not tested / pending

| TBM field | Reason not tested | Hypothesis it would test |
|---|---|---|
| m_dSepFeedLength_mm / m_dSepTailLength_mm | R006 pending; F-series blocked | H004-5 |
| C00–C17 Detailed Builder / PCD transplants | Campaign never run | H011 (localization) |
| Package m_dextDiameter (enlarged for F-series) | Not in any sent package | H008 fix |
| Single-polarity surplus in target-axial-stack | T-series only tested both-together | H007 threshold asymmetry |
| m_dOffsetPosAvg = 1e-6 vs 0.5 | Not varied | Effect on winding geometry unknown |
| m_dElectrodeOverlapAtEnd_mm = 20 vs 30–50 (other references) | C04 never run | E004 localization |
