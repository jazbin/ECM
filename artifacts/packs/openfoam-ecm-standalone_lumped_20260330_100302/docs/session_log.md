# Session Log

- 2026-01-17 12:06 UTC — Reviewed project status and set up session logging for future sessions.
- 2026-01-17 12:13 UTC — Built libecmCouplingFunctionObjects; fixed scalarTransport example (added U, div scheme, solver) and ran serial/parallel; fixed CHT case (function config, decomposeParDict per region) and ran serial/parallel successfully.
- 2026-01-17 12:17 UTC — Replaced unsupported CHT functionObjects; added heat transfer (wallHeatFlux) and flow monitor (phi sum) outputs; removed failing residual/continuityErrors entries; reran CHT serial successfully with new monitors.
- 2026-01-17 12:39 UTC — Added new cpuCabinet-based ECM case (`cases/chtMultiRegionSimpleFoam_cpuCabinet_ecm`), wiring ecmCoupler on `v_CPU` and coded fvOption injecting `ecmQdot`; reduced decomposition to 4; attempted parallel run (snappy + solver completed but reconstructPar aborted due to missing times from timeout—needs a full-duration rerun).
- 2026-01-17 12:49 UTC — Split cpuCabinet scripts into `Allmesh` (one-off meshing) and `Allrun` (reuse mesh, decompose, run, reconstruct); updated README accordingly.
- 2026-01-17 13:27 UTC — Ran cpuCabinet ECM case serial to endTime=20. Issue: parallel decompose (post-split) caused coupled-patch face-count mismatch. Workaround: ran serial; outputs written for times 0..20 (ecmQdot present, monitors recorded).
- 2026-01-17 13:57 UTC — Fixed cpuCabinet pipeline (decompose before splitMeshRegions/topoSet). Parallel run (4 ranks) to endTime=20 with ECM active now completes; fields reconstructed. Remaining observation: volAvg T drifts slightly downward (~299.72 K v_CPU) over 20 s, suggesting current boundary/source balance favors mild cooling. Generated volAvg plot (`postProcessing/ecm_volAvg_T.png`). Next: adjust source/boundaries or extend run for steady plateau.
- 2026-02-24 14:27 UTC — Added repo operating rules and initialized STATUS/TODO plus log/assumption registers to match MY_CODEX_BEST_PRACTICES_RULES.
