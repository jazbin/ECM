# TBM Hypothesis Dependency Graph — Independent Reconstruction
**Date:** 2026-09-22

## Runtime gate sequence (sequential dependency)

```
[STAR environment valid]
         │
         ▼
[R001] Mandrel thickness > 0
  H001 CONFIRMED — fixed
         │
         ▼
[E004 gate] Electrode Root 1 extrusion
  ┌──────────────────────────────────────────┐
  │ Refuted paths (do not retest):           │
  │  H002: tab enable/orientation            │
  │  H003: m_bOnly1D                         │
  │  H004-1: S3=0                            │
  │  H004-2: transport number                │
  │  H004-3: JR/Can exact radial contact     │
  │  H004-6: Package m_dintHeight            │
  └──────────────────────────────────────────┘
         │
         ├──► H004-5: SepFeed/Tail 0/0
         │    Status: BLOCKED (R006 pending)
         │    Tests: production TBM only; F-series can't reach this
         │
         └──► H007: tab_length − electrode_width surplus threshold
              Status: SUPPORTED (confirmed in H/T series)
              Threshold: combined surplus between 0.10mm and 0.70mm
              ┌── STEP saturation
              │   H009: surplus > ~2mm produces identical geometry
              │   Status: SUPPORTED
              └── T09 anomaly
                  H010: large negative surpluses fail (consistent with H007)
                  Status: OPEN (may not be separate)

[F-series gate — separate from E004] Radial geometry conflict
  H008: STAR-computed wound JR OD > Package Can ID
  Status: CONFIRMED (separate blocker for all 9 F-TBMs)
  Depends on: electrode widths + Package radial dimensions
  Blocks: all production-cell TBM testing (F01–F09)
  Resolution path: H008 must be resolved BEFORE production import is testable

[C00–C17 campaign — localization, not yet run]
  H011: Detailed Builder vs PCD vs their interaction
  Status: BLOCKED (campaign not run)
  Depends on: E004 still active in production TBM
  Resolution path: requires Robert to run C00, C12, C13 at minimum
```

## Hypothesis interaction map

| Hypothesis | Depends on | Blocks or informs |
|---|---|---|
| H001 | STAR environment | All downstream hypotheses (E003 must be absent) |
| H007 | H001 resolved | Production TBM tab-length fix; H009 saturation threshold |
| H004-5 | H001 resolved; R006 result received | Production TBM validation; independent of H007 |
| H008 | Independent of E004 | All F-series tests; production cell qualification |
| H009 | H007 supported; STEP export from passing cases | Tab-length upper limit for production choice |
| H010 | H007 threshold analysis | If explained by H007, no new hypothesis needed |
| H011 | E004 active in production TBM; C00–C17 run | Localization: which Builder/PCD section drives E004 |

## Frozen subsystems (do not retest these)

The following have been directly refuted at runtime and should not consume further test slots:

- Tab enable/disable flags (H002)
- Tab vertical orientation (H002)
- m_bOnly1D values (H003) — still fix for model correctness; not E004
- +Electrode S3 field (H004-1)
- Transport number metadata (H004-2)
- JR OD / Can ID radial equality (H004-3) — distinct from H008 F-series
- Package m_dintHeight isolated change (H004-6)

## Production TBM path dependencies

```
To get a production-ready TBM:

1. [H008 resolution]
   Understand why STAR-computed JR OD > Can ID for 2170 electrodes.
   Fix: likely increase Package m_dextDiameter, OR use correct m_dJellyrollThickness_mm
   that matches STAR's winding computation.
   PREREQUISITE for all F-series tests.

2. [H007 fix applied]
   Set both tab lengths ≥ electrode_width + 0.70mm (conservative; final value after
   threshold is confirmed).
   Alternatively: close R006 to determine if H004-5 is an alternative fix path.

3. [F-series retry with H008 fix + H007 fix]
   Rerun F04-equivalent with corrected radial geometry and positive root surpluses.
   If passes: STEP export to verify JellyRoll/Can/Cap contact topology.

4. [Contact topology verification]
   Confirm JellyRoll–Cap axial contact and JellyRoll–Can radial contact match
   OpenFOAM equivalence targets.

5. [Distributed RCR model verification]
   Confirm RCRTable 3D, correct electrical mesh, distributed spoke count.
```
