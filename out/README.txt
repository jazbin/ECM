hp2170NCA-RCR-distributed-S3fix.tbm — STAR-CCM+ import test candidate
2026-09-10

WHAT THIS IS
This is the next controlled STAR-CCM+ import test candidate for the 2170 NCA cell with RCR electrochemical model (distributed 3D mode). It differs from the previous tested file (hp2170-rcr-v1, tested 2026-09-09) by one geometry parameter only.

WHAT CHANGED
Positive-electrode root/extension dimension S3 was changed from 0 mm to 5 mm. This is the only change.

Reason: comparison with Siemens STAR-CCM+ cylindrical reference TBM files (validationBattery.tbm, testTBM.tbm, LiIonSpiral.tbm, tutorialCylindricalCell.tbm) showed that all of them use +Electrode m_dS3 = 5. The previous candidate had the value at 0 (inherited from the BDS-generated source TBM which was configured for 1D-only mode). The 2026-09-09 runtime failure "Electrode Root 1 : Extrusion distance can not be 0" is consistent with this zero-length segment.

All RCR tables, model data, package dimensions, mandrel, jelly-roll diameter, separator, tab configuration, offsets, and MODELMAP (IET = RCRTable 3D, Thermal = Distributed) are unchanged.

SHA-256: 372c99026580732866708f0f45906caa74733a826e816fdf2d7de0b416ca0e3b

WHAT TO DO
1. Run: Batteries > Battery Cell > Create from Tbm
2. Select hp2170NCA-RCR-distributed-S3fix.tbm
3. If it fails: send us the exact next error message from STAR-CCM+.
4. If it succeeds: send a screenshot or STEP export of the generated geometry before further modification.

We have not yet proven that S3=5 is the sole cause — we will know after this test.
