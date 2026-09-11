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
    last = None
    for r in [ref, "origin/"+ref] if not ref.startswith("origin/") else [ref]:
        try: return subprocess.check_output(["git","show",f"{r}:{path}"], cwd=ROOT)
        except subprocess.CalledProcessError as e: last=e
    raise last

def spans(s, start, end):
    out=[]; pos=0
    while True:
        a=s.find(start,pos)
        if a<0: break
        b=s.find(end,a)
        if b<0: raise RuntimeError(f"unclosed {start}")
        b += len(end); out.append((a,b)); pos=b
    return out

def single_span(s,start,end):
    x=spans(s,start,end)
    if len(x)!=1: raise RuntimeError(f"expected one {start}, got {len(x)}")
    return x[0]

def pcd_span(s): return single_span(s,"<Physical Cell Description>","</Physical Cell Description>")
def builder_spans(s): return spans(s,"<BUILDER>","</BUILDER>")

def replace_all_blocks(dst, src, start, end, required=True):
    ds=spans(dst,start,end); ss=spans(src,start,end)
    if not ds and not ss and not required: return dst
    if len(ds)!=len(ss) or (required and not ds):
        raise RuntimeError(f"{start} count mismatch dst={len(ds)} src={len(ss)}")
    for (da,db),(sa,sb) in reversed(list(zip(ds,ss))):
        dst=dst[:da]+src[sa:sb]+dst[db:]
    return dst

def mask_geometry(s):
    patterns=[
      (r"<Physical Cell Description>.*?</Physical Cell Description>","<PCD/>"),
      (r"<BUILDER>.*?</BUILDER>","<BUILDER/>"),
      (r"<DEFAULT BUILDER>.*?</DEFAULT BUILDER>","<DEFAULT_BUILDER/>"),
    ]
    for pat,repl in patterns: s=re.sub(pat,repl,s,flags=re.S)
    return s

def full_geometry_shell(project, source):
    out=replace_all_blocks(project,source,"<BUILDER>","</BUILDER>")
    out=replace_all_blocks(out,source,"<Physical Cell Description>","</Physical Cell Description>")
    out=replace_all_blocks(out,source,"<DEFAULT BUILDER>","</DEFAULT BUILDER>",required=False)
    if mask_geometry(project) != mask_geometry(out):
        raise RuntimeError("non-geometry content changed during shell transplant")
    if len(builder_spans(out)) != len(builder_spans(source)):
        raise RuntimeError("builder count mismatch after shell transplant")
    return out

def replace_field(s, sp, field, old, new):
    a,b=sp; blk=s[a:b]
    pat=r"(\t"+re.escape(field)+r"\t=\t)"+re.escape(old)+r"(?=[\t\r\n])"
    nblk,n=re.subn(pat,r"\g<1>"+new,blk)
    if n!=1: raise RuntimeError(f"{field}: expected one {old!r}, got {n}")
    return s[:a]+nblk+s[b:]

def deltas_pcd(s, ds):
    for f,(o,n) in ds.items(): s=replace_field(s,pcd_span(s),f,o,n)
    return s

def deltas_first_builder(s, ds):
    bs=builder_spans(s)
    if not bs: raise RuntimeError("no BUILDER")
    for f,(o,n) in ds.items():
        s=replace_field(s,builder_spans(s)[0],f,o,n)
    return s

def validate(path):
    p=subprocess.run([sys.executable,str(VALIDATOR),str(path)],cwd=ROOT,
                     capture_output=True,text=True)
    text=(p.stdout or "")+(p.stderr or "")
    return text.count("\nFAIL "),text.count("\nWARN "),text

def assert_two_lines(base,var,fields):
    a=base.splitlines(); b=var.splitlines()
    if len(a)!=len(b): raise RuntimeError("TL line count changed")
    d=[(x,y) for x,y in zip(a,b) if x!=y]
    if len(d)!=2: raise RuntimeError(f"TL expected 2 changed lines, got {len(d)}")
    hit={f for x,y in d for f in fields if f in x and f in y}
    if hit!=set(fields): raise RuntimeError(f"TL fields mismatch: {hit}")

