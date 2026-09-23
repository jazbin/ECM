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
- `19_axial_section_view.png` — centerline section (Can, Jellyroll, Mandrel, top + bottom stacks)
- `19b_can_topology_tree.png` — Can Region tree/hierarchy in STAR's UI showing computational subdivision answer; or note "NOT AVAILABLE" if nothing below Can Region

## S0-B — Interfaces / contacts

- `20_interfaces_tree_full.png`
- `21_interface_can_jellyroll.png` — include area if visible in panel
- `22_interface_can_mandrel.png`
- `23_interface_can_pos_endplate.png` — include area if visible in panel
- `24_interface_can_neg_endplate.png` — include area if visible in panel
- `25_interface_pos_endplate_post.png`
- `26_interface_neg_endplate_post.png`
- `27_interface_pos_post_washer.png`
- `28_interface_neg_post_washer.png`
- `29_interface_pos_washer_tabstem.png`
- `30_interface_neg_washer_tabstem.png`
- `31_interface_pos_tabstem_tabroot.png`
- `32_interface_neg_tabstem_tabroot.png`
- `33_interface_pos_tabroot_jellyroll.png` — include area if visible in panel
- `34_interface_neg_tabroot_jellyroll.png` — include area if visible in panel

## S0-C.1 — Anisotropic conductivity capability

- `39a_jellyroll_material_conductivity_model.png` — conductivity model selector for Jellyroll (or any solid Region); is anisotropic an option?
- `39b_anisotropic_coord_frame_options.png` — if anisotropic is available, shows coordinate frame selector
- `39c_anisotropic_krkthkz_fields.png` — if cylindrical anisotropy is available, shows the three independent component fields

If anisotropic is not available, a single screenshot of the conductivity model panel is sufficient.

## S0-C.2 — +Tab electrical/thermal independence (T06_S0_material_test.sim)

- `40_before_core_tab_parts.png`
- `41_before_battery_cell_valid.png`
- `42_before_electrical_mesh_status.png`
- `42b_continuum_assignment_check.png` — which Physics Continuum +Ve Tab Stem uses; whether other Regions share it; temporary duplicate if created
- `43_material_change_dialog.png`
- `44_after_tab_parts_check.png`
- `45_after_battery_cell_status.png`
- `46_after_electrical_mesh_status.png`
- `47_short_solve_start.png`
- `48_error_message_if_any.png`

## S0-C.3 — Core Part + non-default k (T06_S0_core_test.sim)

- `49a_before_core_parts_list.png` — full Core Parts list before any change
- `49b_c3_continuum_check.png` — continuum assignment for chosen Core Part Region
- `49c_c3_material_change.png` — thermal conductivity change on isolated continuum
- `49d_c3_after_core_parts.png` — Core Parts list after change (confirming test Region still present)
- `49e_c3_battery_model_status.png`
- `49f_c3_error_if_any.png`

## S0-D — Thermal path suppression (each test in its own independent .sim)

### D1 (T06_S0_D1.sim — fresh baseline, low-k only)
- `50a_d1_continuum_check.png`
- `50b_d1_low_conductivity_applied.png`
- `50c_d1_neg_tab_parts_after.png`

### D2 (T06_S0_D2.sim — fresh baseline, Energy exclusion only)
- `51a_d2_energy_exclusion_attempt.png`
- `51b_d2_neg_tab_parts_after.png`
- `51c_d2_error_if_any.png`

### D3 (T06_S0_D3.sim — fresh baseline, adiabatic interface only)
- `52a_d3_interface_uncoupled.png`
- `52b_d3_neg_tab_parts_after.png`

### D4 (T06_S0_D4.sim — fresh baseline, explicit contact resistance only)
- `53a_d4_resistance_property_panel.png` — exact model name, value field, and units as displayed by STAR
- `53b_d4_neg_tab_parts_after.png`
