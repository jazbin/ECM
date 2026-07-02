# EcmCouplerMacro — Code Summary

**File:** `src/EcmCouplerMacro.java` (~5400 lines)
**Also at:** `package/src/EcmCouplerMacro.java`, `in/starCCM_10C_experiment_twoCells/src/EcmCouplerMacro.java`
**Last updated:** 2026-07-02 (pre-warm-up ECM call in LMR mode: eliminates first-step qVol jump caused by IC temperature mismatch between ecm_qvol_injection.csv and STAR-CCM+ initial temperatures)

---

## Top-level structure

```
EcmCouplerMacro  (extends StarMacro)        line 33
│
├── Static config constants                  lines 40–230  (incl. REGION_NAME_PATTERN, nRegionsForEnv)
├── execute()                                line 348   ← STAR entry point; dispatches to:
│     • elementWise → executeElementWise()
│     • lumped N>1 + csvReload → executeLumpedMultiRegion()  ← NEW
│     • lumped N=1 or globalParam → inline lumped loop
├── executeElementWise()                     line 793   ← distributed coupling loop (takes List<Region>)
├── executeLumpedMultiRegion()               line ~1325 ← NEW: lumped T per region, uniform Q/region via table
├── applyElementWiseHeat()                   line ~1545 ← globalParam injection (DEPRECATED, warns)
├── applyElementWiseHeatCsv()                line ~1190 ← csvReload injection (no per-cell vol division)
├── writeQVolInjectionCsv()                  line ~1235 ← writes X,Y,Z,qVol [W/m³] CSV directly
├── getOrCreateQInjectionTable()             line ~1270 ← FileTable setup
├── setupWeightVisualization()               line ~1370 ← load zone-weights table + create 18 UserFieldFunctions
├── autoConfigureJellyRollEnergySource()     line ~1574 ← wires STAR energy source (looped over N regions)
├── diagProfileMethodType()                  line ~1622 ← DIAG-1: log active method class on VolumetricHeatSourceProfile
├── diagQTableReadback()                     line ~1702 ← DIAG-2: re-read Q CSV after extract(), log min/max/mean
├── getOrCreateEnergySourceReports()         line ~1762 ← DIAG-3: create Min/Max/VolInt reports on energy source field
├── logEnergySourceReports()                 line ~1852 ← DIAG-3 per-step: query and log energy-source reports
├── regenEcmMapping()                        line ~1968 ← auto-regenerate ecm_mapping.csv after re-mesh (now passes --geometry-csv)
├── writeRegionGeometryCsv()                 line ~2041 ← NEW: extract per-region CS origin+axis from STAR, PCA fallback
├── extractCsOrigin()                        line ~2135 ← reflection helper for CS origin vector
├── extractCsAxis()                          line ~2174 ← reflection helper for CS basis vector (axis)
├── pcaCylinderAxis()                        line ~2230 ← PCA on centroids for axis detection (Java)
├── writeStepCsvFallback()                   line ~1585
├── writeCellMapCsv()                        line 1631  ← now writes regionIdx column
├── writeStepCsv()                           line 1654
├── buildMergedCellMapper()                  line 2848  ← merges N regions; spatial-only (no fallback); throws on failure
├── computeRegionIndicesNearestCentroid()    line 3114  ← PRIMARY: nearest-centroid; CSV origins → k-means; no row-order assumption
├── validateRegionIdxWithFvRep()             line 3296  ← warn-only FvRep count check; never overrides spatial assignment
├── computeRegionIndicesFromFvRep()          line 2907  ← DEAD (no longer called); kept for reference only
├── verifyAndCorrectRegionIdxOrdering()      line 2957  ← DEAD (no longer called); assumed T-table block order (wrong)
├── isValidRegionIdx()                       line 3035  ← checks regionIdx is not all-zeros for N>1
├── computeRegionIndicesFromCentroids()      line 3061  ← DEAD (no longer called); Y-bimodality N=2 only
├── getTablePartNames()                      line ~3340 ← reflection helper for T-table Parts order
├── readRegionIndicesFromCsv()               line 3392  ← reads regionIdx column from cell map CSV
│
├── CellMapper  (static nested class)        line 1807  (+ regionIndices field/accessor/setter)
│   ├── create()                             line ~1860 ← calls extractVolumes() when volumes absent
│   ├── createFromCsv()                      line ~1960 ← reads optional cols: volume_m3, regionIdx
│   ├── createFromXyzTable()                 line ~2030 ← rebuild from T table after re-mesh
│   ├── extractVolumes()                     line ~2090 ← FvRep volume extraction or uniform fallback
│   ├── getTemperatures()                    line ~2155 ← dispatch by backend
│   ├── getTemperaturesFromXyzTable()        line ~2200 ← PRIMARY (fast path)
│   ├── buildTableToMapperMapping()          line ~2390 ← coord-hash row→mapper mapping
│   ├── getTemperaturesFromXyzTableCsv()     line ~2430 ← slow CSV fallback
│   ├── centroidHash()                       line ~2450  ← strict 0.01 mm (spot-check only)
│   ├── centroidHashRelaxed()                line ~2460  ← 0.1 mm (full scan; tolerates CGNS–STAR diff)
│   ├── getSeriesArray()                     line ~2480 ← bulk column read
│   ├── safeToDouble()                       line ~2505
│   ├── parseDouble()                        line ~2515
│   ├── safeGetColumnName()                  line ~2530
│   ├── safeGetValueAt()                     line ~2540
│   ├── printFvRepDiagnostics()              line ~2555
│   ├── getVolumeAverageT()                  line ~2570
│   ├── getFvRepresentation()                line ~2600
│   ├── getRegionData()                      line ~2625
│   ├── sliceByRegion()                      line ~2700
│   ├── toDoubleArray()                      line ~2730
│   ├── resolveFieldFunction()               line ~2750
│   └── listMethods()                        line ~2760
│
├── Helper methods (top-level class)
│   ├── getOrCreateTReport()                 line 2849
│   ├── getOrCreateQParam()                  line 2862
│   ├── getDeltaT()                          line ~2878
│   ├── tryGetPhysicalTimeFromStar()         line ~2900
│   ├── runProcess()                         line 2924, 2928  (+ ECM_N_REGIONS env var)
│   ├── waitForFile()                        line 2670
│   ├── printDirectoryContents()             line 2687
│   ├── getEnvOrDefault()                    line 2709
│   ├── resolvePythonCommand()               line 2723
│   ├── readConfigProperty()                 line 2738
│   ├── getDoubleEnvOrDefault()              line 2758
│   ├── getBooleanEnvOrDefault()             line 2776
│   ├── tryInvokeDoubleNoArg()               line ~2800
│   └── tryGetQuantityValueFromNoArgMethod() line ~2820
│
├── EcmBinaryIO  (static nested class)       line 3030
│   ├── buildLumpedInputBytes()              line ~3045
│   ├── writeLumpedInput()                   line 2398
│   ├── readLumpedOutput()                   line 2403
│   ├── readLumpedOutputBytes()              line 2407
│   ├── writeElementWiseInput()              line 2480  ← delegates to buildElementWiseInputBytes
│   ├── buildElementWiseInputBytes()         line 2487  ← NEW: returns byte[] for pipe or file
│   ├── readElementWiseOutput()              line 2538  ← delegates to readElementWiseOutputBytes
│   ├── readElementWiseOutputBytes()         line 2548  ← NEW: parses byte[] (used by persistent pipe)
│   ├── writeBytes()                         line ~2605
│   └── atomicWrite()                        line ~2610
│
├── CurrentProfile  (static nested class)    line 3287
│   ├── load()                               line ~3300
│   ├── currentAt()                          line 2692
│   ├── min() / max()                        line 2726, 2736
│   ├── normalizeCsvToken()                  line 2746
│   └── splitCsvLine()                       line 2754
│
└── PersistentEcmProcess  (static nested)    line 3473
    ├── start()                              line ~3495
    ├── exchange()                           line ~3410  ← lumped: returns double (total W)
    ├── exchangeElementWise()                line ~3430  ← returns Map<cellId,qVol_W>
    ├── close()                              line ~3460
    └── readFully()                          line ~3480
```

