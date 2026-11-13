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
    host=(platform.system(),platform.machine())
    target=a.target or {('Darwin','arm64'):'macos-arm64',('Linux','aarch64'):'linux-arm64',('Linux','x86_64'):'linux-x86_64'}.get(host)
    expected={'macos-arm64':('Darwin','arm64'),'linux-arm64':('Linux','aarch64'),'linux-x86_64':('Linux','x86_64')}
    if target not in expected or host!=expected[target]:raise ValueError('requires the declared actual host ISA')
    pins=json.loads((ROOT/'native-inputs.json').read_text());amu=a.amu.resolve()
    roles={'macos-arm64':['seed/bootstrap/aarch64-macos/amu-full-root.macho','seed/bootstrap/aarch64-macos/kotoba-packager-root.macho'],
           'linux-arm64':['seed/bootstrap/aarch64-linux-static-root.elf','seed/x86_64-kx64-runner.kotoba'],
           'linux-x86_64':['bin/amu-linux-x86_64','seed/x86_64-kx64-runner.kotoba']}
    compiler,provider=[amu/p for p in roles[target]]
    for name,p in zip(roles[target],[compiler,provider]):
        if p.is_symlink() or sha(p)!=pins['files'][name]['sha256']:raise ValueError('native artifact/source pin mismatch')
        if target=='macos-arm64':subprocess.run(['/usr/bin/codesign','--verify','--strict',str(p)],capture_output=True,check=True,timeout=30)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    runner=None
    if target=='linux-x86_64':
        runner=out/'runner.elf';runner_source=out/'runner.kotoba';shutil.copyfile(provider,runner_source)
        r=subprocess.run([str(compiler),'compile',str(runner_source),'--target','x86_64-linux','--output',str(runner),'--format','kx64-runner'],
             cwd=out,env={'PATH':'/nonexistent','KEXE_STACK_BYTES':'8388608','KEXE_CAP_RESOURCES_35':str(out)},capture_output=True,timeout=300)
        (out/'runner-build.stdout').write_bytes(r.stdout);(out/'runner-build.stderr').write_bytes(r.stderr)
        if r.returncode or r.stderr:raise RuntimeError(('native runner derivation failed',r.returncode,r.stderr[-1000:]))
        runner.chmod(0o700)
    source={
        'awai/fs/logical_file.kotoba':ROOT/'src/awai/fs/logical_file.kotoba',
        'awai/fs/chunk_plan.kotoba':ROOT/'src/awai/fs/chunk_plan.kotoba',
        'ipld/car/pack.kotoba':REPO/'lib/kotoba.ioIpldCar/src/ipld/car/pack.kotoba',
        'ipld/dag_cbor_write.kotoba':REPO/'lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba',
        'zstd/frame_header.kotoba':REPO/'lib/org.ietf.zstd/src/zstd/frame_header.kotoba',
        **{f'multiformats/{name}.kotoba':REPO/f'lib/kotoba.ioMultiformats/src/multiformats/{name}.kotoba' for name in ['cid','byte_cid','sha256']}}
    corpus=ROOT/'corpus/v1.json';data=json.loads(corpus.read_text())
    stage=Path(__file__).with_name('stage_corpus.py')
    spec=importlib.util.spec_from_file_location('fixed_literals',stage);literal=importlib.util.module_from_spec(spec);spec.loader.exec_module(literal)
    zstd_test=REPO/'lib/org.ietf.zstd/test/zstd/frame_header_test.kotoba'
    watched=[ROOT/'schema/v1.json',ROOT/'native-inputs.json',ROOT/'test/writer.kotoba',ROOT/'test/values.kotoba',ROOT/'test/pack_values.kotoba',zstd_test,*source.values(),compiler,provider,corpus,stage,Path(__file__)]
    inputs={str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p):sha(p) for p in watched}
    initial={p:sha(p) for p in watched};results=[]
    def run_case(kind,index,case,control=None):
        name=f'{kind}-{index}'+('-'+control if control else '')
        directory=out/name;src=directory/'src';src.mkdir(parents=True)
        for relative_name,original in source.items():
            if relative_name=='zstd/frame_header.kotoba' and case.get('name')!='zstd_header':continue
            if case.get('name')=='zstd_header' and relative_name!='zstd/frame_header.kotoba':continue
            if relative_name=='awai/fs/chunk_plan.kotoba' and case.get('name')!='chunk_plan_values':continue
            if kind=='primitive' and case['name']=='writer' and relative_name not in {'ipld/dag_cbor_write.kotoba','multiformats/cid.kotoba'}:continue
            if kind!='pack' and case.get('name')!='pack_values' and relative_name=='ipld/car/pack.kotoba':continue
            if kind=='primitive' and case['name']=='pack_values' and relative_name=='awai/fs/logical_file.kotoba':continue
            p=src/relative_name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,p)
        fixture=(zstd_test if case['name']=='zstd_header' else ROOT/'test'/case['file']).read_text() if kind=='primitive' else literal.fixture(case,kind,index)
        if control=='wrong-cid':
            old=json.dumps(case['cid']);new=json.dumps(case['cid'][:-1]+('a' if case['cid'][-1]!='a' else 'b'))
            if old not in fixture:raise ValueError('golden control anchor drift')
            fixture=fixture.replace(old,new)
        elif control=='wrong-zstd-window':
            needle='(not= (record-get [:ref :zstd/header] forest :window-size) 2097152)'
            if fixture.count(needle)!=1:raise ValueError('native Zstd control anchor drift')
            fixture=fixture.replace(needle,needle.replace('2097152','2097151'))
        elif control=='wrong-zstd-block-size':
            needle='(not= (record-get [:ref :zstd/block-header] first-block :size) 59)'
            if fixture.count(needle)!=1:raise ValueError('native Zstd block control anchor drift')
            fixture=fixture.replace(needle,needle.replace('59','58'))
        elif control=='wrong-zstd-raw-byte':
            needle='(vector-i64 58 162 101 114 111 111 116 115'
            if fixture.count(needle)!=1:raise ValueError('native Zstd raw control anchor drift')
            fixture=fixture.replace(needle,needle.replace('58 162','57 162'))
        elif control=='allow-plan-overflow':
            p=src/'awai/fs/chunk_plan.kotoba';body=p.read_text()
            needle='(> count 1024)'
            if body.count(needle)!=1:raise ValueError('native mutation anchor drift')
            p.write_text(body.replace(needle,'false'))
        elif control:
            p=src/'awai/fs/logical_file.kotoba';body=p.read_text()
            needle={'allow-file-version':'(not= (record-get [:ref :awai.fs/file] f :version) 1)',
                    'allow-link-codec':'(= (record-get [:ref :multiformats.cid/parts] p :codec) 85)'}[control]
            if body.count(needle)!=1:raise ValueError('native mutation anchor drift')
            p.write_text(body.replace(needle,'false' if control=='allow-file-version' else 'true'))
        entry=src/'corpus.kotoba';entry.write_text(fixture)
        files=sorted(src.rglob('*.kotoba'));lock=directory/'source.ksl'
        virtual=target=='macos-arm64'
        entry_arg='/src/corpus.kotoba' if virtual else str(entry)
        src_arg='/src' if virtual else str(src)
        lock.write_text('KSL1\nentry '+entry_arg+'\nroot '+src_arg+'\n'+''.join('file '+sha(p)+' '+('/'+str(p.relative_to(directory)) if virtual else str(p))+'\n' for p in files))
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        if fd!=3:os.dup2(fd,3);os.close(fd)
        calls=[]
        env={'PATH':'/nonexistent','LANG':'C'}
        if not virtual:env.update(KEXE_ALLOW='35,37,38,39',KEXE_CAP_RESOURCES_35=':'.join(map(str,[directory,amu])),KEXE_STACK_BYTES='8388608')
        def call(label,args,check=True,runtime=False):
            child_env=dict(env)
            if runtime and not virtual:child_env.update(KEXE_ALLOW='-',KEXE_FUEL='off',KEXE_STRUCTURED_REPORT='1',KEXE_STRING_POOL='268435456')
            r=subprocess.run(list(map(str,args)),cwd=directory,pass_fds=(3,),env=child_env,capture_output=True,timeout=300)
            (directory/(label+'.stdout')).write_bytes(r.stdout);(directory/(label+'.stderr')).write_bytes(r.stderr)
            calls.append({'step':label,'exit':r.returncode})
            if check and (r.returncode or r.stderr):raise RuntimeError((name,label,r.returncode,r.stderr[-1200:]))
            return r
        try:
            if virtual:
                call('compile',[compiler,'compile',entry_arg,'--target','aarch64-macos','--output','program.kseed',
                     '--source-path',src_arg,'--source-lock','source.ksl','--source-lock-sha256',sha(lock)])
                r=call('extract',[compiler,'extract-native','program.kseed','--symbol','main','--output','program.raw'])
                m=re.search(rb':offset (\d+), :length (\d+), :arity 0}',r.stdout)
                if not m or int(m[2])!=(directory/'program.raw').stat().st_size:raise ValueError('invalid native entry')
                call('pack',[provider,'program-unsigned.macho','program.raw','fs2-cli-stdio-general',m[1].decode()])
                binary=directory/'program.macho';shutil.copyfile(directory/'program-unsigned.macho',binary);binary.chmod(0o700)
                subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(binary)],check=True,capture_output=True,timeout=30)
                r=call('execute',[binary],check=False,runtime=True);verdict=r.returncode
            elif target=='linux-arm64':
                payload=directory/'program.kseed';binary=directory/'program.elf'
                call('compile',[compiler,'compile',entry_arg,'--target','aarch64-macos','--output',payload,
                     '--source-path',src_arg,'--source-lock',lock,'--source-lock-sha256',sha(lock)])
                call('pack',[compiler,'compile',provider,'--target','aarch64-linux','--output',binary,'--format','packed','--payload',payload])
                binary.chmod(0o700);r=call('execute',[binary],check=False,runtime=True);verdict=r.returncode
            else:
                binary=directory/'program.kx64'
                call('compile',[compiler,'compile',entry_arg,'--target','x86_64-linux','--output',binary,'--format','kx64-v1',
                     '--source-path',src_arg,'--source-lock',lock,'--source-lock-sha256',sha(lock)])
                header,payload=binary.read_bytes().split(b'\n\n',1)
                m=re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0',header)
                if not m or int(m[1])!=len(payload) or not payload or payload[0]!=0xe9:raise ValueError('invalid Native payload framing')
                raw=directory/'program.bin';raw.write_bytes(payload)
                r=call('execute',[runner,raw,'0','0','x86_64','-','--'],check=False,runtime=True)
                m=re.search(rb':status :ok\s+:result (-?[0-9]+)\b',r.stdout)
                if r.returncode or not m:raise RuntimeError(('native runner refused',name,r.returncode,r.stdout[-500:]))
                verdict=int(m[1])
            if not virtual:
                m=re.search(rb':status :ok\s+:result (-?[0-9]+)\b',r.stdout)
                if r.returncode or not m:raise RuntimeError(('native process refused',name,r.returncode,r.stdout[-500:]))
                verdict=int(m[1])
            expected_result=42 if control=='wrong-zstd-raw-byte' else 28 if control=='wrong-zstd-block-size' else 12 if control=='wrong-zstd-window' else 8 if control=='allow-plan-overflow' else 1 if control and control!='wrong-cid' else 5 if control=='wrong-cid' else 0
            if r.stderr or verdict!=expected_result:
                raise RuntimeError((name,'native predicate mismatch',r.returncode,verdict,r.stdout[-200:],r.stderr[-500:]))
            result={'name':case['name'],'kind':kind,'control':control,'calls':calls,'sourceLock':sha(lock),'artifact':sha(binary),'fixture':sha(entry),'nativeResult':verdict}
            results.append(result);(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS',name,case['name'],flush=True)
        finally:os.close(3)
    for kind in ('positive','negative'):
        for i,case in enumerate(data[kind]):
            if not a.only or case['name'] in a.only:run_case(kind,i,case)
    for i,case in enumerate(data['legacyPacks']['cases']):
        if not a.only or case['name'] in a.only:run_case('pack',i,dict(case,wireHex=case['carHex']))
    for i,name in enumerate(['writer','values','pack_values','chunk_plan_values','zstd_header']):
        if not a.only or name in a.only:run_case('primitive',i,{'name':name,'file':name+'.kotoba'})
    if not a.only or 'zstd_header' in a.only:
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-window')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-block-size')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-raw-byte')
    if not a.only:
        run_case('positive',0,data['positive'][0],'wrong-cid')
        for control,name in [('allow-file-version','file-version'),('allow-link-codec','codec')]:
            i=next(i for i,c in enumerate(data['negative']) if c['name']==name);run_case('negative',i,data['negative'][i],control)
        run_case('primitive',3,{'name':'chunk_plan_values','file':'chunk_plan_values.kotoba'},'allow-plan-overflow')
    if any(sha(p)!=h for p,h in initial.items()):raise ValueError('input drift during gate')
    receipt={'status':'PASS_NATIVE_AWAI_LOGICAL_FILE','host':[platform.system(),platform.machine(),platform.release()],
             'target':target,'compilerRevision':pins['revision'],'runnerSha256':sha(runner) if runner else None,'inputs':inputs,'cases':results,'allCorpus':not bool(a.only),
             'legacyPacksExecuted':not bool(a.only),'nativeIoQualified':False,'productionQualified':False,'hostedFallback':False}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'],len(results),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--amu',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--only',action='append');p.add_argument('--target',choices=['macos-arm64','linux-arm64','linux-x86_64'])
    main(p.parse_args())
