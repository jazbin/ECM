# RCR Candidate V2 → V3 Delta Proof: Transport Number sets

Date: 2026-09-10

## Summary

V3 adds exactly one field to V2: `Transport Number sets = 0` inside the `General Electrolyte` SIMMOD block. This is the only difference. No geometry, electrochemistry, RCR tables, model map, package dimensions, tabs, or MODELMAP fields are changed.

## File identity

| Version | File | SHA-256 | Bytes |
|---|---|---|---|
| V2 (frozen) | `out/rcr_candidate/hp2170-rcr-v2-S3fix-tabs-on-sameFace.tbm` | `372c99026580732866708f0f45906caa74733a826e816fdf2d7de0b416ca0e3b` | 304308 |
| V3 (preflight) | `out/rcr_candidate/hp2170-rcr-v3-star-preflight-tabs-on-sameFace.tbm` | `91cb8f8a2069c308db8dd910a695a2e7bbf55cca509330df004fa8ce82f638d4` | 304337 |
| Client copy | `out/hp2170NCA-RCR-distributed-final-preflight.tbm` | `91cb8f8a2069c308db8dd910a695a2e7bbf55cca509330df004fa8ce82f638d4` | 304337 |

V3 is 29 bytes larger than V2 (exactly the length of the inserted line `\tTransport Number sets\t=\t0\t!\n`).

## Diff

Line inserted after `INL(Kevin_L_Gering)_EC:DMC_Transport# m_dR6 = ...` (line 2168 in V3):

```
+	Transport Number sets	=	0	!
```

No other lines changed. Line count: V2 has N lines, V3 has N+1 lines (one new line inserted).

## Classification: CHANGE_REQUIRED

### Criterion 1 — STAR reference corpus

All 4 STAR-CCM+ cylindrical reference TBMs from the Siemens installation contain this field in the `General Electrolyte` SIMMOD block with value `0`:

| File | Field present | Value |
|---|---|---|
| `validationBattery.tbm` | Yes | 0 |
| `testTBM.tbm` | Yes | 0 |
| `LiIonSpiral.tbm` | Yes | 0 |
| `tutorialCylindricalCell.tbm` | Yes | 0 |

BDS-generated files (`HE18650/he18650spiral1.tbm`, `HP18650/hp18650Spiral-DIST.tbm`, our source `hp2170NCA-ECM.tbm`) do not contain this field. This identifies a structural difference between older BDS-format files and current STAR-CCM+ importer expectations.

### Criterion 2 — Runtime confirmation

Robert's STAR-CCM+ runtime log from the V1 RCR candidate test (2026-09-09) explicitly reported:

> "Transport Number sets not found in the file, defaulting to 0."

This is direct evidence that:
1. The STAR-CCM+ importer actively searches for this field.
2. When absent, it generates a runtime message (non-fatal in V1, but importer-consumed).
3. The correct value is 0 (STAR defaults to 0 when absent; all 4 STAR refs use 0).

### Why this is CHANGE_REQUIRED and not WARN-only

The field was flagged WARN in the validator (not FAIL) because the V1 and V2 failures had a different root cause (S3=0 geometry error that prevented any SIMMOD evaluation). However, the combination of (a) explicit runtime log evidence that the field is consumed and (b) presence in all 4 STAR-install references elevates it to CHANGE_REQUIRED for the final preflight package. Adding it makes V3's General Electrolyte SIMMOD structurally identical to the STAR-install references on this field.

## Physics impact: NONE

Transport Number sets = 0 matches the runtime default STAR would apply anyway. Adding the field explicitly does not change any electrochemical or transport calculation. It eliminates the runtime warning and aligns the file with the STAR-install reference format.

## Generator implementation

The insertion is performed by `tools/generate_tbm_v4_candidate.py` and `tools/generate_tbm_test_variants.py` via the `insert_after_first()` function, using `INL(Kevin_L_Gering)_EC:DMC_Transport# m_dR6` as the anchor (the last field of the Transport# parametrization group, unique in the file). The `generate_tbm_rcr_candidate.py` script reads the updated V4/v3 base (SHA `2cd3b503559e5ed0dd060d7b26cd555121cd224e40d91fe6c2b96dc23a7c8afd`) and applies only the MODELMAP IET switch; Transport Number sets is already present in the base.

## Validator result

| Version | FAIL | WARN | INFO | PASS |
|---|---|---|---|---|
| V2 | 0 | 5 | 14 | 36 |
| V3 | 0 | 4 | 14 | 37 |

The reduction from 5 WARN to 4 WARN is the `transport_number_sets` check flipping from WARN (missing) to PASS (present, value 0). All other checks are unchanged.

Remaining 4 WARNs in V3 (all pre-existing UNRESOLVED items, none linked to a known runtime failure):
1. `jr_od` — JellyRoll-can gap 1.38 mm; correct winding OD not confirmed from AE data
2. `report_jr_diameter` — REPORT block JR diameter (19.25) stale vs Builder value (19.25 = same, flagged for confirmation)
3. `report_jr_height` — REPORT block JR height stale
4. `report_capacity` — REPORT block capacity stale vs DataSheet 5.0 Ah
