"""Independent public datagram bytes, using the checked Cacophony IK split.

No language source, executables, application secrets or network operations.
"""
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def fixtures():
    blob, ik_expected, sessions = load('datagram_public_ik', HERE / 'ik_region_reference.py').fixtures()
    c = load('datagram_independent_chacha', HERE.parents[1] / 'org.ietf.chacha20Poly1305/tools/reference.py')
    row = blob[64:576]
    keys = [row[224:256], row[256:288]]
    digest = lambda value: hashlib.blake2s(value).digest()
    def wire(key, number, plain):
        header = number.to_bytes(8, 'little')
        return header + c.seal(key, bytes(4) + header, header, plain)
    expected = [ik_expected[i*32:(i+1)*32] for i in range(5)]
    sizes = [0,1,15,16,17,63,64,65,257,1024,4096,65511]
    for count in sizes:
        for side in range(2):
            plain = bytes((i*17 + side*13 + 3) % 256 for i in range(count))
            expected.append(digest(wire(keys[side], 0, plain)))
    expected.append(digest(b''.join(wire(keys[0], n, b'') for n in range(2048))))
    counters = [0,1,2047,2048,4095,65535,281474976710655,281474976710656,9007199254740989]
    expected.extend(digest(wire(keys[0], n, bytes([42]))) for n in counters)
    assert len(expected) == 39 and all(len(v) == 32 for v in expected)
    forbidden = [9007199254740990,9007199254740991,9007199254740992,9223372036854775807,9223372036854775808,18446744073709551615]
    blob += b''.join(wire(keys[0], n, bytes([42])).ljust(32, b'\0') for n in forbidden)
    return blob, b''.join(expected), dict(handshake=dict(vector=sessions[0], initiatorBound=True, responderBound=False, firstWritePrepared=True, firstReadTokenOnly=True, secondMessageAutomatic=True), payloadSizes=sizes, directions=2,
        replayStreamPackets=2048, syntheticCounters=counters, authenticForbiddenCounters=forbidden, recordCount=39)
