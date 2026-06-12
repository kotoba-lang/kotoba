"""Tests for pure rendering functions in handlers/gameka_avatar.py.

render_avatar_png and render_avatar_data_uri are fully deterministic:
no DB, no network, no filesystem. All paths testable without mocks.

Uses isolated module load to avoid NSID double-registration.
"""

from __future__ import annotations

import base64
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub arrow_udf so @udf decorator is a no-op
if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub

_mod_name = "_handler_pure_gameka_avatar"
if _mod_name not in sys.modules:
    _src = _py_src / "kotodama" / "handlers" / "gameka_avatar.py"
    _spec = importlib.util.spec_from_file_location(_mod_name, _src)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_mod_name] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
_ga = sys.modules[_mod_name]

render_avatar_png = _ga.render_avatar_png
render_avatar_data_uri = _ga.render_avatar_data_uri


# ─── render_avatar_png ───────────────────────────────────────────────────────

def test_png_starts_with_magic_bytes() -> None:
    result = render_avatar_png("test-slug")
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_png_contains_ihdr_chunk() -> None:
    result = render_avatar_png("test-slug")
    assert b"IHDR" in result


def test_png_contains_idat_chunk() -> None:
    result = render_avatar_png("test-slug")
    assert b"IDAT" in result


def test_png_contains_iend_chunk() -> None:
    result = render_avatar_png("test-slug")
    assert b"IEND" in result


def test_png_is_bytes() -> None:
    result = render_avatar_png("test-slug")
    assert isinstance(result, bytes)


def test_png_deterministic_same_slug() -> None:
    a = render_avatar_png("hello-world")
    b = render_avatar_png("hello-world")
    assert a == b


def test_png_varies_with_slug() -> None:
    a = render_avatar_png("slug-a")
    b = render_avatar_png("slug-b")
    assert a != b


def test_png_empty_slug_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="slug"):
        render_avatar_png("")


def test_png_size_too_small_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        render_avatar_png("x", size=32)


def test_png_size_too_large_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        render_avatar_png("x", size=2048)


def test_png_default_size_256() -> None:
    result = render_avatar_png("slug-1")
    assert len(result) > 100


def test_png_custom_biome_differs_from_default() -> None:
    default_png = render_avatar_png("slug", biome="default")
    plains_png = render_avatar_png("slug", biome="plains")
    assert default_png != plains_png


def test_png_unknown_biome_uses_default() -> None:
    unknown = render_avatar_png("slug", biome="xyzzy")
    default = render_avatar_png("slug", biome="default")
    assert unknown == default


def test_png_size_rounds_down_to_multiple_of_8() -> None:
    result1 = render_avatar_png("slug", size=256)
    result2 = render_avatar_png("slug", size=257)
    assert result1 == result2


def test_png_explicit_64_size() -> None:
    result = render_avatar_png("slug", size=64)
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_png_explicit_512_size() -> None:
    result = render_avatar_png("slug", size=512)
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_png_different_sizes_differ() -> None:
    small = render_avatar_png("slug", size=64)
    large = render_avatar_png("slug", size=256)
    assert small != large


def test_png_larger_is_bigger() -> None:
    small = render_avatar_png("slug", size=64)
    large = render_avatar_png("slug", size=256)
    assert len(large) > len(small)


# ─── render_avatar_data_uri ──────────────────────────────────────────────────

def test_data_uri_starts_with_mime() -> None:
    result = render_avatar_data_uri("slug")
    assert result.startswith("data:image/png;base64,")


def test_data_uri_is_valid_base64() -> None:
    result = render_avatar_data_uri("slug")
    b64_part = result.split(",", 1)[1]
    decoded = base64.b64decode(b64_part)
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


def test_data_uri_deterministic() -> None:
    a = render_avatar_data_uri("same-slug")
    b = render_avatar_data_uri("same-slug")
    assert a == b


def test_data_uri_varies_with_slug() -> None:
    a = render_avatar_data_uri("slug-x")
    b = render_avatar_data_uri("slug-y")
    assert a != b


def test_data_uri_is_string() -> None:
    result = render_avatar_data_uri("slug")
    assert isinstance(result, str)
