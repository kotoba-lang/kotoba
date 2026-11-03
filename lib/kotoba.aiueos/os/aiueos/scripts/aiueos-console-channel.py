#!/usr/bin/env python3
"""Finite console RPC inside one existing authenticated SSH channel.

Mac administration transport only. Native nonce/signature/approval policy is
still enforced by the board. A failed in-flight request is never retried.
"""
import json
import os
import re
import select
import struct
import subprocess
import threading
import time

MAGIC = b'ITONAMI-CONSOLE1\n'
MAX_REQUEST = 1024
MAX_RESPONSE = 1 << 20
HEADER = struct.Struct('>QBI')  # request identity, payload kind, byte length
ALLOWED = {'status', 'pointer', 'console-key', 'screenshot-band'}


def allowed_request(operation,args):
    if operation=='status': return not args
    count={'pointer':4,'console-key':2,'screenshot-band':3}.get(operation)
    return (count is not None and len(args)==count and
            re.fullmatch('nonce=[0-9a-f]{16}',args[0]) is not None and int(args[0][6:],16)>0)


def read_exact(stream, count, boundary=False):
    result = bytearray()
    while len(result) < count:
        part = stream.read(count-len(result))
        if not part:
            if boundary and not result: return None
            raise ValueError('truncated console channel request')
        result.extend(part)
    return bytes(result)


def serve(reader, writer, execute):
    """SSH has already authenticated; validate the finite RPC before dispatch."""
    writer.write(MAGIC); writer.flush(); previous = 0
    while True:
        prefix = read_exact(reader,4,boundary=True)
        if prefix is None: return
        size = struct.unpack('>I',prefix)[0]
        if not 0 < size <= MAX_REQUEST: raise ValueError('console request size refused')
        request = json.loads(read_exact(reader,size))
        if not isinstance(request,dict) or set(request) != {'id','operation','args'}:
            raise ValueError('console request shape refused')
        identity = request['id']; operation = request['operation']; args = request['args']
        if type(identity) is not int or not previous < identity < 1 << 63:
            raise ValueError('console request identity refused')
        if not isinstance(operation,str) or not isinstance(args,list) or len(args)>4 or any(type(v) is not str for v in args):
            raise ValueError('console request arguments refused')
        previous = identity
        if operation not in ALLOWED or not allowed_request(operation,args):
            kind,payload = 2,b'{"error":"operation refused"}'
        else:
            try: kind,payload = execute([operation,*args])
            except (ValueError,RuntimeError,AssertionError,OSError):
                # Never return exception text, typed data or private paths.
                kind,payload = 2,b'{"error":"operation refused"}'
        if kind not in (0,1,2) or not isinstance(payload,bytes) or len(payload)>MAX_RESPONSE:
            raise ValueError('console response shape refused')
        writer.write(HEADER.pack(identity,kind,len(payload))); writer.write(payload); writer.flush()


class Channel:
    def __init__(self, host):
        if host != 'itonami-6600h': raise ValueError('unsupported management host')
        self.lock = threading.RLock(); self.identity = 0; self.closed = False
        self.process = subprocess.Popen(['/usr/bin/ssh','-T','-o','BatchMode=yes',
            '-o','ConnectTimeout=5','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3',
            host,'console-session'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,bufsize=0)
        try:
            if self.read(len(MAGIC),time.monotonic()+15) != MAGIC:
                raise RuntimeError('unexpected console channel protocol')
        except (OSError,RuntimeError,TimeoutError):
            self.close(); raise

    def read(self, size, until):
        result = bytearray()
        while len(result)<size:
            remaining = until-time.monotonic()
            if remaining<=0 or not select.select([self.process.stdout],[],[],remaining)[0]:
                raise TimeoutError('console channel deadline expired')
            part = os.read(self.process.stdout.fileno(),size-len(result))
            if not part: raise RuntimeError('console channel closed')
            result.extend(part)
        return bytes(result)

    def request(self, operation, args):
        with self.lock:
            if self.closed: raise RuntimeError('console channel closed; reconnect required')
            self.identity+=1
            data=json.dumps({'id':self.identity,'operation':operation,'args':list(args)},separators=(',',':')).encode()
            if len(data)>MAX_REQUEST: raise ValueError('console request size refused')
            try:
                wire=memoryview(struct.pack('>I',len(data))+data)
                while wire:
                    sent=self.process.stdin.write(wire)
                    if not sent: raise RuntimeError('console request write failed')
                    wire=wire[sent:]
                until=time.monotonic()+25
                identity,kind,size=HEADER.unpack(self.read(HEADER.size,until))
                if identity!=self.identity or kind not in (0,1,2) or size>MAX_RESPONSE:
                    raise RuntimeError('console response identity/shape differs')
                payload=self.read(size,until)
            except (OSError,RuntimeError,TimeoutError):
                # Dispatch may already have happened. Do not replay it.
                self.close(); raise
            if kind==2: raise RuntimeError('console operation refused')
            return kind,payload

    def close(self):
        with self.lock:
            if self.closed: return
            self.closed=True
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=3)
            for stream in (self.process.stdin,self.process.stdout):
                if stream: stream.close()
