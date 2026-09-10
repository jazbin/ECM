# TBM Inventory

Every TBM file tracked in this repository. Provenance, status, and known issues are documented per file. Do not modify or overwrite historical files — they exist to establish a change chain.

---

## Source TBMs (`tbm_validation/source/`)

These are preserved read-only. The generate scripts read from these files but never write back.

| File | SHA-256 | Provenance | Status |
|---|---|---|---|
| `hp2170NCA-ECM.tbm` | `fa4cb299fc444a35875b51bb0093fae43b88f78a677b92554d732cc72cae6204` | Current working source. Cloned from `BDS_files/_Projects/GapExample/hp18650Spiral1.tbm` (Siemens stock 18650), then electrochemistry replaced from `python/params.csv` (About-Energy characterisation data). See NOTES below. | KNOWN ISSUES |
| `hp2170NCA-ECM-20260831.tbm` | `fa4cb299fc444a35875b51bb0093fae43b88f78a677b92554d732cc72cae6204` | Identical to `hp2170NCA-ECM.tbm` by SHA-256. Timestamped backup from 2026-08-31. | Same SHA — same content. |
| `hp2170NCA-ECM-simplified.tbm` | `84b8451219135a09b91078e98985316e2bfb5da52ec3488c44cdb3916d4c7fad` | Simplified variant of the source — exact generation procedure not reconstructed. Contains electrochemical data but may differ in SIMMOD block count or secondary fields. | UNVERIFIED — not used in any sent package. |
| `2170_resized_from_stock_DRAFT.tbm` | `239314c36c784aaf1635480393c43e609a6b3fe540f5ee077f5ce334d0a26fae` | Earlier draft of the resize-from-stock exercise. Retained for provenance. | DRAFT — superseded by `hp2170NCA-ECM.tbm`. |
| `hp18650Spiral-DIST.tbm` | `604f18c2844d07af77ba593f6d43afb1a66924560b490ab3d1891327dd950666` | Siemens stock distributed-mode HP18650 reference. Copied here for field comparison. (Identical SHA to `reference/HP18650/hp18650Spiral-DIST.tbm`.) | REFERENCE ��� not a 2170 cell. |

### Known issues in `hp2170NCA-ECM.tbm` (source)

These issues exist in the source file and are corrected by `tools/generate_tbm_test_variants.py` for the test variant packages:

| Field | Source value | Correct value | Fixed in generate script |
|---|---|---|---|
| `Package m_dintDiameter` | 17.8 mm | 20.6274 mm (can ID) | Yes |
| `Package m_dintHeight` | 60 mm | 65.11 mm (jelly-roll height) | Yes |
| `Package m_strName` | `18650` | `2170` | Yes |
| `m_dElectrodeOverlapAtStart_mm` | 0 | 8 mm | Yes |
| `m_dMandrelWidth_mm` | 0 | 6 mm | Yes |
| `m_bOnly1D` | 1 (all 4 blocks) | 0 | Yes (package_rev3 onward) |
| `m_nNegTabVertOrientation` | 1 (bottom) | 0 (top, same-face) | Yes (variant-dependent) |

Still open in source and NOT yet fixed by the generate script:
- `m_dJellyrollThickness_mm = 19.25` (current value; can ID is 20.6274 mm; correct winding OD remains unresolved)
- Active `RCRTable 3D`: `m_bSpecifyCapacity = 1`, `m_dAhCell = 5.0`; whether STAR interprets the override as intended remains unconfirmed.
- `DataSheet m_dDSHeight = 65` (should be 70.02 mm = can external height)
- `m_dElectrodeOverlapAtEnd_mm = 20` — not verified from cell spec
- `m_dSepFeedLength_mm = 0`, `m_dSepTailLength_mm = 0` — not verified

---

## Reference TBMs (`tbm_validation/reference/`)

Siemens stock TBMs. Preserved byte-exact. These are NOT 2170 cells — they are used for structural comparison only.

| File | SHA-256 | Cell | Notes |
|---|---|---|---|
| `HE18650/he18650spiral1.tbm` | `f9171ff23582854e4c3cc9ff6fe506efe0f8fe90b13c8a39cc9ad56169999ef1` | HE18650 (high-energy 18650) | Used as primary reference for field-by-field comparison. Known to import successfully in STAR-CCM+. `m_bOnly1D` absent from this file. |
| `HP18650/hp18650Spiral-DIST.tbm` | `604f18c2844d07af77ba593f6d43afb1a66924560b490ab3d1891327dd950666` | HP18650 (high-power 18650) | Distributed mode reference. Has `m_bOnly1D = 1` in ALL 4 SIMMOD blocks. Import status in STAR-CCM+ 3D mode UNKNOWN. |
| `GapExample/hp18650Spiral1.tbm` | `c0edc8f31bd21bd028b5c05a605057bb3f50471689f42749a00ec98cacdcff8b` | HP18650 | **Our direct clone template.** The `m_bOnly1D` pattern in this file: first=1, remaining=0/false. |
| `GapExample/hp18650Spiral1-1D.tbm` | `9f551a1ed0d1d766529f82795e98d720b1aec65f9afdb0f187613e7a1cf70c87` | HP18650 | 1D-only variant. `m_bOnly1D = 1` throughout. Not used. |
| `CompareChem/HV-LiCoO2f.tbm` | `61825772b3d9ce381e17f9871c058d884ced1b647f61f4d18f9b049aaf9a11b5` | LiCoO2 (different chemistry) | HV chemistry reference. Has `m_bOnly1D = 0` (or `false`) throughout �� represents an alternative known-clean pattern. |
| `LiIonSpiral-VarDiffCoeff.tbm` | `aef1e0031525cf8f56c9a7b8098865abf5a73956df93d7f5ad11a125fa91da9a` | LiIon spiral | Variable diffusion coefficient variant. Secondary reference. |

---

## Siemens Stock TBMs from STAR-CCM+ Installation (`tbm_validation/in_StarCCM_bds/`)

These were extracted from the STAR-CCM+ installation. They are STAR-CCM+ internal reference files, not our deliverables.

| File | SHA-256 | Notes |
|---|---|---|
| `LiIonSpiral.tbm` | `c9ef515dd9787a4d4d89994a73d8c40091a65c14a422d4d40149f12516d770d7` | General LiIon spiral template from STAR-CCM+ install. |
| `testTBM.tbm` | `21a1558c0df4134cceab3ef58a960c23dca09627db71f4cbfc03c24dc40f9f7f` | Test TBM from STAR-CCM+ install. |
| `tutorialCylindricalCell.tbm` | `7c3dfb1c77c38187b0ddbba48c024b047239e6f9cc020def34757fc065b95be2` | Tutorial cylindrical cell from STAR-CCM+ install. |
| `validationBattery.tbm` | `82aa9daa6a7e9a4218bb8eb5e3aad2fdfb299a3031deede89523715a542dffee` | Validation battery from STAR-CCM+ install. |

---

## Variant packages — geometry test

### v1 package — 2026-09-04 (`tbm_validation/variants/v1_package_20260904/`)

Fixes applied vs source: Package m_dintDiameter, m_dintHeight, m_strName.
`m_dElectrodeOverlapAtStart_mm` was still 0. `m_bOnly1D` still 1.

| File | SHA-256 | Status |
|---|---|---|
| `hp2170-test-v1-tabs-on-standard.tbm` | `be80e87f670add175e4525c066fca87cbb62f60e213d6bacde246e8c40f10bbf` | FAILED — "Electrode Root 1 : Extrusion distance can not be 0" |
| `hp2170-test-v2-tabs-off-standard.tbm` | `fec98c831d471df3a9aee20ba9d3168dc751a0d95020a8630588ea0e5493aa0d` | FAILED — same error |
| `hp2170-test-v3-tabs-on-sameFace.tbm` | `388e6481df04b9c7357a0f65b592484fac95bcdcb7448d7c1f5fc921b0635743` | FAILED — same error |
| `hp2170-test-v4-tabs-off-sameFace.tbm` | `c3e1f61cac6de1b5442c003bdd3707095be1d7f20dfbda07c9a2458e8094d7ca` | FAILED — same error |

### v2 package — 2026-09-07 (`tbm_validation/variants/v2_package_20260907/`)

Fixes added vs v1: `m_dElectrodeOverlapAtStart_mm = 8`, `m_dMandrelWidth_mm = 6`.
`m_bOnly1D` still 1.

