# E004 Post-ROOT Fallback Analysis — 2026-09-11

**Status:** ANALYSIS / FALLBACK GENERATOR PREPARED, NOT YET RUNTIME-TESTED  
**Trigger:** use only if ROOT_A and ROOT_B both return the identical `Electrode Root 1 : Extrusion distance can not be 0.` failure.  
**Immutable baseline:** R005 SHA-256 `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`

## 1. Why the old C12 -> C13 fallback was revised

Existing `C12_FULL_SIEMENS_DETAILED_BUILDER.tbm` replaces only the project first Detailed Builder with the STAR `validationBattery.tbm` Builder while leaving the project PCD unchanged. That produces a substantial cross-geometry mismatch:

```text
Project Package m_dintDiameter                = 20.6274 mm
Transplanted Builder m_dJellyrollThickness_mm = 17.9 mm
```

Therefore a C12 PASS would still be informative, but a C12 FAIL would not cleanly rule out Builder involvement. C12 is demoted to a secondary rescue case.

A second structural issue is that cylindrical TBMs carry both a Detailed Builder and a Simple Builder. The stock files identify Detailed Builder as the default, but we do not have runtime proof that STAR completely ignores the non-default Builder during all validation stages. Therefore a true geometry-shell discriminator should not leave a project Simple Builder behind.

## 2. Primary post-ROOT control: Siemens HP18650

Use the unmodified source:

`tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm`

This source is especially valuable because a client-generated STEP from the same stock HP18650 lineage has already been inspected: 13 named solids were produced with zero pairwise boolean-intersection volume. Successful STAR logs also show the expected generated root topology:

```text
Jellyroll <-> -Ve Tab Root <-> -Ve Tab Stem
Jellyroll <-> +Ve Tab Root <-> +Ve Tab Stem
```

### HP_CONTROL

Run the unmodified HP18650 TBM in Robert's current STAR environment.

- PASS -> establishes a known-good current `Create from Tbm` control.
- FAIL -> stop. Do not interpret hybrids until the environment/version/import-path difference is understood.

### HP_SHELL_PROJECT_RCR

Construct from immutable project R005 by transplanting the **complete Siemens geometry definition**:

- complete `<Physical Cell Description>`;
- **both** `<BUILDER>` blocks;
- `<DEFAULT BUILDER>` selector if present;

while preserving every non-geometry block from R005, including the project RCR/SIMMOD/MODELMAP context.

The generator verifies this by masking PCD/Builder/default-builder blocks and requiring all remaining project text to be identical before and after the transplant.

Interpretation:

- **HP_CONTROL PASS + HP_SHELL E004 absent:** the project model context can coexist with a known-good Siemens geometry shell. Persistent E004 is localized strongly toward project geometry/PCD/Builder content.
- **HP_CONTROL PASS + HP_SHELL identical E004:** a known-good complete geometry shell is not enough. Investigate project model/SIMMOD/MODELMAP/non-geometry coupling; use the independent validationBattery shell next.
- **HP_SHELL reaches a different downstream error:** E004 is cleared for localization even if the hybrid is not a runnable battery model.

## 3. Independent second shell: validationBattery

`C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm` is regenerated as a **complete** validationBattery geometry shell:

- complete PCD;
- both Builder blocks;
- default-builder selector if present;
- project non-geometry/model context retained.

If both the HP shell and validationBattery shell give identical E004 while their unmodified Siemens control geometry is valid, stop random geometry perturbations and investigate the project model/context outside the geometry shell.

## 4. Builder-only discriminator after a shell pass

If HP_SHELL clears E004, `C10_STAR_BUILDER_PATTERN.tbm` is preferred over C12 for a project-geometry Builder-only test. C10 preserves the project PCD and project JR diameter while changing a bounded set of first/active Detailed-Builder fields toward the Siemens pattern.

A C10 PASS would implicate Builder content. A C10 FAIL would shift attention toward PCD/root geometry, but does not by itself prove the PCD is the only cause.

## 5. Tab-length anomaly: targeted correlation only

A PCD comparison shows that R005 retained 60-mm tab lengths while increasing the electrode widths to the 2170 values:

| TBM | +Electrode width | +Tab length | numeric difference | -Electrode width | -Tab length | numeric difference |
|---|---:|---:|---:|---:|---:|---:|
| Project R005 | 64.11 | 60.00 | **-4.11** | 65.11 | 60.00 | **-5.11** |
| Siemens HP18650 | 51.50 | 60.00 | **+8.50** | 52.50 | 60.00 | **+7.50** |
| Siemens HE18650 | 58.30 | 65.00 | **+6.70** | 59.30 | 60.00 | **+0.70** |
| STAR validationBattery | 56.00 | 65.00 | **+9.00** | 57.00 | 65.00 | **+8.00** |

Every compared Siemens/reference case has tab length numerically greater than the corresponding electrode width, unlike R005. This is root-specific enough to keep as a controlled probe because `Electrode Root` connects the Jellyroll to the Tab Stem.

However, **do not call this an axial clearance.** Public BDS material shows `L_tab`, `W_tab`, electrode `L`, and electrode `W` as distinct flat-electrode parameters and does not establish that TBM `Tab m_dLength_mm` and electrode `m_dWidth` share the same STAR construction axis. Siemens does not publish the proprietary `Electrode Root` extrusion formula.

If shell localization implicates project geometry and a targeted PCD probe is useful:

### TL_A

```text
+Electrode Tab m_dLength_mm : 60.00 -> 64.21
-Electrode Tab m_dLength_mm : 60.00 -> 65.21
```

Numerical `Ltab - W = +0.10 mm` for both polarities.

### TL_B

```text
+Electrode Tab m_dLength_mm : 60.00 -> 64.81
-Electrode Tab m_dLength_mm : 60.00 -> 65.81
```

Numerical `Ltab - W = +0.70 mm` for both polarities. The value is chosen because +0.70 mm is the smallest such numerical difference in the compared references (HE18650 negative side), not because +0.70 mm is known to be a STAR tolerance.

Both are diagnostic only.

## 6. Revised runtime order

If ROOT_A and ROOT_B both return identical E004:

1. **HP_CONTROL**.
2. If HP_CONTROL passes, **HP_SHELL_PROJECT_RCR**.
3. If HP_SHELL clears E004:
   - use **C10** as the cleaner Builder-only discriminator;
   - use **TL_A**, then **TL_B** only if a targeted PCD/root probe is still useful.
4. If HP_CONTROL passes but HP_SHELL still gives identical E004:
   - run the complete **C13 validationBattery shell**;
   - if both complete shell hybrids fail identically, escalate to model/SIMMOD/MODELMAP/non-geometry coupling.
5. Keep **C12** only as a secondary rescue experiment; do not use a C12 failure to rule out Builder involvement.

This sequence maximizes information per Robert runtime run and prevents a deliberately mismatched hybrid from being treated as a clean negative result.

## 7. Production constraints

No diagnostic pass is automatically a production solution. Production still requires:

- TBM-only cell creation;
- native distributed `RCRTable 3D`;
- correct retained JellyRoll + Can + Cap geometry;
- JellyRoll–Can radial contact;
- JellyRoll–Cap axial contact;
- physically defensible tab/root geometry even if auxiliary generated solids are later deselected.

A construction pass is Gate 1 only. Any successful diagnostic candidate must be exported/inspected before promotion.
