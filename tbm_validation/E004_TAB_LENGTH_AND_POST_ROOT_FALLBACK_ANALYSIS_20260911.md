# E004 Post-ROOT Fallback Analysis — 2026-09-11

**Status:** ANALYSIS / FALLBACK GENERATOR PREPARED, NOT YET RUNTIME-TESTED  
**Applies if:** ROOT_A and ROOT_B both return the identical `Electrode Root 1 : Extrusion distance can not be 0.` failure.  
**Baseline:** immutable R005, SHA-256 `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`

## 1. Main result of the post-ROOT review

The old recommendation “run C12 then C13” is too coarse. In particular, existing
`C12_FULL_SIEMENS_DETAILED_BUILDER.tbm` inserts the STAR `validationBattery.tbm`
Detailed Builder into the project PCD while leaving the project cavity unchanged:

```text
Project Package m_dintDiameter            = 20.6274 mm
Transplanted Builder m_dJellyrollThickness_mm = 17.9 mm
```

That hybrid is deliberately geometrically inconsistent. A C12 PASS would still be useful,
but a C12 FAIL would be difficult to interpret. C12 is therefore demoted to a secondary
rescue case rather than the primary localization test.

The better fallback is to use a complete, internally coherent Siemens geometry shell and
then add the project model context back around it.

## 2. Strong control lineage: stock Siemens HP18650

Use the unmodified source:

`tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm`

This is stronger than a static template control because a client-generated STEP from this
same source lineage has already been inspected: 13 named solids were produced and no
pairwise boolean-intersection volume was found. Successful STAR logs also show the expected
root topology:

```text
Jellyroll <-> -Ve Tab Root <-> -Ve Tab Stem
Jellyroll <-> +Ve Tab Root <-> +Ve Tab Stem
```

### HP_CONTROL

Run the unmodified HP18650 TBM in Robert's current STAR environment.

Interpretation:

- **PASS:** establishes that the current `Create from Tbm` path accepts a known-good Siemens
  cylindrical source and allows hybrid localization to be interpreted.
- **FAIL:** stop. Do not interpret project hybrids until the STAR version/import/environment
  difference is understood.

### HP_SHELL_PROJECT_RCR

Construct from immutable project R005 by replacing only:

- complete `<Physical Cell Description>` with the HP18650 PCD;
- first / active Detailed `<BUILDER>` with the HP18650 Detailed Builder;

while retaining the project model context after the active Builder, including the project
RCRTable 3D SIMMOD / RCR arrays, MODELMAP and Distributed model blocks where structurally
compatible.

Interpretation:

- **HP_CONTROL PASS + HP_SHELL PASS:** the project RCR/model context can coexist with a
  known-good Siemens geometry shell. The persistent E004 is then localized strongly toward
  the project's geometry/PCD/Builder content.
- **HP_CONTROL PASS + HP_SHELL identical E004:** geometry alone is insufficient to explain
  the failure. Investigate non-transplanted SIMMOD/MODELMAP/model-context coupling or a block
  consumed during construction.
- **HP_SHELL reaches a different downstream error:** E004 is cleared for localization even
  if the hybrid is not yet a runnable battery model.

## 3. Tab-length anomaly: useful, but axis mapping is NOT proven

A second anomaly emerged while comparing PCD geometry fields:

| TBM | +Electrode width | +Tab length | numeric difference | -Electrode width | -Tab length | numeric difference |
|---|---:|---:|---:|---:|---:|---:|
| Project R005 | 64.11 | 60.00 | **-4.11** | 65.11 | 60.00 | **-5.11** |
| Siemens HP18650 | 51.50 | 60.00 | **+8.50** | 52.50 | 60.00 | **+7.50** |
| Siemens HE18650 | 58.30 | 65.00 | **+6.70** | 59.30 | 60.00 | **+0.70** |
| STAR validationBattery | 56.00 | 65.00 | **+9.00** | 57.00 | 65.00 | **+8.00** |

