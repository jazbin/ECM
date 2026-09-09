#!/usr/bin/env python3
"""Collect and structurally index Siemens/BDS/STAR TBM references.

The source roots are deliberately restricted to installation/reference trees.
Client/generated TBMs under ``out`` and the repository validation corpus are
excluded. Files are copied with shutil.copyfile, preserving file bytes.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tbm_validation/siemens_reference_corpus"
SOURCES = [
    (Path("/workspace/BDS_files"), "bds_install", "SIEMENS_SUPPLIED_REFERENCE"),
    (Path("/workspace/in/StarCCM_bds"), "star_install", "INSTALLATION_SAMPLE"),
    (Path("/workspace/in/testedVersion"), "sample_projects", "UNKNOWN_IMPORT_STATUS"),
]
EXTENSIONS = {".tbm", ".ebm"}
RELATED_EXTENSIONS = {".bdw", ".prg", ".cellbak", ".wcs"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lines(path: Path) -> list[str]:
    return path.read_bytes().decode("utf-8", errors="replace").splitlines()


def value_from_line(line: str) -> tuple[str, str] | None:
    if "=" not in line or line.lstrip().startswith("!"):
        return None
    key, value = line.split("=", 1)
    value = value.split("!", 1)[0].strip()
    # REPORT records commonly append a tab-separated flag after the value.
    # Keep the extracted value and omit the storage flag from CSV fields.
    value = value.split("\t", 1)[0].strip()
    return key.strip(), value


def all_fields(block: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for line in block:
        item = value_from_line(line)
        if item:
            result[item[0]].append(item[1])
    return dict(result)


def sections(raw: list[str], tag: str) -> list[list[str]]:
    found: list[list[str]] = []
    current: list[str] | None = None
    depth = 0
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    for line in raw:
        stripped = line.strip()
        if stripped == open_tag:
            current = []
            depth = 1
            continue
        if current is not None:
            if stripped == open_tag:
                depth += 1
            elif stripped == close_tag:
                depth -= 1
                if depth == 0:
                    found.append(current)
                    current = None
                    continue
            current.append(line)
    return found


def first_section_name(block: list[str]) -> str:
    for line in block:
        text = line.strip()
        if text and not text.startswith("!") and "=" not in text:
            return text
    return ""


def selected(fields: dict[str, list[str]], names: list[str]) -> dict[str, list[str]]:
    selected_fields: dict[str, list[str]] = {}
    for name in names:
        values = []
        for key, key_values in fields.items():
            if key == name or key.endswith(" " + name):
                values.extend(key_values)
        if values:
            selected_fields[name] = values
    return selected_fields


BUILDER_FIELDS = [
    "m_dJellyrollThickness_mm", "m_dJellyrollThickness", "m_dJellyrollWidth_mm",
    "m_dJellyrollWidth", "m_dMandrelThickness_mm", "m_dMandrelWidth_mm",
    "m_dMandrelWidth", "m_dElectrodeOverlapAtStart_mm", "m_dElectrodeOverlapAtStart",
    "m_dElectrodeOverlapAtEnd_mm", "m_dElectrodeOverlapAtEnd", "m_dSepFeedLength_mm",
    "m_dSepFeedLength", "m_dSepTailLength_mm", "m_dSepTailLength", "m_dOffsetPosAvg",
    "m_dOffsetNegAvg", "m_dOffsetSepAvg", "m_bNegTab", "m_bPosTab",
    "m_nNegTabVertOrientation", "m_nPosTabVertOrientation", "m_nNumSpokes",
    "m_nFixedTabs", "m_strBuilderVersion", "m_dBuilderVersion", "classversion",
]
SIMMOD_FIELDS = [
    "classversion", "m_dModelVersion", "m_dLiIonModelBaseVersion", "m_nVersion", "m_bOnly1D", "m_bSpecifyCapacity", "m_dAhCell",
    "m_bSpecifyActiveArea", "m_dActiveArea_m2", "m_dThermalConductivity",
    "m_dThermalConductivityX", "m_dThermalConductivityY", "m_dThermalConductivityZ",
    "m_dHeatCapacity", "m_dDensity", "m_dDensity_gpercm3", "m_nRCRParameterSets",
    "RCR_dUdT_DataPoints", "RCR_Veq_nSize", "RCR_dUdT_nSize",
]
PACKAGE_KEYS = [
    "Package m_bextVolCalc", "Package m_bintVolCalc", "Package m_dextDiameter",
    "Package m_dextHeight", "Package m_dextVolume", "Package m_dintDiameter",
    "Package m_dintHeight", "Package m_dintVolume", "Package m_strName",
]
DATASHEET_KEYS = [
    "DataSheet m_dCapacity", "DataSheet m_dDiameter", "DataSheet m_dHeight",
    "DataSheet m_dThickness", "DataSheet m_dVoltage", "DataSheet m_dWeight",
    "DataSheet m_dWidth", "DataSheet m_strName", "DataSheet m_strDSName",
]
REPORT_PREFIX = "m_dRep"


def parse(path: Path) -> dict:
    raw = lines(path)
    fields = all_fields(raw)
    physical = sections(raw, "Physical Cell Description")
    cell_type = ""
    if physical:
        for line in physical[0]:
            text = line.strip()
            if text and "=" not in text and not text.startswith("!"):
                cell_type = text
                break
    report = sections(raw, "REPORT")
    builders = sections(raw, "BUILDER")
    simmods = sections(raw, "SIMMOD")
    builder_records = []
    for index, block in enumerate(builders, 1):
        block_fields = all_fields(block)
        builder_records.append({
            "section_index": index,
            "builder_name": next((x.strip() for x in block if x.strip() in {"Detailed Builder", "Simple Builder"}), ""),
            "fields": selected(block_fields, BUILDER_FIELDS),
        })
    simmod_records = []
    for index, block in enumerate(simmods, 1):
        block_fields = all_fields(block)
        simmod_records.append({
            "section_index": index,
            "simmod_name": first_section_name(block),
            "model_version": " | ".join(selected(block_fields, ["m_dModelVersion"]).get("m_dModelVersion", [])),
            "fields": selected(block_fields, SIMMOD_FIELDS),
        })
    report_fields = all_fields(report[0]) if report else {}
    return {
        "tbmfileversion": fields.get("tbmfileversion", [""])[0],
        "cell_type": cell_type,
        "package": selected(fields, PACKAGE_KEYS),
        "datasheet": selected(fields, DATASHEET_KEYS),
        "report_field_count": sum(1 for key in report_fields if key.startswith(REPORT_PREFIX)),
        "report": {key: values for key, values in report_fields.items() if key.startswith(REPORT_PREFIX)},
        "builders": builder_records,
        "simmods": simmod_records,
    }


def classify(root: Path, path: Path, default: str) -> tuple[str, str]:
    rel = path.relative_to(root).as_posix()
    lower = rel.lower()
    if "tutorial" in lower:
        return "tutorials", "TUTORIAL_REFERENCE"
    if "sample" in lower or "demo" in lower or "validation" in lower:
        return "sample_projects", "INSTALLATION_SAMPLE"
    return ("bds_install" if "BDS_files" in str(root) else "star_install"), default


def main() -> None:
    candidates: list[tuple[Path, Path, str, str, str]] = []
    related_candidates: list[tuple[Path, Path, str, str]] = []
    for root, category_hint, status_hint in SOURCES:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name.lower().endswith(".tbm.bak_before_currentfix"):
                candidates.append((path, root, "legacy", "UNKNOWN_IMPORT_STATUS", category_hint))
            elif path.is_file() and path.suffix.lower() in EXTENSIONS:
                category, status = classify(root, path, status_hint)
                candidates.append((path, root, category, status, category_hint))
            elif path.is_file() and path.suffix.lower() in RELATED_EXTENSIONS:
                category, status = classify(root, path, status_hint)
                related_candidates.append((path, root, category, status))
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for path, *_ in candidates:
        by_hash[sha256(path)].append(path)

    inventory_rows = []
    matrix_rows = []
    for source, root, category, status, _hint in candidates:
        digest = sha256(source)
        relative = source.relative_to(root)
        repo_rel = Path("tbm_validation/siemens_reference_corpus") / category / root.name / relative
        destination = ROOT / repo_rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        data = parse(source)
        duplicate_paths = [str(p) for p in by_hash[digest] if p != source]
        inventory_rows.append({
            "filename": source.name,
            "repo_path": repo_rel.as_posix(),
            "original_absolute_path": str(source),
            "source_category": category,
            "STAR_or_BDS_version_if_known": "BDS 17.04.008 (path evidence)" if root.name == "BDS_files" else ("BDS 20.04.007 (BDW evidence)" if root.name == "StarCCM_bds" else "STAR version not established for this file"),
            "file_size": source.stat().st_size,
            "sha256": digest,
            "tbmfileversion": data["tbmfileversion"],
            "cell_type": data["cell_type"],
            "provenance_status": status,
            "duplicate_source_paths": " | ".join(duplicate_paths),
            "notes": "Copied byte-for-byte; import status not inferred from existence.",
        })
        base = {"repo_path": repo_rel.as_posix(), "filename": source.name, "sha256": digest, "record_type": "TBM", "section_index": "", "section_name": "", "model_version": "", "tbmfileversion": data["tbmfileversion"], "cell_type": data["cell_type"], "source_category": category, "m_bOnly1D": "", "m_bSpecifyCapacity": "", "m_dAhCell": "", "m_bSpecifyActiveArea": "", "m_dActiveArea_m2": "", "thermal_fields": "", "heat_capacity_fields": "", "density_fields": "", "field_values_json": json.dumps({"package": data["package"], "datasheet": data["datasheet"], "report_field_count": data["report_field_count"], "report": data["report"]}, sort_keys=True)}
        matrix_rows.append(base)
        for builder in data["builders"]:
            row = dict(base)
            row.update(record_type="BUILDER", section_index=builder["section_index"], section_name=builder["builder_name"], field_values_json=json.dumps(builder["fields"], sort_keys=True))
            matrix_rows.append(row)
        for simmod in data["simmods"]:
            fields = simmod["fields"]
            row = dict(base)
            row.update(record_type="SIMMOD", section_index=simmod["section_index"], section_name=simmod["simmod_name"], model_version=simmod["model_version"], m_bOnly1D=" | ".join(fields.get("m_bOnly1D", [])), m_bSpecifyCapacity=" | ".join(fields.get("m_bSpecifyCapacity", [])), m_dAhCell=" | ".join(fields.get("m_dAhCell", [])), m_bSpecifyActiveArea=" | ".join(fields.get("m_bSpecifyActiveArea", [])), m_dActiveArea_m2=" | ".join(fields.get("m_dActiveArea_m2", [])), thermal_fields=json.dumps({k: v for k, v in fields.items() if "ThermalConductivity" in k}), heat_capacity_fields=json.dumps({k: v for k, v in fields.items() if "HeatCapacity" in k}), density_fields=json.dumps({k: v for k, v in fields.items() if "Density" in k}), field_values_json=json.dumps(fields, sort_keys=True))
            matrix_rows.append(row)

    inventory_rows.sort(key=lambda row: row["repo_path"])
    matrix_rows.sort(key=lambda row: (row["repo_path"], row["record_type"], str(row["section_index"])))
    inventory_path = CORPUS / "INVENTORY.csv"
    with inventory_path.open("w", newline="", encoding="utf-8") as stream:
        fields = ["filename", "repo_path", "original_absolute_path", "source_category", "STAR_or_BDS_version_if_known", "file_size", "sha256", "tbmfileversion", "cell_type", "provenance_status", "duplicate_source_paths", "notes"]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(inventory_rows)
    matrix_path = CORPUS / "SIEMENS_TBM_CORPUS_MATRIX.csv"
    with matrix_path.open("w", newline="", encoding="utf-8") as stream:
        fields = ["repo_path", "filename", "sha256", "record_type", "section_index", "section_name", "model_version", "tbmfileversion", "cell_type", "source_category", "m_bOnly1D", "m_bSpecifyCapacity", "m_dAhCell", "m_bSpecifyActiveArea", "m_dActiveArea_m2", "thermal_fields", "heat_capacity_fields", "density_fields", "field_values_json"]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(matrix_rows)
    related_rows = []
    for source, root, category, status in related_candidates:
        relative = source.relative_to(root)
        repo_rel = Path("tbm_validation/siemens_reference_corpus") / "related" / category / root.name / relative
        destination = ROOT / repo_rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        related_rows.append({
            "filename": source.name,
            "repo_path": repo_rel.as_posix(),
            "original_absolute_path": str(source),
            "source_category": category,
            "provenance_status": status,
            "file_size": source.stat().st_size,
            "sha256": sha256(source),
            "notes": "Related BDS/STAR sample file; copied byte-for-byte and not parsed as TBM.",
        })
    related_path = CORPUS / "RELATED_FILE_INVENTORY.csv"
    with related_path.open("w", newline="", encoding="utf-8") as stream:
        fields = ["filename", "repo_path", "original_absolute_path", "source_category", "provenance_status", "file_size", "sha256", "notes"]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(related_rows, key=lambda row: row["repo_path"]))
    summary = CORPUS / "INVENTORY.md"
    unique = len(by_hash)
    duplicates = len(candidates) - unique
    categories = defaultdict(int)
    for row in inventory_rows:
        categories[row["source_category"]] += 1
    summary.write_text(
        "# Siemens/BDS/STAR TBM reference corpus\n\n"
        f"Collected {len(candidates)} TBM/EBM reference files with {unique} unique SHA-256 contents and {duplicates} duplicate copies, plus {len(related_candidates)} related BDS/STAR sample files.\n\n"
        "## Provenance\n\n"
        "The corpus includes the BDS project tree at `/workspace/BDS_files`, the STAR/BDS reference workspace at `/workspace/in/StarCCM_bds`, and `/workspace/in/testedVersion/testTBM.tbm`. Generated/client TBMs under `/workspace/out` and repository validation TBMs were excluded. Original files were read only and copied with byte-preserving `shutil.copyfile`.\n\n"
        "The BDS project tree contains path evidence for BDS 17.04.008. `in/StarCCM_bds/bdsTest.bdw` contains a BDS 20.04.007 source path. STAR logs in the workspace identify Simcenter STAR-CCM+ 2602.0001, build 21.02.008; that STAR version is recorded as environment evidence and is not asserted for every TBM.\n\n"
        "## Search scope\n\n"
        "The recursive search covered `/opt`, `/usr/local`, `/home`, and `/workspace`, including likely Siemens/STAR/BDS, tutorial, sample-data, and documentation locations. No additional `.tbm` or `.ebm` files were found outside the three source trees listed above; one explicitly retained legacy backup, `validationBattery.tbm.bak_before_currentfix`, is included under `legacy`.\n\n"
        "Presence is not treated as proof of import success. Each inventory row carries a provenance status and source path. Duplicate source paths are retained in the inventory; the copied corpus retains all original filenames and relative source layout.\n\n"
        "## Counts by corpus directory\n\n" + "\n".join(f"- `{key}`: {value} files" for key, value in sorted(categories.items())) + "\n\n"
        "## Machine-readable files\n\n"
        "- `INVENTORY.csv`: one row per copied source file, including absolute source path, hash, version evidence, and duplicate paths.\n"
        "- `SIEMENS_TBM_CORPUS_MATRIX.csv`: TBM, BUILDER, and SIMMOD extraction rows. REPORT and top-level Package/DataSheet fields are included in the TBM row.\n"
        "- `RELATED_FILE_INVENTORY.csv`: byte-preserving inventory for associated BDS project/sample files (`.bdw`, `.prg`, `.cellbak`, `.wcs`).\n",
        encoding="utf-8",
    )
    print(f"copied_files={len(candidates)} unique_hashes={unique} duplicate_copies={duplicates} related_files={len(related_candidates)} matrix_rows={len(matrix_rows)}")


if __name__ == "__main__":
    main()