---

## Configuration constants (lines 40–220)

All constants are overridable at runtime via environment variable (priority 1) or
Java system property set by `EcmPrepAndRun.java` (priority 2). Defaults shown.

| Constant | Env var | Default | Notes |
|---|---|---|---|
| `PROJECT_ROOT_PATH` | `ECM_PROJECT_ROOT` | *(auto-detected from macro location: parent of `src/`)* | No hardcoded path; always derived at runtime from where the macro file lives |
| `PYTHON_CMD` | `ECM_PYTHON_EXE` | `["py", "-3"]` | Falls back to `config.properties` |
| `USE_PERSISTENT_PYTHON` | `ECM_USE_PERSISTENT_PYTHON` | `true` | Keep Python process alive between steps |
| `REGION_NAME` | — | `"jellyRoll"` | Coupled STAR-CCM+ region (used for lumped mode) |
| `REGION_NAME_PATTERN` | `ECM_REGION_PATTERN` | `"jellyRoll"` | Substring match for multi-region discovery; all regions whose name contains this string are coupled |
| `nRegionsForEnv` | — | 1 (volatile static) | Set by `executeElementWise()`, passed as `ECM_N_REGIONS` to Python |
| `QPARAM_NAME` | — | `"ecmQdot_W"` | ScalarGlobalParameter name |
| `ALPHA` | — | `1.0` | Under-relaxation (1 = off) |
| `ECM_CALL_EVERY_N_STEPS` | — | `0` | 0 = call every CFD timestep |
| `N_STEPS` | — | `100000` | Coupling loop iteration limit |
| `ECM_TIMEOUT_S` | — | `60` | Max wait for ecm_out.bin [s] |
| `FALLBACK_DELTA_T_S` | `ECM_FALLBACK_DELTA_T_S` | `1.0e-3` | Used if STAR API returns invalid dt |
| `CURRENT_A` | `ECM_CURRENT_A` | `5.05` | Discharge current [A]; 1C for 2170 cell |
| `CURRENT_PROFILE_PATH` | `ECM_CURRENT_PROFILE_CSV` | `ecm/electrical_inputs.csv` | I(t) schedule CSV |
| `CAPACITY_AH` | `ECM_CAPACITY_AH` | `5.05` | Initial capacity [Ah]; SOC=1 at start |
| `INITIAL_TIME_S` | `ECM_INITIAL_TIME_S` | `0.0` | Restart offset [s] |
| `COUPLING_MODE` | `ECM_COUPLING_MODE` | `"elementWise"` | `"lumped"` or `"elementWise"` |
| `CELL_MAP_CSV_PATH` | `ECM_CELL_MAP_CSV` | `ecm/ecm_cell_map.csv` | Pre-generated by `cgns_cell_map.py` |
| `CELL_STEP_CSV_PATH` | `ECM_CELL_STEP_CSV` | `ecm/ecm_cell_step.csv` | Per-step diagnostic snapshot |
| `INJECTION_MODE` | `ECM_INJECTION_MODE` | `"csvReload"` | `"globalParam"` or `"csvReload"` |
| `Q_TABLE_NAME` | `ECM_Q_TABLE_NAME` | `"ECM_jellyRoll_Q_Table"` | STAR FileTable for qVol injection |
| `Q_TABLE_CSV_PATH` | `ECM_Q_TABLE_CSV` | `ecm/ecm_qvol_injection.csv` | Per-cell qVol CSV for injection |
| `JELLY_ROLL_VOLUME_M3` | `ECM_JELLY_ROLL_VOLUME_M3` | `2.36e-5` | Total jellyRoll volume [m³] |
| `T_EXTRACTION_BACKEND` | `ECM_T_EXTRACTION_BACKEND` | `"xyzTableInMemory"` | See backends table below |
| `T_TABLE_NAME` | `ECM_T_TABLE_NAME` | `"ECM_jellyRoll_T_Table"` | XYZ Internal Table in .sim |
| `ECM_DISTRIBUTED_ELECTRICAL_MODE` | `ECM_DISTRIBUTED_ELECTRICAL_MODE` | `"partitionStates"` | `"sharedState"` = lumped T; `"partitionStates"` = per-zone T+state |
| `ECM_MAPPING_FILE_PATH` | `ECM_MAPPING_FILE` | `"ecm/ecm_mapping.csv"` | meshKey→ecmZone CSV; absent → synthetic fallback; multi-row for overlap-weighted boundary cells |
| `ECM_N_ELEMENTS` | `ECM_N_ELEMENTS` | `20` | zones for synthetic fallback when mapping file absent |
| `ECM_N_REGIONS` | `ECM_N_REGIONS` | `1` | number of coupled jellyRoll regions; passed to Python; set from `nRegionsForEnv` |
| `ZONE_WEIGHTS_CSV_PATH` | `ECM_ZONE_WEIGHTS_CSV` | `"ecm/ecm_zone_weights.csv"` | X,Y,Z,w_zone_0…w_zone_17 fractions — for visualization |
| `ZONE_WEIGHTS_TABLE_NAME` | `ECM_ZONE_WEIGHTS_TABLE` | `"ECM_ZoneWeights_Table"` | STAR FileTable name for zone-weight visualization |
| `ECM_N_PHYSICAL_REGIONS` | `ECM_N_PHYSICAL_REGIONS` | `2` | Physical battery cylinders → --n-regions arg for gen_ecm_mapping.py |
| `ECM_REGION_CENTERS` | `ECM_REGION_CENTERS` | `"-0.000027,...;0.049882,..."` | Cylinder axis (y,z m) for local radial zone assignment |
| `REGION_GEOMETRY_CSV_PATH` | `ECM_REGION_GEOMETRY_CSV` | `"ecm/ecm_region_geometry.csv"` | Per-region origin+axis CSV from STAR-CCM+ coordinate systems |
| `TEMP_LOG_CSV_PATH` | `ECM_TEMP_LOG` | `"ecm/tempLog.csv"` | Dedicated T log (STAR VolumeAverageReport source) |
| `APPLIED_HEAT_LOG_CSV_PATH` | `ECM_APPLIED_HEAT_LOG` | `"ecm/ecmHeatLog.csv"` | ECM-computed heat log (relaxed W set on STAR parameter) |

