#!/usr/bin/env python3
from __future__ import annotations
import argparse,re
from pathlib import Path
JAVA_STRING=re.compile(r'"(?P<body>(?:\\.|[^"\\])*)"'); CLASS_RE=re.compile(r"public\s+class\s+(\w+)")

def esc(s): return s.replace("\\","\\\\").replace('"','\\"')
def decoded(s): return s.replace("\\\\","\\")

def replace_unique(text,suffixes,replacement,required):
    ms=[m for m in JAVA_STRING.finditer(text) if decoded(m.group("body")).lower().endswith(suffixes)]
    if not ms:
        if required: raise RuntimeError(f"No recorded string literal ending in {suffixes}")
        return text,0
    if len(ms)!=1: raise RuntimeError(f"Expected one recorded path ending in {suffixes}; got {len(ms)}")
    m=ms[0]; repl='"'+esc(str(Path(replacement).resolve()))+'"'
    return text[:m.start()]+repl+text[m.end():],1

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("recorded_macro",type=Path); ap.add_argument("--tbm",required=True); ap.add_argument("--step"); ap.add_argument("--out-dir",type=Path,required=True); a=ap.parse_args()
    text=a.recorded_macro.read_text(encoding="utf-8")
    text,_=replace_unique(text,(".tbm",),a.tbm,True)
    if a.step:
        text,n=replace_unique(text,(".step",".stp"),a.step,False)
        if n==0: print("WARNING: no STEP path in recorded macro; import path patched only")
    cm=CLASS_RE.search(text)
    if not cm: raise RuntimeError("Could not find public Java class")
    a.out_dir.mkdir(parents=True,exist_ok=True); out=a.out_dir/f"{cm.group(1)}.java"; out.write_text(text,encoding="utf-8"); print(out)
if __name__=="__main__": main()
