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

- Exact OF reference thermal operator (geometry, ρ/c_p/K tensors, BCs, interfaces, heat-source spatial mapping) reconstructed from real case files. The 3 open items originally flagged here are now resolved (`docs/equivalence/OPENFOAM_REFERENCE_RESOLUTION_20260918.md`): heat source is 100% Q→JellyRoll (no split exists in the executable code path), bottom contact is the production case's near-ideal R≈1.8mΩ·K/W (the documented 5.4 K/W value is stale, superseded documentation for an abandoned calibration variant), and a fresh non-stale pure-thermal reference run has been generated in `cases/wedge_2170_thermal_qualification`.
- Exact (B-Rep boolean) geometric classification of all 13 T06 bodies against the OF reference domains.
- A real, previously-undocumented conduction-shortcut finding (**topological**, dimension-independent): Can↔EndPlate↔Internal-Post↔Washer↔TabStem↔TabRoot↔Jellyroll is a confirmed touching chain at both cell ends, bypassing OF's only bottom-contact resistance.
- A geometric-coverage observation (**dimensional, NOT decision-driving**): BDS solid material at T06's current (non-final, 19.25mm JR OD) radial dimensions covers only ~56% (Can) and ~16% (Cap) of the corresponding OF reference-domain volume, which is sized to the final 20.6274mm JR OD target. This is expected geometry mismatch from comparing pre-final to final radial dimensions, not evidence of an architectural BDS thermal-mass deficiency — see `docs/equivalence/T06_GEOMETRIC_EQUIVALENCE_AUDIT.md`'s "Finding classification" section. Must be recomputed against final-dimension geometry before it can inform any decision.
