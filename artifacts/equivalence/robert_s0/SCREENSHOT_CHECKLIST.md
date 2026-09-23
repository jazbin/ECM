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
- `19b_can_topology_tree.png` — Can Region tree/hierarchy in STAR's UI (or note "NOT AVAILABLE" if nothing is shown below Can Region level)

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

- `39a_jellyroll_material_conductivity_model.png` — shows the conductivity model selector for the Jellyroll (or any solid Region) — is anisotropic an option?
- `39b_anisotropic_coord_frame_options.png` — if anisotropic is available, shows the coordinate frame selection panel (cylindrical / Cartesian / etc.)
- `39c_anisotropic_krkthkz_fields.png` — if cylindrical anisotropy is available, shows the three independent component fields (kr, kθ, kz)

If anisotropic is not available at any step, a single screenshot of what IS shown in the conductivity model panel is sufficient.

## S0-C.2 — Electrical/thermal independence

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

## S0-D — Thermal path suppression (−Ve Tab Stem or substitute)

- `50_d_precheck_neg_tab_parts.png` — shows −Ve Tab Stem (or substitute) listed in −Tab Parts before any change
- `50b_d_continuum_check.png` — shows continuum assignment for test Region (same isolation check as S0-C)
- `51_d1_low_conductivity_test.png`
- `52_d2_energy_model_exclusion.png`
- `53_d3_interface_uncoupled.png`
- `54_d4_resistance_property_panel.png` — shows the D4 resistance property panel with exact model name, value field, and units as displayed by STAR
