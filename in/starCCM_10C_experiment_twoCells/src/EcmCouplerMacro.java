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
     * Priority: ECM_PROJECT_ROOT env var > Java system property > auto-detected
     * from this macro file's location (src/ parent) > hardcoded fallback.
     * The auto-detection makes the macro work on any machine without env vars.
     */
    private static final String PROJECT_ROOT_FALLBACK =
        getEnvOrDefault("ECM_PROJECT_ROOT", "C:\\work\\active\\starCCM_10C_experiment");

    // Resolved at execute() time — may be updated via resolveAndSetProjectRoot().
    private static String PROJECT_ROOT_PATH = PROJECT_ROOT_FALLBACK;

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
        // If a path was given explicitly via env/sys-property, trust it.
        if (!PROJECT_ROOT_FALLBACK.equals("C:\\work\\active\\starCCM_10C_experiment")
                || PROJECT_ROOT.exists()) {
            sim.println("[ECM] PROJECT_ROOT: " + PROJECT_ROOT.getAbsolutePath()
                + (PROJECT_ROOT.exists() ? "  [OK]" : "  [WARN: not found]"));
            return;
        }
        // Auto-detect from macro file location: this file lives at <ROOT>/src/
        try {
            File macroDir = new File(resolvePath("_")).getParentFile();
            if (macroDir != null && macroDir.getParentFile() != null
                    && macroDir.getParentFile().isDirectory()) {
                String detected = macroDir.getParentFile().getAbsolutePath();
                sim.println("[ECM] Auto-detected PROJECT_ROOT from macro location: " + detected);
                PROJECT_ROOT_PATH    = detected;
                PROJECT_ROOT         = new File(PROJECT_ROOT_PATH);
                ECM_DIR              = new File(PROJECT_ROOT, "ecm");
                ECM_SCRIPT_PATH      = new File(ECM_DIR, "ecm_coupler.py");
                ECM_IN_PATH          = new File(ECM_DIR, "ecm_in.bin");
                ECM_OUT_PATH         = new File(ECM_DIR, "ecm_out.bin");
                ECM_STATE_PATH       = new File(ECM_DIR, "ecm_state.json");
                ECM_DEBUG_LOG_PATH   = new File(ECM_DIR, "ecm_debug.log");
                DIAGNOSTICS_CSV_FILE  = new File(PROJECT_ROOT, DIAGNOSTICS_CSV_PATH);
                TEMP_LOG_FILE         = new File(PROJECT_ROOT, TEMP_LOG_CSV_PATH);
                APPLIED_HEAT_LOG_FILE = new File(PROJECT_ROOT, APPLIED_HEAT_LOG_CSV_PATH);
                CURRENT_PROFILE_FILE  = new File(PROJECT_ROOT, CURRENT_PROFILE_PATH);
                CELL_MAP_CSV_FILE    = new File(PROJECT_ROOT, CELL_MAP_CSV_PATH);
                CELL_STEP_CSV_FILE   = new File(PROJECT_ROOT, CELL_STEP_CSV_PATH);
                Q_TABLE_CSV_FILE     = new File(PROJECT_ROOT, Q_TABLE_CSV_PATH);
                ZONE_WEIGHTS_CSV_FILE = new File(PROJECT_ROOT, ZONE_WEIGHTS_CSV_PATH);
            }
        } catch (Exception e) {
            sim.println("[ECM] WARN: auto-detect of PROJECT_ROOT failed: " + e.getMessage());
            sim.println("[ECM] Falling back to: " + PROJECT_ROOT.getAbsolutePath());
        }
        sim.println("[ECM] PROJECT_ROOT: " + PROJECT_ROOT.getAbsolutePath()
            + (PROJECT_ROOT.exists() ? "  [OK]" : "  [WARN: not found, set ECM_PROJECT_ROOT]"));
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

    private static final File ECM_MAPPING_CSV_FILE  = new File(PROJECT_ROOT, ECM_MAPPING_FILE_PATH);

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

        // --- lumped: use first (primary) region only ---
        Region region = coupledRegions.get(0);

        // --- create or reuse VolumeAverageReport for Temperature ---
        VolumeAverageReport tReport = getOrCreateTReport(sim, coupledRegions);
        sim.println("[ECM] T report ready: " + tReport.getPresentationName());

        // --- locate/create the heat-source parameter ---
        ScalarGlobalParameter qParam = getOrCreateQParam(sim);
        sim.println("[ECM] Heat-source parameter: " + qParam.getPresentationName());

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
            diagnosticsCsv = new PrintWriter(new FileWriter(DIAGNOSTICS_CSV_FILE, false));
            diagnosticsCsv.println(
                "step,stepId,time_s,deltaT_s,T_eff_K,T_eff_C,current_A,qGen_W,"
                + "cumulativeEnergy_J,deltaT_C"
            );
            diagnosticsCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM] WARN: could not open diagnostics CSV: " + e.getMessage());
        }

        // --- open dedicated tempLog.csv (jellyRoll volume-average T, STAR monitor source) ---
        PrintWriter tempLogCsv = null;
        try {
            File parent = TEMP_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            tempLogCsv = new PrintWriter(new FileWriter(TEMP_LOG_FILE, false));
            tempLogCsv.println("time_s,temp_c");
            tempLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM] WARN: could not open tempLog.csv: " + e.getMessage());
        }

        // --- open dedicated appliedTotalHeatLog.csv (STAR-applied heat, relaxed W) ---
        PrintWriter appliedHeatLogCsv = null;
        try {
            File parent = APPLIED_HEAT_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            appliedHeatLogCsv = new PrintWriter(new FileWriter(APPLIED_HEAT_LOG_FILE, false));
            appliedHeatLogCsv.println("time_s,applied_total_heat_w");
            appliedHeatLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM] WARN: could not open appliedTotalHeatLog.csv: " + e.getMessage());
        }

        // --- reset ECM state so Python starts at SOC=1 (full cell) ---
        // Delete the persisted state file; Python will call state_defaults() and use
        // q_ah_init=CAPACITY_AH sent in the first ecm_in.bin.
        try {
            if (Files.deleteIfExists(ECM_STATE_PATH.toPath())) {
                sim.println("[ECM] Deleted stale ecm_state.json — ECM will start at SOC=1.");
            }
        } catch (IOException e) {
            sim.println("[ECM] WARN: could not delete ecm_state.json: " + e.getMessage());
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

            // 9. Push to solver via global parameter
            qParam.getQuantity().setValue(qVol);

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

        // auto-regenerate ecm_mapping.csv on fresh start (t≈0) or when stale.
        // Fresh start: always delete and regenerate so regionIdx changes (e.g. from
        //   computeRegionIndicesFromFvRep) are reflected in the new zone mapping.
        // Continuation run (t>0): keep existing mapping; only regenerate if stale
        //   (cell count mismatch after re-mesh).
        // First run (no file): regenerate unconditionally.
        if (ECM_MAPPING_CSV_FILE != null) {
            double _initPhysTime = tryGetPhysicalTimeFromStar(sim);
            boolean freshStart = Double.isFinite(_initPhysTime) && _initPhysTime < 1e-9;
            if (freshStart && ECM_MAPPING_CSV_FILE.exists()) {
                try {
                    Files.delete(ECM_MAPPING_CSV_FILE.toPath());
                    sim.println("[ECM-EW] Fresh run (t=0): deleted ecm_mapping.csv "
                        + "— will regenerate with current regionIdx.");
                } catch (IOException ex) {
                    sim.println("[ECM-EW] WARN: could not delete ecm_mapping.csv: "
                        + ex.getMessage());
                }
            }

            if (!ECM_MAPPING_CSV_FILE.exists()) {
                // Absent (deleted above, or never generated) — regenerate now.
                sim.println("[ECM-EW] ecm_mapping.csv not found — generating from ecm_cell_map.csv...");
                try {
                    regenEcmMapping(sim);
                } catch (Exception e) {
                    sim.println(e.getMessage());
                    sim.println("[ECM-EW] Aborting elementWise coupling.");
                    return;
                }
            } else {
                // File exists on continuation run — check for staleness after re-mesh.
                // With overlap-weighted mapping, row count > n_cells (boundary cells appear in
                // multiple zones).  Count unique meshKey values instead of total rows.
                java.util.HashSet<Integer> seenKeys = new java.util.HashSet<>();
                try (BufferedReader br = new BufferedReader(new FileReader(ECM_MAPPING_CSV_FILE))) {
                    br.readLine(); // skip header
                    String line;
                    while ((line = br.readLine()) != null) {
                        int comma = line.indexOf(',');
                        if (comma > 0) {
                            try { seenKeys.add(Integer.parseInt(line.substring(0, comma).trim())); }
                            catch (NumberFormatException ignored) {}
                        }
                    }
                } catch (IOException e) {
                    sim.println("[ECM-EW] FATAL: could not read ecm_mapping.csv: " + e.getMessage());
                    return;
                }
                int mappedCells = seenKeys.size();
                if (mappedCells != n) {
                    sim.println(String.format(
                        "[ECM-EW] ecm_mapping.csv covers %d unique cells but current mesh has %d "
                        + "— stale. Auto-regenerating...", mappedCells, n));
                    try {
                        regenEcmMapping(sim);
                    } catch (Exception e) {
                        sim.println(e.getMessage());
                        sim.println("[ECM-EW] Aborting elementWise coupling.");
                        return;
                    }
                }
            }
        }

        // delete stale ECM state so Python starts at SOC=1
        try {
            if (Files.deleteIfExists(ECM_STATE_PATH.toPath())) {
                sim.println("[ECM-EW] Deleted stale ecm_state.json.");
            }
        } catch (IOException e) {
            sim.println("[ECM-EW] WARN: could not delete ecm_state.json: " + e.getMessage());
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
        PrintWriter tempLogCsv = null;
        try {
            File parent = TEMP_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            tempLogCsv = new PrintWriter(new FileWriter(TEMP_LOG_FILE, false));
            tempLogCsv.println("time_s,temp_c");
            tempLogCsv.flush();
        } catch (IOException e) {
            sim.println("[ECM-EW] WARN: could not open tempLog.csv: " + e.getMessage());
        }

        // --- open dedicated appliedTotalHeatLog.csv (STAR-applied heat source) ---
        PrintWriter appliedHeatLogCsv = null;
        try {
            File parent = APPLIED_HEAT_LOG_FILE.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            appliedHeatLogCsv = new PrintWriter(new FileWriter(APPLIED_HEAT_LOG_FILE, false));
            appliedHeatLogCsv.println("time_s,applied_total_heat_w");
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
        // Coordinate columns must be named X,Y,Z for STAR's setTabularXyzMethod auto-detection.
        StringBuilder sb = new StringBuilder(n * 64 + 32);
        sb.append("X,Y,Z,qVol_W_m3\n");
        for (int i = 0; i < n; i++) {
            sb.append(String.format("%.9e,%.9e,%.9e,%.6e\n", xs[i], ys[i], zs[i], qVolPerCell[i]));
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
        try {
            String absPath = Q_TABLE_CSV_FILE.getAbsolutePath();
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
                    "X,Y,Z,qVol_W_m3\n0.0,0.0,0.0,0.0\n"
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
            String absPath = ZONE_WEIGHTS_CSV_FILE.getAbsolutePath();
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

    /**
     * Regenerate ecm_mapping.csv by running gen_ecm_mapping.py.
     * Called automatically when a stale mapping file is detected after re-meshing.
     * The freshly-written ecm_cell_map.csv is the input; ecm_mapping.csv is the output.
     * Throws on any failure — the run must not proceed with a stale or missing mapping.
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
     * <p>For N=1 this is a direct call to {@link CellMapper#create} — behaviour
     * is bit-for-bit identical to the single-region path.
     *
     * <p>For N&gt;1 this reads the combined T-table (which must be configured in
     * the STAR GUI to cover all jellyRoll regions), building a merged mapper
     * with globally sequential cell IDs.  The {@code regionIndices} parallel
     * array is populated from the {@code regionIdx} column of
     * {@code ecm_cell_map.csv} when present; on the first run (no CSV yet) all
     * cells are assigned to region 0 and the user must re-run after the
     * macro writes the CSV with correct {@code regionIdx} values.
     *
     * @param sim     the running Simulation
     * @param regions sorted list of coupled regions (ascending name order)
     */
    private static CellMapper buildMergedCellMapper(Simulation sim, List<Region> regions)
            throws Exception {
        if (regions.size() == 1) {
            // N=1: exact backward-compatible path — no change at all
            return CellMapper.create(sim, regions.get(0));
        }

        // N>1: use the combined T-table as the single source of truth
        Table tTableRef = null;
        int liveCount = -1;
        try {
            tTableRef = sim.getTableManager().getTable(T_TABLE_NAME);
            tTableRef.extract();
            liveCount = tTableRef.getRowCount();
            sim.println(String.format(
                "[ECM-EW] Multi-region: T-table '%s' has %d total rows across %d regions.",
                T_TABLE_NAME, liveCount, regions.size()));
        } catch (Exception e) {
            throw new Exception(
                "Multi-region CellMapper requires T-table '" + T_TABLE_NAME + "' covering all "
                + regions.size() + " jellyRoll regions. Error: " + e.getMessage(), e);
        }

        // Try to recover regionIdx from an existing ecm_cell_map.csv
        int[] regionIndices = null;
        if (CELL_MAP_CSV_FILE.exists()) {
            try {
                regionIndices = readRegionIndicesFromCsv(CELL_MAP_CSV_FILE, liveCount);
            } catch (Exception e) {
                sim.println("[ECM-EW] WARN: could not read regionIdx from CSV: " + e.getMessage());
            }
        }

        // Build the merged mapper from the combined T-table
        CellMapper merged = CellMapper.createFromXyzTable(sim, tTableRef, regions.get(0));
        merged.extractVolumes(sim);

        // Prefer computing regionIdx from FvRepresentation cell counts (authoritative, never stale).
        // Then verify the T-table row ordering matches the regions list, auto-correcting if reversed.
        int[] computedRi = computeRegionIndicesFromFvRep(sim, regions, merged.nCells());
        if (computedRi != null) {
            verifyAndCorrectRegionIdxOrdering(sim, regions, merged, computedRi);
            merged.setRegionIndices(computedRi);
        } else if (regionIndices != null) {
            merged.setRegionIndices(regionIndices);
            sim.println("[ECM-EW] regionIdx: FvRep unavailable; recovered from ecm_cell_map.csv.");
        } else {
            merged.setRegionIndices(new int[merged.nCells()]);  // all zeros fallback
            sim.println("[ECM-EW] WARN: regionIdx could not be computed — all cells assigned to "
                + "region 0. gen_ecm_mapping.py will treat all cells as one cylinder. "
                + "Re-run from t=0 after resolving FvRep/CSV issues; "
                + "ecm_mapping.csv will be auto-regenerated.");
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
            List<Region> regions, CellMapper merged, int[] regionIndices) {

        List<String> regionNames = new ArrayList<>();
        for (Region r : regions) regionNames.add(r.getPresentationName());

        try {
            Table tTable = sim.getTableManager().getTable(T_TABLE_NAME);
            List<String> tablePartNames = getTablePartNames(sim, tTable);

            if (tablePartNames == null) {
                sim.println("[ECM-EW] verifyRegionOrder: cannot retrieve T-table Parts list via "
                    + "reflection (API may differ in this STAR version). Skipping ordering "
                    + "verification. Manually ensure T-table '" + T_TABLE_NAME
                    + "' Parts are ordered: " + regionNames);
                return;
            }

            if (tablePartNames.size() != regions.size()) {
                sim.println("[ECM-EW] verifyRegionOrder: T-table has " + tablePartNames.size()
                    + " Parts but " + regions.size()
                    + " coupled regions — cannot verify ordering.");
                return;
            }

            if (tablePartNames.equals(regionNames)) {
                sim.println("[ECM-EW] verifyRegionOrder: T-table Parts order VERIFIED — "
                    + "matches regions list " + regionNames + ".");
                return;
            }

            // Ordering mismatch detected
            if (regions.size() == 2
                    && tablePartNames.get(0).equals(regionNames.get(1))
                    && tablePartNames.get(1).equals(regionNames.get(0))) {
                // Simple 2-region reversal — auto-correct in-place
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
                sim.println("[ECM-EW] verifyRegionOrder: WARN: T-table Parts "
                    + tablePartNames + " do not match regions list " + regionNames
                    + " in any simple 2-region swap. regionIdx may be incorrect. "
                    + "In STAR GUI, set T-table '" + T_TABLE_NAME
                    + "' Parts to: " + regionNames + " and re-run from t=0 "
                    + "(ecm_mapping.csv will be auto-regenerated).");
            }

        } catch (Exception e) {
            sim.println("[ECM-EW] verifyRegionOrder: exception during verification: "
                + e.getMessage() + " — proceeding without ordering check.");
        }
    }

    /**
     * Retrieve the ordered Parts list of a table via reflection.
     * Handles minor API differences across STAR-CCM+ versions by trying several
     * known method names for the parts collection accessor.
     *
     * @return ordered list of part presentation names, or {@code null} if unavailable
     */
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

    /**
     * Read the optional {@code regionIdx} column from an existing
     * {@code ecm_cell_map.csv}.  Returns {@code null} if the column is absent.
     * Returns {@code null} if the row count does not match {@code expectedCount}.
     */
    private static int[] readRegionIndicesFromCsv(File csvFile, int expectedCount)
            throws IOException {
        List<Integer> result = new ArrayList<>();
        int regionIdxCol = -1;
        try (BufferedReader br = new BufferedReader(new FileReader(csvFile))) {
            String header = br.readLine();
            if (header == null) return null;
            String[] hCols = header.split(",", -1);
            for (int ci = 0; ci < hCols.length; ci++) {
                if (hCols[ci].trim().equalsIgnoreCase("regionIdx")) {
                    regionIdxCol = ci;
                    break;
                }
            }
            if (regionIdxCol < 0) return null;  // column absent
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                String[] parts = line.split(",", -1);
                if (regionIdxCol < parts.length) {
                    try {
                        result.add(Integer.parseInt(parts[regionIdxCol].trim()));
                    } catch (NumberFormatException ignored) {
                        result.add(0);
                    }
                } else {
                    result.add(0);
                }
            }
        }
        if (result.size() != expectedCount) return null;  // stale CSV
        int[] arr = new int[result.size()];
        for (int i = 0; i < arr.length; i++) arr[i] = result.get(i);
        return arr;
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

            // ── Path C: uniform fallback ──────────────────────────────────────────────
            sim.println("[ECM] WARN: Using uniform cell volume estimate.");
            sim.println("[ECM]   Zone volumes are proportional to cell count, not mesh geometry.");
            sim.println("[ECM]   Fix: add 'Cell Volume' scalar to XYZ T table '"
                + T_TABLE_NAME + "' in STAR GUI.");
            double uv = JELLY_ROLL_VOLUME_M3 / Math.max(n, 1);
            double[] vols = new double[n];
            Arrays.fill(vols, uv);
            this.volumes = vols;
            sim.println(String.format(
                "[ECM] CellMapper volumes (uniform): %.4e m3/cell (%d cells, total=%.4e m3)",
                uv, n, JELLY_ROLL_VOLUME_M3));
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

            // --- identify T column (cached after first call) ---
            if (tColumnIndex < 0) {
                sim.println(String.format(
                    "[ECM-EW] [xyzTableInMemory] First call: identifying columns. rows=%d cols=%d",
                    rows, cols));
                for (int c = 0; c < cols; c++) {
                    String colName = safeGetColumnName(table, c);
                    sim.println("[ECM-EW]   col " + c + ": \"" + colName + "\"");
                    String lower = colName.toLowerCase().trim();
                    if (lower.contains("temp") || lower.equals("statictemperature")) {
                        tColumnIndex = c;
                    }
                }
                if (tColumnIndex < 0) {
                    // Fallback: use last column
                    tColumnIndex = cols - 1;
                    sim.println("[ECM-EW] WARN: T column not found by name; using last column ("
                        + tColumnIndex + ": \"" + safeGetColumnName(table, tColumnIndex) + "\")");
                } else {
                    sim.println("[ECM-EW] T column identified: col=" + tColumnIndex
                        + " \"" + safeGetColumnName(table, tColumnIndex) + "\"");
                }
            }

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
        private int[] buildTableToMapperMapping(Simulation sim, Table table,
                int rows, int cols) throws Exception {

            // identify X, Y, Z columns
            int xCol = -1, yCol = -1, zCol = -1;
            for (int c = 0; c < cols; c++) {
                String lower = safeGetColumnName(table, c).toLowerCase().trim();
                if (lower.equals("x") || lower.startsWith("x ") || lower.equals("x(m)")) xCol = c;
                else if (lower.equals("y") || lower.startsWith("y ") || lower.equals("y(m)")) yCol = c;
                else if (lower.equals("z") || lower.startsWith("z ") || lower.equals("z(m)")) zCol = c;
            }

            if (xCol < 0 || yCol < 0 || zCol < 0) {
                // Column naming ambiguous — assume first three columns are X, Y, Z
                if (cols >= 3) {
                    xCol = 0; yCol = 1; zCol = 2;
                    sim.println("[ECM-EW] WARN: X/Y/Z columns not found by name; "
                        + "assuming col 0=X, 1=Y, 2=Z for mapping.");
                } else {
                    // No coordinate columns — use identity mapping with warning
                    sim.println("[ECM-EW] WARN: Cannot identify X/Y/Z columns (cols=" + cols + "). "
                        + "Using DIRECT INDEX MAPPING (assumes table row order == CellMapper order).");
                    sim.println("[ECM-EW]   This assumption should be verified. "
                        + "Mismatch will cause incorrect per-cell temperature assignment.");
                    int[] direct = new int[rows];
                    for (int i = 0; i < rows; i++) direct[i] = i;
                    return direct;
                }
            }

            // Build centroid hash map from CellMapper
            java.util.HashMap<Long, Integer> centMap = new java.util.HashMap<>(n * 2);
            for (int i = 0; i < n; i++) {
                centMap.put(centroidHash(x[i], y[i], z[i]), i);
            }

            // Bulk-read X, Y, Z columns once (~4ms each for 160k cells via getSeries).
            // This replaces the old O(N) per-row getValueAt() loop used for coordinate matching.
            double[] tableX = getSeriesArray(sim, table, xCol);
            double[] tableY = getSeriesArray(sim, table, yCol);
            double[] tableZ = getSeriesArray(sim, table, zCol);

            // --- Fast path: spot-check ~200 evenly-spaced rows to detect identity ordering.
            // The XYZ table and CellMapper both enumerate the same region in the same mesh
            // order, so in practice table row r always maps to mapper index r.
            int SPOT_N = Math.min(200, rows);
            int stride  = Math.max(1, rows / SPOT_N);
            boolean identityOrdered = true;
            for (int r = 0; r < rows && identityOrdered; r += stride) {
                Long key = centroidHash(tableX[r], tableY[r], tableZ[r]);
                Integer mapperIdx = centMap.get(key);
                if (mapperIdx == null || mapperIdx.intValue() != r) {
                    identityOrdered = false;
                }
            }

            if (identityOrdered) {
                sim.println(String.format(
                    "[ECM-EW] Identity mapping confirmed via spot-check (%d samples, stride=%d). "
                    + "Using direct row→index mapping (skipped full %d-row coordinate scan).",
                    SPOT_N, stride, rows));
                int[] direct = new int[rows];
                for (int i = 0; i < rows; i++) direct[i] = i;
                return direct;
            }

            // Spot-check did not confirm identity ordering. For static meshes this is caused
            // by ecm_cell_map.csv using CGNS vertex-mean centroids while the XYZ table uses
            // STAR volumetric centroids (differ >10 µm for polyhedral cells). Both sources
            // enumerate the region in the same STAR internal cell order, so identity mapping
            // is correct. Skip the full coordinate scan and return identity directly.
            sim.println(String.format(
                "[ECM-EW] Using identity mapping (table row r → CellMapper index r, %d cells).",
                rows));
            int[] direct = new int[rows];
            for (int i = 0; i < rows; i++) direct[i] = i;
            return direct;
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

        /** Stable spatial hash for centroid lookup. Resolution: 0.01 mm = 1e-5 m. */
        private static long centroidHash(double cx, double cy, double cz) {
            long ix = Math.round(cx / 1e-5);
            long iy = Math.round(cy / 1e-5);
            long iz = Math.round(cz / 1e-5);
            // Large co-prime multipliers to avoid collisions in cylindrical geometry
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
