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

Can computational topology:
- Can Region appears as: [ ] (A) one monolithic Region / [ ] (B) multiple sub-regions/cell-zones / [ ] (C) visually clipped/resolved
- Details/notes on what you see in the tree below Can Region:
- Can topology screenshot filename (or "NOT AVAILABLE"):

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

### C.2 — Electrical role vs. thermal material independence (on material_test.sim)

Before change:
- Core Parts:
- +Tab Parts:
- −Tab Parts:
- Battery Cell / Unit Cell Model valid (Y/N):
- Electrical mesh status:
- +Ve Tab Stem confirmed in positive electrical path (Y/N):

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

## S0-D — Electrical role vs. thermal path suppression

Test Region used: [ ] −Ve Tab Stem  [ ] Other (specify: _________)
−Ve Tab Stem (or substitute) confirmed in −Tab Parts before starting (Y/N / NOT LISTED):

Continuum isolation check (same as S0-C):
- Original Physics Continuum assigned to test Region:
- Was original continuum shared by other Regions: YES / NO
- Temporary dedicated continuum created: YES / NO / NOT NEEDED

D1 — low thermal conductivity while preserving negative electrical assignment:
- Possible (Y/N):
- Electrical assignment (−Tab Parts) retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Isolated to test Region only (other Regions' thermal setup unchanged) (Y/N):
- Notes:

D2 — Energy model disabled/excluded for test Region while electrically referenced:
- Possible (Y/N):
- Electrical assignment (−Tab Parts) retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Isolated to test Region only (other Regions' thermal setup unchanged) (Y/N):
- Notes:

D3 — interface to thermal neighbour made non-conducting while electrical identity intact:
- Possible (Y/N):
- Electrical assignment (−Tab Parts) retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Isolated to selected interface only (other interfaces unaffected) (Y/N):
- Notes:

D4 — explicit thermal contact resistance applied to interface while electrical path intact:
- Possible (Y/N):
- Electrical assignment (−Tab Parts) retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Isolated to selected interface only (other interfaces unaffected) (Y/N):
- STAR property/model name used (exact string as shown in UI):
- Input units as shown in STAR field (e.g. m²·K/W, K/W, W/m²·K):
- Quantity type: [ ] area-specific resistance (m²·K/W) [ ] total resistance (K/W) [ ] conductance (W/K) [ ] conductance-per-area (W/m²·K) [ ] thickness+conductivity pair [ ] other (describe):
- Test value entered and units:
- D4 property panel screenshot filename:
- Notes:

## General

Anything unexpected or worth flagging that doesn't fit the above:
