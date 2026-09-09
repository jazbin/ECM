# Data Files — README

This directory contains the About-Energy characterisation data used to populate the electrochemical content of our 2170 TBM files. All files are copies from the main workspace (`/workspace/python/` and `/workspace/`). The originals remain the authoritative versions; these copies exist to give a self-contained forensic snapshot at the time of the TBM generation.

---

## `python_params.csv`

**Source:** `python/params.csv` in the main workspace
**Purpose:** About-Energy electrochemical characterisation data for the 2170 NCA cell. This is the primary input to `tools/translate_tbm_from_openfoam.py`.

**Columns:**
| Column | Units | Description |
|---|---|---|
| `Q_Ah` | Ah | State of charge (capacity discharged, 0 = fully charged) |
| `T_degC` | °C | Temperature |
| `E_OCV_dch_V` | V | Open-circuit voltage on discharge |
| `E_OCV_ch_V` | V | Open-circuit voltage on charge |
| `R0_Ohm` | Ω | Ohmic resistance (R0) |
| `R_Ohm_1` | Ω | First RC pair resistance (R1) |
| `C_F_1` | F | First RC pair capacitance (C1); τ1 = R1·C1 |
| `R_Ohm_2` | Ω | Second RC pair resistance (R2) |
| `C_F_2` | F | Second RC pair capacitance (C2); τ2 = R2·C2 |
| `gamma` | — | Entropic heat coefficient scaling parameter |
| `dUdT` | V/K | Entropy coefficient (dU/dT) for reversible heat |

**Structure:** 3 temperature points (15°C / 25°C / 35°C) × 7 SOC points = 21 rows.

**TBM translation:**
- R0, R1, C1, R2, C2 → `RCRTable 3D` SIMMOD block (`Set[N]_RCR_V_Ro`, `_V_Rp`, `_V_tau`, `_V_Rp1`, `_V_tau1`)
- E_OCV_dch_V, E_OCV_ch_V → OCV equilibrium curves in the electrochemistry blocks
- dUdT → entropic heat term

**Cell identifier fields in params.csv:**
- `Qnom_Ah = 5.0` — nominal capacity (used to set capacity in TBM)
- `C_rate_1h = 5.0` A — 1C rate

---

## `cellprops.csv`

**Source:** `cellprops.csv` in the main workspace root
**Purpose:** Physical (thermal) properties of the 2170 cell: density, specific heat capacity, thermal conductivity. Used for region-level properties in STAR-CCM+ or OpenFOAM cases.

**Contents:** Density (kg/m³), cp (J/kg·K), k_radial and k_axial (W/m·K) for jellyRoll, shell, cap regions.

**TBM usage:** Cell-level thermal properties (heat capacity, thermal conductivity) should be cross-checked against these values when populating `m_dDensity`, `m_dHeatCapacity`, `m_dThermalConductivity` fields in the TBM electrochemistry blocks. Whether the current source TBM uses these values or the stock 18650 values is UNVERIFIED — this is an open audit item.

---

## `cellprops_root.csv`

**Source:** Root of main workspace (`/workspace/cellprops.csv` root copy if different)
**Purpose:** May be an alternate or earlier version of `cellprops.csv`. Retained for provenance. Inspect both files if they differ in SHA-256.

---

## Relationship to TBM generation pipeline

```
python/params.csv
       ↓
tools/translate_tbm_from_openfoam.py
       ↓ (populates electrochemical tables)
out/hp2170NCA-ECM.tbm   ← source TBM (electrochemistry from AE, geometry partially stock 18650)
       ↓
tools/generate_tbm_test_variants.py
       ↓ (applies geometry fixes + tab/orientation variants)
out/test/hp2170-test-v{1..4}-*.tbm   ← test variant TBMs
       ↓
out/tbm_geometry_test_20260909.zip   ← client package v3
```

The `translate_tbm_from_openfoam.py` script reads `params.csv` and writes the RCR and OCV sections into the TBM. The `generate_tbm_test_variants.py` script reads the resulting source TBM and applies geometry corrections + variant-specific tab settings.
