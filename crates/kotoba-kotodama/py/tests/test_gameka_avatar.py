"""
Offline unit tests for gameka.avatar.render — pure-stdlib procedural
identicon used by publishGame.bpmn (ADR 2604250900 P10).

Coverage:
  - PNG bytes start with the 8-byte PNG magic
  - rendering is deterministic across runs (same slug → same bytes)
  - distinct slugs → distinct bytes
  - biome palette switches change the bytes
  - data URI helper round-trips back to the raw PNG
  - task wrapper rejects empty slug + caps oversize at 900 KB
"""

from __future__ import annotations

import base64
import importlib.util as _ilu
import sys
from pathlib import Path as _P

ROOT = _P(__file__).resolve().parents[1] / "src" / "kotodama"


def _load(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = _ilu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


av = _load("_gameka_avatar", "handlers/gameka_avatar.py")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ─── PNG container ──────────────────────────────────────────────────────


def test_png_starts_with_magic():
    png = av.render_avatar_png("grid-merge-quarry", "quarry", 256)
    assert png.startswith(PNG_MAGIC)


def test_png_has_iend_chunk():
    png = av.render_avatar_png("grid-merge-quarry", "quarry", 256)
    # PNG ends with the IEND chunk: 0x00 0x00 0x00 0x00 + b"IEND" + crc(4).
    assert png[-12:].endswith(b"IEND" + b"\xae\x42\x60\x82")


# ─── Determinism ────────────────────────────────────────────────────────


def test_render_is_deterministic_across_runs():
    a = av.render_avatar_png("drop-merge-tundra", "tundra", 128)
    b = av.render_avatar_png("drop-merge-tundra", "tundra", 128)
    assert a == b


def test_distinct_slugs_produce_distinct_bytes():
    a = av.render_avatar_png("grid-merge-quarry",  "quarry", 128)
    b = av.render_avatar_png("drop-merge-tundra",  "tundra", 128)
    c = av.render_avatar_png("field-merge-plains", "plains", 128)
    assert len({a, b, c}) == 3


def test_biome_changes_bytes_for_same_slug():
    a = av.render_avatar_png("same-slug", "quarry", 128)
    b = av.render_avatar_png("same-slug", "tundra", 128)
    assert a != b


def test_unknown_biome_falls_back_to_default():
    # Should not raise; should produce a stable byte string.
    a = av.render_avatar_png("anything", "neon-cyberpunk", 128)
    b = av.render_avatar_png("anything", "default",        128)
    assert a == b


# ─── Size policing ──────────────────────────────────────────────────────


def test_png_size_under_10kb_at_256():
    # 4-colour palette + 8×8 mirror grid + zlib level 9 → very small.
    # Sanity guard: anything blowing past 10 KB at 256×256 means the
    # palette / cell-fill changed in a way that breaks zlib's LZ77.
    png = av.render_avatar_png("grid-merge-quarry", "quarry", 256)
    assert len(png) < 10_000, len(png)


def test_render_rejects_silly_sizes():
    import pytest

    with pytest.raises(ValueError):
        av.render_avatar_png("x", "default", 32)   # < 64
    with pytest.raises(ValueError):
        av.render_avatar_png("x", "default", 2048)  # > 1024


def test_render_rejects_empty_slug():
    import pytest

    with pytest.raises(ValueError):
        av.render_avatar_png("", "default", 128)


# ─── Data URI helper ────────────────────────────────────────────────────


def test_data_uri_round_trips():
    uri = av.render_avatar_data_uri("grid-merge-quarry", "quarry", 128)
    assert uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert raw.startswith(PNG_MAGIC)
    assert raw == av.render_avatar_png("grid-merge-quarry", "quarry", 128)


# ─── Task wrapper ───────────────────────────────────────────────────────


def test_task_returns_failed_on_empty_slug():
    import asyncio

    out = asyncio.run(
        av.task_gameka_avatar_render(slug="")
    )
    assert out["buildStatus"] == "failed"
    assert out["avatarDataUri"] == ""


def test_task_returns_ready_on_valid_input():
    import asyncio

    out = asyncio.run(
        av.task_gameka_avatar_render(
            slug="grid-merge-quarry", biome="quarry", size=128,
        )
    )
    assert out["buildStatus"] == "ready"
    assert out["avatarDataUri"].startswith("data:image/png;base64,")
    assert out["avatarSizeBytes"] > 0
    assert out["biome"] == "quarry"


def test_task_round_size_to_grid_multiple():
    import asyncio

    # 100 isn't a multiple of 8; renderer rounds down to 96.
    out = asyncio.run(
        av.task_gameka_avatar_render(
            slug="any", biome="plains", size=100,
        )
    )
    assert out["buildStatus"] == "ready"
    raw = base64.b64decode(out["avatarDataUri"].split(",", 1)[1])
    # IHDR width is bytes 16..20 big-endian after the 8-byte magic.
    import struct
    w = struct.unpack(">I", raw[16:20])[0]
    assert w == 96