### Derived file paths (lines ~247–253)

```
PROJECT_ROOT/ecm/ecm_in.bin                ← written by macro, read by Python
PROJECT_ROOT/ecm/ecm_out.bin               ← written by Python, read by macro
PROJECT_ROOT/ecm/ecm_state.json            ← Python ECM state persistence
PROJECT_ROOT/ecm/ecm_debug.log             ← verbose per-step debug log
PROJECT_ROOT/ecm/ecm_cell_map.csv          ← one-time cell ID/centroid map (now includes regionIdx column)
PROJECT_ROOT/ecm/ecm_cell_step.csv         ← per-step T + qVol snapshot
PROJECT_ROOT/ecm/ecm_qvol_injection.csv    ← csvReload injection CSV
PROJECT_ROOT/ecm/tempLog.csv               ← dedicated T time-history (overwritten each run)
PROJECT_ROOT/ecm/ecmHeatLog.csv   ← ECM-computed heat time-history (overwritten each run)
PROJECT_ROOT/ecm/voltageLog.csv            ← dedicated V_common time-history (Python side, overwritten each run)
```

### Output CSV files — provenance and restart policy

| File | Source | Side | Restart |
|------|--------|------|---------|
| `tempLog.csv` | STAR `VolumeAverageReport` on jellyRoll region | Java/STAR | Overwritten at run start |
| `ecmHeatLog.csv` | ECM-computed heat [W] set on STAR parameter (lumped) or sum of per-cell W (EW) | Java/STAR | Overwritten at run start |
| `voltageLog.csv` | `V_common_V` from ECM backend diag dict | Python/ECM | Truncated when `step_id == 1` |
| `voltageHistory.csv` | Mixed diagnostic (voltage + Q + T_eff + n_partitions) | Python/ECM | Append; may accumulate across restarts |
| `ecm_runtime_diagnostics.csv` | Mixed (lumped mode only): T_eff_K, qGen_W, cumE_J | Java/STAR | Overwritten at run start |

