# STAR-CCM+ E004 Multifile Diagnostic Campaign — Addendum

**Date:** 2026-09-10
**Applies to:** `STAR_E004_MULTIFILE_DIAGNOSTIC_CAMPAIGN_20260910.md`

This addendum is mandatory and takes precedence where it conflicts with the original campaign document.

## 1. Critical baseline correction

The failed runtime-tested exact-contact baseline must be sourced from the frozen commit, **not from the current branch working path**, because the branch copy has subsequently been edited during diagnosis.

Canonical failed baseline source:

```text
commit: d74b3283cb5d73e114bc141f3f0d18e7c7ed5463
path:   out/hp2170NCA-RCR-distributed-exact-contact-final.tbm
sha256: 2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5
```

Canonical failed Detailed Builder values include:

```text
m_dSepFeedLength_mm = 0
m_dSepTailLength_mm = 0
```

The generator must obtain the baseline from that commit (for example with `git show <commit>:<path>`) and verify the SHA-256 before generating variants. It must not use the branch-tip copy merely because the filename is the same.

If the SHA differs, abort generation.

## 2. Add C12 — complete Siemens Detailed Builder transplant

Filename:

`C12_FULL_SIEMENS_DETAILED_BUILDER.tbm`

Base: canonical failed project baseline above.

Diagnostic change: replace the complete active `Detailed Builder` block with the corresponding complete Detailed Builder block from the unmodified Siemens STAR-install `validationBattery.tbm`. Do not cherry-pick only the fields already present in C01-C11.

Keep the project's SIMMOD blocks, MODELMAP and About-Energy RCR data unchanged.

Purpose:

This is a broad localization control. If C01-C11 all fail but C12 clears E004, the culprit lies somewhere in the Detailed Builder configuration outside the individually tested subset, or in an interaction among those Builder fields.

This is diagnostic only and is not a production geometry candidate.

Record an exact block-level diff and SHA.

## 3. Add C13 — Siemens geometry shell with project model/RCR retained

Filename:

`C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm`

Construct a diagnostic TBM whose geometry-defining content is taken from the unmodified Siemens STAR-install `validationBattery.tbm`, while retaining the project's selected model configuration and About-Energy RCR data.

At minimum, retain from the project:

```text
MODELMAP Electrolyte = General Electrolyte
MODELMAP IET = RCRTable 3D
MODELMAP Thermal = Distributed
project General Electrolyte SIMMOD if structurally compatible
project RCRTable 3D SIMMOD and all About-Energy RCR numerical data
project Distributed Thermal SIMMOD
```

Use Siemens geometry-defining Physical Cell Description and Builder content consistently as a set. Do not mix isolated geometry fields without documenting the exact transplant boundary.

Purpose:

This is the strongest geometry-vs-model localization control.

Interpretation:

- `C00 PASS`, `C12 PASS`: E004 is localized to the project Detailed Builder configuration.
- `C00 PASS`, `C12 FAIL`, `C13 PASS`: E004 is caused by geometry-defining content outside the Detailed Builder, or by an interaction between Physical Cell Description geometry and Builder content.
- `C00 PASS`, `C13 FAIL with E004`: the assumption that E004 is solely due to project geometry is wrong or the transplant is structurally incompatible; investigate model/geometry coupling and exact section compatibility before another speculative geometry edit.
- `C00 FAIL`: do not interpret project variants until the environment/reference-path issue is understood.

C13 is diagnostic only; it is not a production candidate.

## 4. Updated campaign size and runtime order

Campaign is now C00-C13.

Recommended order:

```text
C00
C03
C01
C02
C10
C12
C13
C05
C07
C04
C06
C08
C09
C11
```

Robert should still run every case if practical and return the exact terminal message for each case, including cases that progress beyond E004 to a different error.

## 5. Completion criterion

The campaign's purpose is to localize and clear **E004**. It does not guarantee that STAR will have no later-stage error after E004 is cleared.

Do not declare E004 resolved until at least one project-derived diagnostic case progresses past the exact message:

```text
Electrode Root 1 : Extrusion distance can not be 0.
```

A new downstream error is progress and must be recorded as a new runtime error class, not treated as campaign failure.
