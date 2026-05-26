# ECM Coupler for STAR-CCM+ — Full Setup Guide

This macro couples an external electrochemical battery model (ECM) to STAR-CCM+ at every
timestep. The macro drives the transient solver loop, extracts the volume-averaged cell
temperature, passes it to a Python ECM backend, and injects the returned volumetric heat
source back into the battery region — using the same validated binary protocol as the
OpenFOAM `ecmCoupler` functionObject.

**Validated against:** 18650 / 2170 NCA cell, 3600 s CCCV discharge profile.
**Temperature RMSE vs experiment:** < 0.33 °C.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Package layout](#2-package-layout)
3. [Simulation requirements](#3-simulation-requirements)
4. [First-time setup on Windows](#4-first-time-setup-on-windows)
5. [One-time wiring inside STAR-CCM+](#5-one-time-wiring-inside-star-ccm)
6. [Finding your region name](#6-finding-your-region-name)
7. [Configuring the macro](#7-configuring-the-macro)
8. [Setting up the current profile](#8-setting-up-the-current-profile)
9. [Running the coupled simulation](#9-running-the-coupled-simulation)
10. [What happens each timestep](#10-what-happens-each-timestep)
11. [Output and monitoring](#11-output-and-monitoring)
12. [Before re-running](#12-before-re-running)
13. [Troubleshooting](#13-troubleshooting)
14. [Rebuilding the macro JAR](#14-rebuilding-the-macro-jar)
15. [ECM parameters and chemistry](#15-ecm-parameters-and-chemistry)

---

## 1. Prerequisites

### STAR-CCM+

- Any recent version with Java macro support (tested on 21.02.008)
- Your simulation must be **transient (unsteady)** — the macro reads `deltaT` from the
  `ImplicitUnsteadySolver`. Steady-state simulations are not supported.
- The battery region must have an **energy equation** enabled (i.e. the physics continuum
  must include a heat transfer model so that a Volumetric Heat Source can be applied).

### Python

- Python 3.9 or newer
- Must be reachable from the command line. On Windows, install from https://python.org
  and tick **"Add Python to PATH"** during installation.
- Required packages:
  ```
  pip install numpy pandas
  ```
  Running `setup.bat` installs these automatically.

---

## 2. Package layout

```
ecm_coupler_starccm/
├── EcmCouplerMacro.jar     Compiled macro — load this in STAR-CCM+
├── setup.bat               One-time Windows setup script
├── README.md               This file
├── ecm/
│   ├── ecm_coupler.py              ECM orchestrator (called once per timestep)
│   ├── ecm_io.py                   Binary protocol reader/writer
│   ├── mock_ecm_backend.py         Stateful electrochemical mock model
│   ├── mock_model.py               Core voltage/heat compute kernel
│   ├── params.csv                  ECM lookup table (NCA cell chemistry)
│   └── electrical_inputs_from_validation.csv   Current profile [A vs t]
└── src/
    ├── EcmCouplerMacro.java        Macro source (edit CONFIG block here)
    └── EcmBinaryIO.java            Binary protocol Java implementation
```

> **Critical:** The `ecm/` folder must live in the **same directory as your `.sim` file**.
> STAR-CCM+ sets its working directory to the folder containing the `.sim` file, so all
> relative paths in the macro (`ecm/ecm_in.bin`, `ecm/ecm_coupler.py`, etc.) resolve from
> there. See [Section 9](#9-running-the-coupled-simulation) for the required folder layout.

---

## 3. Simulation requirements

Before loading the macro, verify the following in your `.sim` file:

| Requirement | Where to check in STAR-CCM+ |
|---|---|
| Transient (unsteady) solver enabled | Solvers → Implicit Unsteady |
| Energy equation active for the battery region | Physics → Continua → *your continuum* → Models → Energy |
| A single battery region whose volume-averaged temperature represents the cell | Regions tree |
| Time step (`deltaT`) is already set | Solvers → Implicit Unsteady → Time-Step |

The macro does **not** create or modify physics models, meshes, or solver settings.
It only reads temperature and injects a heat source — everything else must already be set up.

---

## 4. First-time setup on Windows

1. Place the entire package folder (containing `EcmCouplerMacro.jar`, `setup.bat`,
   `README.md`, and the `ecm/` subfolder) next to your `.sim` file.

2. Open a command prompt in that folder and run:
   ```
   setup.bat
   ```
   The script will:
   - Locate Python on your `PATH`
   - Install `numpy` and `pandas` via pip
   - Write a `config.properties` file recording the Python executable path
   - Run a quick smoke test of `ecm_coupler.py`

3. If setup reports `[OK]` for all steps, proceed to Section 5.

4. If Python is not found, install it from https://python.org (tick "Add to PATH"),
   then re-run `setup.bat`.

---

## 5. One-time wiring inside STAR-CCM+

This wiring step connects the ECM heat value to the battery region's energy equation.
**You only do this once** — it is saved inside the `.sim` file and persists across runs.

### Step A — Create a Global Parameter to carry the heat value

The macro updates a STAR-CCM+ Scalar Global Parameter each timestep. The parameter acts
as a live variable that the field function (created in Step B) reads from.

1. In STAR-CCM+, go to **Tools → Parameters** (or right-click "Parameters" in the tree
   and choose **New Parameter → Scalar**).
2. Set the following:
   - **Name:** `ecmQdot_W_m3`  ← exact spelling, case-sensitive
   - **Value:** `0`
   - **Dimensions / Units:** `W/m³`  (choose from the units dropdown)
3. Click OK. The parameter now appears under **Parameters** in the tree.

> If you use a different name here you must also update `QPARAM_NAME` in the macro
> (see [Section 7](#7-configuring-the-macro)).

### Step B — Create a Field Function that references the parameter

The Volumetric Heat Source on a region accepts a Field Function, not a Global Parameter
directly. This one-line field function bridges them.

1. Go to **Tools → Field Functions → New Scalar Field Function**.
2. Set:
   - **Name:** `ecmQdot_field`  (you choose — it just needs to be memorable)
   - **Function Definition:** `$ecmQdot_W_m3`
     - The `$` prefix tells STAR-CCM+ to look up the Global Parameter named `ecmQdot_W_m3`.
3. Click OK.

### Step C — Apply the field function as the Volumetric Heat Source

This tells STAR-CCM+ to use the ECM heat value when solving the energy equation in the
battery region.

1. In the tree, expand **Regions → [your battery region name]**.
2. Click **Physics Values**.
3. Find **Volumetric Heat Source** in the right panel.
4. Click the small dropdown/icon next to the method and change it from `Constant` to
   **Field Function**.
5. Click the field function selector and choose `ecmQdot_field` (the one you created
   in Step B).
6. Click OK / Apply.

Now save the `.sim` file. Steps A–C never need to be repeated for this file.

---

## 6. Finding your region name

The macro must know the exact name of your battery region as it appears in the STAR-CCM+
tree. The name is **case-sensitive**.

To find it:
- In STAR-CCM+, expand the **Regions** node in the simulation tree.
- The name shown there is exactly what you must put in `REGION_NAME`.

Example tree entries and the corresponding `REGION_NAME` value:

| What you see in the tree | What to set in REGION_NAME |
|---|---|
| `jellyRoll` | `"jellyRoll"` |
| `Battery Region` | `"Battery Region"` |
| `ActiveMaterial_1` | `"ActiveMaterial_1"` |

Once you have the name, edit `REGION_NAME` in `src/EcmCouplerMacro.java` and rebuild
the JAR (see [Section 14](#14-rebuilding-the-macro-jar)). If your region is already named
`jellyRoll`, no rebuild is needed.

---

## 7. Configuring the macro

Open `src/EcmCouplerMacro.java` in any text editor. All user-configurable settings are
collected in the CONFIG block near the top of the file (lines 35–59). Edit these before
rebuilding the JAR.

```java
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

/** Shell command to invoke the ECM. Must block until ecm_out.bin is ready. */
private static final String ECM_COMMAND    = "python3 ecm/ecm_coupler.py";

/** Under-relaxation factor (0 < alpha <= 1). Start conservative (0.5–0.8). */
private static final double ALPHA          = 0.7;

/** Number of timesteps to run. Set to match your end time / deltaT. */
private static final int    N_STEPS        = 100;

/** Max wall-clock seconds to wait for ecm_out.bin to appear. */
private static final int    ECM_TIMEOUT_S  = 60;
```

### Explanation of each constant

**`REGION_NAME`**
The battery region whose volume-averaged temperature is passed to the ECM and whose
Volumetric Heat Source is driven by the ECM output. Must match the STAR tree exactly
(case-sensitive). See [Section 6](#6-finding-your-region-name).

**`QPARAM_NAME`**
The name of the Scalar Global Parameter you created in Step A of
[Section 5](#5-one-time-wiring-inside-star-ccm). Default is `ecmQdot_W_m3`. Change
only if you chose a different name in Step A.

**`ECM_IN_FILE` / `ECM_OUT_FILE`**
Paths to the binary exchange files, relative to the working directory (which is the
folder containing the `.sim` file). Default `ecm/ecm_in.bin` and `ecm/ecm_out.bin`
match the layout of the `ecm/` subfolder. Only change these if you restructure the
folder layout.

**`ECM_COMMAND`**
The shell command used to launch the Python ECM backend each timestep. The macro
splits this string on spaces and passes it to `ProcessBuilder`. Options:

| Scenario | Value to use |
|---|---|
| `python3` is on your PATH (Linux/macOS/WSL) | `"python3 ecm/ecm_coupler.py"` |
| `python` is on your PATH (Windows, standard install) | `"python ecm/ecm_coupler.py"` |
| Python is NOT on your PATH | `"C:/Python312/python.exe ecm/ecm_coupler.py"` |
| Using `py` launcher (Windows) | `"py ecm/ecm_coupler.py"` |

Run `setup.bat` to have the correct command detected automatically and written to
`config.properties`. You still need to copy that value into the Java constant manually
and rebuild.

**`ALPHA`**
Under-relaxation factor applied to the heat source between timesteps.
- `ALPHA = 1.0` — no relaxation; ECM output applied directly.
- `ALPHA = 0.7` — default; blends 70 % new value + 30 % previous value.
- `ALPHA = 0.5` — more conservative; useful if temperatures oscillate.

Formula: `qVol_applied = ALPHA * qVol_new + (1 - ALPHA) * qVol_prev`

**`N_STEPS`**
Total number of transient timesteps the macro will run. Calculate this as:
```
N_STEPS = end_time_seconds / delta_T_seconds
```
Example: 3600 s simulation with 0.1 s timestep → `N_STEPS = 36000`.

**`ECM_TIMEOUT_S`**
How many seconds the macro will wait for `ecm_out.bin` to appear after launching
the Python process. Default 60 s is generous. If the ECM crashes silently, the
macro will wait this long before skipping the step and keeping the previous heat value.
Reduce to 10–15 s for faster failure detection during debugging.

---

## 8. Setting up the current profile

The ECM needs to know the applied current at each timestep to compute heat generation.
The current profile is read from:

```
ecm/electrical_inputs_from_validation.csv
```

### File format

The file must have exactly two columns with **unquoted** headers:

```
time,current_A
0,0
11,0
100,5.05
200,5.05
3600,0
```

- `time` — simulation time in seconds
- `current_A` — applied current in amperes (positive = discharge)
- The ECM linearly interpolates between rows
- The file must cover the full simulation time range (0 to end)

### Common mistakes

| Mistake | Result | Fix |
|---|---|---|
| Quoted headers: `"time","current_A"` | Current always reads as 0 | Remove the quotes — headers must be bare text |
| File not found | ECM exits with error; heat stays 0 | Ensure the file is inside `ecm/` next to the `.sim` file |
| Only one row | Interpolation fails | Add at least two rows |
| Time range shorter than simulation | Current clamps to last value | Extend the file to cover full `end_time` |

### Using your own current profile

Replace the contents of `ecm/electrical_inputs_from_validation.csv` with your own
charge or discharge profile. The two-column format is the only requirement.

---

## 9. Running the coupled simulation

### Required folder layout

Before running, your simulation directory must look like this:

```
MySimulations/
├── MyBattery.sim              ← your STAR-CCM+ simulation file
├── EcmCouplerMacro.jar        ← compiled macro
└── ecm/
    ├── ecm_coupler.py
    ├── ecm_io.py
    ├── mock_ecm_backend.py
    ├── mock_model.py
    ├── params.csv
    └── electrical_inputs_from_validation.csv
```

The `ecm/` folder must be a sibling of the `.sim` file — not inside a subfolder,
not on a different drive. STAR-CCM+ will set its working directory to the folder
containing the `.sim` file, and the macro uses relative paths from there.

### Steps to run

1. Open `MyBattery.sim` in STAR-CCM+.
2. Verify the one-time wiring from Section 5 is present (check **Parameters** →
   `ecmQdot_W_m3` exists, and the battery region's Volumetric Heat Source references
   `ecmQdot_field`).
3. Go to **Tools → Macros → Run Macro**.
4. Navigate to `EcmCouplerMacro.jar` and click **Open**.
5. The macro begins running immediately. You will see `[ECM]` log lines in the
   STAR-CCM+ output panel.

> **Do NOT press the Run button.** The macro controls the solver loop via
> `iter.step(1)`. If you press Run simultaneously, you will have two processes
> advancing the solver and results will be corrupted.

---

## 10. What happens each timestep

Understanding the coupling loop helps diagnose problems:

```
for step in 0 .. N_STEPS-1:

    1.  iter.step(1)
        STAR-CCM+ advances the solver by one timestep (deltaT seconds).

    2.  T_avg = VolumeAverageReport("ECM_T_avg").getValue()
        Read volume-averaged Temperature [K] from the battery region.
        The report is created automatically on first run and reused thereafter.

    3.  Write ecm/ecm_in.bin
        Binary file (v2 header + 1 record):
          - stepId       (transaction counter, echoed back for integrity check)
          - time         (current simulation time [s])
          - deltaT       (timestep size [s])
          - T_avg        (volume-averaged temperature [K])

    4.  Launch: python3 ecm/ecm_coupler.py
        Python reads ecm_in.bin, runs the ECM physics (OCV, R0/R1/R2, dUdT),
        and writes ecm_out.bin. The macro blocks until the process exits.

    5.  Read ecm/ecm_out.bin
        Binary file containing qVol [W/m³] for the battery region.
        If the echoed stepId does not match, the previous heat value is kept
        and a warning is printed.

    6.  Apply under-relaxation:
        qVol_applied = ALPHA * qVol_new + (1 - ALPHA) * qVol_prev

    7.  Set ScalarGlobalParameter "ecmQdot_W_m3" = qVol_applied
        STAR-CCM+ uses this value in the energy equation for the next step
        (via the field function applied to Volumetric Heat Source).
```

The coupling is **explicit** (temperature from step N drives heat for step N+1).
This is standard for this type of weak coupling and is stable provided deltaT is
not excessively large.

---

## 10b. Element-wise (distributed) coupling mode

Set the environment variable `ECM_COUPLING_MODE=elementWise` before running STAR, **or**
edit the CONFIG constant in the Java file:

```java
private static final String COUPLING_MODE =
    getEnvOrDefault("ECM_COUPLING_MODE", "elementWise");
```

In this mode the loop changes:

```
Initialisation (once, at t=0):
    1.  CellMapper built from XYZ Internal T-table (ECM_jellyRoll_T_Table).
        For N>1 regions: merged mapper covering all coupled jellyRoll regions.
        regionIdx assigned per cell via FvRepresentation cell counts, then
        verified against the T-table Parts list (auto-corrected if reversed).
    2.  ecm_cell_map.csv written (cellId, x, y, z, volume_m3, regionIdx).
    3.  ecm_mapping.csv deleted and regenerated via gen_ecm_mapping.py
        → creates N_regions × N_axial × N_radial ECM zones (e.g. 36 for 2 cells).
    4.  ecm_state.json deleted (fresh start only); preserved on continuation.
    5.  autoConfigureJellyRollEnergySource() wires FileTable to each region's
        User Volumetric Heat Source (requires User Volume Source enabled in GUI).

Per step:
    1.  iter.step(1)
    2.  Per-cell T extracted from XYZ Internal T-table (in-memory, fast).
    3.  Write ecm/ecm_in.bin with N records (cellId, T_K).
    4.  Launch Python ECM — reads ecm_mapping.csv, assigns cells to zones,
        runs ECM_N_REGIONS independent parallelBranches ECM states, returns
        per-zone qVol; mapped back to per-cell W/m³.
    5.  Read ecm/ecm_out.bin with N records (cellId, qVol_W_m3).
    6.  Write ecm/ecm_qvol_injection.csv (X, Y, Z, qVol_W_m3) for FileTable.
    7.  FileTable ECM_jellyRoll_Q_Table reloaded; STAR applies spatially
        varying heat to each jellyRoll region via User Volumetric Heat Source.
```

### Multi-region (N physical cells) setup

For a simulation with multiple physical battery cells (e.g. `jellyRoll_1`, `jellyRoll_2`):

1. **Set region pattern** — the macro discovers all coupled regions by matching
   `REGION_NAME_PATTERN` (default: `jellyRoll`). Any region whose name contains
   this string is included.

2. **Create one combined XYZ Internal T-table** (`ECM_jellyRoll_T_Table`) covering
   **all** jellyRoll regions:
   - Tools → Tables → New → XYZ Internal Table
   - Name: `ECM_jellyRoll_T_Table`
   - Parts: add `jellyRoll_1` **then** `jellyRoll_2` (alphabetical order recommended)
   - Scalars: `Temperature` (and optionally `Cell Volume`)

3. **Enable User Volume Source** for each jellyRoll Physics continuum:
   - Physics → [jellyRoll_N continuum] → Models → Energy → User Volumetric Heat Source = Enabled
   - Repeat for every jellyRoll continuum.
   - The macro (`autoConfigureJellyRollEnergySource`) will then wire the FileTable automatically.

4. **Set ECM_N_REGIONS** to the number of physical cells:
   ```
   set ECM_N_REGIONS=2
   ```
   Or add to `config.properties`: `ECM_N_REGIONS=2`

5. Run from t=0. The macro regenerates `ecm_mapping.csv` with
   `N_regions × 18 zones` (36 for 2 cells) automatically.

### Continuation runs

On a continuation run (physical time > 0):
- `ecm_state.json` is **preserved** — Python ECM resumes from saved SOC and RC voltages.
- `ecm_mapping.csv` is **kept** (only regenerated if cell count changes after re-mesh).
- Log files (`tempLog.csv`, `appliedTotalHeatLog.csv`) are **appended** without duplicate headers.

The macro prints `Run mode: FRESH (t=0)` or `CONTINUATION (t=X s)` at startup.

---

## 11. Output and monitoring

### Console output

The STAR-CCM+ output panel shows one summary line per timestep:

```
[ECM] step=0  t=0.1000 s  T_eff=298.1500 K
[ECM] qVol_new=45231.42  qVol_relaxed=31662.00  W/m3
[ECM] step=1  t=0.2000 s  T_eff=298.1612 K
[ECM] qVol_new=45289.11  qVol_relaxed=38712.38  W/m3
...
[ECM] Coupling loop complete.
```

Python ECM output (`ecm_coupler.py` stdout) is prefixed with `[ECM-py]`:

```
[ECM-py] ECM step t=0.10 I=5.05 A T=298.15 K Q=1.095 W SOC=1.000
```

### Binary exchange files

After each step, `ecm/ecm_in.bin` and `ecm/ecm_out.bin` contain the last
exchange. These are overwritten every timestep and are useful for debugging
but do not accumulate.

### ECM state

The Python ECM saves its internal state (SOC, RC-pair voltages) to
`ecm/ecm_state.json` after each step. This file can be inspected to check
SOC evolution:

```json
{
  "soc": 0.9843,
  "v_r1": 0.002341,
  "v_r2": 0.000891,
  "t_last": 100.0
}
```

---

## 12. Before re-running

### Fresh run from t=0 — fully automatic

When the macro detects physical time ≈ 0 (fresh start), it handles cleanup automatically:

| File | Action |
|------|--------|
| `ecm/ecm_state.json` | Deleted → Python ECM restarts at SOC=1 |
| `ecm/ecm_mapping.csv` | Deleted and regenerated from current `ecm_cell_map.csv` |
| Log files (`tempLog.csv`, etc.) | Overwritten with a fresh header row |

**No manual deletion is required.** Simply reset the STAR-CCM+ simulation to t=0
in the GUI and re-run the macro.

### Continuation run — also automatic

When physical time > 0 (continuation), the macro:

- **Preserves** `ecm_state.json` → Python ECM resumes from the correct SOC and RC voltages
- **Keeps** `ecm_mapping.csv` (only regenerates on cell-count mismatch after re-mesh)
- **Appends** to log files without duplicate headers

### Force-reset ECM state on a continuation (if needed)

If you want to reset the ECM state mid-run (e.g. for debugging), use the environment variable:
```
set ECM_STATE_RESET=1
starccm+.exe MyBattery.sim
```
The Python ECM detects this and ignores any existing `ecm_state.json`.

---

## 13. Troubleshooting

### `[ECM] ERROR: region 'jellyRoll' not found. Aborting.`

The name in `REGION_NAME` does not match the region in the STAR tree.

- In STAR-CCM+, expand **Regions** and note the exact spelling (including spaces
  and capitalisation) of your battery region.
- Edit `REGION_NAME` in `src/EcmCouplerMacro.java`, rebuild the JAR
  (see [Section 14](#14-rebuilding-the-macro-jar)), and reload.

---

### `[ECM] WARNING: ECM exited with code 1. Keeping previous qVol.`

The Python ECM process failed. Common causes:

1. **Python not found:** The command in `ECM_COMMAND` is not on your PATH.
   Fix: use the full path, e.g. `"C:/Python312/python.exe ecm/ecm_coupler.py"`.

2. **Missing packages:** `numpy` or `pandas` not installed.
   Fix: open a terminal in the package folder and run `pip install numpy pandas`.

3. **Working directory wrong:** `ecm_coupler.py` cannot find `ecm_io.py` or `params.csv`.
   Fix: ensure the `ecm/` folder is next to the `.sim` file, not somewhere else.

To diagnose: open a terminal, `cd` to the folder containing your `.sim` file,
and run:
```
python ecm/ecm_coupler.py --help
```
Any import or file-not-found error will be printed clearly.

---

### `[ECM] WARNING: ecm_out.bin not found within timeout.`

The Python process exited but did not write `ecm_out.bin` within `ECM_TIMEOUT_S`
seconds. This usually means the process crashed after writing `ecm_in.bin`.

- Increase `ECM_TIMEOUT_S` if the ECM is slow on first run.
- Check for errors in the `[ECM-py]` log lines above the warning.

---

### Heat source is always zero / temperature never rises

**elementWise mode:**

1. **User Volume Source not enabled (most common):** The log shows
   `autoConfigureJellyRollEnergySource failed: Object not found in TypedObjectManager`.
   Fix: Physics → [jellyRoll continuum] → Models → Energy → **User Volumetric Heat Source = Enabled**.
   Do this for every jellyRoll Physics continuum, save the `.sim`, and re-run.

2. **Current profile columns quoted:** Open `ecm/electrical_inputs_from_validation.csv`
   and ensure the first line reads `time,current_A` without quotes.

**Lumped (globalParam) mode:**

1. **Volumetric Heat Source not wired:** Confirm the battery region's
   Physics Values → Volumetric Heat Source is set to Field Function → `ecmQdot_field`.

2. **Field function definition wrong:** Confirm the definition is `$ecmQdot_W_m3`
   (dollar sign + exact parameter name, no spaces).

3. **ECM_COMMAND has wrong Python path:** The ECM exits with code 1 silently.
   See the previous troubleshooting entry.

---

### `stepId mismatch` warnings

These appear when the `ecm_out.bin` from a previous run is still on disk when a new
run starts, and the macro reads the stale file before the Python ECM writes the fresh one.

Fix: delete `ecm/ecm_in.bin`, `ecm/ecm_out.bin`, and `ecm/ecm_state.json` before
each run (see [Section 12](#12-before-re-running)).

---

### Temperature oscillates or diverges

The explicit coupling is susceptible to instability if the heat source changes
rapidly relative to the thermal mass of the cell.

- Reduce `ALPHA` (e.g. from 0.7 to 0.5 or 0.3) to smooth the heat injection.
- Reduce `deltaT` in the STAR solver settings.
- Both changes together are the safest fix.

---

### STAR-CCM+ cannot find `EcmCouplerMacro.jar`

Use the full absolute path when prompted by **Tools → Macros → Run Macro**:
```
C:\Users\yourname\Simulations\MyBattery\EcmCouplerMacro.jar
```

---

## 14. Rebuilding the macro JAR

You only need to rebuild if you edited `EcmCouplerMacro.java` or `EcmBinaryIO.java`.
The pre-built `EcmCouplerMacro.jar` in the package folder is ready to use as-is.

### Requirements

- Java 11 or newer (`javac` on your PATH, or the JDK bundled with STAR-CCM+)
- STAR-CCM+ installation (for `star-coremodule.jar`)

### Steps

1. Edit `STAR_LIB` at the top of `build.sh` to point to your STAR-CCM+ installation:
   ```bash
   STAR_LIB=/opt/starccm/star/lib/java/platform/modules
   ```

2. Run the build script (Linux / WSL):
   ```bash
   cd starccm_plugin
   bash build.sh
   ```

3. The rebuilt JAR appears at `dist/EcmCouplerMacro.jar`. Copy it to the package folder:
   ```bash
   cp dist/EcmCouplerMacro.jar package/EcmCouplerMacro.jar
   ```

### Finding the bundled JDK inside STAR-CCM+

STAR-CCM+ ships its own JDK. If `javac` is not on your system PATH:
```bash
find /opt/starccm -name "javac" 2>/dev/null
```
Use that path as `JAVA_HOME` at the top of `build.sh`.

---

## 15. ECM parameters and chemistry

### params.csv

The electrochemical model is parameterised by `ecm/params.csv`. The default file
contains NCA chemistry data for an 18650 / 2170 cell (nominal capacity 5.05 Ah).

Columns:
| Column | Unit | Description |
|---|---|---|
| `Q_Ah` | Ah | Cumulative charge discharged (0 = full, 5.05 = empty) |
| `T_degC` | °C | Cell temperature |
| `OCV_V` | V | Open-circuit voltage |
| `R0_Ohm` | Ω | Ohmic (instantaneous) resistance |
| `R1_Ohm` | Ω | First RC-pair resistance |
| `C1_F` | F | First RC-pair capacitance |
| `R2_Ohm` | Ω | Second RC-pair resistance |
| `C2_F` | F | Second RC-pair capacitance |
| `DUDT_V_per_K` | V/K | Entropic coefficient (dU/dT); drives reversible heat |

### Using your own cell chemistry

1. Replace `ecm/params.csv` with a file using the same column names.
2. Adjust the current profile in `ecm/electrical_inputs_from_validation.csv`
   to match your cell's capacity and charge/discharge protocol.
3. No code changes are required — the ECM reads the table at runtime.

### Heat generation model

The ECM computes total heat power `Q_gen [W]` as:

```
Q_irreversible = I² × R0  +  I² × R1 × (...)  +  I² × R2 × (...)
Q_reversible   = -I × T × dU/dT
Q_gen          = Q_irreversible + Q_reversible
qVol           = Q_gen / cell_volume_m3
```

The macro receives `qVol [W/m³]` and applies it uniformly across the battery region
via the Global Parameter and Field Function set up in Section 5.
