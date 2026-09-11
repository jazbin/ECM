# E004 Tab-Length and Post-ROOT Fallback Analysis — 2026-09-11

**Status:** ANALYSIS / CANDIDATES NOT YET GENERATED  
**Applies if:** ROOT_A and ROOT_B both return the identical `Electrode Root 1 : Extrusion distance can not be 0.` failure.  
**Baseline:** immutable R005, SHA-256 `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`

## 1. New root-specific anomaly: tab length vs electrode width

The project TBM retained the stock tab lengths while increasing the wound-layer axial widths to the 2170 target.

| TBM | +Electrode width | +Tab length | +Tab minus +Electrode | -Electrode width | -Tab length | -Tab minus -Electrode |
|---|---:|---:|---:|---:|---:|---:|
| Project R005 | 64.11 | 60.00 | **-4.11** | 65.11 | 60.00 | **-5.11** |
| Siemens HP18650 | 51.50 | 60.00 | **+8.50** | 52.50 | 60.00 | **+7.50** |
| Siemens HE18650 | 58.30 | 65.00 | **+6.70** | 59.30 | 60.00 | **+0.70** |
| STAR validationBattery | 56.00 | 65.00 | **+9.00** | 57.00 | 65.00 | **+8.00** |

This is a stronger root-specific discriminator than the broad C12 Builder transplant because:

1. `Electrode Root` is a generated tab/root solid connecting the Jellyroll to the Tab Stem.
2. `±Electrode Tab m_dLength_mm` is a direct tab geometry dimension in the Physical Cell Description.
3. Every known-working/reference cylindrical geometry above has **positive tab-length headroom over the corresponding electrode width**.
4. R005 is the only compared case where both tab lengths are shorter than their electrode widths.
5. The HP18650 geometry is not merely a static TBM reference: its generated 13-solid STEP was measured and found geometry-clean.

No public Siemens source documents the proprietary formula for `Electrode Root` extrusion. Therefore this does **not** prove that STAR computes `extrusion = tab length - electrode width`. A plausible mechanism is that a negative available tab protrusion is clamped/collapsed during root construction, producing a zero extrusion passed to the CAD kernel. This remains a hypothesis until runtime tested.

## 2. Why ROOT_A / ROOT_B remain the correct first tests

ROOT_A/B change only `Package m_dintHeight`, so they cleanly test the current leading package/axial-envelope hypothesis.

The tab-length hypothesis becomes especially important if both ROOT candidates fail, because ROOT_A/B leave both tab lengths fixed at 60 mm. Thus a package-height failure does not test whether the tab itself lacks enough axial extent to create a root/stem outside the wound electrode.

Conversely, if ROOT_A passes while tab lengths remain 60 mm, the simple tab-length-headroom hypothesis is substantially weakened.

## 3. Recommended next candidates if ROOT_A and ROOT_B both fail

Generate both candidates independently from immutable R005. Freeze all other fields.

### TL_A — minimum positive tab headroom

Change only:

```text
+Electrode Tab m_dLength_mm : 60.00 -> 64.21
-Electrode Tab m_dLength_mm : 60.00 -> 65.21
```

Result:

```text
+Tab - +Electrode width = +0.10 mm
-Tab - -Electrode width = +0.10 mm
```

Purpose: test whether merely changing both tab/electrode relations from negative to positive clears `Electrode Root 1`.

### TL_B — HE-scale minimum headroom

Change only:

```text
+Electrode Tab m_dLength_mm : 60.00 -> 64.81
-Electrode Tab m_dLength_mm : 60.00 -> 65.81
```

Result:

```text
+Tab - +Electrode width = +0.70 mm
-Tab - -Electrode width = +0.70 mm
```

Purpose: if TL_A fails, test a finite allowance equal to the smallest observed valid tab/electrode margin in the Siemens HE18650 reference (`-Tab 60.0 - -Electrode 59.3 = +0.7 mm`).

Both TL_A and TL_B are **diagnostic only**. They must not be treated as production tab dimensions without geometry inspection and physical justification.

### Runtime interpretation

- **TL_A clears E004:** strong runtime evidence that tab-length / derived root geometry participates causally. The exact STAR formula remains unproven.
- **TL_A fails, TL_B clears E004:** consistent with a finite minimum tab/root construction allowance or geometry-kernel tolerance between +0.10 and +0.70 mm.
- **TL_A and TL_B both fail with identical E004:** downgrade the tab-length-headroom hypothesis and move to geometry-shell localization.

