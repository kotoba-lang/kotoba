"""
Domain coverage expansion — K8s LangGraph CronJob implementation.

Ports expandDomainCoverage() from 50-infra/cloudflare/workers/atproto/src/app.ts
after ADR-2605111200 removed env.HYPERDRIVE from CF Workers.

One domain per invocation:
  1. Gap query: mv_cc_domain_coverage LEFT JOIN vertex_app → next unregistered domain
  2. Fallback: static candidate list
  3. Context: CC CDX → WAT range → site.etzhayyim.com crawlPage → gyotaku.etzhayyim.com snapshots
  4. LLM classify: description + sector + knowledge_edges (call_tier "structured")
  5. PDS writes: profile, app, knowledgeEdge (putRecord); feed post (createRecord)

Env:

  ATPROTO_BASE_URL    — PDS gateway (default: https://atproto.etzhayyim.com)
  PDS_INTERNAL_TOKEN  — x-kotoba-kotodama-verified header value (default: "true")
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import math
import os
import time
from typing import Any

import aiohttp

from kotodama import llm as llm_module
from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("domain_expansion")

ATPROTO_BASE = os.environ.get("ATPROTO_BASE_URL", "https://atproto.etzhayyim.com")
# PDS_INTERNAL_TOKEN is the HMAC secret (from pds-service-auth-mint k8s secret)
# used to sign x-etzhayyim-internal-hmac alongside x-kotoba-kotodama-verified: true.
# ADR-0022 Amendment A2: HMAC-SHA256(METHOD:pathname:minute_epoch, secret).
_PDS_HMAC_SECRET = os.environ.get("PDS_INTERNAL_TOKEN", "")


def _pds_internal_headers(method: str, pathname: str) -> dict[str, str]:
    """Build x-kotoba-kotodama-verified + x-etzhayyim-internal-hmac headers for PDS auth."""
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "x-kotoba-kotodama-verified": "true",
    }
    if _PDS_HMAC_SECRET:
        minute_epoch = math.floor(time.time() / 60)
        signing_input = f"{method.upper()}:{pathname}:{minute_epoch}"
        mac = hmac.new(
            _PDS_HMAC_SECRET.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        mac_b64url = base64.urlsafe_b64encode(mac).rstrip(b"=").decode()
        headers["x-etzhayyim-internal-hmac"] = mac_b64url
    return headers

_STATIC_CANDIDATES = [
    {"domain": "states",           "nanoid": "st4t3s01"},
    {"domain": "treaty",           "nanoid": "tr3aty01"},
    {"domain": "blockchain",       "nanoid": "bl0ckch1"},
    {"domain": "religious",        "nanoid": "r3lgus01"},
    {"domain": "customary",        "nanoid": "cst0m4ry"},
    {"domain": "communities",      "nanoid": "2tqvrutp"},
    {"domain": "ethics",           "nanoid": "eth1cs01"},
    {"domain": "industry-standard","nanoid": "indstd01"},
    {"domain": "tradition",        "nanoid": "trdtn001"},
    {"domain": "autorace",         "nanoid": "4ut0r4c3"},
    {"domain": "keirin",           "nanoid": "k31r1njp"},
    {"domain": "kyotei",           "nanoid": "qv8yed1k"},
    {"domain": "keiba",            "nanoid": "k31b4jp0"},
    {"domain": "hanrei",           "nanoid": "h4nr31jp"},
]


async def _gap_query() -> str:
    """Return first domain in mv_cc_domain_coverage not yet registered in vertex_app."""
    client = get_kotoba_client()
    # R0: Datalog escape hatch for LEFT JOIN and string manipulation in WHERE clause.
    datalog_query = """
        [:find ?domain
         :where
           [?c :mv_cc_domain_coverage/domain ?domain]
           (not= ?domain "")
           (not= ?domain nil)
           [(clojure.string/replace ?domain "." "-") ?domain-did-part]
           [(str "did:web:" ?domain-did-part ".etzhayyim.com") ?did]
           (not [?a :vertex_app/did ?did])]"""
    result = client.q(datalog_query, limit=1)
    return str(result[0][0]) if result else ""


async def _registered_dids() -> set[str]:
    client = get_kotoba_client()
    # R0: Datalog escape hatch to fetch all DIDs from vertex_app with a limit.
    datalog_query = """
        [:find ?did
         :where
           [?a :vertex_app/did ?did]
         :limit 5000]"""
    results = client.q(datalog_query)
    return {str(r[0]) for r in results}


async def _fetch_cc_context(session: aiohttp.ClientSession, domain: str) -> str:
    """Layer 1: Common Crawl CDX → WAT S3 range."""
    try:
        url = f"https://index.commoncrawl.org/CC-MAIN-2025-51-index?url={domain}/*&output=json&limit=5"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if not resp.ok:
                return ""
            text = await resp.text()
        lines = [l for l in text.strip().splitlines() if l]
        records: list[dict] = []
        for l in lines:
            try:
                records.append(json.loads(l))
            except Exception:
                pass
        ctx = ""
        for rec in records[:3]:
            if not rec.get("filename") or rec.get("offset") is None:
                continue
            offset = int(rec["offset"])
            length = int(rec["length"])
            try:
                async with session.get(
                    f"https://data.commoncrawl.org/{rec['filename']}",
                    headers={"Range": f"bytes={offset}-{offset + length - 1}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as wr:
                    if wr.ok or wr.status == 206:
                        ctx += (await wr.text())[:300] + "\n"
            except Exception:
                pass
        return ctx
    except Exception:
        return ""


async def _fetch_site_context(session: aiohttp.ClientSession, domain: str, slug: str) -> str:
    """Layer 2: site.etzhayyim.com crawlPage fallback."""
    try:
        async with session.post(
            "https://site.etzhayyim.com/xrpc/com.etzhayyim.apps.site.crawlPage",
            json={"url": f"https://{domain}", "topics": [slug]},
            headers={"Content-Type": "application/json", "x-kotoba-kotodama-verified": "true"},
            timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            if not resp.ok:
                return ""
            d = await resp.json()
        return str(d.get("markdown") or d.get("wet") or "")[:600]
    except Exception:
        return ""


async def _fetch_gyotaku_context(session: aiohttp.ClientSession, domain: str) -> str:
    """Layer 3: gyotaku.etzhayyim.com searchSnapshots fallback."""
    try:
        async with session.post(
            "https://gyotaku.etzhayyim.com/xrpc/com.etzhayyim.apps.gyotaku.searchSnapshots",
            json={"domain": domain, "limit": 3},
            headers={"Content-Type": "application/json", "x-kotoba-kotodama-verified": "true"},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if not resp.ok:
                return ""
            d = await resp.json()
        snaps = d.get("snapshots") or []
        return "\n".join(f"{s.get('title','')}: {s.get('extract','')}" for s in snaps)[:600]
    except Exception:
        return ""


def _llm_classify(domain: str, nanoid: str, ctx: str) -> tuple[str, list[dict]]:
    """Sync LLM call — wrapped in asyncio.to_thread at call site."""
    ctx_block = f"\nData from Common Crawl / site.etzhayyim.com:\n{ctx[:400]}" if ctx else ""
    system = "You are a domain knowledge architect. Output ONLY valid JSON."
    user = (
        f'Classify and describe domain "{domain}".'
        f"{ctx_block}\n"
        f'Output JSON: {{"domain_summary":"2-3 sentence description",'
        f'"sector":"one of: technology|government|legal|finance|healthcare|education|media|science|commerce|infrastructure|culture|security",'
        f'"knowledge_edges":[{{"from":"{nanoid}","relation":"EXPERTISE_IN|SERVES|MONITORS|PRODUCES","to":"concept"}}]}}'
    )
    try:
        result = llm_module.call_tier(
            "structured", system, user, max_tokens=512, temperature=0.3
        )
        parsed = json.loads(result["content"])
        description = parsed.get("domain_summary") or f"{domain} domain"
        edges = parsed.get("knowledge_edges") or []
        if not isinstance(edges, list):
            edges = []
        return description, edges
    except Exception as exc:
        LOG.warning("LLM classify failed for %s: %s", domain, exc)
        return f"{domain} domain", []


def _llm_post_text(domain: str, description: str, edges: list[dict]) -> str:
    """Sync LLM call — wrapped in asyncio.to_thread at call site."""
    knowledge_str = ", ".join(e.get("to", "") for e in edges if e.get("to")) if edges else ""
    system = (
        "You are an AI agent announcing a new domain registration on a social feed. "
        "Write 1-2 sentences. Be specific and factual. No hashtags, no emojis."
    )
    user = (
        f'Write a social post for the domain "{domain}" ({description}).'
        + (f" Knowledge: {knowledge_str}" if knowledge_str else "")
    )
    try:
        result = llm_module.call_tier("fast", system, user, max_tokens=128, temperature=0.7)
        text = (result.get("content") or "").strip()
        return text[:300] if len(text) > 10 else f"{domain} domain registered."
    except Exception:
        return f"{domain} domain registered."


async def _pds_put_record(
    session: aiohttp.ClientSession,
    repo: str,
    collection: str,
    rkey: str,
    record: dict[str, Any],
) -> None:
    pathname = "/xrpc/com.atproto.repo.putRecord"
    payload = {"repo": repo, "collection": collection, "rkey": rkey, "record": record}
    async with session.post(
        f"{ATPROTO_BASE}{pathname}",
        json=payload,
        headers=_pds_internal_headers("POST", pathname),
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        body = await resp.json()
        if not resp.ok:
            raise RuntimeError(f"putRecord {collection}/{rkey} failed {resp.status}: {body}")


async def _pds_create_record(
    session: aiohttp.ClientSession,
    repo: str,
    collection: str,
    record: dict[str, Any],
) -> str:
    pathname = "/xrpc/com.atproto.repo.createRecord"
    payload = {"repo": repo, "collection": collection, "record": record}
    async with session.post(
        f"{ATPROTO_BASE}{pathname}",
        json=payload,
        headers=_pds_internal_headers("POST", pathname),
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        body = await resp.json()
        if not resp.ok:
            raise RuntimeError(f"createRecord {collection} failed {resp.status}: {body}")
        return str(body.get("uri", ""))


async def expand_one_domain() -> dict[str, Any]:
    """
    Main entry point. Finds one unregistered domain and expands it.
    Returns dict: {ok, domain, app_did, knowledge_edges, post_written, error?}
    """
    try:
        target_domain = await _gap_query()

        if not target_domain:
            registered = await _registered_dids()
            candidate = next(
                (c for c in _STATIC_CANDIDATES if f"did:web:{c['domain']}.etzhayyim.com" not in registered),
                None,
            )
            if not candidate:
                LOG.info("all static domains registered — nothing to do")
                return {"ok": True, "domain": "", "app_did": "", "knowledge_edges": 0, "post_written": False}
            target_domain = candidate["domain"]

        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in target_domain.lower())
        nanoid_candidate = next(
            (c["nanoid"] for c in _STATIC_CANDIDATES if c["domain"] == target_domain), None
        )
        nanoid = nanoid_candidate or (slug.replace("-", "")[:8] or slug[:8])
        app_did = f"did:web:{slug}.etzhayyim.com"
        now_ms = int(time.time() * 1000)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        async with aiohttp.ClientSession() as session:
            # Context fetch (layers 1→2→3)
            cc_ctx = await _fetch_cc_context(session, target_domain)
            if not cc_ctx:
                cc_ctx = await _fetch_site_context(session, target_domain, slug)
            if not cc_ctx:
                cc_ctx = await _fetch_gyotaku_context(session, target_domain)

            # LLM classify
            description, edges = await asyncio.to_thread(_llm_classify, target_domain, nanoid, cc_ctx)

            # Profile
            await _pds_put_record(
                session, app_did, "app.bsky.actor.profile", "self",
                {
                    "did": app_did, "displayName": target_domain, "description": description,
                    "nanoid": nanoid, "performerType": "service", "sensitivity": "public",
                    "collection": "app.bsky.actor.profile", "repo": app_did,
                    "sensitivityOrd": "0", "createdAt": str(now_ms), "updatedAt": str(now_ms),
                },
            )

            # App record
            await _pds_put_record(
                session, app_did, "com.etzhayyim.actor.app", nanoid,
                {
                    "nanoid": nanoid, "displayName": target_domain, "description": description,
                    "did": app_did, "performerType": "service", "contentMode": "timeline",
                    "status": "active", "deployAt": now_ms,
                    "collection": "com.etzhayyim.actor.app", "repo": app_did,
                    "sensitivityOrd": "0", "updatedAt": str(now_ms),
                },
            )

            # Knowledge edges (up to 5)
            edge_count = 0
            for edge in edges[:5]:
                if not edge.get("to"):
                    continue
                rkey = f"ke-{nanoid}-{edge['to']}"
                rkey = "".join(c if c.isalnum() or c == "-" else "-" for c in rkey)[:64]
                try:
                    await _pds_put_record(
                        session, app_did, "com.etzhayyim.actor.knowledgeEdge", rkey,
                        {
                            "from": nanoid,
                            "relation": edge.get("relation") or "EXPERTISE_IN",
                            "to": edge["to"],
                            "createdAt": now_iso,
                        },
                    )
                    edge_count += 1
                except Exception as exc:
                    LOG.warning("knowledgeEdge %s failed: %s", rkey, exc)

            # Social post
            post_text = await asyncio.to_thread(_llm_post_text, target_domain, description, edges)
            post_uri = await _pds_create_record(
                session, app_did, "app.bsky.feed.post",
                {"$type": "app.bsky.feed.post", "text": post_text, "createdAt": now_iso},
            )

            # Capabilities update
            capabilities = [
                e["to"] for e in edges
                if e.get("relation") in ("EXPERTISE_IN", "SERVES", "PRODUCES") and e.get("to")
            ][:5]
            if capabilities:
                try:
                    await _pds_put_record(
                        session, app_did, "com.etzhayyim.actor.app", nanoid,
                        {
                            "nanoid": nanoid, "displayName": target_domain, "description": description,
                            "did": app_did, "performerType": "service", "contentMode": "timeline",
                            "status": "active", "deployAt": now_ms,
                            "capabilitiesJson": json.dumps(capabilities),
                            "collection": "com.etzhayyim.actor.app", "repo": app_did,
                            "sensitivityOrd": "0", "updatedAt": str(now_ms),
                        },
                    )
                except Exception as exc:
                    LOG.warning("capabilities update failed for %s: %s", app_did, exc)

        LOG.info(
            "registered %s (%s, %d edges, post=%s)",
            app_did, target_domain, edge_count, post_uri[:60] if post_uri else "none",
        )
        return {
            "ok": True,
            "domain": target_domain,
            "app_did": app_did,
            "knowledge_edges": edge_count,
            "post_written": bool(post_uri),
        }

    except Exception as exc:
        msg = str(exc)[:500]
        LOG.exception("expand_one_domain failed: %s", msg)
        return {"ok": False, "domain": "", "app_did": "", "knowledge_edges": 0, "post_written": False, "error": msg}
