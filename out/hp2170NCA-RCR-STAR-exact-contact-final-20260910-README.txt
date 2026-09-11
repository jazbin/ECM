hp2170NCA-RCR-distributed-exact-contact-final.tbm — STAR-CCM+ TBM Package
======================================================

Overview
--------
This TBM file is the OpenFOAM-ECM-equivalent exact-contact candidate for the
HP 2170 NCA cylindrical cell. It has been built to reproduce the OpenFOAM-ECM
reference model in STAR-CCM+ using STAR's native TBM distributed battery solver.

Geometry target
---------------
JR OD = can ID = 20.6274 mm (exact equality, zero gap).
This is the ideal/shared JR-can contact condition, equivalent to the
OpenFOAM-ECM reference model where no air gap exists at the JR-can interface.

STAR-CCM+ cylindrical reference TBMs (LiIonSpiral.tbm, validationBattery.tbm)
use the same pattern (17.9 mm / 17.9 mm), confirming that exact JR/can-ID
equality is a known valid STAR TBM pattern.

Model configuration
-------------------
  Electrolyte : General Electrolyte
  IET         : RCRTable 3D
  Thermal     : Distributed

RCR data: 3 temperature sets (15, 25, 35 deg C), 7 SOC points per set.
Cell capacity: 5.0 Ah.

Static preflight status
-----------------------
Full static preflight completed 2026-09-10.
FAIL = 0 | ACTION_REQUIRED = 0 | UNRESOLVED_BLOCKERS = 0
MAXIMUM_STATIC_PREFLIGHT_PASS
Runtime STAR import success is not yet proven — this audit is static only.

Instructions for Robert
-----------------------
1. Before any Create from Tbm runs, please send a screenshot of the
   "Import Battery Options" dialog with all selectable object names visible.
   (Appears when you select a TBM file — before creation starts.)

2. Open STAR-CCM+ with the TBM battery module.
3. For the E004 diagnostic campaign: see hp2170NCA-STAR-E004-multifile-diagnostic-20260910.zip
   which contains 18 TBMs (C00-C17). Run Create from Tbm for each and report:
       C00: PASS / <exact error text>
       ...
       C17: PASS / <exact error text>
       E00 RCR-data-only import: PASS / <exact error>
       Import-options screenshot: attached

4. E00 — RCR data-only import (independent control):
   a. Create a User Defined Battery Cell.
   b. Select the RCR Model.
   c. Under the RCR model, select "Extract RCR Parameters from TBM File".
   d. Choose this TBM file (hp2170NCA-RCR-distributed-exact-contact-final.tbm).
   e. Record whether 3 temperature-set RCR tables are created (288.15/298.15/308.15 K).

5. For the exact-contact candidate (this file):
   - If creation succeeds: send a screenshot of the imported geometry; export STEP.
   - If STAR blocks creation: send the complete STAR-CCM+ log/error output.

Campaign ZIP: out/hp2170NCA-STAR-E004-multifile-diagnostic-20260910.zip
Campaign ZIP SHA-256: 5fc9776510e707f3e058ad4948b3768e3dd12bbbf06ef31d7c2060ac91bbd2f9

