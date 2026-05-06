# Report Image Set

This folder contains the curated image set currently intended for report assembly.

## Main body candidates

- `01_architecture_workflow.png`
- `02_model_concept_lumped_vs_distributed.png`
- `03_validation_summary_metrics.png`
- `04_zero_current_comparison_30s.png`
- `05_fixed_current_comparison_30s.png`
- `06_energy_balance_comparison.png`
- `07_lumped_allregions_longitudinal_30s.png`
- `08_distributed_allregions_longitudinal_30s.png`
- `09_lumped_allregions_cross_section_30s.png`
- `10_distributed_allregions_cross_section_30s.png`
- `11_runtime_comparison.png`
- `12_timestep_and_interpolation_logic.png`
- `13_overlap_mapping_heat_per_ecm_zone_W.png`
- `14_overlap_mapping_heat_per_cfd_cell_W.png`
- `28_overlap_mapping_heat_per_ecm_zone_W_cross.png`
- `29_overlap_mapping_heat_per_cfd_cell_W_cross.png`
- `30_overlap_mapping_zone_volumes.png`
- `31_overlap_mapping_zone_heat_share.png`

## Appendix / technical figures

- `15_assignment_vs_overlap_mapping_qsum.png`
- `16_weight_support_zone00.png`
- `17_weight_support_zone08.png`
- `18_weight_support_zone17.png`
- `19_zero_current_comparison_first5s.png`
- `20_fixed_current_comparison_first5s.png`
- `21_validation_gate_bars.png`
- `22_lumped_allregions_longitudinal_10s.png`
- `23_distributed_allregions_longitudinal_10s.png`
- `24_lumped_allregions_cross_section_10s.png`
- `25_distributed_allregions_cross_section_10s.png`
- `26_overlap_case_allregions_longitudinal_300s.png`
- `27_overlap_case_allregions_cross_section_300s.png`

## Notes

- Cross-sections are now generated with support/variation-aware plane selection for the field being shown rather than by fixed geometric center alone.
- The time-stepping figure is now centered on the accepted validated configuration: ECM fire at every CFD step, with optional relaxation on the applied field.
- The overlap mapping visuals now include applied heat in `W`, plus zone-volume and zone-heat-share summaries.
