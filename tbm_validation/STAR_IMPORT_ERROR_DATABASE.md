# STAR-CCM+ TBM Import Error Database

**Project:** hp2170 NCA / STAR-CCM+ native distributed battery TBM
**Canonical runtime evidence database**
**Created:** 2026-09-10

## Purpose

This file is the canonical record of **observed client-side STAR-CCM+ TBM import behaviour**. It separates runtime facts from diagnostic hypotheses.

Rules:

1. A TBM field is not declared the root cause of an error merely because changing it is plausible.
2. A proposed fix is only `RUNTIME_CONFIRMED` if STAR subsequently progresses past the exact prior blocker or imports successfully.
3. If the same error persists after a change, that change is `PROVEN_INSUFFICIENT` for eliminating that blocker, even if the field may still be required.
4. Client log text is preserved verbatim where available.
5. Static reference-corpus evidence may rank hypotheses, but it does not replace runtime confirmation.

---

## Error classes

| Error ID | STAR message / condition | Severity | First observed | Last observed | Current status |
|---|---|---:|---|---|---|
| `E001` | `[Transport Number sets] not found in the file, defaulting to 0.` | NOTE | 2026-09-03 | 2026-09-09 | `RESOLVED` — absent after explicit `Transport Number sets = 0` was added |
| `E002` | `Warning: m_bOnly1D option is not supported.` | WARNING | 2026-09-03 | 2026-09-07 | `RESOLVED` — absent in later RCR candidates after relevant flags were set to 0 |
| `E003` | `Error: Mandrel thickness must be positive` | FATAL | 2026-09-03 | 2026-09-03 | `RESOLVED` — later files progressed beyond this check |
| `E004` | `Electrode Root 1 : Extrusion distance can not be 0.` | FATAL | 2026-09-04 | 2026-09-10 | **`ACTIVE / UNRESOLVED`** |

---

# Runtime event database

## `R001` — 2026-09-03 — first four-variant geometry package

**Client location:** `F:\About-Energy\20260903\tbm_geometry_test_20260903\`

**Variants explicitly reported by client:**

- `hp2170-test-v1-tabs-on-standard.tbm`
- `hp2170-test-v2-tabs-off-standard.tbm`
- `hp2170-test-v3-tabs-on-sameFace.tbm`
- `hp2170-test-v4-tabs-off-sameFace.tbm`

**Scope:** all four variants produced the same fatal mandrel-thickness error.

**Observed messages:**

```text
Read 5549 lines from ...
LiIon     Electrolyte        General Electrolyte     load message
Note: [Transport Number sets] not found in the file, defaulting to 0.
Warning: m_bOnly1D option is not supported.
Warning: m_bOnly1D option is not supported.
Unable to create cell from ...: Error: Mandrel thickness must be positive
```

**Observed error classes:** `E001`, `E002`, `E003`.

**Runtime conclusion:**

- STAR read the TBM far enough to parse the electrolyte block.
- Missing `Transport Number sets` was non-fatal and STAR defaulted it to 0.
- `m_bOnly1D` produced warnings but was not the terminating message.
- The fatal blocker was mandrel thickness.
- Tab on/off and standard/same-face orientation did not affect this blocker because all four variants stopped at the same error.

**Progress evidence:** later packages progressed past `E003`, so the mandrel-thickness correction is runtime-confirmed as sufficient to clear that specific blocker.

---

## `R002` — 2026-09-04 — second four-variant geometry package

**Client location shown:** `F:\About-Energy\20260903\tbm_geometry_test_20260904\`

**Example shown:** `hp2170-test-v1-tabs-on-standard.tbm`

**Client statement:** the new error occurred **for all four cases**.

**Observed messages:**

```text
Read 5549 lines from ...
LiIon     Electrolyte        General Electrolyte     load message
Note: [Transport Number sets] not found in the file, defaulting to 0.
Warning: m_bOnly1D option is not supported.
Warning: m_bOnly1D option is not supported.
Read 5549 lines from ...
LiIon     Electrolyte        General Electrolyte     load message
Note: [Transport Number sets] not found in the file, defaulting to 0.
Warning: m_bOnly1D option is not supported.
Warning: m_bOnly1D option is not supported.
Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
error: Server Error
```

**Observed error classes:** `E001`, `E002`, `E004`.

**Runtime conclusion:**

- This package cleared the prior mandrel-thickness blocker `E003`.
- STAR then reached a later geometry feature and failed on `E004`.
- All four tab/orientation variants produced the same `E004`; therefore tab enablement and same-face/standard orientation are not the cause of this particular blocker.

---

## `R003` — 2026-09-07 — V2 four-variant geometry package

**Client location shown:** `F:\About-Energy\20260907\V2\tbm_geometry_test_20260907\`

**Example shown:** `hp2170-test-v1-tabs-on-standard.tbm`

**Client statement:** `Same error for all four cases I'm afraid.`

