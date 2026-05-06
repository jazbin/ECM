# Client Report Outline

This document captures the agreed structure for the comprehensive client-facing
report, including the main section hierarchy, appendix framing, and the planned
visual/graphics groups.

## Main Report Structure

1. **Executive Summary**
   1.1 Project goal
   1.2 What is working today
   1.3 Main validated outcomes
   1.4 Main limitations and open items

2. **System Overview**
   2.1 Problem being solved
   2.2 Coupled workflow: OpenFOAM ↔ ECM
   2.3 Lumped vs distributed model definitions
   2.4 Terminology: battery cell, mesh cell, partition

3. **Implementation Delivered**
   3.1 Custom OpenFOAM components
   3.2 `ecmCoupler` function object
   3.3 Custom solver / solids-only path
   3.4 Custom patch / source-term handling
   3.5 Python ECM runtime and wrappers
   3.6 Binary / persistent communication modes

4. **Coupling Architecture**
   4.1 File-based serial coupling
   4.2 Persistent-pipe coupling
   4.3 Binary protocol and handshake
   4.4 Stable IDs and mapping tables
   4.5 Temperature pullback and heat redistribution
   4.6 Runtime state files and restart behavior

5. **Numerical Strategy**
   5.1 Time integration approach
   5.2 Non-synced time stepping: what it means here
   5.3 ECM call cadence vs CFD timestep cadence
   5.4 Under-relaxation and temporal smoothing
   5.5 Diffusion-number control (`maxDi`)
   5.6 Why these controls were needed

6. **Models Compared**
   6.1 Lumped thermal-electrical coupling
   6.2 Distributed thermal coupling with shared electrical state
   6.3 Earlier distributed formulation and why it was rejected
   6.4 Final accepted baseline for equivalence testing

7. **Test Methodology**
   7.1 Validation philosophy
   7.2 Forward-only test execution rule
   7.3 Common-sense analytic checks
   7.4 Development validation harness
   7.5 Report generation and diagnostics

8. **Lumped Model Results**
   8.1 Zero-current equilibrium
   8.2 Fixed-current timestep convergence
   8.3 Adiabatic energy-balance test
   8.4 Mesh-independence test
   8.5 Fixed-current smoothness / cadence
   8.6 Overall lumped assessment

9. **Distributed Model Results**
   9.1 Zero-current equilibrium
   9.2 Fixed-current timestep convergence
   9.3 Adiabatic energy-balance test
   9.4 Mesh-independence test
   9.5 Fixed-current smoothness / cadence
   9.6 Overall distributed assessment

10. **Lumped vs Distributed Comparison**
   10.1 What should match and what should not
   10.2 Shared-state equivalence target
   10.3 Final comparison results
   10.4 Residual differences and interpretation

11. **Technical Maturation And Issues Resolved**
   11.1 Benchmark-definition corrections
   11.2 Startup stale-state artifact
   11.3 Runner environment discrepancy
   11.4 Persistent JSON bottleneck and binary fix
   11.5 PyVista/reporting issue and fallback renderer
   11.6 Final robustness safeguards introduced

12. **Performance And Runtime Findings**
   12.1 Lumped runtime characteristics
   12.2 Distributed runtime characteristics
   12.3 Persistent JSON vs persistent binary vs file-based
   12.4 Solver cost vs coupling-stack cost
   12.5 Practical runtime expectations for longer runs

13. **Code Quality And Robustness Improvements**
   13.1 Shared-state distributed ECM implementation
   13.2 Cleaner runner behavior
   13.3 Safer test harness behavior
   13.4 Portable package and build scripts
   13.5 Logging, checkpoints, and reproducibility

14. **Current Limitations**
   14.1 Weak coupling / no sub-iterations
   14.2 Non-synced timestep implications
   14.3 Dependence on effective temperature definition
   14.4 Limits of current distributed electrical modeling
   14.5 Remaining validation gaps against external data

15. **What The Client Can Use Now**
   15.1 Supported cases
   15.2 Recommended run workflow
   15.3 Packaged deliverables
   15.4 What is production-ready vs investigational

