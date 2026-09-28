#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
Q=["can_od_mm","can_id_mm","jellyroll_od_mm","jr_can_radial_gap_mm"]
def load(p):return json.loads(Path(p).read_text(encoding="utf-8"))["summary"]
def delta(a,b,k):return None if a.get(k) is None or b.get(k) is None else b[k]-a[k]
def changed(x,t):return x is not None and abs(x)>=t
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--baseline",required=True); ap.add_argument("--rad-a",required=True); ap.add_argument("--rad-b",required=True); ap.add_argument("--rad-c",required=True); ap.add_argument("--tol",type=float,default=.05); ap.add_argument("--out",type=Path); a=ap.parse_args()
    base=load(a.baseline); probes=[("Package m_dintDiameter",load(a.rad_a)),("m_dRepCanXDim/YDim",load(a.rad_b)),("m_dJellyrollThickness_mm",load(a.rad_c))]
    out={"tolerance_mm":a.tol,"baseline":base,"probes":{},"evidence":{}}
    for name,p in probes:
        ds={k:delta(base,p,k) for k in Q}; out["probes"][name]={"summary":p,"delta_from_baseline_mm":ds}
        out["evidence"][name]={"changes_can_od":changed(ds["can_od_mm"],a.tol),"changes_can_id":changed(ds["can_id_mm"],a.tol),"changes_jr_od":changed(ds["jellyroll_od_mm"],a.tol)}
    txt=json.dumps(out,indent=2)
    if a.out:a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(txt+"\n",encoding="utf-8")
    print(txt)
if __name__=="__main__":main()
