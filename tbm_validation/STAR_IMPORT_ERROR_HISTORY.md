# STAR-CCM+ TBM Import Error History

Complete record of every STAR-CCM+ / BDS runtime error reported by Robert (client-side testing), in chronological order. Each entry records the verbatim error text, the file tested, the confirmed or candidate cause, and whether a fix was confirmed by a subsequent passing import.

**Do not delete or modify historical entries. Append new entries only.**

---

## Summary Table

| # | Date | Package / File | Error | Cause | Fix Applied | Fix Confirmed? |
|---|------|---------------|-------|-------|-------------|----------------|
| 1 | 2026-09-03 | tbm_geometry_test_20260903 (v1–v4) | Mandrel thickness must be positive | `m_dMandrelThickness_mm = 0` in Detailed Builder | Set to 6 mm | Not directly — superseded by next error |
| 2 | 2026-09-07 | tbm_geometry_test_20260907 (v1–v4) | Unknown (new error after mandrel fix) | Unknown — logs not preserved | Unknown | NO — error text never received |
| 3 | 2026-09-07 | tbm_geometry_test_20260907 | `m_bOnly1D` warning + unknown downstream error | `m_bOnly1D = 1` in SIMMOD blocks | Set all to 0 | UNCONFIRMED |
| 4 | 2026-09-04 | tbm_geometry_test_20260904 | Mandrel thickness must be positive | Same as #1 | (same) | No |
| 5 | 2026-09-09 | hp2170-rcr-v1-tabs-on-sameFace | Electrode Root 1: Extrusion distance can not be 0 | MISDIAGNOSED as `+Electrode m_dS3 = 0`; actual cause UNRESOLVED | S3 set to 5 | **NO — same error persists in v5** |
| 6 | 2026-09-10 | hp2170NCA-RCR-distributed-exact-contact-final | Electrode Root 1: Extrusion distance can not be 0 | Candidate: `m_dSepFeedLength_mm = 0` and `m_dSepTailLength_mm = 0` in Detailed Builder | SepFeed=10, SepTail=85 applied 2026-09-10 | **PENDING — awaiting Robert's test** |

---

## Error 1 — tbm_geometry_test_20260903 (2026-09-03)

**Package:** `tbm_geometry_test_20260903.zip` (all four tab variants: v1–v4)
**Files:** `hp2170-test-v1-tabs-on-standard.tbm`, `hp2170-test-v2-tabs-off-standard.tbm`, `hp2170-test-v3-tabs-on-sameFace.tbm`, `hp2170-test-v4-tabs-off-sameFace.tbm`
**TBM SHA-256:** Not recorded (predates SHA-256 audit)

**Error text (verbatim from Robert):**
```
Read 5549 lines from F:\About-Energy\20260903\tbm_geometry_test_20260903\hp2170-test-v1-tabs-on-standard.tbm

LiIon     Electrolyte        General Electrolyte     load message

Note:  [Transport Number sets] not found in the file, defaulting to 0.

Warning: m_bOnly1D option is not supported.
Warning: m_bOnly1D option is not supported.

Unable to create cell from F:\About-Energy\20260903\tbm_geometry_test_20260903\hp2170-test-v1-tabs-on-standard.tbm: Error: Mandrel thickness must be positive
```
(Same error for all four variants in this package.)

**STAR-CCM+ operation:** Batteries > Battery Cell > Create from Tbm

**Pre-error warnings (also present):**
- `[Transport Number sets] not found in the file, defaulting to 0` — field absent, harmless default applied
- `Warning: m_bOnly1D option is not supported` — appears twice per file

**Confirmed cause:**
`m_dMandrelThickness_mm = 0` in the Detailed Builder (`<BUILDER>`) section. STAR-CCM+ requires a positive mandrel diameter to construct the jelly-roll winding geometry. The source TBM (hp2170NCA-ECM.tbm) had this field absent or zero — a placeholder from the 1D-mode template.

Correct value for hp2170 NCA 21700: 6 mm (from AE characterisation data).

**Fix applied in subsequent package:**
`m_dMandrelThickness_mm` set to 6 mm in all generated variants.

**Validator check:** `mandrel_thickness` → FAIL if `m_dMandrelThickness_mm ≤ 0`.

---

## Error 2 — tbm_geometry_test_20260904 (2026-09-04)

**Package:** `tbm_geometry_test_20260904.zip`
**Files:** `hp2170-test-v1-tabs-on-standard.tbm` (at minimum)
**TBM SHA-256:** Not recorded