| File | SHA-256 | Status |
|---|---|---|
| `hp2170-test-v1-tabs-on-standard.tbm` | `9dea2c6a70b5701b5fa97d8b24fe8cdcb092928d82844e5845e945b17b727a9c` | FAILED — "Warning: m_bOnly1D option is not supported" ×2, then failure |
| `hp2170-test-v2-tabs-off-standard.tbm` | `ecff71c4fcdf55d0304305d959136f9322101f91d5d2e9646129892f1d51f527` | FAILED — same error |
| `hp2170-test-v3-tabs-on-sameFace.tbm` | `918cf52a0df655a23b3987b749cbf0218743883a307020ee8f8c1b6022246337` | FAILED — same error |
| `hp2170-test-v4-tabs-off-sameFace.tbm` | `946c7553bafc0a7112283d61dc8e67525dd2562341cbd187f312fa2f67abd3fb` | FAILED — same error |

### package_rev3 — 2026-09-09 (`tbm_validation/variants/v3_package_20260909/`) — CURRENT

Fixes added vs v2: `m_bOnly1D = 0` (all 4 SIMMOD blocks).

Static validator result: **0 FAIL, 11 WARN, 29 PASS** per file (identical result for all 4 variants).
STAR-CCM+ import status: **PENDING** — not yet tested by Robert.

| File | SHA-256 | Static validator | STAR import |
|---|---|---|---|
| `hp2170-test-v1-tabs-on-standard.tbm` | `cae78b4d66204b18898ce081252a1aae4fbf53f6cb325b77310690f727e411ad` | 0 FAIL 11 WARN | PENDING |
| `hp2170-test-v2-tabs-off-standard.tbm` | `9f388fdf2a177a01d0441ce5ef5a24d06ae2104491a73db3ef955eeff7393593` | 0 FAIL 11 WARN | PENDING |
| `hp2170-test-v3-tabs-on-sameFace.tbm` | `e03d2eaf97cf21d0a16e24bb503ab632bd1a2b0c17dfb0d3b6d8d1cbf8011c81` | 0 FAIL 11 WARN | PENDING |
| `hp2170-test-v4-tabs-off-sameFace.tbm` | `9a973f4de048907520d8b48f592dab2d2c29e3d120b2db97a5c29bbacfcd8329` | 0 FAIL 11 WARN | PENDING |

Remaining WARNs in package_rev3 (not blocking import but need resolution before production):
1. `m_dJellyrollThickness_mm = 19.25` — 1.38 mm gap to can ID 20.627 mm
2. `DataSheet m_dDSHeight = 65.0` vs `Package m_dextHeight = 70.02`
3. Active RCRTable 3D capacity override is `m_bSpecifyCapacity = 1`, `m_dAhCell = 5.0`; confirm STAR interprets it as intended and that geometry-derived quantities remain internally consistent.

---

## RCR Distributed Candidate (`out/rcr_candidate/`)

### V1 — 2026-09-09 (Robert-tested; FAILED)

**Do not overwrite. Retained as runtime evidence baseline.**

| File | SHA-256 | Status |
|---|---|---|
| `hp2170-rcr-v1-tabs-on-sameFace.tbm` | `7d5850b628389e713e83468d27e45600942b1deb1e23e672f9d18c4f580d6940` | FAILED — "Electrode Root 1 : Extrusion distance can not be 0" (2026-09-09) |

V1 source: `out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm` (prior SHA `24eacae56e40d826f162046bc63131f7c590b3c5d72dec80828c7e6a5520667f`) + MODELMAP IET switch to RCRTable 3D. Had `+Electrode m_dS3 = 0` (1D-mode placeholder, never corrected in V1 generator).

### V2 — 2026-09-10 (S3 geometry fix; PENDING Robert test)

| File | SHA-256 | Validator | STAR import |
|---|---|---|---|
| `hp2170-rcr-v2-S3fix-tabs-on-sameFace.tbm` | `372c99026580732866708f0f45906caa74733a826e816fdf2d7de0b416ca0e3b` | 0 FAIL 4 WARN | PENDING |

V2 source: `out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm` (new SHA `e645ab18ad5da81b8a90646743051e8a2e3259d745a2d683589154ad68c12b26`, regenerated with S3 fix) + MODELMAP IET switch.

