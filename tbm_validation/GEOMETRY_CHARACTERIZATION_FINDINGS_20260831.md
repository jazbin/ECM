# TBM geometry characterization findings — 2026-08-31

This record summarizes the STEP export characterization completed on 2026-08-31. It is separate from the later four-variant `package_rev3` import/topology check.

## Evidence

- Input package: `in/TBM_STARCCM_Complete_Geometry_Characterization_20260814_RESULTS.zip`
- Matrix: 21 isolated TBM variants (one control plus 20 perturbations).
- Returned geometry: 19 STEP files plus one documented geometry-creation failure (Test 04). The remaining 20 successful variants were analyzed with pythonOCC (`STEPControl_Reader`, bounding boxes, and boolean intersections).
- Analysis record: `artifacts/logs/session_20260831_073946.log` and `artifacts/reports/TBM_GEOMETRY_CHARACTERIZATION_FINDINGS_20260831.md`.

## Established findings

- Detailed Builder `m_dJellyrollThickness_mm` is consumed by `Create from Tbm` and drives realized jelly-roll diameter. Requested values 17.0, 17.3, and 17.6 mm realized as approximately 17.009, 17.303, and 17.562 mm.
- A requested 18.2 mm jelly-roll diameter failed because it exceeded the 18.0 mm can diameter in that characterization model.
- Changing REPORT `m_dRepJellyrollDiameter` or the Simple Builder jelly-roll diameter produced no observed geometry change. In conflicts, the Detailed Builder value won over REPORT and physical winding-length values.
- Realized diameter was monotonic and tracked the Detailed Builder input; discretization deviations were below 0.25 mm in the tested matrix.
- Physical electrode widths drove jelly-roll axial length. Detailed Builder JR width, REPORT JR height, and physical winding electrode lengths were not observed to drive that result.
- Detailed Builder mandrel diameter was consumed. Package external height drove can height; REPORT can diameter apparently drove can OD in the tested matrix, while REPORT can height and DataSheet dimensions were not observed to drive geometry.
- All 20 successful variants had zero measured JellyRoll∩Can and JellyRoll∩Mandrel intersection volume.

## Limitation and remaining question

This characterization establishes the relevant STAR field behavior and feasibility guard, but it does not prove the correct physical winding OD for the current 2170 project TBM. The current package value is 19.25 mm and the can internal diameter is 20.6274 mm, a 1.3774 mm diametral difference. The 20.6274 mm value is a cavity ID/geometric upper bound, not a required jelly-roll OD. A package-specific STAR import/topology result and physical design evidence are still needed for the production configuration.

The production objective remains equivalent cell-level and distributed electrothermal response within defined validation tolerances. STAR internal topology and discretization do not need to reproduce the OpenFOAM representation one-to-one.
