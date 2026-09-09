# RCR MODELMAP engineering correction — 2026-09-09

## Status

Engineering finding: the reviewed 2170 V4 candidate contains the intended About-Energy data in the `RCRTable 3D` SIMMOD, but its `<MODELMAP>` still selects `IET = Distributed 3D` because the translation lineage inherited the Siemens `hp18650Spiral-DIST.tbm` selector.

This is a semantic release blocker for intended RCR electrothermal use. It is not a geometry/import-format blocker by itself.

## Independent Siemens evidence

Observed Siemens/STAR reference patterns:

- `hp18650Spiral-DIST.tbm`: `IET = Distributed 3D`
- STAR `validationBattery.tbm`: `IET = RCRTable 3D`
- STAR cylindrical tutorial: `IET = NTGPTable 3D`
- Siemens `hp18650Spiral-RCR25deg.tbm`: `IET = RCRTable 3D`

The selector therefore tracks the intended IET SIMMOD and must not be treated as informational metadata.

The Siemens RCR reference also demonstrates that BDS-side RCR models may contain `m_bOnly1D = 1`. Robert's STAR import error independently established that the STAR path used for this project does not accept that option. Therefore the current all-zero `m_bOnly1D` adaptation is retained for the STAR candidate; it is not generalized as a universal TBM rule.

## Corrected candidate definition

Base, frozen and unchanged:

`out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm`

Pinned SHA-256:

`24eacae56e40d826f162046bc63131f7c590b3c5d72dec80828c7e6a5520667f`

Physical lineage:

- tabs ON
- both terminals same-face/top
- all reviewed V4 consistency corrections retained
- all `m_bOnly1D` values remain zero
- RCR/OCV/thermal fields remain byte-identical to V4
- builder and REPORT fields remain byte-identical to V4

Authorized delta only:

```text
<MODELMAP>
    IET = Distributed 3D
```

becomes

```text
<MODELMAP>
    IET = RCRTable 3D
```

No other TBM field is authorized to change in this correction step.

## New guardrails on branch `tbm-rcr-modelmap-fix-exec`

- `tools/generate_tbm_rcr_candidate.py`
  - pins the frozen V4/variant_3 SHA
  - requires exactly one MODELMAP block
  - requires an existing `RCRTable 3D` SIMMOD
  - changes exactly one logical line
  - refuses any unexpected base selector or multi-line delta

- `tools/validate_tbm_modelmap.py`
  - parses MODELMAP independently of the existing validator
  - verifies selected IET has a matching SIMMOD
  - supports an explicit expected-IET requirement
  - verifies RCR capacity override, capacity value and parameter-set presence
  - can enforce the STAR-specific all-zero `m_bOnly1D` requirement

- `tbm_validation/tests/test_modelmap_consistency.py`
  - fixture-level selector tests
  - Siemens DIST/RCR/NTGP reference-pattern checks
  - verifies frozen V4/variant_3 is invalid for an expected RCR target
  - verifies the patch changes exactly one line and then satisfies the RCR selector checks

## Required local execution / Codex handoff

Run from repo root on branch `tbm-rcr-modelmap-fix-exec`:

```bash
python3 tbm_validation/tests/test_modelmap_consistency.py
python3 tbm_validation/tests/test_structural_fields.py
python3 tbm_validation/tests/test_validator.py
python3 tbm_validation/tests/test_documentation_consistency.py
```

Generate exactly one candidate:

```bash
python3 tools/generate_tbm_rcr_candidate.py
```

Then run:

```bash
python3 tools/validate_tbm_modelmap.py \
  out/rcr_candidate/hp2170-rcr-v1-tabs-on-sameFace.tbm \
  --expect-iet 'RCRTable 3D' \
  --expect-capacity-ah 5.0 \
  --require-all-only1d-zero
```

Also run the existing validator against the new file/reference. Since the candidate differs from V4/variant_3 only in MODELMAP, the existing field-level WARN profile should not silently improve or worsen; investigate any changed finding rather than accepting it automatically.

Perform a byte/line diff against frozen V4/variant_3 and prove exactly one logical line changed.

Record the new candidate SHA-256.

## Translator hardening still required

`tools/translate_tbm_from_openfoam.py` currently rewrites/populates `RCRTable 3D` but does not update MODELMAP. Add a narrow helper that, whenever RCR translation is selected/applied, requires exactly one MODELMAP and sets its `IET` selector to `RCRTable 3D`.

Add regression coverage so translating from a DIST template cannot produce a populated RCR target with `IET = Distributed 3D` again.

Do not modify the eight frozen package_rev3/package_rev4_candidate TBMs. Do not retrofit historical packages in place.

## Release state

- package_rev3: may still provide useful STAR geometry/import evidence, but is not approved for intended RCR electrothermal physics because its selector lineage remains DIST.
- frozen package_rev4_candidate: same limitation.
- new RCR candidate: static approval pending local generation/tests; STAR import/runtime qualification still required afterward.

Do not send a new package to Robert until local generation, regression, existing-validator, one-line-delta and hash checks are complete.
