#!/usr/bin/env python3
"""
session_close.py — one-call session close for ecm-openfoam-coupling / TBM project.

Replaces the manual Read/Edit/Read/Edit cycle that costs ~8K tokens.
Claude calls this script once with structured args; it writes the session log,
patches the error database blocker state, and commits.

Usage:
    python3 tools/session_close.py \\
        --title "ROOT_A/ROOT_B result; 30-case suite validated" \\
        --in   "in/20260914: error log, hp* working zip, 30-case zip" \\
        --find "ROOT_A/B both failed E004 — H004-6 disproven" \\
        --find "30-case static check: 4 FAIL (B01/B02/B03/X02, all feed/tail=0)" \\
        --next "Package 30-case zip; send to Robert" \\
        --db-patch "LAST_OBSERVED=2026-09-14" \\
        --db-patch "LEADING_HYPOTHESIS=H004-5 (SepFeed/Tail=0) — re-elevated 2026-09-14" \\
        --db-patch "HYPOTHESIS_STATUS=CANDIDATE_APPLIED / RUNTIME_PENDING on R006 and 30-case suite" \\
        --db-patch "NEXT_TEST=30-case suite in/20260914/hp2170NCA-STAR-E004-30case-highres-diagnostic-20260914.zip" \\
        --commit

Flags:
    --title TEXT      one-line session title (appended to date in filename/header)
    --in    TEXT      files/inputs received this session (repeatable)
    --find  TEXT      key finding (repeatable, bullet per finding)
    --next  TEXT      next action item (repeatable)
    --db-patch K=V    patch a named field in the STAR_IMPORT_ERROR_DATABASE blocker
                      state block (repeatable); field must already exist in the block
    --db-file PATH    error database to patch (default: tbm_validation/STAR_IMPORT_ERROR_DATABASE.md)
    --log-dir PATH    directory for session logs (default: repo root)
    --no-commit       write files but skip git commit
    --commit          stage changed files and commit (default behaviour)
    --dry-run         print what would be written/patched; do nothing
"""

from __future__ import annotations
import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "tbm_validation" / "STAR_IMPORT_ERROR_DATABASE.md"
DEFAULT_LOG_DIR = REPO_ROOT


def today() -> str:
    return datetime.date.today().isoformat()


def write_session_log(
    log_path: Path,
    title: str,
    inputs: list[str],
    findings: list[str],
    nexts: list[str],
    dry_run: bool,
) -> None:
    date = today()
    lines = [f"# Session {date} — {title}", ""]
    if inputs:
        lines += ["## In"] + [f"- {i}" for i in inputs] + [""]
    if findings:
        lines += ["## Findings"] + [f"- {f}" for f in findings] + [""]
    if nexts:
        lines += ["## Next"] + [f"- {n}" for n in nexts] + [""]
    content = "\n".join(lines)
    if dry_run:
        print(f"[dry-run] would write {log_path}:\n{content}")
    else:
        log_path.write_text(content, encoding="utf-8")
        print(f"wrote {log_path}")


def patch_db_blocker(
    db_path: Path,
    patches: dict[str, str],
    dry_run: bool,
) -> None:
    """Patch KEY = VALUE lines inside the blocker-state code block."""
    if not patches:
        return
    text = db_path.read_text(encoding="utf-8")
    changed = False
    for key, value in patches.items():
        # Match "KEY = <anything up to newline>" inside a ``` block
        pattern = re.compile(
            r"(?m)^(" + re.escape(key) + r"\s*=\s*)(.+)$"
        )
        m = pattern.search(text)
        if not m:
            print(f"  WARN: field {key!r} not found in {db_path.name} — skipped", file=sys.stderr)
            continue
        new_line = m.group(1) + value
        if dry_run:
            print(f"[dry-run] patch {key!r}: {m.group(2)!r} → {value!r}")
        else:
            text = pattern.sub(new_line, text, count=1)
            changed = True
    if changed and not dry_run:
        db_path.write_text(text, encoding="utf-8")
        print(f"patched {db_path}")


def git_commit(paths: list[Path], title: str, dry_run: bool) -> None:
    msg = (
        f"Close session {today()}: {title}\n\n"
        "Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>\n"
        "Claude-Session: https://claude.ai/code/session_01357p51V8o5ZGUYDfQ3huq2"
    )
    rel = [str(p.relative_to(REPO_ROOT)) for p in paths if p.exists()]
    if dry_run:
        print(f"[dry-run] git add {rel}")
        print(f"[dry-run] git commit -m {msg!r}")
        return
    subprocess.run(["git", "add"] + rel, cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=REPO_ROOT, check=True)


def parse_patch(s: str) -> tuple[str, str]:
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"--db-patch must be KEY=VALUE, got {s!r}")
    k, _, v = s.partition("=")
    return k.strip(), v.strip()


def main() -> None:
    p = argparse.ArgumentParser(description="One-call session close helper")
    p.add_argument("--title", default="session close", help="One-line session title")
    p.add_argument("--in",    dest="inputs",   action="append", default=[], metavar="TEXT")
    p.add_argument("--find",  dest="findings", action="append", default=[], metavar="TEXT")
    p.add_argument("--next",  dest="nexts",    action="append", default=[], metavar="TEXT")
    p.add_argument("--db-patch", action="append", default=[], metavar="KEY=VALUE",
                   help="Patch a field in the DB blocker state block")
    p.add_argument("--db-file", default=str(DEFAULT_DB), metavar="PATH")
    p.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), metavar="PATH")
    p.add_argument("--no-commit", action="store_true")
    p.add_argument("--commit", action="store_true")  # explicit flag, same as default
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    date = today()
    log_path = Path(args.log_dir) / f"SESSION_LOG_{date}.md"
    db_path = Path(args.db_file)

    patches = {}
    for raw in args.db_patch:
        k, v = parse_patch(raw)
        patches[k] = v

    write_session_log(log_path, args.title, args.inputs, args.findings, args.nexts, args.dry_run)
    patch_db_blocker(db_path, patches, args.dry_run)

    if not args.no_commit and not args.dry_run:
        changed = [log_path]
        if patches:
            changed.append(db_path)
        git_commit(changed, args.title, args.dry_run)


if __name__ == "__main__":
    main()
