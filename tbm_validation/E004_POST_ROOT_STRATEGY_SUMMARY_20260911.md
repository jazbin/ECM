# E004 Post-ROOT Strategy Summary — 2026-09-11

## Trigger

Use this strategy only if both `ROOT_A_AXIAL_CLEARANCE_0p10.tbm` and `ROOT_B_AXIAL_CLEARANCE_HE_0p70.tbm` return the identical fatal STAR error:

```text
Electrode Root 1 : Extrusion distance can not be 0.
```

The immutable failed project baseline remains R005:

```text
SHA-256: 2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5
```

## Revised strategy

Do not use the old broad `C12 -> C13` sequence as the primary fallback.

`C12_FULL_SIEMENS_DETAILED_BUILDER.tbm` is an intentionally mismatched hybrid: it puts a Siemens Detailed Builder with a `17.9 mm` JellyRoll target inside the project's `20.6274 mm` PCD/cavity. A C12 PASS is informative, but a C12 FAIL does not cleanly rule out Builder involvement.

Instead use the following conditional sequence.

```text
ROOT_A fails
ROOT_B fails
      |
      v
HP_CONTROL
unmodified Siemens HP18650
      |
      +-- FAIL -> stop and investigate STAR environment/import path
      |
      v
HP_SHELL_PROJECT_RCR
complete known-good HP geometry shell
inside frozen project model/RCR context
      |
      +-- E004 clears
      |      |
      |      +-- C10 Builder-only discriminator
      |      |
      |      +-- targeted PCD/root probes only if still useful
      |
      +-- identical E004
             |
             v
C13 complete validationBattery geometry shell
             |
             +-- identical E004 again -> investigate model/SIMMOD/
                 MODELMAP/non-geometry coupling, not random geometry edits
```

## HP_CONTROL

Use the unmodified stock Siemens file:

`tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm`

This is preferred because the generated 13-solid STEP from this lineage has already been inspected and found geometry-clean, including the generated Tab Root/Tab Stem topology.

If this control fails in Robert's current STAR environment, do not interpret any hybrid candidates until the environment/version/import-path difference is understood.

## HP_SHELL_PROJECT_RCR

This is the strongest geometry-vs-model localization test.

Starting from immutable R005, transplant the complete HP18650 geometry definition:

- complete `<Physical Cell Description>`;
- all `<BUILDER>` blocks (Detailed + Simple in the current corpus);
- `<DEFAULT BUILDER>` selector if present;

while keeping every non-geometry project block unchanged, including the project RCR/SIMMOD/MODELMAP context.

The generator verifies this by masking the geometry blocks and requiring all remaining project text to be byte-identical.

Interpretation:

- `HP_CONTROL PASS + HP_SHELL E004 absent` -> project geometry/PCD/Builder content is strongly implicated.
- `HP_CONTROL PASS + HP_SHELL identical E004` -> known-good geometry alone is insufficient; investigate project model/context coupling and run the independent validationBattery shell.
- a different downstream error still counts as clearing E004 for localization purposes.

## C10

If HP_SHELL clears E004 and Builder-only localization is still needed, prefer:

`C10_STAR_BUILDER_PATTERN.tbm`

C10 preserves the project PCD and project JellyRoll diameter while changing a bounded set of first/active Detailed-Builder fields toward the Siemens pattern. This is cleaner than C12.

## Tab-length anomaly

R005 retained `60 mm` tab lengths while the project electrode widths were increased to `64.11 / 65.11 mm`.

Compared references:

| TBM | +Electrode width | +Tab length | numeric difference | -Electrode width | -Tab length | numeric difference |
|---|---:|---:|---:|---:|---:|---:|
| Project R005 | 64.11 | 60.00 | -4.11 | 65.11 | 60.00 | -5.11 |
| Siemens HP18650 | 51.50 | 60.00 | +8.50 | 52.50 | 60.00 | +7.50 |
| Siemens HE18650 | 58.30 | 65.00 | +6.70 | 59.30 | 60.00 | +0.70 |
| STAR validationBattery | 56.00 | 65.00 | +9.00 | 57.00 | 65.00 | +8.00 |

This remains a root-specific correlation worth probing, but **must not be described as an axial clearance formula**. Public BDS material does not establish that TBM `Tab m_dLength_mm` and electrode `m_dWidth` share the same STAR construction axis, and Siemens does not publish the proprietary `Electrode Root` extrusion formula.

Prepared targeted probes:

### TL_A

```text
+Electrode Tab m_dLength_mm : 60.00 -> 64.21
-Electrode Tab m_dLength_mm : 60.00 -> 65.21
```

### TL_B

```text
+Electrode Tab m_dLength_mm : 60.00 -> 64.81
-Electrode Tab m_dLength_mm : 60.00 -> 65.81
```

These are diagnostic only and should be used after shell localization if a PCD/root-specific probe is still useful.

## Prepared implementation

Authoritative detailed analysis:

`tbm_validation/E004_TAB_LENGTH_AND_POST_ROOT_FALLBACK_ANALYSIS_20260911.md`

Execution handoff:

`tbm_validation/E004_POST_ROOT_FALLBACK_EXECUTION_HANDOFF_20260911.md`

Deterministic generator:

`tools/generate_e004_post_root_fallback.py`

Expected generated fallback package:

`out/hp2170NCA-STAR-E004-post-root-fallback-20260911.zip`

Expected candidates:

- `HP_CONTROL_hp18650Spiral-DIST.tbm`
- `HP_SHELL_PROJECT_RCR.tbm`
- `C10_STAR_BUILDER_PATTERN.tbm`
- `TL_A_TAB_RELATION_0p10.tbm`
- `TL_B_TAB_RELATION_0p70.tbm`
- `C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm`

## Production constraint

No diagnostic pass is automatically a production solution. A successful candidate must still be exported and inspected for:

- correct native distributed `RCRTable 3D` behavior;
- final retained JellyRoll + Can + Cap geometry;
- JellyRoll-Can radial contact;
- JellyRoll-Cap axial contact;
- physically defensible tab/root construction.

Runtime construction success is Gate 1 only.
