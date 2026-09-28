#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
NAMES=["Mandrel","Jellyroll","Can","+Ve Tab Root","+Ve Tab Stem","-Ve Tab Root","-Ve Tab Stem","+Ve Washer","-Ve Washer","+Ve EndPlate","-Ve EndPlate","+Ve Internal-Post","-Ve Internal-Post"]

def bbox(s):
    b=Bnd_Box(); BRepBndLib.AddOptimal_s(s,b,False,True)
    try:return list(b.Get())
    except Exception:
        lo,hi=b.CornerMin(),b.CornerMax(); return [lo.X(),lo.Y(),lo.Z(),hi.X(),hi.Y(),hi.Z()]
def volume(s):
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); return g.Mass()
def cylinder_radii(s,tol=1e-6):
    out=[]; ex=TopExp_Explorer(s,TopAbs_FACE)
    while ex.More():
        f=TopoDS.Face_s(ex.Current()); a=BRepAdaptor_Surface(f,True)
        if a.GetType()==GeomAbs_Cylinder:
            r=float(a.Cylinder().Radius())
            if not any(abs(r-x)<=tol for x in out):out.append(r)
        ex.Next()
    return sorted(out)
def distance(a,b):
    d=BRepExtrema_DistShapeShape(a,b)
    return float(d.Value()) if d.IsDone() and d.NbSolution()>0 else None
def common_volume(a,b):
    c=BRepAlgoAPI_Common(a,b); c.SetRunParallel(False); c.Build()
    return volume(c.Shape()) if c.IsDone() else None
def props(s):
    bb=bbox(s); return {"bbox":bb,"height_y_mm":bb[4]-bb[1],"volume_mm3":volume(s),"cylindrical_radii_mm":cylinder_radii(s)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("step",type=Path); ap.add_argument("-o","--output",type=Path); a=ap.parse_args()
    rd=STEPControl_Reader()
    if rd.ReadFile(str(a.step))!=IFSelect_RetDone: raise SystemExit(f"Cannot read {a.step}")
    nr=rd.TransferRoots(); ns=rd.NbShapes()
    if nr!=13 or ns!=13: raise SystemExit(f"Expected 13 roots/shapes; got roots={nr}, shapes={ns}; refusing name assignment")
    shapes={n:rd.Shape(i+1) for i,n in enumerate(NAMES)}; bodies={n:props(s) for n,s in shapes.items()}
    jr=bodies["Jellyroll"]["cylindrical_radii_mm"]; can=bodies["Can"]["cylindrical_radii_mm"]; mand=bodies["Mandrel"]["cylindrical_radii_mm"]
    summary={"jellyroll_od_mm":2*max(jr) if jr else None,"jellyroll_id_mm":2*min(jr) if len(jr)>=2 else None,"can_od_mm":2*max(can) if can else None,"can_id_mm":2*sorted(can)[-2] if len(can)>=2 else None,"mandrel_od_mm":2*max(mand) if mand else None,"jr_can_min_distance_mm":distance(shapes["Jellyroll"],shapes["Can"]),"jr_can_overlap_volume_mm3":common_volume(shapes["Jellyroll"],shapes["Can"])}
    if summary["can_id_mm"] is not None and summary["jellyroll_od_mm"] is not None: summary["jr_can_radial_gap_mm"]=(summary["can_id_mm"]-summary["jellyroll_od_mm"])/2
    out={"file":str(a.step.resolve()),"root_count":nr,"body_order_assumption":NAMES,"summary":summary,"bodies":bodies}; txt=json.dumps(out,indent=2)
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(txt+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
