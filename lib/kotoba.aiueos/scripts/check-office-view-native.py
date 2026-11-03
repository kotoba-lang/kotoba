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
def index_of(wire, wanted):
 data=wire.encode();pos=4;index=0
 while pos<len(data)-1:
  fields=[]
  for _ in range(8):
   end=data.index(b':',pos); size=int(data[pos:end]);pos=end+1
   fields.append(data[pos:pos+size].decode());pos+=size
  if fields[3]==wanted:return index
  index+=1
 raise ValueError('target not in view: '+wanted)
report={};images={}
for name,build in [('bunsho',bunsho),('hyokeisan',hyokeisan),('zuhyo',zuhyo)]:
 receipt=json.loads((build/'build-receipt.json').read_text());source=(build/'program.kotoba').read_bytes();wasm=(build/'program.wasm').read_bytes()
 if sha(source)!=receipt['sourceSha256'] or sha(wasm)!=receipt['wasmSha256'] or receipt['compilerSha256']!=args.compiler_sha256:raise ValueError(name+' stale build')
 image=gate.build(name,'program.kotoba',{'program.kotoba':source})
 images[name]=image
 init=gate.run(name+'-init',image,args=['init']).stdout.decode().removesuffix('\n')
 wire=gate.run(name+'-view',image,args=['view',init]).stdout.decode()
 result=gate.run(name+'-decode',parser,args=[wire,'']).stdout.decode().strip()
 count,tag=result.split(':',1)
 if not count.isdigit() or int(count)<2 or tag!='div':raise ValueError((name,result))
 field={'bunsho':'b0','hyokeisan':'c0','zuhyo':'body'}[name]
 content='表現😀\n二行'
 idx=index_of(wire,field)
 event=gate.run(name+'-event',parser,args=[wire,'action',str(idx),'input',content]).stdout.decode()
 if event!='app|input|'+field+'|'+content+'\n':raise ValueError((name,'event mapping'))
 current=gate.run(name+'-current-event',parser,args=[wire,'current',str(idx),'input',content]).stdout.decode()
 if current!=event:raise ValueError((name,'current event mapping'))
 for mode in ('stale-generation','zero-generation'):
  if gate.run(name+'-'+mode,parser,expected=3,args=[wire,mode,str(idx),'input',content]).stdout:raise ValueError((name,mode))
 route,kind,target,value=event.removesuffix('\n').split('|',3)
 edited=gate.run(name+'-edit',image,args=['step',init,target,kind,value]).stdout.decode().removesuffix('\n')
 updated=gate.run(name+'-edited-view',image,args=['view',edited]).stdout.decode()
 if gate.run(name+'-stale-view',parser,expected=3,args=[wire,'stale-view',str(idx),'input',content,updated]).stdout:raise ValueError((name,'stale view'))
 parsed=gate.run(name+'-edited-decode',parser,args=[updated,'']).stdout.decode().strip()
 if content not in updated or not parsed.endswith(':div'):raise ValueError((name,'edited view'))
 button_key={'bunsho':'mode','hyokeisan':'backup-export','zuhyo':'mode'}[name]
 button_idx=index_of(wire,button_key)
 click=gate.run(name+'-button-event',parser,args=[wire,'action',str(button_idx),'click','']).stdout.decode()
 expected_route='host' if name=='hyokeisan' else 'app'
 if click!=expected_route+'|click|'+button_key+'|\n':raise ValueError((name,'button mapping'))
 if expected_route=='app':
  route,kind,target,value=click.removesuffix('\n').split('|',3)
  toggled=gate.run(name+'-button-step',image,args=['step',init,target,kind,value]).stdout.decode().removesuffix('\n')
  if toggled==init:raise ValueError((name,'button did not change state'))
 if name=='bunsho':
  original=json.dumps({'found':True,'document':{'documentId':'d1','title':'旧','revisionId':'r1','body':[{'elementId':'b1','kind':'paragraph','text':'元😀'}]}},ensure_ascii=False)+'\n'
  imported=gate.run('bunsho-original-import',image,args=['legacy-import',original]).stdout.decode().removesuffix('\n')
  legacy_view=gate.run('bunsho-original-view',image,args=['view',imported]).stdout.decode()
  original_idx=index_of(legacy_view,'backup-original')
  if gate.run('bunsho-original-action',parser,args=[legacy_view,'current',str(original_idx),'click','']).stdout!=b'host|click|backup-original|\n':raise ValueError('original action route')
  if gate.run('bunsho-original-extract',image,args=['legacy-original',imported]).stdout.decode()!=original+'\n':raise ValueError('original bytes changed')
 if name=='hyokeisan':
  title='旧表';metadata='[{"sheetId":0,"title":"A"}]';grid='{"A":[["雪"]]}\n'
  imported=gate.run('hyokeisan-original-import',image,args=['legacy',title,metadata,grid]).stdout.decode().removesuffix('\n')
  legacy_view=gate.run('hyokeisan-original-view',image,args=['view',imported]).stdout.decode()
  for part,value in [('title',title),('sheets',metadata),('grid',grid)]:
   key='backup-legacy-'+part;idx=index_of(legacy_view,key)
   if gate.run('hyokeisan-original-action-'+part,parser,args=[legacy_view,'current',str(idx),'click','']).stdout!=('host|click|'+key+'|\n').encode():raise ValueError(key+' action')
   if gate.run('hyokeisan-original-extract-'+part,image,args=['legacy-source',imported,part]).stdout.decode()!=value+'\n':raise ValueError(part+' bytes changed')
 report[name]={'sourceSha256':sha(source),'wasmSha256':sha(wasm),'viewSha256':sha(wire.encode()),'nodes':int(count),'root':tag,
               'editedViewSha256':sha(updated.encode()),'editedNodes':int(parsed.split(':')[0])}
