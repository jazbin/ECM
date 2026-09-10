# STAR-CCM+ E004 Multifile Diagnostic Campaign — 2026-09-10

## Objective

Resolve the persistent STAR-CCM+ geometry blocker:

```text
Feature execution failed.
Electrode Root 1 : Extrusion distance can not be 0.
Command: CreateFromTbm
```

This exact fatal error has persisted across multiple TBM generations. Do **not** assume any single field is the root cause until a controlled runtime result proves that STAR progresses past E004.

The purpose of this campaign is to exploit the fact that `Create from Tbm` is cheap for Robert to execute. Instead of sending one speculative fix at a time, generate a controlled family of TBMs that isolates the leading remaining geometry hypotheses and includes broad rescue configurations.

Canonical runtime evidence is in:

`tbm_validation/STAR_IMPORT_ERROR_DATABASE.md`

## Governing modelling objective

The final production target remains the OpenFOAM–ECM reference model, not a reconstructed realistic cell interior.

Protected production intent:

- JR OD = can ID = `20.6274 mm`.
- Ideal JR–can contact.
- Ideal applicable JR–cap/end contact.
- RCRTable 3D electrochemical model.
- Distributed thermal model.
- Same-face/top tabs.
- About-Energy RCR numerical data unchanged.

Diagnostic variants may temporarily alter selected geometry-builder fields only to identify E004. A diagnostic value that imports successfully is **not automatically the production value**.

---

# 1. Immutable failed baseline

Use this exact failed runtime-tested file as the source for every diagnostic variant unless a variant explicitly says otherwise:

`out/hp2170NCA-RCR-distributed-exact-contact-final.tbm`

Runtime-tested SHA-256:

`2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`

Before generating anything, verify the SHA. Abort if it does not match.

Do **not** use a manually edited working copy as the campaign base.

Relevant Detailed Builder baseline values:

```text
m_dElectrodeOverlapAtStart_mm = 8
m_dElectrodeOverlapAtEnd_mm   = 20
m_dJellyrollThickness_mm      = 20.6274
m_dJellyrollWidth_mm          = 0
m_dMandrelThickness_mm        = 6
m_dMandrelWidth_mm            = 6
m_dSepFeedLength_mm           = 0
m_dSepTailLength_mm           = 0
m_dSeparatorThicknessTarget_mm = 0
m_dOffsetNegAvg               = 1
m_dOffsetPosAvg               = 0.5
m_dOffsetSepAvg               = 0
+Electrode m_dS1              = 5
+Electrode m_dS2              = 7
+Electrode m_dS3              = 5
-Electrode m_dS1              = 7
-Electrode m_dS2              = 7
-Electrode m_dS3              = 50
```

---

# 2. Current suspect ranking

## Rank 1 — separator feed/tail lengths — HIGH

Baseline:

```text
m_dSepFeedLength_mm = 0
m_dSepTailLength_mm = 0
```

Siemens STAR cylindrical reference pattern includes nonzero values:

```text
m_dSepFeedLength_mm = 10
m_dSepTailLength_mm = 85
```

These are literal geometry lengths, remained zero through the later E004 failures, and directly match the generic failure class `Extrusion distance can not be 0` better than the other unresolved fields.

They are the leading hypothesis, but are not yet runtime-proven as the E004 cause.

## Rank 2 — interaction of separator feed/tail with root/overlap geometry — MEDIUM

`Electrode Root 1` may be generated from a derived expression involving several builder quantities rather than from one field directly.

Potential participants:

```text
m_dSepFeedLength_mm
m_dSepTailLength_mm
m_dElectrodeOverlapAtStart_mm
m_dElectrodeOverlapAtEnd_mm
```

## Rank 3 — electrode overlap at end — MEDIUM/LOW

Baseline:

```text
m_dElectrodeOverlapAtEnd_mm = 20
```

STAR reference pattern commonly uses `40`. Baseline is nonzero, so it is less likely to directly create a zero extrusion, but it may enter a derived root-length expression.

## Rank 4 — mandrel width convention — LOW

Baseline:

```text
m_bMandrelFlat = 0
m_dMandrelThickness_mm = 6
m_dMandrelWidth_mm = 6
```

STAR cylindrical references commonly use round mandrel with:

```text
m_bMandrelFlat = 0
m_dMandrelThickness_mm = 6
m_dMandrelWidth_mm = 0
```