The displayed excerpt contains the same initial parse sequence:

```text
Read 5549 lines from ...
LiIon     Electrolyte        General Electrolyte     load message
Note: [Transport Number sets] not found in the file, defaulting to 0.
Warning: m_bOnly1D option is not supported.
Warning: m_bOnly1D option is not supported.
Read 5549 lines from ...
```

The client's statement refers to the immediately preceding `Electrode Root 1 : Extrusion distance can not be 0` failure and confirms that all four variants still produced that same error.

**Observed error classes:** `E001`, `E002`, `E004`.

**Runtime conclusion:** `E004` persisted across another four-variant package.

---

## `R004` — 2026-09-09 — RCR distributed V1

**File:** `hp2170-rcr-v1-tabs-on-sameFace.tbm`

**Client location:** `F:\About-Energy\20260909\hp2170-rcr-v1-tabs-on-sameFace.tbm`

**Known SHA-256:** `7d5850b628389e713e83468d27e45600942b1deb1e23e672f9d18c4f580d6940`

**Observed messages:**

```text
Read 5549 lines from F:\About-Energy\20260909\hp2170-rcr-v1-tabs-on-sameFace.tbm
LiIon     Electrolyte        General Electrolyte     load message
Note: [Transport Number sets] not found in the file, defaulting to 0.

Read 5549 lines from F:\About-Energy\20260909\hp2170-rcr-v1-tabs-on-sameFace.tbm
LiIon     Electrolyte        General Electrolyte     load message
Note: [Transport Number sets] not found in the file, defaulting to 0.

Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
error: Server Error
```

**Observed error classes:** `E001`, `E004`.

**Not observed:** `E002` (`m_bOnly1D` warning no longer appears).

**Runtime conclusion:**

- The `m_bOnly1D` warning was cleared in this lineage.
- The fatal `E004` remained.
- Therefore fixing `m_bOnly1D` was necessary for warning cleanup but **insufficient to eliminate `E004`**.

---

## `R005` — 2026-09-10 — exact-contact final preflight candidate

**File:** `hp2170NCA-RCR-distributed-exact-contact-final.tbm`

**Client location:** `F:\About-Energy\20260910\hp2170NCA-RCR-distributed-exact-contact-final.tbm`

**SHA-256:** `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`

**Observed messages:**

```text
Read 5550 lines from F:\About-Energy\20260910\hp2170NCA-RCR-distributed-exact-contact-final.tbm

Read 5550 lines from F:\About-Energy\20260910\hp2170NCA-RCR-distributed-exact-contact-final.tbm

Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
error: Server Error
```

**Observed error class:** `E004` only.

**Not observed:**

- `E001` transport-number note — cleared after explicit `Transport Number sets = 0`.
- `E002` `m_bOnly1D` warning — cleared.
- `E003` mandrel-thickness error — cleared.

**Known relevant geometry/model state in this candidate:**

```text
m_dElectrodeOverlapAtStart_mm = 8
+Electrode m_dS3               = 5
m_dSepFeedLength_mm            = 0
m_dSepTailLength_mm            = 0
m_dJellyrollThickness_mm       = 20.6274
Package m_dintDiameter         = 20.6274
Transport Number sets          = 0
IET                             = RCRTable 3D
Thermal                         = Distributed
```

**Runtime conclusion:**

- `E004` persists despite `+Electrode m_dS3 = 5`.
- `E004` persists despite explicit `Transport Number sets = 0`.
- `E004` persists with exact JR/can-ID equality (`20.6274 / 20.6274`).
- Therefore none of those changes, individually or collectively, eliminated `E004` in this candidate.

---

# `E004` hypothesis ledger — Electrode Root 1 zero extrusion

This section exists specifically to prevent future agents from converting a plausible correlation into a claimed root cause without runtime proof.

