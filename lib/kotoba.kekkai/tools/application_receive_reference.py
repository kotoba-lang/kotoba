"""Independent public ciphertext/schedule for native receive composition.

This is an isolated test peer, never a product backend, policy evaluator,
entropy source, consent authority or application executor.
"""
import hashlib
import hmac
import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixtures(small=False):
    prior = load('receive_managed_public', ROOT/'lib/kotoba.kekkai/tools/frame_link_reference.py')
    raw, old = prior.fixtures()
    blob = bytearray(raw)
    codec = load('receive_part_public', ROOT/'lib/kotoba.kekkai/tools/application_frame_reference.py')
    x = load('receive_x_public', ROOT/'lib/org.ietf.x25519/tools/reference.py')
    c = load('receive_c_public', ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')

    def d(at): return struct.unpack_from('<I', blob, at)[0]
    def value(at, count): return bytes(blob[d(at):d(at)+count])
    def store(data):
        at = len(blob)
        blob.extend(data)
        return at
    digest = lambda data: hashlib.blake2s(data).digest()

    def hkdf(ck, data):
        temp = hmac.digest(ck, data, 'blake2s')
        first = hmac.digest(temp, b'\1', 'blake2s')
        return first, hmac.digest(temp, first+b'\2', 'blake2s')

    def handshake(si, ei, sr, er, version):
        spi, epi, spr, epr = (x.x25519(k, bytes([9])+bytes(31)) for k in [si, ei, sr, er])
        ck = digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s')
        hh = digest(digest(ck+b'kekkai-node/1 tailnet:default netmap:'+str(version).encode())+spr)
        hh = digest(hh+epi)
        ck, key = hkdf(ck, x.x25519(ei, spr))
        static = c.seal(key, bytes(12), hh, spi)
        hh = digest(hh+static)
        ck, key = hkdf(ck, x.x25519(si, spr))
        body = c.seal(key, bytes(12), hh, b'')
        hh = digest(hh+body)
        first = epi+static+body
        hh = digest(hh+epr)
        ck, key = hkdf(ck, x.x25519(er, epi))
        ck, key = hkdf(ck, x.x25519(er, spi))
        body = c.seal(key, bytes(12), hh, b'')
        return first, epr+body, *hkdf(ck, b''), digest(hh+body)

    alice, ea = value(44, 64)[:32], value(44, 64)[32:]
    bob, eb = value(40, 64)[:32], value(40, 64)[32:]
    one = handshake(alice, ea, bob, eb, 42)
    ea2, eb2 = digest(b'JUN-757 receive Alice channel2'), digest(b'JUN-757 receive Bob channel2')
    two = handshake(alice, ea2, bob, eb2, 42)
    ea44 = digest(b'JUN-757 public NIC Alice fresh 44')
    eb44 = digest(b'JUN-757 public NIC Bob fresh 44')
    three = handshake(alice, ea44, bob, eb44, 44)
    struct.pack_into('<II', blob, 176, store(bob+eb2), store(two[4]))
    struct.pack_into('<II', blob, 184, store(one[4]), store(three[4]))
    old = {row['label']: row for row in old}
    assert old['valid-42-with-invalid-policy-update']['payload'] == b'k\1\x30'+one[0]
    assert old['valid-44-fresh-key']['reply'] == b'k\1\x31'+three[1]
    cases = []
    channel, number, sequence = one, 0, 0

    def add(label, payload, status=-1, event=-1, reply=None, transition=0,
            phase=2, completed=None, pending=0, buffered=0, flags=0, delta=0,
            preserve=False, snapshot=False, control=None):
        cases.append(dict(label=label, payload=payload, status=status, event=event,
            reply=reply, transition=transition, phase=phase, completed=completed,
            pending=pending, buffered=buffered, flags=flags, delta=delta,
            preserve=preserve, snapshot=snapshot, control=control))

    def dg(counter, plain, key):
        header = counter.to_bytes(8, 'little')
        return b'k\1\x32'+header+c.seal(key, bytes(4)+header, header, plain)

    def body(label, data, status, kind=1, reply_kind=None, counter=None, **kwargs):
        nonlocal number, sequence
        n = number if counter is None else counter
        packet = dg(n, bytes([kind])+data, channel[2])
        if counter is None: number += 1
        reply = None
        if reply_kind is not None:
            reply = dg(sequence, bytes([reply_kind])+data, channel[3])
            sequence += 1
        add(label, packet, status, (-1 if status == -2 else (kind*65536+len(data) if 1 <= kind <= 5 else 0)), reply, **kwargs)
        return packet

    def part(label, ident, data, index=0, total=1, status=1, **kwargs):
        document = codec.wire(ident, data, index, total)
        return body(label, document, status, **kwargs)

    add('actual-handshake42', b'k\1\x30'+one[0], 4, 48*65536,
        b'k\1\x31'+one[1], transition=3, snapshot=True)
    add('handshake-replay', b'k\1\x30'+one[0], preserve=True)
    body('typed-pong', b'id', 3, kind=3, control=b'id', snapshot=True, flags=8)
    body('typed-cmm-no-route', b'[]', 3, kind=4, control=b'[]')
    body('typed-ping-and-pong', b'JUN-757', 3, kind=2, reply_kind=3, control=b'JUN-757')
    body('empty-keepalive', b'', 3, kind=5, control=b'')
    body('invalid-inner', b'x', 0, kind=6)
    partial = part('part2-first', 'order', b'}', 2, 3, pending=1, buffered=1)
    part('part0-next', 'order', b'{', 0, 3, pending=1, buffered=2)
    part('replace-duplicate', 'order', b'{ ', 0, 3, pending=1, buffered=3)
    part('restore-duplicate', 'order', b'{', 0, 3, pending=1, buffered=2)
    part('part-count-change', 'order', b'', 1, 4, status=0, pending=1, buffered=2, snapshot=True)
    part('invalid-completed-json', 'order', b'x', 1, 3, status=0, pending=1, buffered=2, snapshot=True)
    part('valid-completion-after-refusal', 'order', b'', 1, 3, status=2, completed=b'{}', snapshot=True)
    busy_number = number
    busy = part('completed-busy-counter-preserved', 'busy', b'[]', status=-2,
        completed=b'{}', preserve=True, snapshot=True)
    # Busy preflight must not consume this exact ciphertext or counter.
    add('same-ciphertext-after-release', busy, 2, 65536+len(codec.wire('busy', b'[]', 0, 1)),
        completed=b'[]', flags=1, snapshot=True)
    assert busy_number == number-1
    document = codec.wire('poison', b'{"peerIndex":64,"service":"arbitrary"}', 0, 1)
    document = document[:-1]+b',"peerIndex":64,"generation":999999,"key":"untrusted"}'
    body('json-peer-fields-do-not-bind-or-execute', document, 2, flags=1,
        completed=b'{"peerIndex":64,"service":"arbitrary"}', snapshot=True)
    malformed = codec.wire('bad', b'f', 0, 1).replace(b'Zg==', b'Zh==')
    body('bad-base64', malformed, 0, flags=1)
    add('exact-authenticated-replay', partial, preserve=True)
    part('old-channel-part0', 'channel', b'{', 0, 2, pending=1, buffered=1)
    # Process this real new handshake through the existing frame API, allowing
    # the bridge to observe phase2 -> phase2 at the same peer/key/epoch/time.
    # Only the final public Noise transcript can identify this channel change.
    channel, number, sequence = two, 0, 0
    add('fresh-same-epoch-unobserved-handshake', b'k\1\x30'+two[0], 4, 48*65536,
        b'k\1\x31'+two[1], transition=5, pending=1, buffered=1, flags=4, snapshot=True)
    part('new-channel-part1-cannot-complete-old', 'channel', b'}', 1, 2,
        pending=1, buffered=1, snapshot=True)
    part('new-channel-part0-completes', 'channel', b'{', 0, 2,
        status=2, completed=b'{}', snapshot=True)
    part('before-roster-revoke', 'epoch', b'{', 0, 2, flags=1, pending=1, buffered=1)
    add('revoked-old-data', dg(number, b'\1revoked', two[2]), transition=1, phase=0, snapshot=True)
    add('revoked-handshake', b'k\1\x30'+two[0], phase=0)
    add('restored44-old-prologue-refused', b'k\1\x30'+two[0], transition=2, phase=1, snapshot=True)
    channel, number, sequence = three, 0, 0
    add('actual-handshake44', b'k\1\x30'+three[0], 4, 48*65536,
        b'k\1\x31'+three[1], snapshot=True)
    part('new-epoch-part1-cannot-complete-old', 'epoch', b'}', 1, 2, pending=1, buffered=1)
    part('new-epoch-part0-completes', 'epoch', b'{', 0, 2, status=2, completed=b'{}', snapshot=True)
    if not small:
        # 2048 real authenticated parts, including 550 empty parts; reverse
        # delivery. The completed JSON is exactly1MiB, never a shortened stream.
        full = b'"'+bytes(97+(i % 26) for i in range(1,1048575))+b'"'
        used = 0
        for position, index in enumerate(range(2047, -1, -1)):
            data = full[index*700:(index+1)*700]
            used += len(data)
            part('full1MiB-part-'+str(index), 'full', data, index, 2048,
                status=2 if index == 0 else 1,
                completed=full if index == 0 else None,
                pending=0 if index == 0 else 1,
                buffered=0 if index == 0 else used,
                flags=1 if position == 0 else 0,
                snapshot=index in [2047,1497,1,0])
        part('full-completion-busy', 'after-full', b'{}', status=-2,
            completed=full, preserve=True, snapshot=True)
        part('release-full-and-receive-next', 'next', b'{}', status=2,
            completed=b'{}', flags=1, snapshot=True)
    # Session expiry must invalidate even a pinned completed application result.
    add('expiry-clears-pinned-completion', dg(number, b'\1expired', three[2]),
        phase=0, delta=180, snapshot=True)
    table_at = len(blob)
    for row in cases:
        blob.extend(struct.pack('<q6IqII', row['status'], row['transition'], row['phase'],
            len(row['completed']) if row['completed'] is not None else 0,
            row['pending'], row['buffered'], row['flags'], row['event'], row['delta'], 0))
    struct.pack_into('<II', blob, 148, len(cases), table_at)
    assert len(blob) <= 131072, len(blob)
    return bytes(blob), cases
