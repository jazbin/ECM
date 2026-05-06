ECM Coupler for STAR-CCM+ 21.02
================================

QUICK START
-----------
1. Run setup.bat  (once — installs Python deps, writes config.properties)
2. Open your .sim file in STAR-CCM+
3. One-time wiring in STAR (first run only — saves into the .sim file):
     a. Tools > Global Parameters > New Scalar Parameter
        Name:   ecmQdot_W_m3
        Value:  0
        Units:  W/m^3
     b. Regions > jellyRoll > Physics Values > Volumetric Heat Source
        Method:   Field Function
        Function: $ecmQdot_W_m3
4. Tools > Macros > Run Macro > select EcmCouplerMacro.jar
   (do NOT press the Run button — the macro drives the solver itself)

PACKAGE CONTENTS
----------------
EcmCouplerMacro.jar   Compiled STAR-CCM+ macro (Java 11, ready to load)
setup.bat             One-time setup: finds Python, installs deps, writes config
README.txt            This file
ecm\                  Python ECM backend
    ecm_coupler.py    Main coupling script (called once per timestep)
    ecm_io.py         Binary protocol I/O
    mock_ecm_backend.py  Stateful mock battery model
    mock_model.py     Core electrochemical compute
    params.csv        ECM lookup table (NCA 4680 chemistry)

CONFIGURATION
-------------
Edit the CONFIG block at the top of the macro source (src\EcmCouplerMacro.java)
and rebuild, or edit config.properties (Python path) created by setup.bat.

Key macro settings:
  REGION_NAME   jellyRoll       Name of the coupled region in STAR tree
  QPARAM_NAME   ecmQdot_W_m3    Name of the global scalar parameter
  ECM_COMMAND   python3 ecm\ecm_coupler.py   ECM process to call each step
  ALPHA         0.7             Under-relaxation factor (0 < alpha <= 1)
  N_STEPS       100             Number of timesteps to run

If python3 is not on your PATH, change ECM_COMMAND to the full path, e.g.:
  C:/Python312/python.exe ecm/ecm_coupler.py

WORKING DIRECTORY
-----------------
STAR-CCM+ sets the working directory to the folder containing the .sim file.
Place the ecm\ folder next to your .sim file (or adjust ECM_IN_FILE /
ECM_OUT_FILE / ECM_COMMAND paths in the macro).

TROUBLESHOOTING
---------------
- "[ECM] ERROR: region 'jellyRoll' not found"
  -> Change REGION_NAME in the macro to match the region name in your tree.

- "[ECM] WARNING: ECM exited with code 1"
  -> Run  python ecm\ecm_coupler.py --help  in a terminal from this folder.
     Likely cause: missing numpy/pandas — re-run setup.bat.

- STAR-CCM+ does not find EcmCouplerMacro.jar
  -> Use the full path in Tools > Macros > Run Macro.

- ECM state from a previous run is stale
  -> Delete ecm_state.json next to the .sim file, or set env var ECM_STATE_RESET=1.

REBUILDING THE MACRO (optional)
--------------------------------
Only needed if you change EcmCouplerMacro.java.
Requires: Java 11+ and the STAR-CCM+ 21.02 installation present.
  1. Edit src\EcmCouplerMacro.java
  2. Update STAR_LIB path in build.sh to your STAR-CCM+ install location
  3. bash build.sh        (Linux/WSL)
     The rebuilt jar appears in dist\EcmCouplerMacro.jar.
     Copy it to this package folder.
