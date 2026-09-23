# Geometry Campaign — Return Template

STAR-CCM+ / BDS version:
Date of measurements:

For each case: open TBM in BDS, export STEP, measure dimensions from STEP geometry directly (not from BDS report fields or manual calculation).

---

## RAD-A — GC_RAD_A_can_id_probe.tbm

BDS generated without error (Y/N):
BDS error message (if any):

STEP body list (paste all solid body names from STEP, one per line):
```
(paste here)
```
Number of bodies in STEP:

Dimension table (measure from STEP):
| Quantity | Value (mm) | Notes |
|---|---|---|
| JR OD | | |
| Mandrel OD | | write ABSENT if no Mandrel body |
| Can inner diameter | | |
| Can outer diameter | | |
| Can total height | | |
| JR total height | | |
| JR-top to Can-top distance | | positive = Can extends above JR |
| JR-bottom to Can-bottom distance | | positive = Can extends below JR |

Notes / unexpected observations:

---

## RAD-B — GC_RAD_B_can_od_probe.tbm

BDS generated without error (Y/N):
BDS error message (if any):

STEP body list:
```
(paste here)
```
Number of bodies in STEP:

Dimension table:
| Quantity | Value (mm) | Notes |
|---|---|---|
| JR OD | | |
| Mandrel OD | | |
| Can inner diameter | | |
| Can outer diameter | | |
| Can total height | | |
| JR total height | | |
| JR-top to Can-top distance | | |
| JR-bottom to Can-bottom distance | | |

Notes:

---

## RAD-C — GC_RAD_C_jr_od_probe.tbm

BDS generated without error (Y/N):
BDS error message (if any):

STEP body list:
```
(paste here)
```
Number of bodies in STEP:

Dimension table:
| Quantity | Value (mm) | Notes |
|---|---|---|
| JR OD | | |
| Mandrel OD | | |
| Can inner diameter | | |
| Can outer diameter | | |
| Can total height | | |
| JR total height | | |
| JR-top to Can-top distance | | |
| JR-bottom to Can-bottom distance | | |

Notes:

---

## AX-A — GC_AX_A_can_height_probe.tbm

BDS generated without error (Y/N):
BDS error message (if any):

STEP body list:
```
(paste here)
```
Number of bodies in STEP:

Dimension table:
| Quantity | Value (mm) | Notes |
|---|---|---|
| JR OD | | |
| Mandrel OD | | |
| Can inner diameter | | |
| Can outer diameter | | |
| Can total height | | |
| JR total height | | |
| JR-top to Can-top distance | | |
| JR-bottom to Can-bottom distance | | |

Notes:

---

## AX-B — GC_AX_B_sep_tail_zero.tbm

BDS generated without error (Y/N):
BDS error message (if any):

STEP body list:
```
(paste here)
```
Number of bodies in STEP:

Dimension table:
| Quantity | Value (mm) | Notes |
|---|---|---|
| JR OD | | |
| Mandrel OD | | |
| Can inner diameter | | |
| Can outer diameter | | |
| Can total height | | |
| JR total height | | |
| JR-top to Can-top distance | | |
| JR-bottom to Can-bottom distance | | |

Notes:

---

## AX-C — GC_AX_C_sep_feed_zero.tbm

BDS generated without error (Y/N):
BDS error message (if any):

STEP body list:
```
(paste here)
```
Number of bodies in STEP:

Dimension table:
| Quantity | Value (mm) | Notes |
|---|---|---|
| JR OD | | |
| Mandrel OD | | |
| Can inner diameter | | |
| Can outer diameter | | |
| Can total height | | |
| JR total height | | |
| JR-top to Can-top distance | | |
| JR-bottom to Can-bottom distance | | |

Notes:

---

## AX-D — GC_AX_D_end_overlap_probe.tbm

BDS generated without error (Y/N):
BDS error message (if any):

STEP body list:
```
(paste here)
```
Number of bodies in STEP:

Dimension table:
| Quantity | Value (mm) | Notes |
|---|---|---|
| JR OD | | |
| Mandrel OD | | |
| Can inner diameter | | |
| Can outer diameter | | |
| Can total height | | |
| JR total height | | |
| JR-top to Can-top distance | | |
| JR-bottom to Can-bottom distance | | |

Notes:

---

## CEN-A — GC_CEN_A_mandrel_zero.tbm

BDS generated without error (Y/N):
BDS error message (if any):

STEP body list:
```
(paste here)
```
Number of bodies in STEP:

**Mandrel presence (choose one):**
- [ ] ABSENT — no Mandrel body in STEP
- [ ] PRESENT, REDUCED — Mandrel body present, OD smaller than T06 6 mm
- [ ] PRESENT, UNCHANGED — Mandrel body present, OD unchanged at ~6 mm

Dimension table:
| Quantity | Value (mm) | Notes |
|---|---|---|
| JR OD | | |
| Mandrel OD | | write ABSENT if no Mandrel body |
| Can inner diameter | | |
| Can outer diameter | | |
| Can total height | | |
| JR total height | | |
| JR-top to Can-top distance | | |
| JR-bottom to Can-bottom distance | | |
| JR inner void diameter (if Mandrel absent, is JR solid to axis?) | | write SOLID if no central void |

Notes:

---

## General

BDS version confirmed (Y/N):
Any case that could not be generated (list case IDs and reasons):
Anything unexpected across any case:
