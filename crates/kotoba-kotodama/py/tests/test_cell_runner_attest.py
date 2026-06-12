"""Integration tests for the cell-runner /kotoba-datomic/attest endpoint.

Uses aiohttp's AppRunner + TCPSite to spin up the real cell-runner HTTP
server, then asserts the orchestrator-side request/response contract.

PDS write-back is disabled via SUBSTRATE_WRITE_DISABLED=1 so the test
focuses on the attestation production + transport plumbing.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os

import aiohttp
import pytest
from aiohttp import web

import kotodama.cell_runner_main as cell_runner
from kotodama.kotoba-datomic import quorum_group_for


# ─── fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _disable_substrate_write(monkeypatch):
    monkeypatch.setenv("SUBSTRATE_WRITE_DISABLED", "1")
    monkeypatch.setenv("ETZHAYYIM_NODE_NAME", "testnode")


@pytest.fixture
def _hosted_cells(monkeypatch):
    """Populate the module-level _active_cells_metadata so the endpoint
    knows what cells are hosted on this node."""
    metadata = [
        {"name": "MapsFeatureAttestor0", "trigger": {"kind": "xrpc"}},
        {"name": "MapsFeatureAttestor1", "trigger": {"kind": "xrpc"}},
    ]
    monkeypatch.setattr(cell_runner, "_active_cells_metadata", metadata)
    return metadata


@pytest.fixture
async def _server(_hosted_cells):
    app = web.Application()
    app.router.add_get("/healthz", cell_runner._cell_runner_healthz)
    app.router.add_post("/kotoba-datomic/attest", cell_runner._cell_runner_kotoba-datomic_attest)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[attr-defined]
    base = f"http://127.0.0.1:{port}"
    try:
        yield base
    finally:
        await runner.cleanup()


def _valid_request_body(cell_id: str = "MapsFeatureAttestor0") -> dict:
    return {
        "v": 1,
        "cellId": cell_id,
        "recordUri": "at://did:web:maps.etzhayyim.com/com.etzhayyim.maps.feature/mount-fuji",
        "recordCid": "bafy-mount-fuji",
        "record": {
            "label": "Mountain",
            "geometryGeoJson": '{"type":"Point","coordinates":[138.7274,35.3606]}',
            "h3Cell": "8a30d8bd2477fff",
            "h3Resolution": 8,
            "name": "富士山",
        },
        "rule": {
            "v": 1,
            "nsid": "com.etzhayyim.maps.feature",
            "schemaRef": {"path": "lex.json", "contentHash": "0" * 64, "version": "1.0.0"},
            "policyRef": {"path": "p.rego", "contentHash": "0" * 64, "version": "1.0.0"},
            "cellRef": {"path": "cell/", "contentHash": "0" * 64, "version": "abcdef0"},
            "quorumSize": 5,
            "quorumThreshold": 3,
            "escalationPolicy": "council",
            "registeredAt": "2026-05-23T00:00:00Z",
        },
    }


# ─── happy path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_healthz_lists_hosted_cells(_server):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{_server}/healthz") as resp:
            assert resp.status == 200
            body = await resp.json()
            assert body["ok"] is True
            assert body["service"] == "kotoba-kotodama-cell-runner"
            assert body["node"] == "testnode"
            assert body["cells_loaded"] == 2
            names = [c["name"] for c in body["cells"]]
            assert "MapsFeatureAttestor0" in names


@pytest.mark.asyncio
async def test_attest_happy_path_returns_202_with_verdict(_server):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_server}/kotoba-datomic/attest",
            json=_valid_request_body(),
        ) as resp:
            assert resp.status == 202
            body = await resp.json()
            assert body["ok"] is True
            assert body["verdict"] == "accept"
            assert body["cellId"] == "MapsFeatureAttestor0"
            assert body["cellNode"] == "testnode"
            # quorumGroup is deterministic — should match sha256(cid)[:16]
            expected_qg = quorum_group_for("bafy-mount-fuji")
            assert body["quorumGroup"] == expected_qg


# ─── rejection paths ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_attest_404_when_cell_not_hosted(_server):
    body = _valid_request_body(cell_id="UnknownCell")
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{_server}/kotoba-datomic/attest", json=body) as resp:
            assert resp.status == 404
            err = await resp.json()
            assert err["error"] == "cell-not-hosted"
            assert err["cellId"] == "UnknownCell"
            assert "MapsFeatureAttestor0" in err["hosted"]


@pytest.mark.asyncio
async def test_attest_400_on_missing_cellId(_server):
    body = _valid_request_body()
    del body["cellId"]
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{_server}/kotoba-datomic/attest", json=body) as resp:
            assert resp.status == 400
            err = await resp.json()
            assert err["error"] == "missing-cellId"


@pytest.mark.asyncio
async def test_attest_400_on_invalid_request_shape(_server):
    body = _valid_request_body()
    del body["recordUri"]
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{_server}/kotoba-datomic/attest", json=body) as resp:
            assert resp.status == 400
            err = await resp.json()
            assert err["error"] == "invalid-request-shape"


@pytest.mark.asyncio
async def test_attest_400_on_non_json_body(_server):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_server}/kotoba-datomic/attest",
            data="not json at all",
            headers={"Content-Type": "application/json"},
        ) as resp:
            assert resp.status == 400
            err = await resp.json()
            assert err["error"] == "invalid-json"


# ─── interop sanity: produced attestation matches lexicon shape ──────


@pytest.mark.asyncio
async def test_attest_response_carries_canonical_quorum_group(_server):
    """The cellNode + quorumGroup in the response must match what the
    orchestrator will derive client-side. This is the interop contract."""
    body = _valid_request_body()
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{_server}/kotoba-datomic/attest", json=body) as resp:
            resp_body = await resp.json()
    assert resp_body["quorumGroup"] == quorum_group_for(body["recordCid"])
