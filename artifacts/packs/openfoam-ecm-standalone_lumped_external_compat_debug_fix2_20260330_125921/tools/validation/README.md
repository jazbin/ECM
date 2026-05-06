# Validation scripts

This folder provides lightweight scripts to compare simulation outputs against
open datasets. The first target is the TU Berlin 21700 dataset.

## TU Berlin: V0–V2 comparison

`tu_berlin_validate.py` computes voltage and temperature errors by comparing
simulation outputs against a chosen dataset CSV (either extracted or accessed
directly from the ZIP).

Expected simulation CSV columns (case-insensitive):
- time (seconds)
- voltage (V)
- T_core or T_inner (degC)
- T_surf or T_outer (degC)

Example:
```
python3 tools/validation/tu_berlin_validate.py \
  --zip externalInputs/datasets/berlin_2026_bitstream_ae2d5a48.zip \
  --member 1_split/AM23NMC00103/AM23NMC00103_std_05deg/1_BCDC_AM23NMC00103_05deg_raw.csv \
  --sim /path/to/simulation_outputs.csv \
  --out /tmp/tu_berlin_metrics.csv
```

## Khan (OSF) dataset

The Khan dataset is distributed as CSVs inside a ZIP. Use `--zip` and `--member`
to select the desired file. This dataset provides voltage and current but no
temperature probes.

Example:
```
python3 tools/validation/khan_validate.py \
  --zip externalInputs/datasets/khan_2025_osf_Dataset_Molicell_P42A.zip \
  --member Dataset_Molicell_P42A/phase_1/20231212_A10_Cby3_Pulse_D2_CD2.csv \
  --sim /path/to/simulation_outputs.csv \
  --out /tmp/khan_metrics.csv
```

## Stanford/Mendeley 2021 dataset

The Stanford dataset is provided as XLSX files with columns such as
`Test_Time(s)`, `Voltage(V)`, and `Surface_Temp(degC)`.

Example:
```
python3 tools/validation/stanford_validate.py \
  --xlsx externalInputs/datasets/stanford_2021_mendeley/72b6cf9c-0f71-438f-878f-ae1b6863b533_NMC_k5_0_05C_35degC.xlsx \
  --sim /path/to/simulation_outputs.csv \
  --out /tmp/stanford_metrics.csv
```
