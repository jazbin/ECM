# BLOCK 01 — STAR-CCM+ Machine Instructions

**Block:** 01 (radial mapping + production candidates)
**TBM count:** 18
**Estimated runtime:** 3–6 min (18 × 10 s) to 6–10 min (18 × 20 s)
**Prepared by:** offline workspace (no Claude access during session)

---

## What this block does

This block answers a single question: which TBM fields control generated Can OD,
Can ID, and JR OD in STAR's `Create from Tbm` geometry builder?

Using those answers it also includes precomputed production candidates, so the same
session may produce the final OpenFOAM-equivalent 2170 geometry without a second
POD block.

You do not need to understand the geometry. Your only jobs are:
1. Import each TBM in order.
2. If successful: export STEP to the RETURN folder.
3. If failed: record the exact STAR error.
4. Continue immediately.

---

## Before you start

Verify the `cases/` folder contains exactly 18 `.tbm` files:

```
01_CTRL_T06_S.tbm
02_RA_19P0.tbm
03_RA_20P0.tbm
04_RA_20P5.tbm
05_RA_21P09.tbm
06_RB_19P0.tbm
07_RB_20P0.tbm
08_RB_20P6274.tbm
09_RB_21P0.tbm
10_CTRL_T06_M.tbm
11_RC_17P5.tbm
12_RC_17P0.tbm
13_RC_16P0.tbm
14_PROD_D1_GAP.tbm
15_PROD_D1_SLIM.tbm
16_PROD_D1_NEAR.tbm
17_PROD_D2_CONT.tbm
18_CTRL_T06_E.tbm
```

Verify the `RETURN/` folder exists with one sub-folder per case ID (names without the
run-number prefix, e.g. `RETURN/CTRL_T06_S/`, `RETURN/RA_19P0/`, …).

---

## Step 1 — Start STAR-CCM+ with POD licence

Launch STAR with your POD licence. Create a **new empty simulation** (File → New).

Do not open any existing simulation.

---

## Step 2 — Confirm `Create from Tbm` exists

Navigate: **Battery Cell → Create from Tbm…** (usually under the Batteries or
Physics menu, exact location depends on version).

If this menu item is absent, record the STAR version (Help → About) and stop.
Do not consume more POD time.

---

## Step 3 — Run each case in RUN_ORDER.txt

Work through the 18 TBMs **in order** (01 through 18).

For each case:

### If import SUCCEEDS (geometry appears in scene)

1. Export the geometry as a STEP file.
   - File → Export → STEP  OR  right-click the geometry node → Export → STEP
   - Save to: `RETURN/<case_id>/<case_id>.step`
   - Example: `RETURN/CTRL_T06_S/CTRL_T06_S.step`
   - Use the **case_id** exactly as listed — do NOT include the run-number prefix.

2. Do **not** close the simulation between cases. Just keep importing.
   - If STAR requires a fresh simulation per TBM, create a new one (File → New)
     before the next import.

### If import FAILS (STAR shows an error)

1. Copy the **exact** error text into a file called `ERROR.txt` inside the case
   folder: `RETURN/<case_id>/ERROR.txt`
2. Do **not** attempt to fix the TBM.
3. Continue immediately to the next case.

### Expected FAIL cases (do not be alarmed)

| Case | Expected error |
|---|---|
| `09_RB_21P0.tbm` | "Can Thickness is -ve" (deliberate diagnostic) |

Cases `16_PROD_D1_NEAR.tbm` and `17_PROD_D2_CONT.tbm` have unknown outcomes —
both PASS and FAIL are informative. Record result either way.

---

## Step 4 — After the last case (18_CTRL_T06_E)

1. Close STAR immediately — do not keep the session running.
2. Copy the entire `RETURN/` folder back to the workspace.
3. Do not modify or rename any files before copying.

---

## RETURN folder structure after the session

```
RETURN/
  CTRL_T06_S/
    CTRL_T06_S.step        ← if PASS
    ERROR.txt              ← if FAIL (leave empty folder if skipped)
  RA_19P0/
    RA_19P0.step
  RA_20P0/
    RA_20P0.step
  ... (one folder per case)
  CTRL_T06_E/
    CTRL_T06_E.step
```

---

## Timing

At 10 s per import: ~3 min
At 20 s per import: ~6 min
STEP export adds ~10 s per PASS case.
Total session including setup: aim for under 30 min.

---

## If STAR crashes or the licence drops mid-session

Record the last successfully completed case in `RETURN/SESSION_NOTES.txt`.
Return whatever partial results exist — partial blocks are still analysable.

Do not restart and re-run already-completed cases.

---

## Do not

- Measure anything.
- Change any TBM.
- Run a Java macro.
- Inspect geometry beyond confirming the import succeeded.
- Keep STAR running after the last case.
