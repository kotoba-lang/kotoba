from __future__ import annotations

import hashlib
import hmac
import sys
from pathlib import Path
from typing import Any

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import gov_fetch_proxy


def test_body_to_hash_text_strips_html() -> None:
    body = b"<html><body><h1>Hello</h1><p>World</p></body></html>"
    content_hash, text = gov_fetch_proxy.body_to_hash_text(body)
    assert content_hash == hashlib.md5(body).hexdigest()
    assert text == "Hello World"


def test_proxy_fetch_hash_signs_get_payload(monkeypatch: Any) -> None:
    seen: dict[str, Any] = {}

    class FakeResponse:
        status = 200

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self, _limit: int = -1) -> bytes:
            return b"<title>Gov</title>"

    def fake_urlopen(req: Any, timeout: int = 0) -> FakeResponse:
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("GOV_FETCH_PROXY_URL", "https://gov-fetch.etzhayyim.com/fetch")
    monkeypatch.setenv("GOV_FETCH_HMAC", "secret")
    monkeypatch.setattr(gov_fetch_proxy._u_req, "urlopen", fake_urlopen)

    content_hash, text = gov_fetch_proxy.proxy_fetch_hash("https://www.example.gov/", timeout=7)

    expected = hmac.new(
        b"secret",
        b"GET\nhttps://www.example.gov/",
        hashlib.sha256,
    ).hexdigest()
    assert content_hash == hashlib.md5(b"<title>Gov</title>").hexdigest()
    assert text == "Gov"
    assert "url=https%3A%2F%2Fwww.example.gov%2F" in seen["url"]
    assert seen["headers"]["X-etzhayyim-gov-fetch-auth"] == expected
    assert seen["timeout"] == 7


def test_direct_then_proxy_uses_proxy_after_direct_failure(monkeypatch: Any) -> None:
    monkeypatch.setattr(gov_fetch_proxy, "direct_fetch_hash", lambda *_args, **_kwargs: ("", ""))
    monkeypatch.setattr(gov_fetch_proxy, "proxy_fetch_hash", lambda *_args, **_kwargs: ("abc", "fallback"))
    assert gov_fetch_proxy.direct_then_proxy_fetch_hash("https://blocked.example/") == (
        "abc",
        "fallback",
    )
