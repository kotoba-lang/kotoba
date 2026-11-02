#!/usr/bin/env python3
"""Run synthetic fleet sender cases against a task-owned remote Linux ARM VM."""
import json,subprocess,sys,time,shlex
from pathlib import Path
if len(sys.argv) != 8:
 raise SystemExit('usage: check SSH_HOST OBSERVER_PATH PODMAN_PATH MACHINE BIND_IP RUN_ID LOCAL_BUILD_DIR')
ssh_host,observer,pod,machine,host,run_id,build_dir=sys.argv[1:]
out={}
for case in ('good','wrong','wrong-server','tampered','bad-ack','bad-record'):
 cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',ssh_host,shlex.join(['python3',observer,pod,machine,host,run_id,case])]
 p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  line=p.stdout.readline(); row=json.loads(line); assert row['ready'] and row['case']==case, line
  addr=host+':'+str(row['port'])
  sender=['podman','run','--rm','--pull','never','--platform','linux/arm64','-v',str(Path(build_dir).resolve())+':/work:ro','-e','KEXE_STACK_BYTES=8388608','-e','KEXE_FUEL=100000000000','-e','KEXE_STRUCTURED_REPORT=1','-e','KEXE_SECCOMP=if-available','-e','KEXE_ALLOW=38,45,46,47','-e','KEXE_CAP_RESOURCES_45='+addr,'docker.io/library/python:3.12-alpine','/work/runner-arm.elf','send-'+case,'/work',addr]
  r=subprocess.run(sender,text=True,capture_output=True,timeout=180)
  stdout,stderr=p.communicate(timeout=180)
  if r.returncode or r.stderr or ':status :ok :result 0 ' not in r.stdout or p.returncode or stderr:raise ValueError((case,'sender',r.returncode,r.stdout,r.stderr,'receiver',p.returncode,stdout,stderr))
  response=json.loads(stdout.strip()); assert response['receiver']=='PASS' and response['case']==case,response
  out[case]={'sender':r.stdout.strip(),'receiver':response['stdout']};print(case,'PASS',flush=True)
 except BaseException:
  if p.poll() is None:p.terminate();p.wait(timeout=5)
  raise
open(Path(build_dir)/('cross-host-'+run_id+'.json'),'x').write(json.dumps(out,indent=2)+'\n')
