# TBM Geometry Degree-of-Freedom Matrix

**Baseline:** T06 returned STEP. Dimensions are nominal STEP geometry; OpenFOAM targets come from the raw reference mesh. Status vocabulary is limited to `CONFIRMED`, `SUPPORTED`, `OPEN`, and `NOT YET CHARACTERIZED`.

| Production-relevant quantity | OpenFOAM target | Current T06/generated value | Known controlling TBM field(s) | Evidence status | Confidence | Current mismatch | Requires new Robert test? |
|---|---|---|---|---|---|---|---|
| JR OD | 20.62736 mm | 17.880992 mm | Detailed Builder `m_dJellyrollThickness_mm` | CONFIRMED in August class; T06 transfer OPEN | high / medium | -2.746368 mm | Yes: RAD-C validates this class |
| JR height | 65.11000 mm | 65.11000 mm | H/T axial field bundle, especially electrode widths; not isolated | SUPPORTED | medium | none | No immediate test for value; mapping remains open |
| JR axial position | bottom 0.23132, top 65.34130 mm in cell frame | nominal 0..65.11 mm; centred within Can envelope | placement follows JR/envelope construction; no isolated field | OPEN | low | target is asymmetric in cell frame | Yes |
| JR top position relative to Can | flush with Can wall top; touches Cap | Can extends 2.445 mm beyond JR | likely external envelope/end-stack fields; exact control unknown | OPEN | low | +2.445-mm generated end space | Yes: axial-envelope test |
| JR bottom position relative to Can | 0.23132 mm above Can bottom; full-disc contact | Can extends 2.445 mm below JR; no Can bottom disc | likely external envelope/end-stack fields; exact control unknown | OPEN | low | wrong spacing and wrong domain topology | Yes |
| Can OD | 21.09 mm | 20.90 mm | REPORT `m_dRepCanXDim/YDim` inferred from August data; package `m_dextDiameter` competing | SUPPORTED | medium | -0.19 mm | Yes: RAD-B |
| Can ID | 20.62736 mm | 18.00 mm | package `m_dintDiameter` candidate | OPEN | low | -2.62736 mm | Yes: RAD-A |
| Can radial thickness | 0.23132 mm | 1.45 mm | derived from OD and ID drivers | OPEN | low | +1.21868 mm | Resolved by RAD-A/B combination |
| Can bottom thickness/domain | 0.23132-mm integral solid Can bottom | none; Can is annular tube | no identified field/topology control | NOT YET CHARACTERIZED | low | missing Can bottom domain | Yes, after offline field selection |
| Cap/end-equivalent height | top-only 4.67870 mm | two EndPlates, each 0.059504 mm | EndPlate thickness control unidentified | NOT YET CHARACTERIZED | low | wrong height and mirrored bottom part | Yes |
| Cap/end-equivalent radial extent | radius 10.545 mm | EndPlate radius 10.45 mm | follows generated Can OD in current files; independent control unknown | OPEN | low | -0.095 mm radius | Measure in RAD-B and end test |
| JR↔Can radial gap | 0; coincident contact | +0.0595041 mm | derived from JR OD and Can ID drivers | OPEN | high geometry / low control | positive gap | RAD-A/C then exact-contact test |
| JR↔Can bottom gap/contact | zero; full disc, explicit thin resistance | no Can bottom; localized -Root touches JR; EndPlate 2.385496 mm away | end-stack/topology controls unknown | NOT YET CHARACTERIZED | high mismatch | operator topology absent | Yes |
| JR↔top-Cap gap/contact | zero; full disc | localized +Root touches JR; EndPlate 2.385496 mm away | surplus controls internal bridge partition; full-face control unknown | NOT YET CHARACTERIZED | high mismatch | operator topology absent | Yes |
| Central void / Mandrel volume | none; full JR to axis | radius-3-mm Mandrel, 1840.941879 mm³; annular JR | Detailed/Simple Builder Mandrel width/thickness fields; valid suppression route unknown | OPEN | medium | extra domain plus central subdivision | Yes |
| Top auxiliary stack extent | no auxiliary stack; Cap occupies 0..4.6787 mm above JR | Root bridge to fixed EndPlate; Can end 2.445 mm above JR | tab surplus partitions Root/Stem/Washer/Post; envelope control unknown | SUPPORTED | high | five auxiliary solids and wrong extent | Yes for envelope/topology |
| Bottom auxiliary stack extent | no auxiliary stack; integral 0.23132-mm Can bottom | mirrored Root bridge to EndPlate; Can end 2.445 mm below JR | same coupled controls as top | SUPPORTED | high | mirrored five-solid stack replaces bottom wall | Yes for topology |
| Top contact graph | JR↔Cap full face; Can↔Cap planar annulus | JR→Root→Stem→Washer→Post→EndPlate, all touching; EndPlate overlaps Can | surplus affects internal partition; topology driver unknown | CONFIRMED geometry | high | different nodes, contacts, and overlap | Yes |
| Bottom contact graph | JR↔Can full face | same mirrored five-body chain; EndPlate overlaps Can | topology driver unknown | CONFIRMED geometry | high | extra bottom Cap-equivalent and no Can bottom | Yes |
| Can↔end relationship | Can↔Cap coincident planar annulus, zero overlap volume | Can overlaps each EndPlate by 5.272108319 mm³ | follows current Builder construction; control unknown | CONFIRMED geometry | high | volumetric overlap | Yes if overlap persists after radial scaling |

## What is already controlled well enough

- T06 fixes the importable root-validation state and the complete surplus plateau; no higher-surplus test has information value.
- JR height already equals the OpenFOAM target.
- All generated top/bottom relations and the Can-EndPlate overlap are exactly characterized for T06.

## Unknown classification

### Offline-resolvable before another Robert run

1. Search existing TBM/reference variants for candidate flags or Builder fields that suppress Mandrel and polarity-specific auxiliary parts.
2. Reconcile the August returned STEP matrix with its one-field TBM deltas to strengthen Can/JR control priors before choosing RAD values.
3. If thermal contact area becomes necessary, run a targeted existing-STEP Root/JR common-edge/contact-dimension calculation; no all-pair campaign is needed.

### STAR-runtime-required

1. operative Can ID control on the T06 geometry class;
2. operative Can OD control on the T06 geometry class;
3. JR OD control transfer to the T06 geometry class;
4. Can/end-envelope axial control and whether symmetric centring can be broken;
5. a route to full-area JR top contact and an OpenFOAM-equivalent top Cap;
6. a route to integral Can-bottom contact without a bottom Cap-equivalent;
7. a valid no-Mandrel/full-JR topology;
8. persistence or removal of Can-EndPlate volumetric overlap after production scaling.
