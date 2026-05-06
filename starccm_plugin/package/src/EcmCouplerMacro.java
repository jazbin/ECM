import star.common.*;
import star.base.neo.*;
import star.base.report.*;

import java.io.*;
import java.nio.file.*;

/**
 * EcmCouplerMacro — per-timestep ECM coupling for STAR-CCM+ 21.02.
 *
 * USAGE
 * -----
 * 1. Open your .sim file in STAR-CCM+.
 * 2. In the tree, manually create a ScalarGlobalParameter named "ecmQdot_W_m3"
 *    and set the jellyRoll region's energy source to reference it (see README).
 * 3. Tools > Macros > Run Macro > select EcmCouplerMacro.java (or the compiled jar).
 * 4. The macro drives the solver loop; DO NOT press the Run button separately.
 *
 * The macro writes ecm_in.bin, calls the external ECM (Python), reads ecm_out.bin,
 * applies under-relaxation, and updates ecmQdot_W_m3 before the next solver step.
 *
 * CONFIGURATION
 * -------------
 * Edit the constants in the CONFIG block below before running.
 *
 * BINARY PROTOCOL
 * ---------------
 * Matches docs/IO_FORMAT.md in the OpenFOAM ECM repository (v2 header, lumped mode).
 * The same Python ECM backend (ecm/ecm_coupler.py) works unchanged.
 */
public class EcmCouplerMacro extends StarMacro {

    // =========================================================================
    // CONFIG — edit these before running
    // =========================================================================

    /** Name of the coupled battery region in the STAR-CCM+ tree. */
    private static final String REGION_NAME    = "jellyRoll";

    /** Name of the ScalarGlobalParameter that drives the energy source. */
    private static final String QPARAM_NAME    = "ecmQdot_W_m3";

    /** Path to ecm_in.bin written by this macro (relative to working dir). */
    private static final String ECM_IN_FILE    = "ecm/ecm_in.bin";

    /** Path to ecm_out.bin written by the Python ECM (relative to working dir). */
    private static final String ECM_OUT_FILE   = "ecm/ecm_out.bin";

    /** Shell command to invoke the ECM.  Must block until ecm_out.bin is ready. */
    private static final String ECM_COMMAND    = "python3 ecm/ecm_coupler.py";

    /** Under-relaxation factor (0 < alpha <= 1).  Start conservative (0.5-0.8). */
    private static final double ALPHA          = 0.7;

    /** Number of timesteps to run.  Set to match your simulation end time / deltaT. */
    private static final int    N_STEPS        = 100;

    /** Max wall-clock seconds to wait for ecm_out.bin to appear. */
    private static final int    ECM_TIMEOUT_S  = 60;

    // =========================================================================
    // MAIN ENTRY POINT
    // =========================================================================

