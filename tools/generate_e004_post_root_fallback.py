#!/usr/bin/env python3
"""Generate the conditional E004 fallback package after ROOT_A/ROOT_B both fail."""
from __future__ import annotations
import csv, hashlib, pathlib, re, subprocess, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "tools/validate_tbm.py"
BASE_REF = "d74b3283cb5d73e114bc141f3f0d18e7c7ed5463"
BASE_PATH = "out/hp2170NCA-RCR-distributed-exact-contact-final.tbm"
BASE_SHA = "2c89d2d9a60e5be6a40ca48fcf29e1075fd67b2764e94436c7c9af1119063ea5"
HP_REF = "tbm-siemens-reference-corpus"
HP_PATH = "tbm_validation/reference/HP18650/hp18650Spiral-DIST.tbm"
VAL_REF = "tbm-rcr-modelmap-fix-exec"
VAL_PATH = "tbm_validation/in_StarCCM_bds/validationBattery.tbm"
OUT = ROOT / "out/e004_post_root_fallback_20260911"
ZIP = ROOT / "out/hp2170NCA-STAR-E004-post-root-fallback-20260911.zip"

TL = {
 "TL_A_TAB_RELATION_0p10.tbm": {
   "+Electrode Tab m_dLength_mm": ("60","64.21"),
   "-Electrode Tab m_dLength_mm": ("60","65.21")},
 "TL_B_TAB_RELATION_0p70.tbm": {
   "+Electrode Tab m_dLength_mm": ("60","64.81"),
   "-Electrode Tab m_dLength_mm": ("60","65.81")},
}
C10 = {
 "m_dSepFeedLength_mm": ("0","10"),
 "m_dSepTailLength_mm": ("0","85"),
 "m_dElectrodeOverlapAtStart_mm": ("8","3"),
 "m_dElectrodeOverlapAtEnd_mm": ("20","40"),
 "m_dMandrelWidth_mm": ("6","0"),
}

def sha(b): return hashlib.sha256(b).hexdigest()

def git_show(ref, path):
    refs = [ref]
    if not ref.startswith("origin/"): refs.append("origin/" + ref)
    last = None
    for r in refs:
        try:
            return subprocess.check_output(["git","show",f"{r}:{path}"], cwd=ROOT)
        except subprocess.CalledProcessError as e:
            last = e
    raise last

def block_span(s, a, b):
    i=s.index(a); j=s.index(b,i)+len(b); return i,j
def pcd_span(s): return block_span(s,"<Physical Cell Description>","</Physical Cell Description>")
def builder_span(s): return block_span(s,"<BUILDER>","</BUILDER>")

def replace_field(s, sp, field, old, new):
    a,b=sp; blk=s[a:b]
    pat=r"(\t"+re.escape(field)+r"\t=\t)"+re.escape(old)+r"(?=[\t\r\n])"
    nblk,n=re.subn(pat,r"\g<1>"+new,blk)
    if n != 1: raise RuntimeError(f"{field}: expected one {old!r}, got {n}")
    return s[:a]+nblk+s[b:]

def deltas_pcd(s, ds):
    for f,(o,n) in ds.items(): s=replace_field(s,pcd_span(s),f,o,n)
    return s
def deltas_builder(s, ds):
    for f,(o,n) in ds.items(): s=replace_field(s,builder_span(s),f,o,n)
    return s

def shell(project, source):
    p0,p1=pcd_span(project); b0,b1=builder_span(project)
    s0,s1=pcd_span(source); t0,t1=builder_span(source)
    out=project[:p0]+source[s0:s1]+project[p1:b0]+source[t0:t1]+project[b1:]
    op1=pcd_span(out)[1]; ob0=builder_span(out)[0]; ob1=builder_span(out)[1]
    if project[p1:b0] != out[op1:ob0]: raise RuntimeError("middle changed")
    if project[b1:] != out[ob1:]: raise RuntimeError("suffix changed")
    return out

def validate(path):
    p=subprocess.run([sys.executable,str(VALIDATOR),str(path)],cwd=ROOT,
                     capture_output=True,text=True)
    text=(p.stdout or "")+(p.stderr or "")
    return text.count("\nFAIL "), text.count("\nWARN "), text

def assert_two_lines(base, var, fields):
    a=base.splitlines(); b=var.splitlines()
    if len(a)!=len(b): raise RuntimeError("TL line count changed")
    d=[(x,y) for x,y in zip(a,b) if x!=y]
    if len(d)!=2: raise RuntimeError(f"TL expected 2 changed lines, got {len(d)}")
    hit={f for x,y in d for f in fields if f in x and f in y}
    if hit != set(fields): raise RuntimeError(f"TL fields mismatch: {hit}")

