"""
gameka.avatar.render — pure-stdlib procedural avatar generator
(ADR 2604250900 P10).

Renders a deterministic 256×256 RGB PNG identicon from `slug` + biome.
Used by `publishGame.bpmn` Task_RenderAvatar between sub-DID provision
and title persistence so the resulting `vertex_gameka_title` row
carries an `avatar_data_uri` (data:image/png;base64,…). The shell
page at `game-play.etzhayyim.com/play/{slug}` then surfaces it as the
`<link rel="icon">` and OG image.

Why a data URI rather than a PDS blob ref:
  - blob registration on `app.bsky.actor.profile.avatar` requires
    `com.atproto.repo.uploadBlob` AS the per-title sub-DID, which
    needs deeper PDS-side custody plumbing (ADR-0023 SIGNING_KEYS_D1
    + binary body in dispatch). Out of scope for P10.
  - data URI is enough for the shell + the launch post `embed.external
    .thumb` field (a follow-up can promote it to a blob ref without
    re-rendering — same bytes deterministically derived from slug).

Determinism: same (slug, biome, size) → same byte string. Achieved by:
  - sha256 of slug → deterministic 8×8 bit pattern (mirror-symmetric)
  - fixed zlib compression level (9) → identical byte output
  - no timestamps, no random colour variance

Pure stdlib — only `hashlib`, `zlib`, `struct`, `base64`. No Pillow,
no Cairo, no canvas. Output is ~1-5 KB per avatar (4-colour palette
+ 8×8 grid compresses very well).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import struct
import zlib
from typing import Tuple

log = logging.getLogger(__name__)


# Splatoon-pastel palettes per kami-engine biome (4 tones each).
# Hand-picked so the resulting identicons read as biome-coherent at
# a glance. Palette order is dark→light; mid-tones ride the 8×8 hash.
_PALETTES: dict[str, Tuple[Tuple[int, int, int], ...]] = {
    "quarry":  ((90, 70, 50),    (140, 110, 80),  (200, 180, 150), (244, 234, 214)),
    "tundra":  ((90, 130, 180),  (150, 180, 210), (210, 225, 240), (245, 245, 255)),
    "plains":  ((70, 130, 70),   (120, 180, 100), (190, 215, 160), (245, 235, 210)),
    "desert":  ((180, 130, 60),  (220, 170, 80),  (245, 210, 140), (255, 235, 200)),
}
_DEFAULT_PALETTE = ((100, 100, 100), (150, 150, 150), (200, 200, 200), (244, 234, 214))

# Biome name normaliser — same shape as gameka_codegen._biome_for but
# operates on a single short string instead of free-form scene text.
_BIOME_RE = re.compile(r"[^a-z]+")


def _normalise_biome(biome: str) -> str:
    s = _BIOME_RE.sub("", str(biome or "").lower())[:16]
    return s if s in _PALETTES else "default"


def _palette_for(biome: str) -> Tuple[Tuple[int, int, int], ...]:
    return _PALETTES.get(_normalise_biome(biome), _DEFAULT_PALETTE)


def _png_chunk(typ: bytes, data: bytes) -> bytes:
    """Single PNG chunk: length(4) + type(4) + data(N) + crc32(4)."""
    crc = zlib.crc32(typ + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", crc)


def render_avatar_png(slug: str, biome: str = "default", size: int = 256) -> bytes:
    """Pure-function PNG render. Deterministic across runs.

    The 8×8 identicon is mirror-symmetric (left↔right) so the result
    looks like a recognisable face/sigil. Each cell picks a palette
    index from sha256(slug) bits.
    """
    if not slug:
        raise ValueError("slug is required")
    if size < 64 or size > 1024:
        raise ValueError("size must be in 64..1024")
    grid_n = 8
    if size % grid_n != 0:
        # Round down to the nearest multiple of 8 so cells tile cleanly.
        size = (size // grid_n) * grid_n
    cell = size // grid_n

    palette = _palette_for(biome)

    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    # 256 bits → 128 2-bit symbols. We need only 32 (8 rows × 4 left
    # cols, mirrored), so reading from the front of the stream is
    # plenty.
    cells: list[list[int]] = [[0] * grid_n for _ in range(grid_n)]
    bit_idx = 0
    for row in range(grid_n):
        for col in range(grid_n // 2):
            byte = digest[bit_idx // 4]
            shift = (bit_idx % 4) * 2
            color = (byte >> shift) & 0b11
            cells[row][col] = color
            cells[row][grid_n - 1 - col] = color  # mirror
            bit_idx += 1

    # Rasterise to a flat RGB byte array. Solid blocks compress
    # extremely well via zlib's LZ77, so the IDAT stays in the
    # 1-5 KB range even at size=256.
    row_bytes = size * 3
    img = bytearray(size * row_bytes)
    for row in range(grid_n):
        for col in range(grid_n):
            r, g, b = palette[cells[row][col]]
            y0 = row * cell
            x0 = col * cell
            for y in range(y0, y0 + cell):
                off = y * row_bytes + x0 * 3
                for _ in range(cell):
                    img[off] = r
                    img[off + 1] = g
                    img[off + 2] = b
                    off += 3

    # Add the per-scanline filter byte (0 = None). PNG requires this.
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        raw.extend(img[y * row_bytes:(y + 1) * row_bytes])
    compressed = zlib.compress(bytes(raw), 9)

    png = b"\x89PNG\r\n\x1a\n"
    # IHDR: width, height, bit_depth=8, color_type=2 (RGB),
    # compression=0, filter=0, interlace=0
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", compressed)
    png += _png_chunk(b"IEND", b"")
    return bytes(png)


def render_avatar_data_uri(slug: str, biome: str = "default", size: int = 256) -> str:
    """Convenience — render + base64-wrap as a `data:image/png;base64,…`
    URI ready to be stored in `vertex_gameka_title.avatar_data_uri`."""
    png = render_avatar_png(slug, biome, size)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


# ─── LangServer task wrapper ───────────────────────────────────────────────


async def task_gameka_avatar_render(
    slug: str = "",
    biome: str = "default",
    size: int = 256,
) -> dict:
    """Entry point registered as `gameka.avatar.render`. The BPMN passes
    spec.slug + the FEEL-extracted biome hint. Returns a flat dict
    consumable by FEEL ioMapping.

    Failure modes (all return without raising — BPMN persists an empty
    avatar_data_uri rather than incident-stopping the publish chain):
      - missing slug                 → buildStatus="failed"
      - PNG render exception         → buildStatus="failed"
      - oversize after compression   → buildStatus="failed" (>=900 KB
                                       hard cap; protects RW row size
                                       and the AT firehose)
    """
    if not slug:
        return {
            "avatarDataUri": "",
            "avatarSizeBytes": 0,
            "biome": "default",
            "buildStatus": "failed",
            "error": "missing slug",
        }
    try:
        png = render_avatar_png(slug, biome or "default", int(size or 256))
    except Exception as e:  # noqa: BLE001
        log.warning("gameka.avatar.render error: %s", e)
        return {
            "avatarDataUri": "",
            "avatarSizeBytes": 0,
            "biome": biome or "default",
            "buildStatus": "failed",
            "error": f"{type(e).__name__}:{str(e)[:80]}",
        }
    if len(png) > 900_000:
        return {
            "avatarDataUri": "",
            "avatarSizeBytes": len(png),
            "biome": biome or "default",
            "buildStatus": "failed",
            "error": f"oversize: {len(png)} bytes (cap 900_000)",
        }
    uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    return {
        "avatarDataUri": uri,
        "avatarSizeBytes": len(png),
        "biome": _normalise_biome(biome or "default"),
        "buildStatus": "ready",
    }
