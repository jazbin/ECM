# Client Report Figure Index

This file indexes the expanded figure set prepared for the internal/client report work.

## Core report figures

Located under `artifacts/plots/client_report_full/`.

- architecture workflow diagram
- lumped vs distributed model concept diagram
- forward-only validation flow diagram
- validation summary metric chart
- energy-balance comparison chart
- fixed-current lumped vs distributed comparison
- zero-current lumped vs distributed comparison
- runtime comparison chart
- all-region section comparison
- current distributed source panel
- overlap-weighted source panel
- full-page normalized weight figures for representative lower/mid/upper ECM zones

## Additional figure pack

Located under `artifacts/plots/client_report_extra/`.

### Time-series comparison plots

- `zero_30s.png`
- `zero_30s_zoom5.png`
- `fixed_30s.png`
- `fixed_30s_zoom5.png`
- `mapping_old_vs_overlap_qsum.png`

### Validation summary plots

- `validation_gate_bars.png`
- `timestep_interpolation_logic.png`

### All-region temperature sections

Lumped forward current case:

- `lumped_fw_t10_x.png`
- `lumped_fw_t10_z.png`
- `lumped_fw_t30_x.png`
- `lumped_fw_t30_z.png`

Distributed forward current case:

- `distributed_fw_t10_x.png`
- `distributed_fw_t10_z.png`
- `distributed_fw_t30_x.png`
- `distributed_fw_t30_z.png`

Overlap-weighted distributed case:

- `overlap_300s_t300_x.png`
- `overlap_300s_t300_z.png`

## Notes

- The section images in this pack are all-region views, not jellyRoll-only views.
- The fixed-current comparison uses a dashed line for the distributed trace.
- Mapping weight images in the full report use normalized CFD→ECM contribution fractions, not raw overlap-volume values.
- `timestep_interpolation_logic.png` is a code-derived explanatory figure for the implemented multi-rate coupling logic, including ECM fire cadence, subcycle hold/linear reconstruction, and OpenFOAM-side temporal averaging plus relaxation.
