# Project Plan

## Scope
This plan covers the OpenFOAM ECM/CHT coupling and a one-month migration plan
for an equivalent Simcenter STAR-CCM+ implementation while preserving the
frozen coupling contract (elementID keys, fixed Nr x Nz partition, mapping_table
CSV, volume-weighted element temperatures, uniform volumetric heat injection,
per-step coupling with under-relaxation, and consistent logging fields).

## Frozen coupling contract (summary)
- keyMode: elementID (globalCellID only for OpenFOAM debug)
- partition: fixed Nr x Nz, stable elementID ordering
- temperature: volumeAverage(T) per element
- heat: uniform volumetric injection per element (qVol)
- cadence: per-step coupling, under-relaxation alpha
- logs: T_i, qVol_i, V, SOC, Q_total, plus checks (Q_sum_check, returnCode)

## STAR-CCM+ migration plan (one-month)

Detailed plan and translation recipes are in `docs/STARCCM_MIGRATION.md`.

### Week 1: Setup and inventory
- Inventory OpenFOAM artifacts to port (mesh, zones, mapping_table, coupling IO)
- Recreate geometry and regions in STAR-CCM+ (jelly-roll, casing, cap, fluid)
- Define element partitions (Nr x Nz) with consistent naming
- Load mapping_table.csv and validate volumes/centroids

Deliverable: STAR-CCM+ case with regions and element partitions; volume check
report vs mapping_table.csv.

### Week 2: Coupling core
- Implement STAR-CCM+ macro to compute element volumeAverage(T)
- Implement ICD I/O (tmp + rename, stepId, elementID keyed records)
- Implement ECM call, parse outputs, and under-relaxation
- Apply volumetric heat sources per element

Deliverable: Macro that runs one coupling step and writes log row with required
fields.

### Week 3: Integration and parity tests
- Integrate macro into timestep loop
- Run parity tests vs OpenFOAM on short scenarios
- Compare T_i, qVol_i, V, SOC, Q_total logs for consistency

Deliverable: Parity test report and discrepancy log (if any).

### Week 4: CHT validation and handoff
- Run STAR-CCM+ CHT scenario(s) matching OpenFOAM test cases
- Capture temperature fields and coupling logs
- Package deliverables for client review and sign-off

Deliverable: CHT validation report and handoff pack.

## Translation map (OpenFOAM to STAR-CCM+)
- cellZones -> Regions or Volume Parts
- mapping_table.csv -> Macro-loaded elementID mapping
- volumeAverage(T) -> VolumeAverageReport per element
- ecmCoupler -> Java macro (ICD write/read, ECM call, under-relaxation)
- fvOptions heat source -> Volumetric heat source on each element part
- masterGather -> macro I/O on master rank with MPI barrier

## Tests and acceptance
- Unit tests: mapping_table volume/centroid checks, uniform temperature check
- Integration: parity logs vs OpenFOAM (T_i, qVol_i, V, SOC, Q_total)
- CHT: temperature field parity and Q_sum_check consistency

## Risks and mitigations
- ElementID stability: rely on external mapping_table, not internal IDs
- I/O atomicity: tmp + rename, master-only I/O with barrier
- Mesh differences: validate element volumes and centroids
- Performance: limit element count during prototyping

## Required client inputs
- ECM interface and parameter ranges
- Nr and Nz partition specs and elementID ordering
- Thermal properties (k_r, k_z, rho, cp)
- Contact resistances or perfect contact decision
- Boundary conditions for validation (chamber/plate/air)
- Coupling parameters (alpha, frequency)
- Validation acceptance thresholds

## Mapping table template
```
elementID,regionName,cellZoneName,Volume_m3,centroid_x,centroid_y,centroid_z
0,jellyRoll_R0_Z0,zone0,1.23e-5,0.0,0.0,0.01
1,jellyRoll_R1_Z0,zone1,1.23e-5,0.0,0.0,0.03
```