Do not immediately perform a threshold binary search. First inspect any successful generated STEP/root/stem geometry.

## 4. Existing C12 is weaker than previously stated

Existing `C12_FULL_SIEMENS_DETAILED_BUILDER.tbm` replaces the project first Detailed Builder with the STAR `validationBattery.tbm` Builder while leaving the project PCD unchanged.

This creates an intentional but substantial cross-geometry mismatch:

```text
Project Package m_dintDiameter       = 20.6274 mm
Siemens Builder m_dJellyrollThickness_mm = 17.9 mm
```

The C12 Builder diff is largely composed of fields already represented by C10 or already runtime-pruned/demoted: feed/tail, start/end overlap, mandrel width, tab orientation, plus the incompatible 17.9-mm JR target.

Therefore:

- **C12 PASS** remains informative: a full Siemens Builder can clear E004 inside the project PCD.
- **C12 FAIL** is not strong evidence against Builder involvement because the hybrid is geometrically inconsistent.
- C12 should no longer be the primary post-ROOT localization test.

`C10_STAR_BUILDER_PATTERN.tbm` is the cleaner Builder-only rescue because it retains the project JR diameter and PCD while applying the main Siemens Builder-pattern changes.

## 5. Stronger geometry-vs-model localization: HP18650 shell

Prepare a new geometry-shell candidate from the **verified-clean Siemens HP18650 source**, not only `validationBattery.tbm`.

### HP_CONTROL

Unmodified:

`tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm`

Purpose: confirm Robert's current STAR `Create from Tbm` path still accepts the same Siemens source lineage whose generated STEP is already known geometry-clean.

### HP_SHELL_PROJECT_RCR

Construct from immutable project R005 by replacing:

- complete `<Physical Cell Description>` with HP18650 PCD;
- first / active Detailed `<BUILDER>` with HP18650 Detailed Builder;

while retaining project:

- active `RCRTable 3D` SIMMOD and its RCR arrays;
- MODELMAP;
- General Electrolyte SIMMOD where structurally compatible;
- Distributed Thermal SIMMOD;
- other non-geometry model blocks required by the current project lineage.

This candidate must be statically checked for block-count and model-map consistency before runtime use.

Interpretation:

- **HP_CONTROL passes + HP_SHELL_PROJECT_RCR passes:** project model/RCR can coexist with a known-clean Siemens geometry shell. The remaining fault is localized to project geometry/PCD/Builder content.
- **HP_CONTROL passes + HP_SHELL_PROJECT_RCR fails with E004:** the failure is not explained by the geometry shell alone; investigate model/SIMMOD/MODELMAP coupling or a non-transplanted block consumed during construction.
- **HP_CONTROL itself fails:** stop interpreting project candidates until the STAR version/import path/environment difference is understood.

This is a stronger control than using only `validationBattery.tbm`, because the HP18650 source has direct generated-STEP evidence for all 13 solids including both Tab Roots and Tab Stems.

## 6. Revised post-ROOT test order

If ROOT_A and ROOT_B both return identical E004:

1. **TL_A** — both tab lengths raised to width +0.10 mm.
2. If identical E004, **TL_B** — both tab lengths raised to width +0.70 mm.
3. If identical E004, **HP_CONTROL**.
4. If HP_CONTROL passes, **HP_SHELL_PROJECT_RCR**.
5. Run **C10** if a project-PCD / Builder-only discriminator is still needed.
6. Retain **C13** (validationBattery geometry shell / project RCR) as an independent second shell lineage.
7. Demote **C12** to a secondary hybrid test because its 17.9-mm Siemens Builder JR target is inconsistent with the project 20.6274-mm PCD/cavity.

## 7. Production constraints remain unchanged

None of these diagnostic candidates is automatically a production geometry.

Production still requires:

- TBM-only cell creation;
- native distributed `RCRTable 3D`;
- correct retained JellyRoll + Can + Cap geometry;
- JellyRoll–Can radial contact;
- JellyRoll–Cap axial contact;
- physically defensible tab geometry if tabs remain part of the generated construction even when later deselected from imported parts.

A runtime pass is Gate 1 only. Generated geometry must then be inspected before any candidate is promoted.
