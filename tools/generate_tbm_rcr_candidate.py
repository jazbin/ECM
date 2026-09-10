#!/usr/bin/env python3
"""Generate the single RCR-selected 2170 TBM candidate from frozen V4/variant_3.

This is intentionally a narrow, byte-preserving patch layer. It does not regenerate
geometry, RCR tables, builder fields, REPORT data, tab fields, or m_bOnly1D values.
It starts from the reviewed V4 same-face/tabs-on candidate and changes exactly one
MODELMAP selector:

    IET = Distributed 3D  ->  IET = RCRTable 3D

The base SHA-256 is pinned so the script refuses to operate if the reviewed V4
candidate changes underneath it.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

BASE = Path("out/v4_candidate/hp2170-v4c-v3-tabs-on-sameFace.tbm")
OUT = Path("out/rcr_candidate/hp2170-rcr-v3-star-preflight-tabs-on-sameFace.tbm")
# V3 base: V4/v3 regenerated with Transport Number sets = 0 added to General Electrolyte SIMMOD.
# Prior pinned SHA was e645ab18ad5da81b8a90646743051e8a2e3259d745a2d683589154ad68c12b26 (V2 base, S3=5, no TN sets).
# BASE_SHA256 must be updated after running generate_tbm_v4_candidate.py to get the new V4/v3 SHA.
BASE_SHA256 = "2cd3b503559e5ed0dd060d7b26cd555121cd224e40d91fe6c2b96dc23a7c8afd"
EXPECTED_OLD_IET = b"Distributed 3D"
EXPECTED_NEW_IET = b"RCRTable 3D"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _modelmap_span(raw: bytes) -> tuple[int, int, bytes]:
    matches = list(re.finditer(br"<MODELMAP>(.*?)</MODELMAP>", raw, flags=re.DOTALL))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one MODELMAP block, found {len(matches)}")
    m = matches[0]
    return m.start(1), m.end(1), m.group(1)


def _iet_value(block: bytes) -> bytes:
    matches = re.findall(br"(?m)^[ \t]*IET[ \t]*=[ \t]*([^\t\r\n]+)", block)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one IET entry in MODELMAP, found {len(matches)}")
    return matches[0].strip()


def patch_modelmap(raw: bytes) -> bytes:
    """Return a copy with only MODELMAP/IET switched to RCRTable 3D."""
    start, end, block = _modelmap_span(raw)
    current = _iet_value(block)
    if current != EXPECTED_OLD_IET:
        raise ValueError(
            f"unexpected base MODELMAP IET={current!r}; expected {EXPECTED_OLD_IET!r}"
        )

    # A RCRTable 3D SIMMOD must exist before selecting it.
    if not re.search(br"<SIMMOD>\r?\nRCRTable 3D\r?\n", raw):
        raise ValueError("RCRTable 3D SIMMOD not found")

    # Restrict whitespace to horizontal characters so line boundaries cannot move.
    old_line = re.compile(br"(?m)^([ \t]*IET[ \t]*=[ \t]*)Distributed 3D([ \t]*)$")
    patched_block, count = old_line.subn(br"\1RCRTable 3D\2", block)
    if count != 1:
        raise ValueError(f"expected one MODELMAP IET replacement, got {count}")

    patched = raw[:start] + patched_block + raw[end:]

    # Safety: semantic diff is exactly one logical line.
    before_lines = raw.splitlines()
    after_lines = patched.splitlines()
    if len(before_lines) != len(after_lines):
        raise ValueError("line count changed while patching MODELMAP")
    diffs = [(i + 1, a, b) for i, (a, b) in enumerate(zip(before_lines, after_lines)) if a != b]
    if len(diffs) != 1:
        raise ValueError(f"expected exactly one changed line, found {len(diffs)}")
    _, before, after = diffs[0]
    if b"IET" not in before or EXPECTED_OLD_IET not in before:
        raise ValueError(f"unexpected source diff line: {before!r}")
    if b"IET" not in after or EXPECTED_NEW_IET not in after:
        raise ValueError(f"unexpected target diff line: {after!r}")

    return patched


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=BASE)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--allow-unpinned-base",
        action="store_true",
        help="allow a non-default input SHA; never use for the reviewed release candidate",
    )
    args = ap.parse_args()

    if not args.base.exists():
        sys.exit(f"ERROR: base TBM not found: {args.base}")

    raw = args.base.read_bytes()
    base_sha = sha256_bytes(raw)
    if args.base == BASE and not args.allow_unpinned_base and base_sha != BASE_SHA256:
        sys.exit(
            "ERROR: frozen V4/variant_3 SHA mismatch\n"
            f"  expected: {BASE_SHA256}\n"
            f"  actual:   {base_sha}"
        )

    try:
        patched = patch_modelmap(raw)
    except ValueError as exc:
        sys.exit(f"ERROR: {exc}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(patched)
    out_sha = sha256_bytes(patched)

    print(f"base:       {args.base}")
    print(f"base sha:   {base_sha}")
    print(f"output:     {args.out}")
    print(f"output sha: {out_sha}")
    print("delta:      exactly one logical line")
    print("             MODELMAP IET = Distributed 3D -> RCRTable 3D")
    print("NOTE: this is a static candidate only; STAR import/runtime qualification remains required.")


if __name__ == "__main__":
    main()
