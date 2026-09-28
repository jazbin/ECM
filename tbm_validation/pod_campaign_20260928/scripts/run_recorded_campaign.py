#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,re,shlex,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve(); PATCHER=HERE.with_name("patch_recorded_macro.py")
FAIL=[
 ("FAIL_E004",re.compile(r"Electrode Root 1\s*:\s*Extrusion distance can not be 0|\bE004\b",re.I)),
 ("FAIL_CAN_THICKNESS",re.compile(r"Can Thickness is -ve|can thickness.*negative",re.I)),
 ("FAIL_MANDREL",re.compile(r"Mandrel thickness must be positive",re.I)),
 ("FAIL_BATTERY_INIT",re.compile(r"VCELL call to init failed|IDACalcIC failed|IDAKLUSetup",re.I)),
 ("FAIL_SERVER",re.compile(r"error:\s*Server Error|Server Error",re.I)),
]
def classify(text,rc,step):
    for name,rx in FAIL:
        if rx.search(text): return name
    if rc==0 and step.is_file() and step.stat().st_size>0:return "PASS"
    if rc==0:return "PASS_NO_STEP"
    return "FAIL_OTHER"

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("manifest",type=Path); ap.add_argument("recorded_macro",type=Path); ap.add_argument("--launch",required=True); ap.add_argument("--results",type=Path,default=Path("results")); ap.add_argument("--only"); ap.add_argument("--timeout",type=int,default=900); ap.add_argument("--dry-run",action="store_true"); a=ap.parse_args()
    launch=shlex.split(a.launch)
    if "{macro}" not in launch: raise SystemExit("--launch must contain {macro} as a standalone token")
    only=set(filter(None,(a.only or "").split(",")))
    with a.manifest.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
    if only: rows=[r for r in rows if r["case_id"] in only]
    a.results.mkdir(parents=True,exist_ok=True); summary=[]
    for r in rows:
        case=r["case_id"]; tbm=Path(r["tbm"]).resolve(); cdir=(a.results/case).resolve(); cdir.mkdir(parents=True,exist_ok=True); step=cdir/f"{case}.step"; pdir=cdir/"macro"
        pc=[sys.executable,str(PATCHER),str(a.recorded_macro),"--tbm",str(tbm),"--step",str(step),"--out-dir",str(pdir)]
        pp=subprocess.run(pc,check=True,capture_output=True,text=True); macro=Path(pp.stdout.strip().splitlines()[-1]).resolve()
        cmd=[str(macro) if x=="{macro}" else x for x in launch]
        print(f"[{case}] "+" ".join(shlex.quote(x) for x in cmd))
        if a.dry_run: continue
        t0=time.monotonic(); timeout=False
        try:
            proc=subprocess.run(cmd,cwd=cdir,capture_output=True,text=True,timeout=a.timeout); rc=proc.returncode; text=(proc.stdout or "")+"\n"+(proc.stderr or "")
        except subprocess.TimeoutExpired as e:
            timeout=True; rc=124; text=(e.stdout or "")+"\n"+(e.stderr or "")+"\nPOD_CAMPAIGN_TIMEOUT\n"
        elapsed=time.monotonic()-t0; (cdir/"star.log").write_text(text,encoding="utf-8",errors="replace"); status="FAIL_TIMEOUT" if timeout else classify(text,rc,step)
        summary.append({"case_id":case,"expected":r.get("expected",""),"status":status,"returncode":rc,"elapsed_s":f"{elapsed:.3f}","tbm":str(tbm),"step":str(step) if step.exists() else "","log":str(cdir/"star.log")})
        print(f"[{case}] {status} ({elapsed:.1f}s)")
    if a.dry_run:return
    out=a.results/"results.csv"
    with out.open("w",newline="",encoding="utf-8") as f:
        fields=["case_id","expected","status","returncode","elapsed_s","tbm","step","log"]; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(summary)
    print(out)
if __name__=="__main__": main()