Delta vs V1: exactly one semantic field — `+Electrode m_dS3 = 0 → 5`.
Evidence: all 4 STAR-install cylindrical references use S3=5; BDS-generated source had S3=0 (1D-mode placeholder). See `STAR_GEOMETRY_COMPATIBILITY_AUDIT_20260910.md` and `RCR_V1_TO_V2_S3_GEOMETRY_DELTA_20260910.md`.

Client package: `out/hp2170NCA-RCR-STAR-import-test-S3fix-20260910.zip` (SHA-256: `ec6df0c5918667d76c82c4610decfc2ff7f9cf8e3b319c7769d1c52c7c595830`)

### V3 — 2026-09-10 (maximum static preflight; PENDING Robert test)

| File | SHA-256 | Bytes | Validator | STAR import |
|---|---|---|---|---|
| `hp2170-rcr-v3-star-preflight-tabs-on-sameFace.tbm` | `91cb8f8a2069c308db8dd910a695a2e7bbf55cca509330df004fa8ce82f638d4` | 304337 | 0 FAIL 4 WARN 14 INFO 37 PASS | PENDING |

V3 base: `out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm` (SHA `2cd3b503559e5ed0dd060d7b26cd555121cd224e40d91fe6c2b96dc23a7c8afd`, regenerated with Transport Number sets fix) + MODELMAP IET switch to RCRTable 3D.

Delta vs V2: exactly one field inserted — `Transport Number sets = 0` in General Electrolyte SIMMOD block (+29 bytes).
Evidence: all 4 STAR-install cylindrical references contain this field; Robert's V1 runtime log (2026-09-09) confirmed "Transport Number sets not found in the file, defaulting to 0."
See `RCR_V2_TO_V3_TRANSPORT_NUM_DELTA.md` and `STAR_MAXIMUM_STATIC_PREFLIGHT_20260910.md`.

Client copy: `out/hp2170NCA-RCR-distributed-final-preflight.tbm` (byte-identical; SHA `91cb8f8a2069c308db8dd910a695a2e7bbf55cca509330df004fa8ce82f638d4`)
Client package: `out/hp2170NCA-RCR-STAR-final-preflight-20260910.zip`

**FREEZE: no further RCR candidate TBM changes until Robert returns runtime evidence on V3.**

---

## JR OD Test Variants (`out/jr_od_test/`) — 2026-09-10

Purpose: determine the correct `m_dJellyrollThickness_mm` value for the 2170 NCA cell. The OpenFOAM-ECM `wedge_2170` case has JR OD = can ID = 20.6274 mm (zero gap, shared face). The current V3 TBM has 19.25 mm, leaving a 1.3774 mm diametral gap with no equivalent in the OpenFOAM thermal model.

**Evidence source:** `cases/wedge_2170/constant/jellyRoll_rotated/polyMesh/points` — max radial coordinate = 0.010314 m → JR OD = 20.6274 mm = Package m_dintDiameter (can ID). Measured directly from the mesh, 2026-09-10.

**Winding formula (from August 2026 characterisation):** realised OD = Detailed Builder `m_dJellyrollThickness_mm` ± <0.1 mm (monotonic, Detailed Builder is the sole driver — REPORT and Simple Builder fields not consumed).

Both variants are based on the frozen V3 preflight TBM (SHA `91cb8f8a...`). Only `m_dJellyrollThickness_mm` differs (line 2110).

| File | Input JR OD | Gap to can ID | SHA-256 | STAR import |
|---|---|---|---|---|
| `hp2170-jr-safe_20p55.tbm` | 20.55 mm | 0.077 mm | `62a11705f39890d1fe5d27c7ef98f7ce8155cb8acc4e7b2b746cb95adfea37f6` | PENDING |
| `hp2170-jr-perfect_contact_20p6274.tbm` | 20.6274 mm | 0.000 mm | `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5` | PENDING |

Package: `out/hp2170NCA-JR-OD-test-20260910.zip`
Generator: `tools/generate_tbm_jr_od_test.py` (SHA-pinned to V3 base)

**Decision tree on Robert's result:**
- `perfect_contact` succeeds → 20.6274 mm is the production value; WARN 1 (`jr_od`) closes
- `perfect_contact` fails with feasibility guard → `safe_20p55` is the production value; request STEP + JR OD measurement
- Either way, 19.25 mm is retired in V4 RCR candidate

---

## E004 Diagnostic Campaign (`out/e004_multifile_campaign_20260910/`) — 2026-09-10

