# OpenFOAM–ECM Reference-Model Equivalence Requirement

**Date:** 2026-09-10  
**Status:** Project-level modelling requirement  
**Applies to:** STAR-CCM+ TBM geometry, thermal interfaces, and validation for the hp2170 NCA RCR distributed model

## Governing objective

For this project, **we are not trying to reconstruct the physically realistic internal clearances of the cell**. We are trying to reproduce the already-defined **OpenFOAM–ECM reference model** in STAR-CCM+.

The OpenFOAM–ECM case is the reference definition. STAR geometry and interface choices must therefore be judged by **model equivalence to that case**, not by whether they look more realistic for a manufactured cylindrical cell.

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

> Does the STAR-CCM+ implementation reproduce the geometry, thermal coupling, electrical response, and integrated behaviour of the OpenFOAM–ECM reference model within the agreed validation tolerances?

This requirement takes precedence over attempts to infer undocumented real-cell internal gaps or contact imperfections unless the project objective is explicitly changed later.
