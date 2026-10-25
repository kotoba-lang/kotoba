"""Read-only AT Protocol PDS helpers."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
import urllib.request
from typing import Any


def _endpoint() -> str:
    return os.environ.get("ETZHAYYIM_PDS_URL", "https://pds.etzhayyim.com").rstrip("/")


async def get_record(*, uri: str) -> dict[str, Any]:
    """Resolve an ``at://did/collection/rkey`` record through XRPC."""
    if not uri.startswith("at://"):
        raise ValueError("record URI must start with at://")
    repo, collection, rkey = uri[5:].split("/", 2)
    query = urllib.parse.urlencode({"repo": repo, "collection": collection, "rkey": rkey})
    url = f"{_endpoint()}/xrpc/com.atproto.repo.getRecord?{query}"

    def fetch() -> dict[str, Any]:
        with urllib.request.urlopen(url, timeout=30) as response:  # nosec: B310 - operator PDS URL
            return json.load(response)

    return await asyncio.to_thread(fetch)
