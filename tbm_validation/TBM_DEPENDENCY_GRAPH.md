# TBM Dependency Graph — Authoritative
**Last updated:** 2026-09-22
**Supersedes:** TBM_DEPENDENCY_GRAPH_CLAUDE.md (retained as audit evidence)

---

## Campaign logic

```
[STAR environment valid]
         │
         ▼
[E003 gate] Mandrel thickness > 0
  H001 CONFIRMED — resolved in all current TBMs
  FROZEN: do not perturb mandrel thickness
         │
         ▼
[E004 gate] Electrode Root 1 extrusion

  REFUTED / FROZEN — do not retest:
  ┌─────────────────────────────────────────────────┐
  │  H002: tab enable/orientation                   │
  │  H003: m_bOnly1D (retain for model correctness) │
  │  H004-1: S3=0                                   │
  │  H004-2: transport number (retain for model)    │
  │  H004-6: Package m_dintHeight                   │
  └─────────────────────────────────────────────────┘

  BLOCKED (retrieve opportunistically, not campaign-blocking):
  │  H004-5: SepFeed/Tail 0/0 → R006 result pending
  │

  CURRENT OPERATIVE CONTROL:
  └──► H007: combined tab-electrode surplus
           Status: SUPPORTED/HIGH
           Frozen baseline: T06 (both surpluses = +2.00mm) → PASS
           T06 is on the STEP saturation plateau: do not increase further
           Do NOT prioritize exact threshold localization
           ┌── H009: STEP Tab Stem saturation (SUPPORTED/HIGH)
           │   Surplus > ~2mm produces identical STEP geometry
           └── H010: SUPERSEDED — large-negative T09 explained by H007
         │
         ▼
[RADIAL GATE] Can/JR geometry — CURRENT PRIMARY UNKNOWN

  F-series fails here first (before E004 can be assessed):
  H008a: CONFIRMED — separate fatal error from E004
  H008b: SUPPORTED — inherited m_dRepCanXDim = 18mm vs JR OD = 20.6274mm
  H008c: OPEN — electrode-width contribution to wound JR OD

  Radial black-box mapping (CURRENT ATTACK SURFACE):
  ┌──────────────────────────────────────────────────────────┐
  │  RMAP-1: m_dJellyrollThickness_mm → JR OD               │
  │          CONFIRMED/HIGH (August isolated tests)          │
  │                                                          │
  │  RMAP-2: m_dRepCanXDim/YDim → Can OD                    │
  │          SUPPORTED/HIGH (August "apparently drove")      │
  │          RAD-B will confirm or refute                    │
  │                                                          │
  │  RMAP-3: m_dintDiameter → Can ID                        │
  │          OPEN — untested                                 │
  │          RAD-A will confirm or refute                    │
  └──────────────────────────────────────────────────────────┘
         │
         ▼
[RAD-A] Vary m_dintDiameter only; STEP Can OD/ID/JR OD
         │
         ▼
[RAD-B] Vary m_dRepCanXDim/YDim only; STEP Can OD/ID/JR OD
         │
         ▼
[RAD-C] Vary m_dJellyrollThickness_mm only; STEP JR OD
         │
         ▼
[RAD-D1] Production geometry: Can OD=21.09, Can ID=20.6274, JR OD≈20.50
         T06 surplus baseline; STEP to verify; confirm no blocker
         │
         ▼ (only if D1 passes)
[RAD-D2] Production geometry: JR OD = Can ID = 20.6274 mm (exact contact)
         H004-3 physical exact-contact test
         │
         ▼ (only if D2 passes OR physical contact not relevant)
[NE06]  Full production TBM: project Builder/PCD + ≥2mm surplus + RAD-derived radial
         STEP for JR/Can/Cap contact topology verification
         │
         ▼ (only if NE06 fails for unexplained reason)
[H011 contingency] C00/C12/C13 Builder-section localization campaign
```

---

## Frozen subsystems

Do not allocate Robert run slots to these:

| Subsystem | Basis |
|---|---|
| Tab enable/orientation flags | H002 REFUTED (R002–R004) |
| m_bOnly1D for E004 | H003 REFUTED (R004) |
| S3 for E004 | H004-1 REFUTED (R005) |
| Transport number for E004 | H004-2 REFUTED (R005) |
| JR/Can field-value equality for E004 | H004-3 field-value refutation (R005) |
| Package m_dintHeight isolated for E004 | H004-6 REFUTED (R007) |
| Root/tab surplus above T06 | H009 STEP saturation; no geometric benefit |
| T-series radial fields | T06 passes; root geometry frozen |

---

## Hypothesis interaction map

| Hypothesis | Depends on | Informs |
|---|---|---|
| H001 | STAR environment | All downstream (E003 must be absent) |
| H007 | H001 resolved | Production TBM tab-length fix; H009 saturation |
| H004-5 | H001; R006 received | Contingent production fix path if H007-fix still blocked |
| H008a | Independent | All F-series planning; production radial design |
| H008b | H008a; RMAP-2 | F-series fix specification |
| H008c | H008a | Whether electrode-width isolation needed |
| H009 | H007 SUPPORTED; T-series STEP | Tab-length upper limit for production |
| RMAP-1 | August characterization | RAD-C verification; RAD-D JR OD field choice |
| RMAP-2 | August characterization | RAD-B confirmation; Can OD field choice for RAD-D |
| RMAP-3 | Nothing yet | RAD-A test; Can ID field choice for RAD-D |
| H004-3 | RMAP-1,2,3 confirmed; RAD-D1 passes | RAD-D2 exact-contact test |
| H011 | NE06 fails unexpectedly | Builder-section localization (contingency) |
