"""HTTP client for a kotoba node's XRPC surface.

This is the data path that every ``.remote()`` ultimately lands on. Two XRPC
endpoints are wrapped:

  * ``com.etzhayyim.apps.kotoba.infer.run``  — prompt → completion. Runs on the
    node's inference engine, which on a religious-corp deployment is the
    **Murakumo distributed fleet** (Mac mini cluster + EVO-X2 LAN inference pod,
    ADR-2605202345 / ADR-2605215000) reached via the LiteLLM gateway.
  * ``com.etzhayyim.apps.kotoba.invoke.run`` — dispatch a pre-built WASM
    component (``program_cid``) with a CBOR context. Runs the function *body*
    on the node (kotoba-node world).

Auth mirrors ``graph_auth::require_operator_auth`` on the node:
  * ``Authorization: Bearer <jwt>`` whose ``sub`` is the operator DID.
  * ``x-internal-trust: <secret>`` — only enforced when the node sets
    ``KOTOBA_INTERNAL_SECRET`` (i.e. direct LAN/pod access without the edge
    Worker). Harmless to send when unset.

Transport is plain stdlib ``urllib`` so the inference path has zero third-party
dependencies. A ``transport`` hook is exposed for tests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional

from ._errors import RemoteError

INFER_RUN_NSID = "com.etzhayyim.apps.kotoba.infer.run"
INVOKE_RUN_NSID = "com.etzhayyim.apps.kotoba.invoke.run"

# (nsid, body_dict, headers) -> (status_code, response_text)
Transport = Callable[[str, Dict[str, Any], Dict[str, str]], "tuple[int, str]"]


class KotobaNodeClient:
    """Thin XRPC client for one kotoba node."""

    def __init__(
        self,
        base_url: str,
        *,
        token: Optional[str] = None,
        internal_secret: Optional[str] = None,
        timeout: float = 120.0,
        transport: Optional[Transport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.internal_secret = internal_secret
        self.timeout = timeout
        self._transport = transport or self._urllib_transport

    # ── public XRPC calls ────────────────────────────────────────────────

    def infer(self, prompt: str, max_new_tokens: Optional[int] = None) -> str:
        """POST infer.run — returns the generated completion text."""
        body: Dict[str, Any] = {"prompt": prompt}
        if max_new_tokens is not None:
            body["max_new_tokens"] = int(max_new_tokens)
        resp = self._post(INFER_RUN_NSID, body)
        return resp.get("output", "")

    def invoke(
        self,
        program_cid: str,
        ctx_b64: str,
        *,
        program_type: str = "wasm-node",
        agent_did: str = "",
        wasm_b64: Optional[str] = None,
        graph_cid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST invoke.run — dispatch a WASM component. Returns the raw response
        (``output_b64``, ``gas_used``, ``journal_cids`` …)."""
        body: Dict[str, Any] = {
            "program_cid": program_cid,
            "program_type": program_type,
            "agent_did": agent_did,
            "ctx_b64": ctx_b64,
        }
        if wasm_b64 is not None:
            body["wasm_b64"] = wasm_b64
        if graph_cid is not None:
            body["graph_cid"] = graph_cid
        return self._post(INVOKE_RUN_NSID, body)

    # ── internals ────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.internal_secret:
            h["x-internal-trust"] = self.internal_secret
        return h

    def _post(self, nsid: str, body: Dict[str, Any]) -> Dict[str, Any]:
        status, text = self._transport(nsid, body, self._headers())
        if not (200 <= status < 300):
            raise RemoteError(status, text, nsid)
        try:
            return json.loads(text) if text else {}
        except json.JSONDecodeError:
            return {"output": text}

    def _urllib_transport(
        self, nsid: str, body: Dict[str, Any], headers: Dict[str, str]
    ) -> "tuple[int, str]":
        url = f"{self.base_url}/xrpc/{nsid}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")
