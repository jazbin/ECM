# Project Memory — ECM Coupler / OpenFOAM battery thermal (/workspace)

> This file lives in the repo. Claude should read and update it each session.
> The global ~/.claude auto-memory file redirects here.
>
> **SESSION CLOSE RULE**: When the user writes "close session" (or any variant),
> ALWAYS write the session log to `artifacts/logs/session_YYYYMMDD_HHMMSS.log`
> BEFORE acknowledging. No exceptions. This is the FIRST thing to do on close.

---

### HARD RULE — NO AGENTS IN THIS WORKSPACE
Never spawn Agent tool calls in /workspace. Do all work directly with Read/Edit/Bash/Grep/Glob. Use `cp` for file sync, not agents.

---

### Session 2026-07-07 (3) — ecm_mapping.csv blending absent (stale uniform-weight file)

- **Symptom:** STAR-CCM+ mesh cells between ECM zone boundaries showed no blending.
- **Root cause:** `in/testedVersion/ecm/ecm_mapping.csv` was generated from an old
  `ecm_cell_map.csv` without the `volume_m3` column → `gen_ecm_mapping.py` used uniform
  weight (3.017e-10 m³, half=0.333 mm) → too small to detect boundary cells →
  0 multi-zone rows → no blending.
- **Root cause (code bug):** `_maybe_regen_mapping()` in `ecm_coupler.py` had NO stale
  check. In file-based mode (new Python process per step), `_REGEN_CHECKED` is empty on
  every process start → the function ran on every coupling step → always overwrote the
  blended mapping from `gen_ecm_mapping.py` with a simplified no-blending version
  (ignores `volume_m3` column, always uses uniform weight, one row per cell).
- **Code fix:** added stale check in `_maybe_regen_mapping()` — compares unique meshKey
  count in existing mapping to row count in `ecm_cell_map.csv`. If equal (no remesh),
  returns immediately, preserving the blended mapping. Only regenerates on actual cell-
  count change (remesh). Synced to all 3 copies.
- **Diagnostic:** `awk -F, 'NR>1 {c[$1]++} END {for(k in c) if(c[k]>1) m++; print m+0}' ecm_mapping.csv`
  → 0 means no blending (bad); >0 means blending is present.
- **Prevention going forward:** after any remesh, Java macro runs `gen_ecm_mapping.py`
  (blended mapping produced); Python's `_maybe_regen_mapping()` now detects the new cell
  count (≠ old mapping) → regenerates → blended result from `gen_ecm_mapping.py` is
  expected to have been run already by the Java macro.
- `in/starCCM_10C_experiment_twoCells_distributed/ecm/ecm_mapping.csv` was already
  correct (7,611 / 30,131 boundary cells) — no action needed there.

### Session 2026-07-07 (2) — Fix 8: post-remesh coord mismatch + reload CSV cleanup

- **Post-remesh failure (54/78231 rows unmatched):** After remesh 22162→78231 cells, first macro attempt FATAL at step 0. Root cause: `getSeriesArray()` returns slightly different fp values on first extract() after remesh vs subsequent extractions. 54 cells straddle a 0.1mm hash-bin boundary, so startup coordinates and step-0 coordinates hash differently.
- **Fix 8a:** Added `builtFromXyzTableOrder = true` flag to `CellMapper` when built via `createFromXyzTable()`. `buildTableToMapperMapping()` now returns identity `[0,1,...,N-1]` when this flag is set (T-table row order IS mapper cell order). Avoids fp re-comparison entirely. Flag cleared after first use.
- **Fix 8b (CSV accumulation):** `writeQVolReloadCsv()` was creating `ecm_qvol_injection_reload_XXXXXX_YYYYY.csv` per coupling step with no cleanup. After a 78-step run, 78 files accumulated. Fix: added `prevReloadCsv` field; delete prev file after each successful `extract()`. Added startup cleanup: scan and delete all `ecm_qvol_injection_reload_*.csv` files at startup, reset `qTableReloadSerial=0`.
- **autoConfigureJellyRollEnergySource non-fatal:** `CoupledSolidEnergyModel` in 2602 has ZERO heat-source getter methods (only setImplicit, getSecondaryGradients, etc). Full model scan shows 9 models, none have VolumetricHeatSourceProfile. Heat IS applied correctly because user configured energy source manually in STAR GUI. The WARN is noisy but non-blocking — simulation runs correctly.
- **Copies synced:** all 4 copies. CODE_SUMMARY updated.

### Session 2026-07-07 — Fix 7: T-table Parts-based regionIdx (7-cell distributed)

- **Root cause diagnosed:** `computeRegionIndicesFromFvRep` failed (all 3 API paths → `Region.getCellCount()` NoSuchMethod). k-means fallback used instead → Voronoi boundary bleeding between adjacent cylindrical cells → cell counts 2752–3615 (±13%) → radial extents up to 25 mm (expected ≤10.85 mm).
- **Fix 7:** `computeRegionIndicesFromTableParts()` — new SOLE method for multi-region regionIdx. Temporarily restricts the T-table to each Part one at a time → `extract()` + `getRowCount()` → exact per-region row counts, no k-means. Parts not in coupled-regions list are skipped (offset still tracked). Throws with clear diagnostic if any coupled region is missing from the Parts list. No fallbacks — k-means and FvRep removed from `buildMergedCellMapper()`.
- **PCA axis issue also confirmed:** 3/7 regions had wrong PCA axes (Y/X dominant instead of Z). Consensus correctly recovers ≈Z. New `computeRegionIndicesFromTableParts` makes PCA axis purely a geometry annotation issue (not a cell-assignment issue).
- **Active copies:** `starccm_plugin/src/`, `starccm_plugin/package/src/`, `in/testedVersion/src/`, `in/starCCM_10C_experiment_twoCells_distributed/src/`
- CODE_SUMMARY.md updated (fix 7).

### Session 2026-07-06 (7) — Full continuum-model scan (fix 6)

- **Root cause confirmed:** `SegregatedSolidEnergyModel` has ZERO methods matching any of our keywords (`heat`, `source`, `volumetric`, `profile`, `energy`, `user`). The heat-source profile is on a DIFFERENT model in the physics continuum (likely `UserVolumetricHeatSourceModel` or similar).
- **Fix 6:** `autoConfigureJellyRollEnergySource` now falls through to scan ALL models via `phys.getModelManager().getClass().getMethod("getObjects")` after the energy-model attempt fails. Each model is tried with each profile getter. On success: logs "Profile found on model: <classname> via <getter>". On failure: logs full model list.
- **DIAG-1 upgraded:** now also dumps ALL methods (unfiltered) on `SegregatedSolidEnergyModel` AND lists every continuum model with keyword-matched methods. This will identify the correct class+getter name after next run.
- **Next run:** check log for either "Profile found on model:" (fix worked) or DIAG-1 model list (need to add the new class name to getter list).
- Synced to all 3 copies. CODE_SUMMARY updated (fix 6).

### Session 2026-07-06 (6) — FileTable 1-row confirmed; verbose diagnostics added

- **"Imported 1 rows" is NOT just startup** — it appears after EVERY step. `setFileName()` alone with same relative path does NOT force a re-read in STAR 2602. Fix: call BOTH `setFileName()` AND `extract()` every step. Also added: file-size check before/after CSV write, `getRowCount()` reflection check on FileTable.
- **Energy source wiring failing** — `autoConfigureJellyRollEnergySource` fails: no method on `SegregatedSolidEnergyModel` matches keyword filter. Synced to all 3 copies. CODE_SUMMARY updated (fix 5).

### Session 2026-07-06 (4) — regionIdx k-means + REGION_NAME → "Cell" (7-cell pack)

- **Bug 1 (regionIdx=0 for N=7):** `computeRegionIndicesFromCentroids` has hardcoded `N=2` guard → always returns null for N=7. `computeRegionIndicesNearestCentroid` was listed in CODE_SUMMARY as PRIMARY but **was not implemented**. Fixed: implemented k-means spatial clustering (any N≥2, 150-iter, evenly-spaced init, sorted-output for determinism); wired into `buildMergedCellMapper` fallback chain after Y-bimodality.
- **`REGION_NAME` default changed from `"jellyRoll"` to `"Cell"`** — matches Cell_01…Cell_07 naming in 7-cell pack .sim file. Overridable via `ECM_REGION_PATTERN` env var.
- Synced to all 3 copies. CODE_SUMMARY updated.

---

### Session 2026-07-06 (3) — Heat=0 fix + regionIdx fix (STAR-CCM+ 2602, 7-cell sim)

- **Root cause 1 (heat=0):** `SegregatedSolidEnergyModel.getVolumetricHeatSourceProfile()` does NOT exist in STAR-CCM+ 2602. Fixed: replaced with reflection loop over 7 candidate getter names (`getVolumetricHeatSourceProfile`, `getUserVolumetricHeatSourceProfile`, `getVolumetricEnergyGenerationProfile`, `getHeatSourceProfile`, `getVolumetricHeatSource`, `getUserHeatSourceProfile`, `getEnergySourceProfile`). Also 3-name loop for setter (`setTabularXyzMethod`/`setTableXyzMethod`/`setXyzTabularMethod`). On all-fail: logs all available methods on the energy model for diagnosis.
- **Root cause 2 (all cells in region 0):** `FvRepresentation.getCellCount(Region)` and `getRegionCellCount(Region)` both absent in 2602 → `computeRegionIndicesFromFvRep` returns null for N=7 regions → fallback `computeRegionIndicesFromCentroids` only handles N=2 → all cells region 0. Fixed: third fallback `Region.getCellCount()` (no-arg, on Region directly).
- **"Imported 1 rows"** in log = STAR's first-load message for stub CSV at startup; subsequent extract() calls are silent. Not the root cause.
- Both fixes synced to all 4 copies. Next run will show whether a getter name matches (check log for `getter=` message) or will log available methods for final identification.

---

### Session 2026-07-06 (2) — EcmCouplerMacro compile fixes (STAR-CCM+ 2602)

- `star.common.ClientServerObject` removed from 2602 API — previous fix to `star.common.StarObject` was ALSO wrong (`StarObject` does not exist in `star.common`)
- **Correct fix (session 3)**: `ModelManager.getModel()` signature is `<T extends star.common.Model> T getModel(Class<T>)` → type bound must be `star.common.Model`
- Fixed: `Class<star.common.StarObject>` → `Class<star.common.Model>` at lines ~2389/2390 and ~2462/2463 in all 4 copies
- `TableManager.createTable(Class<T>)` deprecated → replaced with `createTable("FileTable")` (lines ~2162, ~2261)
- All 4 copies synced: `in/testedVersion/src/`, `starccm_plugin/src/`, `starccm_plugin/package/src/`, `in/starCCM_10C_experiment_twoCells_distributed/src/`
- `star.base.neo.ClientServerObject` still exists in 2602; `star.common.ClientServerObject` and `star.common.StarObject` do NOT
- `StarApiInspector.java` updated: added `star.common.Model`, `star.common.StarObject`, `star.base.neo.ClientServerObject`, coupled flow model classes, `star.base.neo` to scan packages — run this first before guessing API names

---

### Session 2026-07-06 — Client proposal PDF + Battery Assistant API

#### Integration proposal (client deliverable)
- LaTeX source: `tools/proposal/starccm_ecm_integration_proposal.tex`
- Final PDF: `artifacts/reports/starccm_ecm_integration_proposal_RevA_20260706.pdf`
- SHA-256: `9bbc35066c242d0b9d4fb9cf1eebc50f93b2fbdf3e58da4e2339248c00daf9b5`
- Three options: (1) TBM Generator [needs Battery Module], (2) Direct Setup Macro [RECOMMENDED, base license], (3) Full Pipeline [base license]
- tectonic 0.15.0 static binary at `/tmp/tectonic` — use for all future LaTeX compilation

#### Battery Assistant API confirmed (STAR-CCM+ 2602)
- Program name: **Battery Assistant** (`BatteryUIAssistant extends SimulationAssistant`)
- Requires **Battery Module license** — not included in base STAR-CCM+
- Key class: `star.battery.BatteryCellManager`
  - `createFromTbm(String tbmFile, List<BatteryCellBuildObject> objects)` — main TBM import
  - `getTBMFileDescription(String tbmFile)` → `BatteryCellImportDescription` — validate without importing
  - `importPartsAndcreateFromTbm(String, List<GeometryPart>, List<GeometryPart>)` — full import + post geometry
- `BatteryCell.importTBMFile(String)` / `reloadTbmFile(String)` / `exportTBMData(String)`
- Task hierarchy (Battery Assistant wizard):
  `Task00_CreateBatteryCell` → `Task00_00_ImportTBMFile` → `Task00_01_CreateNewCell`
  → `Task01_00_OverrideCellData` → `Task01_01_ElectricalGridResolution`
  → `Task01_02_CreateBatteryModule` → `Task02_00_ModuleConfiguration` → `Task02_01_ModuleLayout`
- Our Option 2 (Direct Setup Macro) bypasses all of this — builds .sim without Battery Assistant

#### Tool note
- `pdflatex`/`xelatex` not installed in this environment
- Use `/tmp/tectonic` (downloaded from GitHub releases, musl static binary) for LaTeX → PDF
- Command: `cd /tmp && ./tectonic <tex-file> --outdir <output-dir>`
- Downloads packages from relay.fullyjustified.net on first use (cached)
- UTF-8 ć: use `Vidovi\'c` (T1 + lmodern); em-dash: use `---` not Unicode `—`

---

## Next session TODO

0. **BDS — EcmBdsCompanion v1.1 ready (2026-07-05)**:
   - Compile fixes: `star.segregatedenergy.*` package; `createTable("star.common.FileTable")`
   - Detailed logging added: `ECM_BDS_VERBOSE=1` (stack traces + method/model listings); `ECM_BDS_LOG_FILE=<path>` (file mirror)
   - Step timing (ms) on every step; `listMethods(obj, filter)` + `listModels(phys)` helpers
   - Energy model search expanded: also tries CoupledSolidEnergyModel + CoupledEnergyModel → Step 5 now works on test sim too
   - Launch scripts: `starccm_plugin/run_bds_companion.bat` + `in/testedVersion/run_bds_companion.bat`
   - Expected result on waterDomain_twoCells_rev3.sim: 4/7 (checks 2–4 FAIL = no BDS cells, expected)
   - **NEXT: copy to Windows, run `run_bds_companion.bat`, confirm 4/7 on test sim; 7/7 on real BDS sim**
   - CreateMinimalBdsTestCase requires `batterysim` license — FATAL on current installation (expected)

1. **Build EcmCoSimPartner.exe** — never compiled. Run on Windows:
   `build.bat "C:\Program Files\Siemens\21.02.008\STAR-CCM+21.02.008"`
   from `starccm_plugin/cosim/`. See `starccm_plugin/cosim/README.md`.

2. **Anisotropic k in STAR-CCM+ .sim** — verify and correct AnisotropicThermalConductivityMethodWithValues setup in delivered .sim. Guide: STAR_CCM_ANISOTROPIC_THERMAL_CONDUCTIVITY_GUIDE.md.
3. **Validation temperature sweep (10–60 °C)** — lumped and element-wise cases. ~3–5 days.
4. **Cell-size scaling methodology document** (21700 → 4680). Writing task only. ~1–2 days.
5. **Element-wise baseline re-run** post impedance-network fix before sweep campaign.
6. **Verify pre-warm-up fix in STAR-CCM+** — run waterDomain_twoCells_rev3.sim, confirm no jump at t=0.02→0.04.

---

### CONFIRMED REQUIREMENT — BDS + Distributed ECM (2026-07-03)

Client requirement (Robert, end client): use BDS to generate and parametrise the cell,
AND run our custom distributed (element-wise) ECM coupling on the BDS-generated STAR case.

- BDS role: cell design, HPPC regression, OCV/RCR tables, .tbm → STAR
- Our distributed ECM role: axial×radial zone partitioning, per-zone T → Python ECM
  (impedance-network current distribution via parallel_2rc_step) → per-zone qVol injection
