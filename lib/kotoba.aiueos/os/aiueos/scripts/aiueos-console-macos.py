#!/usr/bin/env python3
"""Mac loopback RFB console -> existing key-authenticated SSH debug bridge.

Host administration adapter only; the OS input reducers remain native Kotoba.
No app origin, arbitrary command, remote listener, clipboard, or app approval.
The OS-native SSH/Kekkai and interactive performance gates remain separate.
"""
import argparse
import collections
import ctypes
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import threading
import time
import zlib


def private_file(path):
    path = Path(path)
    s = path.lstat()
    if path.is_symlink() or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise ValueError('configuration/credential must be an owner-only regular file')
    if not path.is_file(): raise ValueError('not a regular file')
    return path.read_bytes()


def vnc_response(password, challenge):
    """Classic RFB auth via the Mac's existing CommonCrypto DES primitive."""
    if len(password) != 8 or len(challenge) != 16: raise ValueError('invalid VNC credential/challenge size')
    key = bytes(int(f'{c:08b}'[::-1], 2) for c in password)
    cc = ctypes.CDLL('/usr/lib/system/libcommonCrypto.dylib')
    cc.CCCrypt.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                          ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                          ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    cc.CCCrypt.restype = ctypes.c_int32
    k = ctypes.create_string_buffer(key); data = ctypes.create_string_buffer(challenge)
    out = ctypes.create_string_buffer(16); moved = ctypes.c_size_t()
    status = cc.CCCrypt(0, 1, 2, k, 8, None, data, 16, out, 16, ctypes.byref(moved))
    if status != 0 or moved.value != 16: raise RuntimeError('system VNC cipher failed')
    return out.raw


def png_rgb(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('not a PNG screenshot')
    at = 8; payload = bytearray(); dimensions = None; ended = False
    while at+12 <= len(data):
        size = struct.unpack_from('>I', data, at)[0]; kind = data[at+4:at+8]
        if size > 8 << 20 or at+12+size > len(data): raise ValueError('oversized/truncated PNG')
        body = data[at+8:at+8+size]
        if zlib.crc32(kind+body) & 0xffffffff != struct.unpack_from('>I',data,at+8+size)[0]:
            raise ValueError('PNG CRC differs')
        if kind == b'IHDR':
            if dimensions is not None or size != 13: raise ValueError('duplicate/invalid PNG header')
            w,h,bits,color,compression,filtering,interlace = struct.unpack('>IIBBBBB',body)
            if not (0 < w <= 8192 and 0 < h <= 8192 and (bits,color,compression,filtering,interlace)==(8,2,0,0,0)):
                raise ValueError('unsupported screenshot format')
            dimensions = (w,h)
        elif kind == b'IDAT':
            payload.extend(body)
            if len(payload) > 8 << 20: raise ValueError('oversized screenshot')
        elif kind == b'IEND':
            ended = True; break
        at += 12+size
    if dimensions is None or not ended: raise ValueError('incomplete screenshot')
    w,h = dimensions; expected = (w*3+1)*h
    decoder = zlib.decompressobj(); raw = decoder.decompress(payload,expected+1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError('screenshot decompression bounds differ')
    if any(raw[y*(w*3+1)] != 0 for y in range(h)): raise ValueError('unexpected PNG filter')
    return w,h,b''.join(raw[y*(w*3+1)+1:(y+1)*(w*3+1)] for y in range(h))


class Bridge:
    """One worker orders native keys/button edges; only adjacent motion coalesces."""
    def __init__(self, host):
        if host != 'itonami-6600h': raise ValueError('unsupported management host')
        self.host = host; self.cv = threading.Condition(); self.queue = collections.deque()
        self.stopped = False; self.active = False; self.session_nonce = None; self.last_pointer = (0,0,0); self.errors = 0; self.input_serial=0
        self.thread = threading.Thread(target=self.run,daemon=True); self.thread.start()

    def ssh(self, *args, screenshot=False):
        control=Path.home()/'.ssh/itonami-6600h/console-control'
        r = subprocess.run(['/usr/bin/ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',
                           '-o','ControlMaster=auto','-o','ControlPersist=60',
                           '-o','ControlPath='+str(control),self.host,*args],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
        if r.returncode != 0: raise RuntimeError('bounded SSH management operation failed')
        if screenshot: return r.stdout
        reply = json.loads(r.stdout)
        if reply.get('nativeSSH') is not False: raise RuntimeError('unexpected management transport')
        return reply

    def begin(self):
        self.session_nonce = self.ssh('status')['bootNonce']

    def input(self, kind, *values):
        item = (kind,tuple(values))
        with self.cv:
            if self.stopped: return
            if self.session_nonce is None: raise RuntimeError('no authenticated console session')
            if kind == 'pointer':
                # Preserve every down/up edge and ordering relative to keys.
                edge=values[2]!=self.last_pointer[2]
                if edge: item=('pointer-edge',tuple(values))
                if not edge and self.queue and self.queue[-1][0] == kind and self.queue[-1][1][2] == values[2]:
                    self.queue[-1] = item
                else: self.queue.append(item)
                self.last_pointer = tuple(values)
            else: self.queue.append(item)
            if len(self.queue) > 256: raise RuntimeError('console input queue limit reached')
            self.input_serial+=1
            self.cv.notify()

    def run(self):
        while True:
            with self.cv:
                self.cv.wait_for(lambda:self.queue or self.stopped)
                if self.stopped and not self.queue: return
                kind,values = self.queue.popleft()
                self.active = kind != '_barrier'
            if kind == '_barrier':
                values[0].set(); continue
            if kind == 'pointer-edge':kind='pointer'
            try: self.ssh(kind,'nonce='+self.session_nonce,*(str(v) for v in values))
            except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):
                self.errors += 1
                print('ITONAMI_CONSOLE_INPUT_REFUSED',flush=True)
            finally:
                with self.cv: self.active=False; self.cv.notify_all()

    def capture_band(self, first, count):
        # At most one32-row capture can be ahead of a newly queued input.
        with self.cv: self.cv.wait_for(lambda:not self.queue and not self.active)
        raw=self.ssh('screenshot-band','nonce='+self.session_nonce,str(first),str(count),screenshot=True)
        if len(raw)<24: raise ValueError('truncated management band')
        magic,nonce,row,rows,w,h=struct.unpack_from('<8sQHHHH',raw)
        if not (magic==b'IRGBBND1' and nonce==int(self.session_nonce,16) and (row,rows)==(first,count)
                and 0<w<=3200 and first+count<=h<=8192 and len(raw)==24+w*count*3):
            raise ValueError('management band identity/geometry differs')
        return w,h,raw[24:]

    def capture(self):
        w,h,first=self.capture_band(0,1); image=bytearray(w*h*3);image[:w*3]=first
        for row in range(1,h,32):
            count=min(32,h-row);nw,nh,rgb=self.capture_band(row,count)
            if (nw,nh)!=(w,h): raise ValueError('native dimensions changed')
            image[row*w*3:(row+count)*w*3]=rgb
        return w,h,bytes(image)

    def release(self):
        barrier = threading.Event()
        with self.cv:
            # Session close cancels unsent input. A final release is ordered
            # after any in-flight SSH command and before a new client starts.
            x,y,left = self.last_pointer
            self.queue.clear()
            self.queue.append(('pointer',(x,y,0)))
            self.queue.append(('_barrier',(barrier,)))
            self.last_pointer = (x,y,0); self.cv.notify()
        if not barrier.wait(20): raise RuntimeError('console release did not drain')


def receive(sock, size):
    out = bytearray()
    while len(out) < size:
        part = sock.recv(size-len(out))
        if not part: raise EOFError()
        out.extend(part)
    return bytes(out)


DEFAULT_FORMAT = struct.pack('>BBBBHHHBBB3x',32,24,0,1,255,255,255,16,8,0)
MODIFIERS = set(range(0xffe1,0xffef)) | {0xff7e}
KEYS = {0xff08:14,0xff09:15,0xff0d:28,0xff1b:1,0xff51:75,0xff52:72,0xff53:77,0xff54:80,
        0xffff:83,0xff50:71,0xff57:79,0xff55:73,0xff56:81}
KEYS.update({0xffbe+i:59+i for i in range(10)}); KEYS.update({0xffc8:87,0xffc9:88})
for char,code in zip('abcdefghijklmnopqrstuvwxyz',[30,48,46,32,18,33,34,35,23,36,37,38,50,49,24,25,16,19,31,20,22,47,17,45,21,44]):
    KEYS[ord(char)] = code
KEYS[32] = 57
for i,char in enumerate('1234567890'): KEYS[ord(char)] = 2+i


def pixel_format(raw):
    bpp,depth,endian,true,r,g,b,rs,gs,bs = struct.unpack('>BBBBHHHBBB3x',raw)
    if bpp not in (8,16,32) or not 0 < depth <= bpp or endian not in (0,1) or true != 1:
        raise ValueError('unsupported RFB pixel format')
    masks = []
    for maximum,shift in ((r,rs),(g,gs),(b,bs)):
        if not (0 < maximum <= 255 and maximum & (maximum+1) == 0 and shift+maximum.bit_length() <= bpp):
            raise ValueError('invalid channel mask')
        masks.append(maximum << shift)
    if masks[0]&masks[1] or masks[0]&masks[2] or masks[1]&masks[2]: raise ValueError('overlapping channel masks')
    return bpp//8,endian,r,g,b,rs,gs,bs


def pixels(rgb, fmt):
    size,endian,r,g,b,rs,gs,bs = fmt
    if fmt == (4,0,255,255,255,16,8,0):
        out = bytearray(len(rgb)//3*4); out[0::4]=rgb[2::3]; out[1::4]=rgb[1::3]; out[2::4]=rgb[0::3]
        return out
    out = bytearray(); order = 'big' if endian else 'little'
    for i in range(0,len(rgb),3):
        value = ((rgb[i]*r//255)<<rs)|((rgb[i+1]*g//255)<<gs)|((rgb[i+2]*b//255)<<bs)
        out.extend(value.to_bytes(size,order))
    return out


def session(sock, bridge, password, interval):
    sock.settimeout(30); sock.sendall(b'RFB 003.008\n')
    version=receive(sock,12)
    if version not in (b'RFB 003.003\n',b'RFB 003.007\n',b'RFB 003.008\n',b'RFB 003.889\n'):
        raise ValueError('unsupported RFB version')
    print('ITONAMI_CONSOLE_PROTOCOL '+version[4:11].decode('ascii'),flush=True)
    if version==b'RFB 003.003\n': sock.sendall(struct.pack('>I',2))
    else:
        sock.sendall(b'\x01\x02')
        if receive(sock,1) != b'\x02': raise ValueError('VNC authentication required')
    print('ITONAMI_CONSOLE_PASSWORD_CHALLENGE',flush=True)
    challenge = secrets.token_bytes(16); sock.sendall(challenge)
    if not hmac.compare_digest(receive(sock,16),vnc_response(password,challenge)):
        print('ITONAMI_CONSOLE_AUTHENTICATION_REFUSED',flush=True)
        reason = b'Authentication failed'; sock.sendall(struct.pack('>II',1,len(reason))+reason); return
    sock.sendall(struct.pack('>I',0)); receive(sock,1)
    print('ITONAMI_CONSOLE_AUTHENTICATED',flush=True)
    bridge.begin()
    width,height,initial = bridge.capture()
    name = b'Itonami 6600H - local SSH console (diagnostic)'
    sock.sendall(struct.pack('>HH',width,height)+DEFAULT_FORMAT+struct.pack('>I',len(name))+name)
    print('ITONAMI_CONSOLE_FRAMEBUFFER_READY',flush=True)
    lock = threading.Lock(); cv = threading.Condition(); requests = collections.deque(maxlen=1)
    closed = threading.Event(); fmt = [pixel_format(DEFAULT_FORMAT)]; modifiers = set()

    def frames():
        previous = None; last_capture = 0; cached = initial; last_errors = bridge.errors; next_row=0
        last_response=0;last_input=bridge.input_serial
        try:
            while not closed.is_set():
                with cv:
                    cv.wait_for(lambda:requests or closed.is_set())
                    if closed.is_set(): return
                    incremental,x,y,w,h = requests.popleft(); selected_format = fmt[0]
                    original_request=(incremental,x,y,w,h)
                closed.wait(max(0,interval-(time.monotonic()-last_capture)))
                if closed.is_set(): return
                if previous is not None and incremental:
                    # A client request receives one bounded strip, then the
                    # next request advances the scan. Never wait a full screen
                    # before giving queued keys/button edges a turn.
                    row=y+(next_row%h); count=min(32,y+h-row)
                    nw,nh,rgb=bridge.capture_band(row,count)
                    if (nw,nh)!=(width,height): raise ValueError('native dimensions changed; reconnect required')
                    changed=bytearray(cached);changed[row*width*3:(row+count)*width*3]=rgb;cached=bytes(changed)
                    next_row=(row-y+count)%h;y=row;h=count
                elif previous is not None:
                    nw,nh,cached = bridge.capture()
                    if (nw,nh) != (width,height): raise ValueError('native dimensions changed; reconnect required')
                last_capture = time.monotonic()
                same = incremental and cached == previous
                if bridge.errors != last_errors:
                    with lock: sock.sendall(b'\x02')
                    last_errors = bridge.errors
                if same and bridge.input_serial==last_input and time.monotonic()-last_response<1:
                    # Keep the incremental request outstanding while scanning
                    # unchanged strips. Native Screen Sharing waits for a
                    # changed update rather than polling after an empty one.
                    with cv:
                        if not requests: requests.append(original_request)
                    continue
                with lock:
                    part = b''.join(cached[(row*width+x)*3:(row*width+x+w)*3] for row in range(y,y+h))
                    sock.sendall(b'\0\0\0\1'+struct.pack('>HHHHi',x,y,w,h,0)+pixels(part,selected_format))
                last_response=time.monotonic();last_input=bridge.input_serial
                previous = cached
        except (OSError,ValueError,RuntimeError,EOFError,subprocess.TimeoutExpired):
            closed.set()
            try: sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass

    thread = threading.Thread(target=frames,daemon=True); thread.start()
    try:
        while not closed.is_set():
            try: kind = receive(sock,1)[0]
            except socket.timeout: continue  # Authenticated idle is not a disconnect.
            if kind == 0:
                receive(sock,3); next_format = pixel_format(receive(sock,16))
                with cv: fmt[0] = next_format
            elif kind == 2:
                _,count = struct.unpack('>BH',receive(sock,3))
                if count > 128: raise ValueError('encoding list too large')
                encodings = struct.unpack('>'+str(count)+'i',receive(sock,count*4)) if count else ()
                # RFC6143: Raw remains valid even when absent from this list.
            elif kind == 3:
                incremental,x,y,w,h = struct.unpack('>BHHHH',receive(sock,9))
                if incremental not in (0,1) or not (w and h and x+w<=width and y+h<=height):
                    raise ValueError('framebuffer request outside native viewport')
                with cv: requests.append((incremental,x,y,w,h)); cv.notify()
            elif kind == 4:
                down,_,keysym = struct.unpack('>BHI',receive(sock,7))
                if down not in (0,1): raise ValueError('invalid key direction')
                if keysym in MODIFIERS:
                    if down: modifiers.add(keysym)
                    else: modifiers.discard(keysym)
                elif down and not modifiers and keysym in KEYS: bridge.input('console-key',KEYS[keysym])
            elif kind == 5:
                buttons,x,y = struct.unpack('>BHH',receive(sock,5))
                if x>=width or y>=height: raise ValueError('pointer outside native viewport')
                bridge.input('pointer',x,y,buttons&1)
            elif kind == 6:
                receive(sock,3); size = struct.unpack('>I',receive(sock,4))[0]
                if size > 65536: raise ValueError('clipboard too large')
                receive(sock,size)  # Clipboard transfer is deliberately not an OS operation.
            else: raise ValueError('unsupported RFB message')
    finally:
        closed.set()
        with cv: cv.notify_all()
        try: bridge.release()
        finally: thread.join(timeout=2)


def main(a):
    cfg = json.loads(private_file(a.config)); password = private_file(cfg['vncPassword'])
    if len(password) != 8: raise ValueError('VNC password must be exactly8 bytes')
    vnc_response(password,bytes(16))  # Fail before listening if the system primitive is unavailable.
    bridge = Bridge(cfg.get('sshHost','itonami-6600h'))
    listener = socket.socket(); listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',int(cfg.get('vncPort',22078)))); listener.listen(1)
    print('ITONAMI_CONSOLE_LOOPBACK_READY',flush=True)
    while True:
        sock,peer = listener.accept()
        try:
            with sock: session(sock,bridge,password,max(.02,float(cfg.get('frameInterval',.03))))
        except (OSError,ValueError,RuntimeError,EOFError,subprocess.TimeoutExpired) as error:
            # Never log passwords, screenshots or typed data.
            print('ITONAMI_CONSOLE_SESSION_CLOSED '+type(error).__name__,flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--config',type=Path,required=True)
    main(p.parse_args())
