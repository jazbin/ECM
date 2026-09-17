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
(paste CSV/text table here)
```

Axial section screenshot filename:

Notes:

## S0-B — Interface / contact topology

Interface/contact table (Region A, Region B, exists Y/N, interface/contact type, thermal coupling active, contact resistance/gap):
```
(paste CSV/text table here)
```

Notes:

## S0-C — Electrical role vs thermal material independence

Before change:
- Core Parts:
- +Tab Parts:
- −Tab Parts:
- Battery Cell / Unit Cell Model valid (Y/N):
- Electrical mesh status:
- +Ve Tab Stem confirmed in positive electrical path (Y/N):

Change made: +Ve Tab Stem thermal conductivity set to k = ______ W/m·K

After change:
- +Ve Tab Stem still in +Tab Parts (Y/N):
- Battery Cell / Unit Cell Model still valid (Y/N):
- Electrical mesh still valid (Y/N):
- Battery model initializes/regenerates without error (Y/N):
- Short solve starts without error (Y/N):
- Exact error/warning message (if any):

## S0-D — Electrical role vs thermal path suppression

D1 — low thermal conductivity while preserving electrical assignment:
- Possible (Y/N):
- Electrical assignment retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Notes:

D2 — Energy model disabled/excluded for Region while electrically referenced:
- Possible (Y/N):
- Electrical assignment retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Notes:

D3 — interface to neighbour made non-conducting while electrical identity intact:
- Possible (Y/N):
- Electrical assignment retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Notes:

D4 — explicit thermal contact resistance applied to interface while electrical path intact:
- Possible (Y/N):
- Electrical assignment retained (Y/N):
- Battery Cell / Unit Cell Model valid (Y/N):
- Notes:

## General

Anything unexpected or worth flagging that doesn't fit the above:
