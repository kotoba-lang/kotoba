"""Tests for kotodama.substrate — Python SDK seam (ADR-2605231400).

Network calls are mocked via httpx MockTransport so the suite runs in CI
without a live PDS.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from kotodama.substrate import (
    AuthError,
    Etzhayyim,
    ReadError,
    ReadOpts,
    ReadResponse,
    WriteError,
    WriteOpts,
    WriteReceipt,
    _exclusive_upper_bound,
)


DID_FIX = "did:web:maps.etzhayyim.com"
PDS_FIX = "https://pds.test.local"


def _client(handler) -> Etzhayyim:
    """Build an Etzhayyim with a MockTransport-backed httpx client."""
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(base_url=PDS_FIX, transport=transport)
    return Etzhayyim(
        did=DID_FIX,
        pds_url=PDS_FIX,
        session_jwt="test-jwt",
        http_client=http,
    )


# ── _exclusive_upper_bound ─────────────────────────────────────────────


def test_exclusive_upper_bound_simple():
    assert _exclusive_upper_bound("registry-") == "registry."
    assert _exclusive_upper_bound("geocode") == "geocodf"
    assert _exclusive_upper_bound("a") == "b"


def test_exclusive_upper_bound_empty():
    assert _exclusive_upper_bound("") == ""


# ── write ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_happy_path():
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/xrpc/com.atproto.repo.createRecord"
        body = json.loads(req.content)
        captured["body"] = body
        captured["headers"] = dict(req.headers)
        return httpx.Response(
            200,
            json={
                "uri": "at://did:web:maps.etzhayyim.com/com.etzhayyim.maps.source/geocode",
                "cid": "bafyreidemo",
            },
        )

    async with _client(handler) as e:
        receipt = await e.write(
            WriteOpts(
                collection="com.etzhayyim.maps.source",
                record={"v": 1, "slug": "geocode"},
                rkey="geocode",
            )
        )

    assert isinstance(receipt, WriteReceipt)
    assert receipt.uri.endswith("/geocode")
    assert receipt.cid == "bafyreidemo"
    assert captured["body"]["repo"] == DID_FIX
    assert captured["body"]["collection"] == "com.etzhayyim.maps.source"
    assert captured["body"]["rkey"] == "geocode"
    assert captured["body"]["record"]["slug"] == "geocode"
    assert captured["headers"]["authorization"] == "Bearer test-jwt"


@pytest.mark.asyncio
async def test_write_omits_rkey_when_absent():
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return httpx.Response(200, json={"uri": "at://did/c/abc", "cid": "bafy"})

    async with _client(handler) as e:
        await e.write(WriteOpts(collection="x.y.z", record={"v": 1}))

    assert "rkey" not in captured["body"]


@pytest.mark.asyncio
async def test_write_401_raises_auth_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid token")

    async with _client(handler) as e:
        with pytest.raises(AuthError):
            await e.write(WriteOpts(collection="x.y.z", record={}))


@pytest.mark.asyncio
async def test_write_4xx_raises_write_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="invalid record")

    async with _client(handler) as e:
        with pytest.raises(WriteError):
            await e.write(WriteOpts(collection="x.y.z", record={}))


@pytest.mark.asyncio
async def test_write_requires_auth():
    """Etzhayyim with no session_jwt and no internal_token must reject write."""
    http = httpx.AsyncClient(base_url=PDS_FIX, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    e = Etzhayyim(did=DID_FIX, pds_url=PDS_FIX, http_client=http)
    with pytest.raises(AuthError):
        await e.write(WriteOpts(collection="x.y.z", record={}))
    await e.aclose()


@pytest.mark.asyncio
async def test_write_internal_token_header():
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(req.headers)
        return httpx.Response(200, json={"uri": "at://did/c/abc", "cid": "bafy"})

    http = httpx.AsyncClient(base_url=PDS_FIX, transport=httpx.MockTransport(handler))
    e = Etzhayyim(did=DID_FIX, pds_url=PDS_FIX, internal_token="srv-token", http_client=http)
    await e.write(WriteOpts(collection="x.y.z", record={}))
    await e.aclose()

    assert captured["headers"]["x-kotoba-kotodama-verified"] == "srv-token"
    assert "authorization" not in captured["headers"]


@pytest.mark.asyncio
async def test_write_response_missing_uri_raises():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"cid": "bafy"})  # missing uri

    async with _client(handler) as e:
        with pytest.raises(WriteError):
            await e.write(WriteOpts(collection="x.y.z", record={}))


# ── read (getRecord, single) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_single_record_happy_path():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/xrpc/com.atproto.repo.getRecord"
        assert req.url.params["rkey"] == "geocode"
        return httpx.Response(
            200,
            json={
                "uri": "at://did/c/geocode",
                "cid": "bafy",
                "value": {"v": 1, "slug": "geocode"},
            },
        )

    async with _client(handler) as e:
        resp = await e.read(ReadOpts(collection="com.etzhayyim.maps.source", rkey="geocode"))

    assert isinstance(resp, ReadResponse)
    assert len(resp.records) == 1
    assert resp.records[0].value["slug"] == "geocode"
    assert resp.cursor is None


@pytest.mark.asyncio
async def test_read_single_record_404_returns_empty():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    async with _client(handler) as e:
        resp = await e.read(ReadOpts(collection="x.y.z", rkey="missing"))

    assert resp.records == []


# ── read (listRecords) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_list_records_with_prefix():
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["params"] = dict(req.url.params)
        return httpx.Response(
            200,
            json={
                "records": [
                    {"uri": "at://did/c/registry-gleif", "cid": "bafy1", "value": {"slug": "registry-gleif"}},
                    {"uri": "at://did/c/registry-osm", "cid": "bafy2", "value": {"slug": "registry-osm"}},
                ],
                "cursor": "next-page",
            },
        )

    async with _client(handler) as e:
        resp = await e.read(
            ReadOpts(
                collection="com.etzhayyim.maps.source",
                prefix="registry-",
                limit=50,
            )
        )

    assert len(resp.records) == 2
    assert resp.cursor == "next-page"
    assert captured["params"]["rkeyStart"] == "registry-"
    assert captured["params"]["rkeyEnd"] == "registry."  # exclusive upper bound


@pytest.mark.asyncio
async def test_read_list_records_empty():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"records": []})

    async with _client(handler) as e:
        resp = await e.read(ReadOpts(collection="x.y.z"))

    assert resp.records == []
    assert resp.cursor is None


@pytest.mark.asyncio
async def test_read_propagates_cursor():
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["params"] = dict(req.url.params)
        return httpx.Response(200, json={"records": []})

    async with _client(handler) as e:
        await e.read(ReadOpts(collection="x.y.z", cursor="my-cursor-abc"))

    assert captured["params"]["cursor"] == "my-cursor-abc"


@pytest.mark.asyncio
async def test_read_401_raises_auth_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid token")

    async with _client(handler) as e:
        with pytest.raises(AuthError):
            await e.read(ReadOpts(collection="x.y.z"))


@pytest.mark.asyncio
async def test_read_5xx_raises_read_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    async with _client(handler) as e:
        with pytest.raises(ReadError):
            await e.read(ReadOpts(collection="x.y.z"))


@pytest.mark.asyncio
async def test_read_malformed_item_raises():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"records": [{"uri": "at://x"}]})  # missing cid

    async with _client(handler) as e:
        with pytest.raises(ReadError):
            await e.read(ReadOpts(collection="x.y.z"))


# ── verify ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_scaffold_returns_not_implemented():
    """The scaffold reports `included=False` + a 'not yet implemented' error,
    matching the TS SDK's v0.1.0-alpha shape."""

    async with _client(lambda r: httpx.Response(200, json={})) as e:
        result = await e.verify("at://did/c/x")

    assert result.included is False
    assert result.error is not None
    assert "not yet implemented" in result.error.lower()
