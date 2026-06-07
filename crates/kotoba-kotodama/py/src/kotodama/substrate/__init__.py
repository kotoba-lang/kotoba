"""kotodama.substrate — Python-side seam for the etzhayyim RW-free substrate.

Mirrors the surface of TypeScript ``@etzhayyim/sdk`` (Etzhayyim class with
``write`` / ``read`` / ``verify``) so Python bulk-ingest pods can write to
the AT Protocol PDS + IPFS substrate without importing RW or atproto SDK
clients directly. Per ADR-2605231400 + ADR-2605172000.

Substrate boundary:
  * Allowed substrate clients: ``httpx`` (this module). PDS HTTP endpoint
    is the canonical surface; kotodama.substrate is the documented Python
    SDK seam (analog of the TS @etzhayyim/sdk seam).
  * Prohibited substrate clients: ``atproto`` SDK, ``viem`` analog,
    ``ipfshttpclient``, ``noble-ciphers`` analog. Re-route those through
    HTTP API calls from this module.

Auth modes:
  1. **session_jwt**: User-side. Standard AT Protocol Bearer JWT obtained
     via ``com.atproto.server.createSession``. Refresh handled by caller
     (kotodama does not currently auto-refresh).
  2. **internal_token**: Service-to-service. Sends ``x-kotoba-kotodama-verified``
     header against kotoba-kotodama-host-sdk's internal trust path. Used by
     bulk-ingest pods that don't have a per-user session.

Read access does not require auth for public collections; write always
requires auth.

Status: scaffold v0.0.0. Live PDS interop pending operator wiring
(env var ETZ_PDS_URL etc.).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx


DEFAULT_PDS_URL = "https://pds.etzhayyim.com"
DEFAULT_IPFS_GATEWAY = "https://ipfs.etzhayyim.com"
DEFAULT_L2_RPC_URL = "https://mainnet.base.org"

DEFAULT_HTTP_TIMEOUT_SEC = 30.0


# ─── Public dataclasses (mirror @etzhayyim/sdk shapes) ────────────────


@dataclass
class WriteOpts:
    """Single record write."""

    collection: str
    record: dict[str, Any]
    rkey: str | None = None
    """Optional. If absent and the lexicon ``key`` is ``tid``, PDS assigns one."""


@dataclass
class WriteReceipt:
    uri: str
    cid: str


@dataclass
class ReadOpts:
    """Range or single-record read."""

    collection: str
    rkey: str | None = None
    prefix: str | None = None
    limit: int = 100
    cursor: str | None = None
    fetch_blobs: bool = False


@dataclass
class ReadRecord:
    uri: str
    cid: str
    value: dict[str, Any]


@dataclass
class ReadResponse:
    records: list[ReadRecord] = field(default_factory=list)
    cursor: str | None = None


@dataclass
class VerifyResult:
    """Subset of TS VerifyResult — Python pods rarely need the full Merkle path here."""

    uri: str
    included: bool
    anchor_tx_hash: str | None = None
    anchor_block_number: int | None = None
    root_cid: str | None = None
    error: str | None = None


# ─── Errors ──────────────────────────────────────────────────────────


class SubstrateError(Exception):
    """Base error for kotodama.substrate operations."""


class AuthError(SubstrateError):
    """Authentication failure (no token / expired token / 401 from PDS)."""


class WriteError(SubstrateError):
    """PDS rejected a write (validation, conflict, 4xx)."""


class ReadError(SubstrateError):
    """PDS rejected a read or returned an unexpected shape."""


# ─── Etzhayyim client ────────────────────────────────────────────────


class Etzhayyim:
    """Async substrate client. One per pod / per actor DID.

    Usage::

        e = Etzhayyim(
            did="did:web:maps.etzhayyim.com",
            session_jwt=os.environ["ETZ_SESSION_JWT"],
        )
        receipt = await e.write(WriteOpts(
            collection="com.etzhayyim.maps.source",
            record={"v": 1, "slug": "geocode", ...},
            rkey="geocode",
        ))
        rows = await e.read(ReadOpts(
            collection="com.etzhayyim.maps.source",
            prefix="registry-",
            limit=20,
        ))

    Two auth modes:
      * Pass ``session_jwt`` for user-side writes (AT Protocol Bearer).
      * Pass ``internal_token`` for service-to-service writes (sent as
        ``x-kotoba-kotodama-verified`` header).
    """

    def __init__(
        self,
        did: str,
        *,
        pds_url: str | None = None,
        ipfs_gateway: str | None = None,
        l2_rpc_url: str | None = None,
        session_jwt: str | None = None,
        internal_token: str | None = None,
        timeout_sec: float = DEFAULT_HTTP_TIMEOUT_SEC,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.did = did
        self.pds_url = (pds_url or os.environ.get("ETZ_PDS_URL") or DEFAULT_PDS_URL).rstrip("/")
        self.ipfs_gateway = ipfs_gateway or os.environ.get("ETZ_IPFS_GATEWAY") or DEFAULT_IPFS_GATEWAY
        self.l2_rpc_url = l2_rpc_url or os.environ.get("ETZ_L2_RPC_URL") or DEFAULT_L2_RPC_URL
        self._session_jwt = session_jwt or os.environ.get("ETZ_SESSION_JWT")
        self._internal_token = internal_token or os.environ.get("KOTODAMA_INTERNAL_TOKEN")
        self._owned_http = http_client is None
        self._http: httpx.AsyncClient = http_client or httpx.AsyncClient(
            base_url=self.pds_url,
            timeout=timeout_sec,
        )

    # ── lifecycle ────────────────────────────────────────────────────

    async def __aenter__(self) -> "Etzhayyim":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owned_http:
            await self._http.aclose()

    # ── public API ───────────────────────────────────────────────────

    async def write(self, opts: WriteOpts) -> WriteReceipt:
        """Create a record. Maps to ``com.atproto.repo.createRecord``."""
        if not self._session_jwt and not self._internal_token:
            raise AuthError("write requires session_jwt or internal_token")
        body: dict[str, Any] = {
            "repo": self.did,
            "collection": opts.collection,
            "record": opts.record,
        }
        if opts.rkey is not None:
            body["rkey"] = opts.rkey
        try:
            resp = await self._http.post(
                "/xrpc/com.atproto.repo.createRecord",
                json=body,
                headers=self._auth_headers(),
            )
        except httpx.RequestError as caught:
            raise WriteError(f"PDS request failed: {caught}") from caught
        if resp.status_code == 401:
            raise AuthError(f"PDS returned 401: {resp.text}")
        if resp.status_code >= 400:
            raise WriteError(f"PDS returned {resp.status_code}: {resp.text}")
        payload = _parse_json(resp, "write")
        try:
            return WriteReceipt(uri=payload["uri"], cid=payload["cid"])
        except (KeyError, TypeError) as caught:
            raise WriteError(f"PDS response missing uri/cid: {payload!r}") from caught

    async def read(self, opts: ReadOpts) -> ReadResponse:
        """List or get records.

        If ``rkey`` is set → ``com.atproto.repo.getRecord`` (single record).
        Otherwise → ``com.atproto.repo.listRecords`` with optional rkey-prefix
        + cursor pagination.
        """
        if opts.rkey is not None:
            return await self._get_record(opts)
        return await self._list_records(opts)

    async def verify(self, uri: str) -> VerifyResult:
        """Merkle proof against the Base L2 anchor.

        Scaffold: returns a 'not yet implemented' result. Live verification
        requires the L2 anchor contract to be deployed + the anchor-cron
        pipeline to be writing roots. Caller may inspect ``error`` to
        distinguish 'not anchored yet' from 'tampered'.
        """
        return VerifyResult(
            uri=uri,
            included=False,
            error="verify() not yet implemented in kotodama.substrate scaffold (parity with TS SDK 0.1.0-alpha)",
        )

    # ── internal helpers ─────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._session_jwt:
            headers["Authorization"] = f"Bearer {self._session_jwt}"
        if self._internal_token:
            headers["x-kotoba-kotodama-verified"] = self._internal_token
        return headers

    async def _get_record(self, opts: ReadOpts) -> ReadResponse:
        params = {
            "repo": self.did,
            "collection": opts.collection,
            "rkey": opts.rkey or "",
        }
        try:
            resp = await self._http.get(
                "/xrpc/com.atproto.repo.getRecord",
                params=params,
                headers=self._auth_headers(),
            )
        except httpx.RequestError as caught:
            raise ReadError(f"PDS request failed: {caught}") from caught
        if resp.status_code == 404:
            return ReadResponse(records=[], cursor=None)
        if resp.status_code == 401:
            raise AuthError(f"PDS returned 401: {resp.text}")
        if resp.status_code >= 400:
            raise ReadError(f"PDS returned {resp.status_code}: {resp.text}")
        payload = _parse_json(resp, "read.get")
        try:
            return ReadResponse(
                records=[
                    ReadRecord(
                        uri=payload["uri"],
                        cid=payload["cid"],
                        value=payload["value"],
                    )
                ],
                cursor=None,
            )
        except (KeyError, TypeError) as caught:
            raise ReadError(f"PDS getRecord response shape: {payload!r}") from caught

    async def _list_records(self, opts: ReadOpts) -> ReadResponse:
        params: dict[str, str | int] = {
            "repo": self.did,
            "collection": opts.collection,
            "limit": opts.limit,
        }
        if opts.cursor:
            params["cursor"] = opts.cursor
        if opts.prefix:
            params["rkeyStart"] = opts.prefix
            params["rkeyEnd"] = _exclusive_upper_bound(opts.prefix)
        try:
            resp = await self._http.get(
                "/xrpc/com.atproto.repo.listRecords",
                params=params,
                headers=self._auth_headers(),
            )
        except httpx.RequestError as caught:
            raise ReadError(f"PDS request failed: {caught}") from caught
        if resp.status_code == 401:
            raise AuthError(f"PDS returned 401: {resp.text}")
        if resp.status_code >= 400:
            raise ReadError(f"PDS returned {resp.status_code}: {resp.text}")
        payload = _parse_json(resp, "read.list")
        raw_records = payload.get("records") or []
        records: list[ReadRecord] = []
        for r in raw_records:
            try:
                records.append(ReadRecord(uri=r["uri"], cid=r["cid"], value=r["value"]))
            except (KeyError, TypeError) as caught:
                raise ReadError(f"PDS listRecords item shape: {r!r}") from caught
        return ReadResponse(records=records, cursor=payload.get("cursor"))


# ─── module-level helpers ────────────────────────────────────────────


def _parse_json(resp: httpx.Response, ctx: str) -> dict[str, Any]:
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError) as caught:
        raise SubstrateError(f"PDS {ctx} returned non-JSON: {resp.text[:200]!r}") from caught


def _exclusive_upper_bound(prefix: str) -> str:
    """Build a rkey upper bound that PDS listRecords treats as exclusive.

    AT Protocol listRecords ``rkeyEnd`` is exclusive when supplied. For a
    prefix like ``"registry-"`` we want the listing to return all rkeys
    ``>= "registry-"`` and ``< "registry/"`` (the next code point after ``-``).
    """
    if not prefix:
        return prefix
    last = prefix[-1]
    return prefix[:-1] + chr(ord(last) + 1)


__all__ = [
    "AuthError",
    "DEFAULT_HTTP_TIMEOUT_SEC",
    "DEFAULT_IPFS_GATEWAY",
    "DEFAULT_L2_RPC_URL",
    "DEFAULT_PDS_URL",
    "Etzhayyim",
    "ReadError",
    "ReadOpts",
    "ReadRecord",
    "ReadResponse",
    "SubstrateError",
    "VerifyResult",
    "WriteError",
    "WriteOpts",
    "WriteReceipt",
]
