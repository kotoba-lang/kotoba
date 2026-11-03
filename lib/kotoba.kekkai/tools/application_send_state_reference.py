"""Prescribed public sender states, never a product backend or consent gate."""
import hashlib
import hmac
import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NOW = 1750000000000


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pending():
    return load('send_public_pending', ROOT/'lib/kotoba.kekkai/tools/application_pending_reference.py')


def packed():
    return pending().packed()


def public_channels(font):
    ref = pending()
    ref.ROOT = ROOT
    channels = ref.public_channels(font)
    data = font[393216:]
    take = lambda at, size: data[struct.unpack_from('<I', data, at)[0]:][:size]
    x = load('send_public_x', ROOT/'lib/org.ietf.x25519/tools/reference.py')
    cipher = load('send_public_cipher', ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')
    si, ei = take(44, 64)[:32], take(44, 64)[32:]
    digest = lambda value: hashlib.blake2s(value).digest()

    def hkdf(ck, value):
        temp = hmac.digest(ck, value, 'blake2s')
        one = hmac.digest(temp, b'\1', 'blake2s')
        return one, hmac.digest(temp, one+b'\2', 'blake2s')

    for number, offset in [(1, 40), (2, 176)]:
        sr, er = take(offset, 64)[:32], take(offset, 64)[32:]
        spi, epi, spr, epr = [x.x25519(key, b'\x09'+bytes(31)) for key in [si, ei, sr, er]]
        ck = digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s')
        hh = digest(digest(ck+b'kekkai-node/1 tailnet:default netmap:42')+spr)
        hh = digest(hh+epi)
        ck, key = hkdf(ck, x.x25519(ei, spr))
        hh = digest(hh+cipher.seal(key, bytes(12), hh, spi))
        ck, key = hkdf(ck, x.x25519(si, spr))
        hh = digest(hh+cipher.seal(key, bytes(12), hh, b''))
        hh = digest(hh+epr)
        ck, key = hkdf(ck, x.x25519(er, epi))
        ck, key = hkdf(ck, x.x25519(er, spi))
        hh = digest(hh+cipher.seal(key, bytes(12), hh, b''))
        incoming, outgoing = hkdf(ck, b'')
        assert hh == channels['binding'+str(number)][64:]
        channels['outgoing'+str(number)] = outgoing
    return channels


def goldens(kind, owner, session, io, input_base, sender, channels):
    ref = pending()
    binding1, binding2 = channels['binding1'], channels['binding2']
    # phase, outcome, request sequence (0 means prepared but unissued), ID
    # sequence, original channel, ready counter, next pending sequence, live.
    rows = {
        1: (1, 0, 0, 1, 1, 0, 1, False),
        2: (4, 2, 0, 1, 1, 0, 1, False),
        3: (3, 0, 1, 1, 1, 0, 2, True),
        4: (4, 2, 1, 1, 1, 0, 2, False),
        5: (4, 3, 2, 2, 1, 1, 3, True),
        6: (0, 0, 0, 0, 0, 0, 3, False),
        7: (3, 0, 3, 3, 1, 2, 4, True),
        8: (4, 5, 3, 3, 1, 2, 4, True),
        9: (4, 6, 4, 4, 1, 0, 5, False),
        10: (4, 6, 5, 5, 1, 2051, 6, False),
        11: (4, 2, 0, 6, 1, 0, 7, False),
        12: (3, 0, 7, 7, 1, 2052, 8, True),
        13: (4, 6, 7, 7, 1, 2052, 8, False),
        14: (4, 4, 8, 8, 1, 0, 9, False),
        15: (4, 4, 9, 9, 2, 0, 10, False),
    }
    if kind == 16:
        return dict(sender=bytes(24576), transmit=bytes(1048576), pending=bytes(262144))
    phase, outcome, seq, id_seq, channel, counter, next_seq, live = rows[kind]
    now = NOW if kind < 12 else NOW+29999 if kind == 12 else NOW+30000
    binding = binding1 if channel == 1 else binding2 if channel == 2 else bytes(96)
    ident = ref.issued(binding, owner, id_seq).hex().encode() if id_seq else bytes(64)
    message = ref.message(binding, owner, id_seq) if id_seq else b''
    used = len(message) if seq else 0
    codec = load('send_public_codec', ROOT/'lib/kotoba.kekkai/tools/application_frame_reference.py')
    cipher = load('send_state_public_cipher', ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')
    number = struct.pack('<Q', counter)
    wire = b''
    if seq and kind not in [9, 14]:
        plain = b'\1'+codec.wire(ident.decode(), message, 0, 1)
        wire = b'k\1\x32'+number+cipher.seal(channels['outgoing'+str(channel)], bytes(4)+number, number, plain)
    state = bytearray(24576)
    struct.pack_into('<8I', state, 0, 0x3153544b, 1, phase, outcome, used, 1 if seq else 0, 0, len(wire) if phase == 3 else 0)
    struct.pack_into('<6Q', state, 32, seq, now, session, owner, io, sender)
    state[80:176] = binding
    struct.pack_into('<Q', state, 176, counter)
    state[192:256] = ident
    struct.pack_into('<I', state, 272, used if wire else 0)
    if phase == 3:
        state[20480:20480+len(wire)] = wire
    transmit = message+bytes(1048576-len(message)) if phase in [1, 3] else bytes(1048576)
    page = bytearray(262144)
    pphase, epoch = (0, 2) if kind == 15 else (2, 1)
    pbinding = binding2 if kind >= 14 else binding1
    struct.pack_into('<4I6Q', page, 0, 0x3150504b, 1, int(live), pphase, epoch, now, 30000, session, next_seq, 0)
    if pphase == 2:
        page[64:160] = pbinding
    struct.pack_into('<Q', page, 160, owner)
    if live:
        page[4096:4608] = ref.slot(pbinding, owner, seq)
    return dict(sender=bytes(state), transmit=transmit, pending=bytes(page))