def emit(name, raw, source, scope, purpose, rows, logs):
    p=OUT/name; p.write_bytes(raw)
    fail,warn,log=validate(p)
    rows.append(dict(filename=name,sha256=sha(raw),source=source,
                     changed_scope=scope,purpose=purpose,
                     validator_fail=fail,validator_warn=warn))
    logs.append((name,log))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base_raw=git_show(BASE_REF,BASE_PATH)
    if sha(base_raw)!=BASE_SHA: raise RuntimeError(f"baseline SHA mismatch: {sha(base_raw)}")
    base=base_raw.decode("latin-1")
    hp_raw=git_show(HP_REF,HP_PATH); hp=hp_raw.decode("latin-1")
    val_raw=git_show(VAL_REF,VAL_PATH); val=val_raw.decode("latin-1")
    rows=[]; logs=[]

    # 1) Unmodified known-good geometry control.
    emit("HP_CONTROL_hp18650Spiral-DIST.tbm",hp_raw,f"{HP_REF}:{HP_PATH}",
         "none","Current STAR/CreateFromTbm environment control",rows,logs)

    # 2) Known-good HP PCD+Builder surrounded by project model/RCR context.
    hps=shell(base,hp)
    emit("HP_SHELL_PROJECT_RCR.tbm",hps.encode("latin-1"),"R005 + HP18650",
         "replace PCD + first active Builder",
         "Localize project geometry versus project model/context",rows,logs)

    # 3) Cleaner Builder-only rescue than old C12.
    c10=deltas_builder(base,C10)
    emit("C10_STAR_BUILDER_PATTERN.tbm",c10.encode("latin-1"),"R005",
         "first active Builder: five controlled fields",
         "Builder-only rescue while preserving project PCD/JR diameter",rows,logs)

    # 4) Tab-length PCD probes. Numerical relation only: axis mapping is unproven.
    for name,ds in TL.items():
        v=deltas_pcd(base,ds); assert_two_lines(base,v,ds)
        bp1=pcd_span(base)[1]; vp1=pcd_span(v)[1]
        if base[bp1:] != v[vp1:]: raise RuntimeError(f"{name}: suffix changed")
        emit(name,v.encode("latin-1"),"R005","two PCD Tab m_dLength_mm fields only",
             "Root-specific tab-length probe; do NOT interpret Ltab-W as a proven axial clearance",
             rows,logs)

    # 5) Independent second shell lineage.
    c13=shell(base,val)
    emit("C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm",c13.encode("latin-1"),
         "R005 + validationBattery","replace PCD + first active Builder",
         "Independent geometry-shell/project-model discriminator",rows,logs)

    with (OUT/"MANIFEST.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with (OUT/"VALIDATOR_LOG.txt").open("w",encoding="utf-8") as f:
        for n,l in logs: f.write(f"===== {n} =====\n{l}\n\n")

    readme=f"""hp2170 NCA — STAR E004 POST-ROOT FALLBACK
USE ONLY IF ROOT_A AND ROOT_B BOTH RETURN THE IDENTICAL E004.

Immutable R005 SHA-256:
{BASE_SHA}

AUTHORITATIVE CONDITIONAL ORDER

1) HP_CONTROL_hp18650Spiral-DIST.tbm
   Unmodified Siemens HP18650 source. Its generated 13-solid STEP is already
   known geometry-clean.
   - If this fails in Robert's current STAR environment: STOP.

2) HP_SHELL_PROJECT_RCR.tbm
   HP18650 PCD + active Detailed Builder, project model/RCR context retained.
   - If E004 clears: project geometry/PCD/Builder content is strongly implicated.
   - If identical E004 remains while HP_CONTROL passes: investigate project
     model/SIMMOD/MODELMAP/non-transplanted context. Run C13 if requested.

IF HP_SHELL CLEARS E004 AND MORE GEOMETRY LOCALIZATION IS NEEDED:

3) C10_STAR_BUILDER_PATTERN.tbm
   Cleaner Builder-only discriminator than old C12; keeps project PCD and
   project JR diameter.

4) TL_A_TAB_RELATION_0p10.tbm
5) TL_B_TAB_RELATION_0p70.tbm
   These change only the two tab-length fields. Public BDS material does NOT
   prove Tab m_dLength_mm and electrode m_dWidth share the same construction
   axis. Treat these as root-specific correlation probes, not axial-clearance
   tests. Stop as soon as E004 clears or changes.

IF HP_CONTROL PASSES BUT HP_SHELL STILL HAS IDENTICAL E004:

6) C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm
   Independent validationBattery geometry shell with project model/RCR context.

C12 is intentionally omitted from the primary sequence because its transplanted
17.9-mm Builder JR target is inconsistent with the project 20.6274-mm PCD/cavity.

For every tested file return complete STAR console output. If CreateFromTbm
succeeds, export STEP. A different downstream error counts as clearing E004 for
localization, not as a production pass.

All hybrids/probes are diagnostic only.
"""
    (OUT/"README.txt").write_text(readme,encoding="utf-8")

    names=[r["filename"] for r in rows]+["README.txt","MANIFEST.csv"]
    with zipfile.ZipFile(ZIP,"w",zipfile.ZIP_DEFLATED) as z:
        for n in names: z.write(OUT/n,arcname=n)
    print("BASE",BASE_SHA)
    print("HP_CONTROL_SOURCE_SHA",sha(hp_raw))
    for r in rows:
        print(r["filename"],r["sha256"],"FAIL",r["validator_fail"],"WARN",r["validator_warn"])
    print("ZIP",ZIP)
    print("ZIP_SHA",sha(ZIP.read_bytes()))

if __name__=="__main__": main()