### T extraction backends

| Backend value | Description | Status |
|---|---|---|
| `"xyzTableInMemory"` | `XyzInternalTable.extract()` + `getSeries(int)` | **DEFAULT — use this** |
| `"directFieldData"` | `FvRepresentation.getInternalDataVector()` | BROKEN in STAR 2602 |
| `"xyzTableCsvFallback"` | Export table to CSV then parse | Slow (~10×), last resort |
| `"volumeAverageDebugOnly"` | Single volume-average T for all cells | Debug only |

### Heat injection modes

| Mode | Description | Notes |
|---|---|---|
| `"globalParam"` | Sum all per-cell W → push total to `ecmQdot_W` | No spatial variation |
| `"csvReload"` | Write (X,Y,Z,qVol) CSV per step + `FileTable.extract()` | True per-cell, ~500–700 ms/step |

### Overlap-weighted mapping (ecm_mapping.csv format)

`ecm_mapping.csv` has columns `meshKey, ecmCellId, weight` where:
- `weight` = partial volume [m³] = `V_cell × overlap_fraction`
- Cells entirely inside one zone: **one row**, `weight = V_cell`
- Cells straddling a zone boundary: **two or more rows**, weights summing to `V_cell`
- For the 2170 mesh: 30,131 rows for 21,552 cells (avg 1.40 per cell, 35.3% boundary cells)

The stale-mapping check counts **unique meshKey values** (not total rows) to detect re-meshing.

`ecm_zone_weights.csv` has columns `X_m, Y_m, Z_m, w_zone_0 … w_zone_17` (fractions, one row
per cell). Loaded as a static FileTable at startup; 18 `ECM_Zone_k_Weight` UserFieldFunctions
are created automatically for scalar-scene visualization in STAR-CCM+.

---

## execute() — entry point (line 348)

1. Print startup diagnostics (paths, OS, Java version)
2. Validate `PROJECT_ROOT` and `ECM_DIR` exist
3. Validate `ecm_coupler.py` script exists
4. **Discover all regions** whose `PresentationName` contains `REGION_NAME_PATTERN`; sort alphabetically
5. **Dispatch:**
   - `COUPLING_MODE == "elementWise"` → `executeElementWise(sim, coupledRegions)` and return
   - Otherwise → lumped coupling loop using `coupledRegions.get(0)` (first region only)

### Lumped coupling loop — N=1 (lines ~485–820)

Setup:
- `getOrCreateTReport()` — `VolumeAverageReport` across **all coupled regions**
- `getOrCreateQParam()` — `ScalarGlobalParameter("ecmQdot_W")`
- If `INJECTION_MODE=csvReload`: `buildMergedCellMapper()` + `getOrCreateQInjectionTable()` + `autoConfigureJellyRollEnergySource()` — same FileTable wiring as elementWise, so the energy source in the `.sim` file does not need reconfiguration when switching modes
- Open `ecm_debug.log` and `ecm_runtime_diagnostics.csv`
- Write `{}` to `ecm_state.json` (fresh start only; ECM loads empty dict → SOC=1 defaults)
- `CurrentProfile.load()` from CSV or constant `CURRENT_A`
- Optionally start `PersistentEcmProcess`

Per-step sequence:
```
iter.step(1)                              advance solver
tEff = tReport.getValue()                 volume-average T [K]
deltaT, simTime                           timestep and sim time
currentA = currentProfile.currentAt(t)   interpolated from schedule
inputBytes = EcmBinaryIO.buildLumpedInputBytes(stepId, tEff, ...)
qGenW = persistent.exchange() or file I/O + runProcess()
qVol = ALPHA*qGenW + (1-ALPHA)*qVolPrev  under-relaxation

if INJECTION_MODE=csvReload:
    qUniform[all cells] = qVol           uniform fill
    applyElementWiseHeatCsv()            write CSV + FileTable.extract()
else:
    qParam.getQuantity().setValue(qVol)  globalParam fallback

write diagnostics CSV row
```