def emit(name,raw,source,scope,purpose,rows,logs):
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

    # Environment control: exact Siemens source.
    emit("HP_CONTROL_hp18650Spiral-DIST.tbm",hp_raw,f"{HP_REF}:{HP_PATH}",
         "none","Known-good CreateFromTbm environment control",rows,logs)

    # Full geometry shell: PCD + BOTH Builders + default-builder selector.
    hps=full_geometry_shell(base,hp)
    emit("HP_SHELL_PROJECT_RCR.tbm",hps.encode("latin-1"),"R005 + HP18650",
         "complete PCD + all BUILDER blocks + DEFAULT BUILDER selector",
         "Localize project geometry versus frozen project model/RCR context",rows,logs)

    # Builder-only broad project discriminator; only active/first Detailed Builder.
    c10=deltas_first_builder(base,C10)
    emit("C10_STAR_BUILDER_PATTERN.tbm",c10.encode("latin-1"),"R005",
         "first/active Detailed Builder: five controlled fields",
         "Builder-only rescue while preserving project PCD/JR diameter",rows,logs)

    # Root-specific tab-length probes; axis relation to electrode width is unproven.
    for name,ds in TL.items():
        v=deltas_pcd(base,ds); assert_two_lines(base,v,ds)
        bp1=pcd_span(base)[1]; vp1=pcd_span(v)[1]
        if base[bp1:]!=v[vp1:]: raise RuntimeError(f"{name}: content after PCD changed")
        emit(name,v.encode("latin-1"),"R005","two PCD Tab m_dLength_mm fields only",
             "Root-specific correlation probe; Ltab-W is NOT a proven axial clearance",
             rows,logs)

    # Independent second full geometry shell.
    c13=full_geometry_shell(base,val)
    emit("C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm",c13.encode("latin-1"),
         "R005 + validationBattery",
         "complete PCD + all BUILDER blocks + DEFAULT BUILDER selector",
         "Independent full geometry-shell/project-model discriminator",rows,logs)

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
   Unmodified Siemens HP18650 source whose generated 13-solid STEP is known clean.
   If this fails in the current STAR environment: STOP.

2) HP_SHELL_PROJECT_RCR.tbm
   Complete HP18650 geometry definition transplanted into project model context:
   PCD + BOTH BUILDER blocks + DEFAULT BUILDER selector.
   Every non-geometry block remains from immutable R005.
   - E004 clears: project geometry content is strongly implicated.
   - Identical E004 while HP_CONTROL passes: investigate model/SIMMOD/MODELMAP or
     other non-geometry context; use C13 as independent shell discriminator.

IF HP_SHELL CLEARS E004 AND MORE GEOMETRY LOCALIZATION IS NEEDED:
3) C10_STAR_BUILDER_PATTERN.tbm
4) TL_A_TAB_RELATION_0p10.tbm
5) TL_B_TAB_RELATION_0p70.tbm

TL_A/TL_B change only two Tab m_dLength_mm fields. Public BDS material does
not prove Tab m_dLength_mm and electrode m_dWidth share a construction axis.
Treat them as root-specific correlation probes, not axial-clearance tests.

IF HP_CONTROL PASSES BUT HP_SHELL STILL HAS IDENTICAL E004:
6) C13_VALIDATION_GEOMETRY_SHELL_PROJECT_RCR.tbm
   Complete validationBattery geometry shell with project model context.

Old C12 is omitted from the primary sequence because its 17.9-mm Detailed
Builder JR target is inconsistent with the project 20.6274-mm PCD/cavity.

Return complete STAR console output for every run. If CreateFromTbm succeeds,
export STEP. A different downstream error clears E004 for localization only;
it is not automatically a production pass. All hybrids/probes are diagnostic.
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
