# Client return analysis — root-surrogate v2 — 2026-09-16

## Scope

Independent analysis of the client-returned STAR-CCM+ Battery Design Studio diagnostic package:

- client data branch: `client-data/20260916-tbm-root-surrogate-v2`
- raw package: `in/20260916/hp2170NCA-STAR-E004-root-surrogate-client-v2-TBM-only-20260914-PROCESSED.zip`
- client runtime result workbook: `hp2170NCA_STAR_TBM_runtime_results_20260914.xlsx` inside the returned package
- returned `.tbm` files
- returned `.step` CAD exports for successful imports
- STEP export logs

This note supersedes the runtime hypotheses in `TBM_EXTERNAL_AUDIT_20260914.md` where the returned data provide stronger evidence.

The governing modelling objective remains unchanged: reproduce the OpenFOAM-ECM reference model in a reusable TBM-native STAR cell, with no manual Part-module geometry corrections after import.

---

# Executive result

The returned campaign separates the previous single apparent failure into **two different mechanisms**.

| Runtime class | Cases | STAR result |
|---|---:|---|
| Success | 18 | `CreateFromTbm` succeeds |
| Root / E004 failure | 5 | `Electrode Root 1 : Extrusion distance can not be 0.` |
| Can / radial failure | 9 | `Can Thickness is -ve Check tbm file..`, sometimes preceded by a Jellyroll-vs-Can warning |

The E004 cases are:

- `H09`
- `H10`
- `T02`
- `T03`
- `T09`

All full-2170 F-series cases `F01` through `F09` fail on the **Can/radial construction path**, not E004.

Therefore:

1. the H/T series genuinely characterizes the root mechanism;
2. the F series does **not** test root/feed/tail/overlap behavior because it dies earlier on radial geometry;
3. the production radial field mapping must be characterized before further full-2170 Builder testing.

---

# 1. E004 is not an independent per-electrode `tab length - electrode width > 0` rule

The September 14 audit identified the strong correlation:

```text
root-surplus candidate = tab length - electrode width
```

That relation remains relevant, but the returned runtime data disprove the simple rule that **each individual electrode** must have positive surplus.

Define:

```text
Delta+ = positive tab length - positive electrode width
Delta- = negative tab length - negative electrode width
Delta_avg = (Delta+ + Delta-) / 2
```

Key returned cases:

| Case | Delta+ [mm] | Delta- [mm] | Delta_avg [mm] | Runtime |
|---|---:|---:|---:|---|
| D00 | +9.00 | +8.00 | +8.50 | PASS |
| H01 | 0.00 | +8.00 | +4.00 | PASS |
| H02 | +0.10 | +8.00 | +4.05 | PASS |
| H05 | +9.00 | 0.00 | +4.50 | PASS |
| H06 | +9.00 | +0.10 | +4.55 | PASS |
| H09 | 0.00 | 0.00 | 0.00 | **E004** |
| H10 | +0.10 | +0.10 | +0.10 | **E004** |
| H11 | +0.70 | +0.70 | +0.70 | PASS |
| T01 | +0.89 | -0.11 | +0.39 | PASS |
| T02 | 0.00 | 0.00 | 0.00 | **E004** |
| T03 | +0.10 | +0.10 | +0.10 | **E004** |
| T04 | +0.70 | +0.70 | +0.70 | PASS |
| T09 | -4.11 | -5.11 | -4.61 | **E004** |

Critical observations:

- `H01` passes with positive-electrode surplus exactly zero.
- `H05` passes with negative-electrode surplus exactly zero.
- `T01` passes even though the negative-electrode surplus is slightly negative (`-0.11 mm`).
- `H09` / `T02` fail when both sides are zero.
- `H10` / `T03` fail when both sides are only `+0.10 mm`.
- `H11` / `T04` pass when both sides are `+0.70 mm`.
- `T09`, where both surpluses are strongly negative, fails with E004.

Within the returned H/T dataset, `Delta_avg` gives a perfect empirical separation:

```text
Delta_avg <= 0.10 mm  -> E004
Delta_avg >= 0.39 mm  -> PASS
```

This is an **empirical campaign result**, not a claimed Siemens proprietary formula. The exact BDS construction can still depend on other coupled geometry quantities. The threshold is only bracketed by the tested values:

```text
0.10 mm < transition <= 0.39 mm
```

The production generator should therefore **not** implement the old validator rule "each surplus must be > 0" as a proven Siemens law.

A safer interim diagnostic rule is:

- flag very small combined/mean available tab-root extension;
- treat `Delta_avg <= 0.10 mm` as runtime-proven unsafe for the tested geometries;
- treat `Delta_avg >= 0.39 mm` as runtime-proven constructible for the tested H/T geometries;
- keep the exact threshold/mechanism explicitly empirical until further characterized.

---

# 2. Returned STEP geometry confirms that root construction is coupled

The successful STEP exports materially strengthen the runtime result.

The H-series cases that vary only one tab (`H01-H08`) generate the same overall component topology, and the corresponding root/stem geometry is effectively saturated by the long opposite-side tab.

This means a zero nominal surplus on one side is not translated directly into a zero solid extrusion on that side.

The cases where both tabs are shortened show a more useful progression. Returned STEP measurements indicate the generated Tab Root / Tab Stem dimensions respond to the **combined available geometry**, then saturate when the package/end-space limit is reached.

Representative target-stack cases:

| Case | Approx. mean surplus [mm] | Approx. generated mean Tab Stem axial extent [mm] | Runtime |
|---|---:|---:|---|
| T01 | 0.39 | 0.425 | PASS |
| T04 | 0.70 | 0.668 | PASS |
| T05 | 1.00 | 0.953 | PASS |
| T06 | 2.00 | 1.108 | PASS |
| T07 | 5.00 | 1.108 | PASS |
| T08 | 8.50 | 1.108 | PASS |

The important production consequence is that very large tab surplus is unnecessary. In this target axial stack, the generated root/stem geometry is already saturated by approximately the T06 condition. T06/T07/T08 produce the same practical end geometry to numerical measurement tolerance.

Therefore T06 is a better basis for the next radial characterization than T08: it is safely away from E004 without carrying unnecessarily extreme tab lengths.

---

# 3. The F-series failure is a separate radial / Can construction defect

All nine F-series files fail before the campaign reaches the intended root/feed/tail/overlap discriminators.

The STAR errors are of the form:

```text
Warning: Jellyroll outer diameter is greater than Can inner diameter.
Can inner diameter set to JR outer diameter.

Can Thickness is -ve Check tbm file..
```

or directly:

```text
Can Thickness is -ve Check tbm file..
```

Every F-series file contains the target radial values introduced under the previous field interpretation:

```text
Package m_dextDiameter        = 21.09
Package m_dintDiameter        = 20.6274
m_dJellyrollThickness_mm      = 20.6274
```

The previous assumption was:

```text
Package m_dintDiameter == physical Can ID
```

The returned successful STEP files contradict that assumption.

---

# 4. Direct STEP evidence: `Package m_dintDiameter` behaves like generated Can OD in this BDS path

In the successful H/T STEP exports, the generated `Can` solid measures approximately:

```text
Can outer diameter  ~= 20.900 mm
Can inner diameter  ~= 18.000 mm
Jellyroll diameter  ~= 17.880992 mm
```

The corresponding successful TBM fields are:

```text
Package m_dintDiameter        = 20.9
m_dRepCanXDim                 = 18
m_dRepCanYDim                 = 18
m_dJellyrollThickness_mm      = 17.9
```

The observed geometry therefore maps very strongly as:

```text
20.9  -> generated Can outer cylindrical diameter
18.0  -> generated Can inner cylindrical diameter
17.9  -> generated Jellyroll diameter (realized ~17.881)
```

This is direct CAD evidence and supersedes the previous semantic interpretation based only on the field name `m_dintDiameter`.

Important wording:

- **Observed behavior:** `Package m_dintDiameter` corresponds to the generated Can OD in the returned successful STEP geometry.
- **Not yet proven:** the exact internal Siemens/BDS formula or whether `m_dRepCanXDim/YDim` alone universally define the Can ID in every Builder configuration.

This distinction matters because the field names are misleading relative to the observed generated geometry.

---

# 5. Why the full-2170 F geometry fails

The F series sets:

```text
Package m_dintDiameter       = 20.6274
m_dJellyrollThickness_mm     = 20.6274
```

Under the mapping observed in successful STEP files, this is effectively asking BDS to construct the Can outer radial scale and Jellyroll outer radial scale at essentially the same diameter.

STAR then attempts to reconcile the Jellyroll with the Can cavity and reaches a non-positive wall thickness, producing:

```text
Can Thickness is -ve Check tbm file..
```

So Claude Code's high-level statement that the F series has a zero-clearance radial defect is directionally correct, but the more precise conclusion from the returned STEP files is:

> The production field mapping was wrong: `Package m_dintDiameter` must not be treated as the generated physical Can ID in this Detailed Builder workflow.

The failure is not simply "JR OD equals a correctly identified Can ID". It is that the wrong TBM field was assigned the desired 20.6274-mm physical Can-ID target.

---

# 6. Working control does not have a 3-mm JR-to-Can clearance

It is incorrect to infer the working radial clearance from:

```text
20.9 - 17.9 = 3.0 mm
```

because the returned STEP geometry shows the `20.9` value on the **outer** Can surface.

Actual generated successful geometry is approximately:

```text
Can ID     = 18.000 mm
Jellyroll  = 17.881 mm
```

Therefore the diametral gap is only:

```text
18.000 - 17.881 = 0.119 mm
```

or about:

```text
0.0595 mm radial clearance
```

The same control also generates an unusually thick Can wall:

```text
(20.9 - 18.0) / 2 = 1.45 mm
```

Thus the client working 21700 TBM is valuable as a **BDS construction reference**, but its generated radial dimensions are not yet the desired OpenFOAM-equivalent physical shell geometry.

---

# 7. Likely target radial field mapping for the production 2170

OpenFOAM/reference target remains:

```text
physical Can OD = 21.09 mm
physical Can ID = 20.6274 mm
JR OD           = 20.6274 mm
```

Nominal physical shell thickness:

```text
(21.09 - 20.6274) / 2 = 0.2313 mm
```

Based on returned STEP behavior, the next characterization should test a mapping approximately like:

```text
Package m_dintDiameter        -> 21.09      # candidate generated Can OD control
m_dRepCanXDim                 -> 20.6274    # candidate generated Can ID control
m_dRepCanYDim                 -> 20.6274
m_dJellyrollThickness_mm      -> ~20.6274   # candidate JR OD control
```

This is a **test hypothesis**, not yet a production prescription.

The exact mapping should be established with a small radial-only DOE using a proven safe axial/root configuration.

---

# 8. Package volume fields are ruled out as the observed F-series import blocker

`F04` and `F09` are identical for the relevant geometry except that F09 synchronizes the package volume fields to the target dimensions.

F04 retains stale/reference-like volume values; F09 uses approximately:

```text
Package m_dextVolume = 24.4605 cm^3
Package m_dintVolume = 21.7584 cm^3
```

Both fail on the same Can/radial construction path.

Therefore:

```text
package-volume inconsistency != cause of the observed F-series import failure
```

The stale volume fields remain a production-consistency defect and should still be corrected, but they are removed from the import-blocker investigation.

---

# 9. F04/F05 does NOT test the separator feed/tail hypothesis

The intended discriminator was:

```text
F04: separator feed/tail = 10 / 85
F05: separator feed/tail = 0 / 0
```

However F04 already fails during Can/radial construction.

Therefore the campaign never reaches a state where F04/F05 can isolate the influence of feed/tail on root construction.

The same caveat applies to:

- F04 vs F06: overlap `3/40 -> 8/20`
- F04 vs F07: mandrel width and negative orientation changes
- F08: full project Builder configuration

These comparisons are **runtime-inconclusive** because all cases are blocked upstream by the radial Can defect.

Do not cite F04/F05 as evidence that `0/0` feed/tail is valid or invalid for the target full-2170 geometry.

The Siemens HP reference still provides an independent counterexample to any universal rule that feed/tail must be nonzero.

---

# 10. T09 is not an unexplained anomaly

`T09` uses:

```text
positive surplus = -4.11 mm
negative surplus = -5.11 mm
```

and fails with E004.

That does not contradict the returned H/T pattern. The data already prove that BDS root construction is not a direct independent extrusion equal to each individual `tab length - electrode width` value.

The useful pattern is coupled availability:

- one zero side with a large opposite surplus: PASS (`H01`, `H05`)
- one slightly negative side with enough opposite surplus: PASS (`T01`)
- both near zero: E004 (`H09`, `H10`, `T02`, `T03`)
- both strongly negative: E004 (`T09`)

T09 therefore strengthens, rather than weakens, the coupled-root interpretation.

---

# 11. Successful BDS topology is stable

The successful returned STEP files consistently contain the same 13-solid architecture:

```text
Mandrel
Jellyroll
Can
+Ve Tab Root
+Ve Tab Stem
-Ve Tab Root
-Ve Tab Stem
+Ve Washer
-Ve Washer
+Ve EndPlate
-Ve EndPlate
+Ve Internal-Post
-Ve Internal-Post
```

