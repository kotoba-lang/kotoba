# Transient process orchestration. Fixture execution and comparisons are native.
from pathlib import Path
import concurrent.futures,subprocess,time,json,threading,os,random,hashlib
p=Path(__file__).resolve().parent;root=p.parent;version=os.environ.get('CORPUS_RUN','v29')
out=p/('results-'+version);logs=p/('runs-'+version);failed=p/('failures-'+version);pending=p/('pending-'+version)
for d in [out,logs,failed,pending]:d.mkdir(exist_ok=True)
manifest=json.loads((p/'manifest.json').read_text());slow_ids={x['id'] for x in manifest['cases'] if any(t in x['path'] for t in ['vmPerformance/','stTimeConsuming/','stQuadraticComplexityTest/']) or ('diffplaces' in x['path'].lower() and x['indexes']['data']==34) or x['path']=='stStackTests/underflowTest.json'}
lock=threading.Lock();start=time.time();done=0
base=['podman','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','32','--memory','2g','--cpus','1','-e','PATH=/nonexistent','-e','KEXE_STRUCTURED_REPORT=1','-e','KEXE_CAP_RESOURCES_35=/work/paris-full','-e','KEXE_STACK_BYTES=8388608','-v',str(root)+':/work:rw','--entrypoint','/work/native-project/full-state-'+version+'.elf']
(p/('run-'+version+'.json')).write_text(json.dumps({'artifactSha256':hashlib.sha256((root/'native-project'/('full-state-'+version+'.elf')).read_bytes()).hexdigest(),'manifestSha256':hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest(),'nativeOnly':True,'workers':3,'containerMemory':'2g','timeoutSeconds':600,'slowBatchTimeoutSeconds':2700,'slowSuites':['vmPerformance/','stTimeConsuming/','stQuadraticComplexityTest/'],'orderSeed':81,'deadlineResetsOnEachNativeCaseResult':True},indent=2))
def run(f):
 global done
 if (p/('STOP-'+version)).exists():return
 rows=[r for r in f.read_text().splitlines() if not (out/r.split('~')[0]).exists() and not (failed/(r.split('~')[0]+'.json')).exists()];round=0
 while rows and not (p/('STOP-'+version)).exists():
  name='awai81-full-'+version+'-'+f.stem+'-'+str(round);inp=pending/(f.stem+'-'+str(round)+'.txt');inp.write_text('\n'.join(rows))
  cmd=base+['--name',name,'docker.io/library/alpine:3','/work/paris-full/'+pending.name+'/'+inp.name,'/work/paris-full/'+out.name];begin=time.time()
  timeout=2700 if any(x.split('~',1)[0] in slow_ids for x in rows) else 600
  proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE);deadline=time.monotonic()+timeout;completed=0;timedout=False
  while proc.poll() is None:
   count=sum((out/row.split('~')[0]).exists() for row in rows)
   if count>completed:completed=count;deadline=time.monotonic()+timeout
   if time.monotonic()>deadline:
    subprocess.run(['podman','kill',name],capture_output=True);timedout=True;break
   time.sleep(.25)
  stdout,stderr=proc.communicate(timeout=30);code=124 if timedout else proc.returncode

  key=f.stem+'-'+str(round);(logs/(key+'.stdout')).write_bytes(stdout);(logs/(key+'.stderr')).write_bytes(stderr)
  remaining=[r for r in rows if not (out/r.split('~')[0]).exists()]
  receipt={'batch':f.name,'round':round,'exit':code,'seconds':time.time()-begin,'completed':len(rows)-len(remaining),'cases':len(rows)}
  if remaining:
   case=remaining.pop(0).split('~')[0];receipt['unfinishedCase']=case
   (failed/(case+'.json')).write_text(json.dumps({'id':case,'exit':code,'reason':'wall-time' if code==124 else 'native-trap-or-harness','run':key,'stderr':stderr.decode(errors='replace')},indent=2))
  (logs/(key+'.json')).write_text(json.dumps(receipt));rows=remaining;round+=1
 with lock:
  done+=1
  if done%25==0:print('batches',done,'nativeResults',len(list(out.iterdir())),'hostFailures',len(list(failed.iterdir())),'seconds',round_time(time.time()-start),flush=True)
def round_time(x):return int(x+.5)
files=sorted((p/'inputs').glob('*.txt'));random.Random(81).shuffle(files)
files.sort(key=lambda f:any(r.split('~',1)[0] in slow_ids for r in f.read_text().splitlines()))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(run,files))
print('finished','nativeResults',len(list(out.iterdir())),'hostFailures',len(list(failed.iterdir())),flush=True)
