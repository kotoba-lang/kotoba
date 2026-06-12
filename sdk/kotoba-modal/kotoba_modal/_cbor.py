"""Minimal, dependency-free CBOR (RFC 8949) encoder/decoder.

kotoba_modal owns the call-context wire format on **both** ends — the client
that builds `ctx_b64` and the guest's `handle_invoke` that decodes it. Shipping
our own tiny CBOR (rather than depending on `cbor2`, which is not always
installable) means the round-trip is testable in plain CPython and the same code
runs inside the componentize-py guest.

Output is standard CBOR, so the Rust node (`ciborium`) and `cbor2` can read it.
Supported types: None, bool, int, float (encoded as float64), bytes, str, list,
dict (string keys). That is exactly what the `{v, fn, args, kwargs}` /
`{v, ok, result|error}` envelopes need — not a general-purpose CBOR library.
"""

from __future__ import annotations

import struct
from typing import Any, Tuple


def dumps(obj: Any) -> bytes:
    out = bytearray()
    _encode(obj, out)
    return bytes(out)


def loads(data: bytes) -> Any:
    value, off = _decode(memoryview(data), 0)
    if off != len(data):
        raise ValueError(f"trailing CBOR bytes: consumed {off} of {len(data)}")
    return value


# ── encode ────────────────────────────────────────────────────────────────

def _head(major: int, n: int, out: bytearray) -> None:
    if n < 24:
        out.append((major << 5) | n)
    elif n < 0x100:
        out.append((major << 5) | 24)
        out.append(n)
    elif n < 0x10000:
        out.append((major << 5) | 25)
        out += struct.pack(">H", n)
    elif n < 0x100000000:
        out.append((major << 5) | 26)
        out += struct.pack(">I", n)
    else:
        out.append((major << 5) | 27)
        out += struct.pack(">Q", n)


def _encode(obj: Any, out: bytearray) -> None:
    if obj is None:
        out.append(0xF6)
    elif obj is True:
        out.append(0xF5)
    elif obj is False:
        out.append(0xF4)
    elif isinstance(obj, int):
        if obj >= 0:
            _head(0, obj, out)
        else:
            _head(1, -obj - 1, out)
    elif isinstance(obj, float):
        out.append(0xFB)
        out += struct.pack(">d", obj)
    elif isinstance(obj, (bytes, bytearray)):
        _head(2, len(obj), out)
        out += bytes(obj)
    elif isinstance(obj, str):
        b = obj.encode("utf-8")
        _head(3, len(b), out)
        out += b
    elif isinstance(obj, (list, tuple)):
        _head(4, len(obj), out)
        for item in obj:
            _encode(item, out)
    elif isinstance(obj, dict):
        _head(5, len(obj), out)
        for k, v in obj.items():
            _encode(k, out)
            _encode(v, out)
    else:
        raise TypeError(f"cannot CBOR-encode {type(obj).__name__}")


# ── decode ──────────────────────────────────────────────────────────────────

def _read_len(data: memoryview, off: int, info: int) -> Tuple[int, int]:
    if info < 24:
        return info, off
    if info == 24:
        return data[off], off + 1
    if info == 25:
        return struct.unpack_from(">H", data, off)[0], off + 2
    if info == 26:
        return struct.unpack_from(">I", data, off)[0], off + 4
    if info == 27:
        return struct.unpack_from(">Q", data, off)[0], off + 8
    raise ValueError(f"unsupported CBOR additional-info {info}")


def _decode(data: memoryview, off: int) -> Tuple[Any, int]:
    ib = data[off]
    off += 1
    major = ib >> 5
    info = ib & 0x1F

    if major == 0:  # unsigned int
        return _read_len(data, off, info)
    if major == 1:  # negative int
        n, off = _read_len(data, off, info)
        return -1 - n, off
    if major == 2:  # bytes
        n, off = _read_len(data, off, info)
        return bytes(data[off : off + n]), off + n
    if major == 3:  # text
        n, off = _read_len(data, off, info)
        return bytes(data[off : off + n]).decode("utf-8"), off + n
    if major == 4:  # array
        n, off = _read_len(data, off, info)
        arr = []
        for _ in range(n):
            item, off = _decode(data, off)
            arr.append(item)
        return arr, off
    if major == 5:  # map
        n, off = _read_len(data, off, info)
        d = {}
        for _ in range(n):
            k, off = _decode(data, off)
            v, off = _decode(data, off)
            d[k] = v
        return d, off
    if major == 7:  # simple / float
        if info == 20:
            return False, off
        if info == 21:
            return True, off
        if info == 22 or info == 23:  # null / undefined
            return None, off
        if info == 25:  # float16
            return _f16(struct.unpack_from(">H", data, off)[0]), off + 2
        if info == 26:  # float32
            return struct.unpack_from(">f", data, off)[0], off + 4
        if info == 27:  # float64
            return struct.unpack_from(">d", data, off)[0], off + 8
    raise ValueError(f"unsupported CBOR major/info {major}/{info}")


def _f16(h: int) -> float:
    exp = (h >> 10) & 0x1F
    mant = h & 0x3FF
    sign = -1.0 if (h >> 15) else 1.0
    if exp == 0:
        val = mant / 1024.0 * (2.0 ** -14)
    elif exp == 0x1F:
        return sign * (float("inf") if mant == 0 else float("nan"))
    else:
        val = (1.0 + mant / 1024.0) * (2.0 ** (exp - 15))
    return sign * val
