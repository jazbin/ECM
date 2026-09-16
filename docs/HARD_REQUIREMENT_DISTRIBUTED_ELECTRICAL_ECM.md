# HARD REQUIREMENT — Distributed Electrical ECM in STAR-CCM+

**Status:** NON-NEGOTIABLE PRODUCTION REQUIREMENT  
**Date locked:** 2026-09-16

## Requirement

The production STAR-CCM+ battery model **must use a spatially distributed electrical ECM inside the jelly roll**.

A single whole-cell / whole-jelly-roll electrical RCR state is **not acceptable**.

The fact that the thermal solution is 3D or distributed does **not** satisfy this requirement by itself. The electrical ECM state must also be spatially resolved across multiple elements/zones of the jelly roll, so that different locations can have different local ECM temperatures, electrical states, and heat generation.

## Explicitly rejected architectures

The following are **not acceptable as the production solution**:

- STAR User-Defined Battery Cell using one 0D/lumped RCR model for the whole physical cell.
- One ECM instance/state for the complete jelly roll, even if its total heat is subsequently distributed into a 3D thermal region.
- Any architecture where `Thermal = Distributed` but the electrical model remains one cell-level/lumped state.
- Any geometry simplification that achieves the desired Can + Cap + JellyRoll solids by sacrificing spatially distributed electrical ECM behavior.
- Any fallback that reproduces only average cell voltage/temperature/heat while losing intra-jelly-roll electrical/thermal coupling.

Such configurations may be used only as **diagnostic/control cases**, never as the production architecture or as evidence that the project requirement has been met.

## Required production behavior

The target STAR-CCM+ implementation must demonstrate all of the following:

1. **Multiple electrical ECM states/elements exist within one physical jelly roll.**
2. Local jelly-roll temperature feeds the corresponding local electrical ECM state rather than only one cell-average temperature.
3. Heat generation is obtained from the spatially distributed electrical solution and is spatially resolved inside the jelly roll.
4. The distributed electrical solution uses the About-Energy RCR characterization natively in STAR-CCM+.
5. No external Python/OpenFOAM runtime coupling or additional runtime scripts are required for the production case.
6. Cell-level current/voltage and total heat remain physically consistent when the local distributed contributions are integrated.

## Current preferred STAR/TBM direction

The path to qualify is the native STAR distributed battery route, currently centered on:

```text
IET     = RCRTable 3D
Thermal = Distributed
m_bOnly1D = 0
```

The RCR tables should be consumed natively from the TBM / STAR battery model. The exact STAR electrical discretization does not need to reproduce the previous OpenFOAM axial × radial partition one-to-one, but it **must remain genuinely spatially distributed within the jelly roll**.

## Geometry requirement interaction

The desired macro physical/thermal topology remains:

```text
Can
Cap
JellyRoll
```

However, geometry work must never be allowed to silently downgrade the electrical model to a single lumped ECM state. If STAR requires additional internal electrical assignments, tab paths, connector objects, or solver-specific parts to support the distributed electrical formulation, they must be evaluated as implementation details while preserving the three-part physical topology as closely as STAR permits.

## Qualification rule

A candidate is **NOT production-qualified** until STAR runtime evidence proves that one physical cell contains more than one independently evolving electrical ECM state within the jelly roll.

A successful TBM import, successful CAD generation, successful thermal run, or successful extraction of RCR data from the TBM is **insufficient by itself**.

The decisive proof must come from the electrical solution behavior inside STAR-CCM+.

---

This requirement takes precedence over convenience, geometry simplification, and any lumped-electrical workaround.
