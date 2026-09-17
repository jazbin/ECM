# OpenFOAM–ECM Reference-Model Equivalence Requirement

**Date:** 2026-09-10  
**Updated:** 2026-09-17  
**Status:** Project-level modelling requirement  
**Applies to:** STAR-CCM+ TBM geometry, thermal interfaces, electrical-model capability, and validation for the hp2170 NCA RCR model

## Governing objective

For this project, **we are not trying to reconstruct the physically realistic internal clearances of the cell**. We are trying to reproduce the already-defined **OpenFOAM–ECM reference model** in STAR-CCM+.

The OpenFOAM–ECM case is the reference definition. STAR geometry and interface choices must therefore be judged by **model equivalence to that case**, not by whether they look more realistic for a manufactured cylindrical cell.

The desired macro physical/thermal topology is the OpenFOAM three-part topology:

```text
Can
Cap
JellyRoll
```

STAR/BDS may internally require additional CAD bodies or solver-specific electrical parts (tabs, roots, posts, washers, end plates, etc.). Those extra objects are acceptable only if the final STAR thermal/electrothermal model can be shown to reproduce the OpenFOAM three-part topology and behavior to the required tolerance. Extra solver bookkeeping must not silently introduce unwanted thermal domains or thermal paths.

## Electrical ECM capability requirement

The end goal is a STAR-CCM+ workflow that can use **both distributed and 0D/lumped ECM representations**, natively in STAR, without an external Python/OpenFOAM runtime coupling.

### Distributed electrical ECM — mandatory capability

A spatially distributed electrical ECM inside the jelly roll is a **non-negotiable capability** of the final solution.

For the distributed mode:

- one physical jelly roll must contain multiple spatially resolved electrical ECM states/elements;
- local jelly-roll temperature must feed the corresponding local ECM state rather than only one cell-average temperature;
- local electrical response and heat generation must therefore be spatially resolved inside the jelly roll;
- the About-Energy RCR characterization must be consumed natively by STAR-CCM+;
- no external runtime script or external ECM process may be required;
- integrated current, voltage and heat must remain physically consistent with the local distributed contributions.

The current STAR/TBM direction to qualify is:

```text
IET     = RCRTable 3D
Thermal = Distributed
m_bOnly1D = 0
```

The exact STAR electrical discretization does not need to reproduce the previous OpenFOAM axial × radial zoning one-to-one, but it must be genuinely spatially distributed within the jelly roll.

A successful TBM import, CAD generation, thermal run, or RCR table extraction is **not sufficient proof** of distributed electrical operation. STAR runtime evidence must demonstrate more than one independently evolving electrical ECM state within one physical jelly roll.

### 0D/lumped electrical ECM — also required

The final workflow should also support a **0D/lumped whole-cell ECM mode** for cases where a cell-level electrical representation is desired.

In 0D mode:

- one cell-level ECM state may represent the entire cell;
- the model may use a cell-averaged/effective temperature as its electrical input;
- the resulting total cell heat may be coupled into the 3D thermal model according to the selected STAR formulation;
- the RCR data should still be consumed natively by STAR without external runtime scripts.

0D/lumped mode is therefore **not rejected**. It is a required additional operating mode.

However, proving that 0D mode works does **not** satisfy the distributed-ECM requirement. The two modes must be qualified independently and must not be conflated.

The preferred final architecture is therefore:

```text
same OpenFOAM-equivalent physical/thermal cell target
                |
                +--> distributed electrical ECM mode
                |      spatially resolved RCR states
                |
                +--> 0D/lumped electrical ECM mode
                       whole-cell RCR state
```

Whether STAR exposes these as two modes of one imported cell definition, two TBM configurations, or another native STAR-supported arrangement is an implementation question to resolve. The project requirement is the **capability to run both natively**, not a requirement that one identical TBM file must encode both simultaneously.

## Geometry/contact requirement

Where the OpenFOAM reference model has a shared or coincident interface, the STAR model should reproduce that as closely as STAR permits:

- Jelly-roll outer surface is coincident with the can inner surface.
- Jelly-roll/end surfaces are in ideal contact with cap/end surfaces wherever the OpenFOAM reference has shared contact.
- No artificial internal air gap, liner gap, or clearance is to be introduced merely to make the geometry more physically realistic.
- Default thermal contact/interface resistance is zero, matching ideal contact in the OpenFOAM reference.
- If an interface/contact resistance is needed later for calibration or sensitivity work, it must be introduced explicitly as an interface model/parameter, not implicitly by creating a geometric air gap.

## Current radial target

The reference-model radial target is:

- Package/can inner diameter: `20.6274 mm`
- Jelly-roll target OD: `20.6274 mm`
- Intended condition: **zero radial gap / ideal contact**

The previous TBM value `m_dJellyrollThickness_mm = 19.25 mm` is not acceptable for the final OpenFOAM-equivalent model because it creates a `1.3774 mm` diametral gap that is absent from the reference case.

`20.55 mm` exists only as a STAR CAD-feasibility probe/fallback if exact equality is rejected by `Create from Tbm`. It is **not** the preferred model target. If STAR requires a small geometric clearance, the resulting topology must still be treated so that the thermal coupling reproduces the OpenFOAM ideal-contact condition as closely as possible.

## Validation principle

The acceptance question is not:

> Is this the most realistic internal geometry of a physical 2170 cell?

The acceptance question is:

> Does the STAR-CCM+ implementation reproduce the geometry, thermal coupling, electrical response, and integrated behaviour of the OpenFOAM–ECM reference model within the agreed validation tolerances, while supporting both the required distributed electrical ECM mode and the required 0D/lumped ECM mode natively?

This requirement takes precedence over attempts to infer undocumented real-cell internal gaps or contact imperfections unless the project objective is explicitly changed later.