The root-surplus changes alter dimensions, not the component topology.

This is encouraging for the TBM-native production strategy: BDS is generating a reproducible component structure that can potentially be mapped to the required Jellyroll / Can / cap-equivalent roles without Part-module geometry repair.

However, material/thermal equivalence of the generated cap/end/tab solids remains unresolved and must not be inferred from successful CAD generation alone.

---

# 12. Updated status of previous September 14 audit findings

| Item | 2026-09-16 status |
|---|---|
| Individual root surplus must be positive | **REFUTED** |
| Root geometry associated with tab/electrode surplus | **SUPPORTED, but coupled rather than independent** |
| Exact E004 threshold/formula | **UNRESOLVED; bracketed empirically** |
| Package-height clearance as main E004 cause | **LOW PRIORITY / not supported by current campaign** |
| F-series tests exact-contact 2170 correctly | **FALSE; radial field mapping is wrong** |
| `Package m_dintDiameter` is physical Can ID | **REFUTED by returned STEP geometry in this workflow** |
| Stale package volumes cause F failure | **REFUTED by F04/F09** |
| Feed/tail `0/0` causes target full-cell failure | **NOT TESTED by F-series due earlier Can failure** |
| Cap-equivalent material mapping missing | **STILL OPEN** |
| Shell exact material mapping incomplete | **STILL OPEN** |
| RCR entropy activation | **STILL OPEN** |
| Active-area handling | **STILL OPEN** |
| Legacy lengths/masses | **STILL OPEN production consistency issue** |

---

# 13. Recommended next experiment: small radial characterization only

Do **not** run another broad 30-case DOE.

Use a proven safe axial/root configuration, preferably `T06`-like:

```text
positive surplus ~= 2 mm
negative surplus ~= 2 mm
```

T06 is preferred over T08 because the returned STEP geometry is already saturated at T06-like surplus; larger tab lengths add no geometric value.

Vary only the radial Can/Jellyroll control fields.

Primary candidate fields:

```text
Package m_dintDiameter
Package m_dextDiameter
m_dRepCanXDim
m_dRepCanYDim
m_dJellyrollThickness_mm
```

A 4-6 case campaign should be sufficient to establish which fields control:

1. generated Can OD;
2. generated Can ID;
3. generated Jellyroll OD;
4. realized radial clearance/contact behavior.

Target measurements from each successful STEP:

```text
Can OD = 21.09 mm
Can ID = 20.6274 mm
JR OD  ~= 20.6274 mm
```

Because the governing OpenFOAM model uses ideal/shared JR-can contact, a tiny BDS geometric clearance may be tolerated only as a CAD construction necessity; the final STAR thermal interface must still reproduce ideal contact unless an explicit contact resistance is later introduced as a controlled model parameter.

Once the radial mapping is established, re-run the project Builder changes (feed/tail, overlap, mandrel width/orientation) on the corrected radial base.

---

# 14. Production work remaining after geometry imports

A PASS from `CreateFromTbm` is still not production acceptance.

Outstanding items remain:

1. identify the TBM-native generated solid(s) that will represent the OpenFOAM cap/end region;
2. apply cap-equivalent thermal/material properties inside the TBM;
3. map shell density/conductivity exactly if STAR permits;
4. resolve `m_bUseEntropyData` / dU-dT activation without manual post-import edits;
5. prove active-area/capacity/resistance scaling is TBM-native and matches About-Energy/OpenFOAM reference;
6. reconcile or prove non-consumption of inherited winding-length/mass fields;
7. synchronize consumed REPORT/derived fields once field consumption is characterized;
8. verify final single-cell TBM remains reusable for arbitrary pack layouts/cell counts.

---

# Bottom line

The returned client package materially changes the diagnosis.

The geometry problem is now split into two tractable pieces:

```text
E004 root failure
  -> coupled tab/electrode root construction
  -> unsafe at tested mean surplus <= 0.10 mm
  -> constructible at tested mean surplus >= 0.39 mm
  -> T06-like geometry is safely saturated
```

and:

```text
full-2170 F-series failure
  -> separate Can/Jellyroll radial construction error
  -> caused by incorrect interpretation/mapping of the radial TBM fields
  -> `Package m_dintDiameter` does not behave as the physical Can ID in returned STEP geometry
```

The next highest-value action is therefore **radial field characterization**, not further E004/root sweeps.
