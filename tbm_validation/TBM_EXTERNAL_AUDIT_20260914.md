# TBM external audit — 2026-09-14

## Scope

Independent audit of the current failing 2170 TBM lineage, especially:

- `out/rcr_candidate/hp2170-rcr-v4-exact-contact-final.tbm` (`R005`)
- client-provided runtime-working `validationBattery21700.tbm`
- Siemens HP18650 / HE18650 reference TBMs
- `tools/translate_tbm_from_openfoam.py`
- existing geometry-characterization evidence

The audit separates **import-blocker hypotheses** from **production-fidelity defects**.

---

## Executive findings

1. **Strongest current E004 hypothesis: derived tab/root height becomes zero or negative when tab length is not greater than electrode width.**
2. `R005` contains several **stale HP18650 physical-cell quantities** even though the main 2170 dimensions were changed.
3. The TBM translation pipeline does **not yet map the OpenFOAM cap thermal properties to any TBM-generated component**.
4. The active RCR block contains dU/dT data but `m_bUseEntropyData = 0`; this is a production-physics issue, not an E004 explanation.
5. `m_bSpecifyActiveArea = 0` / `m_dActiveArea_m2 = 0` require explicit validation under the TBM-only acceptance criterion.
6. Two BUILDER blocks / multiple unused SIMMOD blocks are inherited from Siemens reference structure and are **not currently treated as an intrinsic fault**.

---

## A1 — root-height / tab-length relation — highest-priority E004 candidate

A repeated numerical relation exists in independent reference/working TBMs:

`reported tab/root height = tab length - electrode width`

### Siemens HP18650

- positive: `60 - 51.5 = 8.5 mm`; REPORT `PosTabh* = 8.5`
- negative: `60 - 52.5 = 7.5 mm`; REPORT `NegTabh* = 7.5`

### Siemens HE18650

- positive: `65 - 58.3 = 6.7 mm`; REPORT `PosTabh* = 6.7`
- negative: `60 - 59.3 = 0.7 mm`; REPORT `NegTabh* = 0.7`

### Client runtime-working `validationBattery21700.tbm`

- positive: `65 - 56 = 9 mm`; REPORT `PosTabh* = 9`
- negative: `65 - 57 = 8 mm`; REPORT `NegTabh* = 8`

### Failing R005

- positive: `60 - 64.11 = -4.11 mm`
- negative: `60 - 65.11 = -5.11 mm`

STAR then fails at:

```text
Electrode Root 1 : Extrusion distance can not be 0.
```

This does **not** prove the exact proprietary construction formula, but it is the strongest currently available correlation between active PCD inputs and a derived root dimension. It now ranks above package-height clearance and separator feed/tail as the leading E004 mechanism.

### Required runtime discriminator

Use the root-surplus campaign to sweep:

- exact zero surplus,
- small positive surplus,
- larger positive surplus,
- target 2170 axial widths,
- full 2170 radial geometry.

A runtime threshold transition in H/T/F cases would confirm or refute this mechanism.

---

## A2 — stale package volumes inside Physical Cell Description

R005 contains:

```text
Package m_dextDiameter = 21.09
Package m_dextHeight   = 70.02
Package m_dextVolume   = 16.5321

Package m_dintDiameter = 20.6274
Package m_dintHeight   = 65.11
Package m_dintVolume   = 14.9232
```

The two volume values are inherited from the HP18650 lineage and are inconsistent with the current dimensions.

Simple cylindrical volumes for the R005 dimensions are approximately:

- external: `24.4605 cm^3`
- internal: `21.7584 cm^3`

The fields `Package m_bextVolCalc = 1` and `Package m_bintVolCalc = 1` may cause STAR/BDS to recompute these values, but a production TBM must not rely on that assumption without verification.

A dedicated `F09` runtime discriminator is added to the client-v2 campaign: it is identical to F04 except for synchronized package-volume fields.

---

## A3 — stale physical winding lengths and masses

R005 still contains HP18650-lineage physical quantities including:

```text
Settings m_dNegEtrdeLength_mm = 884.906
Settings m_dPosEtrdeLength_mm = 864.906
SeparatorList1_Separator m_dLength_mm = 1769.81
```

Several component mass/weight fields also remain inherited while widths were changed to 2170 values.

Prior geometry characterization found that physical electrode winding-length fields did not drive realized JR axial geometry; electrode widths and Detailed Builder geometry dominated. Therefore these are **not currently ranked as E004 causes**.

However, they are unacceptable unresolved inputs for final thermal mass / active-area / report consistency.

Do not silently change them inside the E004 DOE because doing so would confound the runtime localization campaign. Resolve them in the production-cleanup phase after the import blocker is localized.

