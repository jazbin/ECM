# STAR-CCM+ TBM Selective Import — Electrical/Geometry Behavior Note

**Date:** 2026-09-10

## Question

If STAR-CCM+ allows only selected TBM objects/parts to be created during `Create from Tbm`, can we omit detailed electrode/root geometry while keeping the electronic/electrothermal simulation valid?

## Evidence-backed conclusions

### 1. TBM model data and 3D geometry are related but not identical concerns

STAR imports a 3D Battery Cell from a BDS/TBM definition. The cell stores a `Unit Cell Model` and, for cylindrical cells, an electrical mesh definition (`Specified Electrical Mesh Dimensions`, `Actual Electrical Mesh Dimensions`, `Number of Spokes`). This means the electrical model definition exists as battery-cell data, not merely as material properties attached to an arbitrary CAD solid.

However, STAR documentation also states that 3D battery cells require specified geometry parts. A 3D battery module cell explicitly associates:

```text
Core Parts
+ Tab Parts
- Tab Parts
Battery Cell
```

Therefore a valid distributed 3D battery simulation requires both the imported cell/model definition **and** a complete geometry-part assignment.

### 2. The homogenized jellyroll/core is electrically important

STAR's battery-module reporting/connector setup uses the stack or jellyroll region as the battery-current/core region. For the project architecture, the jellyroll/core is therefore not just a thermal solid. It is the spatial host for the distributed battery model/electrical mesh.

### 3. Positive and negative terminal/tab paths are electrically important

The module cell has separate `+ Tab Parts` and `- Tab Parts` assignments. Connector current-density setup uses the positive and negative terminal interfaces. Therefore omitting both tab/terminal paths may still allow some cell data to import, but is not sufficient evidence of a physically usable distributed electrical simulation.

### 4. Can and cap do not substitute for the electrical tab assignments

The can/package affects thermal performance and is part of the desired thermal-contact model. It may also participate geometrically in an end-plate/post connection depending on the generated cylindrical topology. But the battery module still distinguishes core and positive/negative tab parts. Therefore can/cap alone cannot be assumed to close the distributed electrical circuit.

### 5. The likely minimal useful production topology to test is

```text
JELLYROLL / CORE
+ POSITIVE TAB / TERMINAL PATH
+ NEGATIVE TAB / TERMINAL PATH
+ CAN / CAP for thermal package/contact
```

If STAR exposes a separate detailed `Electrode Root` CAD object that can be omitted while preserving the core and both terminal assignments, that is potentially useful. It must pass an electrical-completeness audit before adoption.

### 6. Can/cap/jellyroll-only import is still useful diagnostically

A geometry containing only the can/cap and jellyroll/core can answer whether the desired macro contact topology is constructible. It must be labelled `GEOMETRY_ONLY_DIAGNOSTIC` until positive/negative terminal parts and the distributed electrical mesh are confirmed.

## Strong independent control: RCR data-only import

STAR supports creating a User Defined Battery Cell, selecting the RCR model, and using `Extract RCR Parameters from TBM File` to populate RCR parameter tables without invoking the cylindrical 3D CAD builder.

Run this once using the exact Robert-tested project TBM. Expected project data are three temperature sets (288.15, 298.15, 308.15 K).

Interpretation:

```text
RCR data-only PASS + Create-from-TBM E004 FAIL
    -> RCR numerical/model data are separable from the CAD-builder failure.

RCR data-only FAIL
    -> there is an electrical/model-data problem in addition to geometry.
```

This control does not prove 3D spatial electrical mapping, but it prevents geometry errors from being confused with RCR table errors.

## Current project axial geometry finding

Robert-tested failed project TBM:

```text
Package internal height = 65.11
Separator width          = 67.11
Negative electrode width = 65.11
Positive electrode width = 64.11
```

Siemens `validationBattery.tbm`:

```text
Package internal height = 60
Separator width          = 59
Negative electrode width = 57
Positive electrode width = 56
```

Both use the same relative electrode nesting (`separator-negative = 2`, `negative-positive = 1`) and the same Detailed Builder offsets (`Neg=1`, `Pos=0.5`). The critical difference is package clearance:

```text
project: package-separator = -2, package-negative = 0
Siemens: package-separator = +1, package-negative = +3
```

Therefore the project already has a STAR-like recessed relationship **between separator/negative/positive layers**, but not relative to the package cavity. The package/layer axial relation is a legitimate E004 suspect and is covered by campaign variants C14-C17.

## Production sign-off rule

Do not judge electrical validity from CAD success alone.

After any selective import, production eligibility requires at least:

```text
Unit Cell Model correct
Actual Electrical Mesh Dimensions valid
Number of Spokes valid
Core Parts populated
+ Tab Parts populated
- Tab Parts populated
```

Then perform a one-cell current/voltage/heat sanity run before comparing to the OpenFOAM-ECM reference.

## Reference sources consulted

- Simcenter STAR-CCM+ Battery Cells Reference, 2406-era documentation mirror.
- Simcenter STAR-CCM+ Battery Modules Reference, 2023/2406-era documentation mirror.
- STAR-CCM+ cylindrical battery tutorial: normal `Create from Tbm` workflow instructs selecting all objects in `Import Battery Options`.

The exact selectable-object names are version-dependent and must be captured from Robert's actual STAR installation rather than guessed here.