**Note on injection mode:** `csvReload` is the default and recommended mode. It writes a per-cell uniform (X,Y,Z,qVol) CSV and reloads the FileTable every step. This keeps the same energy-source wiring as `elementWise` mode, so switching between `lumped` and `elementWise` in the Java constants requires no manual reconfiguration inside the `.sim` file. The `globalParam` fallback only activates if FileTable setup fails.

---

## executeLumpedMultiRegion() — lumped multi-region coupling (line ~1325)  ← NEW

Called when `COUPLING_MODE == "lumped"` AND `regions.size() > 1`.

**Concept:** "one T per cell, one Q per cell, uniform spatial distribution."
Each physical battery cell gets its own `VolumeAverageReport` (`ECM_T_avg_r0`, `ECM_T_avg_r1`, …).
The T values are broadcast uniformly to all CFD cells in that region, then sent to Python
as a standard elementWise binary frame.  Python returns per-CFD-cell qVol using the same
zone mapping as elementWise; these are then aggregated to a per-region total Q [W],
under-relaxed, and written as uniform `qVol[i] = Q[k] / V_region[k]` into the injection CSV.

**Setup (one-time, same as elementWise):**
- `buildMergedCellMapper()` — same N-region mapper
- `writeCellMapCsv()`, `writeRegionGeometryCsv()`
- `regenEcmMapping()` — fresh-start delete + regen; stale-check on continuation
- `ecm_state.json` written as `{}` on fresh start (not deleted)
- Per-region `VolumeAverageReport[]` — one report per jellyRoll
- `getOrCreateQInjectionTable()` + `autoConfigureJellyRollEnergySource()` for each region
- Pre-compute `regionVolume[k]` (stable; summed from `cellMapper.volumes()`)

**Pre-warm-up call (fresh starts only, before the coupling loop):**
```
tAvgInit[k] = tReports[k].getValue()         STAR initial temperatures (before any solve)
ewInputBytes = buildElementWiseInputBytes(stepId=0, deltaT=0, ...)
                                              probe call: no SoC advancement
qVolMap = exchange ECM (persistent or file)
aggregate → qWRelaxed → qVolUniform → applyElementWiseHeatCsv()
                                              FileTable seeded before step 1
qWPrev = wuQW; qVolPrev = wuQVolUniform      seed under-relaxation state
```
WHY this exists: the coupling loop runs `iter.step(1)` **before** calling the ECM, so the
FileTable used during the first solver step comes from whatever was on disk at startup
(`ecm_qvol_injection.csv`).  That file is typically produced by a prior OpenFOAM run at a
different initial temperature than the STAR-CCM+ case, causing a sharp ~2× jump in applied
ECM heat at t=deltaT.  The warm-up call reads STAR's actual initial temperatures, calls the
ECM with `deltaT=0` (so ECM state/SoC is unchanged), and writes the result into the FileTable
**before** `iter.step(1)` executes for the first real step.  Continuation runs skip the
warm-up — their FileTable already holds correct values from the previous run's last step.

**Per-step sequence (coupling loop, step ≥ 0):**
```
iter.step(1)
tAvg[k] = tReports[k].getValue()           per-region volume-average T [K]
temps[i] = tAvg[regionIdx[i]]              broadcast T to all cells in region
ewInputBytes = buildElementWiseInputBytes() same N-cell binary as EW mode
qVolMap = persistentProcess.exchangeElementWise() or file I/O + runProcess()
qW[k] = Σ(qVolNew[i] * V[i])  for i in region k   aggregate to per-region Q [W]
qWRelaxed[k] = α*qW[k] + (1-α)*qWPrev[k]           under-relax per region
qVolUniform[i] = qWRelaxed[regionIdx[i]] / regionVolume[regionIdx[i]]
applyElementWiseHeatCsv()                  write CSV + FileTable.extract()
```

