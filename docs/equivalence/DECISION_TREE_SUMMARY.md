# Decision Tree — Result of This Run

1. Are BDS auxiliary bodies geometric subdivisions of OF domains?
   → **PARTIAL.** 7/13 bodies are exact (≥99%) single-domain subdivisions (Mandrel, Jellyroll → JR; −Ve Tab Root → Can; +Ve Tab Root/Stem, +Ve Washer, +Ve EndPlate, +Ve Internal-Post → Cap). 1/13 (Can) crosses JR/Can/Cap/outside. 4/13 (−Ve Tab Stem, −Ve Washer, −Ve EndPlate, −Ve Internal-Post) are 84–100% outside all three OF reference domains.
   → Offending bodies: **Can** (needs 3-way piecewise split) and the **−Ve bottom-hardware stack** (no OF-domain target exists; requires Option D — equivalent interface treatment — per `BDS_TO_OPENFOAM_THERMAL_MAPPING.md`).

2. Can Can+Cap be merged exactly?
   → **NO** as a single homogeneous material (properties differ by up to 1600× in conductivity). → **EXACT PIECEWISE UNION SUPPORTED** instead: ideal internal interface, two material zones, contiguous geometry confirmed (`CAN_CAP_REDUCTION_DECISION.md`).

3. Does thermal-only BDS geometry reproduce the OF transient?
   → **NOT YET TESTED** in STAR (no STAR session run this task — repository-only analysis). A runnable OpenFOAM-side reference case exists (`cases/wedge_2170_constant_heat_rtherm`, needs a fresh non-stale run) and the exact STAR configuration to attempt (Test A) is specified in `STAR_CLIENT_EQUIVALENCE_TEST_PLAN.md`.

4. Can STAR preserve electrical role after thermal remapping?
   → **UNKNOWN** — this is Test B, and is flagged as the single largest open STAR-capability question (can a Tab/Post/Washer/EndPlate keep its Tab Parts electrical role while carrying Cap-equivalent near-insulating thermal properties, or a suppressed/resistance-only bottom-path treatment?).

5. Does RCRTable 3D have independently evolving local states?
   → **UNKNOWN** — Test C, not run (no STAR access in this task).

6. Full coupled STAR ↔ OF validation
   → **NOT REACHED** — gated behind 3–5.

## What this run resolved with certainty (evidence-backed, not STAR-dependent)

- Exact OF reference thermal operator (geometry, ρ/c_p/K tensors, BCs, interfaces, heat-source spatial mapping) reconstructed from real case files, with 3 explicit open items flagged (heat-split doc conflict, Rtherm value mismatch, stale postProcessing data) — none invented.
- Exact (B-Rep boolean) geometric classification of all 13 T06 bodies against the OF reference domains.
- A real, previously-undocumented conduction-shortcut finding: Can↔EndPlate↔Internal-Post↔Washer↔TabStem↔TabRoot↔Jellyroll is a confirmed touching chain at both cell ends, bypassing OF's only bottom-contact resistance.
- A real, previously-uncharacterized geometric-coverage gap: BDS solid material covers only ~56% (Can) and ~16% (Cap) of the corresponding OF reference-domain volume — independent of the material-mapping question, and relevant to the project's ongoing JR-OD clearance work.
