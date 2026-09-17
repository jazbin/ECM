# Screenshot Checklist

You don't need every one of these if the `.sim` files you return already
contain the equivalent evidence — this list is just to help make sure
nothing important gets missed. Suggested filenames below (exact naming isn't
critical, just keep them identifiable).

## General / R0

- `00_star_version.png` — Help/About or version banner
- `01_import_complete_tree.png` — full Parts/Regions tree right after import

## S0-A — Region geometry / overlap

- `10_regions_tree.png`
- `11_geometry_parts_tree.png`
- `12_volume_report_can.png`
- `13_volume_report_jellyroll.png`
- `14_volume_report_mandrel.png`
- `15_volume_report_pos_endplate.png`
- `16_volume_report_neg_endplate.png`
- `17_volume_report_pos_internalpost.png`
- `18_volume_report_neg_internalpost.png`
- `19_axial_section_view.png` — the centerline section requested in S0-A

## S0-B — Interfaces / contacts

- `20_interfaces_tree_full.png`
- `21_interface_can_jellyroll.png`
- `22_interface_can_mandrel.png`
- `23_interface_can_pos_endplate.png`
- `24_interface_can_neg_endplate.png`
- `25_interface_pos_endplate_post.png`
- `26_interface_neg_endplate_post.png`
- `27_interface_pos_post_washer.png`
- `28_interface_neg_post_washer.png`
- `29_interface_pos_washer_tabstem.png`
- `30_interface_neg_washer_tabstem.png`
- `31_interface_pos_tabstem_tabroot.png`
- `32_interface_neg_tabstem_tabroot.png`
- `33_interface_pos_tabroot_jellyroll.png`
- `34_interface_neg_tabroot_jellyroll.png`

## S0-C — Electrical/thermal independence

- `40_before_core_tab_parts.png`
- `41_before_battery_cell_valid.png`
- `42_before_electrical_mesh_status.png`
- `42b_continuum_assignment_check.png` — shows which Physics Continuum `+Ve Tab Stem` uses and whether other Regions share it (and the temporary duplicated continuum, if one was created)
- `43_material_change_dialog.png`
- `44_after_tab_parts_check.png`
- `45_after_battery_cell_status.png`
- `46_after_electrical_mesh_status.png`
- `47_short_solve_start.png`
- `48_error_message_if_any.png`

## S0-D — Thermal path suppression

- `50_d1_low_conductivity_test.png`
- `51_d2_energy_model_exclusion.png`
- `52_d3_interface_uncoupled.png`
- `53_d4_contact_resistance_applied.png`
