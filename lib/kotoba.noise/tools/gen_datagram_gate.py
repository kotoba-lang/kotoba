#!/usr/bin/env python3
"""Public, independent IK/BLAKE2s datagram fixtures. Never operational keys.

Python/hashlib plus sibling RFC X25519/ChaCha reference implementations are
development oracles only. First cross-check this small reference's handshake
against Cacophony, then emit one counter/AD-bound datagram known answer.
"""
import hashlib
import hmac
import importlib.util
from pathlib import Path
import re
import sys

LIB = Path(__file__).resolve().parents[2]


def load(repo, name):
    spec = importlib.util.spec_from_file_location(name, LIB / repo / 'tools/reference.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


X = load('org.ietf.x25519', 'x_reference')
C = load('org.ietf.chacha20Poly1305', 'c_reference')
text = (LIB / 'kotoba.noise/test/noise/cacophony_vectors.edn').read_text()
at = text.index('"Noise_IK_25519_ChaChaPoly_BLAKE2s"')
start = text.rfind('{:protocol-name', 0, at)
end = text.find('{:protocol-name', at)
block = text[start:end]


def field(name):
    return bytes.fromhex(re.search(rf':{name} "([0-9a-f]*)"', block)[1])


messages = [(bytes.fromhex(p), bytes.fromhex(c)) for p, c in re.findall(
    r'\{:payload "([0-9a-f]*)"\s*:ciphertext "([0-9a-f]*)"\}', block)]
digest = lambda data: hashlib.blake2s(data).digest()
mac = lambda key, data: hmac.digest(key, data, 'blake2s')


def hkdf(ck, material):
    temp = mac(ck, material)
    one = mac(temp, b'\x01')
    return one, mac(temp, one + b'\x02')


basepoint = bytes([9]) + bytes(31)
si, ei = field('init-static'), field('init-ephemeral')
sr, er = field('resp-static'), field('resp-ephemeral')
sp, ep = X.x25519(si, basepoint), X.x25519(ei, basepoint)
rp, reph = X.x25519(sr, basepoint), X.x25519(er, basepoint)
ck = digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s')
hh = digest(digest(ck + field('init-prologue')) + rp)
hh = digest(hh + ep)
ck, key = hkdf(ck, X.x25519(ei, rp))
enc_static = C.seal(key, bytes(12), hh, sp)
hh = digest(hh + enc_static)
ck, key = hkdf(ck, X.x25519(si, rp))
enc_payload = C.seal(key, bytes(12), hh, messages[0][0])
assert ep + enc_static + enc_payload == messages[0][1]
hh = digest(hh + enc_payload)
hh = digest(hh + reph)
ck, key = hkdf(ck, X.x25519(ei, reph))
ck, key = hkdf(ck, X.x25519(si, reph))
enc_payload = C.seal(key, bytes(12), hh, messages[1][0])
assert reph + enc_payload == messages[1][1]
hh = digest(hh + enc_payload)
assert hh == field('handshake-hash')
send, recv = hkdf(ck, b'')
header = bytes(8)
wire = header + C.seal(send, bytes(4) + header, header, bytes([1, 104, 105]))


def lit(data):
    parts = ['(vector-i64 ' + ' '.join(map(str, data[i:i+64])) + ')' for i in range(0, len(data), 64)]
    if not parts:
        return '(vector-i64)'
    result = parts[0]
    for part in parts[1:]:
        result = f'(cat {result} {part})'
    return result


template = (Path(__file__).with_name('datagram_gate_template.kotoba')).read_text()
values = dict(SI=si, EI=ei, SR=sr, ER=er, SP=sp, RP=rp,
              PROLOGUE=field('init-prologue'), P0=messages[0][0], P1=messages[1][0], WIRE=wire)
for name, value in values.items():
    template = template.replace('@' + name + '@', lit(value))
assert '@' not in template
Path(sys.argv[1]).write_text(template)
print('Cacophony IK/BLAKE2s handshake reference matched; public datagram fixture emitted')
