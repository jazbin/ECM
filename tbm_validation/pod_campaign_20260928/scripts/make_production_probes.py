#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,re
from pathlib import Path
HERE=Path(__file__).resolve(); CAMPAIGN=HERE.parents[1]; REPO=HERE.parents[3]; BASE=REPO/"artifacts/equivalence/robert_s0/input/T06_TARGET_AXIAL_SURPLUS_2p00.tbm"
def patch(text,key,value):
    rx=re.compile(rf"^(?P<p>\s*{key}\s*=\s*)(?P<v>[^!\r\n]*)(?P<s>!.*)$",re.MULTILINE); ms=list(rx.finditer(text))
    if len(ms)!=1:raise RuntimeError(f"{key}: expected one match, got {len(ms)}")
    return rx.sub(lambda m:f"{m.group('p')}{value}\t{m.group('s')}",text,count=1)
def set_driver(text,driver,value):
    if driver=="none":return text
    if driver=="report_xy":return patch(patch(text,r"m_dRepCanXDim",value),r"m_dRepCanYDim",value)
    if driver=="package_int":return patch(text,r"Package m_dintDiameter",value)
    if driver=="package_ext":return patch(text,r"Package m_dextDiameter",value)
    raise ValueError(driver)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    choices=["none","report_xy","package_int","package_ext"]; ap=argparse.ArgumentParser(); ap.add_argument("--can-od-driver",required=True,choices=choices); ap.add_argument("--can-id-driver",required=True,choices=choices); ap.add_argument("--can-od",default="21.09"); ap.add_argument("--can-id",default="20.6274"); ap.add_argument("--gap-jr",default="20.50"); ap.add_argument("--contact-jr",default="20.6274"); ap.add_argument("--out-dir",type=Path,default=CAMPAIGN/"build"/"production"); a=ap.parse_args()
    if a.can_od_driver!="none" and a.can_od_driver==a.can_id_driver and a.can_od!=a.can_id:raise SystemExit("One field cannot independently impose different Can OD and ID; mapping is coupled")
    text=BASE.read_text(encoding="utf-8"); text=set_driver(text,a.can_od_driver,a.can_od); text=set_driver(text,a.can_id_driver,a.can_id); a.out_dir.mkdir(parents=True,exist_ok=True)
    for case,jr in [("PROD_GAP",a.gap_jr),("PROD_CONTACT",a.contact_jr)]:
        p=a.out_dir/f"{case}.tbm"; p.write_text(patch(text,r"m_dJellyrollThickness_mm",jr),encoding="utf-8"); print(case,p,sha(p))
if __name__=="__main__":main()
