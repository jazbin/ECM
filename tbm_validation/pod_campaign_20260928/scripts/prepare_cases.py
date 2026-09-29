#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,re,shutil
from pathlib import Path
HERE=Path(__file__).resolve(); CAMPAIGN=HERE.parents[1]; REPO=HERE.parents[3]
SOURCE_MANIFEST=CAMPAIGN/"manifests"/"source_cases.csv"; DEFAULT_BUILD=CAMPAIGN/"build"

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def patch_scalar(text,key_regex,value):
    rx=re.compile(rf"^(?P<prefix>\s*{key_regex}\s*=\s*)(?P<old>[^!\r\n]*)(?P<suffix>!.*)$",re.MULTILINE)
    ms=list(rx.finditer(text))
    if len(ms)!=1: raise RuntimeError(f"Expected exactly one match for {key_regex!r}; got {len(ms)}")
    return rx.sub(lambda m:f"{m.group('prefix')}{value}\t{m.group('suffix')}",text,count=1)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--build",type=Path,default=DEFAULT_BUILD); ap.add_argument("--include-reserve",action="store_true"); args=ap.parse_args()
    build=args.build.resolve(); cases=build/"cases"; cases.mkdir(parents=True,exist_ok=True)
    with SOURCE_MANIFEST.open(newline="",encoding="utf-8") as f: srcrows=list(csv.DictReader(f))
    rows=[]
    for r in srcrows:
        if r["run_default"].lower()!="yes" and not args.include_reserve: continue
        src=REPO/r["repo_relative_path"]
        if not src.is_file(): raise FileNotFoundError(src)
        dst=cases/f"{r['case_id']}.tbm"; shutil.copy2(src,dst)
        rows.append({"case_id":r["case_id"],"phase":r["phase"],"tbm":str(dst),"expected":r["expected"],"sha256":sha256(dst),"source":r["repo_relative_path"],"notes":r["notes"]})
    t06=cases/"CTRL_T06_PASS.tbm"
    if not t06.is_file(): raise RuntimeError("CTRL_T06_PASS missing")
    base=t06.read_text(encoding="latin-1")
    e004=patch_scalar(base,r"\+Electrode Tab m_dLength_mm","64.11")
    e004=patch_scalar(e004,r"\-Electrode Tab m_dLength_mm","65.11")
    p=cases/"CTRL_E004_BOTH_ZERO.tbm"; p.write_text(e004,encoding="latin-1")
    rows.append({"case_id":"CTRL_E004_BOTH_ZERO","phase":"control","tbm":str(p),"expected":"FAIL_E004","sha256":sha256(p),"source":"synthetic-from-T06","notes":"Both tab surpluses zero; expected E004"})
    canneg=patch_scalar(base,r"m_dJellyrollThickness_mm","20.6274")
    p=cases/"CTRL_CAN_NEG_JR20p6274.tbm"; p.write_text(canneg,encoding="latin-1")
    rows.append({"case_id":"CTRL_CAN_NEG_JR20p6274","phase":"control","tbm":str(p),"expected":"FAIL_CAN_THICKNESS","sha256":sha256(p),"source":"synthetic-from-T06","notes":"Target-sized JR with T06 can state; radial conflict control"})
    order={"CTRL_T06_PASS":0,"CTRL_18650_PASS":1,"CTRL_E004_BOTH_ZERO":2,"CTRL_CAN_NEG_JR20p6274":3,"RAD_A":10,"RAD_B":11,"RAD_C":12}
    rows.sort(key=lambda r:(order.get(r["case_id"],100),r["case_id"]))
    with (build/"manifest.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["case_id","phase","tbm","expected","sha256","source","notes"]); w.writeheader(); w.writerows(rows)
    with (build/"HASHES.sha256").open("w",encoding="utf-8") as f:
        for r in rows: f.write(f"{r['sha256']}  {Path(r['tbm']).name}\n")
    print(f"Prepared {len(rows)} cases in {build}")
if __name__=="__main__": main()
