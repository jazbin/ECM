hp2170 NCA — STAR-CCM+ E004 Multifile Diagnostic Campaign
2026-09-10

BACKGROUND

This package diagnoses the persistent STAR-CCM+ geometry creation failure:

    Feature execution failed.
    Electrode Root 1 : Extrusion distance can not be 0.
    Command: CreateFromTbm

This exact fatal error has appeared across multiple packages since 2026-09-04.
Each file in this package intentionally changes only a controlled subset of
Detailed Builder geometry fields so that test results can isolate the cause.

FILES (14 total)

C00_SIEMENS_CONTROL_validationBattery.tbm
    Unmodified Siemens STAR install reference TBM.
    Run this first to confirm your STAR installation and Create from Tbm
    workflow work on a known-good Siemens file. No project data.

C01_FEED10.tbm
    Delta: m_dSepFeedLength_mm 0 -> 10 only.

C02_TAIL85.tbm
    Delta: m_dSepTailLength_mm 0 -> 85 only.

C03_FEED10_TAIL85.tbm
    Delta: m_dSepFeedLength_mm 0 -> 10  AND  m_dSepTailLength_mm 0 -> 85.
    Highest-probability fix candidate.

C04_END40.tbm
    Delta: m_dElectrodeOverlapAtEnd_mm 20 -> 40 only.

C05_FEED10_TAIL85_END40.tbm
    Delta: Feed=10, Tail=85, OverlapEnd=40.

C06_MANDRELWIDTH0.tbm
    Delta: m_dMandrelWidth_mm 6 -> 0 only.

C07_FEED10_TAIL85_MANDRELWIDTH0.tbm
    Delta: Feed=10, Tail=85, MandrelWidth=0.

C08_JRWIDTH65p11.tbm
    Delta: m_dJellyrollWidth_mm 0 -> 65.11 only.

C09_FEED10_TAIL85_JRWIDTH65p11.tbm
    Delta: Feed=10, Tail=85, JellyrollWidth=65.11.

C10_STAR_BUILDER_PATTERN.tbm
    Delta: Feed=10, Tail=85, OverlapStart=3, OverlapEnd=40, MandrelWidth=0.
    Broad rescue using STAR-reference Detailed Builder conventions.

C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm
    Delta: All C10 changes plus JellyrollWidth=65.11. Maximum rescue variant.

C12_FULL_SIEMENS_DETAILED_BUILDER.tbm
    Complete Detailed Builder block from Siemens validationBattery.tbm,
    transplanted into the project file. Project SIMMOD and RCR data retained.
    Diagnostic only — not a production geometry candidate.

C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm
    Both the Physical Cell Description and Detailed Builder from Siemens
    validationBattery.tbm, with project MODELMAP, RCRTable 3D SIMMOD, General
    Electrolyte SIMMOD, and Distributed Thermal SIMMOD retained.
    Diagnostic only — not a production geometry candidate.

WHAT TO DO

Run Batteries > Battery Cell > Create from Tbm for all 14 files.
Recommended order: C00, C03, C01, C02, C10, C12, C13, C05, C07, C04, C06,
C08, C09, C11.

Return results in this exact format:

    C00: PASS / <exact error text>
    C01: PASS / <exact error text>
    C02: PASS / <exact error text>
    C03: PASS / <exact error text>
    C04: PASS / <exact error text>
    C05: PASS / <exact error text>
    C06: PASS / <exact error text>
    C07: PASS / <exact error text>
    C08: PASS / <exact error text>
    C09: PASS / <exact error text>
    C10: PASS / <exact error text>
    C11: PASS / <exact error text>
    C12: PASS / <exact error text>
    C13: PASS / <exact error text>

IMPORTANT

If a file creates geometry successfully, record PASS and continue testing all
remaining files.

If STAR reaches a DIFFERENT error than "Electrode Root 1", report that full
error text. A different error means E004 was cleared for that variant, which
is important diagnostic information even if full creation did not succeed.

The exact error text matters. Do not reduce a different downstream blocker
to just FAIL — report what STAR actually says.
