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
1. Open STAR-CCM+ with the TBM battery module.
2. Select "Create from Tbm" and import this file.
3. If creation succeeds:
   - Please send a screenshot of the imported geometry.
   - Export the resulting geometry as STEP.
4. If STAR blocks creation:
   - Please send the complete STAR-CCM+ log/error output.

Contact: Bojan Vidovic, Helicon Engineering
