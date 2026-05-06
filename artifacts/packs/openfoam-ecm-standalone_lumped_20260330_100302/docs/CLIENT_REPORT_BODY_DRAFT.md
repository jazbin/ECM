# Client Report Body Draft

This is a working text-body draft for the comprehensive report. It is written in a more internal engineering style first, with the intention that it can later be reduced and rephrased into a cleaner client-facing version without losing technical content.

The structure follows [CLIENT_REPORT_OUTLINE.md](/workspace/docs/CLIENT_REPORT_OUTLINE.md).

## 1. Executive Summary

### 1.1 Project goal

The project goal is a robust OpenFOAM to external ECM coupling for conjugate heat transfer battery-cell simulations. The intended coupling contract is that OpenFOAM provides thermal state information from the active cell region and the ECM returns heat-generation information that OpenFOAM applies as a volumetric source term.

At the current stage, the main target is not a full electro-thermal product model, but a reliable, buildable, testable coupling framework that can support both:

- a lumped whole-cell electrical model
- a distributed thermal representation on the OpenFOAM side

### 1.2 What is working today

The following are working today:

- buildable OpenFOAM coupling library and supporting source tree
- lumped and distributed CHT case setups
- binary file-based coupling
- persistent binary pipe coupling
- automated validation harnesses for lumped and distributed forward test campaigns
- plot-first report generation
- portable package/build/run workflow for use on another workstation

The currently accepted distributed comparison baseline uses a shared whole-cell ECM state combined with distributed thermal/source mapping. That choice is important because it makes lumped and distributed comparisons physically meaningful when the comparison target is electrical equivalence.

### 1.3 Main validated outcomes

The main validated outcomes so far are:

- the lumped forward validation campaign passed its defined gates
- the distributed forward validation campaign passed its defined gates
- the accepted shared-state distributed fixed-current result matches the lumped result to numerical tolerance in total heat
- the previously observed distributed zero-current startup discrepancy was traced to inherited runtime state, not model physics
- the distributed runtime path is now practical after the switch from persistent JSON transport to persistent binary transport
- a true overlap-weighted many-to-many mapping generator has now been implemented and demonstrated in a fresh distributed clone

### 1.4 Main limitations and open items

The main limitations remain:

- the accepted coupling is weakly coupled in time
- there is no validated true distributed electrical network model yet
- external experimental dataset validation has not yet been completed
- the new overlap-weighted mapping is implemented, but it is newer than the accepted forward-validation baseline and needs its own explicit validation track

## 2. System Overview

### 2.1 Problem being solved

The problem being solved is the integration of an external electrical/thermal source model into OpenFOAM battery-cell simulations in a way that is:

- operationally robust
- numerically stable
- portable between workstations
- testable with clear validation gates

This requires more than simply calling an ECM from within a solver loop. It also requires a defensible definition of:

- what temperatures are sent to the ECM
- what heat quantity is returned
- how that heat is distributed back into the CFD mesh
- how runtime state, restart behavior, and failure modes are handled

### 2.2 Coupled workflow: OpenFOAM ↔ ECM

The implemented workflow is:

1. OpenFOAM identifies the active jellyRoll cells.
2. Temperatures are pulled from those cells.
3. The ECM runtime receives temperature plus configured electrical inputs.
4. The ECM runtime returns heat-generation output.
5. The returned heat is mapped into an OpenFOAM volumetric source field.
6. OpenFOAM advances the thermal solution using that source.

Depending on configuration, the ECM-side thermal input may be:

- one effective temperature for lumped behavior
- or a distributed partitioned thermal representation

Depending on configuration, the returned heat may be:

- one whole-cell total heat quantity
- or a distributed field over ECM partitions that is then mapped into the CFD mesh

### 2.3 Lumped vs distributed model definitions

In this project, “lumped” and “distributed” must be defined carefully because the words can refer to different layers.

Lumped means:

- one electrical state for the whole battery cell
- one effective thermal input to that electrical state
- one whole-cell heat output

Distributed can mean two different things:

1. distributed thermal mapping with a shared electrical state
2. truly distributed electrical and thermal states

The accepted current baseline is the first of these, not the second.

That distinction became critical during the lumped versus distributed comparison work. An earlier distributed formulation advanced one ECM-like state per section while also scaling section capacity and keeping full applied current. That made it a different electrical model, not a distributed version of the lumped baseline.

