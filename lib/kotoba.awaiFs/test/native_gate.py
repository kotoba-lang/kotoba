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
    io_compiler=None
    if target=='linux-x86_64':
        if not a.x86_io_amu:raise ValueError('x86 file I/O compiler checkout is required')
        io_amu=a.x86_io_amu.resolve();io_pin=pins['x86FileCompiler']
        revision=subprocess.run(['git','-C',str(io_amu),'rev-parse','HEAD'],capture_output=True,text=True,check=True,timeout=30).stdout.strip()
        io_compiler=io_amu/io_pin['path']
        if revision!=io_pin['revision'] or io_compiler.is_symlink() or not io_compiler.is_file() or io_compiler.stat().st_size!=io_pin['bytes'] or sha(io_compiler)!=io_pin['sha256']:
            raise ValueError('x86 file I/O compiler pin mismatch')
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
        'awai/fs/forest_blocks.kotoba':ROOT/'src/awai/fs/forest_blocks.kotoba',
        'awai/fs/forest_index.kotoba':ROOT/'src/awai/fs/forest_index.kotoba',
        'awai/fs/forest_file.kotoba':ROOT/'src/awai/fs/forest_file.kotoba',
        'ipld/car/pack.kotoba':REPO/'lib/kotoba.ioIpldCar/src/ipld/car/pack.kotoba',
        'ipld/dag_cbor_write.kotoba':REPO/'lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba',
        'zstd/frame_header.kotoba':REPO/'lib/org.ietf.zstd/src/zstd/frame_header.kotoba',
        **{f'multiformats/{name}.kotoba':REPO/f'lib/kotoba.ioMultiformats/src/multiformats/{name}.kotoba' for name in ['cid','byte_cid','sha256']}}
    corpus=ROOT/'corpus/v1.json';data=json.loads(corpus.read_text())
    stage=Path(__file__).with_name('stage_corpus.py')
    spec=importlib.util.spec_from_file_location('fixed_literals',stage);literal=importlib.util.module_from_spec(spec);spec.loader.exec_module(literal)
    zstd_test=REPO/'lib/org.ietf.zstd/test/zstd/frame_header_test.kotoba'
    forest_fixture=ROOT/'test/fixtures/forest-part0.car.zst'
    forest_fixture2=ROOT/'test/fixtures/forest-part1.car.zst'
    watched=[ROOT/'schema/v1.json',ROOT/'native-inputs.json',ROOT/'test/writer.kotoba',ROOT/'test/values.kotoba',ROOT/'test/pack_values.kotoba',ROOT/'test/forest_file_io.kotoba',forest_fixture,forest_fixture2,zstd_test,*source.values(),compiler,provider,corpus,stage,Path(__file__)]
    if io_compiler:watched.append(io_compiler)
    inputs={str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p):sha(p) for p in watched}
    initial={p:sha(p) for p in watched};results=[]
    def run_case(kind,index,case,control=None):
        name=f'{kind}-{index}'+('-'+control if control else '')
        directory=out/name;src=directory/'src';src.mkdir(parents=True)
        file_case=case.get('name')=='forest_file_io'
        for relative_name,original in source.items():
            if relative_name=='awai/fs/forest_file.kotoba' and not file_case:continue
            if relative_name in {'awai/fs/forest_blocks.kotoba','awai/fs/forest_index.kotoba','zstd/frame_header.kotoba'} and case.get('name') not in {'zstd_header','forest_file_io'}:continue
            if case.get('name') in {'zstd_header','forest_file_io'} and relative_name not in {'zstd/frame_header.kotoba','awai/fs/forest_file.kotoba','awai/fs/forest_blocks.kotoba','awai/fs/forest_index.kotoba','multiformats/sha256.kotoba','multiformats/cid.kotoba','multiformats/byte_cid.kotoba'}:continue
            if relative_name=='awai/fs/chunk_plan.kotoba' and case.get('name')!='chunk_plan_values':continue
            if kind=='primitive' and case['name']=='writer' and relative_name not in {'ipld/dag_cbor_write.kotoba','multiformats/cid.kotoba'}:continue
            if kind!='pack' and case.get('name')!='pack_values' and relative_name=='ipld/car/pack.kotoba':continue
            if kind=='primitive' and case['name']=='pack_values' and relative_name=='awai/fs/logical_file.kotoba':continue
            p=src/relative_name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,p)
        fixture=(zstd_test if case['name']=='zstd_header' else ROOT/'test'/case['file']).read_text() if kind=='primitive' else literal.fixture(case,kind,index)
        if file_case:
            original=forest_fixture.read_bytes()
            if hashlib.sha256(original).hexdigest()!='87a1d2773c099ef49af8fc7b9b00b43123a4e83ab1bc3f1f2b3fca0278fb62df':raise ValueError('Forest fixture pin mismatch')
            second=forest_fixture2.read_bytes()
            if hashlib.sha256(second).hexdigest()!='33469df01bb4f837d655da9b232a366910ab4a575094235ffc875029f46ad206':raise ValueError('second Forest fixture pin mismatch')
            (directory/'fixture-second').write_bytes(second)
            if target!='macos-arm64':fixture=fixture.replace('"/fixture-second"',json.dumps(str(directory/'fixture-second')))
            for file_name,offset in [('fixture',None),('fixture-corrupt',119),('fixture-hidden',1639),('fixture-badfooter',1751)]:
                contents=bytearray(original)
                if offset is not None:contents[offset]^=1
                (directory/file_name).write_bytes(contents)
                if target!='macos-arm64':fixture=fixture.replace('"/'+file_name+'"',json.dumps(str(directory/file_name)))
            (directory/'fixture-short').write_bytes(original[:-1])
            if target!='macos-arm64':fixture=fixture.replace('"/fixture-short"',json.dumps(str(directory/'fixture-short')))
            if target!='macos-arm64':fixture=fixture.replace('"/fixture-missing"',json.dumps(str(directory/'fixture-missing')))
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
        elif control=='wrong-zstd-literal-byte':
            needle='(vector-i64 164 128 4 1 85 18 32 136'
            if fixture.count(needle)!=1:raise ValueError('native Zstd literal control anchor drift')
            fixture=fixture.replace(needle,needle.replace('164 128','165 128'))
        elif control=='wrong-zstd-sequence-count':
            needle='(not= (record-get [:ref :zstd/sequences] sequences :count) 16)'
            if fixture.count(needle)!=1:raise ValueError('native Zstd sequence control anchor drift')
            fixture=fixture.replace(needle,needle.replace('16','15'))
        elif control=='wrong-zstd-fse-table':
            needle='(vector-i64 0 4 0 0 4 16 1 5 32 3 5 0 4 5 0 6 5 0'
            if fixture.count(needle)!=1:raise ValueError('native Zstd FSE control anchor drift')
            fixture=fixture.replace(needle,needle.replace('0 4 0 0 4 16','0 4 1 0 4 16'))
        elif control=='wrong-zstd-sequence-value':
            needle='(vector-i64 295 7935 259 0 8165 8168'
            if fixture.count(needle)!=1:raise ValueError('native Zstd sequence value control anchor drift')
            fixture=fixture.replace(needle,needle.replace('295 7935','294 7935'))
        elif control=='wrong-zstd-block-digest':
            needle='(sha/digest-hex (record-get [:ref :zstd/execution] executed :bytes)) "3a3d9308758b3a794400d6d5c9e219ee38a15333bd83ddcf502ca65ef369e435"'
            if fixture.count(needle)!=1:raise ValueError('native Zstd block digest control anchor drift')
            fixture=fixture.replace(needle,needle.replace('"3a3d','"0a3d'))
        elif control=='wrong-zstd-integrated-digest':
            needle='(sha/digest-hex (record-get [:ref :zstd/decoded-block] integrated :bytes)) "3a3d9308758b3a794400d6d5c9e219ee38a15333bd83ddcf502ca65ef369e435"'
            if fixture.count(needle)!=1:raise ValueError('native Zstd integrated digest control anchor drift')
            fixture=fixture.replace(needle,needle.replace('"3a3d','"0a3d'))
        elif control=='wrong-zstd-frame-digest':
            needle='f1d148ea23e71ce7a3578d639382ba4d491a57b9d131409f6ce881c19bb576ba'
            if fixture.count(needle)!=1:raise ValueError('native Zstd frame digest control anchor drift')
            fixture=fixture.replace(needle,'0'+needle[1:])
        elif control=='wrong-forest-block-digest':
            needle='(sha/digest-hex (result-value-of [:result :vector-i64 :keyword] found (vector-i64))) "88493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd"'
            if fixture.count(needle)!=1:raise ValueError('native Forest block digest control anchor drift')
            fixture=fixture.replace(needle,needle.replace('"8849','"0849'))
        elif control=='wrong-forest-indexed-digest':
            needle='(sha/digest-hex (result-value-of [:result :vector-i64 :keyword] indexed (vector-i64))) "88493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd"'
            if fixture.count(needle)!=1:raise ValueError('native Forest indexed digest control anchor drift')
            fixture=fixture.replace(needle,needle.replace('"8849','"0849'))
        elif control=='wrong-forest-file-digest':
            needle='88493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd'
            if fixture.count(needle)!=1:raise ValueError('native Forest file digest control anchor drift')
            fixture=fixture.replace(needle,'0'+needle[1:])
        elif control=='wrong-second-forest-digest':
            needle='7786c19371f6b8a948e551624e0dd2993ca6c21439bf876f67a14821807b8c88'
            if fixture.count(needle)!=1:raise ValueError('second Forest digest control anchor drift')
            fixture=fixture.replace(needle,'0'+needle[1:])
        elif control=='allow-group-error-fallback':
            p=src/'awai/fs/forest_file.kotoba';body=p.read_text()
            needle='(recur (+ i 1)) r)'
            if body.count(needle)!=1:raise ValueError('group fallback control anchor drift')
            p.write_text(body.replace(needle,'(recur (+ i 1)) (recur (+ i 1)))'))
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
            if runtime and not virtual:
                child_env.update(KEXE_ALLOW='35' if file_case else '-',KEXE_FUEL='off',KEXE_STRUCTURED_REPORT='1',KEXE_STRING_POOL='268435456')
                if file_case:child_env['KEXE_CAP_RESOURCES_35']=str(directory)
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
                selected=io_compiler if file_case else compiler
                args=[selected,'compile',entry_arg,'--target','x86_64-linux','--output',binary,'--format','kx64-v1',
                     '--source-path',src_arg,'--source-lock',lock,'--source-lock-sha256',sha(lock)]
                if file_case:
                    denied=call('compile-denied',args,check=False)
                    if denied.returncode==0 or b'E7101' not in denied.stdout+denied.stderr or binary.exists():
                        raise RuntimeError(('x86 capability denial control failed',denied.returncode,denied.stdout[-500:],denied.stderr[-500:]))
                    args+=['--project-capabilities','35']
                call('compile',args)
                header,payload=binary.read_bytes().split(b'\n\n',1)
                m=re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0',header)
                if not m or int(m[1])!=len(payload) or not payload or payload[0]!=0xe9:raise ValueError('invalid Native payload framing')
                raw=directory/'program.bin';raw.write_bytes(payload)
                r=call('execute',[runner,raw,'0','0','x86_64','35' if file_case else '-','--'],check=False,runtime=True)
                m=re.search(rb':status :ok\s+:result (-?[0-9]+)\b',r.stdout)
                if r.returncode or not m:raise RuntimeError(('native runner refused',name,r.returncode,r.stdout[-500:]))
                verdict=int(m[1])
            if not virtual:
                m=re.search(rb':status :ok\s+:result (-?[0-9]+)\b',r.stdout)
                if r.returncode or not m:raise RuntimeError(('native process refused',name,r.returncode,r.stdout[-500:]))
                verdict=int(m[1])
            expected_result=20 if control=='allow-group-error-fallback' else 13 if control=='wrong-second-forest-digest' else 3 if control=='wrong-forest-file-digest' else 137 if control=='wrong-forest-indexed-digest' else 128 if control=='wrong-forest-block-digest' else 118 if control=='wrong-zstd-frame-digest' else 108 if control=='wrong-zstd-integrated-digest' else 94 if control=='wrong-zstd-block-digest' else 85 if control=='wrong-zstd-sequence-value' else 78 if control=='wrong-zstd-fse-table' else 62 if control=='wrong-zstd-sequence-count' else 52 if control=='wrong-zstd-literal-byte' else 42 if control=='wrong-zstd-raw-byte' else 28 if control=='wrong-zstd-block-size' else 12 if control=='wrong-zstd-window' else 8 if control=='allow-plan-overflow' else 1 if control and control!='wrong-cid' else 5 if control=='wrong-cid' else 0
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
    for i,name in enumerate(['writer','values','pack_values','chunk_plan_values','zstd_header','forest_file_io']):
        if not a.only or name in a.only:run_case('primitive',i,{'name':name,'file':name+'.kotoba'})
    if not a.only or 'zstd_header' in a.only:
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-window')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-block-size')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-raw-byte')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-literal-byte')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-sequence-count')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-fse-table')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-sequence-value')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-block-digest')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-integrated-digest')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-zstd-frame-digest')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-forest-block-digest')
        run_case('primitive',4,{'name':'zstd_header','file':'zstd_header.kotoba'},'wrong-forest-indexed-digest')
    if not a.only or 'forest_file_io' in a.only:
        run_case('primitive',5,{'name':'forest_file_io','file':'forest_file_io.kotoba'},'wrong-forest-file-digest')
        run_case('primitive',5,{'name':'forest_file_io','file':'forest_file_io.kotoba'},'wrong-second-forest-digest')
        run_case('primitive',5,{'name':'forest_file_io','file':'forest_file_io.kotoba'},'allow-group-error-fallback')
    if not a.only:
        run_case('positive',0,data['positive'][0],'wrong-cid')
        for control,name in [('allow-file-version','file-version'),('allow-link-codec','codec')]:
            i=next(i for i,c in enumerate(data['negative']) if c['name']==name);run_case('negative',i,data['negative'][i],control)
        run_case('primitive',3,{'name':'chunk_plan_values','file':'chunk_plan_values.kotoba'},'allow-plan-overflow')
    if any(sha(p)!=h for p,h in initial.items()):raise ValueError('input drift during gate')
    receipt={'status':'PASS_NATIVE_AWAI_LOGICAL_FILE','host':[platform.system(),platform.machine(),platform.release()],
             'target':target,'compilerRevision':pins['revision'],'runnerSha256':sha(runner) if runner else None,'inputs':inputs,'cases':results,'allCorpus':not bool(a.only),
             'x86FileCompilerRevision':pins['x86FileCompiler']['revision'] if io_compiler else None,
             'legacyPacksExecuted':not bool(a.only),'nativeIoQualified':False,'productionQualified':False,'hostedFallback':False}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'],len(results),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--amu',type=Path,required=True);p.add_argument('--x86-io-amu',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--only',action='append');p.add_argument('--target',choices=['macos-arm64','linux-arm64','linux-x86_64'])
    main(p.parse_args())
