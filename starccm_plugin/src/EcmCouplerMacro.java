import star.common.*;
import star.base.neo.*;
import star.base.report.*;

import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * EcmCouplerMacro — per-timestep ECM coupling for STAR-CCM+.
 *
 * USAGE
 * -----
 * 1. Open your .sim file in STAR-CCM+.
 * 2. Configure the CONFIG block below (REGION_NAME, ECM_DIR, etc.).
 * 3. Tools > Macros > Run Macro > select EcmCouplerMacro.java (or the compiled jar).
 *    Do NOT press the Run button — this macro drives the solver loop.
 *
 * WHAT IT DOES (per step)
 * -----------------------
 * 1. Advances the solver one timestep
 * 2. Reads volume-average T from the jellyRoll region
 * 3. Interpolates current_A from a CSV file at the current sim time
 * 4. Writes ecm_in.bin (binary protocol, v2, nInputs=1 with current_A)
 * 5. Launches the Python ECM subprocess (blocks until done)
 * 6. Reads qVol [W/m3] from ecm_out.bin
 * 7. Applies under-relaxation; updates ScalarGlobalParameter ecmQdot_W_m3
 *
 * BINARY PROTOCOL
 * ---------------
 * Matches docs/IO_FORMAT.md (v2 header, lumped mode, nInputs=1).
 * The Python ECM (ecm/ecm_coupler.py) works unchanged.
 *
 * WINDOWS NOTE
 * ------------
 * ECM_COMMAND should be the path to the Python interpreter plus the script, e.g.:
 *   "C:\\Python311\\python.exe ecm\\ecm_coupler.py"
 * or if Python is on PATH:
 *   "python ecm/ecm_coupler.py"
 * The macro detects the OS and wraps the command appropriately.
 */
public class EcmCouplerMacro extends StarMacro {

    // =========================================================================
    // CONFIG — edit these before running
    // =========================================================================

    /** Name of the coupled battery region in the STAR-CCM+ tree. */
    private static final String REGION_NAME    = "jellyRoll";

    /** Name of the ScalarGlobalParameter that drives the volumetric heat source. */
    /** Active volume of the jellyRoll region [m3]. ECM returns Q_GEN [W] for lumped N=1;
     *  divide by this to get W/m3 for the STAR heat-source parameter. */
    private static final double CELL_VOLUME_M3 = 2.42e-5;  // 2170 cell: pi*(0.0105)^2*0.070

    private static final String QPARAM_NAME    = "ecmQdot_W_m3";

    /**
     * Directory (relative to STAR-CCM+ working dir, or absolute) that contains:
     *   ecm_coupler.py, ecm_io.py, ecm_step.py, params.csv,
     *   electrical_inputs_from_validation.csv
     * The ecm_in.bin / ecm_out.bin / ecm_state.json files are also written here.
     */
    private static final String ECM_DIR        = "ecm";

    /**
     * Python command to invoke the ECM.  On Windows use "python" (not "python3").
     * If Python is not on PATH, supply the full path, e.g.:
     *   "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python311\\python.exe"
     */
    private static final String PYTHON_EXE     = "python";

    /** Under-relaxation factor (0 < alpha <= 1).  Use 1.0 for no relaxation. */
    private static final double ALPHA          = 1.0;

    /** Number of timesteps to run. */
    private static final int    N_STEPS        = 36000;   // 3600 s at dt=0.1 s

    /** Seconds to wait for ecm_out.bin after the Python process exits. */
    private static final int    ECM_TIMEOUT_S  = 120;

    // =========================================================================
    // MAIN ENTRY POINT
    // =========================================================================

