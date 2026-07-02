import star.common.*;
import star.base.neo.*;
import star.base.report.*;
import star.energy.*;
import star.vis.*;

import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;

/**
 * EcmCouplerMacro — per-timestep ECM coupling for STAR-CCM+ 21.02.
 *
 * USAGE
 * -----
 * 1. Open your .sim file in STAR-CCM+.
 * 2. In the tree, manually create a ScalarGlobalParameter named "ecmQdot_W"
 *    and set the jellyRoll region's energy source (total power, W) to reference it.
 * 3. Tools > Macros > Run Macro > select EcmCouplerMacro.java.
 * 4. The macro drives the solver loop; DO NOT press the Run button separately.
 *
 * The macro writes ecm_in.bin, calls the external ECM Python process,
 * reads ecm_out.bin, applies under-relaxation, and updates ecmQdot_W_m3
 * before the next solver step.
 */
public class EcmCouplerMacro extends StarMacro {

    // =========================================================================
    // CONFIG — edit these before running
    // =========================================================================

    /**
     * Root directory of this STAR/ECM coupling workspace.
     * Auto-detected at execute() time from the macro file location (parent of src/).
     * Override via ECM_PROJECT_ROOT env var for non-standard setups.
     * No hardcoded machine path — the macro works on any machine without configuration.
     */
    // Resolved at execute() time via resolveAndSetProjectRoot().
    private static String PROJECT_ROOT_PATH =
        getEnvOrDefault("ECM_PROJECT_ROOT", "");

    /** Python command tokens. Prefer explicit env/config over PATH aliases. */
    private static final List<String> PYTHON_CMD = resolvePythonCommand();

    /** Keep one Python backend resident and exchange binary frames over stdin/stdout. */
    private static final boolean USE_PERSISTENT_PYTHON =
        getBooleanEnvOrDefault("ECM_USE_PERSISTENT_PYTHON", true);

    /** Name of the coupled battery region in the STAR-CCM+ tree. */
    private static final String REGION_NAME = "jellyRoll";

    /**
     * Substring pattern used to discover coupled regions.  All regions whose
     * {@code PresentationName} contains this string are included.
     * Overridable via {@code ECM_REGION_PATTERN}; defaults to {@code REGION_NAME}.
     */
    private static final String REGION_NAME_PATTERN =
        getEnvOrDefault("ECM_REGION_PATTERN", REGION_NAME);

    /**
     * Number of coupled regions, set by {@code executeElementWise()} so that
     * {@code runProcess()} and {@code PersistentEcmProcess.start()} can pass
     * {@code ECM_N_REGIONS} to the Python backend.
     */
    private static volatile int nRegionsForEnv = 1;

    /** Name of the ScalarGlobalParameter that receives Q_GEN [W] from the ECM.
     *  Configure the STAR-CCM+ heat source as a total power source (W), not W/m3. */
    private static final String QPARAM_NAME = "ecmQdot_W";

    /** Under-relaxation factor for qVol update. */
    private static final double ALPHA = 1;

    /**
     * Force the ECM backend to fire every CFD timestep.
     * The Python backend interprets 0 as "call every step".
     */
    private static final int ECM_CALL_EVERY_N_STEPS = 0;

    /** Number of timesteps to run. */
    private static final int N_STEPS = 100000;

    /** Max wall-clock seconds to wait for ecm_out.bin to appear. */
    private static final int ECM_TIMEOUT_S = 60;

    /** Structured runtime diagnostics CSV written by the STAR-side macro. */
    private static final String DIAGNOSTICS_CSV_PATH =
        getEnvOrDefault("ECM_DIAGNOSTICS_CSV", "ecm/ecm_runtime_diagnostics.csv");

    /** Dedicated jellyRoll volume-average temperature time-history (overwritten each run).
     *  Source: STAR VolumeAverageReport on jellyRoll region. Schema: time_s,temp_c. */
    private static final String TEMP_LOG_CSV_PATH =
        getEnvOrDefault("ECM_TEMP_LOG", "ecm/tempLog.csv");

    /** Dedicated STAR-applied total heat time-history (overwritten each run).
     *  Source: relaxed heat value set on ecmQdot_W global parameter (lumped) or sum
     *  of per-cell W written to STAR via csvReload/globalParam (elementWise).
     *  Schema: time_s,applied_total_heat_w. */
    private static final String APPLIED_HEAT_LOG_CSV_PATH =
        getEnvOrDefault("ECM_APPLIED_HEAT_LOG", "ecm/appliedTotalHeatLog.csv");

    /**
     * Used only if the STAR physical-time API is unavailable.
     * For your current case this should be 1.0e-3 because STAR reports:
     * TimeStep 1: Time 1.000000e-03
     */
    private static final double FALLBACK_DELTA_T_S =
        getDoubleEnvOrDefault("ECM_FALLBACK_DELTA_T_S", 1.0e-3);

    /**
     * Applied current [A] sent to the ECM each timestep.
     * Positive = discharge. Set ECM_CURRENT_A env var to override.
     * Default 50.0 A = 10C for the 2170 cell (5.0 Ah capacity).
     */
    private static final double CURRENT_A =
        getDoubleEnvOrDefault("ECM_CURRENT_A", 50.0);

    /**
     * Optional interpolated current schedule CSV.
     * Points to the 10C experimental discharge schedule (50 A constant).
     * If absent, the macro falls back to CURRENT_A.
     */
    private static final String CURRENT_PROFILE_PATH =
        getEnvOrDefault("ECM_CURRENT_PROFILE_CSV", "ecm/electrical_inputs_experimental_10C_discharge.csv");

    /**
     * Initial cell capacity [Ah] = starting q_ah for a fully-charged cell.
     * Sent as q_ah_init input so the Python ECM starts at SOC=1 (full).
     * Override with ECM_CAPACITY_AH env var. Default 5.05 Ah for the 2170 cell.
     */
    private static final double CAPACITY_AH =
        getDoubleEnvOrDefault("ECM_CAPACITY_AH", 5.05);

    /**
     * Used only if STAR physical-time API is unavailable.
     * Set ECM_INITIAL_TIME_S from the environment if restarting from nonzero time.
     */
    private static final double INITIAL_TIME_S =
        getDoubleEnvOrDefault("ECM_INITIAL_TIME_S", 0.0);

    /**
     * Coupling mode: "lumped" (default, single volume-averaged T → single qGen_W)
     * or "elementWise" (per-cell T extraction → per-cell qVol application).
     *
     * Set environment variable ECM_COUPLING_MODE=elementWise to activate Phase 1
     * distributed mode.
     */
    private static final String COUPLING_MODE =
        getEnvOrDefault("ECM_COUPLING_MODE", "elementWise");

    /**
     * In elementWise mode: path (relative to PROJECT_ROOT) for the cell-map CSV
     * written once on startup.  Columns: cellId,x_m,y_m,z_m
     * This file is useful for visualising which cells are coupled and their
     * spatial positions.
     */
    private static final String CELL_MAP_CSV_PATH =
        getEnvOrDefault("ECM_CELL_MAP_CSV", "ecm/ecm_cell_map.csv");

    /**
     * In elementWise mode: path for the per-step diagnostic CSV.
     * Columns: step,cellId,x_m,y_m,z_m,T_K,q_W
     * q_W = heat contribution of this cell [W]; sum over all cells = total Q_GEN [W].
     * Written (overwritten) every step so the file always holds the latest
     * snapshot; useful for plotting with Python.
     */
    private static final String CELL_STEP_CSV_PATH =
        getEnvOrDefault("ECM_CELL_STEP_CSV", "ecm/ecm_cell_step.csv");

    /**
     * Per-cell heat injection mode for elementWise coupling.
     *
     * "globalParam" — sum all per-cell W → push total to ecmQdot_W
     *                 ScalarGlobalParameter. Same as lumped. No spatial variation.
     *
     * "csvReload"   — write (X,Y,Z,qVol_W_m3) CSV per step, reload via
     *                 FileTable.extract(). True per-cell distributed heat injection.
     *                 ~500–700 ms I/O overhead per step. Auto-configures the
     *                 jellyRoll VolumetricHeatSourceProfile at startup.
     *                 Falls back to globalParam if FileTable creation fails.
     */
    private static final String INJECTION_MODE =
        getEnvOrDefault("ECM_INJECTION_MODE", "csvReload");

    /**
     * Name of the STAR-CCM+ FileTable used for per-cell qVol CSV injection.
     * Created at startup if absent.  Configure the jellyRoll energy-source UFF to use:
     *   interpolateTable("ECM_jellyRoll_Q_Table", "qVol_W_m3",
     *       $$Position[0], $$Position[1], $$Position[2])
     */
    private static final String Q_TABLE_NAME =
        getEnvOrDefault("ECM_Q_TABLE_NAME", "ECM_jellyRoll_Q_Table");

    /**
     * Path for the per-cell qVol injection CSV (relative to PROJECT_ROOT).
     * Columns: x_m, y_m, z_m, qVol_W_m3 — overwritten each coupling step.
     */
    private static final String Q_TABLE_CSV_PATH =
        getEnvOrDefault("ECM_Q_TABLE_CSV", "ecm/ecm_qvol_injection.csv");

    /**
     * Approximate total jellyRoll region volume [m³].
     * Used as fallback when per-cell volumes are unavailable (e.g. no volume_m3
     * column in ecm_cell_map.csv) and for legacy globalParam injection mode.
     * Default 2.36e-5 m³ ≈ π × (10.75 mm)² × 65 mm for the 2170 cell.
     * Override with ECM_JELLY_ROLL_VOLUME_M3 env var for other geometries.
     */
    private static final double JELLY_ROLL_VOLUME_M3 =
        getDoubleEnvOrDefault("ECM_JELLY_ROLL_VOLUME_M3", 2.36e-5);

    /**
     * Temperature extraction backend used in elementWise mode.
     *
     * Allowed values:
     *   "xyzTableInMemory"      — extract from XYZ Internal Table via Table API (DEFAULT).
     *                             Requires table named ECM_T_TABLE_NAME to exist in .sim.
     *   "directFieldData"       — legacy FvRepresentation reflection approach.
     *                             Confirmed BROKEN in STAR-CCM+ 2602; kept for backward compat.
     *   "xyzTableCsvFallback"   — export table to CSV each step, then parse. ~10× slower.
     *   "volumeAverageDebugOnly"— one T value for all cells (not real elementWise, debug only).
     */
    private static final String T_EXTRACTION_BACKEND =
        getEnvOrDefault("ECM_T_EXTRACTION_BACKEND", "xyzTableInMemory");

    /**
     * Name of the XYZ Internal Table to use for per-cell temperature extraction.
     * Must be created manually in the .sim file (Tools > Tables > New > XYZ Internal Table).
     * Configure: Parts = jellyRoll region, Scalars = Temperature.
     */
    private static final String T_TABLE_NAME =
        getEnvOrDefault("ECM_T_TABLE_NAME", "ECM_jellyRoll_T_Table");

    /**
     * Enable verbose per-step timing and field statistics logging.
     * Always on for this test case. Set to false for quiet production runs.
     */
    private static final boolean HEAVY_LOG = true;

    // Derived paths — initialised from PROJECT_ROOT_PATH, then optionally
    // updated by resolveAndSetProjectRoot() at the start of execute().
    private static File PROJECT_ROOT     = new File(PROJECT_ROOT_PATH);
    private static File ECM_DIR          = new File(PROJECT_ROOT, "ecm");
    private static File ECM_SCRIPT_PATH  = new File(ECM_DIR, "ecm_coupler.py");
    private static File ECM_IN_PATH      = new File(ECM_DIR, "ecm_in.bin");
    private static File ECM_OUT_PATH     = new File(ECM_DIR, "ecm_out.bin");
    private static File ECM_STATE_PATH   = new File(ECM_DIR, "ecm_state.json");
    private static File ECM_DEBUG_LOG_PATH = new File(ECM_DIR, "ecm_debug.log");
    private static File DIAGNOSTICS_CSV_FILE  = new File(PROJECT_ROOT, DIAGNOSTICS_CSV_PATH);
    private static File TEMP_LOG_FILE         = new File(PROJECT_ROOT, TEMP_LOG_CSV_PATH);
    private static File APPLIED_HEAT_LOG_FILE = new File(PROJECT_ROOT, APPLIED_HEAT_LOG_CSV_PATH);
    private static File CURRENT_PROFILE_FILE  = new File(PROJECT_ROOT, CURRENT_PROFILE_PATH);
    private static File CELL_MAP_CSV_FILE     = new File(PROJECT_ROOT, CELL_MAP_CSV_PATH);
    private static File CELL_STEP_CSV_FILE    = new File(PROJECT_ROOT, CELL_STEP_CSV_PATH);
    private static File Q_TABLE_CSV_FILE      = new File(PROJECT_ROOT, Q_TABLE_CSV_PATH);

    /**
     * Derive PROJECT_ROOT from this macro file's location (src/ parent), update
     * all dependent File fields, and print the resolved path to the STAR log.
     * Called at the top of execute() and executeElementWise() so that the macro
     * works on any machine without environment variables or config files.
     */
    private void resolveAndSetProjectRoot(Simulation sim) {
        // If ECM_PROJECT_ROOT is explicitly set in the environment, trust it.
        String envRoot = System.getenv("ECM_PROJECT_ROOT");
        if (envRoot != null && !envRoot.isEmpty()) {
            sim.println("[ECM] PROJECT_ROOT (ECM_PROJECT_ROOT env): " + PROJECT_ROOT.getAbsolutePath()
                + (PROJECT_ROOT.exists() ? "  [OK]" : "  [WARN: not found]"));
            return;
        }
        // Auto-detect: macro lives at <ROOT>/src/EcmCouplerMacro.java
        // resolvePath("_") gives the macro's directory; one getParentFile() = src/; next = ROOT.
        try {
            File macroDir = new File(resolvePath("_")).getParentFile();
            if (macroDir != null && macroDir.getParentFile() != null
                    && macroDir.getParentFile().isDirectory()) {
                String detected = macroDir.getParentFile().getAbsolutePath();
                PROJECT_ROOT_PATH     = detected;
                PROJECT_ROOT          = new File(detected);
                ECM_DIR               = new File(PROJECT_ROOT, "ecm");
                ECM_SCRIPT_PATH       = new File(ECM_DIR, "ecm_coupler.py");
                ECM_IN_PATH           = new File(ECM_DIR, "ecm_in.bin");
                ECM_OUT_PATH          = new File(ECM_DIR, "ecm_out.bin");
                ECM_STATE_PATH        = new File(ECM_DIR, "ecm_state.json");
                ECM_DEBUG_LOG_PATH    = new File(ECM_DIR, "ecm_debug.log");
                DIAGNOSTICS_CSV_FILE  = new File(PROJECT_ROOT, DIAGNOSTICS_CSV_PATH);
                TEMP_LOG_FILE         = new File(PROJECT_ROOT, TEMP_LOG_CSV_PATH);
                APPLIED_HEAT_LOG_FILE = new File(PROJECT_ROOT, APPLIED_HEAT_LOG_CSV_PATH);
                CURRENT_PROFILE_FILE  = new File(PROJECT_ROOT, CURRENT_PROFILE_PATH);
                CELL_MAP_CSV_FILE     = new File(PROJECT_ROOT, CELL_MAP_CSV_PATH);
                CELL_STEP_CSV_FILE    = new File(PROJECT_ROOT, CELL_STEP_CSV_PATH);
                Q_TABLE_CSV_FILE      = new File(PROJECT_ROOT, Q_TABLE_CSV_PATH);
                ZONE_WEIGHTS_CSV_FILE = new File(PROJECT_ROOT, ZONE_WEIGHTS_CSV_PATH);
                ECM_MAPPING_CSV_FILE  = new File(PROJECT_ROOT, ECM_MAPPING_FILE_PATH);
                REGION_GEOMETRY_CSV_FILE = new File(PROJECT_ROOT, REGION_GEOMETRY_CSV_PATH);
            } else {
                sim.println("[ECM] ERROR: Could not auto-detect PROJECT_ROOT — macro must be at"
                    + " <ROOT>/src/EcmCouplerMacro.java. Set ECM_PROJECT_ROOT env var to override.");
            }
        } catch (Exception e) {
            sim.println("[ECM] WARN: auto-detect of PROJECT_ROOT failed: " + e.getMessage()
                + " — set ECM_PROJECT_ROOT env var.");
        }
        sim.println("[ECM] PROJECT_ROOT: " + PROJECT_ROOT.getAbsolutePath()
            + (PROJECT_ROOT.exists() ? "  [OK]" : "  [WARN: not found]"));
    }

    /**
     * Electrical mode passed to the Python ECM backend when COUPLING_MODE=elementWise.
     *
     * "sharedState"     — single SOC/T for the whole cell (lumped electrical, NOT distributed)
     * "partitionStates" — one independent ECM state per spatial zone; each zone gets its own
     *                     local temperature input and produces its own local heat output.
     *                     Requires ECM_MAPPING_FILE; falls back to synthetic zoning automatically
     *                     when the file does not exist (using ECM_N_ELEMENTS zones).
     */
    private static final String ECM_DISTRIBUTED_ELECTRICAL_MODE =
        getEnvOrDefault("ECM_DISTRIBUTED_ELECTRICAL_MODE", "parallelBranchesSharedSOC");

    /**
     * Path (relative to PROJECT_ROOT) for the spatial mapping CSV that assigns mesh cells
     * to ECM zones.  Columns: meshKey, ecmCellId, weight (m³).
     * If the file does not exist, the Python backend falls back to synthetic round-robin
     * zoning using ECM_N_ELEMENTS zones.
     */
    private static final String ECM_MAPPING_FILE_PATH =
        getEnvOrDefault("ECM_MAPPING_FILE", "ecm/ecm_mapping.csv");

    /**
     * Number of ECM zones for synthetic round-robin mapping when no mapping file exists.
     * Ignored once a real ECM_MAPPING_FILE is present.
     * Default 20 gives ~8,000 cells/zone for 160,313 jellyRoll cells.
     */
    private static final int ECM_N_ELEMENTS =
        (int) getDoubleEnvOrDefault("ECM_N_ELEMENTS", 20);

    private static File ECM_MAPPING_CSV_FILE  = new File(PROJECT_ROOT, ECM_MAPPING_FILE_PATH);

    /**
     * Path (relative to PROJECT_ROOT) for the per-cell zone-weight CSV written by
     * gen_ecm_mapping.py.  Columns: X_m, Y_m, Z_m, w_zone_0 … w_zone_{N-1}
     * Each w_zone_k column holds the overlap fraction [0,1] of that CFD cell's
     * control volume that lies inside ECM zone k.  Values sum to 1.0 per row.
     * Loaded at startup as a STAR-CCM+ FileTable; 18 UserFieldFunctions are then
     * created automatically so zone weights can be plotted in scalar scenes.
     */
    private static final String ZONE_WEIGHTS_CSV_PATH =
        getEnvOrDefault("ECM_ZONE_WEIGHTS_CSV", "ecm/ecm_zone_weights.csv");

    /** Name of the STAR-CCM+ FileTable that holds the zone-weight XYZ data. */
    private static final String ZONE_WEIGHTS_TABLE_NAME =
        getEnvOrDefault("ECM_ZONE_WEIGHTS_TABLE", "ECM_ZoneWeights_Table");

    private static File ZONE_WEIGHTS_CSV_FILE = new File(PROJECT_ROOT, ZONE_WEIGHTS_CSV_PATH);

    /**
     * Path (relative to PROJECT_ROOT) for the per-region geometry CSV written at
     * startup.  Columns: regionIdx, origin_x, origin_y, origin_z, axis_x, axis_y, axis_z.
     * Extracted from STAR-CCM+ coordinate systems named with _1, _2 suffixes matching
     * the coupled jellyRoll regions.  Read by gen_ecm_mapping.py and ecm_coupler.py
     * for correct per-region cylinder axis detection (arbitrary orientations).
     */
    private static final String REGION_GEOMETRY_CSV_PATH =
        getEnvOrDefault("ECM_REGION_GEOMETRY_CSV", "ecm/ecm_region_geometry.csv");

    private static File REGION_GEOMETRY_CSV_FILE = new File(PROJECT_ROOT, REGION_GEOMETRY_CSV_PATH);

    // =========================================================================
    // MAIN ENTRY POINT
    // =========================================================================

    @Override
    public void execute() {
        Simulation sim = getActiveSimulation();
        resolveAndSetProjectRoot(sim);

        // --- startup diagnostics ---
        String javaCwd = new File(".").getAbsolutePath();

        sim.println("[ECM] ==== ECM COUPLER STARTUP ====");
        sim.println("[ECM] Java CWD: " + javaCwd);
        sim.println("[ECM] OS: " + System.getProperty("os.name") + " " + System.getProperty("os.version"));
        sim.println("[ECM] Java: " + System.getProperty("java.version"));
        sim.println("[ECM] ECM_DIR: " + ECM_DIR.getAbsolutePath());
        sim.println("[ECM] PYTHON_CMD: " + PYTHON_CMD);
        sim.println(String.format("[ECM] CURRENT_A: %.9e A", CURRENT_A));
        sim.println("[ECM] ECM_CALL_EVERY_N_STEPS: " + ECM_CALL_EVERY_N_STEPS + " (0 = every CFD timestep)");
        sim.println("[ECM] DIAGNOSTICS_CSV_FILE: " + DIAGNOSTICS_CSV_FILE.getAbsolutePath());
        sim.println("[ECM] ECM_SCRIPT_PATH: " + ECM_SCRIPT_PATH.getAbsolutePath()
            + "  exists=" + ECM_SCRIPT_PATH.exists());
        sim.println("[ECM] ECM_IN_PATH: " + ECM_IN_PATH.getAbsolutePath());
        sim.println("[ECM] ECM_OUT_PATH: " + ECM_OUT_PATH.getAbsolutePath());
        sim.println("[ECM] ECM_STATE_PATH: " + ECM_STATE_PATH.getAbsolutePath());
        sim.println("[ECM] ECM_DEBUG_LOG_PATH: " + ECM_DEBUG_LOG_PATH.getAbsolutePath());
        sim.println("[ECM] USE_PERSISTENT_PYTHON: " + USE_PERSISTENT_PYTHON);
        sim.println("[ECM] CURRENT_PROFILE_FILE: " + CURRENT_PROFILE_FILE.getAbsolutePath()
            + "  exists=" + CURRENT_PROFILE_FILE.exists());

        if (!PROJECT_ROOT.exists() || !PROJECT_ROOT.isDirectory()) {
            sim.println("[ECM] ERROR: PROJECT_ROOT does not exist or is not a directory: "
                + PROJECT_ROOT.getAbsolutePath());
            return;
        }

        if (!ECM_DIR.exists() && !ECM_DIR.mkdirs()) {
            sim.println("[ECM] ERROR: Could not create ECM_DIR: " + ECM_DIR.getAbsolutePath());
            return;
        }

        if (!ECM_SCRIPT_PATH.exists() || !ECM_SCRIPT_PATH.isFile()) {
            sim.println("[ECM] ERROR: ECM Python script not found: " + ECM_SCRIPT_PATH.getAbsolutePath());
            printDirectoryContents(sim, ECM_DIR);
            return;
        }

        printDirectoryContents(sim, ECM_DIR);

        // --- discover all coupled regions (names containing REGION_NAME_PATTERN) ---
        List<Region> coupledRegions = new ArrayList<>();
        for (Object obj : sim.getRegionManager().getObjects()) {
            if (obj instanceof Region) {
                Region r = (Region) obj;
                if (r.getPresentationName().contains(REGION_NAME_PATTERN)) {
                    coupledRegions.add(r);
                }
            }
        }
        Collections.sort(coupledRegions,
            Comparator.comparing(NamedObject::getPresentationName));

        if (coupledRegions.isEmpty()) {
            sim.println("[ECM] ERROR: no regions whose name contains '"
                + REGION_NAME_PATTERN + "'. Aborting.");
            return;
        }

        StringBuilder regionNames = new StringBuilder();
        for (Region r : coupledRegions) {
            if (regionNames.length() > 0) regionNames.append(", ");
            regionNames.append(r.getPresentationName());
        }
        sim.println("[ECM] Coupled regions (" + coupledRegions.size() + "): " + regionNames);
        sim.println("[ECM] COUPLING_MODE: " + COUPLING_MODE);
        sim.println("[ECM] ECM_DISTRIBUTED_ELECTRICAL_MODE: " + ECM_DISTRIBUTED_ELECTRICAL_MODE);
        sim.println("[ECM] ECM_MAPPING_FILE: " + ECM_MAPPING_CSV_FILE.getAbsolutePath()
            + "  exists=" + ECM_MAPPING_CSV_FILE.exists());
        sim.println("[ECM] ECM_N_ELEMENTS: " + ECM_N_ELEMENTS
            + (ECM_MAPPING_CSV_FILE.exists() ? " (ignored — mapping file present)" : " (synthetic fallback)"));
        sim.println("[ECM] T_EXTRACTION_BACKEND: " + T_EXTRACTION_BACKEND);
        sim.println("[ECM] T_TABLE_NAME: " + T_TABLE_NAME);

        // --- dispatch to lumped or elementWise coupling loop ---
        if ("elementWise".equalsIgnoreCase(COUPLING_MODE)) {
            executeElementWise(sim, coupledRegions);
            return;
        }

        // --- lumped multi-region: N>1 regions with csvReload table injection ---
        if (coupledRegions.size() > 1 && "csvReload".equalsIgnoreCase(INJECTION_MODE)) {
            sim.println("[ECM] Dispatching to lumped multi-region coupling ("
                + coupledRegions.size() + " regions, csvReload injection).");
            executeLumpedMultiRegion(sim, coupledRegions);
            return;
        }

        // --- lumped: use first (primary) region only (N=1 or globalParam fallback) ---
        Region region = coupledRegions.get(0);

        // Determine once whether this is a fresh run (t≈0) or a continuation (t>0).
        double _lumpedInitTime = tryGetPhysicalTimeFromStar(sim);
        boolean freshStart = Double.isFinite(_lumpedInitTime) && _lumpedInitTime < 1e-9;
        sim.println("[ECM] Run mode: " + (freshStart ? "FRESH (t=0)"
            : "CONTINUATION (t=" + String.format("%.3f", _lumpedInitTime) + " s)"));

        // --- create or reuse VolumeAverageReport for Temperature ---
        VolumeAverageReport tReport = getOrCreateTReport(sim, coupledRegions);
        sim.println("[ECM] T report ready: " + tReport.getPresentationName());

        // --- locate/create the heat-source parameter ---
        ScalarGlobalParameter qParam = getOrCreateQParam(sim);
        sim.println("[ECM] Heat-source parameter: " + qParam.getPresentationName());

        // --- csvReload injection setup for lumped mode (one-time) ---
        // When INJECTION_MODE=csvReload the STAR energy source is wired to the
        // FileTable, not the ecmQdot_W global parameter.  Write a per-cell uniform
        // CSV every step so the FileTable stays current even in lumped mode.
        CellMapper lumpedCellMapper = null;
        star.common.FileTable lumpedQTable = null;
        if ("csvReload".equalsIgnoreCase(INJECTION_MODE)) {
            try {
                lumpedCellMapper = buildMergedCellMapper(sim, coupledRegions);
                sim.println(String.format(
                    "[ECM] lumped csvReload: cellMapper ready (%d cells).", lumpedCellMapper.n));
                // Write fresh ecm_cell_map.csv so Python's _maybe_regen_mapping() detects
                // any mesh change and regenerates ecm_mapping.csv before the first ECM call.
                try {
                    writeCellMapCsv(CELL_MAP_CSV_FILE, lumpedCellMapper);
                    sim.println("[ECM] lumped csvReload: cell map written → " + CELL_MAP_CSV_FILE.getName());
                } catch (IOException _ioEx) {
                    sim.println("[ECM] WARN: lumped csvReload: could not write cell map CSV: " + _ioEx.getMessage());
                }
                lumpedQTable = getOrCreateQInjectionTable(sim);
                if (lumpedQTable != null) {
                    autoConfigureJellyRollEnergySource(sim, region, lumpedQTable);
                    sim.println("[ECM] lumped csvReload: FileTable + energy source configured.");
                } else {
                    sim.println("[ECM] WARN: lumped csvReload: could not get FileTable — will use globalParam.");
                    lumpedCellMapper = null;
                }
            } catch (Exception ex) {
                sim.println("[ECM] WARN: lumped csvReload setup failed (" + ex.getMessage()
                    + ") — will use globalParam.");
                lumpedCellMapper = null;
                lumpedQTable = null;
            }
        }

        // --- open persistent debug log ---
        PrintWriter debugLog = null;
        PrintWriter diagnosticsCsv = null;
        try {
            debugLog = new PrintWriter(new FileWriter(ECM_DEBUG_LOG_PATH, true));
            debugLog.println("=== ECM DEBUG LOG  " + new java.util.Date() + " ===");
            debugLog.println("Java CWD: " + javaCwd);
            debugLog.println("PROJECT_ROOT: " + PROJECT_ROOT.getAbsolutePath());
            debugLog.println("PYTHON_CMD: " + PYTHON_CMD);
            debugLog.println(String.format("CURRENT_A: %.9e A", CURRENT_A));
            debugLog.println("ECM_CALL_EVERY_N_STEPS: " + ECM_CALL_EVERY_N_STEPS + " (0 = every CFD timestep)");
            debugLog.println("ECM_SCRIPT_PATH: " + ECM_SCRIPT_PATH.getAbsolutePath());
            debugLog.println("ECM_IN_PATH: " + ECM_IN_PATH.getAbsolutePath());
            debugLog.println("ECM_OUT_PATH: " + ECM_OUT_PATH.getAbsolutePath());
            debugLog.println("ECM_STATE_PATH: " + ECM_STATE_PATH.getAbsolutePath());
            debugLog.flush();
        } catch (IOException e) {
            sim.println("[ECM] WARN: could not open debug log: " + e.getMessage());
        }
        try {
            File parent = DIAGNOSTICS_CSV_FILE.getParentFile();
            if (parent != null && !parent.exists()) {
                parent.mkdirs();
            }
            diagnosticsCsv = new PrintWriter(new FileWriter(DIAGNOSTICS_CSV_FILE, !freshStart));
            if (freshStart) {
                diagnosticsCsv.println(
                    "step,stepId,time_s,deltaT_s,T_eff_K,T_eff_C,current_A,qGen_W,"
                    + "cumulativeEnergy_J,deltaT_C");
            }
            diagnosticsCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM] WARN: could not open diagnostics CSV: " + e.getMessage());
        }

