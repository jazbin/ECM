# First STAR-CCM+ POD Session — Operational Checklist

**Objective of this session:** record one clean `Create from Tbm` workflow and stop.
Do not run any other case manually. Do not run RAD-A/B/C yet.

---

## Before starting STAR

- [ ] Confirm `pod_run_20260929/cases/` contains the 7 TBMs (verify hashes against `CASE_MANIFEST.csv`)
- [ ] Confirm `pod_run_20260929/recorded/` exists and is empty
- [ ] Know exactly how to pause or close the POD licence if needed

---

## Step A — Start STAR-CCM+ with the POD licence

Launch with your POD licence server coordinates.
Example (adjust host/port to your licence):

```
starccm+ -power -podKey <KEY> -licpath <port>@<host>
```

Do NOT open any existing simulation. You need a fresh GUI session.

---

## Step B — Confirm `Create from Tbm` exists

Navigate to: **Batteries** menu (or **Physics → Batteries** depending on version).
Look for: `Battery Cell → Create from Tbm...`

If this menu item does NOT exist, STOP and record which STAR version is installed:
Help → About. Do not consume more POD time debugging this.

---

## Step C — Start a fresh simulation

File → New Simulation (or use the New button).
Do not import any mesh. Just accept the empty simulation.

---

## Step D — Start the Java Macro Recorder

Tools → Macro → Record Macro...
(Or: Tools → Record Macro)

A dialog will appear asking where to save the `.java` file.
Save it somewhere you can find, e.g. your Desktop or a temp path.
Keep it simple — single-class name, no spaces in path.

Click **Record** to start recording.

---

## Step E — Import CTRL_T06_PASS via `Create from Tbm`

From the Batteries menu:
`Battery Cell → Create from Tbm...`

In the file browser, navigate to:

```
pod_run_20260929/cases/CTRL_T06_PASS.tbm
```

Select it and click Open / Import.

---

## Step F — Accept import options

Accept the default import dialog options as they appear.
Do NOT change any settings on first run — the goal is to record the default workflow.
Note which options appear (number of dialog pages, any checkboxes).

---

## Step G — Wait for geometry generation

Let STAR complete the geometry build. This may take 1–3 minutes.
Watch for the progress bar to finish and the geometry to appear in the scene.
If STAR shows an error or warning, take a screenshot and note the exact text.

Expected: geometry builds successfully (PASS case).

---

## Step H — Export geometry to STEP (if straightforward)

If STAR shows a STEP export option after geometry generation:
File → Export → STEP (or right-click geometry node → Export → STEP)

Save to:
```
pod_run_20260929/results/CTRL_T06_PASS/CTRL_T06_PASS.step
```

If STEP export is buried in non-obvious menus, skip it for now and note the menu path.
Do NOT spend more than 5 minutes hunting for it.

---

## Step I — Stop macro recording

Tools → Macro → Stop Recording (or the same menu used to start recording).

STAR will finalize the `.java` file.

---

## Step J — Save the recorded Java file

Copy/move the recorded `.java` file to:

```
pod_run_20260929/recorded/CreateFromTbmRecorded.java
```

Open the file in a text editor and confirm:
- It is non-empty (> 50 lines)
- It contains a string literal ending in `.tbm`
- If STEP was exported: a string literal ending in `.step` or `.stp`
- It contains exactly one `public class` declaration

---

## STOP HERE

**Do NOT proceed to RAD-A, RAD-B, or RAD-C manually.**
**Do NOT run the campaign harness yet.**

The recorded Java file is the critical next artifact.
Offline steps:

1. Inspect `pod_run_20260929/recorded/CreateFromTbmRecorded.java` in a text editor.
2. Identify the exact API call STAR used for `Create from Tbm`.
3. Run `patch_recorded_macro.py` to verify path substitution works.
4. Only then proceed to running the harness with `run_recorded_campaign.py`.

---

## POD time note

This session should consume no more than 30 minutes.
If Step G fails (geometry error on T06 which is a known-PASS), stop and investigate offline.
The T06 geometry is the most-tested TBM in this repo — a failure here indicates a licence,
version, or installation issue, not a TBM problem.

---

## Version capture

Before closing STAR, record:
- STAR-CCM+ version: Help → About (e.g. 18.06.xxx)
- Licence type confirmed: POD
- Java macro API prefix used in recorded file (e.g. `simulation.get...`)

Save these notes to `pod_run_20260929/logs/session_01_notes.txt`.