    @Override
    public void execute() {
        Simulation sim = getActiveSimulation();

        // --- locate coupled region ---
        Region region;
        try {
            region = sim.getRegionManager().getRegion(REGION_NAME);
        } catch (Exception e) {
            sim.println("[ECM] ERROR: region '" + REGION_NAME + "' not found. Aborting.");
            return;
        }
        sim.println("[ECM] Coupled region: " + region.getPresentationName());

        // --- create or reuse VolumeAverageReport for Temperature ---
        VolumeAverageReport tReport = getOrCreateTReport(sim, region);
        sim.println("[ECM] T report ready: " + tReport.getPresentationName());

        // --- locate the heat-source parameter ---
        ScalarGlobalParameter qParam = getOrCreateQParam(sim);
        sim.println("[ECM] Heat-source parameter: " + qParam.getPresentationName());

        // --- create ecm/ output directory if needed ---
        new File("ecm").mkdirs();

        // --- coupling loop ---
        SimulationIterator iter = sim.getSimulationIterator();
        double qVolPrev = 0.0;
        long   stepId   = 0;

        for (int step = 0; step < N_STEPS; step++) {

            // 1. Advance solver one timestep
            iter.step(1);
            stepId++;

            // 2. Read volume-average T and simulation time
            double tEff    = tReport.getValue();
            double simTime = getSimTime(sim);
            double deltaT  = getDeltaT(sim);

            sim.println(String.format("[ECM] step=%d  t=%.4f s  T_eff=%.4f K", step, simTime, tEff));

            // 3. Write ecm_in.bin
            try {
                EcmBinaryIO.writeLumpedInput(ECM_IN_FILE, stepId, tEff, simTime, deltaT);
            } catch (IOException e) {
                sim.println("[ECM] ERROR writing ecm_in.bin: " + e.getMessage());
                break;
            }

            // 4. Run ECM process (blocks until completion)
            int exitCode = runProcess(ECM_COMMAND);
            if (exitCode != 0) {
                sim.println("[ECM] WARNING: ECM exited with code " + exitCode + ". Keeping previous qVol.");
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            // 5. Wait for ecm_out.bin (should already exist after process exits)
            if (!waitForFile(ECM_OUT_FILE, ECM_TIMEOUT_S)) {
                sim.println("[ECM] WARNING: ecm_out.bin not found within timeout. Keeping previous qVol.");
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            // 6. Read qVol from ecm_out.bin
            double qVolNew;
            try {
                qVolNew = EcmBinaryIO.readLumpedOutput(ECM_OUT_FILE, stepId);
            } catch (IOException e) {
                sim.println("[ECM] ERROR reading ecm_out.bin: " + e.getMessage());
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            if (Double.isNaN(qVolNew)) {
                sim.println("[ECM] WARNING: stepId mismatch in ECM output. Keeping previous qVol.");
                qParam.getQuantity().setValue(qVolPrev);
                continue;
            }

            // 7. Under-relaxation
            double qVol = ALPHA * qVolNew + (1.0 - ALPHA) * qVolPrev;
            qVolPrev = qVol;

            sim.println(String.format("[ECM] qVol_new=%.2f  qVol_relaxed=%.2f  W/m3", qVolNew, qVol));

            // 8. Push to solver via global parameter
            qParam.getQuantity().setValue(qVol);
        }

        sim.println("[ECM] Coupling loop complete.");
    }

    // =========================================================================
    // HELPERS
    // =========================================================================

    private VolumeAverageReport getOrCreateTReport(Simulation sim, Region region) {
        // Reuse if already exists (e.g. macro re-run)
        try {
            return (VolumeAverageReport) sim.getReportManager().getReport("ECM_T_avg");
        } catch (Exception ignored) {}

        VolumeAverageReport r = sim.getReportManager().createReport(VolumeAverageReport.class);
        r.setPresentationName("ECM_T_avg");
        r.setFieldFunction(
            sim.getFieldFunctionManager().getFunction("Temperature"));
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
        // Works for transient (unsteady) simulations
        try {
            return sim.getSimulationIterator().getCurrentTimeLevel();
        } catch (Exception e) {
            return 0.0;
        }
    }

    private double getDeltaT(Simulation sim) {
        try {
            SpecifiedTimestepUnsteadySolver solver = (SpecifiedTimestepUnsteadySolver) sim.getSolverManager()
                .getSolver(ImplicitUnsteadySolver.class);
            return solver.getTimeStep().getValue();
        } catch (Exception e) {
            return 1.0; // fallback if not unsteady
        }
    }

    private int runProcess(String command) {
        try {
            ProcessBuilder pb = new ProcessBuilder(command.split("\\s+"));
            pb.redirectErrorStream(true);
            Process p = pb.start();

            // drain stdout so process doesn't block on full buffer
            new Thread(() -> {
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(p.getInputStream()))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        System.out.println("[ECM-py] " + line);
                    }
                } catch (IOException ignored) {}
            }).start();

            return p.waitFor();
        } catch (Exception e) {
            System.err.println("[ECM] Process launch failed: " + e.getMessage());
            return -1;
        }
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