        // --- open dedicated tempLog.csv (jellyRoll volume-average T, STAR monitor source) ---
        // Fresh start: overwrite with header. Continuation: append (no duplicate header).
        PrintWriter tempLogCsv = null;
        try {
            File parent = TEMP_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            tempLogCsv = new PrintWriter(new FileWriter(TEMP_LOG_FILE, !freshStart));
            if (freshStart) { tempLogCsv.println("time_s,temp_c"); }
            tempLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM] WARN: could not open tempLog.csv: " + e.getMessage());
        }

        // --- open dedicated appliedTotalHeatLog.csv (STAR-applied heat, relaxed W) ---
        PrintWriter appliedHeatLogCsv = null;
        try {
            File parent = APPLIED_HEAT_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            appliedHeatLogCsv = new PrintWriter(new FileWriter(APPLIED_HEAT_LOG_FILE, !freshStart));
            if (freshStart) { appliedHeatLogCsv.println("time_s,applied_total_heat_w"); }
            appliedHeatLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM] WARN: could not open appliedTotalHeatLog.csv: " + e.getMessage());
        }

        // On fresh start: delete ecm_state.json so Python ECM begins at SOC=1.
        // On continuation: preserve it so Python resumes from saved SOC / RC voltages.
        if (freshStart) {
            try {
                if (Files.deleteIfExists(ECM_STATE_PATH.toPath())) {
                    sim.println("[ECM] Fresh run (t=0): deleted ecm_state.json — ECM will start at SOC=1.");
                }
            } catch (IOException e) {
                sim.println("[ECM] WARN: could not delete ecm_state.json: " + e.getMessage());
            }
        } else {
            sim.println("[ECM] Continuation run: preserving ecm_state.json for ECM state resume.");
            if (!ECM_STATE_PATH.exists()) {
                sim.println("[ECM] WARN: ecm_state.json not found on continuation — "
                    + "ECM will reinitialise at SOC=1.");
            }
        }

        // --- coupling loop ---
        SimulationIterator iter = sim.getSimulationIterator();
        CurrentProfile currentProfile = CurrentProfile.load(sim, CURRENT_PROFILE_FILE, CURRENT_A);
        PersistentEcmProcess persistentProcess = null;
        if (USE_PERSISTENT_PYTHON) {
            persistentProcess = PersistentEcmProcess.start(sim, debugLog);
        }

        double qVolPrev = 0.0;
        long stepId = 0L;
        double cumulativeRequestedEnergyJ = 0.0;
        double tEffInitial = Double.NaN;

        double accumulatedTime = INITIAL_TIME_S;
        double physicalTimeFromStar = tryGetPhysicalTimeFromStar(sim);
        if (Double.isFinite(physicalTimeFromStar) && physicalTimeFromStar >= 0.0) {
            accumulatedTime = physicalTimeFromStar;
            sim.println(String.format("[ECM] Initial physical time from STAR API: %.9e s", accumulatedTime));
        } else {
            sim.println(String.format("[ECM] STAR physical-time API not available. Using accumulated time from INITIAL_TIME_S=%.9e s", accumulatedTime));
        }

        // Reset heat-source parameter to 0 before first step (prevent stale value from previous run)
        qParam.getQuantity().setValue(0.0);
        sim.println("[ECM] Reset ecmQdot_W to 0.0 W before coupling loop.");

        // --- Pre-warm-up ECM call (lumped, fresh starts only) ---
        // WHY: iter.step(1) runs BEFORE the ECM is called, so the first solver
        // step always runs with Q=0 (reset above). That produces a one-step
        // transient: step 1 has Q=0, step 2 has the first real ECM heat.
        //
        // Fix: probe the ECM at the STAR IC temperature (read via tReport.getValue())
        // with stepId=0, deltaT=0 (no SoC advancement) and apply the result before
        // the loop, so step 1 uses an IC-consistent heat source.
        //
        // Continuation runs are skipped (qVolPrev already holds last step value).
        if (freshStart) {
            sim.println("[ECM] Pre-warm-up: probing ECM at STAR IC temperature "
                + "(stepId=0, deltaT=0 — no SoC advancement).");
            double wuTAvg;
            try {
                wuTAvg = tReport.getValue();
            } catch (Exception e) {
                wuTAvg = Double.NaN;
                sim.println("[ECM] WARN: pre-warm-up tReport.getValue() failed: " + e.getMessage());
            }
            if (Double.isFinite(wuTAvg)) {
                sim.println(String.format("[ECM] Pre-warm-up IC T_avg=%.4f K (%.2f C)",
                    wuTAvg, wuTAvg - 273.15));
                double wuCurrent = currentProfile.currentAt(0.0);
                byte[] wuInputBytes = null;
                try {
                    wuInputBytes = EcmBinaryIO.buildLumpedInputBytes(
                        0L, wuTAvg, 0.0, 0.0, wuCurrent, 0.0);
                } catch (IOException e) {
                    sim.println("[ECM] WARN: pre-warm-up input build failed: " + e.getMessage()
                        + " — step 1 will start with Q=0.");
                }
                if (wuInputBytes != null) {
                    double wuQGenW = Double.NaN;
                    if (persistentProcess != null) {
                        try {
                            wuQGenW = persistentProcess.exchange(sim, wuInputBytes, 0L, debugLog);
                        } catch (IOException e) {
                            sim.println("[ECM] WARN: pre-warm-up persistent exchange failed: "
                                + e.getMessage() + " — falling back to file-based.");
                            persistentProcess.close();
                            persistentProcess = null;
                        }
                    }
                    if ((Double.isNaN(wuQGenW) || !Double.isFinite(wuQGenW)) && persistentProcess == null) {
                        try {
                            EcmBinaryIO.writeBytes(ECM_IN_PATH, wuInputBytes);
                            int wuExit = runProcess(sim, debugLog);
                            if (wuExit == 0 && waitForFile(ECM_OUT_PATH, ECM_TIMEOUT_S)) {
                                wuQGenW = EcmBinaryIO.readLumpedOutput(ECM_OUT_PATH, 0L);
                            } else {
                                sim.println("[ECM] WARN: pre-warm-up ECM call failed (exit=" + wuExit
                                    + ") — step 1 will start with Q=0.");
                            }
                        } catch (IOException e) {
                            sim.println("[ECM] WARN: pre-warm-up file exchange failed: "
                                + e.getMessage() + " — step 1 will start with Q=0.");
                        }
                    }
                    if (Double.isFinite(wuQGenW) && !Double.isNaN(wuQGenW)) {
                        sim.println(String.format("[ECM] Pre-warm-up Q=%.6e W. Seeding heat source.", wuQGenW));
                        if ("csvReload".equalsIgnoreCase(INJECTION_MODE)
                                && lumpedCellMapper != null && lumpedQTable != null) {
                            double[] wuUniform = new double[lumpedCellMapper.n];
                            Arrays.fill(wuUniform, wuQGenW);
                            try {
                                applyElementWiseHeatCsv(sim, lumpedCellMapper, wuUniform, lumpedQTable);
                            } catch (IOException e) {
                                sim.println("[ECM] WARN: pre-warm-up csvReload injection failed: "
                                    + e.getMessage());
                            }
                        } else {
                            qParam.getQuantity().setValue(wuQGenW);
                        }
                        qVolPrev = wuQGenW;
                        sim.println("[ECM] Pre-warm-up complete: heat source seeded with IC-consistent Q."
                            + " Jump at t=deltaT eliminated.");
                    } else {
                        sim.println("[ECM] WARN: pre-warm-up returned no valid Q — step 1 starts with Q=0.");
                    }
                }
            } else {
                sim.println("[ECM] WARN: pre-warm-up skipped — IC T not available from tReport.");
            }
        }

        for (int step = 0; step < N_STEPS; step++) {

            // 1. Advance solver one timestep
            iter.step(1);
            stepId++;

            // 2. Read volume-average T and timestep size
            long _tStepStart = System.nanoTime();
            double tEff = tReport.getValue();
            double deltaT = getDeltaT(sim);
            long _tAfterTExtract = System.nanoTime();

            if (!Double.isFinite(deltaT) || deltaT <= 0.0) {
                sim.println(String.format(
                    "[ECM] WARN: invalid STAR deltaT. Using FALLBACK_DELTA_T_S=%.9e s",
                    FALLBACK_DELTA_T_S));
                deltaT = FALLBACK_DELTA_T_S;
            }

            // Prefer STAR physical-time API if available. Otherwise use accumulated time.
            physicalTimeFromStar = tryGetPhysicalTimeFromStar(sim);
            double simTime;
            if (Double.isFinite(physicalTimeFromStar) && physicalTimeFromStar >= 0.0) {
                simTime = physicalTimeFromStar;
                accumulatedTime = physicalTimeFromStar;
            } else {
                accumulatedTime += deltaT;
                simTime = accumulatedTime;
            }

            double currentAThisStep = currentProfile.currentAt(simTime);
            sim.println(String.format(
                "[ECM] step=%d  stepId=%d  t=%.9e s  deltaT=%.9e s  T_eff=%.6f K (%.2f C)  current_A=%.9e",
                step, stepId, simTime, deltaT, tEff, tEff - 273.15, currentAThisStep));

            if (debugLog != null) {
                debugLog.println(String.format(
                    "[ECM] step=%d stepId=%d t=%.9e deltaT=%.9e T_eff=%.6f current_A=%.9e",
                    step, stepId, simTime, deltaT, tEff, currentAThisStep));
                debugLog.flush();
            }

            // 3. Build ECM request payload
            byte[] inputBytes;
            try {
                // On the very first step pass q_ah_init=0.0 so Python starts at SOC=1 (full cell).
                // Convention: q_ah=0 means fully charged (charge throughput=0); q_ah=CAPACITY_AH means empty.
                double qAhInit = (step == 0) ? 0.0 : Double.NaN;
                inputBytes = EcmBinaryIO.buildLumpedInputBytes(
                    stepId, tEff, simTime, deltaT, currentAThisStep, qAhInit
                );
            } catch (IOException e) {
                sim.println("[ECM] ERROR building ECM request: " + e.getMessage());
                break;
            }

            double qGenW;
            if (persistentProcess != null) {
                try {
                    qGenW = persistentProcess.exchange(sim, inputBytes, stepId, debugLog);
                } catch (IOException e) {
                    sim.println("[ECM] WARNING: resident ECM exchange failed: " + e.getMessage());
                    persistentProcess.close();
                    persistentProcess = null;
                    qParam.getQuantity().setValue(qVolPrev);
                    continue;
                }
            } else {
                try {
                    Files.deleteIfExists(ECM_OUT_PATH.toPath());
                } catch (IOException e) {
                    sim.println("[ECM] WARN: could not delete stale ecm_out.bin: " + e.getMessage());
                }

                long _tBeforeWrite = System.nanoTime();
                try {
                    EcmBinaryIO.writeBytes(ECM_IN_PATH, inputBytes);
                    long _writeMs = (System.nanoTime() - _tBeforeWrite) / 1_000_000L;
                    sim.println("[ECM] ecm_in.bin written OK  (" + ECM_IN_PATH.length() + " bytes)"
                        + (HEAVY_LOG ? String.format("  write=%d ms", _writeMs) : ""));
                } catch (IOException e) {
                    sim.println("[ECM] ERROR writing ecm_in.bin: " + e.getMessage());
                    qParam.getQuantity().setValue(qVolPrev);
                    continue;
                }

                long _tBeforePython = System.nanoTime();
                int exitCode = runProcess(sim, debugLog);
                if (exitCode != 0) {
                    sim.println("[ECM] WARNING: ECM exited with code " + exitCode + ". Keeping previous qVol.");
                    qParam.getQuantity().setValue(qVolPrev);
                    continue;
                }

                if (!waitForFile(ECM_OUT_PATH, ECM_TIMEOUT_S)) {
                    sim.println("[ECM] WARNING: ecm_out.bin not found within timeout. Keeping previous qVol.");
                    qParam.getQuantity().setValue(qVolPrev);
                    continue;
                }

                long _tBeforeRead = System.nanoTime();
                try {
                    qGenW = EcmBinaryIO.readLumpedOutput(ECM_OUT_PATH, stepId);
                } catch (IOException e) {
                    sim.println("[ECM] ERROR reading ecm_out.bin: " + e.getMessage());
                    qParam.getQuantity().setValue(qVolPrev);
                    continue;
                }
                if (HEAVY_LOG) {
                    long _pythonMs = (_tBeforeRead - _tBeforePython) / 1_000_000L;
                    long _readMs   = (System.nanoTime() - _tBeforeRead) / 1_000_000L;
                    sim.println(String.format(
                        "[ECM-timing] Textract=%d ms  python=%d ms  read=%d ms",
                        (_tAfterTExtract - _tStepStart) / 1_000_000L, _pythonMs, _readMs));
                }
            }

            if (Double.isNaN(qGenW)) {
                sim.println("[ECM] WARNING: stepId mismatch in ECM output. Keeping previous qVol.");
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            if (!Double.isFinite(qGenW)) {
                sim.println("[ECM] WARNING: non-finite qVol from ECM. Keeping previous qVol.");
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            // ECM returns Q_GEN [W] — pass through directly as total power.
            // 8. Under-relaxation
            long _tBeforeApply = System.nanoTime();
            double qVol = ALPHA * qGenW + (1.0 - ALPHA) * qVolPrev;
            qVolPrev = qVol;

            if (!Double.isFinite(tEffInitial)) {
                tEffInitial = tEff;
            }
            cumulativeRequestedEnergyJ += qGenW * deltaT;
            double deltaTC = tEff - tEffInitial;

            sim.println(String.format(
                "[ECM] qGen_W=%.9e  qVol_relaxed=%.9e  cumE_J=%.9e  deltaT_C=%.6f",
                qGenW, qVol, cumulativeRequestedEnergyJ, deltaTC));

            if (debugLog != null) {
                debugLog.println(String.format(
                    "[ECM] qGen_W=%.9e qVol_relaxed=%.9e cumulativeEnergy_J=%.9e deltaT_C=%.9e",
                    qGenW, qVol, cumulativeRequestedEnergyJ, deltaTC));
                debugLog.flush();
            }
            if (diagnosticsCsv != null) {
                diagnosticsCsv.println(String.format(
                    "%.0f,%.0f,%.9e,%.9e,%.9e,%.6f,%.9e,%.9e,%.9e,%.6f",
                    (double) step, (double) stepId, simTime, deltaT, tEff, tEff - 273.15,
                    currentAThisStep, qGenW, cumulativeRequestedEnergyJ, deltaTC
                ));
                diagnosticsCsv.flush();
            }

            // 9. Apply heat: csvReload (uniform per-cell CSV + FileTable.extract) or globalParam.
            if ("csvReload".equalsIgnoreCase(INJECTION_MODE)
                    && lumpedCellMapper != null && lumpedQTable != null) {
                double[] qUniform = new double[lumpedCellMapper.n];
                java.util.Arrays.fill(qUniform, qVol);
                try {
                    applyElementWiseHeatCsv(sim, lumpedCellMapper, qUniform, lumpedQTable);
                } catch (IOException e) {
                    sim.println("[ECM] FATAL: lumped csvReload injection failed: " + e.getMessage());
                    sim.println("[ECM] Aborting coupling loop.");
                    if (persistentProcess != null) persistentProcess.close();
                    return;
                }
            } else {
                qParam.getQuantity().setValue(qVol);
            }

            // 10. Write dedicated time-history CSVs (one row per accepted coupling step).
            //     tempLog.csv  — source: STAR VolumeAverageReport (jellyRoll), NOT T_eff_K from ECM.
            //     appliedTotalHeatLog.csv — source: relaxed qVol set on ecmQdot_W parameter.
            if (tempLogCsv != null) {
                tempLogCsv.println(String.format("%.9e,%.6f", simTime, tEff - 273.15));
                tempLogCsv.flush();
            }
            if (appliedHeatLogCsv != null) {
                appliedHeatLogCsv.println(String.format("%.9e,%.9e", simTime, qVol));
                appliedHeatLogCsv.flush();
            }

            if (HEAVY_LOG) {
                long _applyMs = (System.nanoTime() - _tBeforeApply) / 1_000_000L;
                long _totalMs = (System.nanoTime() - _tStepStart) / 1_000_000L;
                sim.println(String.format(
                    "[ECM-timing] apply=%d ms  TOTAL_step=%d ms", _applyMs, _totalMs));
                sim.println(String.format(
                    "[ECM-heavy]  T_eff=%.4f K  Q_raw=%.6f W  Q_applied=%.6f W  alpha=%.3f",
                    tEff, qGenW, qVol, ALPHA));
            }
        }

        sim.println("[ECM] Coupling loop complete.");
        if (persistentProcess != null) {
            persistentProcess.close();
        }

        if (debugLog != null) {
            debugLog.println("=== LOOP COMPLETE ===");
            debugLog.close();
        }
        if (diagnosticsCsv != null) {
            diagnosticsCsv.close();
        }
        if (tempLogCsv != null) {
            tempLogCsv.close();
        }
        if (appliedHeatLogCsv != null) {
            appliedHeatLogCsv.close();
        }
    }

    // =========================================================================
    // ELEMENT-WISE COUPLING (Phase 1)
    // =========================================================================

    /**
     * Main loop for elementWise (distributed) coupling mode.
     *
     * Each timestep:
     *   1. Collect per-cell temperatures from STAR via FvRepresentation.
     *   2. Write ecm_in.bin with N records (cellId, T_K).
     *   3. Call the external ECM backend (same as lumped mode).
     *   4. Read ecm_out.bin with N records (cellId, qVol_W/m³).
     *   5. Write ecm_cell_step.csv for per-step visualisation.
     *   6. Apply heat source (Phase 1: logs only; Phase 3 adds STAR field function).
     *
     * On first call, writes ecm_cell_map.csv (cellId, x_m, y_m, z_m).
     */
    private void executeElementWise(Simulation sim, List<Region> regions) {
        resolveAndSetProjectRoot(sim);
        nRegionsForEnv = regions.size();
        Region region = regions.get(0);  // primary region (for T report, logging)

        sim.println("[ECM-EW] Starting elementWise coupling setup.");
        sim.println("[ECM-EW] T_EXTRACTION_BACKEND: " + T_EXTRACTION_BACKEND);
        sim.println("[ECM-EW] T_TABLE_NAME: " + T_TABLE_NAME);
        if ("xyzTableInMemory".equalsIgnoreCase(T_EXTRACTION_BACKEND)) {
            sim.println("[ECM-EW] Using in-memory XYZ Internal Table for per-cell T extraction.");
            sim.println("[ECM-EW] Table must exist in .sim as: \"" + T_TABLE_NAME + "\"");
            sim.println("[ECM-EW] If extraction fails, coupling will ABORT (not silently fall back).");
        } else if ("directFieldData".equalsIgnoreCase(T_EXTRACTION_BACKEND)) {
            sim.println("[ECM-EW] WARNING: directFieldData backend is BROKEN in STAR-CCM+ 2602.");
            sim.println("[ECM-EW]   Use ECM_T_EXTRACTION_BACKEND=xyzTableInMemory instead.");
        }

        // --- initialise CellMapper (enumerates all coupled cells, writes cell_map.csv) ---
        CellMapper cellMapper;
        try {
            cellMapper = buildMergedCellMapper(sim, regions);
        } catch (Exception e) {
            sim.println("[ECM-EW] ERROR creating CellMapper: " + e.getMessage());
            e.printStackTrace();
            return;
        }

        int n = cellMapper.nCells();
        sim.println(String.format("[ECM-EW] CellMapper ready: %d cells across %d region(s).",
            n, regions.size()));

        // write cell map CSV once (for visualisation)
        try {
            writeCellMapCsv(CELL_MAP_CSV_FILE, cellMapper);
            sim.println("[ECM-EW] Cell map written: " + CELL_MAP_CSV_FILE.getAbsolutePath());
        } catch (IOException e) {
            sim.println("[ECM-EW] WARN: could not write cell map CSV: " + e.getMessage());
        }

        // write per-region geometry CSV (coordinate system origin + axis for each jelly roll)
        if (regions.size() > 1) {
            try {
                writeRegionGeometryCsv(sim, REGION_GEOMETRY_CSV_FILE, regions, cellMapper);
                sim.println("[ECM-EW] Region geometry written: " + REGION_GEOMETRY_CSV_FILE.getAbsolutePath());
            } catch (Exception e) {
                sim.println("[ECM-EW] WARN: could not write region geometry CSV: " + e.getMessage());
            }
        }

        // Determine once whether this is a fresh run (t≈0) or a continuation (t>0).
        // Used for: ecm_mapping.csv deletion, ecm_state.json deletion, log file mode.
        // NaN means the STAR API couldn't return a time — treat as fresh start (safe default).
        double _initPhysTime = tryGetPhysicalTimeFromStar(sim);
        boolean freshStart = !Double.isFinite(_initPhysTime) || _initPhysTime < 1e-9;
        sim.println("[ECM-EW] Run mode: " + (freshStart ? "FRESH (t=0)" : "CONTINUATION (t="
            + String.format("%.3f", _initPhysTime) + " s)")
            + (!Double.isFinite(_initPhysTime) ? "  [time query returned NaN — treating as fresh]" : ""));

        // Always regenerate from the current STAR mesh on macro startup.  Do not
        // try to prove an old mapping is still usable: remeshing can preserve row
        // count while changing ordering, centroids, volumes, or region labels.
        if (ECM_MAPPING_CSV_FILE != null) {
            sim.println("[ECM-EW] Regenerating ecm_mapping.csv from current mesh every startup.");
            try {
                Files.deleteIfExists(ECM_MAPPING_CSV_FILE.toPath());
                Files.deleteIfExists(ZONE_WEIGHTS_CSV_FILE.toPath());
                regenEcmMapping(sim);
            } catch (Exception e) {
                sim.println(e.getMessage());
                sim.println("[ECM-EW] Aborting elementWise coupling.");
                return;
            }
        }

        // On fresh start: delete ecm_state.json so Python ECM begins at SOC=1.
        // On continuation: preserve it so Python resumes from the saved SOC / RC voltages.
        if (freshStart) {
            try {
                if (Files.deleteIfExists(ECM_STATE_PATH.toPath())) {
                    sim.println("[ECM-EW] Fresh run (t=0): deleted ecm_state.json — ECM will start at SOC=1.");
                }
            } catch (IOException e) {
                sim.println("[ECM-EW] WARN: could not delete ecm_state.json: " + e.getMessage());
            }
        } else {
            sim.println("[ECM-EW] Continuation run: preserving ecm_state.json for ECM state resume.");
            if (!ECM_STATE_PATH.exists()) {
                sim.println("[ECM-EW] WARN: ecm_state.json not found on continuation — "
                    + "ECM will reinitialise at SOC=1 (expected only on first continuation segment).");
            }
        }

        // --- csvReload injection setup (one-time, before loop) ---
        star.common.FileTable qInjectionTable = null;
        if ("csvReload".equalsIgnoreCase(INJECTION_MODE)) {
            qInjectionTable = getOrCreateQInjectionTable(sim);
            sim.println(String.format(
                "[ECM-EW] csvReload injection ready: %d cells, zone volume constant=%.4e m3",
                n, JELLY_ROLL_VOLUME_M3));
            if (qInjectionTable != null) {
                for (Region jr : regions) {
                    autoConfigureJellyRollEnergySource(sim, jr, qInjectionTable);
                }
            } else {
                sim.println("[ECM-EW] FATAL: FileTable '" + Q_TABLE_NAME + "' could not be created. "
                    + "Per-cell heat injection is not possible without it. Aborting.");
                return;
            }
        } else {
            sim.println("[ECM-EW] INJECTION_MODE=globalParam: sum per-cell W → ecmQdot_W parameter.");
        }

        // DIAG-1: log the active profile method type for each jellyRoll
        diagProfileMethodType(sim, regions);

        // DIAG-3: create energy-source reports (Min / Max / VolumeIntegral)
        final List<star.base.report.Report> energySourceReports =
            getOrCreateEnergySourceReports(sim, regions);

        // --- zone-weight visualization (one UserFieldFunction per ECM zone) ---
        setupWeightVisualization(sim);

        // --- volume-average T report (authoritative STAR monitor for tempLog.csv) ---
        VolumeAverageReport tReport = getOrCreateTReport(sim, regions);
        sim.println("[ECM-EW] Volume-average T report ready: " + tReport.getPresentationName());

        PrintWriter debugLog = null;
        try {
            debugLog = new PrintWriter(new FileWriter(ECM_DEBUG_LOG_PATH, true));
            debugLog.println("=== ECM-EW DEBUG LOG  " + new java.util.Date() + " ===");
            debugLog.println("COUPLING_MODE: elementWise");
            debugLog.println("nCells: " + n);
            debugLog.flush();
        } catch (IOException e) {
            sim.println("[ECM-EW] WARN: could not open debug log: " + e.getMessage());
        }

        // --- open dedicated tempLog.csv (STAR VolumeAverageReport source) ---
        // Fresh start: overwrite (new header). Continuation: append (no header).
        PrintWriter tempLogCsv = null;
        try {
            File parent = TEMP_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            tempLogCsv = new PrintWriter(new FileWriter(TEMP_LOG_FILE, !freshStart));
            if (freshStart) { tempLogCsv.println("time_s,temp_c"); }
            tempLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM-EW] WARN: could not open tempLog.csv: " + e.getMessage());
        }

        // --- open dedicated appliedTotalHeatLog.csv (STAR-applied heat source) ---
        PrintWriter appliedHeatLogCsv = null;
        try {
            File parent = APPLIED_HEAT_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            appliedHeatLogCsv = new PrintWriter(new FileWriter(APPLIED_HEAT_LOG_FILE, !freshStart));
            if (freshStart) { appliedHeatLogCsv.println("time_s,applied_total_heat_w"); }
            appliedHeatLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM-EW] WARN: could not open appliedTotalHeatLog.csv: " + e.getMessage());
        }

        SimulationIterator iter = sim.getSimulationIterator();
        CurrentProfile currentProfile = CurrentProfile.load(sim, CURRENT_PROFILE_FILE, CURRENT_A);
        PersistentEcmProcess persistentProcess = null;
        if (USE_PERSISTENT_PYTHON) {
            persistentProcess = PersistentEcmProcess.start(sim, debugLog);
        }

        // previous qVol per cell (fallback when ECM call fails)
        double[] qVolPrev = new double[n];  // per-cell W from previous step (fallback)

        // --- Pre-warm-up ECM call (elementWise, fresh starts only) ---
        // WHY: iter.step(1) runs BEFORE the ECM is called, so the injection
        // FileTable used for the first solver step comes from whatever was on disk
        // at startup (ecm_qvol_injection.csv). Stale values → jump at t=deltaT.
        //
        // Fix: before the loop, probe the ECM at the STAR IC temperature (read via
        // tReport.getValue()) with stepId=0, deltaT=0 (no SoC advancement) and
        // write the result to the injection CSV so step 1 uses IC-consistent heat.
        //
        // Continuation runs are skipped — FileTable already holds correct values
        // from the previous run's last step.
        if (freshStart && "csvReload".equalsIgnoreCase(INJECTION_MODE) && qInjectionTable != null) {
            sim.println("[ECM-EW] Pre-warm-up: probing ECM at STAR IC temperature "
                + "(stepId=0, deltaT=0 — no SoC advancement).");
            double wuTAvg;
            try {
                wuTAvg = tReport.getValue();
            } catch (Exception e) {
                wuTAvg = Double.NaN;
                sim.println("[ECM-EW] WARN: pre-warm-up tReport.getValue() failed: " + e.getMessage());
            }
            if (Double.isFinite(wuTAvg)) {
                sim.println(String.format("[ECM-EW] Pre-warm-up IC T_avg=%.4f K (%.2f C)",
                    wuTAvg, wuTAvg - 273.15));
                double[] wuTemps = new double[n];
                Arrays.fill(wuTemps, wuTAvg);
                double wuCurrent = currentProfile.currentAt(0.0);
                byte[] wuInputBytes = null;
                try {
                    wuInputBytes = EcmBinaryIO.buildElementWiseInputBytes(
                        0L, cellMapper.cellIds(), wuTemps, 0.0, 0.0, wuCurrent);
                } catch (IOException e) {
                    sim.println("[ECM-EW] WARN: pre-warm-up input build failed: " + e.getMessage()
                        + " — step 1 will use stale injection file values.");
                }
                if (wuInputBytes != null) {
                    Map<Integer, Double> wuQVolMap = null;
                    if (persistentProcess != null) {
                        try {
                            wuQVolMap = persistentProcess.exchangeElementWise(
                                sim, wuInputBytes, 0L, debugLog);
                            if (wuQVolMap == null) {
                                sim.println("[ECM-EW] WARN: pre-warm-up persistent stepId mismatch"
                                    + " — step 1 will use stale injection file values.");
                            }
                        } catch (IOException e) {
                            sim.println("[ECM-EW] WARN: pre-warm-up persistent exchange failed: "
                                + e.getMessage() + " — falling back to file-based.");
                            persistentProcess.close();
                            persistentProcess = null;
                        }
                    }
                    if (wuQVolMap == null && persistentProcess == null) {
                        try {
                            EcmBinaryIO.writeBytes(ECM_IN_PATH, wuInputBytes);
                            int wuExit = runProcess(sim, debugLog);
                            if (wuExit != 0) {
                                sim.println("[ECM-EW] WARN: pre-warm-up ECM exited " + wuExit
                                    + " — step 1 will use stale injection file values.");
                            } else if (!waitForFile(ECM_OUT_PATH, ECM_TIMEOUT_S)) {
                                sim.println("[ECM-EW] WARN: pre-warm-up ecm_out.bin timeout"
                                    + " — step 1 will use stale injection file values.");
                            } else {
                                wuQVolMap = EcmBinaryIO.readElementWiseOutput(ECM_OUT_PATH, 0L);
                                if (wuQVolMap == null) {
                                    sim.println("[ECM-EW] WARN: pre-warm-up output stepId mismatch"
                                        + " — step 1 will use stale injection file values.");
                                }
                            }
                        } catch (IOException e) {
                            sim.println("[ECM-EW] WARN: pre-warm-up file exchange failed: "
                                + e.getMessage() + " — step 1 will use stale injection file values.");
                        }
                    }
                    if (wuQVolMap != null) {
                        double[] wuQVolNew = new double[n];
                        double wuTotalW = 0.0;
                        double[] wuVols = cellMapper.volumes();
                        double wuFallbackV = (n > 0) ? JELLY_ROLL_VOLUME_M3 / n : 0.0;
                        int wuMatched = 0;
                        for (Map.Entry<Integer, Double> entry : wuQVolMap.entrySet()) {
                            int cid = entry.getKey();
                            if (cid >= 0 && cid < n) {
                                wuQVolNew[cid] = entry.getValue();
                                double vi = (wuVols != null) ? wuVols[cid] : wuFallbackV;
                                wuTotalW += wuQVolNew[cid] * vi;
                                wuMatched++;
                            }
                        }
                        sim.println(String.format(
                            "[ECM-EW] Pre-warm-up: %d/%d cells matched. Q_total=%.6e W",
                            wuMatched, n, wuTotalW));
                        try {
                            applyElementWiseHeatCsv(sim, cellMapper, wuQVolNew, qInjectionTable);
                            qVolPrev = wuQVolNew;
                            sim.println("[ECM-EW] Pre-warm-up complete: FileTable seeded with"
                                + " IC-consistent qVol. Jump at t=deltaT eliminated.");
                        } catch (IOException e) {
                            sim.println("[ECM-EW] WARN: pre-warm-up injection failed: "
                                + e.getMessage()
                                + " — step 1 will use stale injection file values.");
                        }
                    }
                }
            } else {
                sim.println("[ECM-EW] WARN: pre-warm-up skipped — IC T not available from tReport.");
            }
        }

        long stepId = 0L;
        double accumulatedTime = INITIAL_TIME_S;
        double physicalTimeFromStar = tryGetPhysicalTimeFromStar(sim);
        if (Double.isFinite(physicalTimeFromStar) && physicalTimeFromStar >= 0.0) {
            accumulatedTime = physicalTimeFromStar;
        }

        for (int step = 0; step < N_STEPS; step++) {

            // 1. Advance solver one timestep
            iter.step(1);
            stepId++;

            // 2. Collect per-cell temperatures
            double[] temps;
            try {
                temps = cellMapper.getTemperatures(sim);
            } catch (Exception e) {
                sim.println("[ECM-EW] FATAL: T extraction failed at step " + step + ": " + e.getMessage());
                sim.println("[ECM-EW] Aborting elementWise coupling loop.");
                sim.println("[ECM-EW]   If using xyzTableInMemory: verify table '" + T_TABLE_NAME + "' exists.");
                sim.println("[ECM-EW]   If using directFieldData: switch to xyzTableInMemory backend.");
                break;
            }

            // 3. Compute mean T for logging
            double tMean = 0.0;
            for (double t : temps) tMean += t;
            tMean /= n;

            // 4. Get deltaT and simulation time
            double deltaT = getDeltaT(sim);
            if (!Double.isFinite(deltaT) || deltaT <= 0.0) {
                deltaT = FALLBACK_DELTA_T_S;
            }

            physicalTimeFromStar = tryGetPhysicalTimeFromStar(sim);
            double simTime;
            if (Double.isFinite(physicalTimeFromStar) && physicalTimeFromStar >= 0.0) {
                simTime = physicalTimeFromStar;
                accumulatedTime = physicalTimeFromStar;
            } else {
                accumulatedTime += deltaT;
                simTime = accumulatedTime;
            }

            double currentAThisStep = currentProfile.currentAt(simTime);
            long _ewStepStart = System.nanoTime();

            sim.println(String.format(
                "[ECM-EW] step=%d stepId=%d t=%.6e s deltaT=%.6e s T_mean=%.4f K current=%.6e A",
                step, stepId, simTime, deltaT, tMean, currentAThisStep));

            if (HEAVY_LOG) {
                double tMin = Double.MAX_VALUE, tMax = -Double.MAX_VALUE, tSum = 0.0;
                for (double t : temps) { tMin = Math.min(tMin, t); tMax = Math.max(tMax, t); tSum += t; }
                sim.println(String.format(
                    "[ECM-EW-heavy] n=%d T_min=%.4f K T_max=%.4f K T_mean=%.4f K T_range=%.4f K",
                    temps.length, tMin, tMax, tSum / temps.length, tMax - tMin));
                // Per-region T stats for multi-region debugging
                int[] regIdx = cellMapper.regionIndices();
                if (regIdx != null) {
                    java.util.Map<Integer, double[]> rStats = new java.util.TreeMap<>();
                    for (int i = 0; i < temps.length; i++) {
                        int ri = regIdx[i];
                        double[] s = rStats.get(ri);
                        if (s == null) { s = new double[]{Double.MAX_VALUE, -Double.MAX_VALUE, 0.0, 0.0}; rStats.put(ri, s); }
                        s[0] = Math.min(s[0], temps[i]);
                        s[1] = Math.max(s[1], temps[i]);
                        s[2] += temps[i];
                        s[3] += 1.0;
                    }
                    for (java.util.Map.Entry<Integer, double[]> e : rStats.entrySet()) {
                        double[] s = e.getValue();
                        sim.println(String.format(
                            "[ECM-EW-heavy]   region[%d]: n=%.0f T_min=%.4f T_max=%.4f T_mean=%.4f K",
                            e.getKey(), s[3], s[0], s[1], s[2] / s[3]));
                    }
                }
            }

            // 5. Build elementWise ecm_in bytes (reused for pipe and/or file write)
            long _ewBeforeWrite = System.nanoTime();
            byte[] ewInputBytes;
            try {
                ewInputBytes = EcmBinaryIO.buildElementWiseInputBytes(
                    stepId, cellMapper.cellIds(), temps, simTime, deltaT, currentAThisStep);
            } catch (IOException e) {
                sim.println("[ECM-EW] ERROR building ecm_in bytes: " + e.getMessage());
                writeStepCsvFallback(sim, step, cellMapper, temps, qVolPrev);
                continue;
            }

            // 6. Call ECM backend: persistent pipe first, file-based fallback
            Map<Integer, Double> qVolMap = null;

            if (persistentProcess != null) {
                try {
                    qVolMap = persistentProcess.exchangeElementWise(sim, ewInputBytes, stepId, debugLog);
                    if (qVolMap == null) {
                        sim.println("[ECM-EW] WARN: persistent stepId mismatch. Keeping previous qVol.");
                        writeStepCsvFallback(sim, step, cellMapper, temps, qVolPrev);
                        continue;
                    }
                } catch (IOException e) {
                    sim.println("[ECM-EW] WARN: persistent exchange failed: " + e.getMessage()
                        + ". Falling back to file-based.");
                    persistentProcess.close();
                    persistentProcess = null;
                }
            }

            if (qVolMap == null) {
                // file-based exchange (when persistent unavailable or not configured)
                long _ewBeforePython = System.nanoTime();
                try {
                    EcmBinaryIO.writeBytes(ECM_IN_PATH, ewInputBytes);
                    if (HEAVY_LOG) {
                        sim.println(String.format("[ECM-EW-heavy] ecm_in.bin: %d bytes  write=%d ms",
                            ECM_IN_PATH.length(), (System.nanoTime() - _ewBeforeWrite) / 1_000_000L));
                    }
                } catch (IOException e) {
                    sim.println("[ECM-EW] ERROR writing ecm_in.bin: " + e.getMessage());
                    writeStepCsvFallback(sim, step, cellMapper, temps, qVolPrev);
                    continue;
                }

                try {
                    Files.deleteIfExists(ECM_OUT_PATH.toPath());
                } catch (IOException ignored) {}

                int exitCode = runProcess(sim, debugLog);
                if (exitCode != 0) {
                    sim.println("[ECM-EW] WARN: ECM exited with code " + exitCode + ". Keeping previous qVol.");
                    writeStepCsvFallback(sim, step, cellMapper, temps, qVolPrev);
                    continue;
                }

                if (!waitForFile(ECM_OUT_PATH, ECM_TIMEOUT_S)) {
                    sim.println("[ECM-EW] WARN: ecm_out.bin not found within timeout. Keeping previous qVol.");
                    writeStepCsvFallback(sim, step, cellMapper, temps, qVolPrev);
                    continue;
                }

                long _ewBeforeRead = System.nanoTime();
                try {
                    qVolMap = EcmBinaryIO.readElementWiseOutput(ECM_OUT_PATH, stepId);
                } catch (IOException e) {
                    sim.println("[ECM-EW] ERROR reading ecm_out.bin: " + e.getMessage());
                    writeStepCsvFallback(sim, step, cellMapper, temps, qVolPrev);
                    continue;
                }
                if (HEAVY_LOG) {
                    long _pythonMs = (_ewBeforeRead - _ewBeforePython) / 1_000_000L;
                    long _readMs   = (System.nanoTime() - _ewBeforeRead) / 1_000_000L;
                    sim.println(String.format(
                        "[ECM-EW-timing] write=%d ms  python=%d ms  read=%d ms",
                        (_ewBeforePython - _ewBeforeWrite) / 1_000_000L, _pythonMs, _readMs));
                }

                if (qVolMap == null) {
                    sim.println("[ECM-EW] WARN: stepId mismatch in ECM output. Keeping previous qVol.");
                    writeStepCsvFallback(sim, step, cellMapper, temps, qVolPrev);
                    continue;
                }
            }

            // 7. Merge returned qVol into per-cell array
            double[] qVolNew = Arrays.copyOf(qVolPrev, n);
            int matched = 0;
            for (Map.Entry<Integer, Double> entry : qVolMap.entrySet()) {
                int cellId = entry.getKey();
                if (cellId >= 0 && cellId < n) {
                    qVolNew[cellId] = entry.getValue();
                    matched++;
                }
            }

            // qVolNew[i] is qVol [W/m³].  Compute actual total power W = Σ(qVol_i * V_i).
            double totalW = 0.0;
            {
                double[] vols = cellMapper.volumes();
                double fallback = (n > 0) ? JELLY_ROLL_VOLUME_M3 / n : 0.0;
                for (int i = 0; i < n; i++) {
                    double vi = (vols != null) ? vols[i] : fallback;
                    totalW += qVolNew[i] * vi;
                }
            }

            sim.println(String.format(
                "[ECM-EW] ECM returned %d/%d cell records. Q_total=%.6e W",
                matched, n, totalW));

            if (HEAVY_LOG) {
                double qMin = Double.MAX_VALUE, qMax = -Double.MAX_VALUE;
                for (double v : qVolNew) { qMin = Math.min(qMin, v); qMax = Math.max(qMax, v); }
                long _totalEwMs = (System.nanoTime() - _ewStepStart) / 1_000_000L;
                sim.println(String.format(
                    "[ECM-EW-heavy] qVol_min=%.4e W/m3  qVol_max=%.4e W/m3  matched=%d/%d  TOTAL_step=%d ms",
                    qMin, qMax, matched, n, _totalEwMs));
                // Per-region Q stats
                int[] regIdx = cellMapper.regionIndices();
                double[] vols = cellMapper.volumes();
                if (regIdx != null && vols != null) {
                    java.util.Map<Integer, double[]> rQ = new java.util.TreeMap<>();
                    for (int i = 0; i < qVolNew.length; i++) {
                        int ri = regIdx[i];
                        double[] s = rQ.get(ri);
                        if (s == null) { s = new double[]{Double.MAX_VALUE, -Double.MAX_VALUE, 0.0, 0.0, 0.0}; rQ.put(ri, s); }
                        s[0] = Math.min(s[0], qVolNew[i]); // qVol min
                        s[1] = Math.max(s[1], qVolNew[i]); // qVol max
                        s[2] += qVolNew[i] * vols[i];       // Q_total [W]
                        s[3] += vols[i];                     // volume sum
                        s[4] += 1.0;                         // cell count
                    }
                    for (java.util.Map.Entry<Integer, double[]> e : rQ.entrySet()) {
                        double[] s = e.getValue();
                        sim.println(String.format(
                            "[ECM-EW-heavy]   region[%d]: n=%.0f Q=%.4f W  vol=%.6e m3  qVol=[%.4e .. %.4e] W/m3",
                            e.getKey(), s[4], s[2], s[3], s[0], s[1]));
                    }
                }
            }

            // 8. Write step CSV for visualisation
            try {
                writeStepCsv(CELL_STEP_CSV_FILE, step, cellMapper, temps, qVolNew);
            } catch (IOException e) {
                sim.println("[ECM-EW] WARN: could not write step CSV: " + e.getMessage());
            }

            // 9. Apply heat: dispatch based on INJECTION_MODE.
            if ("csvReload".equalsIgnoreCase(INJECTION_MODE) && qInjectionTable != null) {
                try {
                    applyElementWiseHeatCsv(sim, cellMapper, qVolNew, qInjectionTable);
                } catch (IOException e) {
                    sim.println("[ECM-EW] FATAL: csvReload injection failed at step " + step
                        + ": " + e.getMessage());
                    sim.println("[ECM-EW] Aborting coupling loop — heat source is in unknown state.");
                    return;
                }
            } else {
                applyElementWiseHeat(sim, qVolNew);
            }

            // DIAG-3: log STAR energy-source field function reports (once per step)
            logEnergySourceReports(sim, energySourceReports, simTime);

            qVolPrev = qVolNew;

            // Write dedicated time-history CSVs (one row per accepted coupling step).
            // tempLog.csv source: STAR VolumeAverageReport (authoritative jellyRoll monitor).
            // appliedTotalHeatLog.csv source: sum of per-cell W applied to STAR energy equation.
            if (tempLogCsv != null) {
                double tVolAvg = tReport.getValue();
                tempLogCsv.println(String.format("%.9e,%.6f", simTime, tVolAvg - 273.15));
                tempLogCsv.flush();
            }
            if (appliedHeatLogCsv != null) {
                appliedHeatLogCsv.println(String.format("%.9e,%.9e", simTime, totalW));
                appliedHeatLogCsv.flush();
            }

            if (debugLog != null) {
                debugLog.println(String.format(
                    "step=%d stepId=%d t=%.6e T_mean=%.4f Q_total=%.6e matched=%d/%d",
                    step, stepId, simTime, tMean, totalW, matched, n));
                debugLog.flush();
            }
        }

        sim.println("[ECM-EW] Coupling loop complete.");
        if (debugLog != null) {
            debugLog.println("=== LOOP COMPLETE ===");
            debugLog.close();
        }
        if (tempLogCsv != null) {
            tempLogCsv.close();
        }
        if (appliedHeatLogCsv != null) {
            appliedHeatLogCsv.close();
        }
    }

    // =========================================================================
    // LUMPED MULTI-REGION COUPLING (N>1 regions, csvReload injection)
    // =========================================================================

    /**
     * Lumped multi-region coupling: one volume-average T per region → ECM →
     * uniform Q per region, injected via CSV FileTable.
     *
     * <p>Sends the standard elementWise binary frame, but with all cells in
     * region k carrying T_avg[k] (the region volume-average temperature).
     * Python computes per-cell qVol using the same zone mapping as elementWise;
     * we then aggregate to a per-region total Q[k] and write
     * {@code qVol[i] = Q[k] / V_region[k]} — uniform within each region —
     * into the injection CSV.  This gives one ECM state per physical cell while
     * keeping the spatial heat distribution flat within each region.
     *
     * <p>Called from {@link #execute} when {@code COUPLING_MODE=="lumped"} and
     * {@code regions.size() > 1}.
     */
    private void executeLumpedMultiRegion(Simulation sim, List<Region> regions) {
        int nR = regions.size();
        resolveAndSetProjectRoot(sim);
        nRegionsForEnv = nR;

        sim.println("[ECM-LMR] Starting lumped multi-region coupling  nRegions=" + nR);
        sim.println("[ECM-LMR] T_TABLE_NAME: " + T_TABLE_NAME);

        // --- CellMapper (same as elementWise) ---
        CellMapper cellMapper;
        try {
            cellMapper = buildMergedCellMapper(sim, regions);
        } catch (Exception e) {
            sim.println("[ECM-LMR] ERROR creating CellMapper: " + e.getMessage());
            return;
        }
        int n = cellMapper.nCells();
        sim.println(String.format("[ECM-LMR] CellMapper ready: %d cells across %d region(s).", n, nR));

        // write cell map CSV once (visualisation + mapping regen input)
        try {
            writeCellMapCsv(CELL_MAP_CSV_FILE, cellMapper);
            sim.println("[ECM-LMR] Cell map written: " + CELL_MAP_CSV_FILE.getAbsolutePath());
        } catch (IOException e) {
            sim.println("[ECM-LMR] WARN: could not write cell map CSV: " + e.getMessage());
        }

        // per-region geometry CSV (for ecm_mapping regen with correct cylinder axes)
        try {
            writeRegionGeometryCsv(sim, REGION_GEOMETRY_CSV_FILE, regions, cellMapper);
            sim.println("[ECM-LMR] Region geometry written: " + REGION_GEOMETRY_CSV_FILE.getAbsolutePath());
        } catch (Exception e) {
            sim.println("[ECM-LMR] WARN: could not write region geometry CSV: " + e.getMessage());
        }

        // fresh-start detection
        double _initPhysTime = tryGetPhysicalTimeFromStar(sim);
        boolean freshStart = !Double.isFinite(_initPhysTime) || _initPhysTime < 1e-9;
        sim.println("[ECM-LMR] Run mode: " + (freshStart ? "FRESH (t=0)"
            : "CONTINUATION (t=" + String.format("%.3f", _initPhysTime) + " s)"));

        // Always regenerate from the current STAR mesh on macro startup.  Do not
        // reuse old mapping files after any mesh/table change.
        if (ECM_MAPPING_CSV_FILE != null) {
            sim.println("[ECM-LMR] Regenerating ecm_mapping.csv from current mesh every startup.");
            try {
                Files.deleteIfExists(ECM_MAPPING_CSV_FILE.toPath());
                Files.deleteIfExists(ZONE_WEIGHTS_CSV_FILE.toPath());
                regenEcmMapping(sim);
            } catch (Exception e) {
                sim.println("[ECM-LMR] FATAL: " + e.getMessage());
                return;
            }
        }

        // ecm_state.json: reset on fresh start
        if (freshStart) {
            try {
                if (Files.deleteIfExists(ECM_STATE_PATH.toPath())) {
                    sim.println("[ECM-LMR] Fresh run: deleted ecm_state.json — ECM starts at SOC=1.");
                }
            } catch (IOException e) {
                sim.println("[ECM-LMR] WARN: could not delete ecm_state.json: " + e.getMessage());
            }
        } else {
            sim.println("[ECM-LMR] Continuation: preserving ecm_state.json.");
        }

        // --- per-region VolumeAverageReport (one per physical cell) ---
        VolumeAverageReport[] tReports = new VolumeAverageReport[nR];
        for (int k = 0; k < nR; k++) {
            String reportName = "ECM_T_avg_r" + k;
            VolumeAverageReport rpt;
            try {
                rpt = (VolumeAverageReport) sim.getReportManager().getReport(reportName);
            } catch (Exception ignored) {
                rpt = sim.getReportManager().createReport(VolumeAverageReport.class);
                rpt.setPresentationName(reportName);
                rpt.setFieldFunction(sim.getFieldFunctionManager().getFunction("Temperature"));
            }
            rpt.getParts().setObjects(Collections.singletonList(regions.get(k)));
            tReports[k] = rpt;
            sim.println(String.format("[ECM-LMR] T report r%d: '%s' → '%s'",
                k, reportName, regions.get(k).getPresentationName()));
        }

        // --- table injection setup (same as elementWise) ---
        star.common.FileTable qInjectionTable = getOrCreateQInjectionTable(sim);
        if (qInjectionTable == null) {
            sim.println("[ECM-LMR] FATAL: could not create injection FileTable '" + Q_TABLE_NAME + "'. Aborting.");
            return;
        }
        for (Region jr : regions) {
            autoConfigureJellyRollEnergySource(sim, jr, qInjectionTable);
        }
        diagProfileMethodType(sim, regions);

        // --- logs ---
        PrintWriter debugLog = null;
        try {
            debugLog = new PrintWriter(new FileWriter(ECM_DEBUG_LOG_PATH, true));
            debugLog.println("=== ECM-LMR DEBUG LOG  " + new java.util.Date() + " ===");
            debugLog.println("COUPLING_MODE: lumped/multiRegion  nR=" + nR + "  nCells=" + n);
            debugLog.flush();
        } catch (IOException e) {
            sim.println("[ECM-LMR] WARN: could not open debug log: " + e.getMessage());
        }
        PrintWriter tempLogCsv = null;
        try {
            File parent = TEMP_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            tempLogCsv = new PrintWriter(new FileWriter(TEMP_LOG_FILE, !freshStart));
            if (freshStart) { tempLogCsv.println("time_s,temp_c"); }
            tempLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM-LMR] WARN: could not open tempLog.csv: " + e.getMessage());
        }
        PrintWriter appliedHeatLogCsv = null;
        try {
            File parent = APPLIED_HEAT_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            appliedHeatLogCsv = new PrintWriter(new FileWriter(APPLIED_HEAT_LOG_FILE, !freshStart));
            if (freshStart) { appliedHeatLogCsv.println("time_s,applied_total_heat_w"); }
            appliedHeatLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM-LMR] WARN: could not open appliedTotalHeatLog.csv: " + e.getMessage());
        }

        // --- pre-compute stable per-region volumes ---
        int[] regIdx = cellMapper.regionIndices();
        double[] vols = cellMapper.volumes();
        double fallbackVCell = JELLY_ROLL_VOLUME_M3 / Math.max(n, 1);
        double[] regionVolume = new double[nR];
        int[] regionCellCount = new int[nR];
        for (int i = 0; i < n; i++) {
            int r = (regIdx != null && regIdx[i] >= 0 && regIdx[i] < nR) ? regIdx[i] : 0;
            regionVolume[r] += (vols != null) ? vols[i] : fallbackVCell;
            regionCellCount[r]++;
        }
        for (int k = 0; k < nR; k++) {
            if (regionVolume[k] <= 0.0) {
                sim.println(String.format(
                    "[ECM-LMR] WARN: region[%d] has zero computed volume — using fallback %.4e m3",
                    k, JELLY_ROLL_VOLUME_M3 / nR));
                regionVolume[k] = JELLY_ROLL_VOLUME_M3 / nR;
            }
            sim.println(String.format("[ECM-LMR] region[%d]: %d cells  volume=%.6e m3",
                k, regionCellCount[k], regionVolume[k]));
        }

        if (regIdx == null) {
            sim.println("[ECM-LMR] WARN: regionIdx not available — all cells assigned to region 0. "
                + "Per-region T will be incorrect. Check ecm_cell_map.csv has regionIdx column.");
        }

        // --- coupling loop ---
        SimulationIterator iter = sim.getSimulationIterator();
        CurrentProfile currentProfile = CurrentProfile.load(sim, CURRENT_PROFILE_FILE, CURRENT_A);
        PersistentEcmProcess persistentProcess = null;
        if (USE_PERSISTENT_PYTHON) {
            persistentProcess = PersistentEcmProcess.start(sim, debugLog);
        }

        double[] qWPrev    = new double[nR];  // per-region relaxed Q [W] from previous step
        double[] qVolPrev  = new double[n];   // per-cell fallback qVol [W/m³]
        long stepId = 0L;
        double accumulatedTime = INITIAL_TIME_S;
        double physicalTimeFromStar = tryGetPhysicalTimeFromStar(sim);
        if (Double.isFinite(physicalTimeFromStar) && physicalTimeFromStar >= 0.0) {
            accumulatedTime = physicalTimeFromStar;
        }

        // --- Pre-warm-up ECM call (fresh starts only) ---
        // WHY: The coupling loop runs iter.step(1) BEFORE calling the ECM, so the
        // FileTable that STAR uses during the first solver step always comes from
        // whatever was on disk at startup (ecm_qvol_injection.csv).  That file is
        // typically produced by a prior OpenFOAM run at a different initial
        // temperature than the STAR-CCM+ case.  The temperature mismatch causes a
        // sharp ~2× jump in applied ECM heat between t=0.2 and t=0.4:
        //   t=0.2 step: uses stale pre-computed qVol from OF IC temperature
        //   t=0.4 step: uses first real ECM call at STAR IC temperature → jump
        // Fix: call the ECM once here with STAR's initial temperatures and
        // deltaT=0 (so ECM state/SoC is not advanced), then write the result into
        // the FileTable so step 1 starts from the correct qVol.
        // Continuation runs are skipped — their FileTable already holds correct
        // values from the previous run's last step.
        if (freshStart) {
            sim.println("[ECM-LMR] Pre-warm-up: calling ECM at STAR initial temperatures "
                + "(stepId=0, deltaT=0 — no SoC advancement).");
            double[] tAvgInit = new double[nR];
            for (int k = 0; k < nR; k++) tAvgInit[k] = tReports[k].getValue();
            double[] tempsInit = new double[n];
            for (int i = 0; i < n; i++) {
                int r = (regIdx != null && regIdx[i] >= 0 && regIdx[i] < nR) ? regIdx[i] : 0;
                tempsInit[i] = tAvgInit[r];
            }
            StringBuilder wuTLog = new StringBuilder();
            for (int k = 0; k < nR; k++) {
                wuTLog.append(String.format(" T_r%d=%.4f K(%.2f C)", k, tAvgInit[k], tAvgInit[k] - 273.15));
            }
            sim.println("[ECM-LMR] Pre-warm-up initial temperatures:" + wuTLog);

            double currentAtT0 = currentProfile.currentAt(0.0);
            byte[] wuInputBytes = null;
            try {
                // stepId=0 is the probe/warm-up slot; actual loop starts at stepId=1.
                // deltaT=0 ensures the ECM does not consume any charge capacity.
                wuInputBytes = EcmBinaryIO.buildElementWiseInputBytes(
                    0L, cellMapper.cellIds(), tempsInit, 0.0, 0.0, currentAtT0);
            } catch (IOException e) {
                sim.println("[ECM-LMR] WARN: pre-warm-up input build failed: " + e.getMessage()
                    + " — step 1 will use stale injection file values.");
            }

            if (wuInputBytes != null) {
                Map<Integer, Double> wuQVolMap = null;
                if (persistentProcess != null) {
                    try {
                        wuQVolMap = persistentProcess.exchangeElementWise(
                            sim, wuInputBytes, 0L, debugLog);
                        if (wuQVolMap == null) {
                            sim.println("[ECM-LMR] WARN: pre-warm-up persistent stepId mismatch"
                                + " — step 1 will use stale injection file values.");
                        }
                    } catch (IOException e) {
                        sim.println("[ECM-LMR] WARN: pre-warm-up persistent exchange failed: "
                            + e.getMessage() + " — falling back to file-based.");
                        persistentProcess.close();
                        persistentProcess = null;
                    }
                }
                if (wuQVolMap == null && persistentProcess == null) {
                    try {
                        Files.deleteIfExists(ECM_OUT_PATH.toPath());
                        EcmBinaryIO.writeBytes(ECM_IN_PATH, wuInputBytes);
                        int wuExit = runProcess(sim, debugLog);
                        if (wuExit != 0) {
                            sim.println("[ECM-LMR] WARN: pre-warm-up ECM exited " + wuExit
                                + " — step 1 will use stale injection file values.");
                        } else if (!waitForFile(ECM_OUT_PATH, ECM_TIMEOUT_S)) {
                            sim.println("[ECM-LMR] WARN: pre-warm-up ecm_out.bin timeout"
                                + " — step 1 will use stale injection file values.");
                        } else {
                            wuQVolMap = EcmBinaryIO.readElementWiseOutput(ECM_OUT_PATH, 0L);
                            if (wuQVolMap == null) {
                                sim.println("[ECM-LMR] WARN: pre-warm-up output stepId mismatch"
                                    + " — step 1 will use stale injection file values.");
                            }
                        }
                    } catch (IOException e) {
                        sim.println("[ECM-LMR] WARN: pre-warm-up file exchange failed: "
                            + e.getMessage() + " — step 1 will use stale injection file values.");
                    }
                }

                if (wuQVolMap != null) {
                    // Merge → aggregate → uniform per region → inject FileTable
                    double[] wuQVolNew = Arrays.copyOf(qVolPrev, n);
                    for (Map.Entry<Integer, Double> e : wuQVolMap.entrySet()) {
                        int cid = e.getKey();
                        if (cid >= 0 && cid < n) wuQVolNew[cid] = e.getValue();
                    }
                    double[] wuQW = new double[nR];
                    for (int i = 0; i < n; i++) {
                        int r = (regIdx != null && regIdx[i] >= 0 && regIdx[i] < nR) ? regIdx[i] : 0;
                        double vi = (vols != null) ? vols[i] : fallbackVCell;
                        wuQW[r] += wuQVolNew[i] * vi;
                    }
                    double[] wuQVolUniform = new double[n];
                    double wuTotalW = 0.0;
                    for (int i = 0; i < n; i++) {
                        int r = (regIdx != null && regIdx[i] >= 0 && regIdx[i] < nR) ? regIdx[i] : 0;
                        wuQVolUniform[i] = wuQW[r] / regionVolume[r];
                        double vi = (vols != null) ? vols[i] : fallbackVCell;
                        wuTotalW += wuQVolUniform[i] * vi;
                    }
                    StringBuilder wuQLog = new StringBuilder();
                    for (int k = 0; k < nR; k++) {
                        wuQLog.append(String.format("  Q_r%d=%.4f W (%.3e W/m3)",
                            k, wuQW[k], wuQW[k] / regionVolume[k]));
                    }
                    sim.println(String.format(
                        "[ECM-LMR] Pre-warm-up Q_total=%.6e W%s", wuTotalW, wuQLog));
                    try {
                        applyElementWiseHeatCsv(sim, cellMapper, wuQVolUniform, qInjectionTable);
                        // Seed qWPrev/qVolPrev so step 1's under-relaxation starts
                        // from the warm-up value rather than zero.
                        qWPrev   = wuQW;
                        qVolPrev = wuQVolUniform;
                        sim.println("[ECM-LMR] Pre-warm-up complete: FileTable seeded with"
                            + " IC-consistent qVol. Jump at t=deltaT eliminated.");
                    } catch (IOException e) {
                        sim.println("[ECM-LMR] WARN: pre-warm-up injection failed: "
                            + e.getMessage()
                            + " — step 1 will use stale injection file values.");
                    }
                }
            }
        }

        for (int step = 0; step < N_STEPS; step++) {

            // 1. Advance solver one timestep
            iter.step(1);
            stepId++;

            // 2. Per-region volume-average temperature
            double[] tAvg = new double[nR];
            for (int k = 0; k < nR; k++) tAvg[k] = tReports[k].getValue();

            // 3. Build temps[] with uniform T per region (lumped assumption)
            double[] temps = new double[n];
            for (int i = 0; i < n; i++) {
                int r = (regIdx != null && regIdx[i] >= 0 && regIdx[i] < nR) ? regIdx[i] : 0;
                temps[i] = tAvg[r];
            }

            // 4. Time and current
            double deltaT = getDeltaT(sim);
            if (!Double.isFinite(deltaT) || deltaT <= 0.0) deltaT = FALLBACK_DELTA_T_S;
            physicalTimeFromStar = tryGetPhysicalTimeFromStar(sim);
            double simTime;
            if (Double.isFinite(physicalTimeFromStar) && physicalTimeFromStar >= 0.0) {
                simTime = physicalTimeFromStar;
                accumulatedTime = physicalTimeFromStar;
            } else {
                accumulatedTime += deltaT;
                simTime = accumulatedTime;
            }
            double currentAThisStep = currentProfile.currentAt(simTime);

            StringBuilder tLog = new StringBuilder();
            for (int k = 0; k < nR; k++) {
                tLog.append(String.format(" T_r%d=%.4f K(%.2f C)", k, tAvg[k], tAvg[k] - 273.15));
            }
            sim.println(String.format(
                "[ECM-LMR] step=%d stepId=%d t=%.6e s deltaT=%.6e s%s current=%.6e A",
                step, stepId, simTime, deltaT, tLog, currentAThisStep));

            // 5. Build elementWise binary (N cells, uniform T per region)
            byte[] ewInputBytes;
            try {
                ewInputBytes = EcmBinaryIO.buildElementWiseInputBytes(
                    stepId, cellMapper.cellIds(), temps, simTime, deltaT, currentAThisStep);
            } catch (IOException e) {
                sim.println("[ECM-LMR] ERROR building input bytes: " + e.getMessage()
                    + " — keeping previous.");
                continue;
            }

            // 6. Exchange with ECM (persistent pipe first, file-based fallback)
            Map<Integer, Double> qVolMap = null;
            if (persistentProcess != null) {
                try {
                    qVolMap = persistentProcess.exchangeElementWise(sim, ewInputBytes, stepId, debugLog);
                    if (qVolMap == null) {
                        sim.println("[ECM-LMR] WARN: persistent stepId mismatch — keeping previous.");
                        continue;
                    }
                } catch (IOException e) {
                    sim.println("[ECM-LMR] WARN: persistent exchange failed: " + e.getMessage()
                        + " — falling back to file-based.");
                    persistentProcess.close();
                    persistentProcess = null;
                }
            }
            if (qVolMap == null) {
                try { Files.deleteIfExists(ECM_OUT_PATH.toPath()); } catch (IOException ignored) {}
                try {
                    EcmBinaryIO.writeBytes(ECM_IN_PATH, ewInputBytes);
                } catch (IOException e) {
                    sim.println("[ECM-LMR] ERROR writing ecm_in.bin: " + e.getMessage()
                        + " — keeping previous.");
                    continue;
                }
                int exitCode = runProcess(sim, debugLog);
                if (exitCode != 0) {
                    sim.println("[ECM-LMR] WARN: ECM exited " + exitCode + " — keeping previous.");
                    continue;
                }
                if (!waitForFile(ECM_OUT_PATH, ECM_TIMEOUT_S)) {
                    sim.println("[ECM-LMR] WARN: ecm_out.bin timeout — keeping previous.");
                    continue;
                }
                try {
                    qVolMap = EcmBinaryIO.readElementWiseOutput(ECM_OUT_PATH, stepId);
                } catch (IOException e) {
                    sim.println("[ECM-LMR] ERROR reading ecm_out.bin: " + e.getMessage()
                        + " — keeping previous.");
                    continue;
                }
                if (qVolMap == null) {
                    sim.println("[ECM-LMR] WARN: stepId mismatch in ecm_out — keeping previous.");
                    continue;
                }
            }

            // 7. Merge returned qVol into per-cell array
            double[] qVolNew = Arrays.copyOf(qVolPrev, n);
            for (Map.Entry<Integer, Double> entry : qVolMap.entrySet()) {
                int cellId = entry.getKey();
                if (cellId >= 0 && cellId < n) qVolNew[cellId] = entry.getValue();
            }

            // 8. Aggregate: per-region Q [W] = Σ(qVol[i] * V[i]) for cells in region k
            double[] qW = new double[nR];
            for (int i = 0; i < n; i++) {
                int r = (regIdx != null && regIdx[i] >= 0 && regIdx[i] < nR) ? regIdx[i] : 0;
                double vi = (vols != null) ? vols[i] : fallbackVCell;
                qW[r] += qVolNew[i] * vi;
            }

            // 9. Under-relaxation per region
            double[] qWRelaxed = new double[nR];
            for (int k = 0; k < nR; k++) {
                qWRelaxed[k] = ALPHA * qW[k] + (1.0 - ALPHA) * qWPrev[k];
                qWPrev[k] = qWRelaxed[k];
            }

            // 10. Build uniform qVol per region → per-cell injection array
            double[] qVolUniform = new double[n];
            double totalW = 0.0;
            for (int i = 0; i < n; i++) {
                int r = (regIdx != null && regIdx[i] >= 0 && regIdx[i] < nR) ? regIdx[i] : 0;
                qVolUniform[i] = qWRelaxed[r] / regionVolume[r];
                double vi = (vols != null) ? vols[i] : fallbackVCell;
                totalW += qVolUniform[i] * vi;
            }

            StringBuilder qLog = new StringBuilder();
            for (int k = 0; k < nR; k++) {
                qLog.append(String.format("  Q_r%d=%.4f W (%.3e W/m3)", k, qWRelaxed[k],
                    qWRelaxed[k] / regionVolume[k]));
            }
            sim.println(String.format("[ECM-LMR] Q_total=%.6e W%s", totalW, qLog));

            // 11. Inject uniform heat per region via FileTable
            try {
                applyElementWiseHeatCsv(sim, cellMapper, qVolUniform, qInjectionTable);
            } catch (IOException e) {
                sim.println("[ECM-LMR] FATAL: table injection failed: " + e.getMessage()
                    + " — aborting coupling loop.");
                break;
            }

            qVolPrev = qVolUniform;

            // 12. Write time-history CSVs
            if (tempLogCsv != null) {
                // volume-weighted average T across all regions
                double tAvgAll = 0.0, vTotal = 0.0;
                for (int k = 0; k < nR; k++) {
                    tAvgAll += tAvg[k] * regionVolume[k];
                    vTotal  += regionVolume[k];
                }
                tAvgAll /= (vTotal > 0.0 ? vTotal : 1.0);
                tempLogCsv.println(String.format("%.9e,%.6f", simTime, tAvgAll - 273.15));
                tempLogCsv.flush();
            }
            if (appliedHeatLogCsv != null) {
                appliedHeatLogCsv.println(String.format("%.9e,%.9e", simTime, totalW));
                appliedHeatLogCsv.flush();
            }
            if (debugLog != null) {
                debugLog.println(String.format(
                    "step=%d stepId=%d t=%.6e Q_total=%.6e", step, stepId, simTime, totalW));
                debugLog.flush();
            }
        }

        sim.println("[ECM-LMR] Coupling loop complete.");
        if (persistentProcess != null) persistentProcess.close();
        if (debugLog != null) { debugLog.println("=== LOOP COMPLETE ==="); debugLog.close(); }
        if (tempLogCsv != null) tempLogCsv.close();
        if (appliedHeatLogCsv != null) appliedHeatLogCsv.close();
    }

    /**
     * Apply per-cell heat contributions returned by the ECM.
     *
     * Record convention: each record value is Q_cell [W] — the power contribution
     * of one cell.  Sum over all cells = total Q_GEN [W].  This is identical to
     * the lumped mode convention (N=1, value = Q_GEN [W]).
     *
     * Phase 1: sum all per-cell W values → push total W to ecmQdot_W global
     * parameter, same as lumped mode.  STAR applies it as total heat to the region.
     *
     * Phase 3 will replace the sum+parameter approach with per-cell field function.
     */
    private void applyElementWiseHeat(Simulation sim, double[] qVolPerCell) {
        // LEGACY globalParam path (not recommended — use csvReload instead).
        // qVolPerCell[i] is qVol [W/m³].  Total power is not meaningful without
        // cell volumes here, so sum is a rough estimate using the zone constant.
        sim.println("[ECM-EW] WARN: globalParam injection mode is deprecated. "
            + "Use INJECTION_MODE=csvReload for correct distributed heat injection.");
        double totalW = 0.0;
        double vCell = JELLY_ROLL_VOLUME_M3 / Math.max(qVolPerCell.length, 1);
        for (double v : qVolPerCell) totalW += v * vCell;

        ScalarGlobalParameter qParam = getOrCreateQParam(sim);
        qParam.getQuantity().setValue(totalW);
        sim.println(String.format("[ECM-EW] Applied approx Q_GEN=%.6e W to ecmQdot_W (globalParam).", totalW));
    }

    // =========================================================================
    // Per-cell CSV injection (csvReload mode)
    // =========================================================================

    /**
     * Per-cell distributed heat injection via CSV reload.
     *
     * Writes the (X,Y,Z,qVol_W_m3) injection CSV atomically with the qVol [W/m³]
     * values received directly from the Python ECM (uniform within each partition,
     * matching the OpenFOAM approach: Q_partition / V_partition per cell — no
     * per-cell volume division here, which would create hotspots at small mesh cells).
     *
     * @param qVolPerCell  per-cell qVol [W/m³] (one entry per CellMapper cell,
     *                     uniform for all cells within the same ECM partition)
     * @param fileTable    the STAR FileTable to reload after writing the CSV
     */
    private void applyElementWiseHeatCsv(Simulation sim, CellMapper cellMapper,
            double[] qVolPerCell,
            star.common.FileTable fileTable) throws IOException {

        long t0 = System.nanoTime();
        writeQVolInjectionCsv(Q_TABLE_CSV_FILE, cellMapper, qVolPerCell);
        long tWrite = System.nanoTime();

        fileTable.extract();
        long tExtract = System.nanoTime();

        // DIAG-2: read back qVol from the in-memory FileTable and compare vs written values
        diagQTableReadback(sim, fileTable, qVolPerCell);

        double writeMs   = (tWrite   - t0)     / 1_000_000.0;
        double extractMs = (tExtract - tWrite)  / 1_000_000.0;

        // Compute Q_total = Σ(qVol_i * V_i) and qVol range for logging.
        double[] vols = cellMapper.volumes();
        double fallback = (qVolPerCell.length > 0) ? JELLY_ROLL_VOLUME_M3 / qVolPerCell.length : 0.0;
        double totalW = 0.0, minQVol = Double.MAX_VALUE, maxQVol = -Double.MAX_VALUE;
        for (int i = 0; i < qVolPerCell.length; i++) {
            double vi = (vols != null) ? vols[i] : fallback;
            totalW += qVolPerCell[i] * vi;
            if (qVolPerCell[i] < minQVol) minQVol = qVolPerCell[i];
            if (qVolPerCell[i] > maxQVol) maxQVol = qVolPerCell[i];
        }
        sim.println(String.format(
            "[ECM-EW] csvReload: write=%.0f ms  extract=%.0f ms  "
            + "Q_total=%.4e W  qVol=[%.2e .. %.2e] W/m3",
            writeMs, extractMs, totalW,
            (minQVol == Double.MAX_VALUE  ? 0.0 : minQVol),
            (maxQVol == -Double.MAX_VALUE ? 0.0 : maxQVol)));
    }

    /**
     * Write per-cell qVol injection CSV: {@code x_m, y_m, z_m, qVol_W_m3}.
     *
     * Performs an atomic write (write to {@code .tmp}, then rename) so STAR never
     * reads a partially written file.
     *
     * @param path         destination file (e.g. ecm/ecm_qvol_injection.csv)
     * @param qVolPerCell  per-cell qVol [W/m³]; index = CellMapper array index.
     *                     Values are written directly — no per-cell volume division.
     *                     Each cell in a partition carries the same uniform W/m³ value
     *                     (= Q_partition / V_partition), eliminating hotspots at small cells.
     */
    private static void writeQVolInjectionCsv(File path, CellMapper cellMapper,
            double[] qVolPerCell) throws IOException {

        int      n   = cellMapper.nCells();
        double[] xs  = cellMapper.xCentroids();
        double[] ys  = cellMapper.yCentroids();
        double[] zs  = cellMapper.zCentroids();

        // Build full CSV in memory first (avoids many small writes; ~10 MB for 160k cells)
        // Coordinate columns must be named X,Y,Z for STAR's setTabularXyzMethod
        // auto-detection.  cellId/regionIdx are extra audit columns; STAR uses
        // the named qVol_W_m3 profile column for the source value.
        StringBuilder sb = new StringBuilder(n * 64 + 32);
        sb.append("X,Y,Z,qVol_W_m3,cellId,regionIdx\n");
        int[] ids = cellMapper.cellIds();
        int[] ri = cellMapper.regionIndices();
        for (int i = 0; i < n; i++) {
            sb.append(String.format("%.9e,%.9e,%.9e,%.6e,%d,%d\n",
                xs[i], ys[i], zs[i], qVolPerCell[i],
                ids != null ? ids[i] : i,
                ri != null ? ri[i] : 0));
        }

        byte[] bytes = sb.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
        File   tmp   = new File(path.getAbsolutePath() + ".tmp");
        if (path.getParentFile() != null) path.getParentFile().mkdirs();
        Files.write(tmp.toPath(), bytes);
        Files.move(tmp.toPath(), path.toPath(),
            StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }

    /**
     * Create or retrieve the FileTable used for per-cell qVol injection.
     *
     * If a table named {@link #Q_TABLE_NAME} already exists in the simulation it is
     * returned directly (its file path is updated to {@link #Q_TABLE_CSV_FILE}).
     * If not found, a new {@code FileTable} is created.  In both cases a single
     * initial {@code extract()} is performed so the table is populated before the
     * first coupling step writes real data.
     *
     * @return the FileTable, or {@code null} if creation failed (caller must fall back
     *         to globalParam mode)
     */
    private star.common.FileTable getOrCreateQInjectionTable(Simulation sim) {
        star.common.FileTable ft = null;

        // Try to retrieve an existing table first
        try {
            Table existing = sim.getTableManager().getTable(Q_TABLE_NAME);
            ft = (star.common.FileTable) existing;
            sim.println("[ECM-EW] Found existing injection FileTable: '" + Q_TABLE_NAME + "'");
        } catch (Exception ignored) {
            // Not found or wrong type — create new
        }

        if (ft == null) {
            try {
                ft = (star.common.FileTable) sim.getTableManager()
                        .createTable(star.common.FileTable.class);
                ft.setPresentationName(Q_TABLE_NAME);
                sim.println("[ECM-EW] Created new injection FileTable: '" + Q_TABLE_NAME + "'");
            } catch (Exception ex) {
                sim.println("[ECM-EW] ERROR: could not create FileTable '" + Q_TABLE_NAME
                    + "': " + ex.getMessage());
                sim.println("[ECM-EW]   csvReload unavailable — injection will fall back to globalParam.");
                return null;
            }
        }

        // Point to our injection CSV (auto-create a placeholder if file absent).
        // FileTable.setFilename() was removed in STAR-CCM+ 2602; use reflection to
        // support both old (setFilename) and new (setFileName) API names.
        // Use relative path so the .sim file remains portable across machines.
        try {
            String absPath = Q_TABLE_CSV_PATH;
            boolean set = false;
            for (String mn : new String[]{"setFileName", "setFilename"}) {
                try {
                    java.lang.reflect.Method m = ft.getClass().getMethod(mn, String.class);
                    m.invoke(ft, absPath);
                    sim.println("[ECM-EW] FileTable filename set via " + mn + "(): " + absPath);
                    set = true;
                    break;
                } catch (NoSuchMethodException ignored) {}
            }
            if (!set) {
                sim.println("[ECM-EW] WARN: no setFileName/setFilename method found on FileTable; "
                    + "table may reference wrong file. Please point it manually to: " + absPath);
            }
        } catch (Exception ex) {
            sim.println("[ECM-EW] WARN: setFileName reflection failed: " + ex.getMessage());
        }
        if (!Q_TABLE_CSV_FILE.exists()) {
            try {
                if (Q_TABLE_CSV_FILE.getParentFile() != null) Q_TABLE_CSV_FILE.getParentFile().mkdirs();
                Files.write(Q_TABLE_CSV_FILE.toPath(),
                    "X,Y,Z,qVol_W_m3,cellId,regionIdx\n0.0,0.0,0.0,0.0,0,0\n"
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8));
                sim.println("[ECM-EW] Created injection CSV placeholder: "
                    + Q_TABLE_CSV_FILE.getAbsolutePath());
            } catch (IOException ex) {
                sim.println("[ECM-EW] WARN: could not create injection CSV placeholder: "
                    + ex.getMessage());
            }
        }

        // Initial extract to verify setup
        try {
            ft.extract();
            sim.println("[ECM-EW] Injection FileTable '" + Q_TABLE_NAME + "' ready. File: "
                + Q_TABLE_CSV_FILE.getAbsolutePath());
        } catch (Exception ex) {
            sim.println("[ECM-EW] WARN: initial injection FileTable extract() failed: "
                + ex.getMessage());
            // Non-fatal: real data written at step 1 will succeed
        }

        return ft;
    }

    /**
     * Load the per-cell zone-weight CSV ({@code ecm_zone_weights.csv}) as a STAR-CCM+
     * FileTable and create one {@code UserFieldFunction} per ECM zone.
     *
     * <p>Each field function uses {@code interpolateTable()} to map the zone's weight
     * column onto the jelly-roll mesh by nearest-neighbour XYZ lookup:
     * <pre>
     *   interpolateTable("ECM_ZoneWeights_Table", "w_zone_k",
     *                    $$Position[0], $$Position[1], $$Position[2])
     * </pre>
     *
     * <p>After this method runs, the functions appear under
     * <b>Tools &rarr; Field Functions</b> in the STAR-CCM+ UI as
     * {@code ECM_Zone_0_Weight} … {@code ECM_Zone_N_Weight}.  Drop any of them onto a
     * scalar scene on the jellyRoll region to visualise the overlap-weight distribution
     * and verify the smooth zone-boundary blending.
     *
     * <p>No-op (with a warning) if {@code ecm_zone_weights.csv} does not exist.
     * Re-run {@code gen_ecm_mapping.py} to regenerate it.
     */
    private void setupWeightVisualization(Simulation sim) {
        if (!ZONE_WEIGHTS_CSV_FILE.exists()) {
            sim.println("[ECM-WViz] ecm_zone_weights.csv not found — weight visualization skipped.");
            sim.println("[ECM-WViz]   Re-run gen_ecm_mapping.py to generate it.");
            return;
        }

        // --- load / refresh the weights FileTable ---
        star.common.FileTable ft = null;
        try {
            try {
                ft = (star.common.FileTable) sim.getTableManager()
                        .getTable(ZONE_WEIGHTS_TABLE_NAME);
                sim.println("[ECM-WViz] Found existing zone-weights table: '"
                    + ZONE_WEIGHTS_TABLE_NAME + "'");
            } catch (Exception notFound) {
                ft = (star.common.FileTable) sim.getTableManager()
                        .createTable(star.common.FileTable.class);
                ft.setPresentationName(ZONE_WEIGHTS_TABLE_NAME);
                sim.println("[ECM-WViz] Created zone-weights FileTable: '"
                    + ZONE_WEIGHTS_TABLE_NAME + "'");
            }
            // Point to weights CSV using reflection (handles setFileName / setFilename API change)
            // Use relative path so the .sim file remains portable across machines.
            String absPath = ZONE_WEIGHTS_CSV_PATH;
            for (String mn : new String[]{"setFileName", "setFilename"}) {
                try {
                    java.lang.reflect.Method m = ft.getClass().getMethod(mn, String.class);
                    m.invoke(ft, absPath);
                    break;
                } catch (NoSuchMethodException ignored) {}
            }
            ft.extract();
            sim.println("[ECM-WViz] Zone-weights table loaded: " + absPath);
        } catch (Exception e) {
            sim.println("[ECM-WViz] WARN: could not load zone-weights table: " + e.getMessage());
            return;
        }

        // --- determine number of zones from CSV header ---
        int nZones = 0;
        try (BufferedReader br = new BufferedReader(new FileReader(ZONE_WEIGHTS_CSV_FILE))) {
            String header = br.readLine();
            if (header != null) {
                for (String col : header.split(",")) {
                    if (col.trim().startsWith("w_zone_")) nZones++;
                }
            }
        } catch (Exception e) {
            sim.println("[ECM-WViz] WARN: could not read zone-weights CSV header: "
                + e.getMessage());
            return;
        }
        if (nZones == 0) {
            sim.println("[ECM-WViz] WARN: no w_zone_* columns found in zone-weights CSV.");
            return;
        }

        // --- create / update one UserFieldFunction per zone ---
        // NOTE: disabled — interpolateTable() syntax for 3-arg XYZ lookup is not supported
        // in STAR-CCM+ 2602 and causes compilation errors on every zone. The table is still
        // loaded above (useful for manual inspection). Re-enable once the correct API is known.
        /*
        int created = 0, updated = 0;
        for (int z = 0; z < nZones; z++) {
            String ffName  = String.format("ECM_Zone_%d_Weight", z);
            String colName = String.format("w_zone_%d", z);
            String defn    = String.format(
                "interpolateTable(\"%s\", \"%s\", $$Position[0], $$Position[1], $$Position[2])",
                ZONE_WEIGHTS_TABLE_NAME, colName);
            try {
                star.common.UserFieldFunction ff;
                boolean existed = false;
                try {
                    ff = (star.common.UserFieldFunction) sim.getFieldFunctionManager()
                            .getFunction(ffName);
                    existed = true;
                } catch (Exception notFound) {
                    ff = (star.common.UserFieldFunction) sim.getFieldFunctionManager()
                            .createFieldFunction();
                    ff.setPresentationName(ffName);
                    ff.setFunctionName(ffName);
                }
                ff.setDefinition(defn);
                if (existed) updated++; else created++;
            } catch (Exception e) {
                sim.println(String.format(
                    "[ECM-WViz] WARN: could not create/update FF for zone %d: %s",
                    z, e.getMessage()));
            }
        }
        sim.println(String.format(
            "[ECM-WViz] Zone weight field functions ready: %d created, %d updated "
            + "(ECM_Zone_0_Weight … ECM_Zone_%d_Weight).",
            created, updated, nZones - 1));
        sim.println("[ECM-WViz]   Open Tools > Field Functions to inspect or "
            + "drag onto a scalar scene on the jellyRoll region.");
        */
        sim.println(String.format(
            "[ECM-WViz] Zone-weights table loaded: %d zones detected. "
            + "Field function creation disabled (interpolateTable syntax TBD).", nZones));
    }

    /**
     * Automatically configure the jellyRoll region's energy source to use the
     * injection FileTable, eliminating any need for manual STAR-CCM+ setup.
     *
     * <p>Sets:
     * <ol>
     *   <li>{@code EnergyUserVolumeSourceOption} → {@code VOLUMETRIC_HEAT_SOURCE}</li>
     *   <li>{@code VolumetricHeatSourceProfile} → tabular-XYZ method, column {@code qVol_W_m3}
     *       from the given FileTable</li>
     * </ol>
     *
     * <p>On any failure the exception is caught, an error is printed, and the
     * simulation continues — the user will need to set up the energy source manually
     * (or accept globalParam fallback).
     *
     * @param sim       the running Simulation
     * @param region    the jellyRoll Region
     * @param fileTable the FileTable to wire into the energy source
     */
    private void autoConfigureJellyRollEnergySource(Simulation sim, Region region,
            star.common.FileTable fileTable) {
        try {
            // Step 1: switch energy source type to volumetric (W/m³).
            // EnergyUserVolumeSourceOption may live on the Region or on its PhysicsContinuum
            // depending on how the STAR-CCM+ physics was configured.  Try both.
            EnergyUserVolumeSourceOption srcOpt;
            try {
                srcOpt = region.get(EnergyUserVolumeSourceOption.class);
            } catch (Exception regionEx) {
                Object pc = region.getPhysicsContinuum();
                if (pc instanceof star.common.PhysicsContinuum) {
                    srcOpt = ((star.common.PhysicsContinuum) pc).get(EnergyUserVolumeSourceOption.class);
                } else {
                    throw new RuntimeException("EnergyUserVolumeSourceOption not found on region; "
                        + "physics continuum is " + (pc != null ? pc.getClass().getName() : "null")
                        + "; original: " + regionEx.getMessage());
                }
            }
            srcOpt.setSelected(EnergyUserVolumeSourceOption.Type.VOLUMETRIC_HEAT_SOURCE);
            sim.println("[ECM-EW] jellyRoll energy source set to VOLUMETRIC_HEAT_SOURCE.");

            // Step 2: wire the profile to the FileTable column (no UFF required).
            VolumetricHeatSourceProfile profile;
            try {
                profile = region.get(VolumetricHeatSourceProfile.class);
            } catch (Exception e2) {
                Object pc = region.getPhysicsContinuum();
                if (pc instanceof star.common.PhysicsContinuum) {
                    profile = ((star.common.PhysicsContinuum) pc).get(VolumetricHeatSourceProfile.class);
                } else {
                    throw e2;
                }
            }
            profile.setTabularXyzMethod(fileTable, "qVol_W_m3");
            sim.println("[ECM-EW] jellyRoll VolumetricHeatSourceProfile wired to FileTable '"
                + Q_TABLE_NAME + "', column 'qVol_W_m3'.");
            sim.println("[ECM-EW] Auto-configuration complete — no manual UFF or energy-source setup required.");
        } catch (Exception ex) {
            sim.println("[ECM-EW] WARN: autoConfigureJellyRollEnergySource failed: " + ex.getMessage());
            sim.println("[ECM-EW]   Root cause: 'User Volumetric Heat Source' is not enabled for jellyRoll.");
            sim.println("[ECM-EW]   Fix (one-time, in STAR-CCM+ GUI before running this macro):");
            sim.println("[ECM-EW]     Physics > [jellyRoll continuum] > Energy > User Volume Source = Enabled");
            sim.println("[ECM-EW]   After enabling, re-run this macro — it will auto-wire the FileTable.");
            sim.println("[ECM-EW]   Do NOT create a User Field Function; the direct FileTable method is used.");
        }
    }

    // =========================================================================
    // DIAGNOSTIC HELPERS — heat-injection verification
    // =========================================================================

    /**
     * DIAG-1: Log the EXACT active method class name for each jellyRoll's
     * {@code VolumetricHeatSourceProfile}.  Called once at startup after
     * {@code autoConfigureJellyRollEnergySource}.  Confirms whether
     * {@code XyzTabularScalarProfileMethod} is actually active or whether some
     * other method (Constant, UFF) is in use instead.
     */
    private void diagProfileMethodType(Simulation sim, List<Region> regions) {
        sim.println("[ECM-DIAG1] === VolumetricHeatSourceProfile method audit ===");
        for (Region jr : regions) {
            String rn = jr.getPresentationName();
            try {
                // Try to get the profile from the region directly
                VolumetricHeatSourceProfile profile;
                try {
                    profile = jr.get(VolumetricHeatSourceProfile.class);
                } catch (Exception e1) {
                    Object pc = jr.getPhysicsContinuum();
                    if (pc instanceof star.common.PhysicsContinuum) {
                        profile = ((star.common.PhysicsContinuum) pc).get(VolumetricHeatSourceProfile.class);
                    } else {
                        sim.println("[ECM-DIAG1]   " + rn + ": CANNOT GET profile — " + e1.getMessage());
                        continue;
                    }
                }
                // Use reflection to call getMethod() which returns the active ProfileMethod
                Object method = null;
                try {
                    java.lang.reflect.Method gm = profile.getClass().getMethod("getMethod");
                    method = gm.invoke(profile);
                } catch (Exception re) {
                    // Try alternate API name
                    try {
                        java.lang.reflect.Method gm = profile.getClass().getMethod("getProfileMethod");
                        method = gm.invoke(profile);
                    } catch (Exception re2) {
                        sim.println("[ECM-DIAG1]   " + rn + ": reflection getMethod() failed: " + re.getMessage());
                    }
                }
                if (method != null) {
                    sim.println("[ECM-DIAG1]   " + rn + ": active method class = " + method.getClass().getName());
                    // Also try to log the table name if it is XyzTabular
                    try {
                        java.lang.reflect.Method tg = method.getClass().getMethod("getTable");
                        Object tbl = tg.invoke(method);
                        String _pn = "?"; try { _pn = (String) tbl.getClass().getMethod("getPresentationName").invoke(tbl); } catch (Exception _pe) {}
                        String tblName = tbl != null ? tbl.getClass().getSimpleName() + ":'" + _pn + "'" : "null";
                        sim.println("[ECM-DIAG1]   " + rn + ": table = " + tblName);
                    } catch (Exception ignored) {}
                    try {
                        java.lang.reflect.Method dg = method.getClass().getMethod("getData");
                        Object data = dg.invoke(method);
                        sim.println("[ECM-DIAG1]   " + rn + ": data/column = " + data);
                    } catch (Exception ignored) {}
                } else {
                    sim.println("[ECM-DIAG1]   " + rn + ": method object is null (reflection gave no result)");
                }
            } catch (Exception ex) {
                sim.println("[ECM-DIAG1]   " + rn + ": EXCEPTION — " + ex.getMessage());
            }
        }
        sim.println("[ECM-DIAG1] === end of profile audit ===");
    }

    /**
     * DIAG-2: After {@code fileTable.extract()}, read back the {@code qVol_W_m3}
     * column directly from the on-disk CSV (Q_TABLE_CSV_FILE) and compare vs the
     * {@code expectedQVol} array (what was written).  Also logs summary stats.
     * This avoids uncertain STAR in-memory FileTable row-access API.
     *
     * @param fileTable    the STAR FileTable (used only for name in logging)
     * @param expectedQVol per-cell qVol values that were written to the CSV (may be null)
     */
    private void diagQTableReadback(Simulation sim, star.common.FileTable fileTable,
            double[] expectedQVol) {
        try {
            // Re-read the CSV we just wrote
            double minQ = Double.MAX_VALUE, maxQ = -Double.MAX_VALUE, sumQ = 0.0;
            int nRows = 0;
            int qCol = -1;
            try (BufferedReader br = new BufferedReader(new FileReader(Q_TABLE_CSV_FILE))) {
                String header = br.readLine();
                if (header == null) {
                    sim.println("[ECM-DIAG2] WARN: Q_TABLE_CSV_FILE is empty");
                    return;
                }
                String[] cols = header.split(",", -1);
                for (int ci = 0; ci < cols.length; ci++) {
                    if ("qVol_W_m3".equalsIgnoreCase(cols[ci].trim())) { qCol = ci; break; }
                }
                if (qCol < 0) {
                    sim.println("[ECM-DIAG2] WARN: 'qVol_W_m3' not found in CSV header: " + header);
                    return;
                }
                String line;
                while ((line = br.readLine()) != null) {
                    if (line.isEmpty()) continue;
                    String[] parts = line.split(",", -1);
                    if (parts.length <= qCol) continue;
                    try {
                        double v = Double.parseDouble(parts[qCol].trim());
                        if (v < minQ) minQ = v;
                        if (v > maxQ) maxQ = v;
                        sumQ += v;
                        nRows++;
                    } catch (NumberFormatException ignored) {}
                }
            }
            double meanQ = (nRows > 0) ? sumQ / nRows : 0.0;
            sim.println(String.format(
                "[ECM-DIAG2] CSV readback (qVol_W_m3): nRows=%d  range=[%.4e .. %.4e]  mean=%.4e W/m3",
                nRows, (minQ == Double.MAX_VALUE ? 0.0 : minQ),
                       (maxQ == -Double.MAX_VALUE ? 0.0 : maxQ), meanQ));

            // Log what was actually written to the array
            if (expectedQVol != null && expectedQVol.length > 0) {
                double expMin = Double.MAX_VALUE, expMax = -Double.MAX_VALUE, expSum = 0.0;
                for (double v : expectedQVol) {
                    if (v < expMin) expMin = v;
                    if (v > expMax) expMax = v;
                    expSum += v;
                }
                double expMean = expSum / expectedQVol.length;
                sim.println(String.format(
                    "[ECM-DIAG2] Written array: nCells=%d  range=[%.4e .. %.4e]  mean=%.4e W/m3",
                    expectedQVol.length, expMin, expMax, expMean));
                // Check table name path
                sim.println("[ECM-DIAG2] FileTable name='" + fileTable.getPresentationName()
                    + "'  CSV path=" + Q_TABLE_CSV_FILE.getAbsolutePath());
            }
        } catch (Exception ex) {
            sim.println("[ECM-DIAG2] WARN: readback failed — " + ex.getMessage());
        }
    }

    /**
     * DIAG-3: Create (or retrieve) STAR MinReport, MaxReport, and VolumeIntegralReport
     * for the "User Specified Energy Source" field function on all coupled jellyRoll
     * regions.  Returns a list of the three reports.  Call once at setup; then call
     * {@link #logEnergySourceReports} each step to record the values.
     *
     * @param regions  the coupled jellyRoll regions
     * @return list of [MinReport, MaxReport, VolumeIntegralReport], or empty list on failure
     */
    private List<star.base.report.Report> getOrCreateEnergySourceReports(
            Simulation sim, List<Region> regions) {
        List<star.base.report.Report> result = new ArrayList<>();
        // DIAG-3 disabled: ReportManager / NeoObjectInterface API incompatible with STAR 2602.
        // Returning empty list — logEnergySourceReports() will be a no-op.
        return result;
        /* ---- disabled body below ----
        String[] names = {"ECM_EnergySource_Min", "ECM_EnergySource_Max", "ECM_EnergySource_VolInt"};
        String ffName = "User Specified Energy Source";

        // Find the field function
        star.common.PrimitiveFieldFunction ff = null;
        try {
            ff = (star.common.PrimitiveFieldFunction)
                sim.getFieldFunctionManager().getFunction(ffName);
        } catch (Exception e) {
            sim.println("[ECM-DIAG3] WARN: field function '" + ffName + "' not found — " + e.getMessage());
            sim.println("[ECM-DIAG3] Energy source reports will not be created.");
            return result;
        }

        // ReportManager API changed in STAR 2602 — use var or reflection if re-enabling
        // NeoObjectInterface removed — pass regions directly to setObjects()
        Object rm = sim.getReportManager(); // placeholder

        // --- MinReport ---
        try {
            star.base.report.MinReport minR;
            try {
                minR = (star.base.report.MinReport) rm.getReport(names[0]);
                sim.println("[ECM-DIAG3] Found existing report: " + names[0]);
            } catch (Exception e) {
                minR = rm.createReport(star.base.report.MinReport.class);
                minR.setPresentationName(names[0]);
            }
            minR.setFieldFunction(ff);
            minR.getParts().setObjects(partsArr);
            result.add(minR);
        } catch (Exception ex) {
            sim.println("[ECM-DIAG3] WARN: could not create MinReport: " + ex.getMessage());
        }

        // --- MaxReport ---
        try {
            star.base.report.MaxReport maxR;
            try {
                maxR = (star.base.report.MaxReport) rm.getReport(names[1]);
                sim.println("[ECM-DIAG3] Found existing report: " + names[1]);
            } catch (Exception e) {
                maxR = rm.createReport(star.base.report.MaxReport.class);
                maxR.setPresentationName(names[1]);
            }
            maxR.setFieldFunction(ff);
            maxR.getParts().setObjects(partsArr);
            result.add(maxR);
        } catch (Exception ex) {
            sim.println("[ECM-DIAG3] WARN: could not create MaxReport: " + ex.getMessage());
        }

        // --- VolumeIntegralReport ---
        try {
            star.base.report.VolumeIntegralReport viR;
            try {
                viR = (star.base.report.VolumeIntegralReport) rm.getReport(names[2]);
                sim.println("[ECM-DIAG3] Found existing report: " + names[2]);
            } catch (Exception e) {
                viR = rm.createReport(star.base.report.VolumeIntegralReport.class);
                viR.setPresentationName(names[2]);
            }
            viR.setFieldFunction(ff);
            viR.getParts().setObjects(partsArr);
            result.add(viR);
        } catch (Exception ex) {
            sim.println("[ECM-DIAG3] WARN: could not create VolumeIntegralReport: " + ex.getMessage());
        }

        if (!result.isEmpty()) {
            sim.println("[ECM-DIAG3] Energy source reports ready (" + result.size()
                + " of 3): " + names[0] + ", " + names[1] + ", " + names[2]);
        }
        return result;
        ---- end disabled body ---- */
    }

    /**
     * DIAG-3 (per-step): Query and log the energy-source reports created by
     * {@link #getOrCreateEnergySourceReports}.  Logs min, max, and volume-integral
     * of the "User Specified Energy Source" field function in [W/m³] and [W].
     *
     * @param reports  the list returned by {@link #getOrCreateEnergySourceReports}
     */
    private void logEnergySourceReports(Simulation sim,
            List<star.base.report.Report> reports, double simTime) {
        if (reports == null || reports.isEmpty()) return;
        try {
            // getValue() removed from star.base.report.Report in STAR 2602 — use reflection
            double minV = Double.NaN, maxV = Double.NaN, volI = Double.NaN;
            for (String _m : new String[]{"getValue","getReportMonitorValue"}) { try { if (reports.size() > 0) { minV = ((Number) reports.get(0).getClass().getMethod(_m).invoke(reports.get(0))).doubleValue(); break; } } catch (Exception _e) {} }
            for (String _m : new String[]{"getValue","getReportMonitorValue"}) { try { if (reports.size() > 1) { maxV = ((Number) reports.get(1).getClass().getMethod(_m).invoke(reports.get(1))).doubleValue(); break; } } catch (Exception _e) {} }
            for (String _m : new String[]{"getValue","getReportMonitorValue"}) { try { if (reports.size() > 2) { volI = ((Number) reports.get(2).getClass().getMethod(_m).invoke(reports.get(2))).doubleValue(); break; } } catch (Exception _e) {} }
            sim.println(String.format(
                "[ECM-DIAG3] t=%.3f s  EnergySource: min=%.4e  max=%.4e  volIntegral=%.4e W/m3·m3=W",
                simTime, minV, maxV, volI));
        } catch (Exception ex) {
            sim.println("[ECM-DIAG3] WARN: report query failed — " + ex.getMessage());
        }
    }

    /**
     * Regenerate ecm_mapping.csv by running gen_ecm_mapping.py.
     * Called on every macro startup after the current ecm_cell_map.csv is written.
     * The freshly-written ecm_cell_map.csv is the input; ecm_mapping.csv is the output.
     * Throws on any failure — the run must not proceed without a fresh mapping.
     */
    private void regenEcmMapping(Simulation sim) throws Exception {
        File genScript = new File(ECM_DIR, "gen_ecm_mapping.py");
        if (!genScript.exists()) {
            throw new Exception(
                "[ECM-EW] FATAL: gen_ecm_mapping.py not found at " + genScript.getAbsolutePath()
                + ". Cannot regenerate ecm_mapping.csv after mesh change. "
                + "Restore gen_ecm_mapping.py to the ecm/ directory and re-run.");
        }

        List<String> command = new ArrayList<>(PYTHON_CMD);
        command.add(genScript.getAbsolutePath());
        command.add("--cell-map");
        command.add(CELL_MAP_CSV_FILE.getAbsolutePath());
        command.add("--out");
        command.add(ECM_MAPPING_CSV_FILE.getAbsolutePath());
        if (REGION_GEOMETRY_CSV_FILE.exists()) {
            command.add("--geometry-csv");
            command.add(REGION_GEOMETRY_CSV_FILE.getAbsolutePath());
        }

        sim.println("[ECM-EW] Running: " + command);
        ProcessBuilder pb = new ProcessBuilder(command);
        pb.directory(PROJECT_ROOT);
        pb.redirectErrorStream(true);
        Process p = pb.start();

        final List<String> lines = new ArrayList<>();
        Thread drain = new Thread(() -> {
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(p.getInputStream()))) {
                String line;
                while ((line = br.readLine()) != null) {
                    synchronized (lines) { lines.add(line); }
                }
            } catch (IOException ignored) {}
        });
        drain.start();
        int exitCode = p.waitFor();
        drain.join(5000);

        synchronized (lines) {
            for (String line : lines) sim.println("[ECM-mapping] " + line);
        }

        if (exitCode != 0 || !ECM_MAPPING_CSV_FILE.exists()) {
            throw new Exception(
                "[ECM-EW] FATAL: gen_ecm_mapping.py exited with code " + exitCode
                + ". ecm_mapping.csv was not produced. "
                + "Fix the error above and re-run.");
        }
        sim.println("[ECM-EW] ecm_mapping.csv regenerated successfully.");
    }

    /** Writes a step CSV using the fallback (previous) qVol array. */
    private void writeStepCsvFallback(Simulation sim, int step, CellMapper cellMapper,
            double[] temps, double[] qVolPrev) {
        try {
            writeStepCsv(CELL_STEP_CSV_FILE, step, cellMapper, temps, qVolPrev);
        } catch (IOException e) {
            sim.println("[ECM-EW] WARN: could not write fallback step CSV: " + e.getMessage());
        }
    }

    /**
     * Write the one-time cell-map CSV: cellId,x_m,y_m,z_m.
     * This file is used for visualisation (e.g. Python scatter plot of cell
     * positions coloured by cellId or initial temperature).
     */
    private static void writeCellMapCsv(File path, CellMapper cellMapper) throws IOException {
        path.getParentFile().mkdirs();
        try (PrintWriter pw = new PrintWriter(new FileWriter(path, false))) {
            pw.println("cellId,x_m,y_m,z_m,volume_m3,regionIdx");
            int      n    = cellMapper.nCells();
            int[]    ids  = cellMapper.cellIds();
            double[] xs   = cellMapper.xCentroids();
            double[] ys   = cellMapper.yCentroids();
            double[] zs   = cellMapper.zCentroids();
            double[] vols = cellMapper.volumes();
            int[]    ri   = cellMapper.regionIndices();
            for (int i = 0; i < n; i++) {
                String volStr = (vols != null) ? ("," + vols[i]) : ",-1";
                String riStr  = (ri   != null) ? ("," + ri[i])   : ",0";
                pw.println(ids[i] + "," + xs[i] + "," + ys[i] + "," + zs[i] + volStr + riStr);
            }
        }
    }

    /**
     * Write ecm_region_geometry.csv with per-region coordinate system data.
     *
     * For each coupled region (jellyRoll_1, jellyRoll_2, ...), looks for a
     * matching STAR-CCM+ Laboratory Coordinate System named with the same
     * numeric suffix (e.g. "jellyRoll_1" → coordinate system containing "_1").
     * If found, extracts the origin and the axis direction (basis1 = axial).
     *
     * Fallback: if no coordinate system is found, computes the cylinder axis
     * via PCA on the cell centroids from the CellMapper.
     *
     * Columns: regionIdx, origin_x, origin_y, origin_z, axis_x, axis_y, axis_z
     */
    private void writeRegionGeometryCsv(Simulation sim, File path,
            List<Region> regions, CellMapper cellMapper) {
        path.getParentFile().mkdirs();
        int nRegions = regions.size();
        int[] ri = cellMapper.regionIndices();
        double[] xs = cellMapper.xCentroids();
        double[] ys = cellMapper.yCentroids();
        double[] zs = cellMapper.zCentroids();

        // Collect all coordinate systems from the simulation
        java.util.Map<String, Object> csMap = new java.util.LinkedHashMap<>();
        try {
            Object csManager = sim.getClass().getMethod("getCoordinateSystemManager").invoke(sim);
            if (csManager != null) {
                // Try getObjects() or getObjectsOf()
                java.util.Collection<?> csList = null;
                for (String mName : new String[]{"getObjects", "getLabCoordinateSystems"}) {
                    try {
                        Object result = csManager.getClass().getMethod(mName).invoke(csManager);
                        if (result instanceof java.util.Collection) {
                            csList = (java.util.Collection<?>) result;
                            break;
                        }
                    } catch (Exception ignored) {}
                }
                if (csList != null) {
                    for (Object cs : csList) {
                        try {
                            String csName = (String) cs.getClass().getMethod("getPresentationName").invoke(cs);
                            csMap.put(csName, cs);
                        } catch (Exception ignored) {}
                    }
                }
                sim.println("[ECM-GEOM] Found " + csMap.size() + " coordinate systems: " + csMap.keySet());
            }
        } catch (Exception e) {
            sim.println("[ECM-GEOM] WARN: could not enumerate coordinate systems: " + e.getMessage());
        }

        try (PrintWriter pw = new PrintWriter(new FileWriter(path, false))) {
            pw.println("regionIdx,origin_x,origin_y,origin_z,axis_x,axis_y,axis_z");

            for (int rIdx = 0; rIdx < nRegions; rIdx++) {
                String regionName = regions.get(rIdx).getPresentationName();
                // Extract suffix (e.g. "_1" from "jellyRoll_1")
                String suffix = "";
                int underscorePos = regionName.lastIndexOf('_');
                if (underscorePos >= 0) {
                    suffix = regionName.substring(underscorePos);
                }

                // Try to find a matching coordinate system
                double[] origin = null;
                double[] axis = null;

                if (!suffix.isEmpty()) {
                    for (java.util.Map.Entry<String, Object> entry : csMap.entrySet()) {
                        if (entry.getKey().endsWith(suffix) || entry.getKey().contains(suffix)) {
                            Object cs = entry.getValue();
                            try {
                                origin = extractCsOrigin(sim, cs);
                                axis = extractCsAxis(sim, cs);
                                sim.println("[ECM-GEOM] Region " + rIdx + " (" + regionName
                                    + "): matched CS '" + entry.getKey() + "'"
                                    + " origin=(" + origin[0] + "," + origin[1] + "," + origin[2] + ")"
                                    + " axis=(" + axis[0] + "," + axis[1] + "," + axis[2] + ")");
                            } catch (Exception e) {
                                sim.println("[ECM-GEOM] WARN: could not extract CS data from '"
                                    + entry.getKey() + "': " + e.getMessage());
                            }
                            break;
                        }
                    }
                }

                // Fallback: PCA on cell centroids
                if (origin == null || axis == null) {
                    sim.println("[ECM-GEOM] Region " + rIdx + " (" + regionName
                        + "): no matching CS found — using PCA fallback");
                    double[] pca = pcaCylinderAxis(xs, ys, zs, ri, rIdx);
                    origin = new double[]{pca[0], pca[1], pca[2]};
                    axis = new double[]{pca[3], pca[4], pca[5]};
                    sim.println("[ECM-GEOM]   PCA center=(" + origin[0] + "," + origin[1] + "," + origin[2] + ")"
                        + " axis=(" + axis[0] + "," + axis[1] + "," + axis[2] + ")");
                }

                pw.println(String.format("%d,%.9e,%.9e,%.9e,%.9e,%.9e,%.9e",
                    rIdx, origin[0], origin[1], origin[2], axis[0], axis[1], axis[2]));
            }
        } catch (IOException e) {
            sim.println("[ECM-GEOM] ERROR writing region geometry CSV: " + e.getMessage());
        }
    }

    /**
     * Extract origin (x,y,z) [m] from a STAR-CCM+ coordinate system object via reflection.
     */
    private static double[] extractCsOrigin(Simulation sim, Object cs) throws Exception {
        // Try getOrigin() → getQuantity() → getVector() or getValue()
        Object originObj = cs.getClass().getMethod("getOrigin").invoke(cs);
        double[] result = new double[3];
        // Try common patterns: getQuantity().getRawValue() or getInternalVector()
        for (String path : new String[]{"getQuantity", "getInternalVector"}) {
            try {
                Object q = originObj.getClass().getMethod(path).invoke(originObj);
                if (q instanceof double[]) {
                    return (double[]) q;
                }
                // Try getRawValue or getValue
                for (String valMethod : new String[]{"getRawValue", "getValue", "getInternalValue"}) {
                    try {
                        Object val = q.getClass().getMethod(valMethod).invoke(q);
                        if (val instanceof double[]) {
                            return (double[]) val;
                        }
                    } catch (Exception ignored) {}
                }
            } catch (Exception ignored) {}
        }
        // Try getComponent(int) pattern
        for (String compMethod : new String[]{"getComponent"}) {
            try {
                for (int i = 0; i < 3; i++) {
                    Object comp = originObj.getClass().getMethod(compMethod, int.class).invoke(originObj, i);
                    if (comp instanceof Number) {
                        result[i] = ((Number) comp).doubleValue();
                    } else {
                        // Try getQuantity().getRawValue()
                        Object q = comp.getClass().getMethod("getQuantity").invoke(comp);
                        result[i] = ((Number) q.getClass().getMethod("getRawValue").invoke(q)).doubleValue();
                    }
                }
                return result;
            } catch (Exception ignored) {}
        }
        // Last resort: try to get as vector from the origin coordinate itself
        try {
            java.lang.reflect.Method[] methods = originObj.getClass().getMethods();
            for (java.lang.reflect.Method m : methods) {
                if (m.getReturnType() == double[].class && m.getParameterCount() == 0) {
                    double[] v = (double[]) m.invoke(originObj);
                    if (v != null && v.length >= 3) {
                        return v;
                    }
                }
            }
        } catch (Exception ignored) {}
        throw new Exception("Could not extract origin vector — tried all known API patterns");
    }

    /**
     * Extract axis direction from a STAR-CCM+ coordinate system.
     * Uses basis vector 0 (typically the "i" or axial direction).
     * Returns unit vector [ax, ay, az].
     */
    private static double[] extractCsAxis(Simulation sim, Object cs) throws Exception {
        // Try getBasis0() or getBasis1() — basis0 is typically the axial direction
        for (String basisMethod : new String[]{"getBasis0", "getBasis1"}) {
            try {
                Object basisObj = cs.getClass().getMethod(basisMethod).invoke(cs);
                // Try to get vector from basis
                double[] vec = extractVectorFromBasis(basisObj);
                if (vec != null) {
                    double norm = Math.sqrt(vec[0]*vec[0] + vec[1]*vec[1] + vec[2]*vec[2]);
                    if (norm > 1e-15) {
                        return new double[]{vec[0]/norm, vec[1]/norm, vec[2]/norm};
                    }
                }
            } catch (Exception ignored) {}
        }
        // Fallback: try getLocalCoordinateSystemBasis() pattern
        try {
            Object basis = cs.getClass().getMethod("getLocalCoordinateSystemBasis").invoke(cs);
            // Each basis has 3 vectors; we want the first one (axial)
            for (String m : new String[]{"getBasis0Vector", "get_e1"}) {
                try {
                    Object vec = basis.getClass().getMethod(m).invoke(basis);
                    double[] v = extractVectorValue(vec);
                    if (v != null) return normalizeVector(v);
                } catch (Exception ignored) {}
            }
        } catch (Exception ignored) {}

        throw new Exception("Could not extract axis vector from coordinate system");
    }

    private static double[] extractVectorFromBasis(Object basisObj) {
        // Try getQuantity().getRawValue() or direct double[] returns
        try {
            java.lang.reflect.Method[] methods = basisObj.getClass().getMethods();
            for (java.lang.reflect.Method m : methods) {
                if (m.getReturnType() == double[].class && m.getParameterCount() == 0) {
                    double[] v = (double[]) m.invoke(basisObj);
                    if (v != null && v.length >= 3) return v;
                }
            }
        } catch (Exception ignored) {}
        // Try getQuantity() chain
        try {
            Object q = basisObj.getClass().getMethod("getQuantity").invoke(basisObj);
            for (String valMethod : new String[]{"getRawValue", "getValue", "getInternalValue"}) {
                try {
                    Object val = q.getClass().getMethod(valMethod).invoke(q);
                    if (val instanceof double[]) return (double[]) val;
                } catch (Exception ignored) {}
            }
        } catch (Exception ignored) {}
        return null;
    }

    private static double[] extractVectorValue(Object vecObj) {
        if (vecObj instanceof double[]) return (double[]) vecObj;
        try {
            java.lang.reflect.Method[] methods = vecObj.getClass().getMethods();
            for (java.lang.reflect.Method m : methods) {
                if (m.getReturnType() == double[].class && m.getParameterCount() == 0) {
                    double[] v = (double[]) m.invoke(vecObj);
                    if (v != null && v.length >= 3) return v;
                }
            }
        } catch (Exception ignored) {}
        return null;
    }

    private static double[] normalizeVector(double[] v) {
        double norm = Math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
        if (norm < 1e-15) return new double[]{1, 0, 0};
        return new double[]{v[0]/norm, v[1]/norm, v[2]/norm};
    }

    /**
     * PCA-based cylinder axis detection from cell centroids (Java fallback).
     * Returns [cx, cy, cz, ax, ay, az] — center + unit axis vector.
     */
    private static double[] pcaCylinderAxis(double[] xs, double[] ys, double[] zs,
            int[] regionIndices, int targetRegion) {
        // Collect centroids for the target region
        int count = 0;
        double cx = 0, cy = 0, cz = 0;
        for (int i = 0; i < xs.length; i++) {
            if (regionIndices != null && regionIndices[i] != targetRegion) continue;
            cx += xs[i]; cy += ys[i]; cz += zs[i];
            count++;
        }
        if (count == 0) return new double[]{0, 0, 0, 1, 0, 0};
        cx /= count; cy /= count; cz /= count;

        // 3x3 covariance matrix (symmetric)
        double c00=0, c01=0, c02=0, c11=0, c12=0, c22=0;
        for (int i = 0; i < xs.length; i++) {
            if (regionIndices != null && regionIndices[i] != targetRegion) continue;
            double dx = xs[i]-cx, dy = ys[i]-cy, dz = zs[i]-cz;
            c00 += dx*dx; c01 += dx*dy; c02 += dx*dz;
            c11 += dy*dy; c12 += dy*dz; c22 += dz*dz;
        }
        c00/=count; c01/=count; c02/=count; c11/=count; c12/=count; c22/=count;

        // Power iteration for largest eigenvector
        double vx=1, vy=0, vz=0;
        for (int iter = 0; iter < 50; iter++) {
            double wx = c00*vx + c01*vy + c02*vz;
            double wy = c01*vx + c11*vy + c12*vz;
            double wz = c02*vx + c12*vy + c22*vz;
            double norm = Math.sqrt(wx*wx + wy*wy + wz*wz);
            if (norm < 1e-30) break;
            vx = wx/norm; vy = wy/norm; vz = wz/norm;
        }

        // Consistent orientation: largest-magnitude component positive
        double maxAbs = Math.abs(vx);
        double maxVal = vx;
        if (Math.abs(vy) > maxAbs) { maxAbs = Math.abs(vy); maxVal = vy; }
        if (Math.abs(vz) > maxAbs) { maxVal = vz; }
        if (maxVal < 0) { vx = -vx; vy = -vy; vz = -vz; }

        return new double[]{cx, cy, cz, vx, vy, vz};
    }

    /**
     * Write per-step diagnostic CSV: step,cellId,x_m,y_m,z_m,T_K,qVol_W_m3.
     * Overwritten each step so the file always holds the latest snapshot.
     */
    private static void writeStepCsv(File path, int step, CellMapper cellMapper,
            double[] temps, double[] qVolPerCell) throws IOException {
        path.getParentFile().mkdirs();
        try (PrintWriter pw = new PrintWriter(new FileWriter(path, false))) {
            pw.println("step,cellId,x_m,y_m,z_m,T_K,q_W");
            int n = cellMapper.nCells();
            int[]    ids = cellMapper.cellIds();
            double[] xs  = cellMapper.xCentroids();
            double[] ys  = cellMapper.yCentroids();
            double[] zs  = cellMapper.zCentroids();
            for (int i = 0; i < n; i++) {
                pw.println(String.format("%d,%d,%.9e,%.9e,%.9e,%.9f,%.9e",
                    step, ids[i], xs[i], ys[i], zs[i], temps[i], qVolPerCell[i]));
            }
        }
    }

    // =========================================================================
    // MULTI-REGION CELL MAPPER BUILDER
    // =========================================================================

    /**
     * Build a CellMapper that covers all cells in the given list of regions.
     *
     * <p>This always reads the current XYZ T-table (configured in STAR to cover
     * the coupled jellyRoll region or regions) and never reuses an existing
     * {@code ecm_cell_map.csv}.  The macro rewrites the cell map and regenerates
     * ECM mapping files on every startup.
     *
     * @param sim     the running Simulation
     * @param regions sorted list of coupled regions (ascending name order)
     */
    private static CellMapper buildMergedCellMapper(Simulation sim, List<Region> regions)
            throws Exception {
        // Always use the current XYZ T-table as the source of truth.  Do not reuse
        // ecm_cell_map.csv: a remesh can leave an old CSV with matching row count
        // but stale centroids, volumes, or region labels.
        Table tTableRef = null;
        try {
            tTableRef = sim.getTableManager().getTable(T_TABLE_NAME);
            tTableRef.extract();
            sim.println(String.format(
                "[ECM-EW] T-table '%s' has %d total rows across %d region(s).",
                T_TABLE_NAME, tTableRef.getRowCount(), regions.size()));
        } catch (Exception e) {
            throw new Exception(
                "CellMapper requires T-table '" + T_TABLE_NAME + "' covering the coupled "
                + "jellyRoll region(s). Error: " + e.getMessage(), e);
        }

        // Build the mapper from the current table and current volumes.
        CellMapper merged = CellMapper.createFromXyzTable(sim, tTableRef, regions.get(0));
        merged.extractVolumes(sim);

        if (regions.size() == 1) {
            merged.setRegionIndices(new int[merged.nCells()]);
            sim.println(String.format(
                "[ECM-EW] CellMapper: %d current cells, single region.", merged.nCells()));
            return merged;
        }

        // Prefer computing regionIdx from FvRepresentation cell counts (authoritative, never stale).
        // Then verify the T-table row ordering matches the regions list, auto-correcting if reversed.
        int[] computedRi = computeRegionIndicesFromFvRep(sim, regions, merged.nCells());
        if (computedRi != null) {
            verifyAndCorrectRegionIdxOrdering(sim, regions, merged, computedRi);
            if (isSpatiallySeparatedRegionIdx(sim, merged, computedRi, regions.size(), "FvRep")) {
                merged.setRegionIndices(computedRi);
            } else {
                sim.println("[ECM-EW] regionIdx: FvRep result failed spatial validation; "
                    + "falling back to centroid clustering.");
                int[] centroidRi = computeRegionIndicesFromCentroids(sim, regions, merged);
                if (centroidRi != null) {
                    merged.setRegionIndices(centroidRi);
                    sim.println("[ECM-EW] regionIdx: replaced invalid FvRep/ordering labels "
                        + "with Y-centroid clustering.");
                } else {
                    merged.setRegionIndices(computedRi);
                    sim.println("[ECM-EW] WARN: centroid fallback failed; keeping FvRep regionIdx.");
                }
            }
        } else {
            // FvRep failed.  Fall back to Y-coordinate bimodality: assign cells
            // to the nearest cylinder from current T-table centroids.
            int[] centroidRi = computeRegionIndicesFromCentroids(sim, regions, merged);
            if (centroidRi != null) {
                // NOTE: do NOT call verifyAndCorrectRegionIdxOrdering here — the centroid
                // assignment is coordinate-based (not T-table-block-based), so the verify
                // function's block-swap logic would incorrectly re-map it.
                merged.setRegionIndices(centroidRi);
                sim.println("[ECM-EW] regionIdx: computed from Y-centroid clustering "
                    + "(FvRep unavailable). "
                    + "ecm_mapping.csv will be regenerated with correct per-region zones.");
            } else {
                merged.setRegionIndices(new int[merged.nCells()]);  // all zeros fallback
                sim.println("[ECM-EW] WARN: regionIdx could not be computed — all cells assigned to "
                    + "region 0. gen_ecm_mapping.py will treat all cells as one cylinder. "
                    + "Re-run from t=0 after resolving FvRep/CSV issues; "
                    + "ecm_mapping.csv will be auto-regenerated.");
            }
        }

        sim.println(String.format(
            "[ECM-EW] Merged CellMapper: %d total cells, %d regions.", merged.nCells(), regions.size()));
        return merged;
    }

    /**
     * Compute per-cell regionIdx by querying FvRepresentation for the cell count of each
     * coupled region.  Assumes the T-table rows are ordered by region in the same order
     * as {@code regions} (the sorted coupledRegions list).  This is reliable and never
     * stale, unlike reading back a previously-written ecm_cell_map.csv.
     *
     * @param regions    sorted list of coupled jellyRoll regions
     * @param totalCells expected total T-table row count (= sum of per-region cell counts)
     * @return regionIdx array (length = totalCells), or {@code null} on any failure
     */
    private static int[] computeRegionIndicesFromFvRep(Simulation sim,
            List<Region> regions, int totalCells) {
        try {
            FvRepresentation fvRep = CellMapper.getFvRepresentation(sim);
            int[] ri = new int[totalCells];
            int offset = 0;
            for (int rIdx = 0; rIdx < regions.size(); rIdx++) {
                int cnt;
                try {
                    Method mCnt = fvRep.getClass().getMethod("getCellCount", Region.class);
                    cnt = ((Number) mCnt.invoke(fvRep, regions.get(rIdx))).intValue();
                } catch (NoSuchMethodException e1) {
                    Method mCnt = fvRep.getClass().getMethod("getRegionCellCount", Region.class);
                    cnt = ((Number) mCnt.invoke(fvRep, regions.get(rIdx))).intValue();
                }
                for (int j = offset; j < offset + cnt && j < totalCells; j++) ri[j] = rIdx;
                sim.println(String.format(
                    "[ECM-EW] regionIdx: '%s' → %d cells (rows %d..%d), regionIdx=%d",
                    regions.get(rIdx).getPresentationName(), cnt, offset, offset + cnt - 1, rIdx));
                offset += cnt;
            }
            if (offset != totalCells) {
                sim.println(String.format(
                    "[ECM-EW] WARN: FvRep cell-count sum %d ≠ T-table rows %d; "
                    + "discarding computed regionIdx.", offset, totalCells));
                return null;
            }
            return ri;
        } catch (Exception e) {
            sim.println("[ECM-EW] WARN: computeRegionIndicesFromFvRep failed: " + e.getMessage());
            return null;
        }
    }

    /**
     * Verify (and if necessary auto-correct) the regionIdx assignment produced by
     * {@link #computeRegionIndicesFromFvRep} by comparing the T-table's configured
     * Parts list order against the sorted {@code regions} list.
     *
     * <p>The T-table row order follows its Parts list (set in the STAR-CCM+ GUI).
     * If the user configured Parts in an order different from the sorted
     * {@code coupledRegions} list, regionIdx would be silently swapped.  This method
     * detects that and, for the 2-region case, auto-corrects {@code regionIndices}
     * in-place.  For N&gt;2 it logs a warning and leaves the array unchanged.
     *
     * @param sim            running Simulation
     * @param regions        sorted coupled jellyRoll regions (ascending name order)
     * @param merged         merged CellMapper (read-only, used only for row count)
     * @param regionIndices  array to correct in-place if ordering is reversed
     */
    private static void verifyAndCorrectRegionIdxOrdering(Simulation sim,
            List<Region> regions, CellMapper merged, int[] regionIndices) throws Exception {

        List<String> regionNames = new ArrayList<>();
        for (Region r : regions) regionNames.add(r.getPresentationName());

        Table tTable = sim.getTableManager().getTable(T_TABLE_NAME);
        List<String> tablePartNames = getTablePartNames(sim, tTable);

        if (tablePartNames == null) {
            // Reflection could not read the Parts list — STAR API version difference.
            // We cannot verify programmatically; warn clearly and require manual check.
            sim.println("[ECM-EW] verifyRegionOrder: WARN: cannot retrieve T-table Parts list "
                + "via reflection (STAR API version may differ). "
                + "MANUAL CHECK REQUIRED: in STAR GUI confirm T-table '" + T_TABLE_NAME
                + "' Parts are in this exact order: " + regionNames + ". "
                + "Wrong order will silently misassign regionIdx and corrupt heat injection.");
            return;
        }

        if (tablePartNames.size() != regions.size()) {
            throw new Exception(
                "[ECM-EW] verifyRegionOrder: T-table '" + T_TABLE_NAME + "' has "
                + tablePartNames.size() + " Parts " + tablePartNames
                + " but there are " + regions.size() + " coupled regions " + regionNames
                + ". Configure the T-table Parts to contain exactly these regions: "
                + regionNames);
        }

        if (tablePartNames.equals(regionNames)) {
            sim.println("[ECM-EW] verifyRegionOrder: T-table Parts order VERIFIED — "
                + "matches coupled regions list " + regionNames + ".");
            return;
        }

        // Ordering mismatch detected.
        if (regions.size() == 2
                && tablePartNames.get(0).equals(regionNames.get(1))
                && tablePartNames.get(1).equals(regionNames.get(0))) {
            // Simple 2-region reversal — auto-correct in-place.
            int cnt0 = 0;
            for (int ri : regionIndices) if (ri == 0) cnt0++;
            sim.println("[ECM-EW] verifyRegionOrder: T-table Parts are REVERSED: "
                + tablePartNames + " vs expected " + regionNames + ". "
                + "AUTO-CORRECTING regionIdx (swapping 0↔1). "
                + "group[0] had " + cnt0 + " rows, group[1] had "
                + (regionIndices.length - cnt0) + " rows.");
            for (int i = 0; i < regionIndices.length; i++) {
                regionIndices[i] = 1 - regionIndices[i];
            }
            sim.println("[ECM-EW] verifyRegionOrder: regionIdx CORRECTED. "
                + "ecm_mapping.csv will be auto-deleted and regenerated on "
                + "fresh-start runs (t=0).");
        } else {
            // Cannot auto-correct: N > 2 or non-trivial permutation.
            throw new Exception(
                "[ECM-EW] verifyRegionOrder: T-table Parts order " + tablePartNames
                + " does not match coupled regions list " + regionNames
                + " and cannot be auto-corrected (N=" + regions.size() + " regions). "
                + "In the STAR GUI set T-table '" + T_TABLE_NAME
                + "' Parts to exactly: " + regionNames
                + " (same order), then delete ecm_cell_map.csv and re-run from t=0.");
        }
    }

    /**
     * Retrieve the ordered Parts list of a table via reflection.
     * Handles minor API differences across STAR-CCM+ versions by trying several
     * known method names for the parts collection accessor.
     *
     * @return ordered list of part presentation names, or {@code null} if unavailable
     */

    /**
     * Check whether {@code regionIdx} contains meaningful (non-trivial) values for
     * {@code nRegions} coupled regions.  Returns {@code false} if the array is
     * all-zeros when {@code nRegions > 1} (i.e. it came from the all-zeros fallback
     * and carries no real region information).
     */
    private static boolean isValidRegionIdx(int[] regionIdx, int nRegions) {
        if (nRegions <= 1) return true;
        for (int r : regionIdx) {
            if (r != 0) return true;   // at least one cell assigned to a non-zero region
        }
        return false;  // all zeros → stale/uninitialised CSV
    }

    /**
     * Sanity-check 2-region labels against the actual centroid positions.
     *
     * <p>The two-cell test cases used here are physically separated mainly in Y.
     * A valid {@code regionIdx} therefore has region 0 almost entirely on one
     * side of the global Y midpoint and region 1 almost entirely on the other.
     * This catches stale/corrupt {@code ecm_cell_map.csv} files whose row count
     * matches the current mesh but whose region labels alternate through both
     * physical jelly-rolls after a remesh.
     */
    private static boolean isSpatiallySeparatedRegionIdx(Simulation sim, CellMapper merged,
            int[] regionIdx, int nRegions, String source) {
        if (nRegions != 2 || regionIdx == null || regionIdx.length != merged.nCells()) {
            return true;
        }

        double[] ys = merged.yCentroids();
        if (ys == null || ys.length == 0) return true;

        double yMin = Double.MAX_VALUE, yMax = -Double.MAX_VALUE;
        for (double y : ys) {
            if (y < yMin) yMin = y;
            if (y > yMax) yMax = y;
        }
        double yRange = yMax - yMin;
        if (yRange < 0.020) {
            // Not a side-by-side two-cell geometry; do not reject labels here.
            return true;
        }

        double yMid = 0.5 * (yMin + yMax);
        int[][] counts = new int[2][2]; // [regionIdx][side: 0=low-Y, 1=high-Y]
        int invalid = 0;
        for (int i = 0; i < regionIdx.length; i++) {
            int ri = regionIdx[i];
            if (ri < 0 || ri >= 2) {
                invalid++;
                continue;
            }
            int side = (ys[i] < yMid) ? 0 : 1;
            counts[ri][side]++;
        }

        int r0 = counts[0][0] + counts[0][1];
        int r1 = counts[1][0] + counts[1][1];
        double purity0 = (r0 > 0) ? Math.max(counts[0][0], counts[0][1]) / (double) r0 : 0.0;
        double purity1 = (r1 > 0) ? Math.max(counts[1][0], counts[1][1]) / (double) r1 : 0.0;
        boolean valid = invalid == 0 && purity0 >= 0.90 && purity1 >= 0.90
            && counts[0][0] != counts[1][0];

        sim.println(String.format(
            "[ECM-EW] regionIdx spatial check (%s): yRange=%.4f m yMid=%.4f m "
            + "r0(low=%d high=%d purity=%.3f) r1(low=%d high=%d purity=%.3f) invalid=%d "
            + "=> %s",
            source, yRange, yMid,
            counts[0][0], counts[0][1], purity0,
            counts[1][0], counts[1][1], purity1,
            invalid, valid ? "OK" : "REJECT"));
        return valid;
    }

    /**
     * Fallback regionIdx assignment using Y-coordinate bimodality.
     *
     * <p>When {@code FvRepresentation.getCellCount()} is unavailable (STAR-CCM+ 2602)
     * and the cell-map CSV carries no valid regionIdx, this method detects two
     * distinct Y-clusters in the merged mapper's centroid array and assigns each
     * cell to the nearer cluster.  The approach mirrors using the per-region
     * coordinate system origin: radial distance would be measured from the local
     * cylinder axis, which is just the cluster centroid in Y,Z.
     *
     * <p>Only supported for N=2 coupled regions.  Returns {@code null} if the
     * Y range is too small to distinguish two cylinders (single-cylinder mesh) or
     * if any other failure occurs.
     *
     * @param regions  sorted list of coupled jellyRoll regions
     * @param merged   merged CellMapper whose yCentroids() reflects the T-table rows
     * @return regionIdx array (length = merged.nCells()), or {@code null} on failure
     */
    private static int[] computeRegionIndicesFromCentroids(Simulation sim,
            List<Region> regions, CellMapper merged) {
        if (regions.size() != 2) {
            sim.println("[ECM-EW] computeRegionIndicesFromCentroids: only N=2 supported; skipping.");
            return null;
        }
        double[] ys = merged.yCentroids();
        if (ys == null || ys.length == 0) return null;

        double yMin = Double.MAX_VALUE, yMax = -Double.MAX_VALUE;
        for (double y : ys) { if (y < yMin) yMin = y; if (y > yMax) yMax = y; }
        double yRange = yMax - yMin;

        // Require at least 20 mm Y separation to consider two distinct cylinders.
        if (yRange < 0.020) {
            sim.println(String.format(
                "[ECM-EW] computeRegionIndicesFromCentroids: Y range %.4f m < 0.020 m "
                + "— cells appear to be in a single cylinder. Skipping.", yRange));
            return null;
        }

        double yMid = (yMin + yMax) / 2.0;
        int[] ri = new int[ys.length];
        int cnt0 = 0;
        for (int i = 0; i < ys.length; i++) {
            ri[i] = (ys[i] < yMid) ? 0 : 1;
            if (ri[i] == 0) cnt0++;
        }
        int cnt1 = ys.length - cnt0;
        if (cnt0 == 0 || cnt1 == 0) {
            sim.println("[ECM-EW] computeRegionIndicesFromCentroids: degenerate split "
                + "(cnt0=" + cnt0 + " cnt1=" + cnt1 + "). Skipping.");
            return null;
        }
        sim.println(String.format(
            "[ECM-EW] computeRegionIndicesFromCentroids: Y range=%.4f m, midpoint=%.4f m "
            + "→ region 0: %d cells (Y<%.4f), region 1: %d cells (Y≥%.4f).",
            yRange, yMid, cnt0, yMid, cnt1, yMid));
        return ri;
    }

    private static List<String> getTablePartNames(Simulation sim, Table table) {
        try {
            Method getParts = table.getClass().getMethod("getParts");
            Object partsGroup = getParts.invoke(table);
            if (partsGroup == null) return null;

            // Find a no-arg method that returns an Iterable/Collection of parts
            Method getObjects = null;
            for (String mn : new String[]{"getObjects", "getEObjects", "getCollection"}) {
                try {
                    Method m = partsGroup.getClass().getMethod(mn);
                    Class<?> ret = m.getReturnType();
                    if (Iterable.class.isAssignableFrom(ret)
                            || java.util.Collection.class.isAssignableFrom(ret)) {
                        getObjects = m;
                        break;
                    }
                } catch (NoSuchMethodException ignored) {}
            }
            if (getObjects == null) {
                // Broad fallback: any no-arg method returning a Collection-like type
                for (Method m : partsGroup.getClass().getMethods()) {
                    if (m.getParameterCount() == 0) {
                        Class<?> ret = m.getReturnType();
                        if (Iterable.class.isAssignableFrom(ret)
                                || java.util.Collection.class.isAssignableFrom(ret)) {
                            getObjects = m;
                            break;
                        }
                    }
                }
            }
            if (getObjects == null) {
                sim.println("[ECM-EW] getTablePartNames: no Iterable/Collection getter found on "
                    + partsGroup.getClass().getSimpleName());
                return null;
            }

            Object col = getObjects.invoke(partsGroup);
            if (!(col instanceof Iterable)) return null;

            List<String> names = new ArrayList<>();
            for (Object part : (Iterable<?>) col) {
                try {
                    Method getPN = part.getClass().getMethod("getPresentationName");
                    names.add((String) getPN.invoke(part));
                } catch (Exception ignored) {
                    names.add(part.toString());
                }
            }
            return names.isEmpty() ? null : names;

        } catch (Exception e) {
            sim.println("[ECM-EW] getTablePartNames: reflection failed (" + e.getMessage() + ")");
            return null;
        }
    }

    // =========================================================================
    // CellMapper — per-cell data extraction from STAR-CCM+ FvRepresentation
    // =========================================================================

    /**
     * Enumerates all cells in the coupled region and caches their IDs and
     * centroids.  On each timestep, getTemperatures() pulls the current cell
     * temperatures from the solver.
     *
     * <p>STAR-CCM+ API notes (18.06):
     * <ul>
     *   <li>{@code FvRepresentation} (star.vis) holds the volume mesh data.</li>
     *   <li>{@code getInternalDataVector(FieldFunction, NamedObject)} returns a
     *       {@code DoubleVector} of per-cell scalar values for a region.</li>
     *   <li>For vector field functions (Centroid) the method returns a flat
     *       array of length 3*N ordered as [x0,y0,z0, x1,y1,z1, ...].</li>
     * </ul>
     */
    private static final class CellMapper {

        private final int[]    cellIds;
        private final double[] x;
        private final double[] y;
        private final double[] z;
        private final int      n;
        private final Region   region;  // cached for getTemperatures()

        /** Per-cell actual volume [m³] extracted from the solver; null if not yet extracted. */
        private double[] volumes;

        /**
         * Per-cell region index (0, 1, 2, …) for multi-region coupling.
         * Null for single-region or when region assignment is unknown.
         * Written to ecm_cell_map.csv as column {@code regionIdx}.
         */
        private int[] regionIndices;

        /**
         * Lazily-built mapping: tableRowIndex → CellMapper array index.
         * Null until first call to getTemperaturesFromXyzTable().
         * Built once by coordinate-hash matching.
         */
        private int[] tableRowToMapperIndex = null;

        /** Cached T-column index in the XYZ table. -1 until identified. */
        private int tColumnIndex = -1;

        /** Field function name for Temperature (differs between STAR physics models). */
        private static final String[] TEMP_FF_NAMES = {
            "Temperature", "StaticTemperature", "AbsoluteTemperature"
        };

        private CellMapper(int[] cellIds, double[] x, double[] y, double[] z,
                           double[] volumes, Region region) {
            this.cellIds = cellIds;
            this.x = x;
            this.y = y;
            this.z = z;
            this.volumes = volumes;
            this.n = cellIds.length;
            this.region = region;
        }

        int      nCells()        { return n; }
        int[]    cellIds()       { return cellIds; }
        double[] xCentroids()   { return x; }
        double[] yCentroids()   { return y; }
        double[] zCentroids()   { return z; }
        double[] volumes()       { return volumes; }
        int[]    regionIndices() { return regionIndices; }
        void setRegionIndices(int[] ri) { this.regionIndices = ri; }

        /**
         * Create a CellMapper for the given region.
         *
         * <p>Primary path: read {@code ecm_cell_map.csv} pre-generated by
         * {@code tools/cgns_cell_map.py} from the CGNS mesh export.  This avoids
         * any dependency on {@code FvRepresentation.getInternalDataVector()} which
         * was removed / renamed between STAR-CCM+ 18.06 and 21.02.
         *
         * <p>Fall-back: if the CSV is absent, attempt the legacy FvRepresentation
         * centroid-extraction path (works on STAR 18.06 and some later builds).
         */
        static CellMapper create(Simulation sim, Region region) throws Exception {
            // --- peek at XYZ T table to get live mesh cell count for staleness check ---
            int liveCount = -1;
            Table tTableRef = null;
            try {
                tTableRef = sim.getTableManager().getTable(T_TABLE_NAME);
                tTableRef.extract();
                liveCount = tTableRef.getRowCount();
                sim.println(String.format(
                    "[ECM-EW] XYZ T table '%s' has %d rows (current mesh).", T_TABLE_NAME, liveCount));
            } catch (Exception e) {
                sim.println("[ECM-EW] WARN: could not pre-extract T table for staleness check: "
                    + e.getMessage());
            }

            // --- primary: read pre-generated cell-map CSV ---
            if (CELL_MAP_CSV_FILE.exists()) {
                sim.println("[ECM-EW] Reading cell map from CSV: "
                    + CELL_MAP_CSV_FILE.getAbsolutePath());
                try {
                    CellMapper cm = createFromCsv(CELL_MAP_CSV_FILE, region);
                    sim.println(String.format(
                        "[ECM-EW] CellMapper loaded from CSV: %d cells", cm.nCells()));
                    if (liveCount > 0 && liveCount != cm.nCells()) {
                        sim.println(String.format(
                            "[ECM-EW] WARN: ecm_cell_map.csv has %d cells but current mesh has %d cells. "
                            + "Mesh was re-meshed — discarding stale CSV and rebuilding cell map.",
                            cm.nCells(), liveCount));
                        // fall through to T-table rebuild below
                    } else {
                        if (cm.volumes == null) {
                            cm.extractVolumes(sim);
                        } else {
                            // Check if volumes are uniform (written by a previous fallback).
                            // If so, attempt extraction again — the user may have since added
                            // the Cell Volume scalar to the XYZ T table.
                            boolean allEqual = true;
                            double v0 = cm.volumes[0];
                            for (double v : cm.volumes) {
                                if (Math.abs(v - v0) > v0 * 1e-9) { allEqual = false; break; }
                            }
                            if (allEqual) {
                                sim.println(String.format(
                                    "[ECM] INFO: ecm_cell_map.csv has uniform cell volumes "
                                    + "(%.4e m3 each — previous fallback). "
                                    + "Attempting to get actual mesh volumes...", v0));
                                cm.extractVolumes(sim);
                            }
                        }
                        return cm;
                    }
                } catch (IOException e) {
                    sim.println("[ECM-EW] WARN: CSV read failed (" + e.getMessage()
                        + "); rebuilding from mesh...");
                }
            } else {
                sim.println("[ECM-EW] Cell map CSV not found at: "
                    + CELL_MAP_CSV_FILE.getAbsolutePath());
            }

            // --- rebuild from XYZ T table (triggered by re-mesh or missing CSV) ---
            if (tTableRef != null && liveCount > 0) {
                sim.println(String.format(
                    "[ECM-EW] Rebuilding CellMapper from XYZ T table '%s' (%d cells)...",
                    T_TABLE_NAME, liveCount));
                CellMapper cm = createFromXyzTable(sim, tTableRef, region);
                cm.extractVolumes(sim);
                return cm;
                // throws on failure — caller aborts
            }

            // Both CSV and XYZ T table are unavailable — cannot proceed.
            throw new Exception(
                "Cannot build CellMapper: ecm_cell_map.csv is absent or unreadable AND "
                + "XYZ T table '" + T_TABLE_NAME + "' could not be extracted. "
                + "Ensure the table exists in the .sim file (Tools > Tables > XYZ Internal Table, "
                + "Parts=jellyRoll, Scalars=Temperature) and re-run.");
        }

        /**
         * Load a CellMapper from a pre-generated CSV file (cellId,x_m,y_m,z_m).
         * Produced by {@code tools/cgns_cell_map.py} from the CGNS mesh export.
         */
        static CellMapper createFromCsv(File csvFile, Region region) throws IOException {
            List<Integer> idList  = new ArrayList<>();
            List<Double>  xList   = new ArrayList<>();
            List<Double>  yList   = new ArrayList<>();
            List<Double>  zList       = new ArrayList<>();
            List<Double>  volList     = new ArrayList<>();
            List<Integer> riList      = new ArrayList<>();
            boolean hasVol = false;
            boolean hasRegionIdx = false;
            // detect columns from header
            int regionIdxCol = -1;
            try (BufferedReader br = new BufferedReader(new FileReader(csvFile))) {
                String header = br.readLine();
                if (header != null) {
                    String[] hCols = header.split(",", -1);
                    for (int ci = 0; ci < hCols.length; ci++) {
                        if (hCols[ci].trim().equalsIgnoreCase("regionIdx")) {
                            regionIdxCol = ci;
                            break;
                        }
                    }
                }
                String line;
                while ((line = br.readLine()) != null) {
                    line = line.trim();
                    if (line.isEmpty()) continue;
                    String[] p = line.split(",", -1);
                    idList.add(Integer.parseInt(p[0].trim()));
                    xList.add(Double.parseDouble(p[1].trim()));
                    yList.add(Double.parseDouble(p[2].trim()));
                    zList.add(Double.parseDouble(p[3].trim()));
                    if (p.length >= 5) {
                        double v = parseDouble(p[4]);
                        volList.add(v);
                        if (v > 0.0) hasVol = true;
                    } else {
                        volList.add(-1.0);
                    }
                    if (regionIdxCol >= 0 && regionIdxCol < p.length) {
                        try {
                            riList.add(Integer.parseInt(p[regionIdxCol].trim()));
                            hasRegionIdx = true;
                        } catch (NumberFormatException ignored) {
                            riList.add(0);
                        }
                    } else {
                        riList.add(0);
                    }
                }
            }
            int n = idList.size();
            int[]    ids  = new int[n];
            double[] x    = new double[n];
            double[] y    = new double[n];
            double[] z    = new double[n];
            int[]    ri   = hasRegionIdx ? new int[n] : null;
            double[] vols = hasVol ? new double[n] : null;
            double fallbackVol = JELLY_ROLL_VOLUME_M3 / Math.max(n, 1);
            for (int i = 0; i < n; i++) {
                ids[i] = idList.get(i);
                x[i]   = xList.get(i);
                y[i]   = yList.get(i);
                z[i]   = zList.get(i);
                if (vols != null) {
                    double v = volList.get(i);
                    vols[i] = (v > 0.0) ? v : fallbackVol;
                }
                if (ri != null) ri[i] = riList.get(i);
            }
            CellMapper cm = new CellMapper(ids, x, y, z, vols, region);
            if (ri != null) cm.regionIndices = ri;
            return cm;
        }

        /**
         * Build a CellMapper directly from an already-extracted XYZ Internal Table.
         * Used when ecm_cell_map.csv is absent or stale after re-meshing.
         * Cell IDs are assigned sequentially 0..N-1 matching table row order.
         */
        static CellMapper createFromXyzTable(Simulation sim, Table table, Region region)
                throws Exception {
            int rows = table.getRowCount();
            int cols = table.getColumnCount();
            if (rows == 0) throw new Exception("XYZ T table has 0 rows; cannot build CellMapper.");

            // Identify X, Y, Z columns by name
            int xCol = -1, yCol = -1, zCol = -1;
            for (int c = 0; c < cols; c++) {
                String lower = safeGetColumnName(table, c).toLowerCase().trim();
                if      (lower.equals("x") || lower.startsWith("x ") || lower.equals("x(m)")) xCol = c;
                else if (lower.equals("y") || lower.startsWith("y ") || lower.equals("y(m)")) yCol = c;
                else if (lower.equals("z") || lower.startsWith("z ") || lower.equals("z(m)")) zCol = c;
            }
            if (xCol < 0 || yCol < 0 || zCol < 0) {
                if (cols >= 3) {
                    xCol = 0; yCol = 1; zCol = 2;
                    sim.println("[ECM-EW] WARN: X/Y/Z columns not identified by name in T table; "
                        + "assuming col 0=X, 1=Y, 2=Z.");
                } else {
                    throw new Exception(
                        "Cannot identify X/Y/Z columns in T table (cols=" + cols + ").");
                }
            }

            double[] xData = getSeriesArray(sim, table, xCol);
            double[] yData = getSeriesArray(sim, table, yCol);
            double[] zData = getSeriesArray(sim, table, zCol);
            int[] ids = new int[rows];
            for (int i = 0; i < rows; i++) ids[i] = i;

            sim.println(String.format(
                "[ECM-EW] CellMapper rebuilt from XYZ T table: %d cells.", rows));
            return new CellMapper(ids, xData, yData, zData, null, region);
        }

        /**
         * Extract per-cell volumes and store in {@link #volumes}.
         *
         * <p>Three paths tried in order:
         * <ol>
         *   <li>XYZ Internal T table — the same proven path used for per-cell Temperature.
         *       Requires the user to add "Cell Volume" as a scalar to
         *       {@link #T_TABLE_NAME} in the STAR GUI (one-time setup):
         *       Tools ▶ Tables ▶ [T_TABLE_NAME] ▶ Scalars ▶ add "Cell Volume".</li>
         *   <li>FvRepresentation + "Cell Volume" field function.  Volume is geometric
         *       so this may succeed even when Temperature extraction via FvRep is broken.</li>
         *   <li>Uniform fallback: every cell gets {@code JELLY_ROLL_VOLUME_M3 / n}.
         *       Zone volumes are proportional to cell count, not geometric volume.</li>
         * </ol>
         *
         * <p>Called once from {@link #create} when the cell-map CSV does not already
         * carry a valid {@code volume_m3} column.
         */
        void extractVolumes(Simulation sim) {

            // ── Path A: XYZ Internal T table (proven to work in STAR-CCM+ 2602) ────────
            // User adds "Cell Volume" scalar to the T table once in the STAR GUI.
            try {
                Table tTable = sim.getTableManager().getTable(T_TABLE_NAME);
                int cols = tTable.getColumnCount();
                int volCol = -1;
                String volColName = "";
                for (int c = 0; c < cols; c++) {
                    String lower = safeGetColumnName(tTable, c).toLowerCase().trim();
                    if (lower.contains("volume") || lower.equals("vol")
                            || lower.contains("cellvol")) {
                        volCol = c;
                        volColName = safeGetColumnName(tTable, c);
                        break;
                    }
                }
                if (volCol >= 0) {
                    double[] vols = getSeriesArray(sim, tTable, volCol);
                    if (vols != null && vols.length == n) {
                        double minV = Double.MAX_VALUE, sumV = 0.0, maxV = -Double.MAX_VALUE;
                        boolean valid = true;
                        for (double v : vols) {
                            if (v <= 0.0) { valid = false; break; }
                            if (v < minV) minV = v;
                            if (v > maxV) maxV = v;
                            sumV += v;
                        }
                        if (valid) {
                            this.volumes = vols;
                            sim.println(String.format(
                                "[ECM] CellMapper volumes (T-table col '%s'): "
                                + "min=%.4e mean=%.4e max=%.4e sum=%.4e m3",
                                volColName, minV, sumV / n, maxV, sumV));
                            return;
                        }
                        sim.println("[ECM] WARN: T-table column '" + volColName
                            + "' has non-positive values; trying FvRep.");
                    }
                } else {
                    sim.println("[ECM] No volume column in T-table '" + T_TABLE_NAME + "'.");
                    sim.println("[ECM]   To enable accurate per-cell volumes: in STAR GUI, add");
                    sim.println("[ECM]   'Cell Volume' as a scalar to that XYZ Internal Table.");
                }
            } catch (Exception e) {
                sim.println("[ECM] T-table volume extraction failed: " + e.getMessage());
            }

            // ── Path B: FvRepresentation (may fail in STAR-CCM+ 2602) ─────────────────
            try {
                FvRepresentation fvRep = getFvRepresentation(sim);
                FieldFunction volFF = resolveFieldFunction(sim,
                    new String[]{"CellVolume", "Volume", "Cell Volume", "CellVol"});
                double[] vols = getRegionData(fvRep, volFF, region);
                if (vols != null && vols.length == n) {
                    double minV = Double.MAX_VALUE, sumV = 0.0, maxV = -Double.MAX_VALUE;
                    boolean valid = true;
                    for (double v : vols) {
                        if (v <= 0.0) { valid = false; break; }
                        if (v < minV) minV = v;
                        if (v > maxV) maxV = v;
                        sumV += v;
                    }
                    if (valid) {
                        this.volumes = vols;
                        sim.println(String.format(
                            "[ECM] CellMapper volumes (FvRep): "
                            + "min=%.4e mean=%.4e max=%.4e sum=%.4e m3",
                            minV, sumV / n, maxV, sumV));
                        return;
                    }
                    sim.println("[ECM] WARN: FvRep volume array has non-positive values.");
                }
            } catch (Exception e) {
                sim.println("[ECM] WARN: FvRep volume extraction failed: " + e.getMessage());
            }

            // ── Path C: no fallback — fail hard ──────────────────────────────────────
            // Uniform cell volumes are wrong for non-uniform meshes and corrupt the
            // per-zone heat balance in elementWise mode.  There is no safe default.
            throw new RuntimeException(
                "[ECM] FATAL: Cell volume extraction failed via both T-table column and FvRep. "
                + "Cannot proceed with unknown cell volumes — uniform fallback is not safe "
                + "for elementWise heat injection.\n"
                + "Fix: in the STAR-CCM+ GUI, add 'Cell Volume' as a scalar to the XYZ "
                + "Internal Table '" + T_TABLE_NAME + "' and re-run.");
        }

        /**
         * Collect per-cell temperatures for the coupled region.
         *
         * Dispatches based on {@code T_EXTRACTION_BACKEND}:
         * <ul>
         *   <li>"xyzTableInMemory" — extract from XYZ Internal Table in JVM memory. PRIMARY.</li>
         *   <li>"directFieldData"  — legacy FvRepresentation reflection (broken in 2602).</li>
         *   <li>"xyzTableCsvFallback" — export table to CSV per step, then parse. Slow fallback.</li>
         *   <li>"volumeAverageDebugOnly" — single volume-average T. Debug only.</li>
         * </ul>
         *
         * In elementWise mode, this method throws on any extraction failure.
         * The caller ({@code executeElementWise}) will abort the loop on exception.
         */
        double[] getTemperatures(Simulation sim) throws Exception {
            String backend = T_EXTRACTION_BACKEND;

            if ("xyzTableInMemory".equalsIgnoreCase(backend)) {
                return getTemperaturesFromXyzTable(sim);

            } else if ("directFieldData".equalsIgnoreCase(backend)) {
                // Legacy FvRepresentation path — confirmed broken in STAR-CCM+ 2602.
                // Kept so users can explicitly opt in for testing on older STAR versions.
                FvRepresentation fvRep = getFvRepresentation(sim);
                FieldFunction tempFF = resolveFieldFunction(sim, TEMP_FF_NAMES);
                try {
                    return getRegionData(fvRep, tempFF, region);
                } catch (Exception e) {
                    printFvRepDiagnostics(sim, fvRep);
                    throw new Exception(
                        "directFieldData extraction failed (expected on STAR 2602): "
                        + e.getMessage()
                        + ". Switch to ECM_T_EXTRACTION_BACKEND=xyzTableInMemory.");
                }

            } else if ("xyzTableCsvFallback".equalsIgnoreCase(backend)) {
                return getTemperaturesFromXyzTableCsv(sim);

            } else if ("volumeAverageDebugOnly".equalsIgnoreCase(backend)) {
                sim.println("[ECM-EW] WARN: volumeAverageDebugOnly backend: all cells get the same T.");
                FieldFunction tempFF = resolveFieldFunction(sim, TEMP_FF_NAMES);
                double tAvg = getVolumeAverageT(sim, region, tempFF);
                double[] temps = new double[n];
                Arrays.fill(temps, tAvg);
                return temps;

            } else {
                throw new Exception("Unknown ECM_T_EXTRACTION_BACKEND: '" + backend
                    + "'. Valid: xyzTableInMemory, directFieldData, xyzTableCsvFallback, volumeAverageDebugOnly");
            }
        }

        /**
         * Extract per-cell temperatures from an XYZ Internal Table in JVM memory.
         *
         * The table is looked up by name ({@code T_TABLE_NAME}), refreshed with
         * {@code extract()}, and then read row by row via {@code getValueAt()}.
         * On first call, column identification and coordinate-hash mapping are built
         * and cached so subsequent calls only read the T column.
         *
         * Throws {@code Exception} on any error so {@code executeElementWise()} can
         * abort rather than silently produce fake data.
         */
        private double[] getTemperaturesFromXyzTable(Simulation sim) throws Exception {
            // --- locate table ---
            Table table;
            try {
                table = sim.getTableManager().getTable(T_TABLE_NAME);
            } catch (Exception e) {
                throw new Exception(
                    "XYZ table '" + T_TABLE_NAME + "' not found. "
                    + "Create it in STAR-CCM+: Tools > Tables > New > XYZ Internal Table, "
                    + "Parts=jellyRoll, Scalars=Temperature, rename to '" + T_TABLE_NAME + "'. "
                    + "Original error: " + e.getMessage());
            }

            // --- extract() ---
            long t0 = System.nanoTime();
            table.extract();
            long extractMs = (System.nanoTime() - t0) / 1_000_000L;

            int rows = table.getRowCount();
            int cols = table.getColumnCount();

            if (rows == 0) {
                throw new Exception(
                    "XYZ table '" + T_TABLE_NAME + "' has 0 rows after extract(). "
                    + "Check that the table Parts is set to the jellyRoll region.");
            }
            if (rows != n) {
                throw new Exception(String.format(
                    "XYZ table row count mismatch: table=%d, CellMapper=%d. "
                    + "Table may be configured on wrong region.", rows, n));
            }

            // --- identify T column every call (not cached) ---
            // Re-identifying each step costs one O(cols) loop (~5–10 cols) — negligible.
            // Caching was fragile: if the user adds a column to the T-table mid-session
            // the cached index would silently read the wrong column for all subsequent steps.
            int newTCol = -1;
            for (int c = 0; c < cols; c++) {
                String colName = safeGetColumnName(table, c);
                String lower = colName.toLowerCase().trim();
                if (lower.contains("temp") || lower.equals("statictemperature")) {
                    newTCol = c;
                }
            }
            if (newTCol < 0) {
                throw new Exception(String.format(
                    "T column not found in XYZ table '%s' (cols=%d). "
                    + "Ensure the table includes a 'Temperature' or 'StaticTemperature' scalar. "
                    + "Column names seen: %s",
                    T_TABLE_NAME, cols, columnNames(table, cols)));
            }
            if (tColumnIndex != newTCol) {
                // Log on first identification or if column position shifted.
                sim.println(String.format(
                    "[ECM-EW] T column: col=%d \"%s\" (cols=%d)",
                    newTCol, safeGetColumnName(table, newTCol), cols));
            }
            tColumnIndex = newTCol;

            // --- build row→mapper mapping (cached after first call) ---
            if (tableRowToMapperIndex == null) {
                tableRowToMapperIndex = buildTableToMapperMapping(sim, table, rows, cols);
            }

            // --- read T column (fast path: getSeries bulk ~4 ms for 160k cells) ---
            long t1 = System.nanoTime();
            double[] rawTemps = getSeriesArray(sim, table, tColumnIndex);
            long readMs = (System.nanoTime() - t1) / 1_000_000L;

            if (rawTemps.length != rows) {
                throw new Exception(String.format(
                    "getSeries returned %d values but table has %d rows (T col=%d).",
                    rawTemps.length, rows, tColumnIndex));
            }

            double[] temps = new double[n];
            int nanCount = 0;
            for (int r = 0; r < rows; r++) {
                double t = rawTemps[r];
                if (!Double.isFinite(t)) {
                    nanCount++;
                }
                temps[tableRowToMapperIndex[r]] = t;
            }

            if (nanCount > 0) {
                throw new Exception(String.format(
                    "XYZ table T extraction: %d/%d NaN/Inf values. "
                    + "Ensure Temperature field is initialized before coupling starts.", nanCount, rows));
            }

            // --- statistics for diagnostics ---
            double tMin = Double.MAX_VALUE, tMax = -Double.MAX_VALUE, tSum = 0.0;
            for (double t : temps) {
                if (t < tMin) tMin = t;
                if (t > tMax) tMax = t;
                tSum += t;
            }
            double tMean = tSum / n;

            sim.println(String.format(
                "[ECM-EW] [xyzTableInMemory] extract_ms=%d read_ms=%d rows=%d tCol=%d "
                + "T_min=%.3f T_mean=%.3f T_max=%.3f NaN=%d",
                extractMs, readMs, rows, tColumnIndex, tMin, tMean, tMax, nanCount));

            return temps;
        }

        /**
         * Build mapping: tableRowIndex → CellMapper array index.
         *
         * Strategy: coordinate-hash matching with 0.01 mm tolerance.
         * If X/Y/Z columns are not identifiable, falls back to direct (identity) mapping
         * with a warning (valid only if table row order matches CellMapper order).
         */
        /**
         * Build the table-row → CellMapper-index mapping once at startup.
         *
         * Always performs a full coordinate scan using the relaxed 0.1 mm centroid hash.
         * No spot-check or identity shortcut — those shortcuts were the source of the
         * parallel-run mapping bug (table.extract() returns rows in partition order, not
         * serial/CSV order; identity is wrong in parallel).  The full scan runs once and
         * is cached; the ~10 ms cost is negligible.
         *
         * Hash tolerance 0.1 mm absorbs the ~10–50 µm difference between CGNS vertex-mean
         * centroids (ecm_cell_map.csv) and STAR volumetric centroids (XYZ T-table), while
         * still uniquely distinguishing cells on a ≥ 1 mm mesh.
         *
         * Fails hard (throws) if X/Y/Z columns cannot be identified, because proceeding
         * with a wrong mapping is worse than stopping with a clear error.
         */
        private int[] buildTableToMapperMapping(Simulation sim, Table table,
                int rows, int cols) throws Exception {

            // Identify X, Y, Z columns by name.
            int xCol = -1, yCol = -1, zCol = -1;
            for (int c = 0; c < cols; c++) {
                String lower = safeGetColumnName(table, c).toLowerCase().trim();
                if      (lower.equals("x") || lower.startsWith("x ") || lower.equals("x(m)")) xCol = c;
                else if (lower.equals("y") || lower.startsWith("y ") || lower.equals("y(m)")) yCol = c;
                else if (lower.equals("z") || lower.startsWith("z ") || lower.equals("z(m)")) zCol = c;
            }
            if (xCol < 0 || yCol < 0 || zCol < 0) {
                if (cols >= 3) {
                    xCol = 0; yCol = 1; zCol = 2;
                    sim.println("[ECM-EW] WARN: X/Y/Z columns not found by name; "
                        + "assuming col 0=X, 1=Y, 2=Z for mapping.");
                } else {
                    throw new Exception(
                        "Cannot build T-table row→mapper mapping: X/Y/Z columns not found "
                        + "and table has fewer than 3 columns (cols=" + cols + "). "
                        + "Ensure the XYZ T-table includes Position columns.");
                }
            }

            // Bulk-read table coordinates once (~4 ms each for 160k cells).
            double[] tableX = getSeriesArray(sim, table, xCol);
            double[] tableY = getSeriesArray(sim, table, yCol);
            double[] tableZ = getSeriesArray(sim, table, zCol);

            // Build relaxed centroid map from CellMapper (CSV/CGNS) coordinates.
            // 0.1 mm bins tolerate CGNS-vs-STAR centroid difference; unique for ≥1 mm cells.
            java.util.HashMap<Long, Integer> centMap = new java.util.HashMap<>(n * 2);
            for (int i = 0; i < n; i++) {
                centMap.put(centroidHashRelaxed(x[i], y[i], z[i]), i);
            }

            // Full scan: match every table row to its CellMapper index by coordinate.
            // Any miss is a hard error — on a correctly configured mesh every row must match.
            int[] mapping = new int[rows];
            int nMissed = 0;
            int firstMissedRow = -1;
            for (int r = 0; r < rows; r++) {
                Integer mi = centMap.get(centroidHashRelaxed(tableX[r], tableY[r], tableZ[r]));
                if (mi != null) {
                    mapping[r] = mi;
                } else {
                    nMissed++;
                    if (firstMissedRow < 0) firstMissedRow = r;
                }
            }

            if (nMissed > 0) {
                throw new Exception(String.format(
                    "T-table row→mapper mapping failed: %d/%d rows unmatched "
                    + "even at 0.1 mm coordinate tolerance (first miss: row %d, "
                    + "table coords=[%.6f, %.6f, %.6f]). "
                    + "Possible causes: wrong T-table region, mesh replaced without "
                    + "regenerating ecm_cell_map.csv, or centroids differ by > 0.1 mm. "
                    + "Delete ecm_cell_map.csv and re-run to trigger automatic rebuild.",
                    nMissed, rows, firstMissedRow,
                    firstMissedRow >= 0 ? tableX[firstMissedRow] : 0.0,
                    firstMissedRow >= 0 ? tableY[firstMissedRow] : 0.0,
                    firstMissedRow >= 0 ? tableZ[firstMissedRow] : 0.0));
            }

            sim.println(String.format(
                "[ECM-EW] T-table row→mapper mapping built: all %d rows matched "
                + "(0.1 mm coordinate scan). Correct for serial and parallel runs.",
                rows));
            return mapping;
        }

        /**
         * CSV-export fallback: export table to a temp file, parse it.
         * Slow (~10× in-memory), but avoids all in-memory API issues.
         * Only used with ECM_T_EXTRACTION_BACKEND=xyzTableCsvFallback.
         */
        private double[] getTemperaturesFromXyzTableCsv(Simulation sim) throws Exception {
            Table table;
            try {
                table = sim.getTableManager().getTable(T_TABLE_NAME);
            } catch (Exception e) {
                throw new Exception(
                    "XYZ table '" + T_TABLE_NAME + "' not found for CSV fallback: " + e.getMessage());
            }

            // Export to temp file
            java.io.File csvTmp = new java.io.File(
                PROJECT_ROOT, "ecm/ecm_T_table_tmp.csv");
            csvTmp.getParentFile().mkdirs();

            long t0 = System.nanoTime();
            table.extract();
            table.export(csvTmp);
            long exportMs = (System.nanoTime() - t0) / 1_000_000L;

            // Parse CSV: find T column header, read values
            java.util.List<Double> tempList = new java.util.ArrayList<>(n + 10);
            java.util.List<Double> xList = new java.util.ArrayList<>(n + 10);
            java.util.List<Double> yList = new java.util.ArrayList<>(n + 10);
            java.util.List<Double> zList = new java.util.ArrayList<>(n + 10);
            int csvXCol = -1, csvYCol = -1, csvZCol = -1, csvTCol = -1;

            try (java.io.BufferedReader br = new java.io.BufferedReader(
                    new java.io.FileReader(csvTmp))) {
                String headerLine = br.readLine();
                if (headerLine == null) {
                    throw new Exception("CSV export produced empty file: " + csvTmp.getAbsolutePath());
                }
                String[] headers = headerLine.split(",", -1);
                for (int c = 0; c < headers.length; c++) {
                    String lower = headers[c].trim().replaceAll("\"", "").toLowerCase();
                    if (lower.equals("x") || lower.startsWith("x ")) csvXCol = c;
                    else if (lower.equals("y") || lower.startsWith("y ")) csvYCol = c;
                    else if (lower.equals("z") || lower.startsWith("z ")) csvZCol = c;
                    else if (lower.contains("temp") || lower.equals("statictemperature")) csvTCol = c;
                }
                if (csvTCol < 0 && headers.length >= 4) csvTCol = headers.length - 1;
                if (csvTCol < 0) {
                    throw new Exception("T column not found in CSV headers: " + headerLine);
                }
                String line;
                while ((line = br.readLine()) != null) {
                    line = line.trim();
                    if (line.isEmpty()) continue;
                    String[] parts = line.split(",", -1);
                    if (parts.length <= csvTCol) continue;
                    double t = parseDouble(parts[csvTCol]);
                    tempList.add(t);
                    if (csvXCol >= 0 && csvXCol < parts.length) xList.add(parseDouble(parts[csvXCol]));
                    if (csvYCol >= 0 && csvYCol < parts.length) yList.add(parseDouble(parts[csvYCol]));
                    if (csvZCol >= 0 && csvZCol < parts.length) zList.add(parseDouble(parts[csvZCol]));
                }
            }
            long parseMs = (System.nanoTime() - t0) / 1_000_000L - exportMs;

            if (tempList.size() != n) {
                throw new Exception(String.format(
                    "CSV fallback row count mismatch: csv=%d, CellMapper=%d", tempList.size(), n));
            }

            // Build coordinate mapping if not yet cached and coordinates available
            double[] temps = new double[n];
            if (tableRowToMapperIndex == null && xList.size() == n) {
                java.util.HashMap<Long, Integer> centMap = new java.util.HashMap<>(n * 2);
                for (int i = 0; i < n; i++) {
                    centMap.put(centroidHash(x[i], y[i], z[i]), i);
                }
                tableRowToMapperIndex = new int[n];
                for (int r = 0; r < n; r++) {
                    Long key = centroidHash(xList.get(r), yList.get(r), zList.get(r));
                    Integer mi = centMap.get(key);
                    tableRowToMapperIndex[r] = (mi != null) ? mi : r;
                }
            }

            int nanCount = 0;
            for (int r = 0; r < n; r++) {
                double t = tempList.get(r);
                if (!Double.isFinite(t)) nanCount++;
                int mi = (tableRowToMapperIndex != null) ? tableRowToMapperIndex[r] : r;
                temps[mi] = t;
            }

            if (nanCount > 0) {
                throw new Exception("CSV fallback: " + nanCount + " NaN/Inf values.");
            }

            sim.println(String.format(
                "[ECM-EW] [xyzTableCsvFallback] export_ms=%d parse_ms=%d rows=%d",
                exportMs, parseMs, tempList.size()));
            return temps;
        }

        /** Stable spatial hash for centroid lookup. Resolution: 0.01 mm = 1e-5 m.
         *  Used for the identity spot-check (strict). */
        private static long centroidHash(double cx, double cy, double cz) {
            long ix = Math.round(cx / 1e-5);
            long iy = Math.round(cy / 1e-5);
            long iz = Math.round(cz / 1e-5);
            // Large co-prime multipliers to avoid collisions in cylindrical geometry
            return ix * 1_000_003_001L + iy * 1_000_003L + iz;
        }

        /**
         * Relaxed spatial hash for centroid lookup. Resolution: 0.1 mm = 1e-4 m.
         *
         * Used when matching CGNS vertex-mean centroids (from ecm_cell_map.csv) against
         * STAR volumetric centroids (from XYZ T-table).  The two centroid values for the
         * same physical cell can differ by up to ~50 µm; 0.1 mm bins absorb that
         * difference while still uniquely identifying cells on a ≥ 1 mm mesh.
         * Also required in parallel runs where the table row order differs from the
         * CSV cell order — the coordinate scan must successfully match every table row
         * to the correct CellMapper entry regardless of global ordering.
         */
        private static long centroidHashRelaxed(double cx, double cy, double cz) {
            long ix = Math.round(cx / 1e-4);
            long iy = Math.round(cy / 1e-4);
            long iz = Math.round(cz / 1e-4);
            return ix * 1_000_003_001L + iy * 1_000_003L + iz;
        }

        private static double safeToDouble(Object val) {
            if (val == null) return Double.NaN;
            if (val instanceof Number) return ((Number) val).doubleValue();
            try { return Double.parseDouble(val.toString().trim()); } catch (Exception e) { return Double.NaN; }
        }

        private static double parseDouble(String s) {
            try { return Double.parseDouble(s.trim().replaceAll("\"", "")); } catch (Exception e) { return Double.NaN; }
        }

        /**
         * Return all values for a table column as a double[] in one bulk API call.
         *
         * <p>Fast path (confirmed ~4 ms for 160k cells in STAR-CCM+ 2602):
         * <pre>
         *   table.getSeriesData().getSeries(int col) → double[]
         * </pre>
         *
         * <p>Falls back through:
         * <ol>
         *   <li>{@code getSeriesData().getSeriesObject(int)} → DoubleVector → double[]</li>
         *   <li>Any DoubleVector-returning method on SeriesData with an (int) parameter</li>
         *   <li>Slow per-row {@code table.getValueAt(row, col)} loop (O(N) API calls)</li>
         * </ol>
         *
         * @param sim  for warning messages if slow fallback is used (may be null)
         * @param table the STAR-CCM+ Table to read from
         * @param col   zero-based column index
         * @return array of length {@code table.getRowCount()} containing column values
         */
        private static double[] getSeriesArray(Simulation sim, Table table, int col) {
            try {
                Method getSD = table.getClass().getMethod("getSeriesData");
                Object sd = getSD.invoke(table);
                if (sd != null) {
                    // Path A: getSeries(int) → double[]  (confirmed fastest in STAR 2602)
                    try {
                        Method m = sd.getClass().getMethod("getSeries", int.class);
                        Object result = m.invoke(sd, col);
                        if (result instanceof double[]) return (double[]) result;
                    } catch (NoSuchMethodException ignored) {}

                    // Path B: getSeriesObject(int) → DoubleVector → toDoubleArray()
                    try {
                        Method m = sd.getClass().getMethod("getSeriesObject", int.class);
                        Object dv = m.invoke(sd, col);
                        if (dv != null) {
                            Method toArr = dv.getClass().getMethod("toDoubleArray");
                            return (double[]) toArr.invoke(dv);
                        }
                    } catch (NoSuchMethodException ignored) {}

                    // Path C: any DoubleVector-returning method with (int) param
                    for (Method m : sd.getClass().getMethods()) {
                        if (m.getReturnType().getSimpleName().equals("DoubleVector")) {
                            Class<?>[] params = m.getParameterTypes();
                            if (params.length == 1 && params[0] == int.class) {
                                try {
                                    Object dv = m.invoke(sd, col);
                                    if (dv != null) {
                                        return ((star.base.neo.DoubleVector) dv).toDoubleArray();
                                    }
                                } catch (Exception ignored) {}
                            }
                        }
                    }
                }
            } catch (Exception ignored) {}

            // Slow fallback: per-row getValueAt() — O(N) API calls, ~500 ms+ for 160k rows
            if (sim != null) {
                sim.println("[ECM-EW] WARN: getSeriesArray col=" + col
                    + ": getSeries fast path unavailable, using slow per-row getValueAt()."
                    + " Extraction will be slow. Check STAR-CCM+ API compatibility.");
            }
            int rows = table.getRowCount();
            double[] result = new double[rows];
            for (int r = 0; r < rows; r++) {
                result[r] = safeToDouble(safeGetValueAt(table, r, col));
            }
            return result;
        }

        private static String safeGetColumnName(Table table, int col) {
            try { return table.getColumnName(col); } catch (Exception e) { return "<col" + col + ">"; }
        }

        /** Returns a bracketed list of all column names — used in error messages. */
        private static String columnNames(Table table, int cols) {
            StringBuilder sb = new StringBuilder("[");
            for (int c = 0; c < cols; c++) {
                if (c > 0) sb.append(", ");
                sb.append('"').append(safeGetColumnName(table, c)).append('"');
            }
            return sb.append(']').toString();
        }

        private static Object safeGetValueAt(Table table, int row, int col) {
            try { return table.getValueAt(row, col); } catch (Exception e) { return Double.NaN; }
        }

        /** Print all methods on FvRepresentation whose name contains 'data', 'vector', or 'cell'. */
        private static void printFvRepDiagnostics(Simulation sim, FvRepresentation fvRep) {
            sim.println("[ECM-EW] FvRepresentation runtime class: "
                + fvRep.getClass().getName());
            StringBuilder sb = new StringBuilder(
                "[ECM-EW] Methods containing 'data', 'vector', or 'cell' (case-insensitive):\n");
            int count = 0;
            for (java.lang.reflect.Method m : fvRep.getClass().getMethods()) {
                String nm = m.getName().toLowerCase();
                if (nm.contains("data") || nm.contains("vector") || nm.contains("cell")) {
                    sb.append("    ").append(m.toGenericString()).append("\n");
                    count++;
                }
            }
            if (count == 0) {
                sb.append("    (none matching — printing all methods):\n");
                for (java.lang.reflect.Method m : fvRep.getClass().getMethods()) {
                    sb.append("    ").append(m.getName()).append(", ");
                }
            }
            sim.println(sb.toString());
        }

        /** Volume-average temperature of the region (fallback when per-cell API unavailable). */
        private static double getVolumeAverageT(Simulation sim, Region region,
                FieldFunction tempFF) {
            try {
                VolumeAverageReport r;
                try {
                    r = (VolumeAverageReport) sim.getReportManager()
                        .getReport("ECM_EW_T_avg_fallback");
                } catch (Exception ex) {
                    r = sim.getReportManager().createReport(VolumeAverageReport.class);
                    r.setPresentationName("ECM_EW_T_avg_fallback");
                    r.setFieldFunction(tempFF);
                    r.getParts().setObjects(region);
                }
                return r.getValue();
            } catch (Exception e) {
                sim.println("[ECM-EW] WARN: volume-average T also failed: " + e.getMessage()
                    + " — using 298.15 K");
                return 298.15;
            }
        }

        // ---- private helpers ------------------------------------------------

        private static FvRepresentation getFvRepresentation(Simulation sim) throws Exception {
            // Try the standard "Volume Mesh" representation name first.
            // Fall back to iterating representations if the name differs.
            try {
                return (FvRepresentation) sim.getRepresentationManager()
                    .getObject("Volume Mesh");
            } catch (Exception ignored) {}

            for (Object rep : sim.getRepresentationManager().getObjects()) {
                if (rep instanceof FvRepresentation) {
                    return (FvRepresentation) rep;
                }
            }
            throw new Exception("No FvRepresentation found in RepresentationManager.");
        }

        /**
         * Extract per-cell scalar data for a region from the FvRepresentation.
         *
         * Uses reflection to handle minor API differences across STAR-CCM+ versions:
         * - Primary:  fvRep.getInternalDataVector(FieldFunction, NamedObject)
         * - Fallback: fvRep.getInternalDataVector(FieldFunction, Collection)
         */
        private static double[] getRegionData(FvRepresentation fvRep,
                FieldFunction ff, NamedObject part) throws Exception {

            // Approach 1: getInternalDataVector(FieldFunction, NamedObject)
            try {
                Method m = fvRep.getClass().getMethod(
                    "getInternalDataVector",
                    FieldFunction.class,
                    NamedObject.class);
                Object vec = m.invoke(fvRep, ff, part);
                return toDoubleArray(vec);
            } catch (NoSuchMethodException ignored) {}

            // Approach 2: getInternalDataVector(FieldFunction, java.util.Collection)
            try {
                Method m = fvRep.getClass().getMethod(
                    "getInternalDataVector",
                    FieldFunction.class,
                    java.util.Collection.class);
                Object vec = m.invoke(fvRep, ff, java.util.Collections.singleton(part));
                return toDoubleArray(vec);
            } catch (NoSuchMethodException ignored) {}

            // Approach 3: getInternalDataVector(FieldFunction) → global array, slice by region
            try {
                Method m = fvRep.getClass().getMethod(
                    "getInternalDataVector",
                    FieldFunction.class);
                Object vec = m.invoke(fvRep, ff);
                double[] all = toDoubleArray(vec);
                return sliceByRegion(fvRep, all, (Region) part);
            } catch (Exception ignored) {}

            // Approaches 4–12: alternate method names used in STAR-CCM+ 19–21+
            // The method was renamed/moved between major releases; try all plausible variants.
            for (String mName : new String[]{
                    "getData", "getDataVector",
                    "getCellData", "getCellDataVector",
                    "getValues", "getFieldValues",
                    "getPrimitiveCellData", "getScalarData"}) {
                // (a) with (FieldFunction, NamedObject)
                try {
                    Method m = fvRep.getClass().getMethod(mName,
                        FieldFunction.class, NamedObject.class);
                    return toDoubleArray(m.invoke(fvRep, ff, part));
                } catch (Exception ignored) {}
                // (b) with (FieldFunction, Collection)
                try {
                    Method m = fvRep.getClass().getMethod(mName,
                        FieldFunction.class, java.util.Collection.class);
                    return toDoubleArray(m.invoke(fvRep, ff,
                        java.util.Collections.singleton(part)));
                } catch (Exception ignored) {}
                // (c) with (FieldFunction) → global, then slice
                try {
                    Method m = fvRep.getClass().getMethod(mName, FieldFunction.class);
                    double[] all = toDoubleArray(m.invoke(fvRep, ff));
                    return sliceByRegion(fvRep, all, (Region) part);
                } catch (Exception ignored) {}
            }

            throw new Exception("All data extraction approaches failed on "
                + fvRep.getClass().getName()
                + ". Check printFvRepDiagnostics output in STAR log.");
        }

        /**
         * Slice the global cell-data array to extract the cells belonging to a
         * specific region.  Used when only the global variant of
         * getInternalDataVector is available.
         */
        private static double[] sliceByRegion(FvRepresentation fvRep,
                double[] all, Region region) throws Exception {
            // Try getCellCount(Region) and getCellOffset(Region) via reflection
            int offset, count;
            try {
                Method mOff = fvRep.getClass().getMethod("getCellOffset", Region.class);
                Method mCnt = fvRep.getClass().getMethod("getCellCount",  Region.class);
                offset = ((Number) mOff.invoke(fvRep, region)).intValue();
                count  = ((Number) mCnt.invoke(fvRep, region)).intValue();
            } catch (NoSuchMethodException e) {
                // Alternative method names observed in some STAR versions
                try {
                    Method mOff = fvRep.getClass().getMethod("getRegionCellOffset", Region.class);
                    Method mCnt = fvRep.getClass().getMethod("getRegionCellCount",  Region.class);
                    offset = ((Number) mOff.invoke(fvRep, region)).intValue();
                    count  = ((Number) mCnt.invoke(fvRep, region)).intValue();
                } catch (NoSuchMethodException e2) {
                    throw new Exception(
                        "Cannot determine region cell offset/count via reflection. "
                        + "FvRepresentation API may differ from expected. "
                        + "Available methods: " + listMethods(fvRep));
                }
            }
            return Arrays.copyOfRange(all, offset, offset + count);
        }

        /** Convert a STAR DoubleVector (or plain double[]) to double[]. */
        private static double[] toDoubleArray(Object vec) throws Exception {
            if (vec instanceof double[]) {
                return (double[]) vec;
            }
            // star.base.neo.DoubleVector → toDoubleArray()
            try {
                Method m = vec.getClass().getMethod("toDoubleArray");
                return (double[]) m.invoke(vec);
            } catch (NoSuchMethodException ignored) {}
            // getArray()
            try {
                Method m = vec.getClass().getMethod("getArray");
                return (double[]) m.invoke(vec);
            } catch (NoSuchMethodException ignored) {}
            throw new Exception("Cannot convert " + vec.getClass().getName() + " to double[]");
        }

        /** Try several field function names in order; return the first that exists. */
        private static FieldFunction resolveFieldFunction(Simulation sim, String... names)
                throws Exception {
            for (String name : names) {
                try {
                    return sim.getFieldFunctionManager().getFunction(name);
                } catch (Exception ignored) {}
            }
            throw new Exception(
                "None of the requested field functions found: " + Arrays.toString(names));
        }

        /** List first 20 method names of an object (for diagnostics). */
        private static String listMethods(Object obj) {
            StringBuilder sb = new StringBuilder("[");
            int count = 0;
            for (java.lang.reflect.Method m : obj.getClass().getMethods()) {
                if (count++ < 20) sb.append(m.getName()).append(", ");
            }
            sb.append("...]");
            return sb.toString();
        }
    }

    // =========================================================================
    // HELPERS
    // =========================================================================

    private VolumeAverageReport getOrCreateTReport(Simulation sim, List<Region> regions) {
        VolumeAverageReport r;
        try {
            r = (VolumeAverageReport) sim.getReportManager().getReport("ECM_T_avg");
        } catch (Exception ignored) {
            r = sim.getReportManager().createReport(VolumeAverageReport.class);
            r.setPresentationName("ECM_T_avg");
            r.setFieldFunction(sim.getFieldFunctionManager().getFunction("Temperature"));
        }
        r.getParts().setObjects(regions);
        return r;
    }

    private ScalarGlobalParameter getOrCreateQParam(Simulation sim) {
        try {
            return (ScalarGlobalParameter) sim.get(GlobalParameterManager.class).getObject(QPARAM_NAME);
        } catch (Exception ignored) {
        }

        ScalarGlobalParameter p = (ScalarGlobalParameter) sim.get(GlobalParameterManager.class)
            .createGlobalParameter(ScalarGlobalParameter.class, QPARAM_NAME);
        p.getQuantity().setValue(0.0);
        return p;
    }

    private double getDeltaT(Simulation sim) {
        Double value;

        try {
            Object solver = sim.getSolverManager().getSolver(SpecifiedTimestepUnsteadySolver.class);
            value = tryGetQuantityValueFromNoArgMethod(solver, "getTimeStep");
            if (value != null && Double.isFinite(value) && value > 0.0) {
                return value;
            }
        } catch (Exception ignored) {
        }

        try {
            Object solver = sim.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
            value = tryGetQuantityValueFromNoArgMethod(solver, "getTimeStep");
            if (value != null && Double.isFinite(value) && value > 0.0) {
                return value;
            }
        } catch (Exception ignored) {
        }

        return FALLBACK_DELTA_T_S;
    }

    private double tryGetPhysicalTimeFromStar(Simulation sim) {
        Double value;

        value = tryInvokeDoubleNoArg(sim.getSimulationIterator(), "getCurrentTime");
        if (value != null && Double.isFinite(value)) {
            return value;
        }

        value = tryInvokeDoubleNoArg(sim.getSimulationIterator(), "getPhysicalTime");
        if (value != null && Double.isFinite(value)) {
            return value;
        }

        value = tryInvokeDoubleNoArg(sim.getSimulationIterator(), "getCurrentPhysicalTime");
        if (value != null && Double.isFinite(value)) {
            return value;
        }

        value = tryGetQuantityValueFromNoArgMethod(sim.getSimulationIterator(), "getCurrentTime");
        if (value != null && Double.isFinite(value)) {
            return value;
        }

        return Double.NaN;
    }

    private int runProcess(Simulation sim, PrintWriter debugLog) {
        return runProcess(sim, debugLog, null);
    }

    private int runProcess(Simulation sim, PrintWriter debugLog, Map<String, String> extraEnv) {
        List<String> command = new ArrayList<>();
        command.addAll(PYTHON_CMD);
        command.add(ECM_SCRIPT_PATH.getAbsolutePath());

        sim.println("[ECM] Launching: " + command);
        sim.println("[ECM] Process CWD: " + PROJECT_ROOT.getAbsolutePath());
        sim.println("[ECM] Process ECM_IN: " + ECM_IN_PATH.getAbsolutePath());
        sim.println("[ECM] Process ECM_OUT: " + ECM_OUT_PATH.getAbsolutePath());
        sim.println("[ECM] Process ECM_STATE_FILE: " + ECM_STATE_PATH.getAbsolutePath());
        sim.println("[ECM] Process ECM_CALL_EVERY_N_STEPS: " + ECM_CALL_EVERY_N_STEPS);

        if (debugLog != null) {
            debugLog.println("--- runProcess: " + command);
            debugLog.println("    CWD: " + PROJECT_ROOT.getAbsolutePath());
            debugLog.println("    ECM_IN: " + ECM_IN_PATH.getAbsolutePath());
            debugLog.println("    ECM_OUT: " + ECM_OUT_PATH.getAbsolutePath());
            debugLog.println("    ECM_STATE_FILE: " + ECM_STATE_PATH.getAbsolutePath());
            debugLog.println("    ECM_CALL_EVERY_N_STEPS: " + ECM_CALL_EVERY_N_STEPS);
            debugLog.flush();
        }

        try {
            ProcessBuilder pb = new ProcessBuilder(command);
            pb.directory(PROJECT_ROOT);
            pb.redirectErrorStream(true);

            Map<String, String> env = pb.environment();
            env.put("ECM_IN", ECM_IN_PATH.getAbsolutePath());
            env.put("ECM_OUT", ECM_OUT_PATH.getAbsolutePath());
            env.put("ECM_STATE_FILE", ECM_STATE_PATH.getAbsolutePath());
            env.put("ECM_CALL_EVERY_N_STEPS", Integer.toString(ECM_CALL_EVERY_N_STEPS));
            env.put("ECM_COUPLING_MODE", COUPLING_MODE);
            env.put("ECM_DISTRIBUTED_ELECTRICAL_MODE", ECM_DISTRIBUTED_ELECTRICAL_MODE);
            env.put("ECM_MAPPING_FILE", ECM_MAPPING_CSV_FILE.getAbsolutePath());
            env.put("ECM_N_ELEMENTS", Integer.toString(ECM_N_ELEMENTS));
            env.put("ECM_N_REGIONS", Integer.toString(nRegionsForEnv));
            if (REGION_GEOMETRY_CSV_FILE.exists()) {
                env.put("ECM_REGION_GEOMETRY_CSV", REGION_GEOMETRY_CSV_FILE.getAbsolutePath());
            }
            if (extraEnv != null) {
                env.putAll(extraEnv);
            }

            Process p = pb.start();

            final List<String> outputLines = new ArrayList<>();

            Thread drain = new Thread(() -> {
                try (BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        synchronized (outputLines) {
                            outputLines.add(line);
                        }
                    }
                } catch (IOException ignored) {
                }
            });

            drain.start();

            int exitCode = p.waitFor();
            drain.join(5000);

            synchronized (outputLines) {
                if (outputLines.isEmpty()) {
                    sim.println("[ECM-py] (no output)");
                }

                for (String line : outputLines) {
                    sim.println("[ECM-py] " + line);
                    if (debugLog != null) {
                        debugLog.println("[ECM-py] " + line);
                    }
                }
            }

            if (debugLog != null) {
                debugLog.println("    exitCode=" + exitCode);
                debugLog.flush();
            }

            sim.println("[ECM] Process exit code: " + exitCode);
            return exitCode;

        } catch (Exception e) {
            sim.println("[ECM] FATAL: Process launch failed: " + e.getMessage());
            if (debugLog != null) {
                debugLog.println("FATAL launch: " + e.getMessage());
                debugLog.flush();
            }
            return -1;
        }
    }

    private boolean waitForFile(File file, int timeoutSeconds) {
        long deadline = System.currentTimeMillis() + timeoutSeconds * 1000L;

        while (System.currentTimeMillis() < deadline) {
            if (file.exists() && file.length() > 0L) {
                return true;
            }

            try {
                Thread.sleep(50L);
            } catch (InterruptedException ignored) {
            }
        }

        return false;
    }

    private static void printDirectoryContents(Simulation sim, File dir) {
        if (dir == null) {
            sim.println("[ECM] Directory is null.");
            return;
        }

        sim.println("[ECM] Directory check: " + dir.getAbsolutePath()
            + " exists=" + dir.exists()
            + " isDirectory=" + dir.isDirectory());

        if (!dir.exists() || !dir.isDirectory()) {
            return;
        }

        String[] contents = dir.list();
        if (contents == null) {
            sim.println("[ECM] Directory contents: <unavailable>");
        } else {
            sim.println("[ECM] Directory contents: " + Arrays.toString(contents));
        }
    }

    private static String getEnvOrDefault(String name, String fallback) {
        // Priority 1: environment variable (set before STAR launches)
        String value = System.getenv(name);
        if (value != null && !value.trim().isEmpty()) {
            return value.trim();
        }
        // Priority 2: Java system property (set by EcmPrepAndRun before StarScript.play())
        value = System.getProperty(name);
        if (value != null && !value.trim().isEmpty()) {
            return value.trim();
        }
        return fallback;
    }

    private static List<String> resolvePythonCommand() {
        String envPython = getEnvOrDefault("ECM_PYTHON_EXE", "");
        if (!envPython.isEmpty()) {
            return new ArrayList<>(Arrays.asList(envPython));
        }

        String configuredPython = readConfigProperty("python");
        if (!configuredPython.isEmpty()) {
            return new ArrayList<>(Arrays.asList(configuredPython));
        }

        // Fallback order for Windows/macOS/Linux launcher conventions.
        return new ArrayList<>(Arrays.asList("py", "-3"));
    }

    private static String readConfigProperty(String key) {
        File config = new File(PROJECT_ROOT, "config.properties");
        if (!config.exists() || !config.isFile()) {
            return "";
        }

        Properties props = new Properties();
        try (FileInputStream fis = new FileInputStream(config)) {
            props.load(fis);
        } catch (IOException ignored) {
            return "";
        }

        String value = props.getProperty(key, "");
        if (value == null) {
            return "";
        }
        return value.trim();
    }

    private static double getDoubleEnvOrDefault(String name, double fallback) {
        String value = System.getenv(name);
        if (value == null) {
            return fallback;
        }

        value = value.trim();
        if (value.isEmpty()) {
            return fallback;
        }

        try {
            return Double.parseDouble(value);
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static boolean getBooleanEnvOrDefault(String name, boolean fallback) {
        String value = System.getenv(name);
        if (value == null) {
            return fallback;
        }

        value = value.trim();
        if (value.isEmpty()) {
            return fallback;
        }

        if (value.equalsIgnoreCase("1")
            || value.equalsIgnoreCase("true")
            || value.equalsIgnoreCase("yes")
            || value.equalsIgnoreCase("y")
            || value.equalsIgnoreCase("on")) {
            return true;
        }

        if (value.equalsIgnoreCase("0")
            || value.equalsIgnoreCase("false")
            || value.equalsIgnoreCase("no")
            || value.equalsIgnoreCase("n")
            || value.equalsIgnoreCase("off")) {
            return false;
        }

        return fallback;
    }

    private static Double tryInvokeDoubleNoArg(Object target, String methodName) {
        if (target == null || methodName == null || methodName.isEmpty()) {
            return null;
        }

        try {
            Method method = target.getClass().getMethod(methodName);
            Object result = method.invoke(target);

            if (result instanceof Number) {
                return ((Number) result).doubleValue();
            }
        } catch (Exception ignored) {
        }

        return null;
    }

    private static Double tryGetQuantityValueFromNoArgMethod(Object target, String methodName) {
        if (target == null || methodName == null || methodName.isEmpty()) {
            return null;
        }

        try {
            Method method = target.getClass().getMethod(methodName);
            Object result = method.invoke(target);

            if (result instanceof Number) {
                return ((Number) result).doubleValue();
            }

            if (result == null) {
                return null;
            }

            Double value;

            value = tryInvokeDoubleNoArg(result, "getValue");
            if (value != null) {
                return value;
            }

            value = tryInvokeDoubleNoArg(result, "getRawValue");
            if (value != null) {
                return value;
            }

            value = tryInvokeDoubleNoArg(result, "getSIValue");
            if (value != null) {
                return value;
            }

        } catch (Exception ignored) {
        }

        return null;
    }

    // =========================================================================
    // EcmBinaryIO — binary protocol implementation
    //
    // Header layout:
    //   char[8]  magic     "ECMIOv1\0"
    //   uint32   fileType  1=input, 2=output
    //   uint32   version   2
    //   uint32   N         number of coupled records
    //   double   time      simulation time [s]
    //   double   deltaT    timestep size [s]
    //   uint32   keyMode   0=globalCellId
    //   uint32   nInputs   1 (current_A)
    //   uint64   stepId    transaction ID
    //
    // Each record:
    //   int32    key       cell/element id
    //   double   value     T [K] for input, qVol [W/m3] for output
    //
    // All values are little-endian.
    // =========================================================================

    private static class EcmBinaryIO {

        private static final byte[] MAGIC = {'E', 'C', 'M', 'I', 'O', 'v', '1', '\0'};
        private static final int FILE_TYPE_IN = 1;
        private static final int FILE_TYPE_OUT = 2;
        private static final int VERSION = 2;
        private static final int KEY_MODE_GLOBAL = 0;

        private static final int HEADER_V1_BYTES = 44;
        private static final int STEP_ID_BYTES = 8;
        private static final int RECORD_BYTES = 12;

        static byte[] buildLumpedInputBytes(long stepId, double tEff, double time,
                double deltaT, double currentA, double qAhInit) throws IOException {

            byte[] nameCurrentA = "current_A".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            byte[] nameQAhInit  = "q_ah_init".getBytes(java.nio.charset.StandardCharsets.UTF_8);

            boolean sendQAhInit = !Double.isNaN(qAhInit);
            int nInputs = sendQAhInit ? 2 : 1;

            int inputBytes = 4 + nameCurrentA.length + 8;
            if (sendQAhInit) {
                inputBytes += 4 + nameQAhInit.length + 8;
            }

            int totalBytes = HEADER_V1_BYTES + STEP_ID_BYTES + inputBytes + RECORD_BYTES;
            ByteBuffer buf = ByteBuffer.allocate(totalBytes);
            buf.order(ByteOrder.LITTLE_ENDIAN);

            buf.put(MAGIC);
            buf.putInt(FILE_TYPE_IN);
            buf.putInt(VERSION);
            buf.putInt(1);
            buf.putDouble(time);
            buf.putDouble(deltaT);
            buf.putInt(KEY_MODE_GLOBAL);
            buf.putInt(nInputs);
            buf.putLong(stepId);
            buf.putInt(nameCurrentA.length);
            buf.put(nameCurrentA);
            buf.putDouble(currentA);
            if (sendQAhInit) {
                buf.putInt(nameQAhInit.length);
                buf.put(nameQAhInit);
                buf.putDouble(qAhInit);
            }
            buf.putInt(0);
            buf.putDouble(tEff);
            return buf.array();
        }

        static void writeLumpedInput(File path, long stepId, double tEff, double time,
                double deltaT, double currentA, double qAhInit) throws IOException {
            atomicWrite(path, buildLumpedInputBytes(stepId, tEff, time, deltaT, currentA, qAhInit));
        }

        static double readLumpedOutput(File path, long expectedStepId) throws IOException {
            return readLumpedOutputBytes(Files.readAllBytes(path.toPath()), expectedStepId);
        }

        static double readLumpedOutputBytes(byte[] data, long expectedStepId) throws IOException {
            if (data.length < HEADER_V1_BYTES + STEP_ID_BYTES + RECORD_BYTES) {
                throw new IOException("ECM output payload is too small: " + data.length + " bytes");
            }

            ByteBuffer buf = ByteBuffer.wrap(data);
            buf.order(ByteOrder.LITTLE_ENDIAN);

            byte[] magic = new byte[8];
            buf.get(magic);

            if (!Arrays.equals(magic, MAGIC)) {
                throw new IOException("Invalid ECM output magic.");
            }

            int fileType = buf.getInt();
            if (fileType != FILE_TYPE_OUT) {
                throw new IOException("Expected ECM output fileType=2, got " + fileType);
            }

            buf.getInt();
            int n = buf.getInt();
            buf.getDouble();
            buf.getDouble();
            buf.getInt();
            int nInputs = buf.getInt();
            long echoedStepId = buf.getLong();

            if (echoedStepId != expectedStepId) {
                return Double.NaN;
            }

            for (int i = 0; i < nInputs; i++) {
                if (buf.remaining() < 4) {
                    throw new IOException("Truncated ECM output while reading input name length.");
                }

                int nameLen = buf.getInt();

                if (nameLen < 0 || buf.remaining() < nameLen + 8) {
                    throw new IOException("Invalid or truncated ECM echoed input record.");
                }

                buf.position(buf.position() + nameLen + 8);
            }

            if (n < 1) {
                throw new IOException("ECM output contains no records.");
            }

            if (buf.remaining() < RECORD_BYTES) {
                throw new IOException("Truncated ECM output record.");
            }

            buf.getInt();
            return buf.getDouble();
        }

        // -----------------------------------------------------------------
        // Element-wise (distributed) I/O
        // -----------------------------------------------------------------

        /**
         * Write element-wise ECM input: N cell records (cellId, T_K).
         *
         * @param path      destination file
         * @param stepId    transaction ID; ECM echoes this back
         * @param cellIds   cell IDs (0-based sequential within region)
         * @param temps     per-cell temperature [K]
         * @param time      simulation time [s]
         * @param deltaT    timestep [s]
         * @param currentA  discharge current [A]
         */
        static void writeElementWiseInput(File path, long stepId,
                int[] cellIds, double[] temps,
                double time, double deltaT, double currentA) throws IOException {
            atomicWrite(path, buildElementWiseInputBytes(stepId, cellIds, temps, time, deltaT, currentA));
        }

        static byte[] buildElementWiseInputBytes(long stepId,
                int[] cellIds, double[] temps,
                double time, double deltaT, double currentA) throws IOException {

            if (cellIds.length != temps.length) {
                throw new IOException("cellIds/temps length mismatch: "
                    + cellIds.length + " vs " + temps.length);
            }

            int n = cellIds.length;
            byte[] nameCurrentA = "current_A".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            int inputBytesLen = 4 + nameCurrentA.length + 8;
            int totalBytes = HEADER_V1_BYTES + STEP_ID_BYTES + inputBytesLen + n * RECORD_BYTES;

            ByteBuffer buf = ByteBuffer.allocate(totalBytes);
            buf.order(ByteOrder.LITTLE_ENDIAN);

            buf.put(MAGIC);
            buf.putInt(FILE_TYPE_IN);
            buf.putInt(VERSION);
            buf.putInt(n);
            buf.putDouble(time);
            buf.putDouble(deltaT);
            buf.putInt(KEY_MODE_GLOBAL);
            buf.putInt(1);              // nInputs = 1 (current_A)
            buf.putLong(stepId);

            buf.putInt(nameCurrentA.length);
            buf.put(nameCurrentA);
            buf.putDouble(currentA);

            for (int i = 0; i < n; i++) {
                buf.putInt(cellIds[i]);
                buf.putDouble(temps[i]);
            }

            return buf.array();
        }

        /**
         * Read element-wise ECM output; return map of cellId → qVol [W/m³].
         * Returns null on stepId mismatch (caller keeps previous qVol).
         */
        static Map<Integer, Double> readElementWiseOutput(File path, long expectedStepId)
                throws IOException {
            return readElementWiseOutputBytes(Files.readAllBytes(path.toPath()), expectedStepId);
        }

        /**
         * Read element-wise ECM output from a byte array (used by persistent pipe mode).
         * Returns null on stepId mismatch (caller keeps previous qVol).
         */
        static Map<Integer, Double> readElementWiseOutputBytes(byte[] data, long expectedStepId)
                throws IOException {

            if (data.length < HEADER_V1_BYTES + STEP_ID_BYTES) {
                throw new IOException("ECM output too small: " + data.length + " bytes");
            }

            ByteBuffer buf = ByteBuffer.wrap(data);
            buf.order(ByteOrder.LITTLE_ENDIAN);

            byte[] magic = new byte[8];
            buf.get(magic);
            if (!Arrays.equals(magic, MAGIC)) {
                throw new IOException("Invalid ECM output magic.");
            }

            buf.getInt();               // fileType
            buf.getInt();               // version
            int n       = buf.getInt(); // number of cell records
            buf.getDouble();            // time
            buf.getDouble();            // deltaT
            buf.getInt();               // keyMode
            int nInputs = buf.getInt();
            long echoed = buf.getLong();

            if (echoed != expectedStepId) {
                return null;
            }

            for (int i = 0; i < nInputs; i++) {
                int nameLen = buf.getInt();
                buf.position(buf.position() + nameLen + 8);
            }

            Map<Integer, Double> result = new LinkedHashMap<>(n * 2);
            for (int i = 0; i < n; i++) {
                int    key  = buf.getInt();
                double qVol = buf.getDouble();
                result.put(key, qVol);
            }
            return result;
        }

        // -----------------------------------------------------------------

        static void writeBytes(File path, byte[] data) throws IOException {
            atomicWrite(path, data);
        }

        private static void atomicWrite(File path, byte[] data) throws IOException {
            File parent = path.getParentFile();
            if (parent != null && !parent.exists()) {
                if (!parent.mkdirs()) {
                    throw new IOException("Could not create parent directory: " + parent.getAbsolutePath());
                }
            }

            Path target = path.toPath();
            Path tmp = Paths.get(path.getAbsolutePath() + ".tmp");

            Files.write(tmp, data);
            Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        }
    }

    private static final class CurrentProfile {
        private final double[] times;
        private final double[] currents;
        private final double fallbackCurrentA;
        private final boolean usesSchedule;

        private CurrentProfile(double[] times, double[] currents, double fallbackCurrentA, boolean usesSchedule) {
            this.times = times;
            this.currents = currents;
            this.fallbackCurrentA = fallbackCurrentA;
            this.usesSchedule = usesSchedule;
        }

        static CurrentProfile load(Simulation sim, File csvFile, double fallbackCurrentA) {
            if (csvFile == null || !csvFile.exists() || !csvFile.isFile()) {
                sim.println(String.format(
                    "[ECM] Current schedule CSV not found. Falling back to constant CURRENT_A=%.9e A",
                    fallbackCurrentA));
                return new CurrentProfile(new double[0], new double[0], fallbackCurrentA, false);
            }

            List<Double> times = new ArrayList<>();
            List<Double> currents = new ArrayList<>();

            try (BufferedReader br = new BufferedReader(new FileReader(csvFile))) {
                String headerLine = br.readLine();
                if (headerLine == null) {
                    sim.println(String.format(
                        "[ECM] Current schedule CSV is empty. Falling back to constant CURRENT_A=%.9e A",
                        fallbackCurrentA));
                    return new CurrentProfile(new double[0], new double[0], fallbackCurrentA, false);
                }

                String[] headers = splitCsvLine(headerLine);
                int timeIdx = -1;
                int currentIdx = -1;
                for (int i = 0; i < headers.length; i++) {
                    String name = normalizeCsvToken(headers[i]);
                    if (name.equalsIgnoreCase("time")) {
                        timeIdx = i;
                    } else if (name.equalsIgnoreCase("current_A")) {
                        currentIdx = i;
                    }
                }

                if (timeIdx < 0 || currentIdx < 0) {
                    sim.println(String.format(
                        "[ECM] Current schedule CSV missing time/current_A headers. Falling back to constant CURRENT_A=%.9e A",
                        fallbackCurrentA));
                    return new CurrentProfile(new double[0], new double[0], fallbackCurrentA, false);
                }

                String line;
                while ((line = br.readLine()) != null) {
                    if (line.trim().isEmpty()) {
                        continue;
                    }
                    String[] parts = splitCsvLine(line);
                    if (parts.length <= Math.max(timeIdx, currentIdx)) {
                        continue;
                    }
                    String timeTok = normalizeCsvToken(parts[timeIdx]);
                    String currentTok = normalizeCsvToken(parts[currentIdx]);
                    if (timeTok.isEmpty() || currentTok.isEmpty()) {
                        continue;
                    }

                    double t = Double.parseDouble(timeTok);
                    double i = Double.parseDouble(currentTok);
                    if (!Double.isFinite(t) || !Double.isFinite(i)) {
                        continue;
                    }
                    times.add(t);
                    currents.add(i);
                }
            } catch (Exception e) {
                sim.println(String.format(
                    "[ECM] Failed to read current schedule CSV (%s). Falling back to constant CURRENT_A=%.9e A",
                    e.getMessage(), fallbackCurrentA));
                return new CurrentProfile(new double[0], new double[0], fallbackCurrentA, false);
            }

            if (times.isEmpty()) {
                sim.println(String.format(
                    "[ECM] Current schedule CSV has no usable rows. Falling back to constant CURRENT_A=%.9e A",
                    fallbackCurrentA));
                return new CurrentProfile(new double[0], new double[0], fallbackCurrentA, false);
            }

            double[] tArr = new double[times.size()];
            double[] iArr = new double[currents.size()];
            for (int i = 0; i < times.size(); i++) {
                tArr[i] = times.get(i);
                iArr[i] = currents.get(i);
            }

            sim.println(String.format(
                "[ECM] Loaded current schedule: %d rows, t=[%.9e .. %.9e] s, I=[%.9e .. %.9e] A",
                tArr.length, tArr[0], tArr[tArr.length - 1], min(iArr), max(iArr)));

            return new CurrentProfile(tArr, iArr, fallbackCurrentA, true);
        }

        double currentAt(double timeS) {
            if (!usesSchedule || times.length == 0) {
                return fallbackCurrentA;
            }

            if (timeS <= times[0]) {
                return currents[0];
            }
            if (timeS >= times[times.length - 1]) {
                return currents[currents.length - 1];
            }

            int lo = 0;
            int hi = times.length - 1;
            while (hi - lo > 1) {
                int mid = (lo + hi) >>> 1;
                if (times[mid] <= timeS) {
                    lo = mid;
                } else {
                    hi = mid;
                }
            }

            double t0 = times[lo];
            double t1 = times[hi];
            double i0 = currents[lo];
            double i1 = currents[hi];
            if (t1 <= t0) {
                return i1;
            }
            double alpha = (timeS - t0) / (t1 - t0);
            return i0 + alpha * (i1 - i0);
        }

        private static double min(double[] values) {
            double out = values[0];
            for (double value : values) {
                if (value < out) {
                    out = value;
                }
            }
            return out;
        }

        private static double max(double[] values) {
            double out = values[0];
            for (double value : values) {
                if (value > out) {
                    out = value;
                }
            }
            return out;
        }

        private static String normalizeCsvToken(String raw) {
            String token = raw == null ? "" : raw.trim();
            if (token.startsWith("\"") && token.endsWith("\"") && token.length() >= 2) {
                token = token.substring(1, token.length() - 1).trim();
            }
            return token;
        }

        private static String[] splitCsvLine(String line) {
            List<String> parts = new ArrayList<>();
            StringBuilder current = new StringBuilder();
            boolean inQuotes = false;
            for (int i = 0; i < line.length(); i++) {
                char ch = line.charAt(i);
                if (ch == '"') {
                    inQuotes = !inQuotes;
                    current.append(ch);
                } else if (ch == ',' && !inQuotes) {
                    parts.add(current.toString());
                    current.setLength(0);
                } else {
                    current.append(ch);
                }
            }
            parts.add(current.toString());
            return parts.toArray(new String[0]);
        }
    }

    private static final class PersistentEcmProcess {
        private final Process process;
        private final OutputStream stdin;
        private final InputStream stdout;
        private final BufferedReader mergedLogReader;
        private final Thread mergedLogThread;

        private PersistentEcmProcess(
                Process process,
                OutputStream stdin,
                InputStream stdout,
                BufferedReader mergedLogReader,
                Thread mergedLogThread) {
            this.process = process;
            this.stdin = stdin;
            this.stdout = stdout;
            this.mergedLogReader = mergedLogReader;
            this.mergedLogThread = mergedLogThread;
        }

        static PersistentEcmProcess start(Simulation sim, PrintWriter debugLog) {
            List<String> command = new ArrayList<>();
            command.addAll(PYTHON_CMD);
            command.add(ECM_SCRIPT_PATH.getAbsolutePath());
            command.add("--pipe-binary");

            sim.println("[ECM] Starting resident ECM process: " + command);
            sim.println("[ECM] Resident ECM_CALL_EVERY_N_STEPS: " + ECM_CALL_EVERY_N_STEPS);
            if (debugLog != null) {
                debugLog.println("--- startResidentProcess: " + command);
                debugLog.println("    ECM_CALL_EVERY_N_STEPS: " + ECM_CALL_EVERY_N_STEPS);
                debugLog.flush();
            }

            try {
                ProcessBuilder pb = new ProcessBuilder(command);
                pb.directory(PROJECT_ROOT);

                Map<String, String> env = pb.environment();
                env.put("ECM_STATE_FILE", ECM_STATE_PATH.getAbsolutePath());
                env.put("ECM_CALL_EVERY_N_STEPS", Integer.toString(ECM_CALL_EVERY_N_STEPS));
                env.put("ECM_DISTRIBUTED_ELECTRICAL_MODE", ECM_DISTRIBUTED_ELECTRICAL_MODE);
                env.put("ECM_MAPPING_FILE", ECM_MAPPING_CSV_FILE.getAbsolutePath());
                env.put("ECM_N_ELEMENTS", Integer.toString(ECM_N_ELEMENTS));
                env.put("ECM_N_REGIONS", Integer.toString(nRegionsForEnv));
                if (REGION_GEOMETRY_CSV_FILE.exists()) {
                    env.put("ECM_REGION_GEOMETRY_CSV", REGION_GEOMETRY_CSV_FILE.getAbsolutePath());
                }

                Process process = pb.start();
                BufferedReader stderrReader = new BufferedReader(new InputStreamReader(process.getErrorStream()));
                Thread stderrThread = new Thread(() -> {
                    try {
                        String line;
                        while ((line = stderrReader.readLine()) != null) {
                            sim.println("[ECM-py] " + line);
                            if (debugLog != null) {
                                debugLog.println("[ECM-py] " + line);
                                debugLog.flush();
                            }
                        }
                    } catch (IOException ignored) {
                    }
                });
                stderrThread.setDaemon(true);
                stderrThread.start();

                return new PersistentEcmProcess(
                    process,
                    process.getOutputStream(),
                    process.getInputStream(),
                    stderrReader,
                    stderrThread
                );
            } catch (IOException e) {
                sim.println("[ECM] WARN: could not start resident ECM process: " + e.getMessage());
                if (debugLog != null) {
                    debugLog.println("WARN resident start: " + e.getMessage());
                    debugLog.flush();
                }
                return null;
            }
        }

        double exchange(Simulation sim, byte[] inputBytes, long expectedStepId, PrintWriter debugLog)
                throws IOException {
            if (!process.isAlive()) {
                throw new IOException("resident ECM process is not alive");
            }

            ByteBuffer sizeBuf = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN);
            sizeBuf.putLong(inputBytes.length);
            stdin.write(sizeBuf.array());
            stdin.write(inputBytes);
            stdin.flush();

            byte[] responseSizeBytes = readFully(stdout, 8);
            long responseSizeLong = ByteBuffer.wrap(responseSizeBytes)
                .order(ByteOrder.LITTLE_ENDIAN)
                .getLong();
            if (responseSizeLong <= 0L || responseSizeLong > Integer.MAX_VALUE) {
                throw new IOException("invalid resident ECM response frame size: " + responseSizeLong);
            }

            byte[] responseBytes = readFully(stdout, (int) responseSizeLong);
            if (debugLog != null) {
                debugLog.println("[ECM] resident response bytes=" + responseBytes.length);
                debugLog.flush();
            }
            return EcmBinaryIO.readLumpedOutputBytes(responseBytes, expectedStepId);
        }

        Map<Integer, Double> exchangeElementWise(Simulation sim, byte[] inputBytes,
                long expectedStepId, PrintWriter debugLog) throws IOException {
            if (!process.isAlive()) {
                throw new IOException("resident ECM process is not alive");
            }

            ByteBuffer sizeBuf = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN);
            sizeBuf.putLong(inputBytes.length);
            stdin.write(sizeBuf.array());
            stdin.write(inputBytes);
            stdin.flush();

            byte[] responseSizeBytes = readFully(stdout, 8);
            long responseSizeLong = ByteBuffer.wrap(responseSizeBytes)
                .order(ByteOrder.LITTLE_ENDIAN)
                .getLong();
            if (responseSizeLong <= 0L || responseSizeLong > Integer.MAX_VALUE) {
                throw new IOException("invalid resident ECM response frame size: " + responseSizeLong);
            }

            byte[] responseBytes = readFully(stdout, (int) responseSizeLong);
            if (debugLog != null) {
                debugLog.println("[ECM] resident elementWise response bytes=" + responseBytes.length);
                debugLog.flush();
            }
            return EcmBinaryIO.readElementWiseOutputBytes(responseBytes, expectedStepId);
        }

        void close() {
            try {
                stdin.close();
            } catch (IOException ignored) {
            }
            try {
                stdout.close();
            } catch (IOException ignored) {
            }
            process.destroy();
            try {
                process.waitFor();
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            try {
                mergedLogReader.close();
            } catch (IOException ignored) {
            }
        }

        private static byte[] readFully(InputStream in, int size) throws IOException {
            byte[] data = new byte[size];
            int off = 0;
            while (off < size) {
                int n = in.read(data, off, size - off);
                if (n < 0) {
                    throw new EOFException("unexpected EOF from resident ECM process");
                }
                off += n;
            }
            return data;
        }
    }
}
