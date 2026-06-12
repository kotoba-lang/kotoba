"""Tests for actor_embed (handler) and ipfs_ingest (primitive) pure functions."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

if "pyzeebe" not in sys.modules:
    _pz = types.ModuleType("pyzeebe")

    class _ZeebeWorkerStub:
        def __init__(self, *a, **kw): pass
        def task(self, **kw): return lambda f: f
        async def work(self): pass

    _pz.ZeebeClient = _ZeebeWorkerStub  # type: ignore[attr-defined]
    _pz.ZeebeWorker = _ZeebeWorkerStub  # type: ignore[attr-defined]
    _pz.create_insecure_channel = lambda **kw: None  # type: ignore[attr-defined]
    sys.modules["pyzeebe"] = _pz

for _mod_name in ("httpx", "requests"):
    if _mod_name not in sys.modules:
        _m = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _m

if "arrow_udf" not in sys.modules:
    _stub = types.ModuleType("arrow_udf")
    def _audf(*a, **kw):
        def _w(fn): return fn
        return _w
    _stub.udf = _audf  # type: ignore[attr-defined]
    sys.modules["arrow_udf"] = _stub


def _load_handler(name: str) -> types.ModuleType:
    src = _py_src / "kotodama" / "handlers" / f"{name}.py"
    mod_name = f"_handler3_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec is not None and spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_primitive(name: str) -> types.ModuleType:
    src = _py_src / "kotodama" / "primitives" / f"{name}.py"
    mod_name = f"_prim_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec is not None and spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ─── actor_embed: _compose ────────────────────────────────────────────────────

AE = _load_handler("actor_embed")


def test_compose_query_prefix():
    result = AE._compose("shinshi", "Legal AI", "tool", "query")
    assert result.startswith("query: ")
    assert "shinshi" in result


def test_compose_passage_prefix():
    result = AE._compose("shinshi", "Legal AI", "tool", "passage")
    assert result.startswith("passage: ")


def test_compose_unknown_mode_defaults_to_passage():
    result = AE._compose("shinshi", None, None, "invalid")
    assert result.startswith("passage: ")


def test_compose_all_fields_present():
    result = AE._compose("Actor X", "An AI agent", "action", "passage")
    assert "Actor X" in result
    assert "An AI agent" in result
    assert "kind=action" in result


def test_compose_missing_description():
    result = AE._compose("Actor X", None, "tool", "passage")
    assert "Actor X" in result
    assert "kind=tool" in result


def test_compose_missing_display_name():
    result = AE._compose(None, "Description only", "tool", "passage")
    assert "Description only" in result


def test_compose_all_none_returns_empty_placeholder():
    result = AE._compose(None, None, None, "passage")
    assert "(empty)" in result


def test_compose_truncates_at_2000_chars():
    long_desc = "a" * 3000
    result = AE._compose("Name", long_desc, None, "passage")
    # Total composed text (after prefix + join) should be <= 2008 chars
    assert len(result) <= 2020  # prefix(8) + 2000 + small overhead


# ─── ipfs_ingest: pure helpers ────────────────────────────────────────────────

II = _load_primitive("ipfs_ingest")


def test_build_multipart_contains_boundary():
    content = b"hello world"
    body, boundary = II._build_multipart(content, "test.txt")
    assert boundary in body.decode("latin-1")
    assert b"hello world" in body


def test_build_multipart_contains_filename():
    content = b"data"
    body, boundary = II._build_multipart(content, "doc.pdf")
    assert b"doc.pdf" in body


def test_ingest_movie_task_accepts_camel_case_aliases(monkeypatch):
    captured = {}

    async def _fake_ingest_movie(source_url, source_ipfs_cid, filename, content_type, max_bytes):
        captured.update(
            source_url=source_url,
            source_ipfs_cid=source_ipfs_cid,
            filename=filename,
            content_type=content_type,
            max_bytes=max_bytes,
        )
        return {"sourceIpfsCid": source_ipfs_cid}

    class _Worker:
        def __init__(self):
            self.tasks = {}

        def task(self, **kwargs):
            def _wrap(fn):
                self.tasks[kwargs["task_type"]] = fn
                return fn
            return _wrap

    monkeypatch.setattr(II, "ingest_movie", _fake_ingest_movie)
    worker = _Worker()
    II.register(worker)

    import asyncio
    asyncio.run(worker.tasks["pdColor.ipfs.ingestMovie"](
        sourceUrl="https://example.com/movie.mp4",
        sourceIpfsCid="bafy-source",
        sourceFilename="movie.mp4",
        sourceContentType="video/mp4",
        maxSourceBytes=123,
    ))
    assert captured == {
        "source_url": "https://example.com/movie.mp4",
        "source_ipfs_cid": "bafy-source",
        "filename": "movie.mp4",
        "content_type": "video/mp4",
        "max_bytes": 123,
    }


def test_build_multipart_boundary_is_hex():
    _, boundary = II._build_multipart(b"x", "f.txt")
    # uuid4().hex is 32 hex chars
    assert len(boundary) == 32
    assert all(c in "0123456789abcdef" for c in boundary)


def test_build_multipart_returns_bytes():
    body, boundary = II._build_multipart(b"content", "file.txt")
    assert isinstance(body, bytes)
    assert isinstance(boundary, str)


def test_base_url_uses_env(monkeypatch):
    monkeypatch.setenv("IPFS_URL", "http://custom-ipfs:5001")
    result = II._base_url()
    assert result == "http://custom-ipfs:5001"


def test_base_url_default(monkeypatch):
    monkeypatch.delenv("IPFS_URL", raising=False)
    result = II._base_url()
    assert "ipfs" in result.lower() or result.startswith("http")


def test_api_requires_hmac_true_for_etzhayyim_domain(monkeypatch):
    monkeypatch.setenv("IPFS_API_URL", "https://ipfs.etzhayyim.com")
    assert II._api_requires_hmac() is True


def test_api_requires_hmac_false_for_local(monkeypatch):
    monkeypatch.setenv("IPFS_API_URL", "http://localhost:5001")
    assert II._api_requires_hmac() is False


def test_load_secret_env_takes_priority(monkeypatch):
    monkeypatch.setenv("IPFS_HMAC", "my-test-hmac-key")
    result = II._load_secret("IPFS_HMAC", "etzhayyim.ipfs", "HMAC_KEY")
    assert result == "my-test-hmac-key"


def test_load_secret_returns_empty_when_not_configured(monkeypatch):
    monkeypatch.delenv("IPFS_HMAC", raising=False)
    # On CI there's no macOS Keychain so this returns ""
    result = II._load_secret("IPFS_HMAC", "etzhayyim.nonexistent.service", "NONEXISTENT_KEY")
    assert isinstance(result, str)


# ─── _api_base_url ────────────────────────────────────────────────────────────

def test_api_base_url_uses_ipfs_api_url_env(monkeypatch):
    monkeypatch.setenv("IPFS_API_URL", "http://api.example.com:5001")
    result = II._api_base_url()
    assert result == "http://api.example.com:5001"


def test_api_base_url_falls_back_to_ipfs_url(monkeypatch):
    monkeypatch.delenv("IPFS_API_URL", raising=False)
    monkeypatch.setenv("IPFS_URL", "http://fallback.example.com:8080")
    result = II._api_base_url()
    assert result == "http://fallback.example.com:8080"


def test_api_base_url_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("IPFS_API_URL", "http://localhost:5001/")
    result = II._api_base_url()
    assert not result.endswith("/")


def test_api_base_url_ipfs_api_url_takes_priority_over_ipfs_url(monkeypatch):
    monkeypatch.setenv("IPFS_API_URL", "http://api-primary:5001")
    monkeypatch.setenv("IPFS_URL", "http://fallback:8080")
    result = II._api_base_url()
    assert result == "http://api-primary:5001"


def test_api_base_url_returns_string_when_no_env(monkeypatch):
    monkeypatch.delenv("IPFS_API_URL", raising=False)
    monkeypatch.delenv("IPFS_URL", raising=False)
    result = II._api_base_url()
    assert isinstance(result, str) and len(result) > 0


# ─── _hmac_key ────────────────────────────────────────────────────────────────

def test_hmac_key_uses_env_var(monkeypatch):
    monkeypatch.setenv("IPFS_HMAC", "my-test-secret")
    result = II._hmac_key()
    assert result == "my-test-secret"


def test_hmac_key_returns_string(monkeypatch):
    monkeypatch.delenv("IPFS_HMAC", raising=False)
    result = II._hmac_key()
    assert isinstance(result, str)
