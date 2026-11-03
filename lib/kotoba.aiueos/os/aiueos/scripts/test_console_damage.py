#!/usr/bin/env python3
"""Host damage scheduling/attribution controls, not native display consent."""
import importlib.util
from pathlib import Path
import struct
import threading
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,HERE/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result
c=module('damage_console','aiueos-console-macos.py')
m=module('damage_management','aiueos-management.py')
rfb=module('damage_rfb_tests','test_console_macos.py')
NONCE='0123456789abcdef'

def reply(counter=9,rows=None,nonce=NONCE):
    return dict(nativeSSH=False,bootNonce=nonce,replies=[dict(value=counter)],
                postRender=dict(counter=f'{counter:016x}',rows=rows))


class Tests(unittest.TestCase):
    def records(self,items,counter=9):
        with mock.patch.object(m.remote,'records',return_value=iter(items)):
            return m.rendered_rows(None,counter,.01)

    def bridge(self,kind=c.Bridge):
        b=kind('itonami-6600h');b.session_nonce=NONCE;b.geometry=(800,600)
        def stop():
            with b.cv:b.stopped=True;b.cv.notify_all()
            b.thread.join(2)
        self.addCleanup(stop)
        return b

    def test_rows_bind_full_counter_and_ignore_stale_pairs(self):
        self.assertEqual(self.records([(0xc015,8),(0xc016,100<<16),
                                      (0xc015,9),(0xc016,(112<<16)|96)]),[96,112])
        with self.assertRaisesRegex(RuntimeError,'missing'):
            self.records([(0xc015,9+(1<<32)),(0xc016,(112<<16)|96)])

    def test_missing_reordered_and_refused_records_are_not_success(self):
        for items in [[],[(0xc016,(112<<16)|96),(0xc015,9)],
                      [(0xc015,9),(0xc015,8),(0xc016,(112<<16)|96)],[(0xc0ff,9)]]:
            with self.subTest(items=items),self.assertRaises(RuntimeError):self.records(items)
        self.assertIsNone(self.records([(0xc015,9),(0xc016,0)]))

    def test_bad_native_row_intervals_are_refused(self):
        for packed in [(20<<16)|20,(19<<16)|20,(8193<<16)|20,-1,1<<40]:
            with self.subTest(packed=packed),self.assertRaises(ValueError):
                self.records([(0xc015,9),(0xc016,packed)])

    def test_damage_edges_precede_interior_and_never_mark_pixels_valid(self):
        b=self.bridge();b.record_damage(reply(rows=[10,450]))
        self.assertEqual([b.damage_band(0,600) for _ in range(3)],[(0,32),(448,32),(32,32)])
        cache=c.FrameCache(800,600)
        self.assertFalse(cache.known(0,0,800,600))

    def test_bad_session_counter_shape_and_geometry_do_not_queue(self):
        b=self.bridge()
        cases=[reply(rows=[96,112],nonce='fedcba9876543210'),reply(rows=[True,112]),
               reply(rows=[96,601]),reply(rows=[112,96]),reply(rows='96,112')]
        changed=reply(rows=[96,112]);changed['postRender']['counter']='0000000000000008';cases.append(changed)
        changed=reply(rows=[96,112]);changed['replies']=[None];cases.append(changed)
        for value in cases:
            with self.subTest(value=value),self.assertRaises(ValueError):b.record_damage(value)
            self.assertFalse(b.dirty_rows)
        b.record_damage(dict(nativeSSH=False));self.assertIsNone(b.damage_band(0,600))

    def test_coalescing_is_bounded_and_a_newer_hint_survives_prior_capture(self):
        b=self.bridge();b.geometry=(3200,8192)
        for counter in range(9,20):b.record_damage(reply(counter,[0,8192]))
        self.assertEqual(len(b.dirty_rows),256)
        self.assertEqual(set(b.dirty_rows.values()),{19})
        self.assertEqual(b.damage_band(8190,2),(8190,2))
        b.record_damage(reply(20,[8190,8192]))
        self.assertEqual(b.damage_band(8190,2),(8190,2))

    def test_input_worker_publishes_rows_after_the_native_response(self):
        class Recording(c.Bridge):
            def ssh(self,*args,**kwargs):return reply(rows=[96,112])
        b=self.bridge(Recording);b.input('console-key',30)
        barrier=threading.Event()
        with b.cv:b.queue.append(('_barrier',(barrier,)));b.cv.notify_all()
        self.assertTrue(barrier.wait(2));self.assertEqual(b.damage_band(0,600),(96,32))

    def test_damage_protocol_profile_is_an_explicit_boolean(self):
        with self.assertRaisesRegex(ValueError,'boolean'):
            m.operation(dict(frameDamageHints='true'),None,['status'])

    def test_three_priority_bands_yield_to_background_scan(self):
        class Hints(rfb.Backend):
            def capture_band(self,row,count):return 4,160,bytes([1,2,3])*4*count
            def damage_band(self,first,count):return 128,32
        # Reuse the real RFB authentication harness, with a finite backend.
        fixture=rfb.Tests();self.addCleanup(fixture.doCleanups)
        client,b,t,challenge,errors=fixture.start(backend=Hints())
        fixture.authenticate(client,challenge,(4,160))
        client.sendall(struct.pack('>BBHHHH',3,0,0,0,4,160))
        self.assertEqual(c.receive(client,4),struct.pack('>BBH',0,0,5))
        for _ in range(5):c.receive(client,12+4*32*4)
        actual=[]
        for _ in range(4):
            b.input_serial+=1
            client.sendall(struct.pack('>BBHHHH',3,1,0,0,4,160))
            self.assertEqual(c.receive(client,4),struct.pack('>BBH',0,0,1))
            x,y,w,h,encoding=struct.unpack('>HHHHi',c.receive(client,12));actual.append((y,h))
            c.receive(client,w*h*4)
        self.assertEqual(actual,[(128,32),(128,32),(128,32),(0,32)])
        client.close();t.join(3)

    def test_disconnect_cancels_capture_after_waiting_for_native_damage(self):
        class Waiting(rfb.Backend):
            def __init__(self):
                super().__init__();self.entered=threading.Event();self.allow=threading.Event();self.closed=threading.Event()
            def damage_band(self,first,count):
                self.entered.set();self.allow.wait(4);return None
            def release(self):super().release();self.closed.set()
        backend=Waiting();self.addCleanup(backend.allow.set)
        fixture=rfb.Tests();self.addCleanup(fixture.doCleanups)
        client,b,t,challenge,errors=fixture.start(backend=backend);fixture.authenticate(client,challenge)
        client.sendall(struct.pack('>BBHHHH',3,0,0,0,3,2));c.receive(client,4+12+24)
        before=b.captures
        client.sendall(struct.pack('>BBHHHH',3,1,0,0,3,2));self.assertTrue(b.entered.wait(2))
        client.close();self.assertTrue(b.closed.wait(2));b.allow.set();t.join(3)
        self.assertFalse(t.is_alive());self.assertEqual(b.captures,before)


if __name__=='__main__':unittest.main()
