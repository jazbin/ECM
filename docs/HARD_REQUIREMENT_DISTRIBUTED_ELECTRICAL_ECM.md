# HARD REQUIREMENT — Distributed Electrical ECM Capability in STAR-CCM+

**Status:** NON-NEGOTIABLE CAPABILITY REQUIREMENT  
**Date locked:** 2026-09-16  
**Clarified:** 2026-09-17

## Requirement

The final STAR-CCM+ battery workflow **must support a spatially distributed electrical ECM inside the jelly roll**.

A single whole-cell / whole-jelly-roll electrical RCR state is **not acceptable as a substitute for the distributed mode**.

However, the end goal is to support **both**:

1. a genuinely distributed electrical ECM mode; and
2. a 0D/lumped whole-cell ECM mode.

The 0D mode is therefore not rejected. It is an additional required operating mode. What is prohibited is treating successful 0D operation as evidence that the distributed requirement has been met.

## Distributed-mode requirement

For distributed operation:

- multiple electrical ECM states/elements must exist within one physical jelly roll;
- local jelly-roll temperature must feed the corresponding local electrical ECM state rather than only one cell-average temperature;
- heat generation must arise from the spatially distributed electrical solution and be spatially resolved inside the jelly roll;
- the About-Energy RCR characterization must be used natively in STAR-CCM+;
- no external Python/OpenFOAM runtime coupling or additional runtime script may be required;
- integrated cell current, voltage and heat must remain physically consistent with the distributed local contributions.

The current path to qualify is the native STAR distributed battery route, centered on:

```text
IET     = RCRTable 3D
Thermal = Distributed
m_bOnly1D = 0
```

The exact STAR electrical discretization does not need to reproduce the previous OpenFOAM axial × radial partition one-to-one, but it **must remain genuinely spatially distributed within the jelly roll**.

## 0D/lumped-mode requirement

The final workflow should also support a native STAR 0D/lumped electrical ECM representation for whole-cell studies.

In this mode:

- one whole-cell ECM state is acceptable;
- a cell-average/effective temperature may drive the electrical state;
- the resulting total heat may be coupled to the 3D thermal model according to the native STAR formulation;
- the same underlying About-Energy RCR characterization should be usable without external runtime scripts, subject to STAR's supported model mapping.

Distributed and 0D modes must be qualified independently.

## Geometry requirement interaction

The desired macro physical/thermal topology remains:

```text
Can
Cap
JellyRoll
```

Geometry simplification must never force the distributed mode to collapse into one lumped electrical state. If STAR requires additional internal electrical assignments, tab paths, connector objects, or solver-specific parts for distributed operation, they should be treated as implementation details while preserving the OpenFOAM-equivalent three-part physical/thermal topology as closely as STAR permits.

## Qualification rule

The distributed capability is **not qualified** until STAR runtime evidence proves that one physical cell contains more than one independently evolving electrical ECM state within the jelly roll.

A successful TBM import, successful CAD generation, successful thermal run, successful extraction of RCR data, or successful 0D/lumped run is insufficient by itself.

The decisive proof for distributed mode must come from the spatial electrical solution behavior inside STAR-CCM+.

The 0D mode has a separate qualification objective: prove native whole-cell RCR operation without external runtime scripts.

---

The project target is therefore **dual capability: distributed + 0D**, with distributed support remaining mandatory and non-substitutable.
