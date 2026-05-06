# OpenFOAM ECM Solver Source Pack

Created: 2026-04-09 15:02:24 UTC

Contents:
- `src/chtMultiRegionSolidFoam`: current custom solid-capable multi-region solver source tree used by the validation cases
- `src/ecmCouplingFunctionObjects`: `ecmCoupler` functionObject source used by both validation cases
- `src/ecmPatchFields`: related custom patch-field source kept with the solver stack for completeness, although the current paramset validation cases do not require it at runtime
- `ecm/`: binary-IO ECM orchestrator and mock backend modules
- root Python support files: `ecm_backend.py`, `ecm_coupling_wrapper.py`, `ecm_daemon.py`, `ecm_step.py`
- root parameter files: `params.csv`, `cellprops.csv`
- `Allwmake`: top-level build entry point

Excluded on purpose:
- case folders
- generated build outputs
- logs, post-processing, and transient run files