- NOT STAR's native ecell solver; NOT BDS/Simulink co-simulation
- Robert has no existing BDS workflow — we define it
- All electrical parameters from OUR measurements/tables — CONFIRMED (pre-meeting)
- BDS used for: cell design, geometry, .tbm → STAR mesh/region setup only
- EcmBdsCompanion: disable BDS heat only; no BDS parameter bridge needed
- Formally recorded in docs/PROJECT_PLAN.md and artifacts/logs/decision.log

---

### Session 2026-07-05 — EcmBdsCompanion compile errors + StarApiInspector

**Errors confirmed on STAR-CCM+ 2602.0001 win64:**
- `batterysim` module absent → `CreateMinimalBdsTestCase` exits FATAL (expected, graceful)
- `EcmBdsCompanion` two compile errors: `SegregatedSolidEnergyModel` and
  `SegregatedFluidTemperatureModel` not found (wrong/missing package in import `star.energy.*`)
- `TableManager.createTable(Class<T>)` is `[DEPRECATED]`

**Fix strategy: enumerate before patching.**
Created `StarApiInspector.java` (both copies). Run it first, paste output, then fix class names and method.

---

### Session 2026-07-04 — BDS macro compilation fix

`sim.get(Class.forName(...))` fails to compile because `Class.forName()` returns
`Class<?>` but `sim.get()` requires `Class<T extends ClientServerObject>`.

**Fix — double-cast pattern (applied to all 4 file copies):**
```java
Class<?> raw = Class.forName("star.battery.BatteryTool");
@SuppressWarnings("unchecked")
Class<star.base.neo.ClientServerObject> typed =
    (Class<star.base.neo.ClientServerObject>) (Class<?>) raw;
Object bt = sim.get(typed);
```
Files: `starccm_plugin/src/` and `in/testedVersion/` copies of both macros.
Macros still untested end-to-end on Windows — user needs to copy and re-run.

---

### Session 2026-07-03 — BDS integration macros written

#### Key discovery: BDS architecture
BDS (Battery Design Studio / Simcenter Battery Design Studio) is a **standalone tool**, NOT a STAR-CCM+ module.
- BDS co-simulates with MATLAB Simulink, not STAR-CCM+
- Workflow: BDS exports `.tbm` file → STAR-CCM+ imports `.tbm` → STAR creates `BatteryCellManager` tree
- No Siemens-supplied template .sim files for BDS integration exist
- Template `.tbm` location: `<BDS_INSTALL>/bin/templates/` and tutorial:
  `_Projects/Automatic_RCR_Regression_Tutorial/High_Power_18650_RCR.tbm`
- BDS docs live in `/workspace/BDS_docs/userguide_wrp/` (GUID-named HTML files)

#### Files created
- `starccm_plugin/src/EcmBdsCompanion.java` (~320 lines) — one-time POC diagnostic macro; 7 checks
- `starccm_plugin/src/CreateMinimalBdsTestCase.java` (~280 lines) — setup macro: adds BDS battery
  objects to existing .sim and saves as test_bds_case.sim
- `CODE_SUMMARY.md` updated with EcmBdsCompanion section

#### Both macros: reflection-only approach
All `star.battery.*` API calls use `Class.forName()` + `Method.invoke()` — no compile-time imports.
Graceful WARN if 'batterysim' license absent. Key API found in docs:
- `BatteryCellManager.createFromTbm(String, List<BatteryCellBuildObject>)`
- `BatteryCellManager.createUserDefinedBatteryCell()`
- `BatteryTool.getBatteryCellBuildObjectManager(CellModelForm)` — CellModelForm: BLOCK, CYLINDRICAL, PRISMATIC, SPIRAL
- `RCREquivalentCircuitBatteryCellDescription.getCellCapacity()` / `getInitialSOC()`
- `RCREquivalentCircuitBatteryCellDescription.extractRCRParametersFromTBMFile(String)`
- `RCREquivalentCircuitBatteryCellDescription.setUseEntropyTableEnabled(boolean)`
- `RCREquivalentCircuitBatteryCellDescription.setUseRelaxationHeatEnabled(HeatFlowTypeOption)`

#### EcmBdsCompanion 7 POC checks
1. BatteryCellManager found  2. RCR params read  3. Regions found  4. BDS heat disabled
5. Energy source → FileTable wired  6. VolumeAverageReport T in 200–500 K  7. Summary PASS/FAIL
Config env vars: ECM_REGION_PATTERN, ECM_Q_TABLE_NAME, ECM_Q_TABLE_CSV, ECM_PROJECT_ROOT

#### CreateMinimalBdsTestCase 5 steps
A: BatteryTool access  B: cell creation (Path A: createFromTbm; fallback: UserDefinedBatteryCell with capacity=5.05 Ah, SOC=1.0)
C: verify RCR  D: scan jellyRoll regions  E: saveSim to BDS_OUTPUT_SIM
Config env vars: BDS_TBM_FILE, BDS_OUTPUT_SIM, ECM_REGION_PATTERN

#### User workflow preference (confirmed this session)
**Do NOT use Agent tool** for searches — do all file reads/greps directly.
Reason: separate agent causes token cost to "skyrocket". Always do explorations in-line.

---

### Session 2026-07-02 — First-step qVol jump fixed in ALL coupling paths

**Root cause (session 1):** `iter.step(1)` runs BEFORE the ECM is called → step 1 always
uses stale `ecm_qvol_injection.csv` from prior run → jump at t=deltaT.
Initial fix (commit 24e985d) only covered `executeLumpedMultiRegion`.

**Remaining jump (session 2):** waterDomain test uses `elementWise` mode → `executeElementWise`
had NO pre-warm-up → still got 22780→28961 W/m³ jump (+27%) between step 1 and step 2.
The CSV was seeded with the previous STAR run's last ECM output (not IC-consistent).

**Final fix (commit 8e49504):** pre-warm-up block added to ALL three coupling paths:
- `executeElementWise()`: reads IC T via `tReport.getValue()`, calls ECM (stepId=0, deltaT=0),
  applies via `applyElementWiseHeatCsv()`, seeds `qVolPrev[]`.
- Inline lumped loop in `execute()`: same pattern using `buildLumpedInputBytes`.
- `executeLumpedMultiRegion()`: already fixed in 24e985d.
Guard: `freshStart` (continuation runs skip). All 5 copies synced.
Expected result: ~1-2% residual jump (from T change during first iter.step vs IC T).

---

### Session 2026-06-17 (session 4) — ECM Extension Offer rewrite

#### ECM Extension Offer — gen_offer_pdf.py (complete rewrite)
File: `tools/gen_offer_pdf.py` → `artifacts/reports/ECM_EXTENSION_OFFER.pdf`

Structure: itemised feature menu (Sections A–D) + recommended bundles + scope ownership statement.

**Section A (U1–U8)** — STAR Usability, all Bojan-owned:
U1 $400 | U2 $400 | U3 $700 | U4 $800 | U5 $1,000 | U6 $1,400 | U7 $600–900 | U8 $1,200
U8 = Battery Assistant-style macro setup wizard (interactive dialog; moved FROM exclusions).
Bundle U1–U8: **$3,200** (saves ~$3,300 vs individual).

**Section B (M1–M3)** — Multi-Cell / Module:
M1 $750 (zone-name refactor, small), M2 $900–1,200 (circuit interface, joint),
M2b not-priced (circuit solver = backend scope), M3 $600–900 (smoke test).
Bundle M1+M3: **$1,200** (was $1,500 — that was NOT a discount; fixed).

**Section C (P1–P4)** — Backend Physics Support (Bojan role = interface/schema/smoke tests only):
P1 $600–900 | P2 $500–800 | P3 $500–900 | P4 $800–1,200.
Bundle: **$2,000** (saves ~$400–$1,800).

**Section D (S1–S4)** — Abuse Interface (S4 = actual heat-release model, not-priced/backend):
S1 $500 | S2 $900 | S3 $700–900 | S4 not-priced.
Bundle S1+S3: **$1,800** (saves ~$300–$500).

Key commercial points:
- "Bojan/Helicon is not responsible for electrochemical accuracy claims for backend changes"
- No ECM algorithm implementation implied in any physics-support item
- Minimum custom order: $1,000
- Bundle highlights show "If purchased separately: ~$X" inline

---

### Session 2026-06-17 (session 3) — Contract report refinement + ECM positioning

#### Contract report — key changes
- Contract wording column now uses **verbatim text** from pasted contract throughout
- Item 1.2 removed (no direct contract line); thermal properties folded into 1.1
- Section 3 collapsed from 3 items to 1 (single contract bullet)
- Application files order corrected: **(a) element-wise, (b) lumped** — was swapped
- All OpenFOAM references removed from implementation text
- Item 7.1 notes block removed (had OpenFOAM mesh tools; STAR uses STEP not STL)
- **Item 1.1 status: DONE → PARTIAL** — anisotropic k not confirmed in delivered .sim
- Open items table: new row 1.1 (anisotropic k gap)

#### Contract status summary (current)
| Deliverable | Status |
|---|---|
| 3D cylindrical cell model (jellyRoll, shell, cap) | **PARTIAL** (aniso k unverified) |
| Element-wise ECM coupling + impedance-network current distribution | DONE |
| Lumped adaptor (volume-avg T in, volumetric heat out) | DONE |
| Coupling scripts + cell property import | DONE |
| Application file (a): element-wise electrothermal case | DONE |
| Application file (b): lumped electrothermal case | DONE |
| Ongoing applications support | DONE (ongoing) |
| Re-validation 10–60 °C voltage response | PARTIAL |
| Cell-size scaling methodology (21700 → 4680 outline) | NOT YET |

#### Three-tier ECM positioning (confirmed correct framing)
The key distinction is ECM *state* resolution, not just mesh:
- **Native STAR 0D RCR**: accepts third-party OCV/RCR tables (not BDS-only); cell-level ECM state — one SOC history, one RC state per physical cell; simpler, fast
- **Custom scripting**: same simple ECM table inputs; sub-cell ECM state — each zone has own SOC, RC state, local T, local R, local heat; intermediate option
- **Native 3D electrochemistry (NTG/DISTNP)**: electrode-level data required; fundamentally different workflow; most detailed

Do NOT say "STAR cannot do this natively" as absolute. Say: *"Based on documented workflows, we do not see a native UI-driven feature that runs multiple independent RCR ECM instances inside a single physical jelly roll with sub-cell SOC/RC state management."*

This framing applied to: `gen_contract_vs_impl_pdf.py` item 2.1 note + `docs/STARCCM_FEATURE_GAP_ANALYSIS.md` section 2.1 positioning note.

---

### Session 2026-06-17 (session 1) — Gap analysis PDF polish (two sessions combined)

#### Gap analysis PDF generators
- **Internal**: `tools/gen_gap_analysis_pdf.py` → `artifacts/reports/STARCCM_FEATURE_GAP_ANALYSIS.pdf`
- **Client**: `tools/gen_gap_analysis_pdf_client.py` → `artifacts/reports/STARCCM_FEATURE_GAP_ANALYSIS_CLIENT.pdf`
- Both use `IdentityReport` from `src/pumpfoil/reporting/identity_report.py`
- Content sourced from `docs/STARCCM_FEATURE_GAP_ANALYSIS.md` (31 gaps across 7 sections)

#### Summary table — 6 columns
Columns: `#`, `Category`, `Gap`, `Rating`, `Impl. status`, `Time needed` / `Time estimate`
`split_closeable(text)` parses the markdown "Closeable?" cell into (status, time) pair.
Client version triples time estimates via `triple_times()`.

#### Closure priorities — 4 tiers + reference (covers all 31 gaps)
- Tier 1: 9 quick-win items (existing arch)
- Tier 2: 6 moderate-effort items (Java/Python extensions, some conditional on tab geometry)
- Tier 3: 5 physics extensions (ecm_step.py); blue header color #1a5276
- Tier 4: 6 out-of-scope items; red header
- For reference: 5 already-addressed/N/A items

#### Gap analysis source document facts
`docs/STARCCM_FEATURE_GAP_ANALYSIS.md` — 31 gaps, 7 categories.
(Cover metric currently says "28" — not yet corrected, low priority.)
Sources: UserGuide_18.06.pdf, batteryModuleStarManual.pdf, STARCCM_CLIENT_MANUAL.pdf.

---

### Session 2026-06-16 — PDFs, STAR battery manual review, ecm_step.py analysis

#### PDFs generated this session
- `artifacts/reports/client_report.pdf` — 41 pages, 5.9 MB. Built by `tools/gen_client_pdf.py`.
  Required `pip install fpdf2 matplotlib` (were missing). Uses DejaVu fonts from matplotlib TTF path.
- `artifacts/reports/meeting_questions_20260616.pdf` — 12 kB. New script:
  `tools/build_meeting_questions_20260616_pdf.py`. Built with reportlab (also required install).
  Content: 2026-06-12 client run findings, 5 questions for client, pre-run checklist, open items.

#### STAR-CCM+ battery module manual — read and analysed
File: `docs/batteryModuleStarManual.pdf` (109 pages, STAR-CCM+ 2602).
Extracted to `/tmp/battery_manual.txt` via pypdf (also required install).

Key STAR battery module capabilities:
- **0D path**: RCR table model + Thermal Runaway (Heat Release / Vent Gas / Mass Loss models)
- **3D path**: requires `.tbm` file from Battery Design Studio + `batterysim` license;
  e-cell mesh solves NTG/RCR/DISTNP electrochemistry spatially
- **Battery modules**: N_Series × N_Parallel circuit topology, automatic circuit solver
- **Field functions**: Battery Volumetric Heat, SOC, V_T, current density vectors per e-cell
- **Electrical solver**: computes spatially varying current density, ohmic heat, polarisation heat
- Aging/cycle-life is NOT in this manual — lives in Battery Design Studio / Amesim

#### STAR 3D e-cell mesh ≠ our distributed ECM mode
The 3D e-cell mesh is a **spatially resolved electrochemical solver**: each e-cell has own SOC,
current density vector, voltage, heat — driven by electrode physics and tab geometry.
Our `elementWise` / distributed mode is a **thermal mapping layer on top of a 0D RCR model**:
one SOC, one voltage, one total heat — spatial variation comes only from temperature distribution,
not from current distribution physics.
This is why the "shared electrical state" baseline was accepted: giving each partition its own
independent SOC (without a current distribution model) makes it a different electrical model,
not a more refined version of the lumped baseline.

#### What we can do WITHOUT modifying ecm_step.py — KEY FINDING

`ecm_step.py` already has three entry points:
1. `ecm_step()` — scalar or N-cell vector, 2RC, lambda_Q/lambda_R scaling
2. `parallel_2rc_step()` — N parallel slices, **solves common terminal voltage via KVL/KCL**,
   returns per-slice `I_BRANCH` from impedance differences. Supports `internal_iterations`.
3. `multi_cell_parallel_step()` — M cells × n_parallel slices, shape (M, n_parallel)

`parallel_2rc_step` already implements the impedance-network current distribution that is the
main physics gap vs STAR's 3D e-cell. It solves:
  `V_terminal` = common; `I_i = (V_terminal - u_cell_i) / R0_i`; `sum(I_i) = I_pack`
Each slice gets a different current based on local (SOC_i, T_i) → R0_i.

**The gap**: `ecm_coupler.py` calls `run_ecm_step_per_partition` which feeds full pack current
`I_total` to every partition. `parallel_2rc_step` is imported but NOT used in the distributed
thermal path.

**The fix (all in ecm_coupler.py, no ecm_step.py changes)**:
- Replace `run_ecm_step_per_partition` with a call to `parallel_2rc_step`, passing
  per-partition temperatures as the slice temperature array.
- Result: hot zones get less current (higher R0), cool zones more — physically correct.