### 2.4 Terminology: battery cell, mesh cell, partition

The report should use the following terminology consistently:

- battery cell: the physical electrochemical unit represented by the ECM
- mesh cell: one OpenFOAM finite-volume cell
- partition or ECM zone: one distributed thermal aggregation/source region used by the coupling

## 3. Implementation Delivered

### 3.1 Custom OpenFOAM components

The repository contains a buildable OpenFOAM extension tree that includes the coupling function object and the solver-side pieces needed for the current CHT workflows.

### 3.2 `ecmCoupler` function object

The `ecmCoupler` function object is the core OpenFOAM-side integration point. It is responsible for:

- collecting temperatures from the configured active region
- packaging runtime inputs
- calling the external runtime
- reading heat output
- applying optional relaxation/interpolation logic
- writing or updating the OpenFOAM source fields

### 3.3 Custom solver / solids-only path

The solids-only path was important because much of the battery-cell validation and debugging was done in solids-only multi-region cases before adding more complexity. This path exposed issues that were not purely “ECM issues”, especially around benchmark definition, implicit coupling, and timestep control.

### 3.4 Custom patch / source-term handling

The project also required care around:

- sign conventions for source application
- interface behavior
- case-local source-term application
- benchmark correctness

Several issues that initially looked like solver problems turned out to be benchmark or harness definition problems, which is why the process documents now emphasize validation of the test itself before solver-code suspicion.

### 3.5 Python ECM runtime and wrappers

The Python side now includes:

- file-based I/O handling
- persistent pipe handling
- binary framed payload support
- shared-state distributed coupling
- overlap-weighted mapping support
- report/diagnostic tooling

### 3.6 Binary / persistent communication modes

Three main communication modes were exercised:

- file-based binary
- persistent JSON
- persistent binary

Persistent binary is the accepted fast path. Persistent JSON was a useful development step, but proved too slow for the distributed element-wise path because of serialization and parsing overhead.

## 4. Coupling Architecture

### 4.1 File-based serial coupling

The file-based binary path established the baseline contract and proved that the mechanics of exchanging temperatures and heat fields were sound.

### 4.2 Persistent-pipe coupling

Persistent pipe coupling removed repeated Python process startup cost. This only became beneficial when the payload format was also efficient, which is why the eventual persistent-binary path matters more than just “having a daemon-like process”.

### 4.3 Binary protocol and handshake

The binary protocol carries:

- run-step metadata
- electrical inputs
- stable keys
- temperature records
- returned heat values

The protocol and handshake behavior are important because numerical agreement is not enough if process restarts, stale outputs, or partial writes can silently corrupt the result.

### 4.4 Stable IDs and mapping tables

Stable mesh-cell identifiers are used so that the coupling is not dependent on incidental storage order. This becomes especially important in distributed and persistent paths.

### 4.5 Temperature pullback and heat redistribution

Two mapping directions matter:

- CFD to ECM: temperature pullback
- ECM to CFD: heat redistribution

These are logically separate operations even if they share the same geometry and tables. That separation became more important once overlap-weighted many-to-many mapping was introduced.

### 4.6 Runtime state files and restart behavior

Runtime state handling exists for robustness, but it also became a source of false discrepancies during validation. The distributed startup transient issue showed that runtime snapshots must be treated as part of the validated system, not as a hidden implementation detail.

## 5. Numerical Strategy

### 5.1 Time integration approach

The current coupling is weakly coupled and partitioned in time. OpenFOAM advances its own timestep, and the ECM is advanced on the configured execute cadence.

### 5.2 Non-synced time stepping: what it means here

“Non-synced” here means that the CFD timestep and the ECM update cadence do not inherently have to be identical. Earlier work showed this can create visible artifacts when the ECM is not called every CFD step.

### 5.3 ECM call cadence vs CFD timestep cadence

The temporal jaggedness investigation showed that a 3-step ECM cadence could still produce a visible pattern even when interpolation was enabled. That was one of the reasons the accepted distributed validation path moved to per-step ECM calls.

### 5.4 Under-relaxation and temporal smoothing

Under-relaxation remains part of the practical stabilization toolkit. In the distributed case it was used to reduce the applied source kink without changing the actual electrical problem.

### 5.5 Diffusion-number control (`maxDi`)

