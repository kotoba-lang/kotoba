#!/usr/bin/env python3
"""Relay bytes between stdio and the task VM's loopback; no protocol processing."""
import socket,sys,os,select
s=socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=20)
s.setblocking(False)
while True:
 r,_,_=select.select([sys.stdin.buffer,s],[],[],60)
 if not r: raise TimeoutError('relay idle')
 if sys.stdin.buffer in r:
  b=os.read(0,65536)
  if not b:
   s.shutdown(socket.SHUT_WR)
  else:
   s.setblocking(True);s.sendall(b);s.setblocking(False)
 if s in r:
  b=s.recv(65536)
  if not b: break
  os.write(1,b)