Mandrel thickness itself is already positive and the earlier `Mandrel thickness must be positive` blocker was cleared. Width remains worth one controlled probe because the exact STAR builder convention differs.

## Rank 5 — Detailed Builder jelly-roll width — LOW

Baseline:

```text
m_dJellyrollWidth_mm = 0
```

STAR cylindrical references also use zero here and August STEP characterization indicated this field did not control realized JR axial length. Therefore this is low probability, but because it is a zero geometry field it gets one explicit probe.

## Very low / do not modify in the primary campaign

These are zero in working STAR references or are optional by configuration:

```text
m_dSeparatorThicknessTarget_mm = 0
m_dOffsetSepAvg = 0
m_dOverwrapThickness_um = 0
m_dOverwrapWidth = 0
+/- Electrode S4/S5/S6 = 0
```

Do not assign arbitrary nonzero values to these.

## Already shown insufficient / eliminated for E004

Do not spend variants repeating these:

- `m_dElectrodeOverlapAtStart_mm: 0 -> 8` did not eliminate E004.
- `+Electrode m_dS3: 0 -> 5` did not eliminate E004.
- adding `Transport Number sets = 0` removed the note but did not eliminate E004.
- JR OD `19.25 -> 20.6274` did not eliminate E004.
- tab on/off and standard/same-face variants all reached the same blocker in earlier four-file campaigns.

---

# 3. Campaign variants

Generate the following campaign in:

`out/e004_multifile_campaign_20260910/`

Every diagnostic TBM except C00 must be generated directly from the immutable failed baseline SHA above.

## C00 — Siemens runtime control

Filename:

`C00_SIEMENS_CONTROL_validationBattery.tbm`

Content:

Unmodified Siemens STAR-install `validationBattery.tbm` from the repository reference corpus.

Purpose:

Prove that Robert's installed STAR version and exact `Create from Tbm` workflow successfully import a known Siemens cylindrical TBM.

No project data are expected in this file. It is strictly an environment/import-path control.

## C01 — feed only

Filename:

`C01_FEED10.tbm`

Only delta:

```text
m_dSepFeedLength_mm: 0 -> 10
```

Purpose: isolate separator feed length.

## C02 — tail only

Filename:

`C02_TAIL85.tbm`

Only delta:

```text
m_dSepTailLength_mm: 0 -> 85
```

Purpose: isolate separator tail length.

## C03 — feed + tail

Filename:

`C03_FEED10_TAIL85.tbm`

Only deltas:

```text
m_dSepFeedLength_mm: 0 -> 10
m_dSepTailLength_mm: 0 -> 85
```

Purpose: highest-probability combined fix and direct interaction test.

## C04 — overlap end only

Filename:

`C04_END40.tbm`

Only delta:

```text
m_dElectrodeOverlapAtEnd_mm: 20 -> 40
```

Purpose: isolate end-overlap influence.

## C05 — feed + tail + overlap end

Filename:

`C05_FEED10_TAIL85_END40.tbm`

Deltas:

```text
m_dSepFeedLength_mm: 0 -> 10
m_dSepTailLength_mm: 0 -> 85
m_dElectrodeOverlapAtEnd_mm: 20 -> 40
```

Purpose: test whether E004 depends on separator lengths plus end-overlap interaction.

## C06 — mandrel width convention only

Filename:

`C06_MANDRELWIDTH0.tbm`

Only delta:

```text
m_dMandrelWidth_mm: 6 -> 0
```

Do not change `m_dMandrelThickness_mm = 6` or `m_bMandrelFlat = 0`.

Purpose: test STAR's round-mandrel builder convention independently.

## C07 — feed + tail + mandrel width convention

Filename:

`C07_FEED10_TAIL85_MANDRELWIDTH0.tbm`

Deltas:

```text
m_dSepFeedLength_mm: 0 -> 10
m_dSepTailLength_mm: 0 -> 85
m_dMandrelWidth_mm: 6 -> 0
```

Purpose: test separator hypothesis with STAR-reference mandrel-width convention.

## C08 — jelly-roll width only

Filename:

`C08_JRWIDTH65p11.tbm`

Only delta:

```text
m_dJellyrollWidth_mm: 0 -> 65.11
```

Purpose: low-probability probe of a remaining zero-valued Detailed Builder geometry field.

This is diagnostic only; STAR references commonly use zero here.

## C09 — feed + tail + jelly-roll width

Filename:

`C09_FEED10_TAIL85_JRWIDTH65p11.tbm`

Deltas:

```text
m_dSepFeedLength_mm: 0 -> 10
m_dSepTailLength_mm: 0 -> 85
m_dJellyrollWidth_mm: 0 -> 65.11
```

Purpose: catch an unexpected interaction involving the Detailed Builder axial width.

## C10 — STAR-like critical Builder pattern

Filename:

`C10_STAR_BUILDER_PATTERN.tbm`

Deltas from baseline:

```text
m_dSepFeedLength_mm:           0 -> 10
m_dSepTailLength_mm:           0 -> 85
m_dElectrodeOverlapAtStart_mm: 8 -> 3
m_dElectrodeOverlapAtEnd_mm:  20 -> 40
m_dMandrelWidth_mm:            6 -> 0
```

Keep project-specific cell dimensions, electrode/separator widths, exact-contact JR OD, tabs, RCR data and MODELMAP unchanged.

Purpose: broad rescue test using the critical Detailed Builder conventions of a working STAR cylindrical reference while retaining the project cell itself.

## C11 — STAR-like Builder pattern + explicit JR width

Filename:

`C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm`

Deltas from baseline:

```text
m_dSepFeedLength_mm:           0 -> 10
m_dSepTailLength_mm:           0 -> 85
m_dElectrodeOverlapAtStart_mm: 8 -> 3
m_dElectrodeOverlapAtEnd_mm:  20 -> 40
m_dMandrelWidth_mm:            6 -> 0
m_dJellyrollWidth_mm:          0 -> 65.11
```

Purpose: maximum geometry-builder rescue variant without changing project-specific physical widths, exact-contact radial geometry, tab topology, thermal model or RCR model/data.

---

# 4. Protected fields — must remain byte/semantic-equivalent across C01–C11

Except for the explicitly listed diagnostic deltas above, do not change:

```text
Package m_dextDiameter = 21.09
Package m_dextHeight   = 70.02
Package m_dintDiameter = 20.6274
m_dJellyrollThickness_mm = 20.6274
m_dMandrelThickness_mm = 6
+Electrode width / collector width = 64.11
-Electrode width / collector width = 65.11
Separator width = 67.11
+Electrode m_dS1/S2/S3 = 5/7/5
-Electrode m_dS1/S2/S3 = 7/7/50
m_bNegTab = 1
m_bPosTab = 1
m_nNegTabVertOrientation = 0
m_nPosTabVertOrientation = 0
Transport Number sets = 0
MODELMAP Electrolyte = General Electrolyte
MODELMAP IET = RCRTable 3D
MODELMAP Thermal = Distributed
RCRTable 3D m_bOnly1D = 0
RCRTable 3D m_bLumpedEnergyBalance = 0
m_dAhCell = 5.0
m_nRCRParameterSets = 3
all About-Energy RCR numerical data
```

Do not make any other cleanup edits while generating the campaign.

---

# 5. Generation requirements

Create a dedicated deterministic generator, for example:

`tools/generate_e004_multifile_campaign.py`

Requirements:

1. SHA-pin the immutable baseline.
2. Generate every C01–C11 file from that baseline independently.
3. Never generate a variant from another variant.
4. Assert the exact intended field delta count for each file.
5. Fail if an intended field occurs an unexpected number of times in the Detailed Builder section.
6. Preserve line endings/encoding unless the field edit itself requires otherwise.
7. Run the current TBM validator on every project variant.
8. Verify protected model/RCR fields are identical to baseline.
9. Compute SHA-256 for every file.
10. Generate a machine-readable campaign matrix.

---

# 6. Campaign matrix

Create:

`out/e004_multifile_campaign_20260910/CAMPAIGN_MATRIX.csv`

Columns at minimum:

```text
id
filename
base_sha256
sha256
changed_fields
sep_feed_mm
sep_tail_mm
overlap_start_mm
overlap_end_mm
mandrel_width_mm
jr_width_mm
expected_purpose
runtime_result
runtime_error_class
runtime_notes
```

Also create:

`out/e004_multifile_campaign_20260910/CAMPAIGN_MATRIX.md`

with a readable version of the same information and exact one-line delta summaries.

---

# 7. Robert README

Create a short `README.txt` for the client package.

Explain that this is a diagnostic campaign for the persistent `Electrode Root 1` zero-extrusion error and that each file intentionally changes only a controlled geometry subset.