The validation campaigns also clarified that diffusion-number control must be chosen for purpose. A very conservative cap can dominate wall time without materially improving the development-time validation question. `maxDi=100` became the accepted development default because it kept energy error within an acceptable range while reducing runtime substantially.

### 5.6 Why these controls were needed

These controls were needed to separate:

- actual model behavior
- harness/runtime artifacts
- timestep/cadence artifacts
- overly conservative runtime-control choices

## 6. Models Compared

### 6.1 Lumped thermal-electrical coupling

The lumped model is the whole-cell baseline. It uses one electrical state, one effective temperature, and one total heat output.

### 6.2 Distributed thermal coupling with shared electrical state

The accepted distributed baseline keeps the same whole-cell electrical model but distributes the thermal side and the source mapping. This is the correct baseline when the goal is a fair lumped versus distributed comparison.

### 6.3 Earlier distributed formulation and why it was rejected

The earlier distributed formulation was rejected because it was not electrically equivalent. Giving each partition reduced capacity while also giving each partition the full applied current changes the electrical problem.

### 6.4 Final accepted baseline for equivalence testing

The final accepted comparison baseline is:

- one shared whole-cell ECM state
- one effective temperature for the electrical step
- conservative distributed mapping of heat back into the CFD mesh

## 7. Test Methodology

### 7.1 Validation philosophy

Validation proceeded from:

- cheap common-sense and analytic checks
- to structured forward validation
- to broader comparison and performance work

### 7.2 Forward-only test execution rule

The forward-only rule was important process control. If a test failed, only that test was fixed and rerun. Earlier tests were not rerun immediately unless later shared changes made them stale.

### 7.3 Common-sense analytic checks

The early analytic checks included:

- zero-current equilibrium
- fixed-power adiabatic energy balance
- timestep convergence
- mesh convergence

These checks were crucial because they exposed benchmark-definition mistakes before deeper solver-code investigations.

### 7.4 Development validation harness

Separate lumped and distributed forward harnesses were built so the same ordered logic could be applied consistently.

### 7.5 Report generation and diagnostics

Plot-first reports and per-test metrics made it easier to reason about what the system was doing without relying on long raw logs.

## 8. Lumped Model Results

### 8.1 Zero-current equilibrium

The lumped zero-current case passed cleanly with zero applied heat and no temperature drift.

### 8.2 Fixed-current timestep convergence

The lumped timestep convergence gate passed with small differences between the finer runs, indicating that the current timestep settings are acceptable for the forward validation path.

### 8.3 Adiabatic energy-balance test

After fixing the benchmark definition, the lumped adiabatic case closed to within about `-1.889%` energy error in the forward campaign, which is consistent with the accepted development tolerance.

### 8.4 Mesh-independence test

The lumped mesh gate passed with a very small medium/fine `Tmax` difference.

### 8.5 Fixed-current smoothness / cadence

The lumped fixed-current cadence check passed and serves as the smooth whole-cell reference behavior.

### 8.6 Overall lumped assessment

The lumped path is currently the accepted whole-cell reference baseline.

## 9. Distributed Model Results

### 9.1 Zero-current equilibrium

The distributed zero-current case also passes now. The earlier discrepancy was not model physics; it was inherited runtime state.

### 9.2 Fixed-current timestep convergence

The distributed timestep gate passes for the accepted comparison baseline.

### 9.3 Adiabatic energy-balance test

The distributed adiabatic benchmark closes to the same error level as the lumped forward case because this benchmark is fundamentally checking the thermal side, not a different electrical formulation.

### 9.4 Mesh-independence test

The distributed mesh gate also passes at the accepted threshold.

### 9.5 Fixed-current smoothness / cadence

The distributed fixed-current cadence check passes when judged on the accepted post-startup metric.

### 9.6 Overall distributed assessment

The distributed thermal/shared-electrical baseline is currently validated for use as the accepted distributed comparison path.

## 10. Lumped vs Distributed Comparison

### 10.1 What should match and what should not

Under the accepted shared-state baseline, whole-cell electrical outputs should match. Spatial thermal fields do not need to match exactly.

### 10.2 Shared-state equivalence target

The equivalence target is that lumped and distributed produce the same total heat history, to numerical tolerance, because they are solving the same electrical problem.

### 10.3 Final comparison results

The final accepted fixed-current comparison closes to numerical tolerance in `Q_sum_check`.