**Error text (verbatim from Robert):**
```
Read 5549 lines from F:\About-Energy\20260903\tbm_geometry_test_20260904\hp2170-test-v1-tabs-on-standard.tbm

LiIon     Electrolyte        General Electrolyte     load message

Note:  [Transport Number sets] not found in the file, defaulting to 0.

Warning: m_bOnly1D option is not supported.
Warning: m_bOnly1D option is not supported.

Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
   error: Server Error
```

**STAR-CCM+ operation:** Batteries > Battery Cell > Create from Tbm

**Note on progression:** The Mandrel error (Error 1) does not appear — the mandrel fix was applied between 20260903 and 20260904 packages. The `m_bOnly1D` warnings remain. A new blocking error appears: **Electrode Root 1**.

**Confirmed cause (retrospective, 2026-09-10):**
`m_dElectrodeOverlapAtStart_mm = 0` in the Detailed Builder. STAR requires a positive inner-winding lead-in dimension to extrude "Electrode Root 1". The source TBM had 0 (1D-mode placeholder); the correct value (8 mm) was already present in the Simple Builder section but BDS reads Detailed Builder.

**Fix applied:**
`m_dElectrodeOverlapAtStart_mm` set to 8 mm (copied from Simple Builder).

**Validator check:** `overlap_start` → FAIL if `m_dElectrodeOverlapAtStart_mm = 0`.

---

## Error 3 — tbm_geometry_test_20260907 (2026-09-07)

**Package:** `tbm_geometry_test_20260907.zip` (four variants)
**Files:** `hp2170-test-v1-tabs-on-standard.tbm` and others
**TBM SHA-256:** Not recorded

**Error text (verbatim from Robert — partial, new error not preserved):**
```
Read 5549 lines from F:\About-Energy\20260907\V2\tbm_geometry_test_20260907\hp2170-test-v1-tabs-on-standard.tbm

LiIon     Electrolyte        General Electrolyte     load message

Note:  [Transport Number sets] not found in the file, defaulting to 0.

Warning: m_bOnly1D option is not supported.
Warning: m_bOnly1D option is not supported.

Read 5549 lines from F:\About-Energy\20260907\V2\tbm_geometry_test_20260907\hp2170-test-v1-tabs-on-standard.tbm
```
Robert reported: "Gets a bit further but gives a new error for all four cases." The specific new error text was not provided.

**STAR-CCM+ operation:** Batteries > Battery Cell > Create from Tbm

**Note:** The Electrode Root 1 error (Error 2) does not appear — the `m_dElectrodeOverlapAtStart_mm = 8` fix was effective. A new error occurred but was not captured. `m_bOnly1D` warnings remain.

**Diagnosis:** Unknown — error text never received from Robert. The `m_bOnly1D` warnings are present and likely contributed.

**Fix applied (package_rev3):**
All `m_bOnly1D` occurrences set to 0 in all SIMMOD blocks (was 1 in source file for all 24 blocks).

**Validator check:** `m_bOnly1D_rcrtable` → FAIL if RCRTable 3D block has `m_bOnly1D = 1`.

**⚠ CRITICAL GAP:** The actual error text for this package was never recorded. The subsequent fix (m_bOnly1D → 0) was applied without knowing which error it was addressing. Confirmation that this fix resolved the unknown error was never obtained.

---

## Error 4 — hp2170-rcr-v1-tabs-on-sameFace (2026-09-09)

**Package:** `tbm_geometry_test_20260909.zip` (RCR distributed candidate V1)
**File:** `hp2170-rcr-v1-tabs-on-sameFace.tbm`
**TBM SHA-256:** `7d5850b628389e713e83468d27e45600942b1deb1e23e672f9d18c4f580d6940`
**Line count:** 5549

**Error text (verbatim from Robert):**
```
Read 5549 lines from F:\About-Energy\20260909\hp2170-rcr-v1-tabs-on-sameFace.tbm

LiIon     Electrolyte        General Electrolyte     load message

Note:  [Transport Number sets] not found in the file, defaulting to 0.

Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
   error: Server Error
```

**STAR-CCM+ operation:** Batteries > Battery Cell > Create from Tbm

**Note on progression:** `m_bOnly1D` warnings absent — the m_bOnly1D fix worked. `Transport Number sets` note still present.

**Misdiagnosis applied (2026-09-09):**
Session on 2026-09-09 identified `+Electrode m_dS3 = 0` as the cause by pattern-matching against reference TBMs (all have S3 = 5). Fix applied: `+Electrode m_dS3 = 0 → 5`. This was documented as "Resolved the geometry extrusion error" — **incorrectly**, because the fix was never confirmed by Robert at STAR runtime.