Other things doable without ecm_step.py changes:
- Populate `E_OCV_ch_V` ≠ `E_OCV_dch_V` in params.csv → charge/discharge OCV asymmetry active
- Set `internal_iterations > 1` at call site → tighter current-balance convergence
- Use `lambda_Q` / `lambda_R` for per-region cell variation without separate params files
- Per-partition initial SOC via initialization helpers

ecm_step.py cannot do without modification: 3RC/Warburg, charge/discharge Ro asymmetry,
max current clamping, aging, thermal runaway.

#### Pending fixes — DONE 2026-06-16 (session 2)
- **partitionstates impedance-network fix** — `run_ecm_step_per_partition` replaced by
  `run_ecm_step_parallel_branches` in the `distributed_mode == "partitionstates"` path.
  Hot zones now get less current (higher R0), cool zones more — closes the physics gap vs
  STAR's 3D e-cell mesh. Mode label in diag: `"partitionStates_impedanceNetwork"`.
  `run_ecm_step_per_partition` kept (still callable if needed) but no longer on the hot path.
  Synced to client pack.
- **V_common_V multi-region** — `combined_diag["V_common_V"]` now set to mean of per-region
  voltages after the region loop (ecm_coupler.py line ~2265). Fixes voltageLog.csv zeros.
  Synced to client pack copy.
- **appliedTotalHeatLog.csv renamed to ecmHeatLog.csv** — reflects that it logs ECM-computed
  heat set on the STAR parameter, not what STAR's solver integrated. Column header updated to
  `ecm_heat_w`. Synced to package/src/, client pack, CODE_SUMMARY.md, README.txt.
- **autoConfigureJellyRollEnergySource STAR 2602** — warning message updated to explicitly
  mention STAR 2602 TypedObjectManager API change and that warning is BENIGN if pre-configured
  in GUI. Javadoc updated. Synced to package/src/ and client pack.

---

### Docker launch infra — added 2026-06-13
Three files added to workspace root: `Dockerfile.claude`, `entrypoint.claude.sh`, `runClaude.sh`.
Key point: claude-code installed as non-root user into `~/.npm-global` so `npm i -g` updates
work in-container. `runClaude.sh` prompts for update (or use `--update` flag).
Dockerfile ENV NPM_CONFIG_PREFIX hardcoded to `/home/helios` — must edit + rebuild for other usernames.

---

### Client jellyRoll_2 cooling diagnosis — 2026-06-12

**Finding**: ECM coupling works correctly for both batteries. jellyRoll_2 cools because:
1. STAR thermal BCs give jellyRoll_2 ~3× stronger cooling than jellyRoll_1 (intrinsic CFD issue)
2. Dead periods between macro restarts pushed jellyRoll_2 below the recovery threshold (~297K)
3. Cold equilibrium ~286K = ECM heat (22W) balanced by strong convective cooling

**Actions needed:**
- Deploy equal-split fix to client: `n_per_region = 96751//2` bug in client's ecm_coupler.py
  (correct sizes: 49309 / 47442; fix uses ECM_REGION_SIZES env var — already in repo)
- ~~Fix `autoConfigureJellyRollEnergySource`~~ **FIXED 2026-07-06** — use `getModelManager().getModel()` path (see below)
- Rename `appliedTotalHeatLog.csv` → misleading name; it logs ECM-computed heat, not STAR-applied
- Tell client: don't restart macro mid-run; check jellyRoll_2 thermal BCs in STAR GUI

**Confirmed working:**
- qvol_injection.csv: both regions non-zero (r0 mean 596 kW/m³, r1 mean 855 kW/m³)
- FileTable readback (DIAG2) correct; EW-1 shows both batteries heating at dt=1s, fresh IC
- autoConfigureJellyRollEnergySource failure is BENIGN if user pre-configured in GUI

Meeting folder: `meeting/20260612/` — 20260612-LOG, 20260612-ecm/ folder, screenshot

---

### ecm_coupler.py hard failures — DONE 2026-06-10; fresh-run fix 2026-06-12

Three silent fallbacks converted to hard failures:
1. `ecm_step.py` missing → `ImportError` raised (was: mock backend with no log output)
2. `ecm_mapping.csv` specified but absent → `FileNotFoundError` (was: synthetic mapping fallback)
3. `ecm_state.json` absent on continuation run → `FileNotFoundError` (was: SOC silently reset to 1)
Also: `ecm_state.json` JSON parse failure → `RuntimeError` (was: silent reset)

**BUG FIXED 2026-06-12**: Java was deleting `ecm_state.json` on fresh start; Python treated absent
file as fatal continuation error. Fix: Java now writes `{}` (empty JSON) instead of deleting.
Python loads `{}`, all `.get(key, default)` calls return defaults → SOC=1 fresh state.
Missing file still correctly errors on genuine continuation runs.
Affects all 3 `freshStart` blocks in `EcmCouplerMacro.java` (ECM, ECM-EW, ECM-LMR paths).

Canonical source: `starccm_plugin/package/ecm/ecm_coupler.py`
Synced copy: `artifacts/packs/ecm_coupler_starccm_client_20260610/ecm/ecm_coupler.py`

### 30-test suite runnable without STAR-CCM+ — DONE 2026-06-10

`tools/test_ecm_no_star.py` — 30/30 passing
- A: hard failure modes (3) — missing ecm_step.py, missing mapping, missing state on continuation
- B: binary I/O round-trip (7) — v1/v2 headers, inputs dict, bad magic, truncation
- C: pipe-binary end-to-end subprocess (8) — frameType, N, stepId, qVol, state written, multi-step
- D: mock backend physics sanity (4) — qVol positive, uniform T, temperature sensitivity, SOC consumed
Key: uses persistent `_ECM_TMPDIR`; `cellprops.csv` must come from `/workspace/Parallel_ECM/`
(STAR format with `Qnom_Ah`), NOT `/workspace/cellprops.csv` (OpenFOAM format with `capacity_Ah`).

### regionIdx fix — DONE 2026-06-10

`buildMergedCellMapper()` now uses **nearest-centroid spatial assignment only** — no fallbacks.
- Primary: read region centroids from `ecm_region_geometry.csv` (origin_x/y/z)
- Fallback (within spatial path): k-means clustering with k=N on cell centroids
- Hard abort (`throw Exception`) if spatial assignment fails — no silent wrong mapping
- `computeRegionIndicesFromFvRep()` and `verifyAndCorrectRegionIdxOrdering()` are DEAD CODE
- Synced to all 3 copies: `starccm_plugin/src/`, `starccm_plugin/package/src/`,
  `artifacts/packs/ecm_coupler_starccm_client_20260610/src/`

### EcmCoSimPartner C++ Co-Sim API partner — v1.2 multi-region as of 2026-06-12

`starccm_plugin/cosim/EcmCoSimPartner.cpp` — replaces CSV injection with STAR Co-Sim API.
5 rounds of consultant review + multi-region refactor completed.
Session logs: `artifacts/logs/session_20260611_000000.log`, `session_20260611_cosim_round45.log`