### 10.4 Residual differences and interpretation

Residual differences in local temperature fields remain meaningful because the distributed thermal representation places heat and thermal resistance in space.

## 11. Technical Maturation And Issues Resolved

### 11.1 Benchmark-definition corrections

The adiabatic benchmark only became trustworthy after correcting the actual case definition on disk.

### 11.2 Startup stale-state artifact

The distributed startup transient was a runtime carryover artifact caused by inherited snapshots.

### 11.3 Runner environment discrepancy

The helper `_run()` was not neutral; it mutated the OpenFOAM environment and changed behavior.

### 11.4 Persistent JSON bottleneck and binary fix

Persistent JSON made the distributed case slower, not faster. Persistent binary fixed that.

### 11.5 PyVista/reporting issue and fallback renderer

The section-rendering path had to be reworked to avoid both off-screen rendering problems and mesh-artifact plotting problems.

### 11.6 Final robustness safeguards introduced

The process documentation and validation harnesses now explicitly guard against:

- bad benchmark definitions
- stale runtime carryover
- harness/environment drift
- misleading plotting/rendering choices

## 12. Performance And Runtime Findings

### 12.1 Lumped runtime characteristics

The lumped path remains relatively cheap and is therefore ideal for routine validation gating.

### 12.2 Distributed runtime characteristics

The distributed path is much more expensive and therefore benefited more from transport and runtime optimizations.

### 12.3 Persistent JSON vs persistent binary vs file-based

The measured difference between those modes is large enough that transport choice is now a first-order design decision.

### 12.4 Solver cost vs coupling-stack cost

The distributed benchmark work showed that the ECM math itself is only a small portion of the total distributed runtime in the validated path.

### 12.5 Practical runtime expectations for longer runs

The 300 s distributed run now provides a practical runtime planning reference for longer transient studies.

## 13. Code Quality And Robustness Improvements

### 13.1 Shared-state distributed ECM implementation

This was the key modeling correction for fair comparison.

### 13.2 Cleaner runner behavior

The runner/harness path is now explicitly part of the validated system.

### 13.3 Safer test harness behavior

Runtime state cleanup and forward-only rerun rules improved debugging discipline.

### 13.4 Portable package and build scripts

The package can now be moved to another workstation and rebuilt there.

### 13.5 Logging, checkpoints, and reproducibility

The repo now has a stronger audit trail for decisions, runs, failures, and accepted outcomes.

## 14. Current Limitations

### 14.1 Weak coupling / no sub-iterations

The accepted baseline is still weakly coupled in time.

### 14.2 Non-synced timestep implications

Future cadence changes need to be handled carefully to avoid reintroducing temporal artifacts.

### 14.3 Dependence on effective temperature definition

The shared-state distributed baseline still depends on the choice of `T_eff`.

### 14.4 Limits of current distributed electrical modeling

There is not yet a validated true distributed electrical network model.

### 14.5 Remaining validation gaps against external data

External dataset validation is still outstanding.

## 15. What The Client Can Use Now

### 15.1 Supported cases

The lumped and distributed shared-state cases are usable today.

### 15.2 Recommended run workflow

The recommended workflow is package-local build, then package-local `Allrun`, with `Allmesh` called automatically if needed.

### 15.3 Packaged deliverables

The package includes source, cases, runtime scripts, docs, and build/run helpers.

### 15.4 What is production-ready vs investigational

Production-ready for current scope:

- lumped path
- distributed shared-state path
- binary-persistent transport
- report/validation infrastructure

Investigational:

- overlap-weighted mapping
- future distributed electrical model

## 16. Recommended Next Steps

### 16.1 External dataset validation

The next major validation stage should use experimental or published reference data.

### 16.2 Stronger electro-thermal validation targets

Mapping and reduction tests should be formalized as separate explicit validation gates.

### 16.3 Optional future distributed electrical model

If required by the client, the next modeling stage should be a true parallel-branch electrical topology, but only on a separate validation track.

### 16.4 Reporting and automation improvements

The current internal-style report can later be rearranged and simplified into a more client-facing version with reduced internal debugging detail and adjusted wording.

## 17. Appendices

### 17.1 File/package inventory

Core deliverables currently relevant to the report are:

