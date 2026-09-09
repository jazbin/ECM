# STAR-CCM+ TBM Battery Simulation — Project Context

**Last updated: 2026-09-09**

---

## 1. What we are doing and why

The original project produced an OpenFOAM ↔ ECM (external electrochemical model) coupling framework for battery thermal simulation. That setup delivered a distributed (element-wise) electrothermal simulation of a 2170 cylindrical cell: the jelly-roll was partitioned into axial × radial zones, each zone exchanged temperature with an independent Python ECM instance that returned a volumetric heat source (qVol, W/m³). This gave spatially resolved heat generation across the cell.

The client pivot: Robert (end client) needs the same distributed electrothermal result delivered as a **pure STAR-CCM+ native simulation** — no OpenFOAM, no Python backend, no external coupling. STAR-CCM+ has its own native distributed battery solver that takes a TBM file as input and runs electrochemistry and thermal physics together inside STAR-CCM+. The goal is to reproduce, or closely approximate, the OpenFOAM-ECM distributed result using this native route. The spatial discretisation will differ (STAR-CCM+'s internal element-wise partitioning vs the OpenFOAM-ECM axial × radial zone scheme), but the physics should be equivalent.

---

## 2. Roles

| Party | Role |
|---|---|
| About-Energy (Miles) | Supplies electrochemical and thermal characterisation data: OCV curves, RCR (equivalent-circuit) tables, thermal conductivity, heat capacity. Same data that was used for the OpenFOAM-ECM coupling. Does NOT supply TBM files. |
| Bojan / this workspace | Creates TBM files from the About-Energy characterisation data, by editing Siemens stock template TBMs. Also responsible for geometry correctness, electrochemical table population, and all QA before delivery. |
| Robert (end client) | Receives our TBM files, imports them into STAR-CCM+ ("Create from Tbm"), and runs STAR-CCM+'s native distributed battery simulation. |

About-Energy does not know about STAR-CCM+ or TBM files — they characterise the cell and hand over tables. We do the translation.

---

## 3. The cell

**2170 cylindrical lithium-ion cell** (NCA chemistry, AboutEnergy characterisation).

| Parameter | Value | Source |
|---|---|---|
| External diameter | 21.09 mm | `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md` |
| External height | 70.02 mm | same |
| Can wall thickness | 0.2313 mm | same |
| Can internal diameter | 20.627 mm | derived: 21.09 − 2 × 0.2313 |
| Jelly-roll active height | 65.11 mm | same (negative electrode collector width) |
| Nominal capacity | 5 Ah | `python/params.csv` (`Qnom_Ah`) |
| Mandrel diameter | 6 mm | TBM source |
| Tab orientation | Both on top (same-face) | confirmed with Miles 2026-09-03 |

The cell regions that map to OpenFOAM are: jellyRoll (active zone), shell (can), cap (top end). There is no bottom end-plate in the target STAR-CCM+ geometry — the can base is a clean sealed steel face, consistent with the dual-top-terminal configuration.

---

## 4. How we create TBM files

We do not have Battery Design Studio (BDS) installed in this environment. We create TBM files by:

1. Taking a Siemens stock 18650 template TBM as a base.
2. Replacing the electrochemical content (OCV curves, RCR table) with About-Energy's characterisation data for the 2170.
3. Correcting the physical geometry fields (package dimensions, jellyroll dimensions, electrode widths) for the 2170 target.

**The source file for all current work is `out/hp2170NCA-ECM.tbm`.** This file was built from a Siemens stock template and populated with About-Energy's data. It is not supplied by About-Energy.

The generation script `tools/generate_tbm_test_variants.py` reads `out/hp2170NCA-ECM.tbm` and applies fixes to produce the test variant files. The production TBM will eventually be produced the same way, with all geometry fields corrected.

---

## 5. TBM file structure relevant to this project

A TBM file contains two main categories of data:

**Electrochemical / thermal characterisation** — from About-Energy:
- OCV curves (insertion / de-insertion equilibrium data for anode and cathode)
- RCR table (`RCRTable 3D` block): 3 temperature sets at 288.15 K / 298.15 K / 308.15 K, 7 SOC points each. Fields: `Set[N]_RCR_V_SOC`, `_V_Ro` (R0), `_V_Rp` / `_V_tau` (R1·C1), `_V_Rp1` / `_V_tau1` (R2·C2), `Set[N]_m_dT`.
- Thermal conductivity, heat capacity, entropy (dU/dT)

**Geometry / winding parameters** — our responsibility to set correctly:
- `Package` block: external and internal can dimensions
- `<BUILDER>` / Detailed Builder block: jelly-roll winding geometry (jellyroll diameter, mandrel diameter/width, electrode overlap at start/end, electrode collector width = axial height, separator feed/tail lengths, number of spokes)
- Tab geometry: `m_bNegTab`, `m_bPosTab`, `m_nNegTabVertOrientation` (0 = top, 1 = bottom), `m_nPosTabVertOrientation`

**Key electrochemical mode flag**:
- `m_bOnly1D` — must be `0` for STAR-CCM+'s distributed 3D solver. The stock template we cloned had this set to `1` (1D-only mode), which BDS/STAR-CCM+ explicitly rejects when creating 3D geometry or running distributed physics. All our generated variants must set this to `0`.

---

## 6. Current state of `out/hp2170NCA-ECM.tbm` (source file)

### What is correct

- External package dimensions (`m_dextDiameter = 21.09`, `m_dextHeight = 70.02`)
- RCR electrochemical tables (3 sets, 288.15 / 298.15 / 308.15 K, from `python/params.csv`)
- OCV curves (from About-Energy characterisation)
- Mandrel thickness (`m_dMandrelThickness_mm = 6`)
- Electrode collector widths: positive = 64.11 mm, negative = 65.11 mm (axial heights)
- Mandrel flat flag (`m_bMandrelFlat = 0`, correct for cylindrical mandrel)
- Tab orientation: `m_nPosTabVertOrientation = 0` (top, correct)

### What is wrong / not yet fixed in the source file

These are fixed by the generate script for the test variants but the source file itself retains the original values:

| Field | Source value | Correct value | Fixed in script? |
|---|---|---|---|
| `Package m_dintDiameter` | 17.8 mm | 20.627 mm (can ID) | Yes |
| `Package m_dintHeight` | 60 mm | 65.11 mm (jelly-roll height) | Yes |
| `Package m_strName` | 18650 | 2170 | Yes |
| `m_dElectrodeOverlapAtStart_mm` | 0 | 8 mm (copied from Simple Builder) | Yes |
| `m_dMandrelWidth_mm` | 0 | 6 mm (= mandrel thickness, cylindrical) | Yes |
| `m_bOnly1D` | 1 | 0 | Yes (added v3) |
| `m_nNegTabVertOrientation` | 1 (bottom) | 0 (top, same-face) | Yes (variant-dependent) |

### What is still open (not yet addressed by the script)

- **`m_dJellyrollThickness_mm = 19.25`** — this is the jelly-roll outer diameter. It should be ~20.627 mm (= can ID) to make contact with the can. Current value leaves a ~1.4 mm radial gap. Not yet fixed in the generate script.
- **`m_dAhCell = 0`, `m_bSpecifyCapacity = 0`** — capacity is not explicitly specified; BDS will derive it from electrode geometry. With the geometry still partially stock-18650-derived, the derived capacity may be wrong.
- **Separator and electrode overlap at end** — `m_dSepFeedLength_mm = 0`, `m_dSepTailLength_mm = 0`, `m_dElectrodeOverlapAtEnd_mm = 20` — not yet validated against About-Energy data or a 2170 reference.
- **`DataSheet m_dDSHeight = 65`** — should probably be 70.02 mm (full can height) or 65.11 mm (active height); inconsistent.

---

## 7. The geometry test (current work)

Before committing to a production TBM, we are running a geometry inspection test. The goal is to confirm that STAR-CCM+'s "Create from Tbm" generates a topology that matches the OpenFOAM geometry: **JellyRoll + Can + top EndPlate only** (no EndPlate at the bottom, consistent with dual-top terminal and the OF jellyRoll / shell / cap regions).

The test uses four variants that isolate two unknowns — whether tabs are on or off, and whether the negative tab is on top (same-face) or bottom (standard) — to see how each combination affects what parts BDS generates.

| Variant | Tabs | Neg orientation | Key question |
|---|---|---|---|
| V1 | ON | Standard (neg=bottom) | Full component list — what does BDS generate by default? |
| V2 | OFF | Standard | Does suppressing tabs remove the bottom EndPlate? |
| V3 | ON | Same-face (neg=top) | Does same-face move the EndPlate to top? |
| V4 | OFF | Same-face | **Target config**: bottom clean, top only? |

Robert's job for this test: import each TBM → "Create from Tbm" → export to STEP → send back 4 STEP files. We then analyse the topology. He does not run any physics for this test.

### Geometry test package history

| Package | Date | SHA-256 | What was fixed |
|---|---|---|---|
| v1 (`tbm_geometry_test_20260904.zip`) | 2026-09-04 | — | Initial attempt |
| v2 (`tbm_geometry_test_20260907.zip`) | 2026-09-07 | `e3abefda...` | `m_dElectrodeOverlapAtStart_mm` 0→8 (fixed "Extrusion distance = 0" error); `m_dMandrelWidth_mm` 0→6 |
| v3 (`tbm_geometry_test_20260909.zip`) | 2026-09-09 | `127079ad...` | `m_bOnly1D` 1→0 (fixed "m_bOnly1D option is not supported" failure) |

**Current package for Robert: v3** (`out/tbm_geometry_test_20260909.zip`)

Variant SHA-256s (v3):
- V1 (tabs-on-standard): `cae78b4d...`
- V2 (tabs-off-standard): `9f388fdf...`
- V3 (tabs-on-sameFace): `e03d2eaf...`
- V4 (tabs-off-sameFace): `9a973f4d...`

---

## 8. Open questions

1. **Geometry test result** — awaiting Robert's 4 STEP files to confirm topology.
2. **Jelly-roll diameter** — `m_dJellyrollThickness_mm = 19.25` needs to be corrected to ~20.627 mm before production TBM. Confirm what the correct value is from About-Energy or cell datasheet.
3. **Electrode overlap at start** — 8 mm was copied from the Simple Builder block in the source TBM. Miles to confirm this is correct per the electrode design spec.
4. **Capacity specification** — whether to explicitly set `m_bSpecifyCapacity = 1` / `m_dAhCell = 5` or allow BDS to derive it from electrode geometry. If geometry is not fully correct, explicit specification is safer.
5. **Distributed discretisation equivalence** — once the geometry test passes and a production TBM is running in STAR-CCM+, a quantitative comparison against the OpenFOAM-ECM distributed results is needed to confirm equivalence.

---

## 9. Key files

| Path | Purpose |
|---|---|
| `out/hp2170NCA-ECM.tbm` | Source TBM (partially corrected from stock 18650, electrochemistry from About-Energy) |
| `out/test/hp2170-test-v{1..4}-*.tbm` | Current geometry test variants (v3) |
| `out/tbm_geometry_test_20260909.zip` | v3 package for Robert |
| `tools/generate_tbm_test_variants.py` | Script that applies fixes and generates all 4 variants from the source TBM |
| `tools/translate_tbm_from_openfoam.py` | Script used to populate the RCR/OCV electrochemical tables from About-Energy / OpenFOAM data |
| `python/params.csv` | About-Energy characterisation data (R0, R1, C1, R2, C2, OCV vs SOC at 3 temperatures) |
| `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md` | 2170 cell physical dimensions reference |
| `BDS_files/_Projects/HE18650/he18650spiral1.tbm` | Siemens stock HE18650 reference TBM (no m_bOnly1D field; used as geometry reference) |
| `artifacts/reports/TBM_CELL_GEOMETRY_FINDINGS_RevA_20260812.pdf` | Controlled PDF report documenting the original geometry mismatch findings (2026-08-12) |
