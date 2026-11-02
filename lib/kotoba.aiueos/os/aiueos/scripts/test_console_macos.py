#!/usr/bin/env python3
"""Host RFB adapter controls only; no native OS or human-input qualification."""
import importlib.util
from pathlib import Path
import socket
import struct
import threading
import unittest
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('mac_console',HERE/'aiueos-console-macos.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
PASSWORD = b'fixture1'  # Public test credential only.
rspec=importlib.util.spec_from_file_location('console_remote',HERE/'aiueos-remote.py')
r=importlib.util.module_from_spec(rspec);rspec.loader.exec_module(r)


class Backend:
    def __init__(self):
        self.errors=0;self.input_serial=0;self.events=[];self.captures=0;self.releases=0;self.band_read=threading.Event();self.mutated=False
    def begin(self): pass
    def capture(self):
        self.captures += 1
        return 3,2,bytes([255,0,0,0,255,0,0,0,255,255,255,255,128,128,128,0,0,0])
    def capture_band(self,row,count):
        w,h,rgb=self.capture();self.band_read.set()
        if self.mutated:rgb=bytes([0])+rgb[1:]
        return w,h,rgb[row*w*3:(row+count)*w*3]
    def input(self,*args): self.events.append(args);self.input_serial+=1
    def release(self): self.releases += 1


class Tests(unittest.TestCase):
    def test_system_cipher_public_kat(self):
        # FIPS DES public known-answer vector, with the VNC bit-order inverse.
        key = bytes.fromhex('133457799bbcdff1')
        password = bytes(int(f'{b:08b}'[::-1],2) for b in key)
        self.assertEqual(c.vnc_response(password,bytes.fromhex('0123456789abcdef')*2),
                         bytes.fromhex('85e813540f0ab405')*2)

    def start(self,version=b'RFB 003.008\n'):
        client,server = socket.socketpair(); client.settimeout(8); backend=Backend(); errors=[]
        def serve():
            try:
                with server: c.session(server,backend,PASSWORD,.5)
            except (ValueError,EOFError,OSError,RuntimeError) as e: errors.append(type(e).__name__)
        t=threading.Thread(target=serve); t.start()
        self.addCleanup(client.close); self.addCleanup(lambda:t.join(10))
        self.assertEqual(c.receive(client,12),b'RFB 003.008\n'); client.sendall(version)
        if version==b'RFB 003.003\n':self.assertEqual(c.receive(client,4),struct.pack('>I',2))
        else:
            self.assertEqual(c.receive(client,2),b'\x01\x02'); client.sendall(b'\x02')
        challenge=c.receive(client,16)
        return client,backend,t,challenge,errors

    def authenticate(self,client,challenge):
        client.sendall(c.vnc_response(PASSWORD,challenge)); self.assertEqual(c.receive(client,4),bytes(4))
        client.sendall(b'\x01'); header=c.receive(client,24)
        self.assertEqual(struct.unpack('>HH',header[:4]),(3,2))
        c.receive(client,struct.unpack('>I',header[20:24])[0])

    def test_wrong_auth_never_reaches_backend(self):
        client,b,t,challenge,errors=self.start(); client.sendall(bytes(16))
        self.assertEqual(struct.unpack('>I',c.receive(client,4))[0],1)
        c.receive(client,struct.unpack('>I',c.receive(client,4))[0]); client.close();t.join(5)
        self.assertFalse(t.is_alive());self.assertEqual(b.captures,0);self.assertEqual(b.events,[])

    def test_standard_and_apple_version_negotiation(self):
        for version in (b'RFB 003.003\n',b'RFB 003.007\n',b'RFB 003.889\n'):
            client,b,t,challenge,errors=self.start(version);self.authenticate(client,challenge)
            client.sendall(struct.pack('>BBHH',5,1,3,1));t.join(5);client.close()
            self.assertFalse(t.is_alive());self.assertEqual(b.events,[]);self.assertEqual(b.releases,1)

    def test_wire_pixels_keys_edges_clipboard_and_bounds(self):
        client,b,t,challenge,errors=self.start();self.authenticate(client,challenge)
        # Raw is implicit per RFC6143, even if only another encoding is listed.
        client.sendall(struct.pack('>BBHi',2,0,1,5))
        client.sendall(struct.pack('>BBHHHH',3,0,0,0,3,2))
        self.assertEqual(c.receive(client,4),b'\0\0\0\1')
        self.assertEqual(struct.unpack('>HHHHi',c.receive(client,12)),(0,0,3,2,0))
        self.assertEqual(c.receive(client,24),bytes.fromhex('0000ff0000ff0000ff000000ffffff008080800000000000'))
        client.sendall(struct.pack('>BBHHHH',3,1,0,0,3,2))
        self.assertTrue(b.band_read.wait(2));client.settimeout(.05)
        with self.assertRaises(socket.timeout):c.receive(client,4)
        b.mutated=True;client.settimeout(8)
        self.assertEqual(c.receive(client,4),b'\0\0\0\1');c.receive(client,12)
        self.assertEqual(c.receive(client,24)[:4],bytes(4))
        def key(d,k):client.sendall(struct.pack('>BBHI',4,d,0,k))
        client.sendall(struct.pack('>BBHH',5,1,2,1));key(1,ord('a'));key(0,ord('a'))
        key(1,0xffe3);key(1,ord('a'));key(0,ord('a'));key(0,0xffe3)
        client.sendall(struct.pack('>BBHI',6,0,0,4)+b'text')
        client.sendall(struct.pack('>BBHH',5,0,2,1))
        # Out-of-viewport events must close without forwarding that event.
        client.sendall(struct.pack('>BBHH',5,1,3,1));t.join(8)
        self.assertFalse(t.is_alive());self.assertEqual(b.releases,1)
        self.assertEqual(b.events,[('pointer',2,1,1),('console-key',30),('pointer',2,1,0)])
        self.assertIn('ValueError',errors)

    def test_pixel_format_rejects_overlap_and_colormap(self):
        with self.assertRaises(ValueError):c.pixel_format(struct.pack('>BBBBHHHBBB3x',32,24,0,1,255,255,255,0,0,0))
        with self.assertRaises(ValueError):c.pixel_format(struct.pack('>BBBBHHHBBB3x',8,8,0,0,7,7,3,0,3,6))
        fmt=c.pixel_format(struct.pack('>BBBBHHHBBB3x',16,16,0,1,31,63,31,11,5,0))
        self.assertEqual(c.pixels(bytes([255,0,0,0,255,0,0,0,255]),fmt),bytes.fromhex('00f8e0071f00'))

    def test_unchanged_input_still_completes_a_pending_frame_request(self):
        client,b,t,challenge,errors=self.start();self.authenticate(client,challenge)
        client.sendall(struct.pack('>BBHHHH',3,0,0,0,3,2));c.receive(client,4+12+24)
        client.sendall(struct.pack('>BBHHHH',3,1,0,0,3,2));self.assertTrue(b.band_read.wait(2))
        client.sendall(struct.pack('>BBHI',4,1,0,ord('a')))
        self.assertEqual(c.receive(client,4),b'\0\0\0\1');c.receive(client,12+24)
        self.assertEqual(b.events,[('console-key',30)])
        client.close();t.join(5);self.assertFalse(t.is_alive())

    def test_bands_reject_stale_missing_malformed_and_conflicting_packets(self):
        def packet(nonce=7,counter=9,row=0,chunk=0,width=201,valid=200,pixel=b'\x01\x02\x03\0'):
            return struct.pack('<8sQQHBBHHH',b'AIUEBND2',nonce,counter,row,chunk,1,width,1,valid)+pixel*200
        class UDP:
            def __init__(self,items):self.items=list(items)
            def recvfrom(self,size):
                if not self.items: raise socket.timeout()
                return self.items.pop(0),('10.77.0.10',7799)
        w,h,rgb=r.receive_band(UDP([packet(nonce=6),packet(counter=8),packet(),packet(chunk=1,valid=1)]),7,9,0,1,.01)
        self.assertEqual((w,h,rgb),(201,1,b'\x03\x02\x01'*201))
        with self.assertRaisesRegex(RuntimeError,'incomplete'):r.receive_band(UDP([packet()]),7,9,0,1,.001)
        with self.assertRaisesRegex(RuntimeError,'malformed'):r.receive_band(UDP([packet(valid=199)]),7,9,0,1,.01)
        with self.assertRaisesRegex(RuntimeError,'conflicting'):r.receive_band(UDP([packet(),packet(pixel=bytes(4))]),7,9,0,1,.01)

    def test_motion_coalesces_without_erasing_edges_or_keys(self):
        begun=threading.Event();allow=threading.Event();calls=[]
        class Recording(c.Bridge):
            def ssh(self,*args,**kwargs):
                calls.append(args)
                if len(calls)==1:begun.set();allow.wait(5)
                return dict(nativeSSH=False)
        b=Recording('itonami-6600h');b.session_nonce='fixture';b.input('pointer',1,1,1);self.assertTrue(begun.wait(3))
        b.input('pointer',2,2,1);b.input('pointer',3,3,1);b.input('console-key',30)
        b.input('pointer',4,4,1);b.input('pointer',5,5,0)
        barrier=threading.Event()
        with b.cv:b.queue.append(('_barrier',(barrier,)));b.cv.notify()
        allow.set();self.assertTrue(barrier.wait(5));b.release()
        with b.cv:b.stopped=True;b.cv.notify()
        b.thread.join(3)
        self.assertEqual(calls,[('pointer','nonce=fixture','1','1','1'),('pointer','nonce=fixture','3','3','1'),('console-key','nonce=fixture','30'),
                                ('pointer','nonce=fixture','4','4','1'),('pointer','nonce=fixture','5','5','0'),('pointer','nonce=fixture','5','5','0')])

    def test_queued_drag_keeps_its_original_press_coordinate(self):
        begun=threading.Event();allow=threading.Event();calls=[]
        class Recording(c.Bridge):
            def ssh(self,*args,**kwargs):
                calls.append(args)
                if len(calls)==1:begun.set();allow.wait(5)
                return dict(nativeSSH=False)
        b=Recording('itonami-6600h');b.session_nonce='fixture';b.input('console-key',30);self.assertTrue(begun.wait(3))
        b.input('pointer',10,10,1);b.input('pointer',20,20,1);b.input('pointer',30,30,1);b.input('pointer',30,30,0)
        barrier=threading.Event()
        with b.cv:b.queue.append(('_barrier',(barrier,)));b.cv.notify()
        allow.set();self.assertTrue(barrier.wait(5))
        with b.cv:b.stopped=True;b.cv.notify()
        b.thread.join(3)
        self.assertEqual(calls,[('console-key','nonce=fixture','30'),('pointer','nonce=fixture','10','10','1'),
                               ('pointer','nonce=fixture','30','30','1'),('pointer','nonce=fixture','30','30','0')])


if __name__=='__main__': unittest.main()
