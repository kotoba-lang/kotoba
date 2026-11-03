#!/usr/bin/env python3
"""Finite host console protocol controls; not native SSH qualification."""
import importlib.util
import errno
import io
import json
from pathlib import Path
import socket
import struct
import threading
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('console_channel', HERE/'aiueos-console-channel.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
NONCE = 'nonce=0123456789abcdef'


def frame(identity=1, operation='status', args=None):
    payload = json.dumps(dict(id=identity, operation=operation, args=args or [])).encode()
    return struct.pack('>I', len(payload))+payload


class Process:
    """Full-duplex local stream with the same unbuffered pipe interface."""
    def __init__(self, run):
        client, server = socket.socketpair()
        self.socket = client
        self.stdin = client.makefile('wb', buffering=0)
        self.stdout = client.makefile('rb', buffering=0)
        self.done = threading.Event()
        self.errors = []
        def target():
            try:
                with server, server.makefile('rb', buffering=0) as reader, server.makefile('wb', buffering=0) as writer:
                    run(reader, writer)
            except (OSError, ValueError) as error:
                self.errors.append(type(error).__name__)
            finally:
                self.done.set()
        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()

    def poll(self):
        return 0 if self.done.is_set() else None

    def terminate(self):
        try: self.socket.shutdown(socket.SHUT_RDWR)
        except OSError as error:
            if error.errno != errno.ENOTCONN: raise

    kill = terminate

    def wait(self, timeout):
        if not self.done.wait(timeout):
            raise RuntimeError('fixture server did not exit')
        self.socket.close()
        self.thread.join(timeout)
        return 0


class Tests(unittest.TestCase):
    def server(self, raw, execute):
        writer = io.BytesIO()
        c.serve(io.BytesIO(raw), writer, execute)
        return writer.getvalue()[len(c.MAGIC):]

    def test_multiple_requests_preserve_identity_and_binary_payload(self):
        calls = []
        binary = bytes(range(256))*300
        def execute(words):
            calls.append(words)
            return (0, b'{"nativeSSH":false}') if words == ['status'] else (1, binary)
        result = self.server(frame()+frame(3, 'screenshot-band', [NONCE, '0', '32']), execute)
        head = c.HEADER.unpack_from(result)
        self.assertEqual(head, (1, 0, 19))
        offset = c.HEADER.size+head[2]
        self.assertEqual(c.HEADER.unpack_from(result, offset), (3, 1, len(binary)))
        self.assertEqual(result[offset+c.HEADER.size:], binary)
        self.assertEqual(calls, [['status'], ['screenshot-band', NONCE, '0', '32']])

    def test_refused_operations_do_not_dispatch_or_expand_authority(self):
        cases = [('reboot', []), ('type', ['yes']), ('usb-select', ['0']),
                 ('console-key', ['30']), ('pointer', ['1', '2', '0']),
                 ('screenshot-band', ['0', '32']), ('status', [NONCE]),
                 ('pointer', ['nonce=0000000000000000', '1', '2', '0']),
                 ('pointer', ['nonce=0123456789ABCDEF', '1', '2', '0'])]
        for operation, args in cases:
            with self.subTest(operation=operation, args=args):
                execute = mock.Mock()
                result = self.server(frame(1, operation, args), execute)
                self.assertEqual(c.HEADER.unpack_from(result)[:2], (1, 2))
                execute.assert_not_called()

    def test_bad_identity_shape_truncation_and_size_fail_closed(self):
        requests = [frame()+frame(), frame(0), frame(True), frame(1 << 63),
                    struct.pack('>I', 0), struct.pack('>I', c.MAX_REQUEST+1), b'\0',
                    frame()[:-1]]
        for payload in [[], {'id':1, 'operation':'status', 'args':[], 'extra':0},
                        {'id':1, 'operation':'status', 'args':[7]}]:
            raw = json.dumps(payload).encode()
            requests.append(struct.pack('>I',len(raw))+raw)
        for raw in requests:
            with self.subTest(raw=raw):
                execute = mock.Mock(return_value=(0, b'{}'))
                with self.assertRaises(ValueError): self.server(raw, execute)
                self.assertLessEqual(execute.call_count, 1)

    def test_private_execution_failure_is_generic_and_next_request_works(self):
        execute = mock.Mock(side_effect=[RuntimeError('private fixture detail'), (0, b'{}')])
        result = self.server(frame()+frame(2), execute)
        identity, kind, size = c.HEADER.unpack_from(result)
        self.assertEqual((identity, kind), (1, 2))
        self.assertNotIn(b'private', result)
        self.assertEqual(c.HEADER.unpack_from(result, c.HEADER.size+size), (2, 0, 2))

    def test_oversized_backend_response_is_never_written(self):
        with self.assertRaisesRegex(ValueError, 'response shape'):
            self.server(frame(), lambda words:(1, bytes(c.MAX_RESPONSE+1)))

    def connect(self, run):
        process = Process(run)
        with mock.patch.object(c.subprocess, 'Popen', return_value=process) as popen:
            channel = c.Channel('itonami-6600h')
        self.assertEqual(popen.call_args.args[0][-1], 'console-session')
        self.addCleanup(process.wait, 3)
        self.addCleanup(channel.close)
        return channel, process

    def test_live_stream_round_trip_and_refusal_without_replay(self):
        calls = []
        def execute(words):
            calls.append(words)
            return 0, b'{"nativeSSH":false}'
        channel, process = self.connect(lambda r,w:c.serve(r,w,execute))
        self.assertEqual(channel.request('status', []), (0, b'{"nativeSSH":false}'))
        with self.assertRaisesRegex(RuntimeError, 'refused'):
            channel.request('reboot', [])
        self.assertEqual(channel.request('status', [])[0], 0)
        self.assertEqual(calls, [['status'], ['status']])
        channel.close()
        with self.assertRaisesRegex(RuntimeError, 'reconnect'):
            channel.request('status', [])

    def test_wrong_identity_or_truncated_reply_closes_without_retry(self):
        for response in [c.HEADER.pack(2,0,2)+b'{}', c.HEADER.pack(1,0,4)+b'{}',
                         c.HEADER.pack(1,3,0), c.HEADER.pack(1,0,c.MAX_RESPONSE+1)]:
            calls = []
            def run(reader, writer):
                writer.write(c.MAGIC)
                size = struct.unpack('>I', c.read_exact(reader,4))[0]
                calls.append(c.read_exact(reader,size))
                writer.write(response)
            channel, process = self.connect(run)
            with self.assertRaises(RuntimeError): channel.request('status', [])
            self.assertTrue(channel.closed)
            self.assertEqual(len(calls), 1)

    def test_ambiguous_timeout_never_replays_an_executed_input(self):
        dispatched = threading.Event()
        calls = []
        def execute(words):
            calls.append(words)
            dispatched.set()
            return 0, b'{}'
        channel, process = self.connect(lambda r,w:c.serve(r,w,execute))
        def expired(*args):
            self.assertTrue(dispatched.wait(2))
            raise TimeoutError('fixture deadline')
        channel.read = expired
        with self.assertRaises(TimeoutError):
            channel.request('console-key', [NONCE, '30'])
        self.assertTrue(channel.closed)
        with self.assertRaisesRegex(RuntimeError, 'reconnect'):
            channel.request('console-key', [NONCE, '30'])
        self.assertEqual(calls, [['console-key', NONCE, '30']])


if __name__ == '__main__': unittest.main()
