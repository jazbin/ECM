hp2170NCA-RCR-distributed-final-preflight.tbm
2026-09-10

WHAT THIS IS

This is the 2170 NCA cell TBM with RCR electrochemical model (distributed 3D mode, IET = RCRTable 3D, Thermal = Distributed). It has completed the full static STAR-CCM+ compatibility preflight against the available Siemens cylindrical reference set (validationBattery.tbm, testTBM.tbm, LiIonSpiral.tbm, tutorialCylindricalCell.tbm). Validator result: 0 FAIL, 4 WARN (all pre-existing unresolved items, none linked to a known runtime failure).

CHANGE HISTORY

This is V3 of the RCR distributed candidate.

V1 (2026-09-09, FAILED): +Electrode m_dS3 = 0. Runtime error: "Electrode Root 1 : Extrusion distance can not be 0."
V2 (2026-09-10, S3 fix): +Electrode m_dS3 = 0 → 5. Resolved the geometry extrusion error. Static preflight was not yet complete.
V3 (2026-09-10, full preflight): Added Transport Number sets = 0 to General Electrolyte SIMMOD. All 4 STAR-install cylindrical references contain this field. Robert's runtime log on V1 explicitly reported "Transport Number sets not found in the file, defaulting to 0." — this confirms the field is consumed by the STAR importer and that the value 0 is correct. This is the only additional change from V2.

SHA-256 (V3): 91cb8f8a2069c308db8dd910a695a2e7bbf55cca509330df004fa8ce82f638d4

PROTECTED CONFIGURATION (unchanged from About-Energy specification)

IET = RCRTable 3D
Thermal = Distributed
m_bOnly1D = 0
m_bLumpedEnergyBalance = 0
m_dAhCell = 5.0
m_nRCRParameterSets = 3
OD = 21.09 mm, height = 70.02 mm, can ID = 20.6274 mm, JR OD = 19.25 mm
+Electrode m_dS3 = 5 mm, -Electrode m_dS3 = 50 mm
Tabs: positive and negative on same face (top)
Three temperature sets (RCR data from About-Energy characterisation)

WHAT TO DO

Please run: Batteries > Battery Cell > Create from Tbm, and select hp2170NCA-RCR-distributed-final-preflight.tbm.

If creation succeeds, please send:
  - A screenshot of the generated cell geometry/topology
  - Preferably a STEP export before further modification

If STAR reports any message that prevents creation, please send the complete message/log.