**Fallback:** if `regIdx == null` (CellMapper couldn't assign regions), all cells fall to
region 0 with a warning. Use elementWise mode if this happens.

---

## executeElementWise() — distributed coupling loop (line ~793)

Takes `List<Region> regions` (sorted, all regions matching `REGION_NAME_PATTERN`).
Sets `nRegionsForEnv = regions.size()` so Python receives `ECM_N_REGIONS`.

Setup:
- `buildMergedCellMapper(sim, regions)` — N=1: delegates to `CellMapper.create()`; N>1: reads combined T-table, assigns regionIndices from FvRep cell counts (primary), falls back to CSV then all-zeros
- `writeCellMapCsv()` — one-time write of (cellId, x, y, z, volume_m3, **regionIdx**)
- Write `{}` to `ecm_state.json` on fresh start (not deleted)
- If `INJECTION_MODE == "csvReload"`:
  - `getOrCreateQInjectionTable()` — create/retrieve `FileTable(Q_TABLE_NAME)`
  - **Loop:** `autoConfigureJellyRollEnergySource(sim, jr, qInjectionTable)` for each region
  - `setupWeightVisualization()` — load zone-weights table + create UserFieldFunctions
- Open `ecm_debug.log`
- `CurrentProfile.load()`
- Note: **persistent Python is now supported** in elementWise via `exchangeElementWise()`; file-based is automatic fallback if pipe fails

Per-step sequence:
```
iter.step(1)
temps[] = cellMapper.getTemperatures(sim)         per-cell T [K] via getSeries
deltaT, simTime                                   same as lumped
currentA = currentProfile.currentAt(t)
ewInputBytes = EcmBinaryIO.buildElementWiseInputBytes(...)  build N-record frame
if persistentProcess != null:
    qVolMap = persistentProcess.exchangeElementWise(...)    pipe frame → N-record response
else (or on pipe failure, automatic fallback):
    EcmBinaryIO.writeBytes(ECM_IN_PATH, ewInputBytes)       write frame to disk
    runProcess()                                            spawn ecm_coupler.py
    waitForFile(ECM_OUT_PATH, timeout)
    qVolMap = EcmBinaryIO.readElementWiseOutput()           read N-record response
merge qVolMap → qVolNew[]                                   per-cell W/m³ array
writeStepCsv()                                              diagnostic CSV
applyElementWiseHeat[Csv]()                                 inject heat into STAR
```

Failure handling at each step: on any error, keep previous `qVolPrev` and continue.

---

## buildMergedCellMapper() (line 1692)

### computeRegionIndicesFromFvRep() (line 1761) — NEW
Queries `FvRepresentation.getCellCount(Region)` for each coupled region (via reflection, trying `getCellCount` then `getRegionCellCount`). Assigns `regionIdx[offset .. offset+cnt-1] = rIdx` sequentially. Returns `null` on any failure (caller falls back to CSV or all-zeros). This correctly handles 2+ physical cells without depending on a pre-written CSV.

Builds one `CellMapper` covering all cells from all coupled regions.
- **N=1**: exact delegation to `CellMapper.create(sim, regions.get(0))` — bit-for-bit identical to previous behavior.
- **N>1**: reads combined T-table (must cover all jellyRoll regions in STAR GUI); **primary**: calls `computeRegionIndicesFromFvRep()` to assign regionIdx from mesh cell counts (FvRep) — never stale; **fallback 1**: reads `regionIdx` from `ecm_cell_map.csv`; **fallback 2**: all-zero assignment with warning.

## CellMapper (line 1807–~3030)

Caches the cell enumeration (IDs and centroids) for the coupled region.
Built once at startup; `getTemperatures()` called every step.

### Fields

| Field | Type | Purpose |
|---|---|---|
| `cellIds` | `int[]` | Stable cell IDs (0-based sequential from CSV or FvRep) |
| `x`, `y`, `z` | `double[]` | Cell centroid coordinates [m] |
| `volumes` | `double[]` | Per-cell actual volume [m³]; null until `extractVolumes()` is called |
| `n` | `int` | Number of cells |
| `region` | `Region` | Cached STAR-CCM+ region reference |
| `tableRowToMapperIndex` | `int[]` | Lazy: table row → cellIds array index (built once) |
| `tColumnIndex` | `int` | Lazy: column index of Temperature in XYZ table (cached) |

### create() — line 1165

Primary path: read `ecm_cell_map.csv` (generated by `tools/cgns_cell_map.py`).
Fallback: `FvRepresentation.getInternalDataVector()` for centroid extraction (STAR 18.06 only).

### getTemperatures() — line 1253

Dispatches by `T_EXTRACTION_BACKEND`:

```
"xyzTableInMemory"    → getTemperaturesFromXyzTable()   ← PRIMARY
"directFieldData"     → getRegionData() via FvRep        ← BROKEN on 2602
"xyzTableCsvFallback" → getTemperaturesFromXyzTableCsv() ← slow
"volumeAverageDebugOnly" → fill all cells with volume-avg T
```

### getTemperaturesFromXyzTable() — line 1302

The primary per-cell T extraction path. Called every step.

```
1. sim.getTableManager().getTable(T_TABLE_NAME)
2. table.extract()                     → refreshes table data (~8ms warm, ~227ms cold)
3. validate rows == n
4. identify T column (cached in tColumnIndex after first call)
5. build tableRowToMapperIndex (cached after first call)
6. rawTemps = getSeriesArray(sim, table, tColumnIndex)  → ~4ms for 160k cells
7. apply mapping: temps[tableRowToMapperIndex[r]] = rawTemps[r]
8. validate no NaN/Inf
9. log: extract_ms, read_ms, T_min/mean/max
```

### getSeriesArray() — line 1688

Bulk-reads all values for one table column as `double[]`. Three reflection paths:

| Path | API | Timing |
|---|---|---|
| A | `table.getSeriesData().getSeries(int)` → `double[]` | ~4 ms (confirmed STAR 2602) |
| B | `getSeriesData().getSeriesObject(int)` → `DoubleVector.toDoubleArray()` | similar |
| C | Any `DoubleVector`-returning method on SeriesData with `(int)` param | fallback |
| D | Per-row `getValueAt(row, col)` loop | ~500 ms+ for 160k rows — WARN logged |

### buildTableToMapperMapping() — line 1414

Builds the `tableRowToMapperIndex[]` array (built once, cached).

```
1. Identify X, Y, Z column indices by name in the table
2. Bulk-read tableX[], tableY[], tableZ[] via getSeriesArray() — ~4ms each
3. Build centroid hash map from CellMapper x[], y[], z[]
4. Spot-check 200 evenly-spaced rows for identity ordering
   → if identity confirmed: return direct [0,1,2,...,N-1] mapping
   → else: full N-row scan using tableX/Y/Z arrays (no per-row API calls)
5. Log: matched/unmatched counts, first 3 samples
```

Always performs a **mandatory full coordinate scan** using `centroidHashRelaxed` (0.1 mm
bins).  No spot-check, no identity shortcut — those were the source of the parallel-run
mapping bug.  Scan runs **once at startup** and is cached; cost ~10 ms.  Throws on
≥ 2% unmatched rows (wrong table / stale CSV) so failures are explicit, not silent.

### centroidHash() — line 1650

```java
long hash = ix * 1_000_003_001L + iy * 1_000_003L + iz
// where ix = round(cx / 1e-5)  — quantised to 0.01 mm
```

---

## EcmBinaryIO (lines 2885–~3140)

Binary I/O implementation for the `ECMIOv2` protocol (see `docs/IO_FORMAT.md`).

### Binary format

```
Header (52 bytes):
  char[8]  magic     "ECMIOv1\0"
  uint32   fileType  1=input  2=output
  uint32   version   2
  uint32   N         number of cell records
  double   time      simulation time [s]
  double   deltaT    timestep [s]
  uint32   keyMode   0=globalCellId
  uint32   nInputs   number of named electrical inputs
  uint64   stepId    transaction counter

Inputs section (nInputs records):
  uint32   nameLen
  char[nameLen]  name (UTF-8)
  double   value

Cell records (N entries):
  int32    key    cell ID
  double   value  T [K] (input) or qVol [W/m³] (output)
```

All values little-endian. Atomic write contract: write `.tmp` then `rename()`.

### Methods

| Method | Direction | Records | Notes |
|---|---|---|---|
| `buildLumpedInputBytes()` | in | 1 | Includes `current_A` and optionally `q_ah_init` inputs |
| `writeLumpedInput()` | in | 1 | Calls `buildLumpedInputBytes` + `atomicWrite` |
| `readLumpedOutput()` | out | 1 | Returns `qGen_W`; NaN on stepId mismatch |
| `readLumpedOutputBytes()` | out | 1 | Same but from byte[] (used by persistent process) |
| `writeElementWiseInput()` | in | N | One record per coupled cell; includes `current_A` |
| `readElementWiseOutput()` | out | N | Returns `Map<cellId, qVol_W_m3>`; null on stepId mismatch |
| `writeBytes()` | — | — | Thin wrapper around `atomicWrite` |
| `atomicWrite()` | — | — | Write to `.tmp`, then `Files.move(ATOMIC_MOVE)` |

---

## CurrentProfile (lines 3142–~3326)

Reads a current schedule from CSV and provides `currentAt(time)` via linear interpolation.

CSV format: header row with columns `time` and `current_A`, then data rows.
If CSV is absent or malformed: falls back to constant `CURRENT_A`.

---

## PersistentEcmProcess (line 3679–~3850)

Keeps one Python `ecm_coupler.py --pipe-binary` process alive between steps to avoid
Python startup overhead (~100–200 ms per step).

Frame protocol over stdin/stdout:
```
Java → Python:  uint64 frameSize (LE)  +  frameSize bytes (ecm_in.bin format)
Python → Java:  uint64 frameSize (LE)  +  frameSize bytes (ecm_out.bin format)
```

**Note:** persistent mode is only used in `lumped` coupling; `executeElementWise` disables
it automatically (elementWise requires file-based exchange for N-record output).

---

## Helper methods (top-level class)

| Method | Line | Purpose |
|---|---|---|
| `getOrCreateTReport()` | 1962 | `VolumeAverageReport` for jellyRoll Temperature |
| `getOrCreateQParam()` | 1975 | `ScalarGlobalParameter("ecmQdot_W")` |
| `getDeltaT()` | 1987 | Queries `SpecifiedTimestepUnsteadySolver` or `ImplicitUnsteadySolver`; fallback to constant |
| `tryGetPhysicalTimeFromStar()` | 2011 | Tries `getCurrentTime`, `getPhysicalTime`, `getCurrentPhysicalTime` via reflection |
| `runProcess()` | 2041 | Spawns Python subprocess; sets `ECM_IN`, `ECM_OUT`, `ECM_STATE_FILE`, `ECM_COUPLING_MODE` env vars |
| `waitForFile()` | 2131 | Polls for file existence with 50 ms sleep; returns false on timeout |
| `getEnvOrDefault()` | 2170 | Env var → Java system property → default |
| `resolvePythonCommand()` | 2184 | `ECM_PYTHON_EXE` → `config.properties:python` → `["py", "-3"]` |
| `tryInvokeDoubleNoArg()` | 2267 | Reflection call returning double; swallows all exceptions |
| `tryGetQuantityValueFromNoArgMethod()` | 2285 | Same but also unwraps Quantity objects via `getValue/getRawValue/getSIValue` |

---

## Data flow diagram

```
STAR-CCM+ solver
      │
      │  iter.step(1)     advance one timestep
      ▼
  Temperature field (jellyRoll region)
      │
      │  XyzInternalTable.extract()   ~8 ms
      │  getSeriesArray() / getSeries(int)   ~4 ms
      ▼
  double[] temps[160313]              per-cell T [K]
      │
      │  EcmBinaryIO.writeElementWiseInput()
      ▼
  ecm_in.bin   (52 B header + N×12 B records)
      │
      │  runProcess()  →  ecm_coupler.py
      ▼
  ecm_out.bin  (52 B header + N×12 B records)
      │
      │  EcmBinaryIO.readElementWiseOutput()
      ▼
  Map<cellId, qVol_W>
      │
      │  merge → double[] qVolNew[160313]   per-cell W
      │
      ├─ INJECTION_MODE=globalParam
      │    sum(qVolNew) → ScalarGlobalParameter("ecmQdot_W")
      │    STAR applies uniform volumetric heat to jellyRoll
      │
      └─ INJECTION_MODE=csvReload
           writeQVolInjectionCsv() → ecm_qvol_injection.csv   ~5 MB
           FileTable.extract()   ~500 ms
           STAR interpolates per-cell qVol_W_m3 via UFF
```

---

## Known limitations and open items

| Item | Notes |
|---|---|
| `applyElementWiseHeat()` | `globalParam` fallback; default is now `csvReload` — true per-cell injection |
| `csvReload` injection overhead | ~500–700 ms per step (CSV write + FileTable.extract) — disk-bound |
| Per-cell volumes | `extractVolumes()` path order: (A) XYZ T-table volume column — proven path, requires "Cell Volume" scalar added to table in STAR GUI; (B) FvRep CellVolume field function — may fail in 2602; (C) uniform fallback with explicit WARN. On re-read, if CSV volumes are all equal, extraction retried automatically in case user has since added the T-table scalar. |
| No C++ UserLibrary path yet | Proposed solution: mmap binary file + ucfunc native field function |
| Python ECM heat distribution | `R0(T[i])`-weighted distribution implemented in `ecm_coupler.py` (falls back to uniform if `ecm_lookup_cache` is unavailable) |
| `directFieldData` backend | Broken in STAR-CCM+ 2602 — confirmed by `TestJellyRollTemperatureExtraction.java` |
| **First-step qVol jump (RESOLVED)** | Root cause: coupling loop runs `iter.step(1)` before the ECM is called, so step 1 always uses the pre-loaded `ecm_qvol_injection.csv`. When that file was generated by an OpenFOAM run at a different initial temperature (e.g. 20°C) than the STAR-CCM+ IC (e.g. 32.8°C), the ECM returns ~2× different heat at the second step → sharp monitor jump at t=deltaT. Fixed by the pre-warm-up ECM call (stepId=0, deltaT=0) that seeds the FileTable before the first `iter.step(1)`. Only runs on fresh starts. |
| Persistent Python in elementWise | **Now supported** via `exchangeElementWise()` — pipe sends N-record frame, Python returns N-record response; file-based is automatic fallback on pipe error |
| Multi-region first-run regionIdx | FvRep getCellCount unavailable in STAR 2602. New fallback `computeRegionIndicesFromCentroids()` assigns regionIdx by Y-cluster midpoint (N=2 only, requires ≥20 mm Y separation). After regionIdx is correctly set in `ecm_cell_map.csv`, `_maybe_regen_mapping()` generates per-region zones (36 total for 2 regions). |
| Multi-region `ecm_zone_weights.csv` | For N regions, the weights CSV has `N × n_zones` columns (`w_zone_0 … w_zone_{N*18-1}`). The STAR `setupWeightVisualization()` creates only 18 UFF entries (first region); extend manually for visualization of subsequent regions. |

---

## Files that must stay in sync

Any edit to `src/EcmCouplerMacro.java` must be mirrored to:
- `starccm_plugin/package/src/EcmCouplerMacro.java`
- `in/starCCM_10C_experiment_twoCells_distributed/src/EcmCouplerMacro.java`

```bash
# Sync command (canonical source is in/testedVersion):
SRC=in/testedVersion/src/EcmCouplerMacro.java
cp $SRC starccm_plugin/package/src/EcmCouplerMacro.java
cp $SRC in/starCCM_10C_experiment_twoCells_distributed/src/EcmCouplerMacro.java
```