**Confirmed correct against `/workspace/include/StarccmplusCoSimulationApiV8.h` + SpringMass.cpp:**
- `registerOutgoingMesh(regionId)` — 1 arg; mesh type from `createContinuum`
- `notifyOutgoingMeshReady(meshId)` — 1 arg with meshId; call once per region mesh
- `getConditionValueProperties(coSimId, name, optionsId)` — 3 args; `getDouble` returns void (sentinel -1.0)
- `fill(id, "FieldValues")` + `getDoubleArrayReferenceAtIndex(id, "FieldValues", 0, &ptr, &sz)` for T retrieval
- `addDoubleArrayElement(id, "FieldValues", data, sz)` for outgoing qVol field
- `setTimeStep(t, dt)` + `setCouplingTime(t+dt)` called per-step BEFORE `waitForIncomingFields()`
- `waitForIncomingFields()` returns 0 = end-of-sim; non-zero = data available
- No `waitForUpdate()` post-connect (SpringMass doesn't use it)
- `StarccmplusMeshType`: only `SurfacePolyMesh` and `VolumePolyMesh` — NO ScatterPolyMesh

**Multi-region support (v1.2) — 2026-06-12:**
- Env vars: `ECM_N_REGIONS` (int), `ECM_REGION_NAMES` (comma-sep, e.g. `jellyRoll_1,jellyRoll_2`)
- Default single-region name: `jellyRoll` (backward compat); multi-region default: `jellyRoll_0, jellyRoll_1, ...`
- Cells reordered: all r=0 first, r=1 next — matches Python ECM_REGION_SIZES slicing
- `g_regionCells[r]` → global indices; per-region mesh/T/qVol containers via `g_meshIdxByContainerId` etc.
- Before `system(g_ecmCmd)`: sets `ECM_N_REGIONS` and `ECM_REGION_SIZES` via `setenv()`/`_putenv_s()`
- `ecm_coupler.py` multi-region slicing fixed: reads `ECM_REGION_SIZES`, falls back to equal-slice

**One remaining runtime risk (cannot resolve statically):**
- VolumePolyMesh with N point-cells (0 faces) — STAR acceptance unverified
- Logged as `gLog.warn()` at mesh fill time
- Resolve by live STAR test with `INJECTION_MODE=coSim`

**Bugs corrected (historical — do not re-apply):**
- B4 was wrong: `addDoubleArrayElement` is correct for outgoing fields (NOT `addDoubleArray`)
- F1/F2a/F2b/F3/F4 were wrong direction — all reverted to match actual headers

Two-tier Logger: `info()` → screen+file, `verbose()` → file only, `warn()`/`error()` → both.
Tests: `starccm_plugin/cosim/tests/` — 63/63 passing (no STAR required), incl. T5 (region reorder).
Consultant pack: `artifacts/packs/cosim_review_20260611/` — in sync with source (v1.2).

**Next steps:**
- Test against live STAR-CCM+ with `INJECTION_MODE=coSim`, `ECM_N_REGIONS=2`,
  `ECM_REGION_NAMES=jellyRoll_1,jellyRoll_2` and `final_2cells.sim`
- If STAR rejects zero-face VolumePolyMesh: contact Siemens for scatter-point guidance
- Add `INJECTION_MODE=coSim` branch to `EcmCouplerMacro.java` once mesh confirmed

---

## Shell command formatting rule

When giving the user shell commands to run manually, keep each line ≤ 100 chars.
Break long paths and pipelines with backslash continuation. Example:

```bash
find "/long/path/here" \
  -name "pattern" | head -20
```

Never put a long path + flags + pipe all on one line — the terminal wraps and
breaks copy-paste.

---

## STAR-CCM+ Client Manual and Package

- PDF manual: `/workspace/docs/STARCCM_CLIENT_MANUAL.pdf` (26 pages, v4 = 2026-06-09)
- Build script: `/workspace/tools/build_manual_pdf.py`
- Figures in `artifacts/plots/starccm_manual_*.png` (architecture, validation, extracted from internal doc)
- `electrical_inputs.csv` is canonical name (renamed from `electrical_inputs_experimental_10C_discharge.csv`)
- Validation: 10C = 50 A, 289 s, to ~20% SOC (NOT full discharge / NOT 70% SOC)
- Timestep recommendation: dt ≤ 0.2 s; 0.25 s is sensitivity baseline only
- Client package: `artifacts/packs/ecm_coupler_starccm_client_20260609.zip` (38 MB) — INCOMPLETE (missing ecm_step.py, gen_ecm_mapping.py)
- **Corrected package**: `artifacts/packs/ecm_coupler_starccm_client_20260610.zip` (1.2 MB, no .sim included)
  - Contains: README.txt, STARCCM_CLIENT_MANUAL.pdf, setup.bat, src/EcmCouplerMacro.java,
    src/EcmBinaryIO.java, ecm/ecm_coupler.py, ecm/ecm_step.py, ecm/gen_ecm_mapping.py,
    ecm/ecm_io.py, ecm/mock_ecm_backend.py, ecm/mock_model.py, ecm/params.csv,
    ecm/electrical_inputs.csv, ecm/requirements-runtime.txt (15 files, NO JAR)
- Package template: `starccm_plugin/package/ecm/` — now contains ecm_step.py and gen_ecm_mapping.py (added 2026-06-10)

## Project Overview

OpenFOAM ↔ ECM coupling framework for battery thermal simulation.
STAR-CCM+ plugin in `starccm_plugin/`. OpenFOAM solver in `src/`, cases in `cases/`.
Active STAR-CCM+ development case: `in/starCCM_10C_experiment_twoCells/` — two-cell distributed run confirmed working. Single-cell original: `in/starCCM_10C_experiment/`. Distributed sim: `in/starCCM_10C_experiment_twoCells_distributed/final_distributed.sim`.

**Rule — "analyze the Windows run":**
1. Use **only** `in/starCCM_10C_experiment_twoCells/` — no other path.
2. List **all** files in that directory.
3. Find the **newest file** — its timestamp is the **baseline time**.
4. Analyze **only** files within **3 hours** of that baseline. Everything older is ignored.

---

## STAR-CCM+ client package — .java files only, NO JAR

**Rule:** The client package must ship `.java` source files, NOT a pre-built `.jar`.

STAR-CCM+ runs macros directly from `.java` source via its built-in Java compiler.
The client loads `src/EcmCouplerMacro.java` through **Tools → Macros → Run Macro**
and STAR compiles and executes it on the fly. A `.jar` is never needed and should
not be included in the package.

**Package must contain:**
- `src/EcmCouplerMacro.java` — main macro (client loads this directly)
- `src/EcmBinaryIO.java` — binary protocol helper (auto-compiled alongside the macro)
- `ecm/` — Python ECM backend files
- `setup.bat` — Windows Python setup helper
- `README.txt` — setup guide

**Package must NOT contain:**
- `EcmCouplerMacro.jar` — remove from package; JAR is only for the internal build step
- Any pre-compiled `.class` files

The `build.sh` / `dist/` / `build/` tree is for internal development only and
must not be shipped to the client.

---

## STAR-CCM+ vs OpenFOAM temperature discrepancy — dt constraint

**Root cause (confirmed 2026-05-26):** STAR dt=1s is too coarse for the ECM RC circuits.

ECM RC time constants: τ₁ = R1·C1 ≈ 0.00149×1109 ≈ **1.65s**, τ₂ ≈ **2.5s**.
Accuracy requires dt < τ/5 → **dt < ~0.3s**. At dt=1s: exp(-dt/τ₁)=0.55 → 45% of
V_RC1 discarded each step → accumulated RC overpotential error → V_terminal ~0.14V low.

**STAR-CCM+ 10C experiment boundary condition: NOT convective.** The 10C experiment
STAR cases use the **same isothermal BC** as OpenFOAM. Do NOT write "STAR uses convective
h=10" for these cases.

**Voltage discrepancy (confirmed 2026-05-27):** If applied heats match but voltage differs,
the culprit is dt RC integration error, NOT temperature and NOT an ECM bug.
Temperature can only shift voltage by tens of mV; the ~0.27V STAR vs OF gap is purely dt.

**Recommendation:** Run STAR at dt≤0.2s to match OF accuracy.

---

## Correct OF runs for 10C experimental comparison plots

**DO NOT use** the `_dirKfix_20260524` OF cases — these used a wrong thermal conductivity
fix that suppressed temperature artificially.

**Use these instead:**
- OF distributed: `rev4/dist_3600_fulllog_iso25_exp10C_hfix_20260511_074620` (287s, dt=0.1s)
- OF lumped:      `rev4/dist_3600_fulllog_iso25_exp10C_trueLumped_20260512` (287s, dt=0.1s)

**"dist_3600" folder naming**: folders tagged `exp10C` only ran for ~287s (the experimental
duration), NOT 3600s. The "3600" prefix is just the base mesh case name — do not be misled.

---

## STAR distributed comparison plot — data sources (2026-05-27)

Script: `tools/plot_star_distributed_vs_of_distributed_10c.py`
Latest plot: `star_distributed_vs_of_distributed_10c_20260527_002415.pdf/png`

**STAR distributed** — from `in/starCCM_10C_experiment_twoCells_distributed/log_distributed`
  - Parser: `load_star_dist_from_log()` — reads `[ECM-py] [ecm_diag]` lines
  - T_end=39.26°C, Q_end=37.95W, V_end=2.23V (dt=1s run → V degraded)
  - `temperatureJellyRoll.csv` in this dir is **stale** (identical to lumped dir, md5 confirmed)

**STAR lumped** — T from `in/starCCM_10C_experiment_twoCells/log` (via `load_star_log_T()`,
  parses `[ECM] step=` lines, last stepId=1 run); V+Q from `ecm/voltageHistory.csv`
  - T_end=36.28°C, V_end=2.36V

**Open issue for next session:** STAR distributed voltage from `log_distributed` (dt=1s)
is 2.23V — degraded by RC integration error. The old `ecm/voltageHistory.csv` in the
distributed dir has a **better dt=0.2s run** (V_end=2.38V, T_end=38.38°C, 1502 rows).
Decision needed: use hybrid (voltageHistory.csv for V+Q, log_distributed for T)
or rerun STAR at dt≤0.2s.

---

## HARD RULE — File paths in Java/STAR-CCM+ code

**Always use RELATIVE paths** when setting file references on STAR-CCM+ `FileTable` objects or any config written by Java/Python.
- **Never** call `getAbsolutePath()`, `toAbsolutePath()`, or build an absolute path string for a table file reference.
- Root cause (2026-05-26): `getOrCreateQInjectionTable()` and `setupWeightVisualization()` were calling `getAbsolutePath()` on `Q_TABLE_CSV_FILE` / `ZONE_WEIGHTS_CSV_FILE`, overwriting the relative path the user had set in the `.sim` file every run.
- Fix: pass `Q_TABLE_CSV_PATH` / `ZONE_WEIGHTS_CSV_PATH` (the relative string constants) directly.
- **Any use of an absolute path requires explicit double-confirmation from the user before proceeding.**

---

## Bug fix — overlap mapping destroyed by Python stale-check (fixed 2026-05-26)

**Symptom:** elementWise (distributed) mode showed only N discrete heat levels (one per
ECM zone) with hard steps at zone boundaries — no blending for boundary cells.

**Root cause:** `_maybe_regen_mapping()` in `ecm/ecm_coupler.py` compared total rows in
`ecm_mapping.csv` to cell count. Overlap-weighted mappings have >1 row per boundary cell
(e.g. 30,137 rows for 21,552 cells), so the check always triggered, overwriting the
correct Java-generated mapping with a flat 1-per-cell mapping.

**Fix (all three copies updated):** Count unique `meshKey` values instead of total rows.
```python
n_unique_keys = len({row[_key_col] for row in csv.DictReader(open(mapping_path))})
if n_cellmap != n_unique_keys:
    needs_regen = True
```
Files: `ecm/ecm_coupler.py`, `in/starCCM_10C_experiment_twoCells/ecm/ecm_coupler.py`,
`in/starCCM_10C_experiment_twoCells_distributed/ecm/ecm_coupler.py`

---

## Quick-reference rule

**`starccm_plugin/CODE_SUMMARY.md`** is the live code map for `EcmCouplerMacro.java`.
Read it before touching the source. Update it after every code change.

---

## Code Map — STAR-CCM+ distributed ECM

### Java source files (`in/starCCM_10C_experiment/src/`)

| File | Purpose | Lines |
|------|---------|-------|
| `EcmCouplerMacro.java` | Main macro — lumped + elementWise + lumpedMultiRegion coupling; N-region support | ~5246 |
| `EcmBinaryIO` (inner class, ~line 3200) | Binary I/O for ecm_in.bin / ecm_out.bin | — |
| `CellMapper` (inner class, line 1807) | Loads cell-ID/centroid map; extracts T each step; regionIndices field | — |
| `CurrentProfile` (inner class, line 3493) | Reads current_profile.csv; returns I(t) | — |
| `PersistentEcmProcess` (inner class, line 3679) | Keeps Python process alive between steps | — |
| `EcmPrepAndRun.java` | One-shot setup macro (generate cell_map.csv etc.) | — |
| `TestV4_SpeedProbe.java` | T-extraction speed benchmark (not production) | — |
| `TestJellyRollTemperatureExtraction.java` | API probe tests (not production) | — |
| `exportJellyRollMesh.java` | Exports CGNS mesh for cgns_cell_map.py | — |

**Canonical copies kept in sync:**
- `in/starCCM_10C_experiment_twoCells/src/EcmCouplerMacro.java` ← active development copy (2-cell case)
- `starccm_plugin/src/EcmCouplerMacro.java` ← plugin package copy
- `starccm_plugin/package/src/EcmCouplerMacro.java` ← deployable zip copy
- Same sync rule applies to `TestJellyRollTemperatureExtraction.java`

### Project folder layout (`in/starCCM_10C_experiment/` = exact replica of Windows project)
```
src/   — Java macros (EcmCouplerMacro.java, EcmPrepAndRun.java, tests)
ecm/   — Python ECM backend + cgns_cell_map.py (co-located here, NOT in tools/)
```
- No `tools/` subfolder inside the project — workspace `tools/` is Linux-only
- `EcmPrepAndRun.java` looks for `cgns_cell_map.py` at `<PROJECT_ROOT>/ecm/`
- `resolveAndSetProjectRoot()` has NO hardcoded fallback — always auto-detects from macro file location
  (parent of `src/` via `resolvePath("_")`); `ECM_PROJECT_ROOT` env var overrides. Bug fixed 2026-05-26:
  old condition `|| PROJECT_ROOT.exists()` caused early-exit when an OLDER project dir existed on disk.
  `ECM_MAPPING_CSV_FILE` also changed from `static final` to `static File` so it can be updated.

### qVol scaling bug + stale mapping (fixed 2026-05-26)

**Bug:** Temperature explosion to >1000°C within 5 timesteps on lumped single-cell run.

**Root cause 1 — qVol shortcut:**
`aggregate_ecm_temperatures` had a "pre-aggregated" shortcut:
`if keys and len(keys) == len(temps) and all(k in ecm_to_mesh for k in keys)`
In lumped mode, STAR sends key=0 (hardcoded in `buildLumpedInputBytes`). If key=0 is in
`ecm_to_mesh` (it always is for any non-trivial mapping), the shortcut fires → `ecm_ids=[0]`
→ only partition 0's volume used → qVol 17× too large.
**Fix:** Added `len(keys) == len(ecm_to_mesh)` so shortcut only fires when caller provides
exactly one temperature per ECM partition (OpenFOAM C++ path).

**Root cause 2 — stale ecm_mapping.csv:**
Lumped csvReload path called `buildMergedCellMapper` (which detects and fixes the in-memory
CellMapper from T-table after re-mesh) but did NOT call `writeCellMapCsv`. So `ecm_cell_map.csv`
stayed stale on disk → Python's mtime check never triggered regen → wrong partition volumes.
**Fix (Java):** Added `writeCellMapCsv` call in lumped csvReload startup path, before Python starts.
**Fix (Python):** Added count-mismatch check in `_maybe_regen_mapping`: if ecm_mapping.csv row
count ≠ ecm_cell_map.csv row count, force regen regardless of mtime.

### Lumped N=1 csvReload injection (fixed 2026-05-26)

**Problem:** Switching `COUPLING_MODE` from `elementWise` to `lumped` left the STAR
energy source wired to the FileTable (from elementWise setup). Old lumped code only set
`ecmQdot_W` global parameter — which the .sim file never read. FileTable CSV was never
updated → constant stale heat → temperature plateau.

**Fix:** Lumped N=1 path now supports `INJECTION_MODE=csvReload` (the default):
- At startup: builds `lumpedCellMapper` + retrieves `lumpedQTable` + calls
  `autoConfigureJellyRollEnergySource()` — same wiring as elementWise.
- Each step: fills `qUniform[n] = qVol`, calls `applyElementWiseHeatCsv()` →
  writes (X,Y,Z,qVol) CSV and calls `FileTable.extract()`.
- Fallback: if FileTable setup fails, reverts to `qParam.getQuantity().setValue(qVol)`.

**Result:** `COUPLING_MODE` can be switched freely between `lumped` and `elementWise`
without any manual reconfiguration inside the `.sim` file.

### Lumped multi-region coupling (implemented 2026-05-26)

`executeLumpedMultiRegion(sim, List<Region>)` — dispatched from `execute()` when:
- `COUPLING_MODE == "lumped"` AND `INJECTION_MODE == "csvReload"` AND `regions.size() > 1`

**How it works:** Sends standard N-cell elementWise binary frame with uniform T per region
(T_avg[k] broadcast to all CFD cells in region k). Python runs normally (parallelBranchesSharedSOC_multiRegion).
Java aggregates returned per-cell qVol → per-region Q[k] → under-relax → writes uniform
`qVol[i] = Q[k]/V_region[k]` to injection CSV. One `VolumeAverageReport` per region
(`ECM_T_avg_r0`, `ECM_T_avg_r1`, ...). Same table injection, same mapping, no Python changes.

**To activate:** set `ECM_COUPLING_MODE=lumped` (everything else stays the same).

### Multi-JellyRoll region support (Option B — implemented 2026-05-26)

- `execute()`: discovers all regions whose name contains `REGION_NAME_PATTERN` (env `ECM_REGION_PATTERN`, default `"jellyRoll"`), sorts alphabetically, dispatches `List<Region>` to `executeElementWise()`.
- `executeElementWise(sim, List<Region>)`: calls `buildMergedCellMapper()` (N=1 → existing path unchanged); loops `autoConfigureJellyRollEnergySource` over all regions; sets `nRegionsForEnv`.
- `buildMergedCellMapper()`: N=1 → delegates to `CellMapper.create()`. N>1 → reads combined T-table; assigns `regionIndices` via `computeRegionIndicesFromFvRep()` (primary: FvRep getCellCount per region), CSV fallback, then all-zeros.
- `writeCellMapCsv()`: now writes `regionIdx` column (all zeros for N=1 — backward compat).
- `runProcess()` / `PersistentEcmProcess.start()`: both pass `ECM_N_REGIONS` env var to Python.
- `ecm_coupler.py`: in `parallelBranchesSharedSOC` block reads `ECM_N_REGIONS`; N=1 → unchanged path; N>1 → splits ecm_ids/ecm_temps into N groups, runs N independent `run_ecm_step_parallel_branches` calls, merges.
- `gen_ecm_mapping.py`: reads optional `regionIdx` column; for each region applies zone offset `region_idx * n_zones`; N=1 output is bit-for-bit identical to before.
- **Backward invariant**: N=1 is fully bit-for-bit identical to confirmed-working single-region run.

### Key constants in EcmCouplerMacro.java (lines 39–230+)

```
REGION_NAME         = "jellyRoll"
QPARAM_NAME         = "ecmQdot_W"         ← ScalarGlobalParameter in STAR
ECM_DIR             = PROJECT_ROOT/ecm/
ECM_IN_PATH         = ECM_DIR/ecm_in.bin
ECM_OUT_PATH        = ECM_DIR/ecm_out.bin
COUPLING_MODE       = env ECM_COUPLING_MODE              default "elementWise"
T_EXTRACTION_BACKEND= env ECM_T_BACKEND                  default "xyzTable"
T_TABLE_NAME        = env ECM_T_TABLE_NAME               default "ECM_jellyRoll_T_Table"
CELL_MAP_CSV_PATH   = env ECM_CELL_MAP_CSV               (pre-generated by cgns_cell_map.py)
CELL_STEP_CSV_PATH  = env ECM_CELL_STEP_CSV              (per-step diagnostic CSV)
ECM_DISTRIBUTED_ELECTRICAL_MODE = env (same name)        default "partitionStates"
ECM_MAPPING_FILE_PATH = env ECM_MAPPING_FILE             default "ecm/ecm_mapping.csv"
ECM_N_ELEMENTS      = env ECM_N_ELEMENTS                 default 20 (ignored if mapping file present)
ECM_MAPPING_CSV_FILE = File(PROJECT_ROOT, ECM_MAPPING_FILE_PATH)
ZONE_WEIGHTS_CSV_PATH = env ECM_ZONE_WEIGHTS_CSV         default "ecm/ecm_zone_weights.csv"
ZONE_WEIGHTS_TABLE_NAME = env ECM_ZONE_WEIGHTS_TABLE     default "ECM_ZoneWeights_Table"
ZONE_WEIGHTS_CSV_FILE = File(PROJECT_ROOT, ZONE_WEIGHTS_CSV_PATH)
ALPHA               = 1.0                  ← under-relaxation (1 = off)
N_STEPS             = 100000
ECM_TIMEOUT_S       = 60
```

**`ECM_DISTRIBUTED_ELECTRICAL_MODE` is passed to Python via env in BOTH `runProcess()` AND `PersistentEcmProcess.start()`.**
Default is `partitionStates` (was previously omitted → Python defaulted to `sharedState`).

### execute() dispatch (line 184 → line 242)
```
execute()
  ├─ COUPLING_MODE == "lumped"      → runLumpedCoupling()     (line ~250)
  └─ COUPLING_MODE == "elementWise" → executeElementWise()    (line 507)
```

### executeElementWise() loop (line 507–730)
Per-step sequence:
1. `CellMapper.create()` — load or build cell map once at step 0
2. `getTemperaturesFromXyzTable()` — call `extract()` + `getSeries(int)` on T table
3. `EcmBinaryIO.writeElementWiseInput()` — write ecm_in.bin (N records)
4. `runProcess()` — spawn `ecm_coupler.py`
5. `waitForFile()` — poll for ecm_out.bin
6. `EcmBinaryIO.readElementWiseOutput()` → `Map<cellId, qVol_W>`
7. Merge into `double[] qVolNew` (per-cell W)
8. `writeStepCsv()` — diagnostic CSV
9. `applyElementWiseHeat()` — **STUB: sums qVolNew → pushes total W to ecmQdot_W**

### STAR-CCM+ vs OpenFOAM — fundamental field injection difference

**OpenFOAM** owns the field memory directly:
- `ecmQdot` is a `volScalarField` living in the solver's memory
- Per-cell write is a direct array assignment: `qField[cellI] = qApplied` (line 2925, ecmCoupler.C)
- No file I/O, no table reload — just a pointer dereference into a C++ `scalarField`
- After the loop: `correctBoundaryConditions()` and done — solver reads same memory next iteration

**STAR-CCM+** has NO equivalent direct memory write path in its Java API (STAR 2602):
- P1 (`UserDataSet`/`getDataSet()`) — **NOT_FOUND** in API
- P2 (`ArrayScalarFieldFunction`) — **NOT_FOUND** in API
- P3 (`XyzInternalTable.setValueAt()`) — call succeeds but value does NOT persist;
  `getSeries()` returns cached snapshot — confirmed by `TestPhase3FieldInjection.java` (May 21)
- Only working path: **CSV-reload** — write new `(X,Y,Z,qVol)` CSV (160,313 rows, ~5 MB)
  every coupling step, then `createFromFile()` to replace the table object, then UFF
  `interpolateTable(...)` re-evaluates at solve time
- **This means constant disk I/O every timestep** — every coupling step = one ~5 MB CSV write
  + one table reload in STAR-CCM+ (no in-memory shortcut available in STAR 2602 Java API)

Root cause: STAR-CCM+ Java API is a remote client-server protocol — Java cannot write
directly into the solver's C++ field arrays. OpenFOAM functionObject IS the solver,
so it has direct pointer access to field memory.

### `getOrCreateTReport` — multi-region fix (2026-05-26c)

Signature changed: `(Simulation sim, Region region)` → `(Simulation sim, List<Region> regions)`.
Now calls `r.getParts().setObjects(regions)` unconditionally (both new and existing reports).
This means every macro startup auto-corrects the ECM_T_avg Parts to all coupled regions.
Call sites: lumped path uses `coupledRegions`; elementWise path uses `regions`.
Note: `ECM_region_volume` and `VolAvgTemp JellyRoll` are NOT managed by the macro — must be
updated manually in the STAR-CCM+ GUI for multi-cell cases.

---

### Heat injection — FULLY IMPLEMENTED via csvReload

`applyElementWiseHeatCsv(sim, cellMapper, qVolPerCell[], fileTable)` (line 1175):
- Writes `(X,Y,Z,qVol_W_m3)` CSV per step, calls `fileTable.extract()` to reload
- STAR nearest-neighbour XYZ lookup applies per-cell qVol as `VolumetricHeatSourceProfile`
- Logs Q_total = Σ(qVol_i × V_i) [W]

`applyElementWiseHeat()` (line 1144): legacy globalParam path. DEPRECATED, warns on use.

Binary protocol: Java → Python sends T [K] per cell; Python → Java sends qVol **[W/m³]** per cell.
No W/m³→W conversion on Python side. No per-cell volume division on Java side. Uniform qVol
per partition (OpenFOAM-equivalent). See 2026-05-26 hotspot fix notes.

### Two-cell geometry (confirmed 2026-05-26d)

jellyRoll_1 and jellyRoll_2 are **side-by-side in Y**, same axial (X) range [0.23, 65.34] mm:
- jellyRoll_1: axis at (cy=−0.027 mm, cz=0.444 mm) ← world coords
- jellyRoll_2: axis at (cy=49.882 mm, cz=0.552 mm)
- Y-gap midpoint: 24.9 mm → clean split threshold
- STL files: `in/starCCM_10C_experiment_twoCells/jellyRoll_1.stl`, `jellyRoll_2.stl`

### PROJECT_ROOT path bug fixed (2026-05-26f — this session)

**Root cause of Q injection failure in two-cell case:**
- `resolveAndSetProjectRoot()` had a broken condition: `if (PROJECT_ROOT.exists()) return`
- `C:\work\active\starCCM_10C_experiment` (single-cell dir) existed on disk → early-exit triggered
- ECM wrote Q CSV to `starCCM_10C_experiment\ecm\ecm_qvol_injection.csv` (wrong dir)
- STAR's FileTable resolved relative path `ecm/ecm_qvol_injection.csv` from the `.sim` file location
  → read `starCCM_10C_experiment_twoCells\ecm\ecm_qvol_injection.csv` (stale 21,552-row single-cell data)
- T table was NOT affected (XYZ Internal Table lives in STAR memory, not on disk)

**Fix:** Removed hardcoded `PROJECT_ROOT_FALLBACK`. `resolveAndSetProjectRoot` now:
1. Checks `System.getenv("ECM_PROJECT_ROOT")` — use it if explicitly set
2. Otherwise always auto-detects: `resolvePath("_")` → parent (`src/`) → parent = project root
3. Updates ALL derived File fields including `ECM_MAPPING_CSV_FILE` (was `static final`, now `static File`)

**No separate T/Q tables needed** for two-region case. Combined single table works for both
regions once the path and energy-source issues are resolved.

### Arbitrary cylinder axis detection — PCA (2026-05-26, this session)

**Problem:** Previous fix computed local radial from per-region centroid in Y,Z — but still
hardcoded X as the axial direction. If cylinders have arbitrary orientation, this breaks.

**Solution — fully implemented across all three files:**

`gen_ecm_mapping.py`:
- Added `_compute_cylinder_axis(xs,ys,zs)`: PCA via power iteration on 3×3 covariance matrix
- Added `_read_geometry_csv(path)`: reads `ecm_region_geometry.csv` (STAR CS data)
- Added `--geometry-csv` CLI argument
- Per-cell: `axial = dot(pos-center, axis)`, `radial = |pos-center-axial*axis|`
- Priority: geometry CSV → PCA fallback

`ecm/ecm_coupler.py` — `_maybe_regen_mapping()`:
- Added `_pca_cylinder_axis()` (same algorithm)
- Added `_read_region_geometry_csv()`
- Auto-reads `ecm_region_geometry.csv` from mapping dir or `ECM_REGION_GEOMETRY_CSV` env

`starccm_plugin/src/EcmCouplerMacro.java` (~4835 lines):
- New constant: `REGION_GEOMETRY_CSV_PATH` → `ecm/ecm_region_geometry.csv`
- New methods: `writeRegionGeometryCsv()`, `extractCsOrigin()`, `extractCsAxis()`, `pcaCylinderAxis()`
- `writeRegionGeometryCsv()` matches regions by name suffix (_1, _2) → STAR CS → PCA fallback
- Called during `executeElementWise()` for N>1 regions after cell map is written
- `regenEcmMapping()` passes `--geometry-csv` to Python if file exists
- `runProcess()` and `PersistentEcmProcess.start()` pass `ECM_REGION_GEOMETRY_CSV` env

**Verification:** PCA tested on actual 2-cell mesh; both regions correctly detect X-axis.
Region 0: center (32.1, -0.0, -0.0) mm; Region 1: center (31.6, 49.9, 0.0) mm.

### Two-cell jellyRoll_2 uniform heat fix (2026-05-26e — previous session)

**Confirmed root cause from live log + files:**
1. `computeRegionIndicesFromFvRep` fails: `FvRepresentation.getRegionCellCount(Region)` not found in STAR 2602.
2. CSV fallback: previous CSV was all-zeros (from first run all-zeros fallback) → `isValidRegionIdx` would return false → stuck.
3. `_maybe_regen_mapping()` in `ecm_coupler.py` processed ALL 8198 cells as one group using `r=sqrt(y²+z²)` from GLOBAL origin → jellyRoll_2 cells (Y~0.05 m) all appear at large r → all land in outer radial bin per axial slice → same zone → **uniform heat**.

**Two fixes applied (this session):**

**Fix 1 — Java `buildMergedCellMapper()` (`starccm_plugin/src/EcmCouplerMacro.java`, synced to all copies):**
- Added `isValidRegionIdx(ri, nRegions)`: returns false if all-zeros for N>1 (stale CSV)
- Added `computeRegionIndicesFromCentroids(sim, regions, merged)`: Y-bimodality fallback
  - Computes Y range from merged CellMapper centroids
  - Requires ≥20 mm Y separation (single-cylinder case safely ignored)
  - Assigns regionIdx by Y < midpoint (=0) vs Y ≥ midpoint (=1)
  - Prints "[ECM-EW] computeRegionIndicesFromCentroids: Y range=..." diagnostic
- Branch logic in `buildMergedCellMapper()`: FvRep → valid CSV → centroid-Y → all-zeros

**Fix 2 — Python `_maybe_regen_mapping()` (`ecm_coupler.py`, synced to workspace root):**
- Now reads `regionIdx` column from cell_map.csv (if present)
- Computes per-region centroid (Y,Z) = mean of cells in that region → local cylinder axis
- Computes `r_local = sqrt((y-cy)²+(z-cz)²)` for each cell (correct per-region local radius)
- Assigns zones PER REGION with offset: `zone_id = region_idx * n_axial * n_radial + ...`
- Result: 36 total zones (18/region) for 2 physical cylinders; both get correct radial variation

**Geometry confirmed:** jellyRoll_1 at Y≈0 (centroid -0.00003), jellyRoll_2 at Y≈0.050 m (centroid 0.04994). Y gap ≈ 50 mm → midpoint ≈ 25 mm. Both regions have local r range 0-10 mm.

### Heat-injection diagnostic methods (added 2026-05-26, this session)

Three diagnostic helpers added to `EcmCouplerMacro.java` (~line 1622) to debug why
STAR "User Specified Energy Source" shows wrong values (-1.25e+05 to +6.44e+04 W/m³)
while ECM writes correct qVol (~1.22e+06 W/m³):

**DIAG-1 `diagProfileMethodType(sim, regions)` (~line 1622)**
- Called once at startup after `autoConfigureJellyRollEnergySource` loop
- Uses reflection to call `getMethod()` on each region's `VolumetricHeatSourceProfile`
- Logs exact class name of active method (e.g. `XyzTabularScalarProfileMethod`)
- Also logs table name and column if accessible
- Log tag: `[ECM-DIAG1]`

**DIAG-2 `diagQTableReadback(sim, fileTable, expectedQVol)` (~line 1702)**
- Called inside `applyElementWiseHeatCsv()` after `fileTable.extract()`
- Re-reads `Q_TABLE_CSV_FILE` from disk; logs nRows, min/max/mean of `qVol_W_m3` column
- Compares vs `expectedQVol` array (what was written)
- Logs FileTable name and absolute CSV path
- Log tag: `[ECM-DIAG2]`
- Reads CSV directly (avoids uncertain STAR in-memory FileTable row-access API)

**DIAG-3 `getOrCreateEnergySourceReports` + `logEnergySourceReports` (~lines 1782, 1867)**
- **DISABLED (stubbed) in STAR 2602**: `star.common.ReportManager` and `NeoObjectInterface` were
  removed/moved in STAR 2602; `star.base.report.Report.getValue()` also removed.
- `getOrCreateEnergySourceReports` now returns empty list immediately — `logEnergySourceReports` is a no-op.
- `logEnergySourceReports` uses reflection for `getValue`/`getReportMonitorValue` (still compiles).
- Log tag: `[ECM-DIAG3]` — will not appear in logs.

**Diagnostic wiring in `executeElementWise()`:**
- After autoConfigureJellyRollEnergySource loop → `diagProfileMethodType`, `getOrCreateEnergySourceReports`
- After `applyElementWiseHeatCsv` call → `logEnergySourceReports`

### STAR 2602 API incompatibilities (confirmed 2026-05-26)

| Symbol | Status | Fix applied |
|--------|--------|-------------|
| `star.common.NeoObjectInterface` | **REMOVED** in STAR 2602 | Use reflection to call `getPresentationName()` |
| `star.common.ReportManager` | **MOVED** (package changed) | DIAG-3 stubbed out; use `var` if re-enabling |
| `star.base.report.Report.getValue()` | **REMOVED** | Use reflection: try `getValue` then `getReportMonitorValue` |
| `TableManager.createTable(Class)` | Deprecated (warning only) | Still compiles; fix later |

**FIXED 2026-07-06**: `autoConfigureJellyRollEnergySource` now uses `phys.getModelManager().getModel(SegregatedSolidEnergyModel)` → `getUserVolumeSourceOption()` / `getVolumetricHeatSourceProfile()`. Root cause: `EnergyUserVolumeSourceOption` is a property of the energy model, NOT the region/continuum TypedObjectManager. The old `region.get()` / `continuum.get()` path never worked in BDS or segregated-solid cases. Fix synced to all 4 copies; `diagProfileMethodType` also fixed.

### Overlap-weighted mapping (implemented 2026-05-26)

`ecm_mapping.csv` has **multiple rows per boundary cell** (weight = partial volume [m³]):
- Boundary cells (35.3%): 2–3 rows with partial-volume weights summing to V_cell
- Interior cells (64.7%): 1 row, weight = V_cell
- 2170 mesh: 30,131 rows for 21,552 cells, avg 1.40 per cell
- Volume conservation verified: 0.0000% error

Python `distribute_qvol_to_mesh()` already handles overlap: `qVol_cell = Σ(qVol_k×w_k)/Σ(w_k)`.
T aggregation also overlap-correct: `T_zone = Σ(w×T)/Σ(w)`. No Python changes needed.

Stale-mapping check counts **unique meshKey values** (not row count) to handle overlap rows.

`ecm_zone_weights.csv`: X_m, Y_m, Z_m, **regionIdx**, w_zone_0…w_zone_N−1 (fractions [0,1]).
`setupWeightVisualization(sim)` (line 1351): loads this as FileTable, creates 18
`ECM_Zone_k_Weight` UserFieldFunctions → visible in Tools > Field Functions in STAR-CCM+.

### CellMapper (updated 2026-05-26)
- **Primary path**: reads `ecm_cell_map.csv`; but first pre-extracts XYZ T-table to get live cell count.
  If CSV count != T-table rows (mesh re-meshed), discards CSV and rebuilds from T-table instead.
- **createFromXyzTable()**: builds CellMapper from XYZ T-table X/Y/Z columns.
- **No FvRepresentation fallback** — removed (broken in STAR 2602). Throws FATAL if both CSV and T-table unavailable.
- Stores: `int[] cellIds`, `double[] x/y/z` (centroids), `double[] volumes` (per-cell m³), `Region region`
- Lazy fields: `tableRowToMapperIndex[]` (coord-hash match, built once), `tColumnIndex`

#### Per-cell volumes — full chain (2026-05-26, complete)
`ecm_cell_map.csv` has 5th column `volume_m3`. `extractVolumes()` path order:
1. **T-table primary (Path A)**: reads any column named `*volume*`/`*vol*`/`*cellvol*` from `ECM_jellyRoll_T_Table`. Requires user to add "Cell Volume" scalar to that table in STAR GUI once. Uses proven `getSeriesArray()` path.
2. **FvRep (Path B)**: tries `CellVolume`/`Volume`/`Cell Volume`/`CellVol` field function. May fail in STAR 2602.
3. **Uniform fallback (Path C)**: `JELLY_ROLL_VOLUME_M3/n`. Emits 3 WARN lines. Cannot be missed.

On CSV re-read: if all volumes equal within 1 ppb (previous fallback), re-calls `extractVolumes()` automatically in case user has since added T-table scalar.

`writeQVolInjectionCsv()`: uses `cellMapper.volumes()[i]` per cell for W→W/m³ (not uniform).
`ecm_coupler.py _maybe_regen_mapping()`: reads `volume_m3` as zone assignment weight.
`ecm_coupler.py` W/m³→W conversion: `Q_cell = qvol_zone × actual_V_cell` (exact round-trip through Java division). Cached in `_CELL_VOL_CACHE` (not rebuilt every step).
`applyElementWiseHeatCsv()` diagnostic: computes qVol range from actual per-cell volumes.

### T extraction path (confirmed fast, implemented 2026-05-21, session_20260521)
```
XyzInternalTable table = sim.getTableManager().getTable(T_TABLE_NAME)
table.extract()                        → warm=7–8 ms, cold=227 ms (one-time)
double[] temps = getSeriesArray(sim, table, tColumnIndex)  → ~4 ms for 160313 cells
```
`getSeriesArray()` (new static helper in CellMapper, ~line 1688) tries:
  1. `table.getSeriesData().getSeries(int)` → double[]  ← fast path (4 ms)
  2. `getSeriesData().getSeriesObject(int)` → DoubleVector → toDoubleArray()
  3. Any DoubleVector method with (int) param via reflection
  4. Slow per-row `getValueAt()` fallback with WARN log
Column 0 = Temperature(K) (STAR 2602 confirmed; tColumnIndex cached after first call).
`extract()` is NOT needed on same-timestep re-calls (data identical — confirmed TestV4).

### buildTableToMapperMapping fast path (2026-05-21)
X, Y, Z columns are bulk-read once via `getSeriesArray()` before any matching.
- Spot-check (200 rows): uses array indexing, not per-row API calls
- Full scan (if needed): array indexing, not 480k `getValueAt()` calls
- Diagnostic prints: use cached array values
Result: coordinate mapping build cost drops from ~480k API calls to ~3 bulk reads.

### EcmBinaryIO inner class (line 1948)

| Method | Purpose |
|--------|---------|
| `writeLumpedInput(path, stepId, tEff, time, dt, I, qAhInit)` | 1-record ecm_in.bin |
| `readLumpedOutput(path, stepId)` → `double` | reads qVol [W] from 1-record output |
| `writeElementWiseInput(path, stepId, cellIds[], temps[], time, dt, I)` | N-record ecm_in.bin (delegates to buildElementWiseInputBytes) |
| `buildElementWiseInputBytes(stepId, cellIds[], temps[], time, dt, I)` → `byte[]` | build N-record frame bytes (used by pipe + file paths) |
| `readElementWiseOutput(path, stepId)` → `Map<Int,Double>` | N-record output; null on stepId mismatch (delegates to readElementWiseOutputBytes) |
| `readElementWiseOutputBytes(byte[], stepId)` → `Map<Int,Double>` | parse N-record response from byte array (used by pipe + file paths) |
| `atomicWrite(path, bytes)` | write to .tmp then atomic rename |

Binary format: magic `ECMIOv1\0` + v2 header (52 bytes) + inputs section + N×(int32 key + double value).

### PersistentEcmProcess — elementWise support (added 2026-05-21)
- `exchangeElementWise(sim, inputBytes, expectedStepId, debugLog)` → `Map<Int,Double>`
  Sends pre-built N-record frame over pipe; reads N-record response via `readElementWiseOutputBytes()`
- `executeElementWise()` now tries persistent pipe first, falls back to file-based if pipe fails
- Previously persistent process was immediately closed for elementWise ("not supported" abort)

---

## Python ECM backend

Three `ecm_coupler.py` copies — all must be kept in sync:
- `in/starCCM_10C_experiment_twoCells/ecm/ecm_coupler.py` — **primary STAR-CCM+ copy** (~2700 lines, most advanced)
- `rev4/python/ecm_coupler.py` — **actual OpenFOAM runtime copy**
- `ecm/ecm_coupler.py` — workspace root copy (kept in sync with twoCells copy)

### Per-region ECM params (added 2026-06-02)
Multi-region `parallelBranchesSharedSOC` path now supports per-region overrides:
- `params_r{N}.csv` — per-region OCV/R0/R1/C1/dUdT lookup (falls back to `params.csv`)
- `cellprops_r{N}.csv` — per-region capacity/properties (falls back to `cellprops.csv`)
- `ECM_CURRENT_R{N}` env var — per-region applied current (falls back to shared `current_a`)
- All fallbacks print uppercase WARNING to stderr — never silent.

`ecm_step.py` also exists in all three locations:
- `in/starCCM_10C_experiment/ecm/ecm_step.py` — source of truth (1027 lines, client-supplied)
- `rev4/python/ecm_step.py` — must match source of truth
- `ecm_step.py` (workspace root, used by ecm/) — must match source of truth

### Top-level functions (STAR-CCM+ copy line references)

| Function | Purpose |
|----------|---------|
| `compute_q_out(h, inputs, keys, temps)` line 995 | Main dispatch; returns `list[float]` of per-cell W |
| `run_ecm_step_per_partition(...)` line 555 | N independent ECM states (one per partition) |
| `run_ecm_step_shared_state(...)` line 632 | Single ECM state, shared across all cells |
| `run_ecm_step_parallel_branches(...)` line 824 | Parallel RC branches per cell |
| `run_ecm_step_parallel_2rc(...)` line 719 | **(NEW)** Parallel 2RC zones, KCL/KVL solved analytically |
| `aggregate_ecm_temperatures(...)` line 307 | Partition T aggregation |
| `distribute_qvol_to_mesh(...)` line 346 | Partition qVol → per-mesh-cell W |
| `run_file_mode()` line 1524 | Entry when called as subprocess (reads ecm_in.bin) |
| `run_pipe_mode()` line 1557 | Entry for persistent-process stdin/stdout mode |

### elementWise distribution modes (`ECM_DISTRIBUTED_ELECTRICAL_MODE`)
- `"sharedState"` (default) — single SOC/T, uniform heat (wrong distribution)
- `"partitionStates"` — N independent SOC per partition
- `"parallelBranches"` — parallel RC branch model (per-cell)
- `"parallel2rc"` — **(NEW 2026-05-22)** all zones treated as electrically parallel branches sharing
  a common terminal voltage; branch currents solved analytically via KCL/KVL from per-zone
  temperature-dependent impedance. Uses `parallel_2rc_step` from `ecm_step.py`.

### `parallel2rc` mode — implementation details (2026-05-22)
- `run_ecm_step_parallel_2rc(ecm_ids, ecm_temps_k, dt_s, current_a, partition_states,
   partition_volumes, params_df, cellprops_df, lookup_cache, total_vol_override=0.0)`
- Available in all three ecm_coupler.py copies (ecm/, rev4/python/, in/starCCM_10C_experiment/ecm/)
- **`total_vol_override` fix**: OpenFOAM mapping files use `weight=1.0` per cell (not m³).
  `partition_volumes[i]` = cell count. Passing `V_jellyroll_m3` from controlDict `electricalInputs`
  as `total_vol_override` causes correct vol_scale = V_jellyroll_m3 / n_cells_total.
  STAR-CCM+ weights ARE actual m³ so vol_scale ≈ 1.0 (no-op there).
- **Voltage logging fix** (2026-05-22): diag dict key changed from `"V_TERMINAL_V"` to
  `"V_common_V"` (+ `"V_branch_min_V"`, `"V_branch_max_V"`, `"I_branch_sum_A"`).
  Applied to all three ecm_coupler.py copies.
- **Sign convention** (CONFIRMED 2026-05-22): `pack_current_a = float(current_a)` directly.
  Positive current_a = DISCHARGE in parallel_2rc_step. The params table Q_Ah is traversed
  in the discharge direction as q_ah increases from 0 (SOC=1) with positive current.
  `q_ah_to_soc` helper shows SOC>1 during discharge (diagnostic bug) but physics/heat is CORRECT.
  Negative current would look up outside params table range → wrong. Keep positive = discharge.
- **10C OpenFOAM run confirmed** (2026-05-22): dist_3600_fulllog_iso25_exp10C_parallel2rc
  - 30240 cells, 18-zone overlap mapping, fixed dt=0.1s, endTime=100s
  - At t=100s: T_mean=310.73 K (+12.6 K), T_max=332.5 K, Q_total=29.3 W
  - vs experiment: mean T ~2.7°C under-prediction at 100s (further investigation needed)

### OpenFOAM 10C case directory
- `rev4/dist_3600_fulllog_iso25_exp10C_parallel2rc/` — NEW parallel2rc run (100s)
- `rev4/dist_3600_fulllog_iso25_exp10C/` — old parallelBranches reference (full 287s)
- Mapping file: `caseLong_dt02_h110_distributed_debug500_overlap/ecm/mapping_table_axial6_radial3_caseLong_overlap.csv`
  (38160 rows, actual volumes ~7e-10 m³/cell, total jellyRoll vol=2.165e-5 m³, 30240 cells)
- Electrical inputs: `constant/electrical_inputs_experimental_10C_discharge.csv` (50A, init_soc=1)

### What "distributed" means — CONFIRMED DEFINITION (2026-05-21)

**Distributed = each ECM zone has its own LOCAL temperature input AND its own LOCAL heat output.**

This means `partitionStates` mode:
- Spatial zones (e.g. axial slices of jelly roll) are defined in a mapping file
- Each zone aggregates temperatures from its member cells → one T per zone
- Each zone runs its own independent ECM step → own Q_GEN, own SOC, own RC voltages
- Each zone's Q_GEN is distributed back to its member cells (R0(T)-weighted within the zone)

**What the current `sharedState` mode does (WRONG for distributed):**
- Collapses ALL 160,313 temperatures into one `T_avg = mean(T[i])`
- Runs ONE ECM step with `T_avg` → ONE `Q_total`
- Distributes `Q_total` across cells by `R0(T[i])` weighting
- The ECM state (SOC, RC voltages, OCV) has NO knowledge of spatial temperature variation
- This is `sharedState` mode — it is a single-zone lumped electrical model, not distributed

**Why T_avg is not sufficient:**
- OCV, R0, R1, R2, dU/dT all depend on T
- A cell with a 5 K internal gradient can have 10–15% variation in R0 across zones
- This means local Q_GEN varies spatially in a way that T_avg cannot capture
- Using T_avg underestimates heat in the coldest zones and overestimates it in the hottest

**Correct architecture for distributed (per zone `z`):**
```
1. For each zone z: T_eff[z] = volume_average(T[i] for i in zone z)
2. For each zone z: run ECM(T_eff[z], I, SOC_z_prev, ...) → SOC_z_new, Q_z [W]
3. For each cell i in zone z:
     weight[i] = R0(T[i]) * V_cell[i]
     Q[i] = Q_z * weight[i] / sum(weight in zone z)
4. Write N-record ecm_out.bin with Q[i] per cell
```

**Note on shared vs per-zone SOC:**
- Rigorously, SOC should be global (one value per cell) as charge is conserved globally
- But using per-zone SOC is a reasonable approximation for large temperature gradients
- Current `partitionStates` mode uses per-zone SOC — acceptable for the target use case

### State persistence
- File: `ecm_state.json` (path via `ECM_STATE_FILE` env)
- Reset: `ECM_STATE_RESET=1`
- In partitionStates mode: dict keyed by partition/cell ID

---

## Binary protocol summary

```
ecm_in.bin  (fileType=1):  header(52B) + inputs_section + N×(int32 cellId + double T_K)
ecm_out.bin (fileType=2):  header(52B) + echoed_inputs  + N×(int32 cellId + double qVol_W)
```
- `keyMode=0` (KEY_MODE_GLOBAL) — used in all current code
- Record unit: **W per cell** (not W/m³); Java sums for total power
- stepId echoed back by Python; mismatch → Java keeps previous qVol

---

## Mesh / geometry facts

- Mesh file: `debugCase.sim` (`in/starCCM_10C_experiment/`)
- jellyRoll: **160,313 cells** (fine mesh); coarse mesh used in testing: **10,475 cells**
- cap: 36,767; can: 154,635 (fine mesh)
- CGNS export: `jellyRollMesh.cgns` (92 MB)
- Cell map tool: `in/starCCM_10C_experiment/ecm/cgns_cell_map.py` → `ecm_cell_map.csv`
  (Note: NOT under tools/ — co-located with ECM files)
- XYZ table name in .sim: `ECM_jellyRoll_T_Table` (XyzInternalTable, Parts=jellyRoll)

### ECM mapping files (generated 2026-05-21)

| File | Description |
|------|-------------|
| `in/starCCM_10C_experiment/ecm/ecm_cell_map.csv` | 160,313 rows: cellId, x_m, y_m, z_m (CGNS vertex-mean centroids) |
| `in/starCCM_10C_experiment/ecm/ecm_mapping.csv` | 160,313 rows: meshKey, ecmCellId, weight (18 zones) |
| `in/starCCM_10C_experiment/ecm/gen_ecm_mapping.py` | Mapping generator: reads cell_map → writes mapping |

Zone layout: 6 axial (along X) × 3 radial (r_yz = sqrt(y²+z²)) = 18 zones.
Zone numbering: `ecmCellId = axial_bin * 3 + radial_bin`

**KNOWN ARTIFACT**: end axial zones (ax=0 and ax=5) have ~12.7k cells vs ~4.8k middle.
Cause: CGNS vertex-mean centroid ≠ STAR volumetric centroid for polyhedral end-face cells.
Fix: after first STAR run, self-heal overwrites ecm_cell_map.csv → re-run gen_ecm_mapping.py.

---

## What is done vs outstanding

### Done
- [x] T extraction: `XyzInternalTable.extract()` + `TableData.getSeries(int)` — 3 ms/step
- [x] `EcmBinaryIO.writeElementWiseInput()` + `readElementWiseOutput()` — full N-record I/O
- [x] `executeElementWise()` loop — per-step extract → write → call → read → merge
- [x] Per-step diagnostic CSV (`writeStepCsv`)
- [x] Binary protocol in Python (`ecm_io.py`) — supports N-record elementWise natively
- [x] `partitionStates` Python backend — N independent ECM state machines already written
- [x] **Coordinate mismatch FATAL fix** (2026-05-21 session 2):
  - `buildTableToMapperMapping()`: when hash-match rate <90%, no longer throws FATAL.
  - Falls back to identity mapping (table row r → mapper index r). Safe: both CGNS and
    XYZ table enumerate jellyRoll in STAR internal cell order.
  - Self-heals: overwrites CellMapper.x/y/z from table XYZ so next `writeCellMapCsv()`
    writes STAR volumetric centroids → second run gets perfect hash-match (silent).
  - Root cause documented: `cgns_cell_map.py` vertex-mean ≠ STAR volumetric centroid for
    polyhedral cells; diff > 10 µm (hash bucket) → 92% miss → old FATAL.
- [x] **`buildTableToMapperMapping()` + T-read speed fixes** (2026-05-21):
  - T column: replaced per-row `getValueAt()` loop with `getSeriesArray()` bulk read (~4 ms for 160k)
  - Coordinate mapping: bulk-read X,Y,Z once each via `getSeriesArray()`; spot-check (200 rows)
    and full scan both use array indexing — no per-row API calls anywhere in mapping build
  - New `getSeriesArray()` static helper in CellMapper (~line 1688) with 3-path reflection fallback
  - Log: `[ECM-EW] Identity mapping confirmed via spot-check (200 samples...)`

### STAR-CCM+ vs OpenFOAM — fundamental field injection difference

**OpenFOAM** owns the field memory directly:
- `ecmQdot` is a `volScalarField` living in the solver's memory
- Per-cell write is a direct array assignment: `qField[cellI] = qApplied` (ecmCoupler.C:2925)
- No file I/O, no table reload — just a pointer dereference into a C++ `scalarField`

**STAR-CCM+** Java macro API has NO direct memory write path (all confirmed dead in STAR 2602):
- P1 UserDataSet — NOT_FOUND; P2 ArrayScalarFieldFunction — NOT_FOUND
- P3 XyzInternalTable.setValueAt() — call OK, value does NOT persist (confirmed TestPhase3FieldInjection.java May 21)
- Only working injection: **CSV-reload** (~5 MB CSV write + table recreation every step)
- Root cause: Java macro is a remote client over socket protocol — no pointer into solver arrays

**Target solution: C++ UserLibrary** (plan at `in/starCCM_10C_experiment/notes/userlibrary_injection_plan.md`):
- Compiled `.dll` loaded directly into STAR solver process — same address space
- `ucfunc("ecmQdot_uf", "ScalarFieldFunction", ...)` registers per-cell native field function
- C++ reads from memory-mapped binary file Python writes (~1.28 MB, ~1 ms, no CSV)
- Java does R0(T)-weighted distribution internally; ECM I/O collapses to 1 record (~100 bytes)
- Estimated effort: ~2–3 days C++ development
- **Key risk**: license expires 2026-05-26 — need prototype before then

### Outstanding (in order)
0. **[DONE] Fix 1 — Zone mapping auto-regen** (2026-05-22):
   - `_maybe_regen_mapping()` added to ecm_coupler.py (~line 250). Called from `_get_mapping()` before cache lookup.
   - Trigger: `ecm_cell_map.csv` mtime > `ecm_mapping.csv` mtime (or mapping absent).
   - Runs once per process (gated by `_REGEN_CHECKED` set). Atomic write (.tmp → rename).
   - After Java self-heals `ecm_cell_map.csv` (run 1), run 2's first coupling step will auto-regen mapping.
   - Log: `[ecm_coupler] ecm_cell_map.csv is newer ... regenerating mapping (6×3 zones) ...`
   - Log: `[ecm_coupler] Mapping regenerated: 160313 cells → 18 zones, NNN–MMM cells/zone`
   - Zone counts controllable via `ECM_MAPPING_AXIAL` / `ECM_MAPPING_RADIAL` env vars (default 6×3).
   - Cell map path: `ECM_CELL_MAP_CSV` env var or same dir as `ECM_MAPPING_FILE` / `ecm_cell_map.csv`.

0b. **[DONE] Fix 2-B — Physics bug in `run_ecm_step_per_partition()`** (2026-05-22):
   - Was: `current_i = I × vol_frac` → `q_ir ∝ vol_frac²` causing large negative qVol in small zones.
   - Fix: run `_ecm_step_fn` with full `current_a` (not scaled) and full `capacity_total` (not scaled).
     Multiply `Q_GEN × vol_frac` after the call. Both q_ir and q_rev now scale linearly with vol_frac.
   - All zones will show positive qVol (same sign as full-cell Q_GEN).
   - **LICENSE EXPIRES 2026-05-26** — Fix 1 (mapping regen on Windows) must happen before then.

1. **[DONE] Unit mismatch fix in partitionStates path** (2026-05-21 session 4):
   - Root cause: `distribute_qvol_to_mesh` returns W/m³ per cell; `ecm_out.bin` protocol requires W per cell.
     Java receives W/m³, treats as W, then divides by V_cell → CSV qVol is ~6.8e9× too large.
   - Fix: in `compute_q_out` (ecm_coupler.py line ~1389), after `distribute_qvol_to_mesh`, multiply
     each per-cell value by V_cell = total_vol/n_cells to convert W/m³ → W.
   - `_get_partition_volumes()` is cached so this is cheap.
   - Diagnostic: Python `qVol_min_Wm3` in ecm_diag is still the zone W/m³ (correct for display);
     the per-cell values written to ecm_out.bin are now W.
   - `autoConfigureJellyRollEnergySource` **FIXED 2026-07-06**: now uses `getModelManager().getModel()` path.
     Old `region.get()` / `continuum.get()` TypedObjectManager lookups removed.
     Root cause confirmed via clientTest.sim inspection: option IS Selected:1 but not in TypedObjectManager;
     it is a property of the energy model object and must be accessed via the model, not the continuum.

2. **[DONE] CSV injection + R0-weighted distribution** (2026-05-21 session 3):
   - `INJECTION_MODE` default changed from `"globalParam"` → **`"csvReload"`** (line 158 of Java).
   - Python `compute_q_out()` stub replaced with **R0(T[i])-weighted distribution**
     (`in/starCCM_10C_experiment/ecm/ecm_coupler.py`, line ~1507).
   - All 3 Java copies synced. CODE_SUMMARY.md updated.
   - On next STAR-CCM+ run: watch for `autoConfigureJellyRollEnergySource` messages at startup
     to confirm energy source wiring succeeded.
   - Per-step log will show: `q=[min..max] W (R0-weighted)` and `csvReload: write=... ms`.

2. **[OPEN] writeCellMapCsv() called before extract()** — self-heal for coordinate mismatch
   never persists because CSV is written at startup (before the first mismatch is detected).
   Need to defer `writeCellMapCsv()` to after step-0 coordinate resolution.

3. **C++ UserLibrary for per-cell heat injection** (lower priority now that csvReload works)
   - Plan: `in/starCCM_10C_experiment/notes/userlibrary_injection_plan.md`
   - **LICENSE EXPIRES 2026-05-26** — if csvReload is verified working, C++ path deprioritised

4. **Cell ID stability** — confirm `CellMapper` sequential IDs stable across timesteps

---

## `multi_cell_parallel` mode — IMPLEMENTED AND VERIFIED (2026-05-24)

### What it does
M physical battery cells (M=1 today), each with N=18 spatial zones.
- All zones of a cell share ONE SOC (cell-global charge conservation)
- Per-zone T drives per-zone Q_GEN via `multi_cell_parallel_step` from `ecm_step.py`
- All M×N calcs in one vectorized call

### Implementation location
`rev4/python/ecm_coupler.py` — function `run_ecm_step_multi_cell_parallel()`
Dispatch mode: `ECM_DISTRIBUTED_ELECTRICAL_MODE=multi_cell_parallel`
Env config: `ECM_N_CELLS=1` (number of physical battery cells M)

### Key bugs fixed during implementation

**Bug 1: Wrong q_ah initialization**
- Wrong: `np.full((M, n_parallel), soc_init * q_nom_slice)` (gives 0.2778 for SOC=1, wrong sign)
- Fixed: `np.full((M, n_parallel), soc_to_q_ah(soc_init, q_nom_slice))` (gives 0.0 for SOC=1)

**Bug 2: Garbage `init_soc` from C++ binary pipe**
- C++ sends `init_soc` field as near-zero float (~5.6e-310) from CSV interpolation (only t=0 has value 1.0, rest is NaN)
- 5.6e-310 passes [0,1] range check → soc_to_q_ah(~0, q_nom) = -q_nom → cell starts discharged
- Fix: `mc_state_stored = state.get("mc_parallel", {"soc_init": 1.0})` (ignore inputs["init_soc"] entirely)
- SAFE FOR RESTARTS: default dict only used when `mc_parallel` key is absent from state file (first step only)
- After step 1: `mc_parallel` key is always present in `ecm_state.json` → restart always uses actual q_ah

**Bug 3: Per-zone SOC divergence**
- Hot zones → lower R0 → higher branch current → more q_ah per step → SOC diverges ±0.5 in 300s
- Fix: average q_ah across zones after each step (enforces shared per-cell SOC):
  ```python
  q_ah_cell_mean = np.mean(q_ah_next, axis=1, keepdims=True)  # (M, 1)
  q_ah_next = np.broadcast_to(q_ah_cell_mean, (M, n_parallel)).copy()
  ```

**Bug 4: `n_partitions=0` in voltageHistory**
- Diag dict was missing `"n_partitions"` key → defaulted to 0
- Fix: add `"n_partitions": n_total` to diag dict

### State convention (`multi_cell_parallel_step`)
- `q_ah` starts at 0 (full charge), increases POSITIVELY during discharge
- `SOC = 1 - q_ah / q_nom_slice` (correct formula, NOT `1 + q/q_nom`)
- `soc_to_q_ah(soc, q_nom) = -q_nom * (1-soc)` → returns 0 for soc=1.0
- Internal voltage: KCL returns V_TERMINAL > V_OCV (artifact of sign convention) — physics correct
- Logged voltage: `V_OCV_DCH - V_OP` (gives physically correct below-OCV discharge curve)

### Verified results (300s test, `dist_3600_fulllog_iso25_exp10C_multiCellParallel_20260524`)
- SOC at t=300s: 0.1667 = 50A × 300s / 3600 / 5Ah ✓ (exact theoretical match)
- v_common_v: 2.50–3.72 V (physically correct discharge curve)
- Q_total: 20–42 W (reasonable)
- n_partitions: 18 ✓
- Voltage RMSE vs experiment: 0.057 V (MultiCell), 0.041 V (Lumped)
- Comparison plot: `artifacts/plots/10c_dirKfix_vs_exp_20260524_*.pdf`

### Case directory
- `rev4/dist_3600_fulllog_iso25_exp10C_multiCellParallel_20260524/` — verified, endTime=300s
- controlDict command: `ECM_DISTRIBUTED_ELECTRICAL_MODE=multi_cell_parallel ECM_N_CELLS=1`

### Future work
- Test with M>1 cells (M=2 or 3)
- Consider `ECM_INIT_SOC` env var for non-100% SOC initialization
- Before production use of `multi_cell_parallel` with M=1, re-examine capacity normalisation and voltage convention vs `parallelBranches` reference

### Discrepancy report (2026-05-24)
`artifacts/reports/ecm_mode_discrepancy_parallelBranches_vs_multiCellParallel.md/.pdf`
Summary: `parallelBranches` RMSE=0.033 V vs `multi_cell_parallel` RMSE=0.057 V (72% higher).
Root causes: (1) multi_cell_parallel averages SOC across zones every step → kills spatial SOC gradient; (2) voltage convention differs (V_OCV_DCH - V_OP vs direct V_T from bisection); (3) capacity normalisation via q_nom_slice introduces rounding; (4) analytic current split vs exact bisection.

### Code backup (2026-05-24)
`artifacts/packs/ecm_code_backup_20260524_185154.zip` — 287 files, ~2 MB
Includes: all 3 ecm_coupler.py copies, ecm_step.py, Java macros, C++ OF sources, tools/

---

## `parallelBranchesSharedSOC` mode — IMPLEMENTED AND FIXED (2026-05-24)

### What it does
Same as `parallelBranches` (bisection V_common, per-zone R0(T)/RC current distribution) but
enforces global charge conservation: all 18 zones share a single cell-level SOC after each step.
v_rc and hysteresis remain per-zone.

### Dispatch
`ECM_DISTRIBUTED_ELECTRICAL_MODE=parallelBranchesSharedSOC` (in `rev4/python/ecm_coupler.py`)

### CRITICAL BUG FIXED (2026-05-24): Non-uniform volume SharedSOC
**Wrong (original):** arithmetic mean `q_ah_mean = sum(q_ah_zone_i) / 18`
- For non-uniform zones (vol_frac range 0.0135–0.1117), this incorrectly over-assigns q_ah to
  small zones. Zone 9 (cap=0.0675 Ah) hits its ceiling immediately → SOC plateaus at ~0.01 Ah.

**Correct (fixed code at line ~1492 of `rev4/python/ecm_coupler.py`):**
```python
if shared_soc:
    q_ah_cell_new = sum(q_ah_next_list)  # sum(vol_frac)=1 → this IS cell-level q_ah
    q_ah_cell_new = max(0.0, min(q_ah_cell_new, capacity_total))
    for b in branch_meta:
        next_states[str(b["ecm_id"])]["q_ah"] = q_ah_cell_new * b["vol_frac"]
```
This ensures `q_ah_zone_i / vol_frac_i = q_ah_cell` (identical SOC for all zones in OCV lookup).

### Verified results (300s, 10C, dirKfix BCs)
- Fresh start V_common = 3.7074 V ✓
- Final V_common = 2.389 V (complete discharge) ✓
- Final Q_total = 36.30 W (vs 37.4 W for parallelBranches — ~3% difference)
- **Voltage RMSE vs experiment: 0.0347 V** (vs 0.0332 V parallelBranches, 0.0406 V lumped)
- Case: `rev4/dist_3600_fulllog_iso25_exp10C_parallelBranchesSharedSOC_dirKfix_20260524/`
- Comparison plot: `artifacts/plots/parallelBranches_vs_sharedSOC_10C_20260524_*.pdf`

### Mode comparison summary (10C, dirKfix, 300s)
| Mode | RMSE vs exp | Notes |
|------|-------------|-------|
| parallelBranches | 0.0332 V | Best; per-zone SOC drift allowed |
| **parallelBranchesSharedSOC** | **0.0347 V** | Near-identical; enforces global charge |
| Lumped | 0.0406 V | Simple; no spatial SOC gradient |
| multi_cell_parallel | 0.057 V | Higher error; see discrepancy report |

---

## Multi-Battery Cell Support — IMPLEMENTED (2026-05-24)

### Python ECM changes (`rev4/python/ecm_coupler.py`)

**`ECM_CELL_ID` env var support** (single string, e.g. "0", "1", "cell_a"):
- Read at the top of `compute_q_out()` as `cell_id = os.environ.get("ECM_CELL_ID", "").strip()`
- Passed to `_emit_ecm_diag_line(diag, cell_id=cell_id)` → prepends `cell_id=N` to `[ecm_diag]` log lines
- Passed to `_append_voltage_history(..., cell_id=cell_id)` → adds `cell_id` column to `voltageHistory.csv`
- Log lines also prefixed with `[cell N]` when cell_id is set (both distributed and lumped paths)
- Backward compatible: empty cell_id (default) produces unchanged output

**`voltageHistory.csv` column added**: `cell_id` between `t_eff_k` and `v_common_v`
  - Header: `time_s,delta_t_s,step_id,current_a,t_eff_k,cell_id,v_common_v,...`
  - Old files without this column will be empty-string for cell_id

### New utility scripts

| Script | Purpose |
|--------|---------|
| `tools/aggregate_multicell_voltage.py` | Merge per-cell voltageHistory CSVs → multicell summary CSV with v_pack, q_pack, t_delta |
| `tools/plot_multicell_comparison.py` | 4-panel comparison: T per cell, Q per cell, V per cell + V_pack, SOC per cell |

**Usage:**
```bash
# Aggregate per-cell voltageHistory into one summary CSV (series config)
python3 tools/aggregate_multicell_voltage.py \
  ecm/cell0/voltageHistory.csv ecm/cell1/voltageHistory.csv \
  --series --output artifacts/plots/multicell_summary.csv

# 4-panel comparison plot
python3 tools/plot_multicell_comparison.py \
  --voltage-history ecm/cell0/voltageHistory.csv ecm/cell1/voltageHistory.csv \
  --cell-labels cell0,cell1 \
  --series
```

### Architecture for multi-cell OpenFOAM runs

One `ecmCoupler` block per cell in controlDict:
```cpp
ecmCoupling_cell0 { region jellyRoll_0; zone jellyRoll_0;
  command "... ECM_CELL_ID=0 ECM_STATE_FILE=ecm/cell0/ecm_state.json ..."; }
ecmCoupling_cell1 { region jellyRoll_1; zone jellyRoll_1;
  command "... ECM_CELL_ID=1 ECM_STATE_FILE=ecm/cell1/ecm_state.json ..."; }
```
Each cell directory (`ecm/cell0/`, `ecm/cell1/`) holds its own state and voltageHistory.
For series config: all cells receive same `current_A` from shared electrical inputs CSV.

---

## Process Rules — Session Closing

**MANDATORY on every "close session" / "end session" command:**
1. Write `artifacts/logs/session_YYYYMMDD_HHMMSS.log` summarising what was done
2. Update `/workspace/MEMORY.md` (this file) with any stable new facts
3. Append to `artifacts/logs/decision.log` if architectural decisions were made
4. Then (and only then) acknowledge closure

---

## Thermal Properties Setup (2026-05-23 Session)

**Validated OpenFOAM case identified** for thermal setup reference:
- Path: `rev4/caseLong_dt02_h110_distributed_parallelBranches_nolog200/`
- Validation: 10C discharge test (50 A), experimental agreement confirmed
- Plots: `artifacts/plots/parallelBranches_10C_*.pdf` (May 22)

**Thermal properties (WEDGE_2170 reference):**
- JellyRoll: ρ=2660.7 kg/m³, Cp=835–1586 J/kgK (temp-dep), k_r=1.4 W/mK, k_z=29 W/mK
- Shell: ρ=8000 kg/m³, Cp=500 J/kgK, k=16 W/mK (isotropic)
- Cap: ρ=1447.2 kg/m³, Cp=500 J/kgK, k_r=0.01 W/mK, k_z=0.1 W/mK

**STAR-CCM+ anisotropic thermal conductivity setup:**
- Official reference: Siemens KB000031622
  URL: https://support.sw.siemens.com/en-US/okba/KB000031622_EN_US/
- Java API: `star.energy.AnisotropicThermalConductivityMethodWithValues`
- Tensor mapping (cylindrical): k11=radial, k22=tangential, k33=axial
- Setup: Local cylindrical coordinate system + Orientation Manager + tensor definition
- Comprehensive guide created: `/workspace/STAR_CCM_ANISOTROPIC_THERMAL_CONDUCTIVITY_GUIDE.md`

**Constant 10 W diagnostic cases (2026-05-23, completed t=0–200 s):**
- `rev4/const10W_tabCp_20260523/`  — tabCp (835–1586 J/kgK), iso k=3.84 W/mK → T_mean=299.74 K (+1.59 °C)
- `rev4/const10W_anisoK_20260523/` — Cp=980, anisoK kr=1.4/kz=29 W/mK    → T_mean=302.78 K (+4.65 °C)
- Comparison plot: `artifacts/plots/star_vs_openfoam_tabCp_anisoK_20260523_085450.pdf`
- Script: `tools/plot_star_vs_openfoam_const10w_tabCp_anisoK.py`
- Purpose: isolate effect of thermal property choices on T discrepancy vs STAR-CCM+

**STAR-CCM+ vs OpenFOAM thermal comparison — ROOT CAUSE IDENTIFIED (2026-05-24):**

- **GEOMETRY ORIENTATION — CONFIRMED:**
  - **OpenFOAM**: cylinder (jellyRoll) axis is along **Z**. kappa (1.4 1.4 29) → k_z=29 = axial ✓
  - **STAR-CCM+**: cylinder (jellyRoll) axis is along **X**. eAxial=[1,0,0], k_axial=29, k_transverse=1.4 ✓

- **CONTACT RESISTANCE — CONFIRMED from sim file** (`thermalDebug_variableConductivity.sim`):
  - `jellyRoll/can 2` (bottom face): R = 0.001804785 m²K/W ACTIVE. All other interfaces: R = 0.

- **ROOT CAUSE 1: `kappaMethod solidThermo` is WRONG for anisotropic coupled BCs**
  - Source: `constAnIsoSolidTransportI.H` line 70: `kappa() { return mag(kappa_); }`
  - Returns √(1.4²+1.4²+29²) = 29.07 W/m/K for ALL interface faces (including radial)
  - Correct radial kappa = 1.4 W/m/K; 29.07 is 20× too high
  - Fix: use `kappaMethod directionalSolidThermo; alphaAni Anialpha;` on jellyRoll coupled patches
  - `Anialpha` is auto-created by `chtMultiRegionSolidFoam`/`chtMultiRegionFoam` via `transformPrincipal`
  - With directional kappa: n & (Anialpha × Cp) & n gives k_r=1.4 at radial, k_z=29 at bottom ✓

- **ROOT CAUSE 2: Contact R placement asymmetry in coupled BC**
  - OF `turbulentTemperatureRadCoupledMixed` BC: side WITH R knows about it, side WITHOUT R does not
  - The side without R reads raw cell-center T from neighbor (no R temperature jump visible to it)
  - This asymmetry makes R placement non-symmetric even though physics should be symmetric
  - STAR applies R as a true interface property (no asymmetry)
  - OF equivalent: **R/2 on each side** reproduces STAR's symmetric interface R

- **COMPARISON RESULTS (SS extrapolated, all `rev4/`):**
  | Case | kappa method | R placement | SS ΔT | Gap vs STAR |
  |------|-------------|-------------|-------|-------------|
  | bothSides (original)     | solidThermo  | R+R      | 4.647°C | +0.848°C ✗ |
  | singleSideR (jroll)      | solidThermo  | jroll-R  | 4.763°C | +0.964°C ✗ |
  | dirK_jrollR              | directional  | jroll-R  | 4.155°C | +0.356°C   |
  | **dirK_halfR** ← BEST    | **directional** | **R/2+R/2** | **3.865°C** | **+0.066°C ✓** |
  | STAR target              | — | — | 3.799°C | 0 |
  | noContactR (shell)       | solidThermo  | shell-R  | 3.551°C | −0.248°C   |
  | directionalK (shell)     | directional  | shell-R  | 3.134°C | −0.665°C ✗ |

  - iso k=1.4 (OF vs STAR): −0.06°C → excellent agreement (validates geometry)
  - **Best OF case: `const10W_anisoK_dirK_halfR_20260524` → only 0.066°C from STAR**

- **ACTIONABLE FIX for production aniso cases:**
  1. On all jellyRoll coupled patches: `kappaMethod directionalSolidThermo; alphaAni Anialpha;`
  2. Contact R at jellyRoll/shell_bottom: use **R/2 on EACH SIDE** (not R on one side, not R on both)
  3. `Anialpha` is auto-generated by solver (no manual field needed) — do NOT write custom `alphaAni` file

- **CONFIRMED INSIGNIFICANT — do not revisit:**
  - Cap k (**CONFIRMED CORRECT in sim via global params** `capAxialCond`=0.10, `capRadialCond`=0.01 W/mK → geometric mean 0.0215 — already correctly set), geometry, BCs, heat source, axis orientation — all confirmed matched.

**STAR diagnostic traces (in/starCCM_10C_experiment/):**
- `temp_variableCond.csv`  — const10W, aniso k (variableCond sim), SS ΔT=3.799°C — PRIMARY COMPARISON TARGET
- `temp_allCondRadial.csv` — const10W, iso k=1.4 jellyRoll, SS ΔT≈4.28°C → agrees with OF ✓
- `cpVariableTemp.csv`     — const10W, var Cp(T), SS ΔT=1.61°C ← matches OF tabCp ✓
- Debug sim file: `in/starCCM_10C_experiment/thermalDebug_variableConductivity.sim`
- Analysis script: `tools/plot_star_new_thermal_props_comparison.py`

**Test cases (2026-05-23/24, all in `rev4/`):**
- `const10W_anisoK_20260523` (solidThermo, both-R): 4.632°C — original broken case
- `const10W_anisoK_noContactR_20260523` (solidThermo, shell-R): 3.545°C
- `const10W_anisoK_singleSideR_20260523` (solidThermo, jroll-R): 4.747°C
- `const10W_anisoK_directionalK_20260524` (directional, shell-R): 3.134°C
- `const10W_anisoK_dirK_jrollR_20260524` (directional, jroll-R): 4.155°C
- `const10W_anisoK_dirK_halfR_20260524` ← BEST: (directional, R/2+R/2): 3.865°C ✓
- `const10W_anisoK_anisoCapFix_20260523` (aniso cap k): 4.618°C (cap k not the cause)
- `const10W_swappedK_20260523` (kappa 29 29 1.4): 0.259°C (confirms axis=Z in OF)
- `const10W_axialKx_20260523` (kappa 29 1.4 1.4): 0.467°C

---

## Plot Registry Rule (added 2026-05-25)

**Every plot saved to `artifacts/plots/` must have a registry entry.**
- File: `artifacts/plots/PLOT_REGISTRY.md` (created 2026-05-25)
- Rule written into `CLAUDE.md` under "Operating rules"
- After saving a plot: append `| <filename> | <script> | <description> |` to the registry
- Generating script for comparison plots: `tools/plot_starccm_vs_openfoam_10c.py`

---

## Clean CSV Time-History Outputs (added 2026-05-25)

Three dedicated, restart-safe CSV files added to the STAR-CCM+ ECM coupler:

| File | Schema | Source | Restart |
|------|--------|--------|---------|
| `ecm/tempLog.csv` | `time_s,temp_c` | STAR `VolumeAverageReport` on jellyRoll (Java) | Overwritten at run start |
| `ecm/appliedTotalHeatLog.csv` | `time_s,applied_total_heat_w` | Relaxed qVol W set on `ecmQdot_W` (lumped) or sum-cell W (EW) (Java) | Overwritten at run start |
| `ecm/voltageLog.csv` | `time_s,v_common_v` | ECM `V_common_V` from Python backend | Truncated when `step_id == 1` |

Key implementation points:
- `tempLog.csv` uses `tReport.getValue()` (VolumeAverageReport), NOT T_eff_K from ECM binary protocol
- `appliedTotalHeatLog.csv` logs `qVol` (after ALPHA relaxation) in lumped mode, `totalW` (sum cell W) in EW mode
- `voltageLog.csv` written by `_append_voltage_log()` in `ecm_coupler.py`; step_id==1 triggers truncate
- Both Java loops (lumped + EW) open CSVs with overwrite at startup, close at loop end
- EW loop now also creates `getOrCreateTReport(sim, region)` for the tempLog source
- Provenance: `artifacts/logs/csv_output_provenance_20260525.md`

---

## STAR vs OF Lumped Comparison Notes (2026-05-25)

- **dt difference (STAR=0.2s vs OF=0.1s) is NOT the cause of T discrepancy** — confirmed irrelevant by user.
- `final.sim` was saved at the **final time** of the simulation (end state, not fresh t=0).
  This means `ecmQdot_W` inside the .sim is the end-of-run value (~29W), NOT zero.
  When STAR re-runs from t=0 IC using this .sim, **step 1 applies stale ~29W** before the first ECM call — causing immediate T elevation vs OF (which always starts from ecmQdot=0).
- Heat injection mode for this run: **csvReload (FileTable / table setup)** — STAR writes (X,Y,Z,qVol_W_m3) CSV each step, loaded via `ECM_jellyRoll_Q_Table`.
- `appliedTotalHeatLog.csv` logs ECM output W — NOT the actual domain-integrated heat (which is qVol × V_star_actual). Volume normalisation uses hardcoded `JELLY_ROLL_VOLUME_M3=2.36e-5` m³.

---

## STAR-CCM+ 10C Run Diagnostic (2026-05-25)

**Run**: `in/starCCM_10C_experiment/` — 1107 steps, t=0–110.7 s, dt=0.1 s, 50 A, parallelBranchesSharedSOC, 10,475 cells, 18 zones.

**CRITICAL FINDING from log — ecmQdot field is FROZEN:**
- `ecmQdot Surface Integral 1 (W)` monitor = **26.56412 W for every single iteration of all 1107 timesteps** (one unique value)
- `appliedHeat Monitor 2` = 33.31 W (frozen after step 1, only 2 unique values total)
- ECM correctly computes heat rising 20 W → 33 W as cell warms, but CFD never sees this variation
- **Direct cause**: `autoConfigureJellyRollEnergySource failed` at startup → energy source NOT wired to FileTable
- **Effect**: CFD runs at constant ~26–27 W instead of time-varying 20→33 W → STAR-CCM+ cell runs cold vs OpenFOAM

**WORKAROUND (one-time GUI, must be done before next run):**
- jellyRoll physics continuum → Energy → User Volumetric Heat Source → method = Table (X,Y,Z) → `ECM_jellyRoll_Q_Table` → column `qVol_W_m3`
- This wiring persists in the `.sim` file; the Java macro cannot do it programmatically on STAR 21.02.008

**Other log findings (all benign):**
- Stale cell map (160,313 → 10,475 cells): rebuilt correctly at startup, no impact
- `ecm_runtime_diagnostics.csv` unit bug: logging artifact only, no simulation impact
- ECM coupling itself: functioning correctly (I_sum=50.000 A, all 10,475 cells matched each step)

**Comparison plot**: `artifacts/plots/starccm_vs_openfoam_10c_<STAMP>.pdf`
**Comparison script**: `tools/plot_starccm_vs_openfoam_10c.py`
**Reference OpenFOAM case**: `rev4/dist_3600_fulllog_iso25_exp10C_parallelBranches_dirKfix_20260524/`

**Heat ratio analysis (2026-05-25):**
- Script: `tools/plot_heat_ratio_star_vs_of.py`
- Plot: `artifacts/plots/heat_ratio_star_vs_of_20260525_123706.png`
- Result: Q_STAR / Q_OF  mean=**1.086**  (range 1.027–1.113, grows over time 0.5→263 s)
- STAR-CCM+ applies ~8.6% more heat than OpenFOAM — systematic, growing bias
- Candidate causes: (1) jellyRoll volume mismatch, (2) dt=0.5s vs 0.1s coarser ECM integration, (3) T-feedback: STAR runs hotter → lower R0 → more heat per step

---

## Two-Cell STAR-CCM+ Case — 2026-05-26 Session

**Active case**: `in/starCCM_10C_experiment_twoCells/src/EcmCouplerMacro.java` (4104 lines)
Two jellyRoll regions: `jellyRoll_0`, `jellyRoll_1`. 36 ECM zones total (18 per cell).

### New methods added (2026-05-26)

| Method | Line | Purpose |
|--------|------|---------|
| `verifyAndCorrectRegionIdxOrdering()` | 1810 | Queries T-table Parts list via reflection; for 2-region case auto-corrects regionIndices[] in-place (swap 0↔1) if reversed |
| `getTablePartNames()` | 1881 | Reflection helper: tries getObjects/getEObjects/getCollection/broad-scan to get ordered Parts list from a Table |

Both called from `buildMergedCellMapper()` between `computeRegionIndicesFromFvRep()` and `setRegionIndices()`.

### Auto-regen ecm_mapping.csv on fresh start

Logic in `executeElementWise()` (hoisted before mapping block):
```
freshStart = tryGetPhysicalTimeFromStar(sim) < 1e-9
if freshStart && file exists → delete (so stale 18-zone mapping cannot survive)
if file absent → regenerate unconditionally (calls gen_ecm_mapping.py)
if continuation && file exists → keep; only re-gen on cell-count mismatch
```
Log line: `[ECM-EW] Run mode: FRESH (t=0)` or `CONTINUATION (t=X s)`.

### Continuation run support (both lumped + elementWise paths)

- **ecm_state.json**: deleted only on `freshStart`; preserved on continuation (SOC/RC voltage retained)
- **Log CSVs** (`tempLog.csv`, `appliedHeatLog.csv`, `diagnostics.csv`): opened with `new FileWriter(file, !freshStart)` — append on continuation, overwrite on fresh start; header only written when `freshStart`
- Lumped path: `freshStart = _lumpedInitTime < 1e-9` (computed from new `_lumpedInitTime` var before log/state block)

### User Volume Source wiring status

- `autoConfigureJellyRollEnergySource` always fails (STAR 21.02.008 API limitation) — non-critical WARN
- The FileTable → User Volume Source link IS manually set up and persisted in `final_2cells.sim`
- Heat IS applied correctly: Q_total ~37–42 W per step confirmed in run log
- No further GUI action needed for `final_2cells.sim`

### Commits this session
- `dfb5f2c` — Add T-table ordering verification and auto-correction for multi-region regionIdx
- `25467c9` — Auto-delete and regenerate ecm_mapping.csv on fresh start (t=0)
- `84b8ccb` — Support continuation runs: preserve ECM state and append to logs on t>0
- `265f3a8` — Update README with elementWise multi-region, continuation, and auto-cleanup docs

---

## BUG — regionIdx misassignment in multi-region mapping (diagnosed 2026-06-10)

**File:** `starccm_plugin/src/EcmCouplerMacro.java` → `buildMergedCellMapper()` →
`computeRegionIndicesFromFvRep()`

**Symptom (confirmed by client visual check):**
- Q heat distribution does not align with expected ECM zone borders
- Zone "borders" appear smeared/displaced — same zone index spans cells from BOTH jellyRolls
- Observed in client run at `meeting/20260610/twoCells/final_2cells.sim`
  (ECM-EW runs 10:50–11:13 BST 10 June 2026)

**Root cause:**
`computeRegionIndicesFromFvRep()` assumes STAR-CCM+'s `XyzInternalTable` rows are sorted
region-by-region (all jellyRoll_1 first, then jellyRoll_2). STAR-CCM+ does NOT guarantee
this — rows are interleaved by its internal FvRep ordering.

The method assigns:
- rows 0..49308  → regionIdx=0 (JR1)
- rows 49309..96750 → regionIdx=1 (JR2)

But ~1493 JR2 cells appear in the first 49308 rows, and ~3548 JR1 cells appear in the
last 47442 rows, giving 9180 cells with wrong regionIdx.

`gen_ecm_mapping.py` uses `regionIdx` to compute zone offset (`regionIdx × 18`). Wrong
regionIdx → wrong zone assignment → JR2 cells get JR1 zone IDs and vice versa →
zones span cells from both physical cells → borders appear displaced/wrapped.

**Also observed:** early runs (10:24–10:31 BST) used lumped/LMR mode with
`ecm_mapping.csv` absent → Python fell back to synthetic mapping (20 zones, uniform Q).

**Fix (not yet implemented):**
In `buildMergedCellMapper()`, change priority for N=2 regions: use
`computeRegionIndicesFromCentroids()` (Y-midpoint split) as **primary**, not fallback.
Centroid-based is always spatially correct; FvRep row-order assumption is not.
After applying centroid-based, skip `verifyAndCorrectRegionIdxOrdering()` (as the
existing NOTE comment already explains — block-swap logic is T-table-order-specific).

**Data confirmation:**
- `ecm_cell_map.csv`: 9180 cells with wrong regionIdx
  - 4590 JR2 cells (Y > 25mm) labeled regionIdx=0
  - 4590 JR1 cells (Y < 25mm) labeled regionIdx=1
- 9 contiguous runs of wrong cells; cellIds span both JR1 and JR2 ranges
- `ecm_zone_weights.csv` and `ecm_mapping.csv` derived from this → also wrong

---

## Environment Notes

- OpenFOAM: `source /opt/openfoam/etc/bashrc`
- Python: system python3 for scripts
- STAR-CCM+: 2602.0001 Build 21.02.008 (win64), running on Windows (DESKTOP-45E5HBM)
- License: 29000@DESKTOP-45E5HBM (check expiry each session)
