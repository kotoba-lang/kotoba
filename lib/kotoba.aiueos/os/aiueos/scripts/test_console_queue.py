#!/usr/bin/env python3
"""Real bridge scheduling under sustained input and disconnect races."""
import importlib.util
from pathlib import Path
import struct
import threading
import unittest

spec=importlib.util.spec_from_file_location('queue_console',Path(__file__).with_name('aiueos-console-macos.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
NONCE='0123456789abcdef'


class Tests(unittest.TestCase):
    def bridge(self):
        entered=threading.Event();allow=threading.Event();calls=[]
        class Controlled(c.Bridge):
            feed=False;fail_read=False
            def ssh(self,*args,**kwargs):
                calls.append(args)
                if len(calls)==1:
                    entered.set()
                    if not allow.wait(4):raise RuntimeError('fixture input remained blocked')
                if args[0]=='screenshot-band':
                    if self.fail_read:raise RuntimeError('fixture ambiguous read')
                    first,count=map(int,args[2:])
                    return struct.pack('<8sQHHHH',b'IRGBBND1',int(NONCE,16),first,count,4,65)+bytes([1,2,3])*4*count
                if self.feed and args[0]=='pointer':self.input('pointer',2,2,1)
                return dict(nativeSSH=False)
        b=Controlled('itonami-6600h');b.session_nonce=NONCE;b.geometry=(4,65)
        def cleanup():
            b.feed=False;allow.set()
            with b.cv:b.stopped=True;b.cv.notify_all()
            b.thread.join(3)
            self.assertFalse(b.thread.is_alive())
        self.addCleanup(cleanup)
        return b,entered,allow,calls

    def read(self,b,kind='capture'):
        done=threading.Event();result=[]
        def run():
            try:result.append(('ok',(b.capture_band if kind=='capture' else b.damage_band)(0,32)))
            except RuntimeError as error:result.append(('error',str(error)))
            finally:done.set()
        thread=threading.Thread(target=run);thread.start()
        self.addCleanup(lambda:thread.join(6))
        return thread,done,result

    def queued_read(self,b):
        with b.cv:
            self.assertTrue(b.cv.wait_for(lambda:any(k in ('_capture','_damage') for k,_ in b.queue),2))

    def test_continuing_motion_cannot_starve_capture(self):
        b,entered,allow,calls=self.bridge();b.feed=True
        b.input('pointer',1,1,1);self.assertTrue(entered.wait(2))
        t,done,result=self.read(b);self.queued_read(b);allow.set()
        self.assertTrue(done.wait(2),'capture must finish while motion continues')
        b.feed=False
        self.assertEqual(result,[('ok',(4,65,bytes([1,2,3])*4*32))])
        self.assertEqual([x[0] for x in calls[:2]],['pointer','screenshot-band'])

    def test_queued_capture_keeps_earlier_edges_keys_and_later_release_ordered(self):
        b,entered,allow,calls=self.bridge()
        b.input('pointer',1,1,1);self.assertTrue(entered.wait(2))
        b.input('pointer',2,2,1);b.input('pointer',3,3,1);b.input('console-key',30)
        t,done,result=self.read(b);self.queued_read(b)
        b.input('pointer',3,3,0)
        barrier=threading.Event()
        with b.cv:b.queue.append(('_barrier',(barrier,)));b.cv.notify_all()
        allow.set();self.assertTrue(done.wait(2));self.assertTrue(barrier.wait(2))
        self.assertEqual([(x[0],x[2:]) for x in calls],
                         [('pointer',('1','1','1')),('pointer',('3','3','1')),
                          ('console-key',('30',)),('screenshot-band',('0','32')),
                          ('pointer',('3','3','0'))])

    def test_damage_query_does_not_wait_for_future_motion(self):
        b,entered,allow,calls=self.bridge();b.feed=True
        with b.cv:b.dirty_rows[1]=9
        b.input('pointer',1,1,1);self.assertTrue(entered.wait(2))
        t,done,result=self.read(b,'damage');self.queued_read(b);allow.set()
        self.assertTrue(done.wait(2));b.feed=False
        self.assertEqual(result,[('ok',None)])
        # The first request covered rows0..31; the retained row32 is separate.
        self.assertEqual(b.damage_band(32,32),(32,32))

    def test_disconnect_cancels_unsent_reads_and_drains_final_release(self):
        for kind in ('capture','damage'):
            with self.subTest(kind=kind):
                b,entered,allow,calls=self.bridge()
                b.input('pointer',1,1,1);self.assertTrue(entered.wait(2))
                t,done,result=self.read(b,kind);self.queued_read(b)
                released=threading.Event()
                def close():
                    try:b.release()
                    finally:released.set()
                closer=threading.Thread(target=close);closer.start()
                self.assertTrue(done.wait(2));self.assertEqual(result[0][0],'error')
                self.assertIn('closed before read',result[0][1])
                allow.set();self.assertTrue(released.wait(2));closer.join(2)
                self.assertEqual([(x[0],x[-1]) for x in calls],[('pointer','1'),('pointer','0')])
                self.assertIsNone(b.session_nonce)
                with self.assertRaisesRegex(RuntimeError,'no authenticated'):b.capture_band(0,1)

    def test_read_failure_is_returned_once_without_replay(self):
        b,entered,allow,calls=self.bridge();b.fail_read=True;allow.set()
        with self.assertRaisesRegex(RuntimeError,'ambiguous read'):b.capture_band(0,1)
        self.assertEqual(len(calls),1)
        b.release();self.assertEqual([x[0] for x in calls],['screenshot-band','pointer'])

    def test_read_cannot_expand_a_full_work_queue(self):
        b,entered,allow,calls=self.bridge()
        b.input('pointer',1,1,1);self.assertTrue(entered.wait(2))
        for _ in range(256):b.input('console-key',30)
        with self.assertRaisesRegex(RuntimeError,'queue limit'):b.capture_band(0,1)
        with b.cv:self.assertEqual(len(b.queue),256);b.queue.clear()
        allow.set()


if __name__=='__main__':unittest.main()