- OpenFOAM extension source under `src/`
- Python ECM runtime and helpers under `ecm/`
- portable build helper `build_portable.sh`
- portable package generator `tools/create_portable_package.sh`
- portable package readme `PORTABLE_PACKAGE_README.md`
- case directories:
  - `cases/lumped_solid`
  - `cases/distributed_solid`
  - `cases/distributed_solid_overlap`
  - forward-validation clones under `cases/validation_*`

For reporting and validation, the key generator scripts now include:

- `tools/generate_client_report_full.py`
- `tools/generate_client_extra_figures.py`
- `tools/generate_client_comprehensive_report.py`
- `tools/generate_lumped_forward_report.py`
- `tools/generate_distributed_forward_report.py`
- `tools/generate_forward_comparison_report.py`

The key supporting technical documents are:

- `docs/CLIENT_REPORT_OUTLINE.md`
- `docs/INCONSISTENT_RESULTS_DEBUGGING.md`
- `docs/LESSONS_LEARNED.md`
- `docs/TEST_CASE_RULES.md`
- `docs/ASSUMPTIONS.md`
- `STATUS.md`

### 17.2 Main logs and reports produced

The most important validated run records are:

- Lumped forward campaign summary:
  - `artifacts/validation/lumped_forward/forward_campaign_summary_20260327_201140.md`
- Distributed forward campaign summary:
  - `artifacts/validation/distributed_forward/forward_campaign_summary_20260327_211520.md`
- Accepted lumped vs distributed forward comparison:
  - `artifacts/reports/lumped_vs_distributed_forward_validation_20260327_224210.pdf`

The most important long-form run logs are:

- Lumped fixed-current validation log:
  - `artifacts/logs/validation_lumped_fw_ecm_current_20260327_201050.log`
- Distributed fixed-current validation log used for final equivalence:
  - `artifacts/logs/validation_distributed_fw_ecm_current_20260327_224059.log`
- Distributed 300 s binary-persistent production-style run:
  - `artifacts/logs/distributed_solid_run_20260327_163918.log`
- Overlap-weighted mapping comparison run:
  - `artifacts/logs/distributed_solid_run_20260328_001212.log`

The main current report artifacts are:

- internal-style full report PDF:
  - `artifacts/reports/client_comprehensive_report_full_20260328_005701.pdf`
- internal-style full report markdown:
  - `artifacts/reports/client_comprehensive_report_full_20260328_005701.md`
- extra figure pack:
  - `artifacts/plots/client_report_extra/`

### 17.3 Validation metrics summary tables

Key accepted forward-validation metrics are:

Lumped:

- timestep gate:
  - `ΔT(0.5 vs 0.25) = 0.0839002583 K`
  - `ΔQ(0.5 vs 0.25) = 0.144948 W`
- energy balance:
  - error `= -1.8893244029 %`
- mesh gate:
  - `|Tmax_medium - Tmax_fine| = 0.05068 K`
- zero-current:
  - `max |Q_sum_check| = 0.0 W`
- fixed-current cadence:
  - `max |d²Q| = 2.594167 W`

Distributed:

- timestep gate:
  - `ΔT(0.25 vs 0.125) = 0.0737433189 K`
  - `ΔQ(0.25 vs 0.125) = 0.099981 W`
- energy balance:
  - error `= -1.8893244029 %`
- mesh gate:
  - `|Tmax_medium - Tmax_fine| = 0.05068 K`
- zero-current:
  - `max |Q_sum_check| = 0.0 W`
- fixed-current cadence:
  - `max |d²Q| after 5 s = 0.057002 W`

Additional mapping comparison numbers:

- assignment-mapped distributed 300 s run:
  - final `Q_sum_check = 51.189242 W`
- overlap-weighted distributed 300 s run:
  - final `Q_sum_check = 47.687211 W`

These numbers should be kept explicitly separated from the accepted shared-state equivalence baseline because the overlap-weighted mapping work is newer and belongs on its own validation track.

### 17.4 Definitions and abbreviations

Recommended glossary terms:

- ECM: equivalent circuit model
- CHT: conjugate heat transfer
- CFD: computational fluid dynamics
- mesh cell: one OpenFOAM finite-volume cell
- partition / ECM zone: one distributed thermal aggregation or source region
- `T_eff`: effective temperature used to drive the whole-cell electrical state in the accepted distributed baseline
- `Q_sum_check`: total applied volumetric heat integrated over the active jellyRoll region
- persistent binary: persistent stdin/stdout transport with framed binary payloads
- shared-state distributed baseline: distributed thermal/source mapping with one whole-cell electrical state

