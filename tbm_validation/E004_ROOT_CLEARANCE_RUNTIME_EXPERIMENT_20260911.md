# E004 Root Clearance Runtime Experiment — 2026-09-11

**Status:** PENDING — awaiting Robert's runtime result
**Branch:** tbm-rcr-modelmap-fix-exec
**Author:** Bojan Vidovic / ECM Developer

---

## Hypothesis being tested

The project's package internal height exactly equals the widest wound component (negative electrode/collector):

```
Package m_dintHeight        = 65.11 mm
Negative electrode width    = 65.11 mm
Package-to-negative margin  = 0.00 mm
```

Hypothesis: STAR's electrode-root construction derives an extrusion distance from some function of the package internal height and/or the wound layer geometry. When package internal height equals the widest wound component exactly, that derived quantity may become zero, producing:

```
Electrode Root 1 : Extrusion distance can not be 0.
```

H004-6 is a geometry-construction hypothesis. All electrochemical model fields are frozen in this experiment.

---

## Immutable baseline identity

```
File:    BASELINE_2c89d2d9.tbm
Path:    out/e004_multifile_campaign_20260910/BASELINE_2c89d2d9.tbm
SHA-256: 2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5
Origin:  R005 runtime event (2026-09-10) — last file tested by Robert
         hp2170NCA-RCR-distributed-exact-contact-final.tbm
```

Both candidates were generated independently from this baseline. Neither was derived from any edited working-tree copy of the final TBM.

---

## Exact semantic deltas

### ROOT_A — `ROOT_A_AXIAL_CLEARANCE_0p10.tbm`

```diff
- Package m_dintHeight = 65.11
+ Package m_dintHeight = 65.21
```

Resulting axial margins:
```
Package - Separator = 65.21 - 67.11 = -1.90 mm
Package - Negative  = 65.21 - 65.11 = +0.10 mm   ← was 0.00
Package - Positive  = 65.21 - 64.11 = +1.10 mm
```

**All other fields byte-identical to baseline.**

### ROOT_B — `ROOT_B_AXIAL_CLEARANCE_HE_0p70.tbm`

```diff
- Package m_dintHeight = 65.11
+ Package m_dintHeight = 65.81
```

Resulting axial margins:
```
Package - Separator = 65.81 - 67.11 = -1.30 mm
Package - Negative  = 65.81 - 65.11 = +0.70 mm
Package - Positive  = 65.81 - 64.11 = +1.70 mm
```

The +0.70 mm margin reproduces the HE18650 reference geometry's package/layer proportions while retaining our actual separator and electrode widths.

**All other fields byte-identical to baseline.**

---

## Generated SHA-256 values

```
ROOT_A_AXIAL_CLEARANCE_0p10.tbm     c6db74313e675b618f2fb51d371e51231f9e0a2a9f26ca5bdc1f1bde48390343
ROOT_B_AXIAL_CLEARANCE_HE_0p70.tbm  59f83aa875415d946b1ccb2b6f880a3a98a036e631e3d78993d14edfbbc9ee36
```

---

## Static validation results

Both candidates inherit the pre-existing baseline validator state unchanged:

```
RESULT: 2 FAIL | 3 WARN | 13 INFO | 38 PASS
```

The two FAILs are `sep_feed_nonzero` and `sep_tail_nonzero` — present in the immutable baseline and in every prior tested candidate. These are intentionally retained. This experiment tests only the package-height variable; modifying sep_feed/tail simultaneously would confound the result.

The WARNs are REPORT-block staleness flags (JR diameter, JR height, capacity) — pre-existing. Whether STAR consumes these fields at import is unconfirmed; they have not been observed to control the relevant geometry in prior characterisation work.

Detailed Builder sections: byte-identical to baseline (verified).
MODELMAP block: byte-identical to baseline (verified).
RCRTable 3D block: byte-identical to baseline (verified).
All physical separator/electrode widths: identical to baseline (verified).

---

## Client package

```
out/hp2170NCA-STAR-E004-ROOT-CLEARANCE-diagnostic-20260911.zip
SHA-256: 42be7e3735686f8e58862940b9ecd738b7326ec3168b4d9d8dd7754344608f85
Contents: ROOT_A, ROOT_B, ROOT_CLEARANCE_README.txt, ROOT_CLEARANCE_MANIFEST.csv
```

---

## Interpretation tree

### ROOT_A passes CreateFromTbm (E004 absent)

Strong runtime confirmation that `Package m_dintHeight` / derived axial construction geometry participates causally in E004. The exact internal quantity that STAR computes and that becomes nonzero remains unproven — package height may affect more than the one clearance we are tracking.

Do NOT call 65.21 mm the production solution. The next task is determining how to satisfy STAR's construction requirement while restoring the desired final JellyRoll–Cap contact geometry.

### ROOT_A fails, ROOT_B passes

Consistent with a minimum axial construction allowance or geometry-kernel tolerance between the two tested values (+0.10 mm and +0.70 mm). A bounded threshold search between 0.10 and 0.70 mm follows only if knowing the specific threshold is useful for the production geometry decision.

### ROOT_A and ROOT_B both fail with identical E004

Substantially downgrade the package-internal-height hypothesis. Do not start random field perturbations. The next discriminators are the existing Siemens-transplant candidates already in the campaign: `C12_FULL_SIEMENS_DETAILED_BUILDER.tbm` and `C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm`, using their existing interpretation matrix.

---

## Explicit diagnostic-only statement

ROOT_A and ROOT_B are diagnostic instruments. They are not approved production geometry. Even if one or both pass CreateFromTbm, the package m_dintHeight value will require separate justification and sign-off before it can become the production TBM configuration.

---

## Runtime status

```
STATUS = PENDING
SENT_TO_ROBERT = [date TBD]
RUNTIME_EVENT_ID = [TBD — R007 or later]
```
