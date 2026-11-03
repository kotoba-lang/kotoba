#!/usr/bin/env python3
"""Observe native CSS rule rendering and breakout refusal."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'kotoba/css_sheet.kotoba'
TEST = ROOT / 'test/native/css_sheet_test.kotoba'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--amu',type=Path,required=True); ap.add_argument('--amu-sha256',required=True); ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if (platform.system(),platform.machine()) != ('Darwin','arm64'): raise ValueError('requires native macOS ARM64')
    amu=a.amu.resolve(strict=True)
    if sha(amu)!=a.amu_sha256: raise ValueError('Amu digest mismatch')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    tracked=[amu,MODULE,TEST,Path(__file__).resolve()];pins={str(p):sha(p) for p in tracked}
    def run(name,module,expected):
        modules={'css-sheet':module,'css-sheet-test':TEST};lock=out/(name+'.ksl')
        lock.write_text('KSL2\nentry '+str(TEST.resolve())+'\n'+''.join('module '+n+' '+str(p.resolve())+'\n' for n,p in sorted(modules.items()))+
                        ''.join('file '+sha(p)+' '+str(p.resolve())+'\n' for p in sorted(modules.values())))
        binary=out/name;env={'PATH':'/nonexistent','LANG':'C'}
        c=subprocess.run([str(amu),'compile',str(TEST),'--source-lock',str(lock),'-o',str(binary)],cwd=ROOT,env=env,capture_output=True,timeout=180)
        if c.returncode or c.stderr: raise RuntimeError(('compile',name,c.returncode,c.stderr[-500:]))
        r=subprocess.run([str(binary)],cwd=ROOT,env=env,capture_output=True,timeout=180)
        if r.returncode or r.stderr or r.stdout!=expected: raise RuntimeError(('verdict',name,r.returncode,r.stdout,r.stderr[-500:]))
        return {'binarySha256':sha(binary),'lockSha256':sha(lock)}
    positive=run('css',MODULE,b'42\n'); text=MODULE.read_text();needle='(string-contains? s ";")'
    if text.count(needle)!=1: raise ValueError('negative mutation anchor changed')
    mutant=out/'mutant.kotoba';mutant.write_text(text.replace(needle,'false'));negative=run('css-negative',mutant,b'7\n')
    if any(sha(p)!=pins[str(p)] for p in tracked): raise ValueError('source changed during gate')
    receipt={'status':'PASS_NATIVE_CSS_SHEET','inputs':pins,'positive':positive,'breakoutMutationRejected':negative,
             'completeCssCoreParity':False,'siteGenerated':False,'publicationQualified':False}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'])
if __name__=='__main__':main()