### 17.5 Lessons learned / debugging safeguards

The strongest lessons learned from the completed work are:

- Benchmark definitions must be treated as part of the validated system, not as assumptions.
- Cheap common-sense checks should come before deep solver debugging.
- Runtime state files and harness behavior can create false physical discrepancies.
- Direct-shell runs and harness runs must be considered separate execution paths until proven equivalent.
- Transport format matters. A persistent process alone is not enough if the payload is too expensive.
- Plotting choices can create false structure. Preserving true slice polygons and figure aspect ratio matters.

The process safeguards now introduced include:

- validation cases must explicitly clean inherited runtime state
- benchmark BCs and relaxation settings must be checked before solver suspicion
- direct shell versus harness run is a required tie-breaker for inconsistent results
- runner/helpers are treated as part of the validated system
- image aspect ratio must be preserved in client-facing reports
- failed or rejected runs should be documented phase-by-phase, not hidden

These safeguards are now reflected in:

- `docs/INCONSISTENT_RESULTS_DEBUGGING.md`
- `docs/LESSONS_LEARNED.md`
- `docs/TEST_CASE_RULES.md`

### 17.6 Project progress timeline by phase

The appendix timeline should be written phase-by-phase, not as a raw chronology, and should include:

- objective
- accepted result
- diagnostic runs and rejected paths
- what was learned

Recommended phase writeup:

#### 17.6.1 Initial coupling architecture and buildable OpenFOAM integration

- Objective:
  establish a buildable OpenFOAM-side coupling extension and a clear binary I/O contract
- Accepted result:
  buildable function-object library and working serial coupling foundation
- Diagnostic runs and rejected paths:
  early build/test scaffolding, I/O smoke tests
- What was learned:
  buildability, runtime correctness, and validation coverage are separate gates

#### 17.6.2 Baseline serial and parallel coupling validation

- Objective:
  prove the basic coupling works in serial and masterGather parallel mode
- Accepted result:
  serial and parallel baseline coupling validated
- Diagnostic runs and rejected paths:
  parser/record-count and stable-ID checks
- What was learned:
  stable IDs and deterministic mapping are essential early, not optional later

#### 17.6.3 CHT case construction and solver-side integration

- Objective:
  move from synthetic/simple coupling to actual battery-cell CHT cases
- Accepted result:
  working lumped and distributed CHT setups
- Diagnostic runs and rejected paths:
  case-definition and solver-side path corrections
- What was learned:
  case setup errors can look like solver bugs for a long time if not isolated early

#### 17.6.4 Lumped-model stabilization and analytic/common-sense validation

- Objective:
  establish a trustworthy whole-cell baseline
- Accepted result:
  passing lumped forward validation campaign
- Diagnostic runs and rejected paths:
  adiabatic benchmark initially invalid because BCs and relaxation were wrong
- What was learned:
  benchmark definitions must be proven before interpreting discrepancies

#### 17.6.5 Distributed-model stabilization and performance optimization

- Objective:
  remove temporal artifacts, startup artifacts, and transport inefficiency
- Accepted result:
  passing distributed forward validation campaign and fast persistent-binary transport
- Diagnostic runs and rejected paths:
  3-step cadence artifact, stale runtime snapshot artifact, persistent JSON bottleneck
- What was learned:
  transport and runtime-state engineering are first-order concerns in distributed coupling

#### 17.6.6 Lumped vs distributed equivalence investigation

- Objective:
  determine what should actually match between lumped and distributed models
- Accepted result:
  shared-state distributed baseline accepted; lumped/distributed fixed-current equivalence closes to numerical tolerance
- Diagnostic runs and rejected paths:
  per-partition reduced-capacity/full-current formulation rejected; runner environment discrepancy rejected
- What was learned:
  equivalence testing only makes sense if both models solve the same electrical problem

#### 17.6.7 Packaging, reporting, and portability hardening

- Objective:
  prepare the code, cases, and evidence for outside use and review
- Accepted result:
  portable package, build/run scripts, and comprehensive report stack
- Diagnostic runs and rejected paths:
  rendering artifacts, report-layout issues, environment-specific assumptions
- What was learned:
  portability and reporting quality also need explicit engineering and validation