R005 retained 60-mm tab lengths while increasing electrode widths to the 2170 values. Every
compared valid/reference cylindrical source has tab length numerically greater than its
corresponding electrode width.

However, **do not interpret this table as a proven axial clearance.** Public BDS material
shows `L_tab`, `W_tab`, electrode `L` and electrode `W` as separate flat-electrode geometry
parameters. It does not document that TBM `Tab m_dLength_mm` and electrode `m_dWidth` share
the same construction axis in STAR, nor does Siemens publish the proprietary formula used to
create `Electrode Root`.

Therefore the tab-length relation is a **root-specific correlation worth probing only after
geometry-shell localization**, not a confirmed or leading mechanism.

If the shell tests localize E004 to project geometry, two controlled PCD probes are prepared:

### TL_A — numerical relation just positive

```text
+Electrode Tab m_dLength_mm : 60.00 -> 64.21
-Electrode Tab m_dLength_mm : 60.00 -> 65.21
```

All other fields frozen from R005. This makes `Tab length - electrode width = +0.10 mm` for
both polarities as a numerical discriminator only.

### TL_B — larger finite discriminator

```text
+Electrode Tab m_dLength_mm : 60.00 -> 64.81
-Electrode Tab m_dLength_mm : 60.00 -> 65.81
```

This gives a numerical difference of +0.70 mm for both polarities. The value is chosen because
+0.70 mm is the smallest such difference among the compared Siemens references (HE18650
negative side), not because +0.70 mm is known to be a STAR tolerance.

Interpretation:

- TL_A clears E004 -> tab-length / derived root geometry participates causally; exact mapping
  remains unproven.
- TL_A fails, TL_B clears -> consistent with a finite geometric threshold somewhere between
  the two probes, but still not proof that STAR uses `Ltab - W` directly.
- both fail -> downgrade the tab-length correlation.

Both are diagnostic only and are not approved production tab dimensions.

## 4. Builder-only and second-shell discriminators

### C10 — preferred Builder-only broad rescue

`C10_STAR_BUILDER_PATTERN.tbm` is cleaner than C12 because it preserves the project PCD and
project JR diameter while changing a bounded set of Builder fields toward the Siemens pattern.
If the HP shell passes but project geometry still needs localization, C10 is useful for asking
whether the active Builder alone can rescue the project PCD.

### C13 — independent second shell lineage

A validationBattery PCD + active Builder / project-RCR hybrid remains useful as an independent
second geometry shell. Agreement between the HP shell and validationBattery shell is much
stronger evidence than either one alone.

## 5. Revised conditional runtime order

If ROOT_A and ROOT_B both return identical E004:

1. **HP_CONTROL** — unmodified verified-clean Siemens source.
2. If HP_CONTROL passes, **HP_SHELL_PROJECT_RCR**.
3. If HP_SHELL passes and therefore localizes the fault to project geometry:
   - run **C10** as the cleaner Builder-only discriminator;
   - use **TL_A**, then **TL_B** only as targeted PCD/root probes if still needed.
4. If HP_CONTROL passes but HP_SHELL still gives identical E004:
   - run **C13** as an independent geometry-shell/project-model hybrid;
   - if both shell hybrids fail identically, escalate to model/SIMMOD/MODELMAP coupling rather
     than continuing random geometry perturbations.
5. Keep **C12** only as a secondary rescue experiment; do not use a C12 failure to rule out
   Builder involvement.

This sequence maximizes information per Robert runtime test and avoids interpreting a
cross-geometry mismatch as a clean negative result.

## 6. Production constraints remain unchanged

None of these diagnostic candidates is automatically a production geometry. Production still
requires:

- TBM-only cell creation;
- native distributed `RCRTable 3D`;
- correct retained JellyRoll + Can + Cap geometry;
- JellyRoll–Can radial contact;
- JellyRoll–Cap axial contact;
- physically defensible tab/root geometry even if auxiliary generated solids are later
  deselected in Import Battery Options.

A runtime construction pass is Gate 1 only. Any successful diagnostic geometry must be
exported/inspected before promotion.