**Purpose:** Controlled multifile campaign to localize the persistent E004 fatal blocker:
`Electrode Root 1 : Extrusion distance can not be 0.`

**Baseline:** commit `d74b3283cb5d73e114bc141f3f0d18e7c7ed5463`, `out/hp2170NCA-RCR-distributed-exact-contact-final.tbm`, SHA `2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5`

**Generator:** `tools/generate_e004_multifile_campaign.py` (deterministic, SHA-pinned)

**Client package:** `out/hp2170NCA-STAR-E004-multifile-diagnostic-20260910.zip`, SHA `5bfb50497d0489e7cd98b9fe7cd679d9c102f4ef5fd136facb32ee7d7a44e84e`

| File | SHA-256 | Changed fields | STAR import |
|---|---|---|---|
| `C00_SIEMENS_CONTROL_validationBattery.tbm` | `82aa9daa6a7e9a4218bb8eb5e3aad2fdfb299a3031deede89523715a542dffee` | N/A — unmodified Siemens reference | PENDING |
| `C01_FEED10.tbm` | `912db12a2183209f2ad4f49c776b176765db6b82cfa8367c532b08ddd62732c7` | SepFeedLength_mm: 0→10 | PENDING |
| `C02_TAIL85.tbm` | `7596ff01f4f43218ba60484b53b59cd9d52994ff8f9735d50621b27c57ad449a` | SepTailLength_mm: 0→85 | PENDING |
| `C03_FEED10_TAIL85.tbm` | `bf0d6c3e5c22cd3f07a48a2b57be56b1dae36f174610ed648fc36dcdacb80b53` | SepFeedLength_mm: 0→10; SepTailLength_mm: 0→85 | PENDING |
| `C04_END40.tbm` | `6e737ca16035da37aa2118f700e38a004f500a17cfebff31368d72e96f82ce80` | ElectrodeOverlapAtEnd_mm: 20→40 | PENDING |
| `C05_FEED10_TAIL85_END40.tbm` | `90d289c9d2e6f20e2759f0dbcf1b7d4327f42bb4c7c7ba4eae0ee04f2f54e5a9` | Feed=10; Tail=85; OverlapEnd=40 | PENDING |
| `C06_MANDRELWIDTH0.tbm` | `49f4f6f50d57db2dc3aed63ca37733ca0cdd51fe41280d7805f4dd7a5475ce36` | MandrelWidth_mm: 6→0 | PENDING |
| `C07_FEED10_TAIL85_MANDRELWIDTH0.tbm` | `e418b2f09c0ea957d25607fe7e90df079e3e6da7b2564350eaaeffd5f06654c4` | Feed=10; Tail=85; MandrelWidth=0 | PENDING |
| `C08_JRWIDTH65p11.tbm` | `a271bfbd6c7012bf9fb9f8543706804c0048594323f4a92047e6967a71acbc88` | JellyrollWidth_mm: 0→65.11 | PENDING |
| `C09_FEED10_TAIL85_JRWIDTH65p11.tbm` | `364501027db55ce8974224aa20ae9b8e20a515ac10b3c9d6139dd9af18f8387e` | Feed=10; Tail=85; JRWidth=65.11 | PENDING |
| `C10_STAR_BUILDER_PATTERN.tbm` | `08252a958eeacc8157d906637e3d2416d1b7baa74f4e21f7d5f87529c0ad8984` | Feed=10; Tail=85; OvStart=3; OvEnd=40; MandrelWidth=0 | PENDING |
| `C11_STAR_BUILDER_PATTERN_JRWIDTH65p11.tbm` | `5726c52ff9be146705f9d6ced6bf502ac03c39524ef4f8e379c85e436f2531e6` | All C10 + JRWidth=65.11 | PENDING |
| `C12_FULL_SIEMENS_DETAILED_BUILDER.tbm` | `94e0fef9b7cb4199103dd462b960be5a26f08d78a5829489c9683bfd25b31c8f` | Complete Siemens BUILDER block transplant | PENDING |
| `C13_SIEMENS_GEOMETRY_SHELL_PROJECT_RCR.tbm` | `606b2ccd3d774e90d25f03a55157f7f6acb1dbcdf21da9274a8fab3d06c67d8d` | Siemens PCD + BUILDER; project SIMMOD/RCR retained | PENDING |

All STAR import results PENDING — awaiting Robert's runtime test.
