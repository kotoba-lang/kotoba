"""Independent public IK fixtures; never executes or emits Kotoba source.

Hashlib/HMAC plus the existing independent RFC7748/RFC8439 references.
The complete first handshake is checked against the vendored Cacophony data.
Only public test bytes are returned; this is not an application runtime.
"""
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import re
import struct

OWNER = Path(__file__).resolve().parents[1]
LIB = OWNER.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_fixture(text):
    # A strict reader for this data's maps/vectors/keywords/strings. No eval,
    # numbers, tags or other EDN forms; duplicate keys and trailing data refuse.
    tokens = []
    for token in re.findall(r';[^\n]*|"(?:[^"\\]|\\.)*"|:[\w-]+|[\[\]{}]|\s+|.', text):
        if token.isspace() or token.startswith(';'):
            continue
        if token[0] not in ':"[{}]':
            raise ValueError('unsupported public fixture token')
        tokens.append(token)
    at = 0

    def read(depth=0):
        nonlocal at
        if depth > 32 or at >= len(tokens):
            raise ValueError('fixture nesting/EOF')
        token = tokens[at]
        at += 1
        if token.startswith('"'):
            return json.loads(token)
        if token == '[':
            value = []
            while at < len(tokens) and tokens[at] != ']':
                value.append(read(depth + 1))
            if at == len(tokens):
                raise ValueError('missing vector end')
            at += 1
            return value
        if token == '{':
            value = {}
            while at < len(tokens) and tokens[at] != '}':
                key = tokens[at]
                at += 1
                if not key.startswith(':') or key[1:] in value:
                    raise ValueError('invalid/duplicate fixture key')
                value[key[1:]] = read(depth + 1)
            if at == len(tokens):
                raise ValueError('missing map end')
            at += 1
            return value
        raise ValueError('unexpected fixture form')

    result = read()
    if at != len(tokens):
        raise ValueError('trailing fixture data')
    return result


def fixtures():
    x = load('ik_independent_x', LIB / 'org.ietf.x25519/tools/reference.py')
    c = load('ik_independent_c', LIB / 'org.ietf.chacha20Poly1305/tools/reference.py')
    corpus = read_fixture((OWNER / 'test/noise/cacophony_vectors.edn').read_text())
    if len(corpus) != 6 or len({v['protocol-name'] for v in corpus}) != 6:
        raise ValueError('Cacophony profile inventory differs')
    known, = [v for v in corpus if v['protocol-name'] == 'Noise_IK_25519_ChaChaPoly_BLAKE2s']
    digest = lambda data: hashlib.blake2s(data).digest()
    mac = lambda key, data: hmac.digest(key, data, 'blake2s')

    def hkdf(ck, material):
        temp = mac(ck, material)
        one = mac(temp, b'\1')
        return one, mac(temp, one + b'\2')

    sizes = [(0, 0, 0), (1, 1, 1), (15, 17, 63), (16, 16, 64),
             (17, 15, 65), (63, 65, 257), (64, 64, 4096), (65, 63, 8),
             (257, 257, 12), (1024, 1024, 1), (4096, 4096, 65), (65439, 65487, 65536)]
    rows, expected, descriptions = [], [], []
    for index in range(13):
        if index == 0:
            si, ei, sr, er = (bytes.fromhex(known[k]) for k in ('init-static', 'init-ephemeral', 'resp-static', 'resp-ephemeral'))
            prologue = bytes.fromhex(known['init-prologue'])
            messages = [bytes.fromhex(m['payload']) for m in known['messages'][:2]]
        else:
            si, ei, sr, er = (digest(('IK region public fixture %d:%s' % (index, label)).encode()) for label in ('si', 'ei', 'sr', 'er'))
            n0, n1, plen = sizes[index - 1]
            prologue = bytes((i * 7 + index) % 256 for i in range(plen))
            messages = [bytes((i * 17 + index * 13 + 3 + side * 5) % 256 for i in range(n)) for side, n in enumerate((n0, n1))]
        spi, epi, spr, epr = (x.x25519(key, bytes([9]) + bytes(31)) for key in (si, ei, sr, er))
        ck = digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s')
        hh = digest(digest(ck + prologue) + spr)
        hh = digest(hh + epi)
        es, ss, ee, se = x.x25519(ei, spr), x.x25519(si, spr), x.x25519(er, epi), x.x25519(er, spi)
        if (es != x.x25519(sr, epi) or ss != x.x25519(sr, spi)
                or ee != x.x25519(ei, epr) or se != x.x25519(si, epr)):
            raise ValueError('independent DH symmetry differs')
        ck, key = hkdf(ck, es)
        static = c.seal(key, bytes(12), hh, spi)
        hh = digest(hh + static)
        ck, key = hkdf(ck, ss)
        token0 = hh
        ct0 = c.seal(key, bytes(12), hh, messages[0])
        hh = digest(hh + ct0)
        wire0 = epi + static + ct0
        hh = digest(hh + epr)
        ck, key = hkdf(ck, ee)
        ck, key = hkdf(ck, se)
        token1 = hh
        ct1 = c.seal(key, bytes(12), hh, messages[1])
        hh = digest(hh + ct1)
        wire1 = epr + ct1
        tx, rx = hkdf(ck, b'')
        if index == 0:
            if (wire0.hex() != known['messages'][0]['ciphertext'] or wire1.hex() != known['messages'][1]['ciphertext']
                    or hh.hex() != known['handshake-hash'] or spr.hex() != known['init-remote-static']):
                raise ValueError('independent IK differs from Cacophony')
            # Also verify all published post-handshake cipher vectors.
            for number, m in enumerate(known['messages'][2:]):
                key = tx if number % 2 == 0 else rx
                nonce = bytes(4) + (number // 2).to_bytes(8, 'little')
                if c.seal(key, nonce, b'', bytes.fromhex(m['payload'])).hex() != m['ciphertext']:
                    raise ValueError('independent split differs from Cacophony')
        row = bytearray(512)
        row[:416] = si + ei + sr + er + spr + spi + hh + tx + rx + digest(wire0) + digest(wire1) + token0 + token1
        struct.pack_into('<6I', row, 416, len(messages[0]), len(messages[1]), len(prologue), index, int(index % 2 == 0), int(index not in (1, 2)))
        if index == 0:
            row[448:448 + len(messages[0])] = messages[0]
            row[480:480 + len(messages[1])] = messages[1]
        rows.append(row)
        prepared = index % 2 == 0
        expected.append(digest(wire0) + digest(wire1) + hh + tx + rx + (token0 + token1 if prepared else bytes(64)))
        descriptions.append(dict(index=index,firstPayloadBytes=len(messages[0]),secondPayloadBytes=len(messages[1]),
                                 prologueBytes=len(prologue),prepared=prepared,peerBound=index not in (1,2),
                                 firstWireBytes=len(wire0),secondWireBytes=len(wire1)))
    header = bytearray(64)
    header[:8] = b'IKREGN01'
    struct.pack_into('<I', header, 8, len(rows))
    transports = []
    for index, message in enumerate(known['messages'][2:]):
        plain, cipher = bytes.fromhex(message['payload']), bytes.fromhex(message['ciphertext'])
        if len(plain) > 32 or len(cipher) > 48:
            raise ValueError('published transport fixture exceeds data record')
        record = bytearray(128)
        struct.pack_into('<4I', record, 0, len(plain), len(cipher), index // 2, index % 2)
        record[16:16 + len(plain)] = plain
        record[48:48 + len(cipher)] = cipher
        record[96:128] = digest(cipher)
        transports.append(record)
        expected.append(digest(cipher))
    if len(transports) != 4:
        raise ValueError('Cacophony transport count differs')
    return bytes(header) + b''.join(rows) + b''.join(transports), b''.join(expected), descriptions