16. **Recommended Next Steps**
   16.1 External dataset validation
   16.2 Stronger electro-thermal validation targets
   16.3 Optional future distributed electrical model
   16.4 Reporting and automation improvements

17. **Appendices**
   17.1 File/package inventory
   17.2 Main logs and reports produced
   17.3 Validation metrics summary tables
   17.4 Definitions and abbreviations
   17.5 Lessons learned / debugging safeguards
   17.6 Project progress timeline by phase

### 17.6 Project Progress Timeline By Phase

17.6.1 Initial coupling architecture and buildable OpenFOAM integration

17.6.2 Baseline serial and parallel coupling validation

17.6.3 CHT case construction and solver-side integration

17.6.4 Lumped-model stabilization and analytic/common-sense validation

17.6.5 Distributed-model stabilization and performance optimization

17.6.6 Lumped vs distributed equivalence investigation

17.6.7 Packaging, reporting, and portability hardening

## Appendix Framing Guidance

The appendix timeline should not be a raw chronological failure dump. Failed or
non-accepted runs should be presented as:

- diagnostic runs
- rejected intermediate configurations
- issue-resolution milestones
- what each branch proved or disproved

Each phase in the appendix can use this mini-template:

- Objective
- Accepted result
- Diagnostic runs and rejected paths
- What was learned

This keeps the report technically honest without presenting the work as
chaotic.

## Visual / Graphics Plan

The report visuals should be organized into five groups.

### 1. Architecture And Workflow Diagrams

1.1 OpenFOAM ↔ ECM coupling workflow

1.2 Lumped vs distributed model concept

1.3 Communication/runtime modes

1.4 Validation flow diagram

### 2. Core Validation Plots

2.1 Lumped validation summary

2.2 Distributed validation summary

2.3 Lumped vs distributed fixed-current comparison

2.4 Lumped vs distributed zero-current comparison

2.5 Energy-balance comparison

2.6 Time-step and mesh-convergence plots

### 3. Temperature Field Graphics

3.1 Lumped cross-sections at representative times

3.2 Distributed cross-sections at representative times

3.3 Side-by-side end-state section comparison

3.4 Optional early-time vs late-time comparison

### 4. Performance Graphics

4.1 Runtime comparison by coupling mode

4.2 Persistent JSON vs binary improvement

4.3 Wall-time vs simulated-time view

4.4 Solver vs coupling-stack cost summary

### 5. Appendix Graphics

5.1 Progress-by-phase timeline

5.2 Diagnostic/rejected-path timeline by phase

5.3 Validation status matrix

## Visual Style Rules

- Use plots for data and tables mainly for setup metadata.
- Keep one message per figure.
- Avoid crowded multi-axis figures unless they are necessary.
- Keep validation visuals separate from performance visuals.
- For lumped vs distributed comparisons, always label whether the distributed
  case uses the accepted shared-state electrical baseline or an earlier
  rejected formulation.

## PyVista Section Rendering Status

PyVista/VTK section rendering was re-checked before report drafting.

Verified environment:

- `pyvista 0.47.1`
- `vtk 9.6.1`

Verified on real cases with successful output:

- `cases/lumped_solid` at `t = 30 s`
- `cases/distributed_solid` at `t = 300 s`

Representative verification images:

- [`artifacts/plots/_pyvista_check/lumped_check_T_slice_z1.png`](/workspace/artifacts/plots/_pyvista_check/lumped_check_T_slice_z1.png)
- [`artifacts/plots/_pyvista_check/lumped_check_T_slice_z2.png`](/workspace/artifacts/plots/_pyvista_check/lumped_check_T_slice_z2.png)
- [`artifacts/plots/_pyvista_check/distributed_check_T_slice_z1.png`](/workspace/artifacts/plots/_pyvista_check/distributed_check_T_slice_z1.png)
- [`artifacts/plots/_pyvista_check/distributed_check_T_slice_z2.png`](/workspace/artifacts/plots/_pyvista_check/distributed_check_T_slice_z2.png)

Conclusion:

- There is no current PyVista installation blocker.
- Temperature sections can be included directly in the client report.
