# Pre-Client Release Checklist

Use this checklist before sending any TBM package to Robert. A candidate package must reach at least STATIC_PASS before it is sent. STAR_IMPORT_PASS is the confidence threshold for production physics use.

---

## Confidence states

| State | Meaning |
|---|---|
| STATIC_PASS | `tools/validate_tbm.py` reports 0 FAIL for all variants in the package. WARNs must be reviewed and either resolved or explicitly accepted with justification. |
| STAR_IMPORT_PASS | Robert has successfully run "File > Create from Tbm" in STAR-CCM+ on all variants without error. BDS has generated the expected geometry. |
| PHYSICS_PASS | A STAR-CCM+ simulation with the TBM has been run and the output is physically reasonable (temperatures, heat generation, capacity). At minimum: initial SOC discharge, temperature rise qualitatively consistent with About-Energy data. |

---

## Checklist: before any send

- [ ] All variants pass: `python3 tools/validate_tbm.py --batch <variant_dir> --ref tbm_validation/reference/HE18650/he18650spiral1.tbm`
- [ ] All FAIL results are zero.
- [ ] All WARN results are reviewed: for each WARN, either the field is fixed or there is a written acceptance justification in this checklist.
- [ ] SHA-256 of each variant file is recorded in TBM_INVENTORY.md before sending.
- [ ] The package (zip) SHA-256 is recorded in TBM_INVENTORY.md.
- [ ] The generate script version (git commit SHA) that produced the variants is recorded.
- [ ] The source TBM used is recorded by SHA-256.
- [ ] Any new error history entries are written to STAR_IMPORT_ERROR_HISTORY.md.

---

## Current v3 package status (`out/tbm_geometry_test_20260909.zip`)

**Sent to Robert:** 2026-09-09
**Static validator:** 0 FAIL, 3 WARN for all 4 variants.

### WARN review for v3

| WARN | Field | Action |
|---|---|---|
| JellyRoll-Can gap | `m_dJellyrollThickness_mm = 19.25` | **ACCEPTED FOR GEOMETRY TEST** — the purpose of this send is to test topology, not final physics. A 1.38 mm JR-Can gap does not prevent geometry creation (BDS may create the JR slightly undersized) but means the JR and Can are not in contact. Must be fixed before any production/physics send. Awaiting geometry test result to understand if STAR-CCM+ treats this as an error. |
| DataSheet height | `DataSheet m_dDSHeight = 65` | **ACCEPTED FOR GEOMETRY TEST** — label field, does not drive geometry. Not expected to cause import error. Must be fixed before production send. |
| Capacity derivation | `m_bSpecifyCapacity = 0` | **ACCEPTED FOR GEOMETRY TEST** — no physics run requested for this send. Must be resolved (either fix JR geometry so derivation is correct, or set `m_bSpecifyCapacity = 1`, `m_dAhCell = 5`) before production send. |

### v3 static confidence level: STATIC_PASS (0 FAIL, 3 WARN all accepted)
### v3 STAR_IMPORT_PASS: PENDING (awaiting Robert's results)

---

## Template for future packages

Copy this block for each new candidate package and fill in the values:

```
## Package: [name] — [date]

**ZIP SHA-256:** [hash]
**Source TBM SHA-256:** [hash]
**Generate script git commit:** [sha]
**Sent to Robert:** [yes/no, date]

### Variant SHA-256s
| Variant | SHA-256 | Static validator |
|---|---|---|
| [name] | [hash] | [N FAIL N WARN] |
...

### WARN review
| WARN | Field | Action |
...

### Confidence level
- Static: STATIC_PASS / NOT PASSED (FAILs present)
- STAR import: PENDING / STAR_IMPORT_PASS / FAILED (error text in STAR_IMPORT_ERROR_HISTORY.md)
- Physics: PENDING / PHYSICS_PASS / TBD
```

---

## Production TBM requirements (not yet met)

The following must be fixed before any TBM is used for production physics simulation:

1. **`m_dJellyrollThickness_mm`** — must equal can ID (~20.627 mm). Confirm exact value from About-Energy or cell teardown.
2. **Capacity specification** — either verify that BDS-derived capacity = 5 Ah with corrected JR geometry, or set `m_bSpecifyCapacity = 1` and `m_dAhCell = 5.0`.
3. **`DataSheet m_dDSHeight`** — set to 70.02 mm (can external height) for consistency.
4. **`m_dElectrodeOverlapAtStart_mm = 8`** — confirm from About-Energy electrode spec. Currently assumed from Simple Builder value.
5. **`m_dElectrodeOverlapAtEnd_mm = 20`** — confirm from About-Energy electrode spec. Currently unknown origin.
6. **`m_bOnly1D` pattern** — confirm [0,0,0,0] is correct vs [1,0,0,0]. Check Siemens documentation for first-block flag semantics.
7. **Geometry test result** — understand what topology BDS generates for all 4 variants before locking the production tab configuration.
