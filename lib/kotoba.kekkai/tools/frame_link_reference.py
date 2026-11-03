"""Public signed fixtures and independent crypto for the managed NIC diagnostic.

No EDN evaluator, runtime, application service or product entropy. The literal
roster and deterministic keys below are public test data, never configuration.
"""
import base64
import hashlib
import hmac
import importlib.util
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
NOW = 1750000000

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def fixtures(fault=None):
    prior = load('frame_managed_vectors', ROOT/'lib/kotoba.kekkai/tools/session_region_reference.py')
    raw, _ = prior.fixtures('policy')
    blob = bytearray(raw)
    def dword(at): return struct.unpack_from('<I', blob, at)[0]
    def value(at, count): return bytes(blob[dword(at):dword(at)+count])
    def add(data):
        at = len(blob)
        blob.extend(data)
        return at
    x = load('frame_public_x', ROOT/'lib/org.ietf.x25519/tools/reference.py')
    c = load('frame_public_c', ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')
    scripts = ROOT/'lib/kotoba.aiueos/os/aiueos/scripts'
    sys.path.insert(0, str(scripts))
    ed = load('frame_public_ed', scripts/'check-native-consent-qemu.py')
    alice, ea = value(44, 64)[:32], value(44, 64)[32:]
    bob, eb = value(40, 64)[:32], value(40, 64)[32:]
    ap, bp = value(36, 32), value(32, 32)
    digest = lambda v: hashlib.blake2s(v).digest()
    def hkdf(ck, data):
        temp = hmac.digest(ck, data, 'blake2s')
        one = hmac.digest(temp, b'\1', 'blake2s')
        return one, hmac.digest(temp, one+b'\2', 'blake2s')
    def handshake(si, ei, sr, er, version):
        spi, epi, spr, epr = (x.x25519(k, bytes([9])+bytes(31)) for k in [si, ei, sr, er])
        ck = digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s')
        hh = digest(digest(ck+b'kekkai-node/1 tailnet:default netmap:'+str(version).encode())+spr)
        hh = digest(hh+epi); ck, key = hkdf(ck, x.x25519(ei, spr))
        static = c.seal(key, bytes(12), hh, spi); hh = digest(hh+static)
        ck, key = hkdf(ck, x.x25519(si, spr)); body = c.seal(key, bytes(12), hh, b'')
        hh = digest(hh+body); first = epi+static+body
        hh = digest(hh+epr); ck, key = hkdf(ck, x.x25519(er, epi))
        ck, key = hkdf(ck, x.x25519(er, spi)); body = c.seal(key, bytes(12), hh, b'')
        return first, epr+body, *hkdf(ck, b'')
    first, response, tx, rx = handshake(alice, ea, bob, eb, 42)
    assert first == value(48, dword(52)) and response == value(56, dword(60))
    new_ea, new_eb = digest(b'JUN-757 public NIC Alice fresh 44'), digest(b'JUN-757 public NIC Bob fresh 44')
    first44, response44, tx44, rx44 = handshake(alice, new_ea, bob, new_eb, 44)
    # Construct literal EDN bytes; only native code interprets/adjudicates them.
    payload = (b'{:netmap/version 44 :netmap/tailnet "default" :netmap/self {:node/id "n-laptop" :node/key "'+bp.hex().encode()+
        b'" :node/overlay-ip "10.0.0.1"} :netmap/peers [{:node/id "n-server" :node/key "'+ap.hex().encode()+b'" :node/overlay-ip "10.0.0.2" :node/status "authorized" :node/expires-at '+
        str(NOW+1000).encode()+b'}] :netmap/edges [{:edge/from "n-laptop" :edge/to "n-server" :edge/capabilities [:overlay :ssh] :edge/ports [22]}] :netmap/relays []}')
    seed = bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb')
    authority = ed.ed_public(seed); hh = hashlib.sha512(seed).digest()
    clamped = bytearray(hh[:32]); clamped[0] &= 248; clamped[31] &= 127; clamped[31] |= 64
    nonce = int.from_bytes(hashlib.sha512(hh[32:]+payload).digest(), 'little') % ed._L
    rr = ed._enc(ed._mul(nonce, ed._B))
    challenge = int.from_bytes(hashlib.sha512(rr+authority+payload).digest(), 'little') % ed._L
    signature = rr+((nonce+challenge*int.from_bytes(clamped, 'little')) % ed._L).to_bytes(32, 'little')
    assert ed.ed_verify(authority, payload, signature)
    fields = [('payload-b64', base64.b64encode(payload).decode()), ('signature-b64', base64.b64encode(signature).decode()),
        ('signer-spki-b64', base64.b64encode(bytes.fromhex('302a300506032b6570032100')+authority).decode()), ('sha256', hashlib.sha256(payload).hexdigest())]
    roster44 = ('{'+', '.join(':netmap/'+k+' "'+v+'"' for k,v in fields)+'}').encode()
    secret_at, roster_at = add(bob+new_eb), add(roster44)
    bad = bytearray(value(20, dword(24))); bad[bad.index(b':netmap/signature-b64 "')+len(b':netmap/signature-b64 "')] ^= 1
    bad_at = add(bytes(bad))
    def outer(kind, body): return bytes([107, 1, kind])+body
    def dg(number, plain, key):
        counter = number.to_bytes(8, 'little')
        return counter+c.seal(key, bytes(4)+counter, counter, plain)
    def flip(data, at):
        out = bytearray(data); out[at] ^= 1
        return bytes(out)
    cases = []
    def case(label, packet, event=-1, reply=None, transition=0, phase=1, output=None):
        cases.append(dict(label=label, payload=packet, event=event, reply=reply, transition=transition, phase=phase, output=output))
    case('short-outer', b'k\1')
    case('bad-magic', bytes([106,1,48])+first)
    case('bad-version', bytes([107,2,48])+first)
    case('unknown-outer', outer(51,first))
    case('wrong-role-response', outer(49,response))
    case('transport-before-handshake', outer(50,dg(0,b'\1early',tx)))
    case('short-handshake', outer(48,first[:95]))
    case('static-tamper', outer(48,flip(first,32)))
    case('payload-tamper', outer(48,flip(first,-1)))
    case('wrong-static', outer(48,handshake(digest(b'public unauthorized NIC peer'),ea,bob,eb,42)[0]))
    case('wrong-netmap-version', outer(48,handshake(alice,ea,bob,eb,41)[0]))
    case('valid-42-with-invalid-policy-update', outer(48,first), 48*65536, outer(49,response), transition=3, phase=2)
    case('repeated-handshake', outer(48,first), phase=2)
    case('short-datagram', outer(50,dg(0,b'',tx)[:23]), phase=2)
    case('bad-tag', outer(50,flip(dg(0,b'',tx),-1)), phase=2)
    case('tampered-counter', outer(50,flip(dg(0,b'',tx),0)), phase=2)
    case('wrong-direction-key', outer(50,dg(0,b'\1wrong',rx)), phase=2)
    case('empty-inner', outer(50,dg(0,b'',tx)), 0, phase=2)
    case('unknown-inner', outer(50,dg(1,b'\0',tx)), 0, phase=2)
    case('pong-event-without-handler', outer(50,dg(2,b'\3id',tx)), 3*65536+2, phase=2, output=b'id')
    case('call-me-maybe-without-route-effect', outer(50,dg(3,b'\4[]',tx)), 4*65536+2, phase=2, output=b'[]')
    case('nonempty-keepalive', outer(50,dg(4,b'\5x',tx)), 0, phase=2)
    case('empty-keepalive', outer(50,dg(5,b'\5',tx)), 5*65536, phase=2, output=b'')
    sequence = 0
    def echo(label, number, body, kind=1, transition=0, epoch=42):
        nonlocal sequence
        itx, irx = (tx,rx) if epoch==42 else (tx44,rx44)
        reply = outer(50,dg(sequence,bytes([3 if kind==2 else kind])+body,irx)); sequence += 1
        case(label,outer(50,dg(number,bytes([kind])+body,itx)),kind*65536+len(body),reply,transition,2)
    echo('data-empty',6,b'')
    case('replay-data',outer(50,dg(6,b'\1',tx)),phase=2)
    for number,size in [(8,1),(7,31),(9,64),(10,257),(11,1024),(12,1444)]:
        echo('data-'+str(size),number,bytes((i*17+size)%256 for i in range(size)))
    echo('ping-pong',13,b'JUN-757',kind=2)
    case('authenticated-unknown-6',outer(50,dg(14,b'\6',tx)),0,phase=2)
    case('wrong-endpoint',outer(50,dg(15,b'\1endpoint',tx)),-2,phase=2)
    echo('data-after-endpoint-refusal',15,bytes(range(16)))
    case('tampered-body',outer(50,flip(dg(16,b'\1'+bytes(range(65)),tx),9)),phase=2)
    echo('data-after-tamper-and-exact-policy-retry',16,bytes(range(65)),transition=4)
    case('revoked-old-data',outer(50,dg(17,b'\1revoked',tx)),transition=1,phase=0)
    case('revoked-handshake',outer(48,first),phase=0)
    case('restored-44-refuses-old-prologue',outer(48,first),transition=2)
    case('valid-44-fresh-key',outer(48,first44),48*65536,outer(49,response44),phase=2)
    case('old-ciphertext-before-new-counter-zero',outer(50,dg(0,b'\1old',tx)),phase=2)
    sequence = 0
    echo('fresh-44-counter-zero',0,b'fresh44',epoch=44)
    case('fresh-44-replay',outer(50,dg(0,b'\1fresh44',tx44)),phase=2)
    echo('fresh-44-ping',1,b'reconnected',kind=2,epoch=44)
    if fault:
        selected = {'valid-42-with-invalid-policy-update', 'pong-event-without-handler',
            'call-me-maybe-without-route-effect', 'nonempty-keepalive', 'empty-keepalive',
            'data-empty', 'data-1', 'revoked-old-data', 'revoked-handshake',
            'restored-44-refuses-old-prologue', 'valid-44-fresh-key',
            'old-ciphertext-before-new-counter-zero', 'fresh-44-counter-zero',
            'fresh-44-replay', 'fresh-44-ping'}
        cases = [row for row in cases if row['label'] in selected]
        assert len(cases) == 15
    table = bytearray()
    for row in cases:
        table.extend(struct.pack('<qII',row['event'],row['transition'],row['phase']))
    table_at = add(table)
    struct.pack_into('<7I',blob,148,len(cases),table_at,secret_at,roster_at,len(roster44),bad_at,len(bad))
    assert len(blob) <= 131072
    return bytes(blob), cases