def frame(x):return str(len(x.encode()))+':'+x
def node(tag='div',typ='',key='',value='',text='',children='0'):
 return ''.join(map(frame,[tag,'',typ,key,value,text,'',children]))
# Exercise the actual largest bounded Bunsho view and a late-node action.
maximum='BS3|1'+''.join(map(frame,['題'*341+'x','edit','32']+sum((['p','x'*1024] for _ in range(32)),[])))
large=gate.run('bunsho-max-view',images['bunsho'],args=['view',maximum]).stdout.decode()
if gate.run('bunsho-max-decode',parser,args=[large,'']).stdout!=b'466:div\n':raise ValueError('maximum view rejected')
last=index_of(large,'b31')
if gate.run('bunsho-max-action',parser,args=[large,'current',str(last),'input','最後😀']).stdout!='app|input|b31|最後😀\n'.encode():raise ValueError('maximum view action')
positive='BV2|'+node(children='1')+node('textarea',key='body',value='日本😀\n二行')+'\n'
if gate.run('unicode-multiline',parser,args=[positive,'']).stdout != b'2:div\n':raise ValueError('unicode')
if gate.run('unicode-value-index',parser,args=[positive,'inspect']).stdout != '日本😀\n二行\n'.encode():raise ValueError('incorrect indexed field')
if gate.run('textarea-action',parser,args=[positive,'action','1','input','新😀\n二行']).stdout != 'app|input|body|新😀\n二行\n'.encode():raise ValueError('textarea event')
for label,idx,kind,value in [('negative','-1','input','x'),('past-end','2','input','x'),('root-input','0','input','x'),('wrong-click','1','click',''),('bad-kind','1','submit',''),('textarea-cr','1','input','a\rb')]:
 if gate.run('action-reject-'+label,parser,expected=3,args=[positive,'action',idx,kind,value]).stdout:raise ValueError(label+' output')
button='BV2|'+node('button',typ='button',key='add',text='追加')+'\n'
if gate.run('button-action',parser,args=[button,'action','0','click','']).stdout != b'app|click|add|\n':raise ValueError('button event')
for key in ['backup-import','backup-export','backup-restore','backup-original','backup-legacy-pull','backup-legacy-title','backup-legacy-sheets','backup-legacy-grid','workbook-upgrade']:
 wire='BV2|'+node('button',typ='button',key=key,text='操作')+'\n'
 if gate.run('host-action-'+key,parser,args=[wire,'action','0','click','']).stdout != ('host|click|'+key+'|\n').encode():raise ValueError('host action route '+key)

for label,wire,idx,kind,value in [('click-with-value',button,'0','click','x'),('button-input',button,'0','input','x'),('missing-key','BV2|'+node('button',typ='button')+'\n','0','click',''),('invalid-view','bad','0','click','')]:
 if gate.run('action-reject-'+label,parser,expected=3,args=[wire,'action',idx,kind,value]).stdout:raise ValueError(label+' output')

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
needle=b'(string=? tag "button") (string=? value "")'
if sources['aiueos/office_view.kotoba'].count(needle)!=1:raise ValueError('action mutation anchor')
mutant=dict(sources);mutant['aiueos/office_view.kotoba']=mutant['aiueos/office_view.kotoba'].replace(needle,b'true (string=? value "")')
broken=gate.build('action-mutant','aiueos/office_view_native_test.kotoba',mutant)
if gate.run('action-mutation-detected',broken,args=[positive,'action','1','click','']).stdout!=b'app|click|body|\n':raise ValueError('action negative control')
needle=b'(= rendered-generation current-generation)'
if sources['aiueos/office_view.kotoba'].count(needle)!=1:raise ValueError('generation mutation anchor')
mutant=dict(sources);mutant['aiueos/office_view.kotoba']=mutant['aiueos/office_view.kotoba'].replace(needle,b'true')
broken=gate.build('generation-mutant','aiueos/office_view_native_test.kotoba',mutant)
if gate.run('generation-mutation-detected',broken,args=[positive,'stale-generation','1','input','x']).stdout!=b'app|input|body|x\n':raise ValueError('generation negative control')

gate.finish('PASS_OFFICE_VIEW_NATIVE',observerSHA256=sha(Path(__file__).read_bytes()),apps=report,refusals=list(bad),
            scope='macOS Arm native synthetic views and actions; no Itonami OS rendering/input, QEMU execution, real migration or publication')
