#!/usr/bin/env python3
"""Compare exact office candidate sources on native Mac and browser Wasm.

Usage: script AMU BUNSHO_BUILD HYOKEISAN_BUILD ZUHYO_BUILD OUTPUT CHROME
Synthetic CLI inputs only. This is not an Itonami OS adapter or QEMU test.
"""
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

if len(sys.argv)!=7: raise SystemExit(__doc__)
amu,bunsho,hyokeisan,zuhyo,out,chrome=map(lambda x:Path(x).resolve(),sys.argv[1:])
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_gate',root/'lib/kotoba.hata/scripts/native_gate.py');ng=importlib.util.module_from_spec(spec);spec.loader.exec_module(ng)
spec=importlib.util.spec_from_file_location('wasm_browser',amu/'scripts/seed/check-wasm32-browser.py');wb=importlib.util.module_from_spec(spec);spec.loader.exec_module(wb)
compiler=amu/'seed/bootstrap/aarch64-macos/amu-full-root.macho';packager=amu/'seed/bootstrap/aarch64-macos/kotoba-packager-root.macho'
args=types.SimpleNamespace(compiler=compiler,compiler_sha256='2c551579c06a0228029bb06bae177e93126ecbbc37d636d693c471dbac8d1536',packager=packager,packager_sha256='e95284408f091c8979ef74ece57116a4df2250e61e42074da5dc95ca30264142',output=out)
gate=ng.NativeGate(args)
if not gate.darwin:raise ValueError('this parity gate currently qualifies macOS Arm only')
builds={'bunsho':bunsho,'hyokeisan':hyokeisan,'zuhyo':zuhyo};results={};native={};sources={}
for name,build in builds.items():
 receipt=json.loads((build/'build-receipt.json').read_text());source=(build/'program.kotoba').read_bytes();wasm=(build/'program.wasm').read_bytes()
 if ng.sha(source)!=receipt['sourceSha256'] or ng.sha(wasm)!=receipt['wasmSha256'] or receipt['compilerSha256']!=args.compiler_sha256:raise ValueError(name+' stale candidate')
 sources[name]=source;native[name]=gate.build(name,'program.kotoba',{'program.kotoba':source});results[name]={'candidate':receipt,'checks':[]}
step=0
def compare(name,arguments,expected=0):
 global step
 step+=1;label=f'{name}-{step}'
 native_result=gate.run(label,native[name],expected=expected,args=arguments)
 version,items=wb.run_modules(str(chrome),out/('browser-'+label),[(label,builds[name]/'program.wasm',{'fuel':100000000,'allow':[37,38],'args':arguments})])
 row=items[label];report=row.get('report') or '';match=re.search(r':status :ok :result (-?[0-9]+)',report)
 if row.get('exit')!=0 or row.get('stderr') or row.get('wasmTrap') or not match or int(match.group(1))!=expected:raise ValueError((name,arguments,'wasm refusal',row))
 browser_output=(row.get('output') or '').encode()
 if browser_output!=native_result.stdout:raise ValueError((name,arguments,'native/Wasm output mismatch',ng.sha(browser_output),ng.sha(native_result.stdout)))
 results[name]['checks'].append({'operation':arguments[0],'result':expected,'outputSha256':ng.sha(browser_output),'outputBytes':len(browser_output),'browser':version['product']})
 return browser_output.decode().removesuffix('\n')
for name in builds:
 state=compare(name,['init'])
 text={'bunsho':'段落😀\n二行','hyokeisan':'計算😀\n二行','zuhyo':'本文😀\n二行'}[name]
 field={'bunsho':'b0','hyokeisan':'c0','zuhyo':'body'}[name]
 state=compare(name,['step',state,field,'input',text])
 if text not in state:raise ValueError(name+' missing multiline state')
 expected_prefix={'bunsho':'BS3|1','hyokeisan':'HX1|1','zuhyo':'ZS2|'}[name]
 if not state.startswith(expected_prefix):raise ValueError(name+' unexpected snapshot version')
 view=compare(name,['view',state])
 if not view.startswith('BV2|') or text not in view:raise ValueError(name+' view lacks value')
 if name=='bunsho':
  state=compare(name,['step',state,'mode','click',''])
  if text not in compare(name,['view',state]):raise ValueError('preview lost paragraph')
 elif name=='hyokeisan':
  state=compare(name,['upgrade',state])
  if not state.startswith('HX1|2'):raise ValueError('multiline workbook upgrade')
  state=compare(name,['step',state,'c1','input','=3/2'])
  if '1.5' not in compare(name,['view',state]):raise ValueError('native/Wasm formula display')
  if not compare(name,['formula-audit',state]).startswith('FA1|'):raise ValueError('formula audit missing')
 elif name=='zuhyo':
  state=compare(name,['step',state,'add','click',''])
  state=compare(name,['step',state,'body','input','次のスライド'])
  state=compare(name,['step',state,'prev','click',''])
  if text not in compare(name,['view',state]):raise ValueError('navigation lost first slide')
 compare(name,['view','bad'],expected=3)
# Negative control: a changed native init dispatch must not match the candidate.
original=sources['zuhyo'];needle=b'(string=? op "init")'
if original.count(needle)!=1:raise ValueError('unexpected control source')
mutant=gate.build('control','program.kotoba',{'program.kotoba':original.replace(needle,b'(string=? op "never-init")')})
control=gate.run('control-init',mutant,expected=4,args=['init'])
if control.stdout:raise ValueError('mutant unexpectedly emitted init')
gate.finish('PASS_OFFICE_NATIVE_BROWSER_PARITY',observerSHA256=ng.sha(Path(__file__).read_bytes()),apps=results,
            negativeControl='native init dispatch disabled: result 4, no snapshot',
            scope='macOS Arm native and Chrome Wasm with synthetic data; no Itonami OS, QEMU, real migration or release')
