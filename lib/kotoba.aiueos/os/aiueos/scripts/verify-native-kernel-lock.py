#!/usr/bin/env python3
"""Stage negative source-lock controls for an actual native build record.

Diagnostic observation only; this is not the native CDCI controller verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess


def pin(p):
    raw = p.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main(compiler, build, out):
    state = json.loads((build/'build-state.json').read_text())
    assert platform.system()=='Linux' and platform.machine() in ('aarch64','arm64','x86_64')
    assert pin(compiler)==state['compiler'] and state['nativeCompilerExecution']
    lock = build/'kernel.ksl'
    assert pin(lock)==state['sourceLock']
    command = next(c['argv'] for c in state['calls'] if c['argv'][0]=='compile')
    out.mkdir(parents=True,exist_ok=False)
    raw=lock.read_text().splitlines()
    roots=[Path(line[5:]) for line in raw if line.startswith('root ')]
    extra=out/'extra.kotoba';extra.write_text('(ns unused (:export [main]))\n(defn main [] :i64 0)\n')
    cases={}
    files=[line for line in raw if line.startswith('file ')]
    head=[line for line in raw if not line.startswith('file ')]
    cases['missing-file']=head+files[1:]
    cases['hash-drift']=head+['file '+'0'*64+' '+files[0].split(' ',2)[2]]+files[1:]
    cases['extra-file']=head+sorted([*files,f'file {pin(extra)["sha256"]} {extra}'],key=lambda line:line.split(' ',2)[2])
    swapped=list(raw); positions=[i for i,line in enumerate(raw) if line.startswith('root ')]
    assert len(positions)>=2
    swapped[positions[0]],swapped[positions[1]]=swapped[positions[1]],swapped[positions[0]]
    cases['root-order']=swapped
    cases['duplicate-file']=head+files+[files[-1]]
    cases['digest']=raw
    records=[]
    for name,lines in cases.items():
        staged=out/(name+'.ksl');staged.write_text('\n'.join(lines)+'\n')
        image=out/(name+'.elf');args=list(command)
        args[args.index('--output')+1]=str(image)
        args[args.index('--source-lock')+1]=str(staged)
        args[args.index('--source-lock-sha256')+1]='0'*64 if name=='digest' else pin(staged)['sha256']
        r=subprocess.run([str(compiler),*args],env=dict(PATH='/nonexistent',KEXE_STACK_BYTES='8388608',KEXE_CAP_RESOURCES_35=':'.join(map(str,[*roots,out]))),capture_output=True,timeout=240)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        assert r.returncode==1 and b'E6015' in r.stderr and b'KEXE_TRAP' not in r.stderr and not image.exists(),(name,r.returncode,r.stderr)
        records.append(dict(name=name,exit=r.returncode,diagnostic=r.stderr.decode(),sourceLock=pin(staged),noArtifact=True))
    report=dict(status='PASS_NATIVE_KERNEL_LOCK_REFUSALS',compiler=pin(compiler),originalBuildState=pin(build/'build-state.json'),originalSourceLock=pin(lock),moduleCount=state['sourceModuleCount'],records=records,nativeCDCI=False,fullKernelQualified=False)
    (out/'lock-refusals.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],len(records),'controls',state['sourceModuleCount'],'modules')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--compiler',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.compiler.resolve(),a.build.resolve(),a.output.resolve())