---

## A4 — cap-equivalent thermal/material properties are not mapped

`tools/translate_tbm_from_openfoam.py` defines the OpenFOAM cap target:

```text
rho   = 1447.2 kg/m^3
Cp    = 500 J/(kg K)
k_r   = 0.01 W/(m K)
k_ax  = 0.1 W/(m K)
```

but the current translation path does not apply these `CAP_*` constants to a TBM-generated component.

The present tab material in R005 is a legacy Nickel 270 definition with very different density, heat capacity and conductivity.

Therefore a geometrically valid Tab Root / Tab Stem is **not automatically a valid cap surrogate**.

Production acceptance requires identifying which TBM-native generated solid can occupy the cap role and mapping equivalent thermal/electrical behavior to that solid entirely inside the TBM.

No Part-module correction after import is acceptable.

---

## A5 — shell properties are close but not exactly mapped

OpenFOAM shell target from translator:

```text
rho = 8000 kg/m^3
Cp  = 500 J/(kg K)
k   = 16 W/(m K)
```

R005 package/can approximately uses:

```text
rho = 8030 kg/m^3
Cp  = 500 J/(kg K)
k   = 14 W/(m K)
```

The translator explicitly updates shell Cp but does not fully apply the defined shell density/conductivity constants.

This is a production-equivalence issue, not a current import blocker.

---

## A6 — entropy data populated but disabled

The active `RCRTable 3D` block contains the translated `RCR_dUdT_*` curve, but:

```text
m_bUseEntropyData = 0
```

The translator itself previously documented this as requiring a manual BDS step.

The current project acceptance criterion forbids manual post-import model editing: the TBM must be the sole reusable cell definition.

Therefore either:

- set and validate the relevant flag directly in TBM, or
- prove that the desired STAR thermal path uses the dU/dT data without that flag.

Do not mix this physics change into the E004 runtime campaign.

---

## A7 — active area / RCR scaling must be proved TBM-native

Active RCR block currently contains:

```text
m_bSpecifyActiveArea = 0
m_dActiveArea_m2     = 0
m_dAhCell            = 5.0
m_bSpecifyCapacity   = 1
```

This may be correct if STAR derives active area from the constructed winding. Under the TBM-only requirement this must be demonstrated, not assumed.

Production validation must include cell-level resistance / heat-generation scaling against the OpenFOAM-ECM reference.

---

## A8 — REPORT block is stale by design in diagnostics

R005 contains stale REPORT quantities such as legacy JR diameter / capacity / tab-height fields. Existing characterization shows several REPORT geometry fields are not consumed by CreateFromTbm, but not every REPORT field has been characterized.

For the runtime DOE, REPORT fields are deliberately left untouched so active PCD/Builder changes remain isolated.

For the final production TBM, REPORT/derived data should be regenerated or synchronized if STAR/BDS provides a deterministic native path.

---

## A9 — extra Builder/SIMMOD structure is not currently a primary fault

R005 contains Detailed + Simple Builder blocks and many SIMMOD definitions. The Siemens HP reference also contains multiple builder/model blocks and imports successfully.

Therefore block multiplicity alone is not evidence of E004.

Revisit block-structure localization only if runtime-working-template geometry variants pass while equivalent R005-context variants still fail.

---

# Acceptance criteria after E004 is cleared

A production TBM is not accepted merely because `CreateFromTbm` succeeds.

Required:

1. one TBM fully defines one reusable battery cell;
2. no Part-module translation, Boolean, repair, or cap repositioning after import;
3. generated TBM-native solids reproduce the required JellyRoll / Can / cap-equivalent physical roles;
4. cap-equivalent solid has correct thermal/electrical behavior;
5. shell properties match target;
6. distributed RCR capacity/resistance/heat scaling matches About-Energy/OpenFOAM reference;
7. entropy/reversible heat handling is explicitly validated;
8. active-area handling is explicitly validated;
9. stale PCD physical quantities are reconciled or proven non-consumed;
10. final topology remains reusable when pack cell count/layout changes.

---

## Audit status

- E004 root cause: **UNRESOLVED**
- Leading geometry mechanism: **tab-length / electrode-width derived root-height relation**
- Package-volume inconsistency: **CONFIRMED STATIC DEFECT**
- Legacy length/mass inconsistency: **CONFIRMED STATIC DEFECT**
- Cap property mapping: **CONFIRMED MISSING PRODUCTION MAPPING**
- Entropy activation: **UNRESOLVED PRODUCTION PHYSICS ITEM**
- Active-area handling: **UNRESOLVED PRODUCTION PHYSICS ITEM**
