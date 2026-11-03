#!/usr/bin/env python3
"""Test-only VM receiver and byte relay. Use synthetic keys and a private interface."""
import os,subprocess,socket,sys,time,json,select,shlex
if len(sys.argv) != 6:
 raise SystemExit('usage: observer PODMAN MACHINE BIND_IP RUN_ID CASE')
pod,machine,host,run_id,case=sys.argv[1:]
if not run_id.isalnum(): raise ValueError('run ID must be alphanumeric')
assert case in ('good','wrong','wrong-server','tampered','bad-ack','bad-record')
server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);server.bind((host,0));server.listen(1);server.settimeout(120)
port=server.getsockname()[1]
addr='127.0.0.1:'+str(port)
base='/var/home/core/jun351-cross-'+run_id+'-'+case
q=shlex.quote
common='KEXE_STACK_BYTES=8388608 KEXE_FUEL=100000000000 KEXE_STRUCTURED_REPORT=1 KEXE_SECCOMP=if-available KEXE_ALLOW=35,38,43,44,46,47 KEXE_CAP_RESOURCES_35=/var/home/core KEXE_CAP_RESOURCES_43='+q(addr)
def cmd(mode):return f'env {common} /task/runner-arm.elf {q(mode)} {q(base)} {q(addr)}'
def ssh(command):return [pod,'machine','ssh',machine,command]
subprocess.run(ssh('mkdir '+q(base)),check=True,timeout=20)
r=subprocess.run(ssh(cmd('init')),capture_output=True,text=True,timeout=60)
if r.returncode or ':status :ok :result 0 ' not in r.stdout or r.stderr:raise RuntimeError(('init',r.returncode,r.stdout,r.stderr))
receiver=subprocess.Popen(ssh(cmd('recv-'+case)),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
bridge=None
try:
 deadline=time.monotonic()+60
 while True:
  if receiver.poll() is not None:raise RuntimeError(('receiver early',receiver.communicate()))
  r=subprocess.run(ssh('test -f '+q(base+'/ready')),capture_output=True,timeout=10)
  if r.returncode==0:break
  if time.monotonic()>deadline:raise TimeoutError('ready')
  time.sleep(.2)
 print(json.dumps({'ready':True,'port':port,'case':case}),flush=True)
 conn,peer=server.accept();conn.settimeout(60)
 bridge=subprocess.Popen(ssh('python3 /task/fleet-cross-host-guest-relay.py '+str(port)),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 while True:
  ready,_,_=select.select([conn,bridge.stdout],[],[],70)
  if not ready:raise TimeoutError('relay')
  if conn in ready:
   b=conn.recv(65536)
   if b:os.write(bridge.stdin.fileno(),b)
   else:bridge.stdin.close();break
  if bridge.stdout in ready:
   b=os.read(bridge.stdout.fileno(),65536)
   if not b:break
   conn.sendall(b)
 conn.close()
 out,err=receiver.communicate(timeout=180)
 if receiver.returncode or b':status :ok :result 0 ' not in out or err:raise RuntimeError(('receiver',receiver.returncode,out[-800:],err[-800:]))
 print(json.dumps({'receiver':'PASS','case':case,'peer':peer[0],'stdout':out.decode().strip()}),flush=True)
finally:
 server.close()
 if bridge is not None and bridge.poll() is None:bridge.terminate();bridge.wait(timeout=5)
 if receiver.poll() is None:receiver.terminate();receiver.wait(timeout=5)
