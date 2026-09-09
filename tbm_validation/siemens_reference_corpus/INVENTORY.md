# Siemens/BDS/STAR TBM reference corpus

Collected 179 TBM/EBM reference files with 124 unique SHA-256 contents and 55 duplicate copies, plus 119 related BDS/STAR sample files.

## Provenance

The corpus includes the BDS project tree at `/workspace/BDS_files`, the STAR/BDS reference workspace at `/workspace/in/StarCCM_bds`, and `/workspace/in/testedVersion/testTBM.tbm`. Generated/client TBMs under `/workspace/out` and repository validation TBMs were excluded. Original files were read only and copied with byte-preserving `shutil.copyfile`.

The BDS project tree contains path evidence for BDS 17.04.008. `in/StarCCM_bds/bdsTest.bdw` contains a BDS 20.04.007 source path. STAR logs in the workspace identify Simcenter STAR-CCM+ 2602.0001, build 21.02.008; that STAR version is recorded as environment evidence and is not asserted for every TBM.

## Search scope

The recursive search covered `/opt`, `/usr/local`, `/home`, and `/workspace`, including likely Siemens/STAR/BDS, tutorial, sample-data, and documentation locations. No additional `.tbm` or `.ebm` files were found outside the three source trees listed above; one explicitly retained legacy backup, `validationBattery.tbm.bak_before_currentfix`, is included under `legacy`.

Presence is not treated as proof of import success. Each inventory row carries a provenance status and source path. Duplicate source paths are retained in the inventory; the copied corpus retains all original filenames and relative source layout.

## Counts by corpus directory

- `bds_install`: 105 files
- `legacy`: 1 files
- `sample_projects`: 62 files
- `star_install`: 2 files
- `tutorials`: 9 files

## Machine-readable files

- `INVENTORY.csv`: one row per copied source file, including absolute source path, hash, version evidence, and duplicate paths.
- `SIEMENS_TBM_CORPUS_MATRIX.csv`: TBM, BUILDER, and SIMMOD extraction rows. REPORT and top-level Package/DataSheet fields are included in the TBM row.
- `RELATED_FILE_INVENTORY.csv`: byte-preserving inventory for associated BDS project/sample files (`.bdw`, `.prg`, `.cellbak`, `.wcs`).
