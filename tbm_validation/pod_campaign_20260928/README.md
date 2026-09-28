# STAR-CCM+ TBM POD Campaign — 2026-09-28

Mission: use the 10-hour STAR-CCM+ POD allocation as a controlled experiment, not an interactive debugging session.

Success means: qualify automated/hybrid TBM import; resolve radial field mapping on T06; test safe-gap and exact-contact 2170 probes; run the real generated TBM through native battery initialization; cold-reproduce it; preserve hashes/logs/STEP evidence.

Hard rules:
1. No routine TBM editing while POD time is running.
2. Maximum 60 minutes total on automating Create from Tbm; then switch to hybrid/manual.
3. Each diagnostic case starts from a clean simulation/process.
4. Every case has ID, SHA-256, expected class, log, and STEP if generated.
5. STEP measurements and Boolean analysis happen offline.
6. Freeze T06 axial geometry during radial tests.
7. Stop testing a hypothesis once resolved.
8. Keep ~20% POD reserve until cold reproduction passes.

Known baseline:
- source: artifacts/equivalence/robert_s0/input/T06_TARGET_AXIAL_SURPLUS_2p00.tbm
- JR OD ~17.880992 mm
- Can ID 18.000000 mm
- Can OD ~20.90 mm
- JR/Can radial gap ~0.059504 mm
- JR height 65.11 mm
- both tab/electrode surpluses +2.00 mm

Exact prebuilt radial probes:
- artifacts/equivalence/geometry_campaign/input/GC_RAD_A_can_id_probe.tbm
- artifacts/equivalence/geometry_campaign/input/GC_RAD_B_can_rep_xy_probe.tbm
- artifacts/equivalence/geometry_campaign/input/GC_RAD_C_jr_od_probe.tbm

Execution order:
A. Before POD: run scripts/prepare_cases.py. Validate build/manifest.csv and build/HASHES.sha256.
B. First POD hour: record one T06 Create-from-Tbm + STEP export operation; replay unchanged; patch paths and replay stock 18650. If unreliable by 60 minutes, stop automation work.
C. Harness qualification: CTRL_T06_PASS -> PASS; CTRL_18650_PASS -> PASS; CTRL_E004_BOTH_ZERO -> E004; CTRL_CAN_NEG_JR20p6274 -> can/radial failure.
D. Run RAD_A/B/C only. Export STEP for successes. Stop STAR if entitlement can pause.
E. Offline: scripts/step_audit.py then scripts/decide_radial.py.
F. Generate PROD_GAP and PROD_CONTACT using scripts/make_production_probes.py with driver assignments determined by Phase D/E. Run GAP first. Run CONTACT only if GAP passes.
G. Generate the real TBM through the production translator/generator; do not hand-fix it. If lab probe passes but production TBM fails, semantic-delta-debug the field groups.
H. Native battery acceptance: create battery objects/module, initialize, tiny nonzero load, verify SOC/voltage/heat, then short representative load.
I. Close STAR and cold-reproduce from the final TBM and scripts only.

POD target budget:
- 0:00-1:00 automation gate
- 1:00-1:30 controls
- 1:30-2:15 RAD-A/B/C
- 2:15-2:45 offline mapping decision
- 2:45-3:30 PROD-GAP/CONTACT
- 3:30-4:30 conditional threshold/mapping work
- 4:30-5:30 real generator output/delta debug
- 5:30-6:45 native battery setup/init
- 6:45-7:30 runtime smoke
- 7:30-8:15 cold reproduction
- 8:15-10:00 reserve

Do not consume reserve on low-information sweeps.
