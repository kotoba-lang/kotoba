#!/usr/bin/env python3
"""Observe two synthetic Noise endpoints on isolated Linux loopback."""
import json, os, socket, subprocess, time
from pathlib import Path

root=Path('/work');image=root/'test.elf';results={}
cases = (os.environ['FLEET_CASE_ONLY'],) if 'FLEET_CASE_ONLY' in os.environ else ('good','wrong','wrong-server','tampered','bad-ack','bad-record')
for case in cases:
 directory=root/('case-'+case);directory.mkdir()
 with socket.socket() as p:
  p.bind(('127.0.0.1',0));address='127.0.0.1:'+str(p.getsockname()[1])
 common=dict(PATH='/usr/bin:/bin',KEXE_STACK_BYTES='8388608',KEXE_FUEL='100000000000',
             KEXE_STRUCTURED_REPORT='1',KEXE_SECCOMP='if-available',KEXE_CAP_RESOURCES_35='/work')
 re=dict(common,KEXE_ALLOW='35,38,43,44,46,47',KEXE_CAP_RESOURCES_43=address)
 se=dict(common,KEXE_ALLOW='38,45,46,47',KEXE_CAP_RESOURCES_45=address)
 def call(mode,env):return subprocess.run([str(image),mode,str(directory),address],env=env,capture_output=True,timeout=180)
 def check(r,label):
  if r.returncode or r.stderr or b':status :ok :result 0 ' not in r.stdout:
   raise ValueError((case,label,r.returncode,r.stdout[-500:],r.stderr[-800:]))
 check(call('init',re),'init')
 receiver=subprocess.Popen([str(image),'recv-'+case,str(directory),address],env=re,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  deadline=time.monotonic()+45
  while not (directory/'ready').exists():
   if receiver.poll() is not None:raise ValueError((case,'receiver exited',receiver.communicate()))
   if time.monotonic()>=deadline:raise TimeoutError(case+' readiness')
   time.sleep(.05)
  check(call('send-'+case,se),'sender')
  stdout,stderr=receiver.communicate(timeout=180)
  check(subprocess.CompletedProcess([],receiver.returncode,stdout,stderr),'receiver')
 finally:
  if receiver.poll() is None:receiver.kill();receiver.wait(timeout=5)
 results[case]='PASS';print(case,'PASS',flush=True)
(root/'duplex-result.json').write_text(json.dumps({'status':'PASS_FLEET_NOISE_DUPLEX', 'cases':results,
 'scope':'two processes, isolated Linux ARM loopback, synthetic deterministic keys; no real roster, live fleet or constant-time qualification'},indent=2)+'\n')
