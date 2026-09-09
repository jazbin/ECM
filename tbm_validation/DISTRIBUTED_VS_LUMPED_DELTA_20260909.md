# Distributed vs Lumped TBM Delta Report
Date: 2026-09-09
Branch: tbm-rcr-modelmap-fix-exec

---

## Files compared

| Role        | File                                                   | SHA-256 (first 16 hex) |
|-------------|--------------------------------------------------------|------------------------|
| Distributed | out/rcr_candidate/hp2170-rcr-v1-tabs-on-sameFace.tbm  | 7d5850b628389e71       |
| Lumped      | out/lumped_candidate/hp2170-rcr-lumped-v1.tbm          | 897ed0ccb267a372       |

Full SHAs:
  Distributed: 7d5850b628389e713e83468d27e45600942b1deb1e23e672f9d18c4f580d6940
  Lumped:      897ed0ccb267a372e3b5af7bad064147b4e19d85039070245f9f7f64e189c9a9

---

## Change: single MODELMAP Thermal line

Size delta: 11 bytes (len("Distributed") = 11)
First diff at byte offset 207351 in distributed candidate.

```
BEFORE (distributed candidate):
    Thermal   =   Distributed

AFTER (lumped candidate):
    Thermal   =
```

No other bytes changed. All RCR data, geometry parameters, SIMMOD block contents,
and all other MODELMAP fields (IET, Electrolyte) are identical.

---

## Per-field classification

| Field / block          | Classification           | Notes                                                     |
|------------------------|--------------------------|-----------------------------------------------------------|
| MODELMAP / IET         | IDENTICAL                | RCRTable 3D in both                                       |
| MODELMAP / Electrolyte | IDENTICAL                | General Electrolyte in both                               |
| MODELMAP / Thermal     | REQUIRED_FOR_LUMPED      | blank = no STAR thermal; Distributed = STAR solves thermal|
| RCRTable 3D / m_bOnly1D | IDENTICAL               | 0 in both (3D electrochemical)                            |
| RCRTable 3D / m_bLumpedEnergyBalance | IDENTICAL  | 0 in both                                                 |
| RCRTable 3D / m_nRCRParameterSets | IDENTICAL     | 3 in both                                                 |
| RCRTable 3D / m_nXGridPoints | IDENTICAL          | 7 in both                                                 |
| RCRTable 3D / m_bSpecifyCapacity | IDENTICAL      | 1 in both                                                 |
| RCRTable 3D / m_dAhCell | IDENTICAL              | 5.0 in both                                               |
| RCRTable 3D / RCR data (Ro, Rp, tau, V, SOC tables) | IDENTICAL | All numerical tables unchanged         |
| All other SIMMOD blocks | IDENTICAL               | Inactive SIMODs not touched                               |

---

## Semantic meaning of the Thermal delta

  Thermal = Distributed  →  STAR-CCM+ activates its own [Distributed] thermal SIMMOD.
                             The battery cell temperature is solved internally by STAR.
                             Appropriate for standalone BDS/STAR-CCM+ runs.

  Thermal = (blank)      →  STAR-CCM+ does NOT activate an internal thermal solver.
                             Temperature is imposed from the external CFD field.
                             Appropriate for OpenFOAM coupling (CHT provides temperature).

Both configurations use the same RCR electrochemical model with the same parameters.
The difference is purely in who solves the thermal field.

---

## Validation summary (lumped candidate)

  MODELMAP IET = RCRTable 3D:  PASS
  RCRTable 3D SIMMOD exists:   PASS
  m_bSpecifyCapacity = 1:      PASS
  m_dAhCell = 5.0:             PASS
  m_nRCRParameterSets = 3:     PASS
  m_bOnly1D in RCRTable 3D block: 0 (PASS)
  MODELMAP Thermal = (blank):  confirmed (intended for OF coupling)
