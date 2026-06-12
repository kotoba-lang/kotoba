"""IPFS ingest LangServer primitives.

Task types registered:
  ipfs.add      — add content to IPFS node; output: cid, ipfs_url
  ipfs.pinByCid — pin an already-reachable CID; output: pinned (bool)

Required secrets (Keychain etzhayyim.ipfs or env):
  IPFS_URL   — https://ipfs.etzhayyim.com (default)
  IPFS_HMAC  — 32-byte hex HMAC key (same value stored in etzhayyim-ipfs-proxy Worker secret)

Task input for ipfs.add:
  source_url  (str)  — URL to fetch and add; mutually exclusive with content_b64
  content_b64 (str)  — base64-encoded bytes to add directly
  filename    (str)  — filename hint for IPFS, e.g. "document.webp" (default: "document")

Task output for ipfs.add:
  cid         (str)  — CIDv1 hash returned by Kubo /api/v0/add
  ipfs_url    (str)  — https://ipfs.etzhayyim.com/ipfs/{cid}
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import logging
import mimetypes
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx
from kotodama.langserver_compat import LangServerWorker

logger = logging.getLogger(__name__)

_IPFS_URL_DEFAULT = "https://ipfs.etzhayyim.com"
_IPFS_API_URL_DEFAULT = "http://kubo.ipfs.svc.cluster.local:5001"
_CHUNK_SIZE = 1024 * 1024

# AT Protocol TID: 64-bit microsecond timestamp encoded in s32 (base32 sortable).
# 13 chars, monotonically increasing, URL-safe.  Used as AT record rkey.
_S32_CHARS = "234567abcdefghijklmnopqrstuvwxyz"


def _generate_tid() -> str:
    ts = int(time.time() * 1_000_000)
    result = []
    for _ in range(13):
        result.append(_S32_CHARS[ts & 0x1F])
        ts >>= 5
    return "".join(reversed(result))


def _load_secret(env_var: str, keychain_service: str, keychain_account: str) -> str:
    val = os.environ.get(env_var, "").strip()
    if val:
        return val
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-s", keychain_service, "-a", keychain_account, "-w"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def _base_url() -> str:
    return os.environ.get("IPFS_URL", _IPFS_URL_DEFAULT).rstrip("/")


def _api_base_url() -> str:
    return os.environ.get("IPFS_API_URL", os.environ.get("IPFS_URL", _IPFS_API_URL_DEFAULT)).rstrip("/")


def _api_requires_hmac() -> bool:
    return "ipfs.etzhayyim.com" in _api_base_url()


def _hmac_key() -> str:
    return _load_secret("IPFS_HMAC", "etzhayyim.ipfs", "HMAC_KEY")


def _sign(body: bytes) -> str:
    key = _hmac_key()
    if not key:
        raise RuntimeError("IPFS_HMAC not configured; set env var or Keychain etzhayyim.ipfs/HMAC_KEY")
    return _hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


def _build_multipart(content: bytes, filename: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, boundary


async def add_content(content: bytes, filename: str = "document") -> str:
    """Add raw bytes to IPFS. Returns CID."""
    body, boundary = _build_multipart(content, filename)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if _api_requires_hmac():
        headers["X-etzhayyim-Ipfs-Auth"] = _sign(body)
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{_api_base_url()}/api/v0/add",
            params={"pin": "true", "cid-version": "1"},
            content=body,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["Hash"]


async def add_from_url(source_url: str, filename: Optional[str] = None) -> str:
    """Fetch URL and add content to IPFS. Returns CID."""
    async with httpx.AsyncClient(
        timeout=180,
        follow_redirects=True,
        headers={"User-Agent": "etzhayyim-ipfs-archiver/0.1"},
    ) as client:
        r = await client.get(source_url)
        r.raise_for_status()
        content = r.content
    fn = filename or source_url.rstrip("/").split("/")[-1] or "document"
    return await add_content(content, fn)


async def _download_to_temp(source_url: str, filename: str, max_bytes: int) -> tuple[Path, int, str]:
    suffix = Path(filename).suffix or ".bin"
    tmp = tempfile.NamedTemporaryFile(prefix="pdcolor-movie-", suffix=suffix, delete=False)
    path = Path(tmp.name)
    tmp.close()
    size = 0
    digest = hashlib.sha256()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, read=900.0),
            follow_redirects=True,
            headers={"User-Agent": "etzhayyim-pdcolor-ipfs-ingest/0.1"},
        ) as client:
            async with client.stream("GET", source_url) as resp:
                resp.raise_for_status()
                with path.open("wb") as out:
                    async for chunk in resp.aiter_bytes(_CHUNK_SIZE):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if max_bytes > 0 and size > max_bytes:
                            raise RuntimeError(f"movie source exceeds max_bytes={max_bytes}")
                        digest.update(chunk)
                        out.write(chunk)
        return path, size, digest.hexdigest()
    except Exception:
        path.unlink(missing_ok=True)
        raise


async def add_file_path(path: Path, filename: str, content_type: str = "") -> str:
    """Add a local file path to IPFS. Uses direct Kubo API when available."""
    content_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if _api_requires_hmac():
        return await add_content(path.read_bytes(), filename)
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=900.0)) as client:
        with path.open("rb") as fh:
            resp = await client.post(
                f"{_api_base_url()}/api/v0/add",
                params={"pin": "true", "cid-version": "1"},
                files={"file": (filename, fh, content_type)},
            )
        resp.raise_for_status()
        last_hash = ""
        for line in resp.text.splitlines():
            if not line.strip():
                continue
            obj = line.strip()
            try:
                last_hash = json.loads(obj)["Hash"]
            except Exception:
                continue
        if not last_hash:
            last_hash = resp.json()["Hash"]
        return last_hash


async def ingest_movie(
    source_url: str = "",
    source_ipfs_cid: str = "",
    filename: str = "movie",
    content_type: str = "",
    max_bytes: int = 0,
) -> dict:
    """Ingest a movie source into ipfs.etzhayyim.com and return durable source metadata."""
    if source_ipfs_cid:
        pinned = await pin_by_cid(source_ipfs_cid)
        return {
            "sourceIpfsCid": source_ipfs_cid,
            "sourceIpfsUrl": f"{_base_url()}/ipfs/{source_ipfs_cid}",
            "sourceIpfsPinned": pinned,
            "sourceByteSize": None,
            "sourceSha256": None,
        }
    if not source_url:
        raise ValueError("pdColor.ipfs.ingestMovie requires source_url or source_ipfs_cid")
    max_bytes = max_bytes or int(os.environ.get("PDCOLOR_MAX_MOVIE_BYTES", "0") or "0")
    safe_filename = filename or source_url.rstrip("/").split("/")[-1] or "movie"
    path, size, sha256 = await _download_to_temp(source_url, safe_filename, max_bytes)
    try:
        cid = await add_file_path(path, safe_filename, content_type)
    finally:
        path.unlink(missing_ok=True)
    return {
        "sourceIpfsCid": cid,
        "sourceIpfsUrl": f"{_base_url()}/ipfs/{cid}",
        "sourceIpfsPinned": True,
        "sourceByteSize": size,
        "sourceSha256": sha256,
    }


async def pin_by_cid(cid: str) -> bool:
    """Pin a CID already reachable by the IPFS node. Returns True on success."""
    empty = b""
    headers = {}
    if _api_requires_hmac():
        headers["X-etzhayyim-Ipfs-Auth"] = _sign(empty)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{_api_base_url()}/api/v0/pin/add",
            params={"arg": cid, "recursive": "true"},
            content=empty,
            headers=headers,
        )
        return resp.status_code == 200


def add_content_sync(content: bytes, filename: str, ipfs_url: str, hmac_key: str) -> Optional[str]:
    """Synchronous variant for non-async callers (e.g. evidence crawler). Returns CID or None."""
    import requests as _requests

    body, boundary = _build_multipart(content, filename)
    sig = _hmac.new(hmac_key.encode(), body, hashlib.sha256).hexdigest()
    try:
        resp = _requests.post(
            f"{ipfs_url.rstrip('/')}/api/v0/add",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-etzhayyim-Ipfs-Auth": sig,
            },
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["Hash"]
    except Exception as exc:
        logger.warning("ipfs add_content_sync failed for %s: %s", filename, exc)
        return None


async def _err_handler(exc: Exception, job: object) -> None:
    logger.error("ipfs_ingest task error: %s", exc)
    raise exc


def register(worker: LangServerWorker, timeout_ms: int = 3_600_000) -> None:
    """Register all IPFS Zeebe task handlers on *worker*."""

    @worker.task(task_type="ipfs.add", exception_handler=_err_handler, timeout_ms=timeout_ms)
    async def task_add(
        source_url: str = "",
        content_b64: str = "",
        filename: str = "document",
    ) -> dict:
        if content_b64:
            cid = await add_content(base64.b64decode(content_b64), filename)
        elif source_url:
            cid = await add_from_url(source_url, filename or None)
        else:
            raise ValueError("ipfs.add requires source_url or content_b64")
        return {"cid": cid, "ipfs_url": f"{_base_url()}/ipfs/{cid}"}

    @worker.task(task_type="ipfs.pinByCid", exception_handler=_err_handler, timeout_ms=timeout_ms)
    async def task_pin(cid: str) -> dict:
        ok = await pin_by_cid(cid)
        return {"pinned": ok}

    @worker.task(task_type="pdColor.ipfs.ingestMovie", exception_handler=_err_handler, timeout_ms=timeout_ms)
    async def task_pd_color_ingest_movie(
        source_url: str = "",
        source_ipfs_cid: str = "",
        sourceUrl: str = "",
        sourceIpfsCid: str = "",
        sourceFilename: str = "",
        sourceContentType: str = "",
        maxSourceBytes: int = 0,
        filename: str = "movie",
        content_type: str = "",
        max_bytes: int = 0,
    ) -> dict:
        return await ingest_movie(
            source_url or sourceUrl,
            source_ipfs_cid or sourceIpfsCid,
            filename if filename != "movie" else (sourceFilename or filename),
            content_type or sourceContentType,
            max_bytes or maxSourceBytes,
        )
