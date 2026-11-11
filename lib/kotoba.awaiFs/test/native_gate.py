#!/usr/bin/env python3
"""Stage fixed inputs and observe Amu-built native predicates. No host codecs."""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main(a):
    if (platform.system(),platform.machine())!=('Darwin','arm64'): raise ValueError('requires actual macOS ARM64')
    amu=a.amu.resolve(); pins=json.loads((REPO/'scripts/native-ci-inputs.json').read_text())['amu']
    names=['seed/bootstrap/aarch64-macos/amu-full-root.macho','seed/bootstrap/aarch64-macos/kotoba-packager-root.macho']
    compiler,packager=[amu/p for p in names]
    for name,p in zip(names,[compiler,packager]):
        if p.is_symlink() or sha(p)!=pins['files'][name]['sha256']: raise ValueError('compiler artifact pin mismatch')
        subprocess.run(['/usr/bin/codesign','--verify','--strict',str(p)],capture_output=True,check=True,timeout=30)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source={
        'awai/fs/logical_file.kotoba':ROOT/'src/awai/fs/logical_file.kotoba',
        'ipld/dag_cbor_write.kotoba':REPO/'lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba',
        **{f'multiformats/{name}.kotoba':REPO/f'lib/kotoba.ioMultiformats/src/multiformats/{name}.kotoba' for name in ['cid','cid_hash','sha256']}}
    corpus=ROOT/'corpus/v1.json';data=json.loads(corpus.read_text())
    stage=Path(__file__).with_name('stage_corpus.py')
    spec=importlib.util.spec_from_file_location('fixed_literals',stage);literal=importlib.util.module_from_spec(spec);spec.loader.exec_module(literal)
    watched=[ROOT/'test/writer.kotoba',ROOT/'test/values.kotoba',*source.values(),compiler,packager,corpus,stage,Path(__file__),REPO/'scripts/native-ci-inputs.json']
    inputs={str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p):sha(p) for p in watched}
    initial={p:sha(p) for p in watched};results=[]
    def run_case(kind,index,case,control=None):
        name=f'{kind}-{index}'+('-'+control if control else '')
        directory=out/name;src=directory/'src';src.mkdir(parents=True)
        for target,original in source.items():
            if kind=='primitive' and case['name']=='writer' and target not in {'ipld/dag_cbor_write.kotoba','multiformats/cid.kotoba'}:continue
            p=src/target;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,p)
        fixture=(ROOT/'test'/case['file']).read_text() if kind=='primitive' else literal.fixture(case,kind,index)
        if control=='wrong-cid':
            old=json.dumps(case['cid']);new=json.dumps(case['cid'][:-1]+('a' if case['cid'][-1]!='a' else 'b'))
            if old not in fixture:raise ValueError('golden control anchor drift')
            fixture=fixture.replace(old,new)
        elif control:
            p=src/'awai/fs/logical_file.kotoba';body=p.read_text()
            needle={'allow-file-version':'(not= (record-get [:ref :awai.fs/file] f :version) 1)',
                    'allow-link-codec':'(= (record-get [:ref :multiformats.cid/parts] p :codec) 85)'}[control]
            if body.count(needle)!=1:raise ValueError('native mutation anchor drift')
            p.write_text(body.replace(needle,'false' if control=='allow-file-version' else 'true'))
        entry=src/'corpus.kotoba';entry.write_text(fixture)
        files=sorted(src.rglob('*.kotoba'));lock=directory/'source.ksl'
        lock.write_text('KSL1\nentry /src/corpus.kotoba\nroot /src\n'+''.join('file '+sha(p)+' /'+str(p.relative_to(directory))+'\n' for p in files))
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        if fd!=3:os.dup2(fd,3);os.close(fd)
        calls=[]
        def call(label,args,check=True):
            r=subprocess.run(list(map(str,args)),cwd=directory,pass_fds=(3,),env={'PATH':'/nonexistent','LANG':'C'},capture_output=True,timeout=300)
            (directory/(label+'.stdout')).write_bytes(r.stdout);(directory/(label+'.stderr')).write_bytes(r.stderr)
            calls.append({'step':label,'exit':r.returncode})
            if check and (r.returncode or r.stderr):raise RuntimeError((name,label,r.returncode,r.stderr[-1200:]))
            return r
        try:
            call('compile',[compiler,'compile','/src/corpus.kotoba','--target','aarch64-macos','--output','program.kseed',
                 '--source-path','/src','--source-lock','source.ksl','--source-lock-sha256',sha(lock)])
            r=call('extract',[compiler,'extract-native','program.kseed','--symbol','main','--output','program.raw'])
            m=re.search(rb':offset (\d+), :length (\d+), :arity 0}',r.stdout)
            if not m or int(m[2])!=(directory/'program.raw').stat().st_size:raise ValueError('invalid native entry')
            call('pack',[packager,'program-unsigned.macho','program.raw','fs2-cli-stdio-general',m[1].decode()])
            binary=directory/'program.macho';shutil.copyfile(directory/'program-unsigned.macho',binary);binary.chmod(0o700)
            subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(binary)],check=True,capture_output=True,timeout=30)
            r=call('execute',[binary],check=False)
            if r.stderr or r.returncode!=(1 if control and control!='wrong-cid' else 5 if control=='wrong-cid' else 0):
                raise RuntimeError((name,'native predicate mismatch',r.returncode,r.stdout[-200:],r.stderr[-500:]))
            result={'name':case['name'],'kind':kind,'control':control,'calls':calls,'sourceLock':sha(lock),'artifact':sha(binary),'fixture':sha(entry)}
            results.append(result);(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS',name,case['name'],flush=True)
        finally:os.close(3)
    for kind in ('positive','negative'):
        for i,case in enumerate(data[kind]):
            if not a.only or case['name'] in a.only:run_case(kind,i,case)
    for i,name in enumerate(['writer','values']):
        if not a.only or name in a.only:run_case('primitive',i,{'name':name,'file':name+'.kotoba'})
    if not a.only:
        run_case('positive',0,data['positive'][0],'wrong-cid')
        for control,name in [('allow-file-version','file-version'),('allow-link-codec','codec')]:
            i=next(i for i,c in enumerate(data['negative']) if c['name']==name);run_case('negative',i,data['negative'][i],control)
    if any(sha(p)!=h for p,h in initial.items()):raise ValueError('input drift during gate')
    receipt={'status':'PASS_NATIVE_AWAI_LOGICAL_FILE','host':[platform.system(),platform.machine(),platform.release()],
             'compilerRevision':pins['revision'],'inputs':inputs,'cases':results,'allCorpus':not bool(a.only),
             'legacyPacksExecuted':False,'nativeIoQualified':False,'productionQualified':False,'hostedFallback':False}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'],len(results),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--amu',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--only',action='append')
    main(p.parse_args())