| Hypothesis | Evidence when proposed | Change/test performed | Runtime result | Current status |
|---|---|---|---|---|
| `H004-1`: Detailed Builder `m_dElectrodeOverlapAtStart_mm = 0` causes `E004` | zero-valued geometry field; later set to 8 | changed to 8 mm in later lineage | `E004` still occurred repeatedly | `PROVEN_INSUFFICIENT_AS_SOLE_CAUSE` |
| `H004-2`: `+Electrode m_dS3 = 0` causes `E004` | STAR-install refs use 5; candidate used 0; plausible root segment | changed to 5 mm | `R005` still produced identical `E004` | `PROVEN_INSUFFICIENT_AS_SOLE_CAUSE` |
| `H004-3`: missing `Transport Number sets` contributes to `E004` | importer explicitly logged missing field | added `Transport Number sets = 0` | note disappeared, `E004` remained | `DISPROVEN_FOR_E004`; field addition still valid for importer completeness |
| `H004-4`: JR/can radial mismatch causes `E004` | prior candidate had 19.25-mm JR vs 20.6274-mm can ID | exact-contact candidate uses 20.6274 / 20.6274 | `E004` remained | `DISPROVEN_FOR_E004` |
| `H004-5`: Detailed Builder `m_dSepFeedLength_mm = 0` and/or `m_dSepTailLength_mm = 0` feeds a mandatory zero extrusion | both remain zero; STAR-install cylindrical refs use nonzero values such as 10/85; exact error is zero extrusion | changed to 10/85 mm in first `<BUILDER>` block (2026-09-10); fix candidate SHA-256 `bf0d6c3e`; R006 package sent to Robert | **RUNTIME_PENDING** | **`CANDIDATE_APPLIED / RUNTIME_PENDING`** |

Important: `H004-5` must **not** be described as the confirmed cause until Robert's test of the R006 candidate shows STAR progresses past `E004`.

---

# Proven negative evidence for `E004`

The following changes/configuration differences did **not** eliminate the `Electrode Root 1` error:

- positive/negative tabs on vs off;
- standard vs same-face tab orientation;
- setting `m_bOnly1D` flags to the later zero configuration;
- setting Detailed Builder start overlap to 8 mm;
- setting `+Electrode m_dS3` from 0 to 5 mm;
- adding `Transport Number sets = 0`;
- changing JR OD from the earlier 19.25-mm value to exact contact at 20.6274 mm.

These facts should be used to prune future diagnoses.

---

# Current blocker state

```text
ACTIVE_FATAL_BLOCKER = E004
MESSAGE = Electrode Root 1 : Extrusion distance can not be 0.
FIRST_OBSERVED = 2026-09-04
LAST_OBSERVED = 2026-09-10
RUNTIME_OCCURRENCES = multiple packages / multiple variants
ROOT_CAUSE = UNRESOLVED
LEADING_HYPOTHESIS = H004-5 (SepFeedLength_mm/SepTailLength_mm = 0)
HYPOTHESIS_STATUS = CANDIDATE_APPLIED
FIX_CANDIDATE_SHA256 = bf0d6c3e5c22cd3f07a48a2b57be56b1dae36f174610ed648fc36dcdacb80b53
FIX_CANDIDATE_RUNTIME_EVENT = R006 (PENDING — awaiting Robert)
```

## Required evidence standard for closure

`E004` may only be marked resolved when one of the following occurs:

1. STAR `CreateFromTbm` completes successfully; or
2. STAR progresses to a different downstream error after a controlled change and the exact prior `Electrode Root 1` error is absent.

A static comparison or a plausible field-name mapping is not sufficient.

---

## `R006` — 2026-09-10 — H004-5 fix candidate (SepFeed/Tail nonzero)

**File:** `hp2170NCA-RCR-distributed-exact-contact-final.tbm` (modified in-place)

**SHA-256:** `bf0d6c3e5c22cd3f07a48a2b57be56b1dae36f174610ed648fc36dcdacb80b53`

**TBM delta from R005:**

```text
m_dSepFeedLength_mm  0 → 10   (Detailed Builder, first <BUILDER> block, RCRTable 3D)
m_dSepTailLength_mm  0 → 85   (Detailed Builder, first <BUILDER> block, RCRTable 3D)
```

Values match the second `<BUILDER>` block (Distributed 2P) in the same file, which already had `m_dSepFeedLength = 10` and `m_dSepTailLength = 85`.

**Rationale for H004-5 as next test:**
Every working reference TBM in the repo has `m_dSepFeedLength_mm ≥ 10` and `m_dSepTailLength_mm ≥ 40`. The R005 candidate (and all prior candidates) had both at 0. After R005 proved S3=5 and ElectrodeOverlapAtStart=8 insufficient, these are the only remaining zero-valued geometry dimensions in the Detailed Builder.

**Runtime result:** PENDING — awaiting Robert's test.

**What this test will prove if E004 disappears:** H004-5 confirmed. Separator feed/tail zeros were the extrusion-distance source. May also be true that multiple zeros contributed cumulatively.

**What this test will prove if E004 persists:** H004-5 insufficient. Root cause remains unresolved; all known Detailed Builder zero-field hypotheses will be exhausted. Next action: obtain full STAR-CCM+ geometry creation log from Robert (not just the final error line).

---

# Next-entry template

```text
Runtime event ID:
Date:
Client file/path:
SHA-256:
Variant scope:
Exact log text:
Observed error IDs:
Previous error absent/present:
TBM delta from previous runtime-tested file:
What this result proves:
What this result does NOT prove:
New/updated hypothesis status:
```
