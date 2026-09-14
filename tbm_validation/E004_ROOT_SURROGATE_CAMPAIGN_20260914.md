# E004 Root-Extrusion / TBM-Native Surrogate Campaign — 2026-09-14

## Hard acceptance criterion

One TBM must completely define one reusable battery cell. No Part-module moves, booleans, cap repositioning, or geometry repair are allowed after `CreateFromTbm`.

A BDS-generated solid may remain in the final cell even if it is named `Tab Root`, `Tab`, `Stem`, etc., provided that it can serve the required physical role (for example cap/end-conductor) with the correct geometry, contact topology, material properties, thermal/electrical behaviour, and native pack replication.

## New evidence motivating campaign replacement

The client-provided runtime-working `validationBattery21700.tbm` contains:

- `+Electrode Tab m_dLength_mm = 65`
- `+Electrode m_dWidth = 56`
- `PosTabhStart0 = PosTabhMiddle0 = PosTabhEnd0 = 9`

and:

- `-Electrode Tab m_dLength_mm = 65`
- `-Electrode m_dWidth = 57`
- `NegTabhStart0 = NegTabhMiddle0 = NegTabhEnd0 = 8`

Therefore the reported tab/root heights match the numerical relations exactly:

- positive: `65 - 56 = 9 mm`
- negative: `65 - 57 = 8 mm`

In failing R005:

- positive: `60 - 64.11 = -4.11 mm`
- negative: `60 - 65.11 = -5.11 mm`

The R005 REPORT block is stale from its source lineage and must not be treated as regenerated evidence. The important evidence is the exact mapping in the runtime-working source plus the negative active-input relation in R005.

This revives and sharpens the root-geometry hypothesis: a positive `tab length - electrode width` surplus may be required to construct the Electrode Root extrusion. Exact zero or negative surplus may collapse a derived extrusion to zero. This is still a hypothesis until STAR runtime testing confirms it.

## Why the previous generic 30-case matrix is superseded

The older matrix was useful for broad localization, but it treated tab lengths mainly as independent scalar fields. The current campaign directly sweeps the newly identified derived relation and then tests whether a root-valid configuration can coexist with the complete 2170 axial/radial geometry and the remaining Builder differences.

## Runtime package

Package generated from the client-provided runtime-working `validationBattery21700.tbm`:

`hp2170NCA-STAR-E004-root-surrogate-30case-20260914.zip`

ZIP SHA-256:

`49bcb6e2754a645d7d50eea04a710e303c1972c64dbe9e6455cf53c91f486a82`

Control source SHA-256:

`41c23e28ef4548e1d74e487f48e5cc96fcfb0626df3792ebfa8ec7b09efc704a`

## Campaign structure

### H01-H13 — derived root-height relation in known-working cell

Sweep positive and negative `tab length - electrode width` surplus independently and together:

- zero
- +0.10 mm
- +0.70 mm
- +2.00 mm

`H13` uses absolute tab length 60 mm for both polarities while preserving positive surpluses in the working cell (+4/+3 mm). If `H13` imports, absolute tab length 60 is not itself the blocker.

### T01-T09 — real 2170 axial PCD stack

Use:

- package internal height 65.11 mm
- separator width 67.11 mm
- negative width 65.11 mm
- positive width 64.11 mm

and sweep tab/electrode surplus:

- existing 65-mm tabs (+0.89 / -0.11 mm)
- zero
- +0.10 mm
- +0.70 mm
- +1.00 mm
- +2.00 mm
- +5.00 mm
- working-derived heights (+9/+8 mm)
- R005 tabs 60 mm (-4.11/-5.11 mm)

This group should determine whether the real 2170 axial geometry can construct natively when positive root height is provided.

### F01-F08 — full 2170 geometry with root-valid relation

Add target geometry:

- package OD 21.09 mm
- package ID 20.6274 mm
- jellyroll diameter 20.6274 mm
- package external height 70.02 mm

Then reintroduce project Builder differences while preserving deliberately positive root-height relations:

- feed/tail 0/0
- overlap 8/20
- mandrel width 6
- negative tab orientation 0
- combined project Builder state

If `F08` imports, this is strong evidence that the visible R005 2170 geometry is TBM-constructible and that the old E004 came from the root/tab relation rather than an inherent inability to represent the required cell topology.

## Client return burden

No STEP exports are required in the first round.

Robert only needs to return the list of successful IDs, e.g.:

```text
H02 PASS
H03 PASS
...
F03 PASS
```

For failures, `E004` is sufficient if it is exactly the familiar `Electrode Root 1 : Extrusion distance can not be 0.` message. Any different downstream error should be returned verbatim.

After the minimum passing root-surplus case is identified, request only ONE STEP from the most production-relevant successful F-case. That geometry will be used to determine whether the surviving TBM-native Tab Root/Tab/Stem solid can serve as the cap-equivalent part without any post-import geometry modification.

## Evidence standard

Do not call the root-surplus hypothesis confirmed until runtime results show a controlled threshold pattern. Static validator rules are not causal evidence.
