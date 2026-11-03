#!/usr/bin/env python3
"""Observe the native JSON fixture and negative control on Linux x86-64."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'lib/kotoba.json/src/json/core.kotoba'
TEST=ROOT/'lib/kotoba.json/test/kotoba/native_json_test.kotoba'
LEDGER=ROOT/'lib/kotoba.json/local-changes.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def image(p,expected):
    if p.is_symlink() or not p.is_file() or sha(p)!=expected:raise ValueError('native image digest mismatch')
    return p.resolve(strict=True)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('compiler','runner','output'):ap.add_argument('--'+key,type=Path,required=True)
    for key in ('compiler-sha256','runner-sha256'):ap.add_argument('--'+key,required=True)
    a=ap.parse_args()
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):raise ValueError('requires Linux x86-64')
    compiler=image(a.compiler,a.compiler_sha256);runner=image(a.runner,a.runner_sha256)
    if sha(CORE)!=json.loads(LEDGER.read_text())['added']['src/json/core.kotoba']['sha256']:raise ValueError('JSON source digest mismatch')
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    tracked=[compiler,runner,CORE,TEST,LEDGER,Path(__file__).resolve()];pins={str(p):sha(p) for p in tracked}
    env={'PATH':'/nonexistent','KEXE_CAP_RESOURCES_35':str(out),'KEXE_STACK_BYTES':'8388608'}
    def run(name,mutant,expected):
        src=out/name/'src';(src/'json').mkdir(parents=True);shutil.copyfile(CORE,src/'json/core.kotoba')
        fixture=TEST.read_text()
        if mutant:
            anchor='(good? "{\\"x\\":1,\\"x\\":2}" "{\\"x\\":2}")'
            changed='(good? "{\\"x\\":1,\\"x\\":2}" "{\\"x\\":3}")'
            if fixture.count(anchor)!=1:raise ValueError('negative control anchor drift')
            fixture=fixture.replace(anchor,changed)
        entry=src/'test.kotoba';entry.write_text(fixture);paths=sorted(src.rglob('*.kotoba'))
        lock=out/(name+'.ksl');lock.write_text('KSL1\nentry '+str(entry)+'\nroot '+str(src)+'\n'+''.join('file '+sha(p)+' '+str(p)+'\n' for p in paths))
        artifact=out/(name+'.kx64')
        build=subprocess.run([str(compiler),'compile',str(entry),'--target','x86_64-linux','--output',str(artifact),'--format','kx64-v1','--source-path',str(src),'--source-lock',str(lock),'--source-lock-sha256',sha(lock)],cwd=out,env=env,capture_output=True,timeout=900)
        if build.returncode or build.stderr:raise RuntimeError(('native compile failed',name,build.returncode,build.stderr[-500:]))
        header,payload=artifact.read_bytes().split(b'\n\n',1);m=re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0',header)
        if not m or int(m[1])!=len(payload) or payload[0]!=0xe9:raise ValueError('invalid native payload')
        raw=out/(name+'.bin');raw.write_bytes(payload)
        result=subprocess.run([str(runner),str(raw),'0','0','x86_64','-','--'],cwd=out,env=dict(env,KEXE_ALLOW='-',KEXE_FUEL='off',KEXE_STRUCTURED_REPORT='1',KEXE_STRING_POOL='268435456'),capture_output=True,timeout=300)
        if result.returncode or result.stderr or not re.search(rb':status :ok\s+:result '+str(expected).encode()+rb'\b',result.stdout):raise RuntimeError(('native result mismatch',name,result.returncode,result.stdout[-500:],result.stderr[-500:]))
        return {'artifactSha256':sha(artifact),'lockSha256':sha(lock),'result':expected}
    positive=run('json-native',False,42);negative=run('json-native-negative',True,7)
    if any(sha(p)!=pins[str(p)] for p in tracked):raise ValueError('source or image changed during execution')
    receipt={'status':'PASS_BOUNDED_JSON_NATIVE_X86_64','inputs':pins,'positive':positive,'negative':negative,'fullJsonQualified':False}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'])
if __name__=='__main__':main()
