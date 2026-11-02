#!/usr/bin/env python3
"""Compile a frozen, already executed receive corpus with an explicit producer.

Exact whole ELF/EFI equality carries the earlier runtime evidence; it is not
a new runtime execution. Native Amu discovers/checks/compiles/packages. Python
only stages declared immutable source/artifact bytes and observes commands.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main(a):
    if not __debug__: raise RuntimeError('assertions must remain enabled')
    out = a.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    stage = out/'source'
    stage.mkdir()
    report = dict(schema='kekkai.receive-compiler-parity.v1',state='STAGING',calls=[],
        observer=pin(Path(__file__)),freshRuntimeExecution=False,physicalDeployment=False,
        productQualified=False,trustedConsent=False)
    def save(): (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        assert pin(a.reference)['sha256'] == a.reference_sha256
        old = json.loads(a.reference.read_text())
        assert old['state'] in ['PASS_FULL_NATIVE_APPLICATION_RECEIVE','DETECTED_NORMALLY_COMPLETED_RECEIVE_FAULT']
        values = old['receiveResult']['observed']
        assert values['cases'] == values['rxFrames'] == values['released'] == 2081 and values['terminal'] == 2
        assert values['rxErrors'] == 0 and len(old['shapeCheckpoints']) == 76
        if old['fault']: assert values['nativeErrors'] > 0
        else: assert values['nativeErrors'] == 0 and not old['receiveResult']['violations']
        assert all(x['match'] for x in old['shapeCheckpoints']) and not old['observationFailures']
        profile = load('receive_profiles',ROOT/'scripts/check-kekkai-application-receive-os.py')
        mac_path = a.amu_source/'scripts/seed/check-aiueos-user-macos-native.py'
        mac = load('receive_parity_native',mac_path)
        assert mac.verify_macho(a.compiler) == dict(bytes=3826784,sha256=profile.COMPILER_PROFILES[a.compiler_profile])
        base = a.reference.parent/'source'
        for virtual,sha in old['sourceGraph'].items():
            source = base/virtual.lstrip('/')
            assert pin(source)['sha256'] == sha
            target = stage/virtual.lstrip('/')
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
        for name,key in [('boot-font.bin','bootFont'),('boot-user-slot.bin','userSlot'),('receive.ksl','sourceLock')]:
            assert pin(base/name) == old[key]
            shutil.copyfile(base/name,stage/name)
        assert pin(base/'kernel.elf') == old['kernel'] and pin(base/'boot.efi') == old['efi']
        flags = next(x['argv'][:-2] for x in old['calls'] if x['label']=='kernel.elf')
        roots = flags[8:flags.index('--source-lock')]
        for root in roots[1::2]: (stage/root.lstrip('/')).mkdir(parents=True,exist_ok=True)
        report.update(compiler=pin(a.compiler),compilerProfile=a.compiler_profile,
            profilesSource=pin(ROOT/'scripts/check-kekkai-application-receive-os.py'),nativeHelper=pin(mac_path),
            reference=dict(receipt=pin(a.reference),state=old['state'],compiler=old['compiler'],fault=old['fault'],
                observed=values,kernel=old['kernel'],efi=old['efi']),sourceGraph=old['sourceGraph'],sourceLock=old['sourceLock'])
        def run(label,argv):
            result = mac.native_run(a.compiler,stage,*argv)
            (out/(label+'.stdout')).write_bytes(result.stdout)
            (out/(label+'.stderr')).write_bytes(result.stderr)
            report['calls'].append(dict(label=label,argv=argv,exit=result.returncode))
            save()
            return result.stdout
        discovered = run('modules',['modules',flags[1],*roots])
        graph = {}
        for line in discovered.decode().splitlines():
            namespace,virtual = line.split(' ',1)
            graph[virtual] = pin(stage/virtual.lstrip('/'))['sha256']
        assert graph == old['sourceGraph'] and len(graph) == 42
        for name in ['kernel.elf','kernel-repeat.elf']: run(name,[*flags,'--output',name])
        for name in ['boot.efi','boot-repeat.efi']:
            run(name,['package-aiueos-boot','kernel.elf','--output',name,'--font','boot-font.bin',
                '--user-slot','boot-user-slot.bin','--pci-resources','v1'])
        assert pin(stage/'kernel.elf') == pin(stage/'kernel-repeat.elf') == old['kernel']
        assert pin(stage/'boot.efi') == pin(stage/'boot-repeat.efi') == old['efi']
        report.update(state='PASS_CURRENT_COMPILER_EXECUTED_ARTIFACT_PARITY',kernel=pin(stage/'kernel.elf'),
            efi=pin(stage/'boot.efi'),wholeELFIdentical=True,wholeEFIIdentical=True)
        save()
        print(report['state'],old['fault'],flush=True)
    except BaseException as error:
        report.update(state='FAILED',failure=str(error),failureType=type(error).__name__)
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,required=True)
    parser.add_argument('--compiler-profile',choices=['pool-v4-main-2f842'],required=True)
    parser.add_argument('--amu-source',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--reference-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args())
