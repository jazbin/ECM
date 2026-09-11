# E004 Post-ROOT Fallback — Execution Handoff

**Date:** 2026-09-11  
**Branch:** `tbm-rcr-modelmap-fix-exec`  
**Trigger:** execute/package this campaign only if Robert reports the **identical E004** for both ROOT_A and ROOT_B.

## Completed engineering work

Authoritative analysis:

`tbm_validation/E004_TAB_LENGTH_AND_POST_ROOT_FALLBACK_ANALYSIS_20260911.md`

Deterministic generator:

`tools/generate_e004_post_root_fallback.py`

The old C12-first strategy is deliberately retired as the primary fallback because C12 places a 17.9-mm Siemens Detailed-Builder JR target inside the project's 20.6274-mm PCD/cavity. A C12 failure is therefore ambiguous.

The new primary pair is:

1. unmodified Siemens HP18650 control;
2. **complete HP18650 geometry shell** inside immutable project R005 model context.

“Complete geometry shell” means:

- complete `<Physical Cell Description>`;
- **all `<BUILDER>` blocks** (Detailed + Simple in the present corpus);
- `<DEFAULT BUILDER>` selector if present.

All non-geometry project content must remain unchanged. This avoids leaving a stale project Simple Builder inside an otherwise Siemens shell.

## Execute

From repo root on `tbm-rcr-modelmap-fix-exec`:

```bash
python3 tools/generate_e004_post_root_fallback.py
```

The script must abort unless immutable R005 matches:

```text
2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5
```

If local `tbm-siemens-reference-corpus` is absent, the script also tries `origin/tbm-siemens-reference-corpus`.

## Expected outputs

Directory:

```text
out/e004_post_root_fallback_20260911/
```

Files:

```text
HP_CONTROL_hp18650Spiral-DIST.tbm
HP_SHELL_PROJECT_RCR.tbm
C10_STAR_BUILDER_PATTERN.tbm
TL_A_TAB_RELATION_0p10.tbm
TL_B_TAB_RELATION_0p70.tbm
C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm
README.txt
MANIFEST.csv
VALIDATOR_LOG.txt
```

ZIP:

```text
out/hp2170NCA-STAR-E004-post-root-fallback-20260911.zip
```

## Required pre-commit checks

1. `HP_CONTROL_hp18650Spiral-DIST.tbm` is byte-identical to `tbm-siemens-reference-corpus:tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm`.
2. `HP_SHELL_PROJECT_RCR.tbm` differs from R005 only inside:
   - complete PCD;
   - every `<BUILDER>` block;
   - `<DEFAULT BUILDER>` block if present.
   The generator's masked comparison must prove every non-geometry character is unchanged.
3. The number of Builder blocks in each full shell matches its Siemens source.
4. C10 changes only the five declared fields in the first/active Detailed Builder.
5. Each TL file differs from immutable R005 by exactly two lines, both `±Electrode Tab m_dLength_mm`.
6. Each TL file preserves everything after `</Physical Cell Description>` byte-identically.
7. C13 uses the complete validationBattery geometry shell (PCD + all Builders + default selector where present) with project non-geometry context retained.
8. Record SHA-256 for every candidate and the ZIP.
9. Preserve full validator output in `VALIDATOR_LOG.txt`; do not hide inherited FAIL/WARN states.
10. Do not mark E004 resolved or any mechanism confirmed before Robert runtime evidence.

## Runtime order if ROOT_A and ROOT_B both fail

### Stage 1 — environment control

Run:

```text
HP_CONTROL_hp18650Spiral-DIST.tbm
```

- If it fails in the current STAR environment: stop. Do not interpret hybrids.
- If it passes: run `HP_SHELL_PROJECT_RCR.tbm`.

### Stage 2 — complete geometry-shell localization

For `HP_SHELL_PROJECT_RCR.tbm`:

- **E004 absent / different downstream error:** project geometry/PCD/Builder content is strongly implicated.
- **identical E004 while HP_CONTROL passes:** complete known-good geometry is not sufficient; investigate project model/SIMMOD/MODELMAP/non-geometry context and run C13 as the independent shell discriminator.

### Stage 3A — only if HP shell clears E004

Run `C10_STAR_BUILDER_PATTERN.tbm` as the cleaner Builder-only discriminator.

Only if a targeted PCD/root probe is still useful, run TL_A then TL_B. Their `Ltab - electrode width` arithmetic is a **correlation only**; public BDS documentation does not establish that these fields share the same STAR construction axis.

### Stage 3B — if HP shell still gives identical E004

Run:

```text
C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm
```

If both independent complete-shell hybrids fail with identical E004 while the Siemens control passes, stop random geometry perturbations and investigate model/context coupling.

## STEP requirement

Whenever a candidate gets through `CreateFromTbm`, obtain generated geometry/STEP. Construction success is Gate 1 only; production still requires the correct JellyRoll/Can/Cap dimensions and contacts.

## Claude completion report

After executing the generator, report:

- branch and commit SHA;
- ZIP path and SHA-256;
- all candidate SHA-256 values;
- validator summary per candidate;
- confirmation of every invariant above;
- any generator bug and exact fix applied.
