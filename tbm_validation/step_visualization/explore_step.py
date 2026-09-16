import sys
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool_ShapeTool
from OCC.Core.TDF import TDF_LabelSequence
from OCC.Core.TDataStd import TDataStd_Name
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib

def load(path):
    doc = TDocStd_Document("mdtv-xcaf")
    app = XCAFApp_Application.GetApplication()
    app.InitDocument(doc)
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    reader.SetColorMode(True)
    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {path}")
    reader.Transfer(doc)
    shape_tool = XCAFDoc_DocumentTool_ShapeTool(doc.Main())
    labels = TDF_LabelSequence()
    shape_tool.GetFreeShapes(labels)
    out = []
    for i in range(1, labels.Length() + 1):
        lab = labels.Value(i)
        name_attr = TDataStd_Name()
        has_name = lab.FindAttribute(TDataStd_Name.GetID(), name_attr)
        nm = name_attr.Get().PrintToString() if has_name else "<unnamed>"
        shp = shape_tool.GetShape(lab)
        bbox = Bnd_Box()
        brepbndlib.Add(shp, bbox)
        xmin,ymin,zmin,xmax,ymax,zmax = bbox.Get()
        out.append((nm, (xmax-xmin, ymax-ymin, zmax-zmin), (xmin,ymin,zmin,xmax,ymax,zmax)))
    return out

if __name__ == "__main__":
    for nm, dims, bb in load(sys.argv[1]):
        print(f"{nm}\tdx={dims[0]:.4f} dy={dims[1]:.4f} dz={dims[2]:.4f}\tbb={bb}")