Ask Robert to run `Create from Tbm` for every file and return results in this compact format:

```text
C00: PASS / <exact error text>
C01: PASS / <exact error text>
C02: PASS / <exact error text>
C03: PASS / <exact error text>
C04: PASS / <exact error text>
C05: PASS / <exact error text>
C06: PASS / <exact error text>
C07: PASS / <exact error text>
C08: PASS / <exact error text>
C09: PASS / <exact error text>
C10: PASS / <exact error text>
C11: PASS / <exact error text>
```

If a file successfully creates geometry, ask him to stop nothing; simply record PASS and continue testing the remaining files. A screenshot/STEP export is useful after the campaign, but not required for the first diagnostic pass.

The exact error text matters. Do not reduce a new error to just PASS/FAIL if STAR progresses to a different blocker.

---

# 8. Recommended runtime order

Robert can test all files, but use this order so we get useful information quickly:

```text
C00
C03
C01
C02
C10
C05
C07
C04
C06
C08
C09
C11
```

Interpretation:

- C00 first validates the STAR environment/reference path.
- C03 attacks the leading hypothesis immediately.
- C01/C02 separate feed from tail.
- C10 gives an early broad STAR-like rescue result.
- remaining tests localize interactions.

---

# 9. Result interpretation logic

## If C00 fails

Stop interpreting project variants as a pure TBM-content problem until the Siemens control failure is understood. Record the exact C00 error separately.

## If C01 passes and C02 fails

Separator feed length is sufficient to clear E004 under the baseline configuration.

Do not yet claim tail is irrelevant to final geometry; only claim feed is sufficient to clear this blocker.

## If C02 passes and C01 fails

Separator tail length is sufficient to clear E004 under the baseline configuration.

## If C03 passes while both C01 and C02 fail

The feed/tail combination is required, or the underlying feature depends on both lengths.

## If C01/C02/C03 fail but C05 passes

End-overlap participates in the successful geometry relation together with feed/tail.

## If C03 fails but C07 passes

Mandrel-width convention interacts with separator feed/tail.

## If only C10/C11 pass

The issue is a broader Detailed Builder compatibility relation. Use the delta between C10/C11 and failed narrower variants to design the next binary-search campaign. Do not immediately copy all C10/C11 values into production without localization.

## If C08 passes

`m_dJellyrollWidth_mm=0` is implicated despite the prior reference/STEP evidence. Investigate why this project geometry differs from the known reference behavior.

## If all C01–C11 fail with E004 while C00 passes

This is highly informative: the current suspect set is incomplete. Do **not** send another one-off fix. Re-audit fields outside the current Detailed Builder shortlist, especially fields used to construct positive electrode root geometry, and compare the full failed baseline against a runtime-confirmed Siemens reference.

## If a variant reaches a new error

That is progress past E004. Record E004 as cleared for that variant and add the new runtime message to `STAR_IMPORT_ERROR_DATABASE.md` as a new error class. Do not conflate a new blocker with campaign failure.

---

# 10. Packaging

Create one ZIP:

`out/hp2170NCA-STAR-E004-multifile-diagnostic-20260910.zip`

Contents:

- `README.txt`
- `CAMPAIGN_MATRIX.csv`
- `CAMPAIGN_MATRIX.md`
- C00–C11 TBM files

No other files.

Verify ZIP member names and compute ZIP SHA-256.

---

# 11. Documentation and GitHub

After generation:

1. Add the campaign to `tbm_validation/TBM_INVENTORY.md`.
2. Add a `CAMPAIGN_PREPARED` entry to `tbm_validation/STAR_IMPORT_ERROR_DATABASE.md` without pretending any hypothesis is confirmed.
3. Do not overwrite historical failed TBMs.
4. Do not change the canonical production target.
5. Push generator, campaign matrices, README, TBMs, ZIP, inventory/error-database updates to branch `tbm-rcr-modelmap-fix-exec`.

---

# 12. Completion report

Return exactly:

- branch
- commit SHA
- verified baseline SHA
- generator path
- number of TBMs in package
- C00 source path and SHA
- C01–C11 SHA values
- exact delta summary for every C01–C11
- validator result for every project variant
- protected-field parity result
- campaign matrix paths
- ZIP path and SHA
- exact ZIP members
- confirmation that nothing was sent to Robert

Do not declare E004 resolved. The campaign exists to obtain the runtime evidence needed to resolve it.
