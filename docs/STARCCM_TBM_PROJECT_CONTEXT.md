# STAR-CCM+ TBM Battery Simulation — Project Context

**Last updated: 2026-09-09**

This file is a synchronized copy of the canonical root-level `STARCCM_TBM_PROJECT_CONTEXT.md`; it also carries the repository-forensics appendix. Factual statements in both files must remain aligned.

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

The cell regions that map to OpenFOAM are: jellyRoll (active zone), shell (can), and cap (top end). The physical target may use a dual-top-terminal configuration, while STAR/BDS generated components may have solver or electrical semantics. The objective is equivalent cell-level and distributed electrothermal response within defined validation tolerances; STAR internal topology and discretization do not need to match the OpenFOAM representation one-to-one.

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
- `m_bOnly1D` — the current package variants use `0` in all four SIMMOD blocks, including the active RCRTable 3D block. The repository documents an import warning for some `1` values, but the exact STAR/BDS semantics by SIMMOD context remain unconfirmed.

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
| `m_bOnly1D` | 1 | 0 | Yes (added in package_rev3) |
| `m_nNegTabVertOrientation` | 1 (bottom) | 0 (top, same-face) | Yes (variant-dependent) |

### What is still open (not yet addressed by the script)

- **`m_dJellyrollThickness_mm = 19.25`** — current value. The 2026-08-31 STEP characterization established that this Detailed Builder field drives realized JR diameter, while the tested Simple Builder and REPORT JR diameter fields were not observed to drive it. The can ID is 20.6274 mm, giving a 1.3774 mm diametral difference. The correct physical 2170 JR OD remains unresolved; 20.6274 mm is a geometric upper bound/cavity ID, not a proven winding OD. See `tbm_validation/GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md`.
- **Active `RCRTable 3D` capacity** — machine extraction verifies `m_bSpecifyCapacity = 1` and `m_dAhCell = 5.0`. The remaining question is whether STAR interprets and uses the 5 Ah override as intended and whether geometry-derived quantities remain internally consistent.
- **Separator and electrode overlap at end** — `m_dSepFeedLength_mm = 0`, `m_dSepTailLength_mm = 0`, `m_dElectrodeOverlapAtEnd_mm = 20` — not yet validated against About-Energy data or a 2170 reference.
- **`DataSheet m_dDSHeight = 65`** — should probably be 70.02 mm (full can height) or 65.11 mm (active height); inconsistent.

---

## 7. Geometry characterization and current package-specific test

The 2026-08-31 STEP characterization is complete for field-dependency and feasibility behavior. It tested 21 variants, received 19 STEP files plus one documented geometry-creation failure, and analyzed 20 successful variants. Detailed Builder jelly-roll diameter was consumed; the tested REPORT and Simple Builder JR diameter fields were not observed to be consumed; all 20 successful variants had zero JellyRoll∩Can and JellyRoll∩Mandrel intersection volume. This establishes the relevant STAR field behavior but does not prove the correct physical 2170 winding OD.

Before committing to a production TBM, we are running a geometry inspection test. The test may inspect parts and topology, but the production objective is equivalent cell-level and distributed electrothermal response within defined validation tolerances. It does not require STAR/BDS to reproduce **JellyRoll + Can + top EndPlate only** one-to-one, and absence of a bottom EndPlate is not a production requirement without Siemens-model evidence.

The test uses four variants that isolate two unknowns — whether tabs are on or off, and whether the negative tab is on top (same-face) or bottom (standard) — to see how each combination affects what parts BDS generates.

| Variant | Tabs | Neg orientation | Key question |
|---|---|---|---|
| variant_1 | ON | Standard (neg=bottom) | Full component list — what does BDS generate by default? |
| variant_2 | OFF | Standard | How does suppressing tabs affect generated components? |
| variant_3 | ON | Same-face (neg=top) | How does same-face tab placement affect generated components? |
| variant_4 | OFF | Same-face | How does the tab-off same-face case affect generated components? |

Robert's job for this test: import each TBM → "Create from Tbm" → export to STEP → send back 4 STEP files. We then analyse the topology. He does not run any physics for this test.

### Geometry test package history

| Package | Date | SHA-256 | What was fixed |
|---|---|---|---|
| package_rev1 (`tbm_geometry_test_20260904.zip`) | 2026-09-04 | — | Initial attempt |
| package_rev2 (`tbm_geometry_test_20260907.zip`) | 2026-09-07 | `e3abefda...` | `m_dElectrodeOverlapAtStart_mm` 0→8 (addressed the reported extrusion-distance error); `m_dMandrelWidth_mm` 0→6 |
| package_rev3 (`tbm_geometry_test_20260909.zip`) | 2026-09-09 | `127079ad...` | `m_bOnly1D` 1→0 (addressed the reported import warning) |

**Current package for Robert: package_rev3** (`out/tbm_geometry_test_20260909.zip`)

Variant SHA-256s (package_rev3):
- variant_1 (tabs-on-standard): `cae78b4d...`
- variant_2 (tabs-off-standard): `9f388fdf...`
- variant_3 (tabs-on-sameFace): `e03d2eaf...`
- variant_4 (tabs-off-sameFace): `9a973f4d...`

---

## 7b. Forensic validation repository (jazbin/ECM on GitHub)

A complete forensic handoff has been pushed to the `jazbin/ECM` GitHub repository for independent review. This was created on 2026-09-09 to enable static inspection of all TBM files and generation scripts before the next client package.

