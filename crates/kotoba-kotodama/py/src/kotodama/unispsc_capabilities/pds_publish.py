"""AT PDS publish callback for the UNSPSC capability wrapper's belief store.

Per ADR-2605232100 Stage D + ADR-2605231400 (kotoba-datomic) §2 (kotoba-datomic-chain).
Wires the AtIpfsLocalBeliefStore's `publish: PublishCallback` injection
point so observations are committed to the atproto PDS in addition to the
local SQLite hot cache. Downstream of the PDS, the existing mst-projector +
ipfs-pinner + anchor-cron pipeline picks the records up and:

  PDS commit → MST root CID → IPFS cluster pin → Base L2 batch anchor.

Result: each of the 18,342 UNSPSC actors' observations become

  - public (PDS XRPC `com.atproto.repo.getRecord` from anywhere)
  - content-addressed (IPFS CID, fetchable from any pinner)
  - globally-anchored (Base L2 EtzhayyimAnchor batches every N commits)

instead of trapped in Pod-local `/tmp` emptyDir SQLite.

Failure-resistant: publish errors degrade to local-only — same behavior as
when `publish=None` (the pre-Stage-D baseline).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Callable

LOG = logging.getLogger("unispsc-capabilities-pds")


def _pds_endpoint() -> str | None:
    """Resolve the PDS XRPC endpoint from env."""
    return (
        os.environ.get("ETZ_PDS_ENDPOINT")
        or os.environ.get("PDS_ENDPOINT")
        or None
    )


def _service_token() -> str | None:
    """Bearer token for PDS writes — if unset the publish is anonymous and
    will be rejected by the PDS for protected NSIDs.

    Per ADR-2605231525 (no_server_key), the long-term goal is member-signed
    writes (Stage E). For Stage D MVP a service token is acceptable when
    the deployment.yaml is marked with the documented exemption comment
    (`no-server-key: read-only — pending Stage E …`).
    """
    return (
        os.environ.get("ETZ_PDS_SERVICE_TOKEN")
        or os.environ.get("PDS_SERVICE_TOKEN")
        or None
    )


def _build_create_record_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    return f"{base}/xrpc/com.atproto.repo.createRecord"


def make_publish_callback() -> Callable[[str, str, dict[str, Any]], str | None] | None:
    """Construct a `PublishCallback` if the PDS endpoint is configured,
    otherwise return None (caller passes None to the belief store and the
    store stays local-only).
    """
    endpoint = _pds_endpoint()
    if not endpoint:
        return None

    url = _build_create_record_url(endpoint)
    token = _service_token()
    # Cloudflare WAF in front of pds.etzhayyim.com blocks Python urllib's
    # default User-Agent (returns HTTP 403 with CF error code 1010).
    # Identify ourselves as the religious-corp organism — readable + auditable.
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "etzhayyim-organism/0.1.0 (+https://etzhayyim.com)",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def publish(agent_did: str, collection_nsid: str, record: dict[str, Any]) -> str | None:
        body = json.dumps(
            {
                "repo": agent_did,
                "collection": collection_nsid,
                "record": record,
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            LOG.warning(
                "PDS createRecord %s/%s failed HTTP %d: %s",
                agent_did,
                collection_nsid,
                e.code,
                e.read()[:200] if e.fp else "",
            )
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            LOG.warning(
                "PDS createRecord %s/%s network failure: %s",
                agent_did,
                collection_nsid,
                e,
            )
            return None
        uri = payload.get("uri")
        if not uri:
            LOG.warning(
                "PDS createRecord %s/%s returned no uri (payload keys=%s)",
                agent_did,
                collection_nsid,
                list(payload.keys())[:5],
            )
            return None
        return str(uri)

    return publish