    @Override
    public void execute() {
        Simulation sim = getActiveSimulation();

        // locate coupled region
        Region region;
        try {
            region = sim.getRegionManager().getRegion(REGION_NAME);
        } catch (Exception e) {
            sim.println("[ECM] ERROR: region '" + REGION_NAME + "' not found. Aborting.");
            return;
        }
        sim.println("[ECM] Coupled region: " + region.getPresentationName());

        // T report and heat-source parameter
        VolumeAverageReport tReport = getOrCreateTReport(sim, region);
        ScalarGlobalParameter qParam = getOrCreateQParam(sim);

        // resolve ECM directory (absolute)
        File ecmDir = new File(ECM_DIR).isAbsolute()
            ? new File(ECM_DIR)
            : new File(System.getProperty("user.dir"), ECM_DIR);
        ecmDir.mkdirs();

        String ecmIn  = new File(ecmDir, "ecm_in.bin").getPath();
        String ecmOut = new File(ecmDir, "ecm_out.bin").getPath();
        String script = new File(ecmDir, "ecm_coupler.py").getPath();
        String csvPath = new File(ecmDir, "electrical_inputs_from_validation.csv").getPath();

        // load current profile CSV
        double[][] currentCsv = loadCurrentCsv(sim, csvPath);
        if (currentCsv == null) {
            sim.println("[ECM] ERROR: could not load current CSV from " + csvPath);
            return;
        }
        sim.println("[ECM] Loaded current profile: " + currentCsv[0].length + " rows, "
                  + "t_max=" + currentCsv[0][currentCsv[0].length-1] + " s");

        // ECM env vars
        Map<String,String> ecmEnv = new LinkedHashMap<>();
        ecmEnv.put("ECM_USE_REAL_STEP",   "1");
        ecmEnv.put("ECM_STATE_FILE",       new File(ecmDir, "ecm_state.json").getPath());
        ecmEnv.put("ECM_INTERP_MODE",      "linear");
        ecmEnv.put("ECM_LOG_EVERY_N_STEPS","10");

        // coupling loop
        SimulationIterator iter = sim.getSimulationIterator();
        double qVolPrev = 0.0;
        long   stepId   = 0;

        for (int step = 0; step < N_STEPS; step++) {

            // 1. advance solver
            iter.step(1);
            stepId++;

            double simTime = getSimTime(sim);
            double deltaT  = getDeltaT(sim);
            double tEff    = tReport.getValue();
            double currentA = interpolateCurrent(currentCsv, simTime);

            sim.println(String.format("[ECM] step=%d  t=%.4f s  T=%.4f K  I=%.4f A",
                                      step, simTime, tEff, currentA));

            // 2. write ecm_in.bin
            try {
                EcmBinaryIO.writeLumpedInput(ecmIn, stepId, tEff, simTime, deltaT, currentA);
            } catch (IOException e) {
                sim.println("[ECM] ERROR writing ecm_in.bin: " + e.getMessage());
                break;
            }

            // delete stale output before calling ECM
            new File(ecmOut).delete();

            // 3. run ECM subprocess
            int exitCode = runEcm(sim, PYTHON_EXE, script, ecmDir, ecmEnv);
            if (exitCode != 0) {
                sim.println("[ECM] WARNING: ECM exited with code " + exitCode
                          + ". Keeping previous qVol.");
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            // 4. wait for / read output
            if (!waitForFile(ecmOut, ECM_TIMEOUT_S)) {
                sim.println("[ECM] WARNING: ecm_out.bin not ready. Keeping previous qVol.");
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            double qVolNew;
            try {
                qVolNew = EcmBinaryIO.readLumpedOutput(ecmOut, stepId);
                if (!Double.isNaN(qVolNew)) { qVolNew = qVolNew / CELL_VOLUME_M3; } // W -> W/m3
            } catch (IOException e) {
                sim.println("[ECM] ERROR reading ecm_out.bin: " + e.getMessage());
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            if (Double.isNaN(qVolNew)) {
                sim.println("[ECM] WARNING: stepId mismatch. Keeping previous qVol.");
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            // 5. under-relaxation + apply
            double qVol = ALPHA * qVolNew + (1.0 - ALPHA) * qVolPrev;
            qVolPrev = qVol;

            sim.println(String.format("[ECM] qVol=%.2f W/m3  (raw=%.2f)", qVol, qVolNew));
            qParam.getQuantity().setValue(qVol);
        }

        sim.println("[ECM] Coupling loop complete.");
    }

    // =========================================================================
    // ECM PROCESS LAUNCH
    // =========================================================================

    /**
     * Launch the Python ECM subprocess.  On Windows, routes through cmd.exe /c
     * so that a bare "python" command resolves from PATH correctly.
     */
    private int runEcm(Simulation sim, String pythonExe, String scriptPath,
                       File workDir, Map<String,String> extraEnv) {
        try {
            List<String> cmd = new ArrayList<>();
            boolean isWindows = System.getProperty("os.name","").toLowerCase().contains("win");

            if (isWindows) {
                cmd.add("cmd.exe"); cmd.add("/c");
                cmd.add(pythonExe + " \"" + scriptPath + "\"");
            } else {
                cmd.add(pythonExe);
                cmd.add(scriptPath);
            }

            ProcessBuilder pb = new ProcessBuilder(cmd);
            pb.directory(workDir);
            pb.redirectErrorStream(true);

            // inherit current environment then add ECM-specific vars
            pb.environment().putAll(extraEnv);

            Process p = pb.start();

            // drain stdout / stderr (prevents buffer deadlock on Windows)
            final Simulation simRef = sim;
            new Thread(() -> {
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(p.getInputStream()))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        simRef.println("[ECM-py] " + line);
                    }
                } catch (IOException ignored) {}
            }).start();

            return p.waitFor();

        } catch (Exception e) {
            sim.println("[ECM] Process launch failed: " + e.getMessage());
            return -1;
        }
    }

    // =========================================================================
    // CURRENT CSV LOADING & INTERPOLATION
    // =========================================================================

    /**
     * Load time vs current_A from CSV.
     * Returns double[2][] where [0] = time array, [1] = current_A array.
     * Columns must be named "time" and "current_A" (unquoted).
     */
    private double[][] loadCurrentCsv(Simulation sim, String path) {
        List<Double> times    = new ArrayList<>();
        List<Double> currents = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(path))) {
            String header = br.readLine();
            if (header == null) return null;

            // find column indices
            String[] cols = header.split(",");
            int tIdx = -1, iIdx = -1;
            for (int c = 0; c < cols.length; c++) {
                String col = cols[c].trim().replace("\"","");
                if (col.equals("time"))      tIdx = c;
                if (col.equals("current_A")) iIdx = c;
            }
            if (tIdx < 0 || iIdx < 0) {
                sim.println("[ECM] CSV header missing 'time' or 'current_A' columns. "
                          + "Header: " + header);
                return null;
            }

            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                String[] parts = line.split(",");
                if (parts.length <= Math.max(tIdx, iIdx)) continue;
                String iStr = parts[iIdx].trim();
                if (iStr.isEmpty()) continue; // sparse CSV rows
                try {
                    times.add(Double.parseDouble(parts[tIdx].trim()));
                    currents.add(Double.parseDouble(iStr));
                } catch (NumberFormatException ignored) {}
            }
        } catch (IOException e) {
            sim.println("[ECM] ERROR reading current CSV: " + e.getMessage());
            return null;
        }

        if (times.isEmpty()) return null;

        double[] t = new double[times.size()];
        double[] I = new double[times.size()];
        for (int i = 0; i < t.length; i++) { t[i] = times.get(i); I[i] = currents.get(i); }
        return new double[][]{t, I};
    }

    /**
     * Linear interpolation of current at simTime.
     * Clamps to first/last value outside the CSV time range.
     */
    private double interpolateCurrent(double[][] csv, double simTime) {
        double[] t = csv[0];
        double[] I = csv[1];
        if (simTime <= t[0]) return I[0];
        if (simTime >= t[t.length-1]) return I[t.length-1];
        // binary search
        int lo = 0, hi = t.length - 1;
        while (hi - lo > 1) {
            int mid = (lo + hi) >>> 1;
            if (t[mid] <= simTime) lo = mid; else hi = mid;
        }
        double frac = (simTime - t[lo]) / (t[hi] - t[lo]);
        return I[lo] + frac * (I[hi] - I[lo]);
    }

    // =========================================================================
    // HELPERS
    // =========================================================================

    private VolumeAverageReport getOrCreateTReport(Simulation sim, Region region) {
        try { return (VolumeAverageReport) sim.getReportManager().getReport("ECM_T_avg"); }
        catch (Exception ignored) {}
        VolumeAverageReport r = sim.getReportManager().createReport(VolumeAverageReport.class);
        r.setPresentationName("ECM_T_avg");
        r.setFieldFunction(sim.getFieldFunctionManager().getFunction("Temperature"));
        r.getParts().setObjects(region);
        return r;
    }

    private ScalarGlobalParameter getOrCreateQParam(Simulation sim) {
        try {
            return (ScalarGlobalParameter) sim.get(GlobalParameterManager.class)
                   .getObject(QPARAM_NAME);
        } catch (Exception ignored) {}
        ScalarGlobalParameter p = (ScalarGlobalParameter) sim.get(GlobalParameterManager.class)
            .createGlobalParameter(ScalarGlobalParameter.class, QPARAM_NAME);
        p.getQuantity().setValue(0.0);
        return p;
    }

    private double getSimTime(Simulation sim) {
        try { return sim.getSimulationIterator().getCurrentTimeLevel(); }
        catch (Exception e) { return 0.0; }
    }

    private double getDeltaT(Simulation sim) {
        try {
            SpecifiedTimestepUnsteadySolver solver =
                (SpecifiedTimestepUnsteadySolver) sim.getSolverManager()
                .getSolver(ImplicitUnsteadySolver.class);
            return solver.getTimeStep().getValue();
        } catch (Exception e) { return 0.1; }
    }

    private boolean waitForFile(String path, int timeoutSeconds) {
        File f = new File(path);
        long deadline = System.currentTimeMillis() + timeoutSeconds * 1000L;
        while (System.currentTimeMillis() < deadline) {
            if (f.exists() && f.length() > 0) return true;
            try { Thread.sleep(50); } catch (InterruptedException ignored) {}
        }
        return false;
    }
}