**Confirmed status of S3 fix:** **WRONG DIAGNOSIS.** Error 5 (2026-09-10) demonstrates that the file with S3 = 5 still produces the identical error. S3 was not the cause.

**Actual cause (candidate, 2026-09-10):**
`m_dSepFeedLength_mm = 0` and `m_dSepTailLength_mm = 0` in the Detailed Builder. Every working reference TBM has non-zero values: `m_dSepFeedLength_mm ≥ 10`, `m_dSepTailLength_mm ≥ 40`. The preflight for exact-contact-final classified these as UNRESOLVED_NONBLOCKING and the geometry audit classified them as ZERO_DIMENSION_PROBABLY_SAFE — both assessments were incorrect.

**Validator check (incorrectly scoped):** `pos_electrode_s3` → FAIL if `+Electrode m_dS3 = 0` (added 2026-09-09; now confirmed insufficient to catch the root cause).

---

## Error 5 — hp2170NCA-RCR-distributed-exact-contact-final (2026-09-10)

**Package:** `out/hp2170NCA-RCR-STAR-exact-contact-final-20260910.zip`
**File:** `hp2170NCA-RCR-distributed-exact-contact-final.tbm`
**TBM SHA-256 (as sent):** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`
**Line count:** 5550

**Error text (verbatim from Robert):**
```
Read 5550 lines from F:\About-Energy\20260910\hp2170NCA-RCR-distributed-exact-contact-final.tbm

Feature execution failed.

Electrode Root 1 : Extrusion distance can not be 0.

Command: CreateFromTbm

   error: Server Error
```

**STAR-CCM+ operation:** Batteries > Battery Cell > Create from Tbm

**Note on progression:** `m_bOnly1D` warnings absent. `Transport Number sets` note absent (field now explicitly present). But Electrode Root 1 error persists despite S3 = 5.

**Confirmed:** S3 fix (Error 4 diagnosis) did NOT resolve this error. S3 was not the cause.

**Cause (candidate, 2026-09-10):**
`m_dSepFeedLength_mm = 0` and `m_dSepTailLength_mm = 0` in the Detailed Builder (`<BUILDER>`, lines 2119–2120 of the file as sent). The Detailed Builder section is what STAR reads for 3D geometry creation. Every working reference TBM in the project repo has:
- `m_dSepFeedLength_mm = 10`
- `m_dSepTailLength_mm = 40` to `85`

The Distributed 2P BUILDER in the same file (second `<BUILDER>` block) correctly has `m_dSepFeedLength = 10` and `m_dSepTailLength = 85`. The RCRTable 3D BUILDER (first `<BUILDER>` block) had both at 0.

**Fix applied (2026-09-10, this session):**
`m_dSepFeedLength_mm = 0 → 10`, `m_dSepTailLength_mm = 0 → 85` in the first `<BUILDER>` block.

**New SHA-256 (post-fix):** `bf0d6c3e5c22cd3f07a48a2b57be56b1dae36f174610ed648fc36dcdacb80b53`

**Fix confirmed:** **PENDING — awaiting Robert's test.**

**Process failure note:**
Between Error 4 and Error 5, sessions applied the (incorrect) S3 fix, declared it "resolved," and built two further versions (V3 preflight, exact-contact-final) without ever getting Robert to confirm V2 passed. The instruction in the STAR_IMPORT_ERROR_HISTORY.md Error 3 entry ("not proven until V2 passes runtime import") was documented but not enforced. The fix for Error 5 must be confirmed by Robert before any further versions are built on top of it.

**Validator check to add:** `sep_feed_tail_nonzero` → FAIL if `m_dSepFeedLength_mm = 0` OR `m_dSepTailLength_mm = 0` in the Detailed Builder.

---

## Process Rules (derived from this error history)

1. Every fix to the Detailed Builder must be confirmed by Robert at STAR runtime before the next version is built on top of it.
2. Any field in the Detailed Builder that is 0 while the same field in all working references is non-zero must be treated as FAIL in the preflight, not WARN or INFO.
3. The Simple Builder section is NOT what STAR reads for 3D geometry. A field being correct in the Simple Builder does not mean the Detailed Builder value is correct.
4. "Static preflight passed" does not mean "STAR runtime will succeed." These are distinct gates.
5. Do not ship a new version without logging the SHA-256 of the file actually sent and the expected state of the runtime test.