**GitHub repo:** `https://github.com/jazbin/ECM`

| Path in repo | Contents |
|---|---|
| `tbm_validation/source/` | All source TBMs (byte-exact, unmodified) |
| `tbm_validation/variants/v{1,2,3}_package_*/` | All 4 variants from each client package |
| `tbm_validation/reference/` | Siemens stock reference TBMs (HE18650, HP18650, GapExample, CompareChem) |
| `tbm_validation/in_StarCCM_bds/` | TBMs from STAR-CCM+ installation |
| `tbm_validation/TBM_INVENTORY.md` | SHA-256 for every TBM; provenance, status, known issues |
| `tbm_validation/STAR_IMPORT_ERROR_HISTORY.md` | Every known STAR import failure: exact TBM hash, verbatim error, diagnosis, fix |
| `tbm_validation/TBM_STRUCTURAL_COMPARISON.md` | Field-by-field comparison vs HE18650 and HP18650 references |
| `tbm_validation/CURRENT_TBM_FIELD_AUDIT.md` | Every important field: VERIFIED/ASSUMED/UNKNOWN classification, risk ranking |
| `tbm_validation/DOCUMENTATION_INDEX.md` | Index of Siemens/AE/cell reference docs with relevant sections for each open question |
| `tbm_validation/PRE_CLIENT_RELEASE_CHECKLIST.md` | Checklist + confidence state machine (STATIC_PASS / STAR_IMPORT_PASS / PHYSICS_PASS) |
| `tools/validate_tbm.py` | Independent static validator; run before every send |
| `tools/generate_tbm_test_variants.py` | TBM variant generator |
| `tools/translate_tbm_from_openfoam.py` | Electrochemistry table populator |
| `data/python_params.csv` | About-Energy characterisation data snapshot |
| `data/README_data.md` | Explanation of all data files and TBM pipeline |
| `docs/STARCCM_TBM_PROJECT_CONTEXT.md` | This document |

**Static validator — current package results:**
Source TBM (`hp2170NCA-ECM.tbm`): 1 FAIL, 11 WARN — correctly captures every known issue.
All package_rev3 variants: **0 FAIL, 11 WARN**. All package_rev4_candidate variants: **0 FAIL, 4 WARN**. These are current corrected-validator totals.

**STAR-CCM+ version:** Not confirmed from Robert. Field interpretation may vary.
**BDS version:** Not confirmed from Robert.

---

## 8. Open questions

1. **Package-specific geometry test result** — awaiting the four `package_rev3` STEP files to confirm the topology and tab variants. This is separate from the completed August field-dependency characterization.
2. **Jelly-roll diameter** — current `m_dJellyrollThickness_mm = 19.25`; can ID is 20.6274 mm and the diametral difference is 1.3774 mm. Confirm the correct physical JR OD and the STAR meaning of this field from Siemens-model evidence, cell teardown, or an applicable datasheet. Do not assume the JR OD must equal the can ID.
3. **Electrode overlap at start** — 8 mm was copied from the Simple Builder block in the source TBM. Miles to confirm this is correct per the electrode design spec.
4. **Capacity specification** — the active RCRTable 3D block currently explicitly sets `m_bSpecifyCapacity = 1` / `m_dAhCell = 5.0`. Confirm STAR interpretation and consistency with geometry-derived quantities.
5. **Distributed discretisation equivalence** — once the geometry test passes and a production TBM is running in STAR-CCM+, a quantitative comparison against the OpenFOAM-ECM distributed results is needed to confirm equivalence.

---

## 9. Key files

| Path | Purpose |
|---|---|
| `out/hp2170NCA-ECM.tbm` | Source TBM (partially corrected from stock 18650, electrochemistry from About-Energy) |
| `out/test/hp2170-test-v{1..4}-*.tbm` | Current geometry test variants (package_rev3) |
| `out/tbm_geometry_test_20260909.zip` | package_rev3 for Robert |
| `tools/generate_tbm_test_variants.py` | Script that applies fixes and generates all 4 variants from the source TBM |
| `tools/translate_tbm_from_openfoam.py` | Script used to populate the RCR/OCV electrochemical tables from About-Energy / OpenFOAM data |
| `tools/validate_tbm.py` | **Independent static validator — run before every send** |
| `python/params.csv` | About-Energy characterisation data (R0, R1, C1, R2, C2, OCV vs SOC at 3 temperatures) |
| `docs/WEDGE_2170_BATTERY_CELL_THERMAL_PROPERTIES_REFERENCE.md` | 2170 cell physical dimensions reference |
| `BDS_files/_Projects/HE18650/he18650spiral1.tbm` | Siemens stock HE18650 reference TBM; machine extraction finds `m_bOnly1D = [1, 0, 0, 0]` |
| `artifacts/reports/TBM_CELL_GEOMETRY_FINDINGS_RevA_20260812.pdf` | Controlled PDF report documenting the original geometry mismatch findings (2026-08-12) |

**Distinction: geometric topology vs electrothermal equivalence.** The pending geometry test will document the parts and topology STAR-CCM+ generates from each package variant. That observation is necessary but not sufficient for electrothermal equivalence. The spatial discretisation in STAR-CCM+'s distributed solver differs from the OpenFOAM-ECM axial × radial zone scheme. A separate quantitative validation step (temperature, heat generation profiles vs OpenFOAM-ECM results at same boundary conditions) is required before the TBM is declared an equivalent replacement.
