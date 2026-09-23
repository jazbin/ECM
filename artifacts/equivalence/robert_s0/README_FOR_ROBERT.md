# STAR-CCM+ Model Capability Check — S0 (for Robert)

Thanks for running this. This is **not a production simulation** — no long
solve, no result you need to interpret. It's a short capability check: we
need to know exactly what STAR does when it imports this cell geometry, so
we can design the next step correctly. Please just perform the actions
below, record what you observe, and send it back. You don't need to judge
whether an answer is "good" or "bad" — we'll do that on our end.

Total time: should fit in one STAR session (well under an hour of actual
setup/interaction, most of it import + a few reports/screenshots).

**Input file:** `input/T06_TARGET_AXIAL_SURPLUS_2p00.tbm` (included in this
package, unmodified).

Please fill in `ROBERT_RETURN_TEMPLATE.md` as you go, and check items off
`SCREENSHOT_CHECKLIST.md`. Send back the completed template + screenshots +
(if practical) the `.sim` files you create below.

---

<!-- INTERNAL TRACEABILITY — not for Robert to act on; IDs reference internal audit matrix -->
<!--
R0         → RUN-004 (STAR version), STAR-001 (13-Region confirmation)
S0-A       → STAR-008 (Can/JR overlap resolution), STAR-009 (Can/EndPlate overlap),
             STAR-012 (Can computational topology), GEO-022/023/024 (Region volumes)
S0-B       → STAR-003 (Mandrel↔JR interface), STAR-007 (Can↔JR across radial gap),
             STAR-010 (+Root↔JR area), STAR-011 (−Root↔JR area),
             TOP-001..015, IFC-001..006
S0-C       → STAR-005 (electrical role retained under thermal remapping),
             STAR-014 (Core Part + non-default k coexist),
             MAT-006 (JR anisotropic cylindrical k capability),
             MAT-012 (Cap-equivalent anisotropic k capability)
S0-D       → STAR-006 (−Tab thermal suppression while −Tab role preserved),
             STAR-013 (generic interface resistance capability)
Electrical context: current DIST-configured T06 baseline.
S0 is a capability gate, not an electrical-equivalence comparison.
-->

---

## R0 — Import and preserve a clean baseline

1. Record your exact STAR-CCM+ version/build (Help → About, or similar).
2. `File → New Simulation`, then `Create from Tbm` using the supplied
   `T06_TARGET_AXIAL_SURPLUS_2p00.tbm`.
3. **Do not modify the geometry.** Let STAR build Parts/Regions from the TBM
   as-is.
4. Save the simulation as `T06_S0_baseline.sim`.
5. If practical, please include this `.sim` file in what you send back —
   it may let us answer follow-up questions without asking you to reopen
   STAR.

This baseline is what S0-A and S0-B are performed on (read-only, no
modification). S0-C and S0-D each use their own separate *copy* of this
baseline — see below.

---

## S0-A — Region geometry / overlap resolution

**What we need to know:** does STAR's computational Region geometry keep the
overlapping solids from the original BDS/STEP export, or does it clip/resolve
them into non-overlapping volumes? We are not asking you to judge which
answer is correct — just report what STAR actually built.

**Actions (on `T06_S0_baseline.sim`):**

1. If practical, create a **Volume report** for each of the following
   Regions (all 13 if your STAR exposes all of them; at minimum these six):
   Can, Jellyroll, Mandrel, +Ve EndPlate, −Ve EndPlate, +Ve Internal-Post,
   −Ve Internal-Post.
2. If STAR also lets you report volume on the original **Geometry Parts**
   (pre-Region, i.e. the imported CAD bodies) separately from the Region
   volumes, please report those too — same list.
3. Create **one screenshot**: a centerline axial section view showing Can,
   Jellyroll, Mandrel, the top hardware stack, and the bottom hardware stack
   together. Please display the Region/computational geometry (not the raw
   imported Geometry Parts) if you have a choice.

**Can computational topology — additional question:**

After collecting the volume numbers, please record what STAR exposes for the `Can` Region's internal computational structure:

- Does `Can` appear as **one monolithic Region** with no further subdivision (A)?
- Does STAR expose **multiple separately addressable sub-regions, cell zones, or components** under `Can` (B)?
- Does STAR appear to have **automatically clipped or resolved** the Can volume against a neighbouring body (e.g., can you see a Can sub-volume that visually corresponds to the Jellyroll-occupied zone) (C)?

If you can see a Region tree or component hierarchy under `Can` in STAR's tree view, please take a screenshot of it and note what you observe. If STAR shows nothing below the `Can` Region, please record: `Can computational topology below Region level: NOT AVAILABLE`.

We are **not** asking you to split anything or assign materials — just record what STAR's UI exposes.

**What to return:** a simple table (CSV or text is fine) with columns
`object_name, object_type, volume_mm3`, where `object_type` is either
`Geometry Part` or `Region`. If STAR cannot report a given object's volume,
write `NOT AVAILABLE` for that row rather than skipping it. Plus the one
section-view screenshot and the Can topology note above.

(For your reference only, not something to comment on: our own solid-model
check of the exported STEP gives the Can body a solid volume around
6202 mm³, while our separate OpenFOAM reference model uses a thin-shell Can
around 1068 mm³. We're not asking you to reconcile these — just report
STAR's actual Region/Part volumes as built.)

---

## S0-B — Interface / contact topology

**What we need to know:** what interfaces/contacts did STAR actually create
between neighbouring Regions when it built the model — not what we'd expect
from the STEP geometry, but what STAR generated.

**Actions (on `T06_S0_baseline.sim`):**

Open the Interfaces (and/or Contacts) tree and inspect it directly — do not
infer connectivity from the geometry. For each of the following Region
pairs, record whether an interface/contact exists between them, and if so
its properties:

- Can ↔ Jellyroll
- Can ↔ Mandrel
- Can ↔ +Ve EndPlate
- Can ↔ −Ve EndPlate
- +Ve EndPlate ↔ +Ve Internal-Post
- −Ve EndPlate ↔ −Ve Internal-Post
- +Ve Internal-Post ↔ +Ve Washer
- −Ve Internal-Post ↔ −Ve Washer
- +Ve Washer ↔ +Ve Tab Stem
- −Ve Washer ↔ −Ve Tab Stem
- +Ve Tab Stem ↔ +Ve Tab Root
- −Ve Tab Stem ↔ −Ve Tab Root
- +Ve Tab Root ↔ Jellyroll
- −Ve Tab Root ↔ Jellyroll

Not every pair is expected to have an interface — just record what's
actually there (including "none").

**Interface area — additional column:**

For every interface/contact that exists, please also record the **interface area in mm²** as STAR reports it. Use STAR's actual computational interface or boundary area for that contact — do not infer it from the STEP geometry.

For these six pairs in particular, the area is **required** (not optional). If STAR does not expose a direct interface area report, a boundary/surface-area report for the actual STAR interface boundary is acceptable. If neither is available, write `NOT AVAILABLE` — do not calculate it manually:

- Can ↔ Jellyroll
- Mandrel ↔ Jellyroll
- +Ve Tab Root ↔ Jellyroll
- −Ve Tab Root ↔ Jellyroll
- Can ↔ +Ve EndPlate
- Can ↔ −Ve EndPlate

For the remaining pairs, area is optional — report if it is easily visible, otherwise skip.

<!-- INTERNAL REFERENCE — do not present these as pass/fail to Robert:
OF target interface areas (mm²):
  JR↔Can radial = 4213.953
  JR↔Can bottom = 332.483
  JR↔Cap top    = 332.483
  Can↔Cap annulus = 15.081
-->

**What to return:** for each pair where an interface/contact *does* exist, a table with columns:
`Region A | Region B | exists | interface/contact type | thermal coupling active | gap/resistance treatment | interface_area_mm2`

If a field is not available, write `NOT AVAILABLE`. Text/CSV is preferred. If that's impractical, screenshots of the full Interfaces tree plus the property panel for each interface are fine instead.

---

## S0-C — Thermal material independence + anisotropic conductivity capability

**What we need to know (two questions):**

**C.1 — Anisotropic conductivity:** Can STAR apply an anisotropic thermal conductivity tensor (three independent components: radial, tangential/azimuthal, axial) in a cylindrical coordinate frame to a Region inside a battery model? This is required for the Jellyroll, which needs (kr=1.4, kθ=1.4, kz=29) W/m·K, and for the Cap-equivalent region, which needs (kr=0.01, kθ=0.01, kz=0.1) W/m·K — neither is isotropic and neither aligns with a Cartesian frame.

**C.2 — Electrical role vs. thermal material independence:** can a single Region keep its electrical role (part of the positive/negative current path) while its *thermal* material is changed independently? We're using `+Ve Tab Stem` as the test Region.

**C.1 — Anisotropic conductivity check (on `T06_S0_baseline.sim`):**

Before copying to the material test sim, while you have the baseline open, please check and record:

1. Does STAR-CCM+ allow an anisotropic thermal conductivity model for a Region in this battery model (i.e. a conductivity tensor with independent kr, kθ, kz rather than a single scalar)? You can check this by looking at the material/physics properties for the Jellyroll (or any solid Region) and seeing whether a cylindrical anisotropic conductivity model is listed as a selectable option.
2. If anisotropic is available: does STAR support setting the conductivity in a **cylindrical coordinate frame** (not Cartesian)? I.e. can you specify kr (radial), kθ (circumferential/tangential), kz (axial) independently?
3. If both of the above are available: can you set **independent** values for all three directions (kr ≠ kθ ≠ kz)?

You do not need to change the actual Jellyroll material here — just check whether the capability exists and record what you see in the UI. If the option is not visible at all, write `NOT AVAILABLE`. If it is present but you are unsure whether cylindrical alignment is supported, please describe what coordinate frame options STAR offers. Take screenshots of the relevant property panels.

---

**C.2 — Electrical role vs. thermal material independence:**

**Setup:** make a **copy** of the baseline — `Save As` →
`T06_S0_material_test.sim`. Do not modify `T06_S0_baseline.sim` itself.

**Before making any change**, please record (this establishes the
"before" state):
- The current Core Parts, +Tab Parts, and −Tab Parts assignments.
- The Battery Cell / Unit Cell Model object status (does it show as valid?).
- Electrical mesh status.
- Confirm `+Ve Tab Stem` is currently listed as part of the positive
  electrical path (Core/+Tab Parts).

**Important — check continuum sharing before changing anything:**

In STAR-CCM+, thermal material/model properties are often controlled by the
Region's assigned **Physics Continuum**, not stored uniquely per-Region. If
several battery Regions share one continuum, changing a property on that
continuum would silently change it for all of them — not just
`+Ve Tab Stem`. Before making any change, please:

1. Identify which Physics Continuum is currently assigned to
   `+Ve Tab Stem`.
2. Check whether that same continuum is assigned to any other Region.
3. **If it is shared with other Regions, do not modify it directly.**
   Instead, duplicate it (or create a new continuum with the same
   models/settings) to get a temporary test continuum, assign only
   `+Ve Tab Stem` to that temporary continuum, and make the test change
   there. Leave every other Region's continuum assignment untouched.
4. If `+Ve Tab Stem` already has a continuum that is not shared with any
   other Region, you can change the property on it directly — no duplicate
   needed.

We're not prescribing exact menu steps here since that depends on your STAR
version's UI — use whatever mechanism duplicates a continuum in your
version. Please record what you did in the return template.

**The one change to make:** change *only* the thermal material/property of
the `+Ve Tab Stem` Region (via the isolated continuum, per above, if
needed) to a deliberately extreme test value — e.g. thermal conductivity
k = 0.01 W/m·K. This is a throwaway test value, not a production value.
Please do **not** change any electrical property, and please confirm no
other Region's thermal behaviour changed as a side effect.

**After the change**, record:
- Is `+Ve Tab Stem` still listed in +Tab Parts?
- Is the Battery Cell / Unit Cell Model still valid?
- Is the electrical mesh still valid?
- Can the battery model initialize/regenerate without error?
- Can a very short solve (just start it — a few iterations/timesteps is
  enough, not a full run) begin without error?

If STAR resets the material, throws an error, or invalidates the electrical
model at any point, please capture the **exact error/warning message** —
that detail matters more to us than a simple pass/fail.

---

## S0-D — Can the thermal path be suppressed while electrical role remains?

**Only do this after S0-C.** Same idea, going one step further: can we make a Region thermally "quiet" (not conducting heat into/out of it) while it still carries its electrical role?

**Test Region for S0-D: `−Ve Tab Stem`** (the negative/bottom electrical path, not the positive/top). If `−Ve Tab Stem` is not accessible in the Parts tree or is not listed as a distinct Region, use the closest available Region in the negative/bottom Tab stack (e.g., `−Ve Tab Root`, `−Ve Washer`, or `−Ve Internal-Post`) and note which one you used.

**Pre-check before starting D1–D4:** confirm that the test Region (`−Ve Tab Stem` or substitute) is currently assigned to `−Tab Parts` in the Battery Cell / Unit Cell Model. Record its current −Tab Parts assignment. If the Region is NOT listed in −Tab Parts (i.e., it has no electrical role at all), please note this and proceed anyway — but flag it.

**Setup:** make a fresh copy of the baseline — `Save As` → `T06_S0_thermal_path_test.sim`. Do not modify the other two `.sim` files.

**Same continuum-sharing caution as S0-C applies here.** Before D1–D4, re-check whether `−Ve Tab Stem`'s Physics Continuum is shared with other Regions. If it is, use an isolated/duplicated temporary continuum (as in S0-C) for any continuum-level change. For D3/D4, which act on the *interface* between `−Ve Tab Stem` and its neighbour rather than on the continuum, this may not apply — just confirm the interface change doesn't affect any other interface.

Try each of these four, in order, and for each one record: was it possible?, did the electrical assignment remain intact?, did the Battery Cell / Unit Cell Model remain valid?, and did every other Region's thermal setup remain unchanged?

1. **D1** — Set a very low thermal conductivity on the Region (similar to S0-C) while explicitly confirming the negative electrical assignment is preserved.
2. **D2** — Check whether the Energy (thermal) model can be disabled or the Region excluded from Energy, while the Part remains electrically referenced. **Do not disable Energy at the continuum level if that continuum is shared with other Regions.** If Region-level exclusion isn't possible without an isolated/duplicated continuum, use one (as in S0-C). If STAR clearly prevents this (e.g. it's greyed out or gives an immediate error), don't force it — just note that it's not available and how you know.
3. **D3** — Check whether the *interface* between this Region and its thermal neighbour can be made non-conducting (uncoupled/adiabatic/or otherwise), while the Region's electrical identity is unaffected.
4. **D4** — Check whether an explicit thermal contact resistance value can be applied to that interface, while the electrical path remains intact. No need to use a production-realistic number. Please record the following specifically:
   - What is the **exact property/model name** STAR uses for this (e.g. "Thermal Resistance", "Contact Resistance", "Interface Resistance", "Gap Conductance")?
   - What are the **input units** as shown in the STAR field (e.g. m²·K/W, K/W, W/m²·K)?
   - Is the quantity entered as **area-specific resistance** (m²·K/W), **total resistance** (K/W), **conductance** (W/K), **conductance per unit area** (W/m²·K), or a **thickness/conductivity** pair (m and W/m·K)?
   - What test value did you enter, and what were the units?
   - Please take a screenshot of the D4 property panel showing the model type and the value/unit field.

   This is a generic capability check (can STAR assign an explicit interface resistance at all?). We are not asking you to confirm that the specific value is correct for production use — that determination is made on our side later.

That's it — please send back the filled-in template, the screenshots, and the three `.sim` files (baseline, material_test, thermal_path_test) if practical.
