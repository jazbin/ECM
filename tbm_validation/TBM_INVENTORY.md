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
| `m_bOnly1D` | 1 (all 4 blocks) | 0 | Yes (v3 onward) |
| `m_nNegTabVertOrientation` | 1 (bottom) | 0 (top, same-face) | Yes (variant-dependent) |

Still open in source and NOT yet fixed by the generate script:
- `m_dJellyrollThickness_mm = 19.25` (should be ~20.627 mm to match can ID)
- `m_dAhCell = 0`, `m_bSpecifyCapacity = 0` (capacity derived from geometry)
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

### v3 package — 2026-09-09 (`tbm_validation/variants/v3_package_20260909/`) — CURRENT

Fixes added vs v2: `m_bOnly1D = 0` (all 4 SIMMOD blocks).

Static validator result: **0 FAIL, 3 WARN, 25 PASS** per file (identical result for all 4 variants).
STAR-CCM+ import status: **PENDING** — not yet tested by Robert.

| File | SHA-256 | Static validator | STAR import |
|---|---|---|---|
| `hp2170-test-v1-tabs-on-standard.tbm` | `cae78b4d66204b18898ce081252a1aae4fbf53f6cb325b77310690f727e411ad` | 0 FAIL 3 WARN | PENDING |
| `hp2170-test-v2-tabs-off-standard.tbm` | `9f388fdf2a177a01d0441ce5ef5a24d06ae2104491a73db3ef955eeff7393593` | 0 FAIL 3 WARN | PENDING |
| `hp2170-test-v3-tabs-on-sameFace.tbm` | `e03d2eaf97cf21d0a16e24bb503ab632bd1a2b0c17dfb0d3b6d8d1cbf8011c81` | 0 FAIL 3 WARN | PENDING |
| `hp2170-test-v4-tabs-off-sameFace.tbm` | `9a973f4de048907520d8b48f592dab2d2c29e3d120b2db97a5c29bbacfcd8329` | 0 FAIL 3 WARN | PENDING |

Remaining WARNs in v3 (not blocking import but need resolution before production):
1. `m_dJellyrollThickness_mm = 19.25` — 1.38 mm gap to can ID 20.627 mm
2. `DataSheet m_dDSHeight = 65.0` vs `Package m_dextHeight = 70.02`
3. `m_bSpecifyCapacity = 0` — capacity derived from geometry (may be wrong if JR dims still off)
