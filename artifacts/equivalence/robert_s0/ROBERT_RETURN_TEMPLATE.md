# S0 Result Return Template

STAR-CCM+ version/build:
TBM filename used:
.sim files attached (Y/N):

## R0 — Baseline

Import completed without error (Y/N):
Notes/errors during import:

## S0-A — Region geometry / overlap resolution

Volume table (object_name, object_type, volume_mm3):
```
(paste CSV/text table here — columns: object_name | object_type | volume_mm3)
```

Axial section screenshot filename:

Can computational topology — two independent observations:

**Computational subdivision (choose one):**
- [ ] MONOLITHIC — one addressable Can Region, nothing further in the tree
- [ ] SUBDIVIDED — multiple sub-regions/cell-zones/components visible under Can
- [ ] NOT AVAILABLE — cannot determine from STAR UI
Details/notes on tree contents below Can Region:

**Overlap resolution — Can↔EndPlate (choose one):**
(The T06 geometry has a confirmed ~5.3 mm³ Can↔EndPlate overlap at each end; BDS Can and BDS Jellyroll do NOT overlap as bodies)
- [ ] CLIPPED — Can and/or EndPlate volumes appear trimmed/clipped where they overlap at the ends
- [ ] OVERLAP PRESERVED — Can and EndPlate appear to retain original shapes and overlap at ends
- [ ] CANNOT DETERMINE — not possible to tell from UI/evidence
Details/notes:

Can topology screenshot filename (or "NOT AVAILABLE"):

Notes:

## S0-B — Interface / contact topology

Interface/contact table:
```
(paste CSV/text table here — columns: Region A | Region B | exists Y/N | interface/contact type | thermal coupling active | gap/resistance treatment | interface_area_mm2)
```

For the following six pairs, `interface_area_mm2` is required (write NOT AVAILABLE if STAR does not expose it — do not calculate manually):
- Can ↔ Jellyroll
- Mandrel ↔ Jellyroll
- +Ve Tab Root ↔ Jellyroll
- −Ve Tab Root ↔ Jellyroll
- Can ↔ +Ve EndPlate
- Can ↔ −Ve EndPlate

Notes:

## S0-C — Thermal material independence + anisotropic conductivity capability

### C.1 — Anisotropic conductivity capability (on baseline, no change required)

Anisotropic thermal conductivity available for solid Regions (Y/N/NOT VISIBLE):
Cylindrical coordinate frame (kr/kθ/kz) selectable (Y/N/NOT VISIBLE):
Independent kr, kθ, kz values configurable (Y/N/NOT VISIBLE):
Coordinate frame options available in STAR (describe what you see):
Screenshot filename(s) for anisotropy property panels:
Notes:

### C.2 — +Tab electrical role vs. thermal material independence (on T06_S0_material_test.sim)

Before change:
- Core Parts:
- +Tab Parts:
- −Tab Parts:
- Battery Cell / Unit Cell Model valid (Y/N):
- Electrical mesh status:
- +Ve Tab Stem confirmed in +Tab Parts (Y/N):

Continuum isolation check:
- Original Physics Continuum assigned to +Ve Tab Stem:
- Was original continuum shared by other Regions: YES / NO
- Temporary dedicated continuum created: YES / NO / NOT NEEDED
- Other Regions left unchanged: YES / NO

Change made: +Ve Tab Stem thermal conductivity set to k = ______ W/m·K

After change:
- +Ve Tab Stem still in +Tab Parts (Y/N):
- Battery Cell / Unit Cell Model still valid (Y/N):
- Electrical mesh still valid (Y/N):
- Battery model initializes/regenerates without error (Y/N):
- Short solve starts without error (Y/N):
- Exact error/warning message (if any):

### C.3 — Core Part assignment preserved while non-default k applied (on T06_S0_core_test.sim)

Before change:
- Full Core Parts list as shown by STAR:
- Test Region chosen (Jellyroll, or other — specify which):
- Battery Cell / Unit Cell Model valid (Y/N):
- Electrical mesh status:

Continuum isolation check:
- Original Physics Continuum assigned to test Region:
- Was original continuum shared by other Regions: YES / NO
- Temporary dedicated continuum created: YES / NO / NOT NEEDED
- Other Regions left unchanged: YES / NO

Change made: test Region thermal conductivity set to k = ______ W/m·K

After change:
- Test Region still in Core Parts (Y/N):
- Battery Cell / Unit Cell Model still valid (Y/N):
- Electrical mesh still valid (Y/N):
- Battery model initializes/regenerates without error (Y/N):
- Short solve starts without error (Y/N):
- Any other Region's thermal material affected (Y/N):
- Exact error/warning message (if any):

## S0-D — Electrical role vs. thermal path suppression

Test Region used: [ ] −Ve Tab Stem  [ ] Other (specify: _________)
−Ve Tab Stem (or substitute) confirmed in −Tab Parts before starting (Y/N / NOT LISTED):

NOTE: each D test was run in an independent .sim file starting from the clean baseline (confirm below):
- D1 .sim file: T06_S0_D1.sim  [ ] fresh baseline / [ ] reverted baseline
- D2 .sim file: T06_S0_D2.sim  [ ] fresh baseline / [ ] reverted baseline
- D3 .sim file: T06_S0_D3.sim  [ ] fresh baseline / [ ] reverted baseline
- D4 .sim file: T06_S0_D4.sim  [ ] fresh baseline / [ ] reverted baseline

### D1 — Low thermal conductivity (in T06_S0_D1.sim)

Continuum isolation check:
- Original Physics Continuum shared with other Regions: YES / NO
- Temporary dedicated continuum created: YES / NO / NOT NEEDED
- Other Regions' thermal setup unchanged: YES / NO

- D1 mechanism available/settable (Y/N):
- Electrical assignment (−Tab Parts) retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Notes/errors:

### D2 — Energy model exclusion (in T06_S0_D2.sim)

Continuum isolation check:
- Original Physics Continuum shared with other Regions: YES / NO
- Temporary dedicated continuum created: YES / NO / NOT NEEDED
- Other Regions' thermal setup unchanged: YES / NO

- D2 mechanism available/settable (Y/N):
- Electrical assignment (−Tab Parts) retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Notes/errors:

### D3 — Interface made non-conducting/adiabatic (in T06_S0_D3.sim)

- D3 mechanism available/settable (Y/N):
- Electrical assignment (−Tab Parts) retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Interface change isolated to selected interface only (other interfaces unaffected) (Y/N):
- Notes/errors:

### D4 — Explicit thermal contact resistance applied (in T06_S0_D4.sim)

- D4 mechanism available/settable (Y/N):
- Electrical assignment (−Tab Parts) retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Interface change isolated to selected interface only (Y/N):
- STAR property/model name used (exact string as shown in UI):
- Input units as shown in STAR field (e.g. m²·K/W, K/W, W/m²·K):
- Quantity type: [ ] area-specific resistance (m²·K/W) [ ] total resistance (K/W) [ ] conductance (W/K) [ ] conductance-per-area (W/m²·K) [ ] thickness+conductivity pair [ ] other (describe):
- Test value entered and units:
- D4 property panel screenshot filename:
- Notes/errors:

## General

Anything unexpected or worth flagging that doesn't fit the above:
