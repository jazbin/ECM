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

**What to return:** a simple table (CSV or text is fine) with columns
`object_name, object_type, volume_mm3`, where `object_type` is either
`Geometry Part` or `Region`. If STAR cannot report a given object's volume,
write `NOT AVAILABLE` for that row rather than skipping it. Plus the one
section-view screenshot.

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

**What to return:** for each pair where an interface/contact *does* exist:
Region A, Region B, interface/contact type, whether thermal coupling is
active (if you can tell), and whether any contact resistance/gap treatment
is applied (if you can tell). Text/CSV is preferred. If that's impractical,
screenshots of the full Interfaces tree plus the property panel for each
interface are fine instead.

---

## S0-C — Electrical role vs. thermal material independence

**What we need to know:** can a single Region keep its electrical role (part
of the positive/negative current path) while its *thermal* material is
changed independently? We're using `+Ve Tab Stem` as the test Region.

**Setup:** make a **copy** of the baseline — `Save As` →
`T06_S0_material_test.sim`. Do not modify `T06_S0_baseline.sim` itself.

**Before making any change**, please record (this establishes the
"before" state):
- The current Core Parts, +Tab Parts, and −Tab Parts assignments.
- The Battery Cell / Unit Cell Model object status (does it show as valid?).
- Electrical mesh status.
- Confirm `+Ve Tab Stem` is currently listed as part of the positive
  electrical path (Core/+Tab Parts).

**The one change to make:** change *only* the thermal material/property of
the `+Ve Tab Stem` Region to a deliberately extreme test value — e.g. thermal
conductivity k = 0.01 W/m·K. This is a throwaway test value, not a
production value. Please do **not** change any electrical property.

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

**Only do this after S0-C.** Same idea, going one step further: can we make
a Region thermally "quiet" (not conducting heat into/out of it) while it
still carries its electrical role?

**Setup:** make a fresh copy of the baseline — `Save As` →
`T06_S0_thermal_path_test.sim`. Test on `+Ve Tab Stem` (or a similar Region
if that's more natural in STAR's UI). Do not modify the other two `.sim`
files.

Try each of these four, in order, and for each one record: was it possible?,
did the electrical assignment remain intact?, did the Battery Cell / Unit
Cell Model remain valid?

1. **D1** — Set a very low thermal conductivity on the Region (similar to
   S0-C) while explicitly confirming the electrical assignment is preserved.
2. **D2** — Check whether the Energy (thermal) model can be disabled or the
   Region/continuum excluded from Energy, while the Part remains
   electrically referenced. If STAR clearly prevents this (e.g. it's greyed
   out or gives an immediate error), don't force it — just note that it's
   not available and how you know.
3. **D3** — Check whether the *interface* between this Region and its
   thermal neighbour can be made non-conducting (uncoupled/adiabatic/or
   otherwise), while the Region's electrical identity is unaffected.
4. **D4** — Check whether an explicit thermal contact resistance value can
   be applied to that interface, while the electrical path remains intact.
   No need to use a production-realistic number — just confirm the
   mechanism exists and is settable.

That's it — please send back the filled-in template, the screenshots, and
the three `.sim` files (baseline, material_test, thermal_path_test) if
practical.
