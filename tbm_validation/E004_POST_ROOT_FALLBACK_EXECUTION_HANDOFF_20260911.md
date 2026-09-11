# E004 Post-ROOT Fallback — Execution Handoff

**Date:** 2026-09-11  
**Branch:** `tbm-rcr-modelmap-fix-exec`  
**Trigger:** Execute/package this campaign only if Robert reports the **identical E004** for both ROOT_A and ROOT_B.

## Work already completed

The engineering review and campaign logic are complete in:

- `tbm_validation/E004_POST_ROOT_FALLBACK_ANALYSIS_20260911.md` if renamed later, otherwise current file:
  `tbm_validation/E004_TAB_LENGTH_AND_POST_ROOT_FALLBACK_ANALYSIS_20260911.md`
- `tools/generate_e004_post_root_fallback.py`

The revised logic deliberately demotes old C12 because its transplanted Siemens Builder uses a 17.9-mm JR target inside the project's 20.6274-mm PCD/cavity, making a C12 failure ambiguous.

The primary post-ROOT localization pair is now:

1. unmodified Siemens HP18650 control;
2. HP18650 PCD + active Detailed Builder transplanted into the immutable project R005 model/RCR context.

The HP source is preferred because its generated 13-solid STEP is already known geometry-clean, including the generated Tab Root/Tab Stem topology.

## Execute

From repo root on `tbm-rcr-modelmap-fix-exec`:

```bash
python3 tools/generate_e004_post_root_fallback.py
```

The script must abort if immutable R005 does not match:

```text
2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5
```

If the local `tbm-siemens-reference-corpus` ref is absent, the script also tries `origin/tbm-siemens-reference-corpus`.

## Expected output directory

```text
out/e004_post_root_fallback_20260911/
```

Expected candidate files:

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

Expected ZIP:

```text
out/hp2170NCA-STAR-E004-post-root-fallback-20260911.zip
```

## Required pre-commit checks

1. `HP_CONTROL_hp18650Spiral-DIST.tbm` must be byte-identical to:
   `tbm-siemens-reference-corpus:tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm`.
2. `HP_SHELL_PROJECT_RCR.tbm` may differ from R005 only by replacement of:
   - complete `<Physical Cell Description>`;
   - first / active `<BUILDER>` block.
   Project content between those blocks and everything after the first `</BUILDER>` must remain byte-identical.
3. C10 must change only the five declared first-Builder fields.
4. Each TL file must differ from immutable R005 by exactly two lines, both `±Electrode Tab m_dLength_mm`.
5. TL files must preserve all content after `</Physical Cell Description>` byte-identically.
6. C13 may differ from R005 only by complete PCD + first active Builder replacement.
7. Record SHA-256 for every TBM and the ZIP.
8. Preserve the full validator output in `VALIDATOR_LOG.txt`; do not hide inherited warnings/fails.
9. Do not mark E004 resolved or any new hypothesis confirmed before Robert runtime evidence.

## Runtime order for Robert if ROOT_A and ROOT_B both fail

### Stage 1 — environment + geometry/model localization

Run:

```text
HP_CONTROL_hp18650Spiral-DIST.tbm
```

- If this fails in current STAR: stop. Do not interpret hybrids.
- If it passes: run `HP_SHELL_PROJECT_RCR.tbm`.

For `HP_SHELL_PROJECT_RCR.tbm`:

- E004 absent / downstream error -> project geometry/PCD/Builder content is strongly implicated.
- identical E004 while HP_CONTROL passes -> project model/SIMMOD/MODELMAP/non-transplanted context must be investigated; use C13 as the next independent shell discriminator.

### Stage 2A — only if HP shell clears E004

Use `C10_STAR_BUILDER_PATTERN.tbm` as the cleaner Builder-only discriminator.

Only if a targeted PCD/root probe is still useful, use TL_A then TL_B. The tab-length arithmetic is a correlation only: public BDS documentation does not establish that `Tab m_dLength_mm` and electrode `m_dWidth` lie on the same STAR construction axis.

### Stage 2B — if HP shell still gives identical E004

Run:

```text
C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm
```

If both independent geometry-shell hybrids fail with identical E004 while the Siemens control passes, stop random geometry perturbations and investigate model/context coupling.

## STEP requirement

Whenever a candidate gets through `CreateFromTbm`, obtain the generated geometry/STEP before calling it useful for production. Runtime construction success is only Gate 1; production still requires correct JellyRoll/Can/Cap dimensions and contacts.

## Claude completion report

Report back only after generation with:

- branch and commit SHA;
- exact output ZIP path and SHA-256;
- all candidate SHA-256 values;
- validator summary per candidate;
- confirmation of invariant checks above;
- any generator bug encountered and exact fix applied.
