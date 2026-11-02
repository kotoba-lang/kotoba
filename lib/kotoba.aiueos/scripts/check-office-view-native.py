#!/usr/bin/env python3
"""Native BV2 consumer against three actual office source candidates.

Usage: script AMU BUNSHO_BUILD HYOKEISAN_BUILD ZUHYO_BUILD OUTPUT
Synthetic observations only; no OS render, QEMU app, storage or release.
"""
import hashlib, importlib.util, json, sys, types
from pathlib import Path
if len(sys.argv) != 6: raise SystemExit(__doc__)
amu,bunsho,hyokeisan,zuhyo,out=map(lambda s:Path(s).resolve(),sys.argv[1:])
root=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('native_gate',root/'lib/kotoba.hata/scripts/native_gate.py');ng=importlib.util.module_from_spec(spec);spec.loader.exec_module(ng)
compiler=amu/'seed/bootstrap/aarch64-macos/amu-full-root.macho';packager=amu/'seed/bootstrap/aarch64-macos/kotoba-packager-root.macho'
args=types.SimpleNamespace(compiler=compiler,compiler_sha256='2c551579c06a0228029bb06bae177e93126ecbbc37d636d693c471dbac8d1536',packager=packager,packager_sha256='e95284408f091c8979ef74ece57116a4df2250e61e42074da5dc95ca30264142',output=out)
gate=ng.NativeGate(args)
if not gate.darwin:raise ValueError('gate currently qualifies macOS Arm only')
paths={'aiueos/office_view.kotoba':root/'lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/office_view.kotoba','aiueos/office_view_native_test.kotoba':root/'lib/kotoba.aiueos/test/aiueos/office_view_native_test.kotoba'}
sources={k:p.read_bytes() for k,p in paths.items()};parser=gate.build('view','aiueos/office_view_native_test.kotoba',sources)
sha=lambda x:hashlib.sha256(x).hexdigest()
report={}
for name,build in [('bunsho',bunsho),('hyokeisan',hyokeisan),('zuhyo',zuhyo)]:
 receipt=json.loads((build/'build-receipt.json').read_text());source=(build/'program.kotoba').read_bytes();wasm=(build/'program.wasm').read_bytes()
 if sha(source)!=receipt['sourceSha256'] or sha(wasm)!=receipt['wasmSha256'] or receipt['compilerSha256']!=args.compiler_sha256:raise ValueError(name+' stale build')
 image=gate.build(name,'program.kotoba',{'program.kotoba':source})
 init=gate.run(name+'-init',image,args=['init']).stdout.decode().removesuffix('\n')
 wire=gate.run(name+'-view',image,args=['view',init]).stdout.decode()
 result=gate.run(name+'-decode',parser,args=[wire,'']).stdout.decode().strip()
 count,tag=result.split(':',1)
 if not count.isdigit() or int(count)<2 or tag!='div':raise ValueError((name,result))
 field={'bunsho':'b0','hyokeisan':'c0','zuhyo':'body'}[name]
 content='表現😀\n二行'
 edited=gate.run(name+'-edit',image,args=['step',init,field,'input',content]).stdout.decode().removesuffix('\n')
 updated=gate.run(name+'-edited-view',image,args=['view',edited]).stdout.decode()
 parsed=gate.run(name+'-edited-decode',parser,args=[updated,'']).stdout.decode().strip()
 if content not in updated or not parsed.endswith(':div'):raise ValueError((name,'edited view'))
 report[name]={'sourceSha256':sha(source),'wasmSha256':sha(wasm),'viewSha256':sha(wire.encode()),'nodes':int(count),'root':tag,
               'editedViewSha256':sha(updated.encode()),'editedNodes':int(parsed.split(':')[0])}
def frame(x):return str(len(x.encode()))+':'+x
def node(tag='div',typ='',key='',value='',text='',children='0'):
 return ''.join(map(frame,[tag,'',typ,key,value,text,'',children]))
positive='BV2|'+node(children='1')+node('textarea',key='body',value='日本😀\n二行')+'\n'
if gate.run('unicode-multiline',parser,args=[positive,'']).stdout != b'2:div\n':raise ValueError('unicode')
if gate.run('unicode-value-index',parser,args=[positive,'inspect']).stdout != '日本😀\n二行\n'.encode():raise ValueError('incorrect indexed field')
# 512 total nodes admitted; 513 and oversized child counts refuse.
full='BV2|'+node(children='16')+(node(children='31')+node('span')*31)*15+node(children='30')+node('span')*30+'\n'
if gate.run('max-nodes',parser,args=[full,'']).stdout != b'512:div\n':raise ValueError('node limit')

bad={'missing-terminator':positive[:-1], 'trailing':'BV2|'+node()+'x\n',
     'unknown-tag':'BV2|'+node('script')+'\n', 'bad-child-count':'BV2|'+node(children='33')+'\n',
     'nonascii-child-count':'BV2|'+node(children='é')+'\n',
     'input-linebreak':'BV2|'+node('input',typ='text',value='a\nb')+'\n',
     'textarea-cr':'BV2|'+node('textarea',value='a\rb')+'\n',
     'noninput-value':'BV2|'+node(value='x')+'\n', 'bad-type':'BV2|'+node('input',typ='password')+'\n',
     'long-key':'BV2|'+node(key='x'*129)+'\n','wrong-boundary':'BV2|1:é'+node()[5:]+'\n',
     'short-field':'BV2|10:hi\n','leading-zero':'BV2|03:div'+node()[5:]+'\n',
     'missing-child':'BV2|'+node(children='1')+'\n',
     'too-many-nodes':'BV2|'+node(children='16')+(node(children='31')+node('span')*31)*16+'\n',
     'depth-13':'BV2|'+node(children='1')*13+node()+'\n'}
for label,wire in bad.items():
 r=gate.run('reject-'+label,parser,expected=3,args=[wire,''])
 if r.stdout:raise ValueError(label+' emitted partial data')
# A skipped attribute check must be detected by the same invalid-tag case.
needle=b'(not (valid-tag? tag))'
if sources['aiueos/office_view.kotoba'].count(needle)!=1:raise ValueError('mutation anchor')
mutant=dict(sources);mutant['aiueos/office_view.kotoba']=mutant['aiueos/office_view.kotoba'].replace(needle,b'false')
broken=gate.build('mutant','aiueos/office_view_native_test.kotoba',mutant)
if gate.run('mutation-detected',broken,args=[bad['unknown-tag'],'']).stdout!=b'1:script\n':raise ValueError('negative control')
gate.finish('PASS_OFFICE_VIEW_NATIVE',observerSHA256=sha(Path(__file__).read_bytes()),apps=report,refusals=list(bad),
            scope='macOS Arm native synthetic inputs; no Itonami OS rendering, QEMU execution, real migration or publication')
