"""kyber Lead Discovery actor — OSS developer + Japan SMB lead gen.

Runs every 6h. Targets:
  - GitHub: stargazers of open-kyber + related OSS ERP/accounting repos
  - HN Algolia: stories mentioning open-source ERP / accounting / AT Protocol
  - Reddit: r/selfhosted, r/Entrepreneur, r/accounting
  - Dev.to: tags oss, erp, accounting, atprotocol

Pipeline: search_github → search_hn → search_reddit → search_devto → filter_new → ingest → report

Env vars:
  GITHUB_TOKEN  — GitHub API token (optional; rate limit 60→5000 req/h)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from lg_kyber.db import execute, fetch

_log = logging.getLogger(__name__)

_GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

_GH_REPOS = [
    "frappe/frappe",
    "frappe/erpnext",
    "odoo/odoo",
    "akaunting/akaunting",
    "invoiceninja/invoiceninja",
]
_HN_KEYWORDS = [
    "open source ERP Japan",
    "open source accounting SMB",
    "AT Protocol enterprise",
    "self hosted invoicing",
    "frappe erpnext alternative",
]
_REDDIT_SUBREDDITS = ["selfhosted", "Entrepreneur", "smallbusiness"]
_REDDIT_KEYWORDS = ["open source ERP", "accounting software", "invoicing"]
_DEVTO_TAGS = ["oss", "erp", "accounting", "atprotocol"]
_MAX_PER_SOURCE = 30


class LeadDiscoveryState(TypedDict, total=False):
    run_date: str
    gh_leads: list[dict]
    hn_leads: list[dict]
    reddit_leads: list[dict]
    devto_leads: list[dict]
    new_leads: list[dict]
    ingested: int
    summary: str


def _http_get(url: str, headers: dict | None = None) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _domain_from_url(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""


def _lead_id(source: str, ref: str) -> str:
    return str(uuid.UUID(hashlib.sha256(f"{source}:{ref}".encode()).hexdigest()[:32]))


async def search_github(state: LeadDiscoveryState) -> LeadDiscoveryState:
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if _GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {_GITHUB_TOKEN}"
    leads: list[dict] = []
    per_repo = max(1, _MAX_PER_SOURCE // len(_GH_REPOS))
    for repo in _GH_REPOS:
        try:
            url = f"https://api.github.com/repos/{repo}/stargazers?per_page={per_repo}&page=1"
            users = _http_get(url, headers)
            for user in (users or [])[:per_repo]:
                login = user.get("login", "")
                if not login:
                    continue
                try:
                    profile = _http_get(f"https://api.github.com/users/{login}", headers)
                    email = (profile.get("email") or "").strip()
                    company = (profile.get("company") or "").strip().lstrip("@")
                    bio = (profile.get("bio") or "")[:120]
                except Exception:
                    email = company = bio = ""
                leads.append({
                    "vertex_id": _lead_id("gh", login),
                    "source": "gh-discovery",
                    "domain": f"github.com/{login}",
                    "contact_email": email,
                    "company": company or login,
                    "signal": f"GitHub star: {repo} | bio: {bio}",
                    "tech_stack": "oss",
                    "outreach_status": "new",
                })
        except Exception as e:
            _log.warning("[kyber.lead_discovery] GitHub repo=%r error: %s", repo, e)
    _log.info("[kyber.lead_discovery] GitHub: %d leads", len(leads))
    return {**state, "run_date": datetime.now(timezone.utc).date().isoformat(), "gh_leads": leads}


async def search_hn(state: LeadDiscoveryState) -> LeadDiscoveryState:
    since_ts = int((datetime.now(timezone.utc) - timedelta(hours=25)).timestamp())
    leads: list[dict] = []
    for kw in _HN_KEYWORDS:
        try:
            q = urllib.parse.quote(kw)
            url = (
                f"https://hn.algolia.com/api/v1/search_by_date"
                f"?query={q}&tags=story&numericFilters=created_at_i>{since_ts}&hitsPerPage=5"
            )
            data = _http_get(url)
            for hit in (data.get("hits") or [])[:3]:
                story_url = hit.get("url") or ""
                domain = _domain_from_url(story_url)
                if not domain:
                    continue
                leads.append({
                    "vertex_id": _lead_id("hn", hit.get("objectID", "")),
                    "source": "hn-discovery",
                    "domain": domain,
                    "contact_email": "",
                    "company": domain,
                    "signal": f"HN score={hit.get('points', 0)}: {hit.get('title', '')[:120]}",
                    "tech_stack": "unknown",
                    "outreach_status": "new",
                })
        except Exception as e:
            _log.warning("[kyber.lead_discovery] HN kw=%r error: %s", kw, e)
    _log.info("[kyber.lead_discovery] HN: %d leads", len(leads))
    return {**state, "hn_leads": leads}


async def search_reddit(state: LeadDiscoveryState) -> LeadDiscoveryState:
    leads: list[dict] = []
    seen: set[str] = set()
    headers = {"User-Agent": "kyber-lead-discovery/1.0 (bot; contact@etzhayyim.com)"}
    for sub in _REDDIT_SUBREDDITS:
        for kw in _REDDIT_KEYWORDS[:1]:
            try:
                q = urllib.parse.quote(kw)
                url = (
                    f"https://www.reddit.com/r/{sub}/search.json"
                    f"?q={q}&sort=new&limit=5&t=day&restrict_sr=1"
                )
                data = _http_get(url, headers)
                posts = (data.get("data") or {}).get("children") or []
                for post in posts[:3]:
                    pd = post.get("data") or {}
                    post_url = pd.get("url") or ""
                    domain = _domain_from_url(post_url)
                    if not domain or "reddit.com" in domain:
                        domain = f"reddit.com/user/{pd.get('author', 'unknown')}"
                    permalink = f"https://reddit.com{pd.get('permalink', '')}"
                    if permalink in seen:
                        continue
                    seen.add(permalink)
                    leads.append({
                        "vertex_id": _lead_id("reddit", pd.get("id", permalink)),
                        "source": "reddit-discovery",
                        "domain": domain,
                        "contact_email": "",
                        "company": pd.get("author", ""),
                        "signal": f"r/{sub} score={pd.get('score', 0)}: {pd.get('title', '')[:120]}",
                        "tech_stack": "unknown",
                        "outreach_status": "new",
                    })
            except Exception as e:
                _log.warning("[kyber.lead_discovery] Reddit sub=%r error: %s", sub, e)
    _log.info("[kyber.lead_discovery] Reddit: %d leads", len(leads))
    return {**state, "reddit_leads": leads}


async def search_devto(state: LeadDiscoveryState) -> LeadDiscoveryState:
    leads: list[dict] = []
    seen: set[str] = set()
    for tag in _DEVTO_TAGS:
        try:
            url = f"https://dev.to/api/articles?tag={tag}&per_page=5&top=1"
            articles = _http_get(url)
            for art in (articles or [])[:3]:
                art_id = str(art.get("id", ""))
                if art_id in seen:
                    continue
                seen.add(art_id)
                user = art.get("user") or {}
                username = user.get("username", "")
                domain = f"dev.to/{username}" if username else "dev.to"
                leads.append({
                    "vertex_id": _lead_id("devto", art_id),
                    "source": "devto-discovery",
                    "domain": domain,
                    "contact_email": "",
                    "company": user.get("name", username),
                    "signal": (
                        f"dev.to tag={tag} reactions={art.get('positive_reactions_count', 0)}: "
                        f"{art.get('title', '')[:120]}"
                    ),
                    "tech_stack": "unknown",
                    "outreach_status": "new",
                })
        except Exception as e:
            _log.warning("[kyber.lead_discovery] Dev.to tag=%r error: %s", tag, e)
    _log.info("[kyber.lead_discovery] Dev.to: %d leads", len(leads))
    return {**state, "devto_leads": leads}


async def filter_new(state: LeadDiscoveryState) -> LeadDiscoveryState:
    all_leads = (
        (state.get("gh_leads") or [])
        + (state.get("hn_leads") or [])
        + (state.get("reddit_leads") or [])
        + (state.get("devto_leads") or [])
    )
    if not all_leads:
        return {**state, "new_leads": []}
    seen: set[str] = set()
    deduped: list[dict] = []
    for lead in all_leads:
        key = lead.get("vertex_id", "")
        if key and key not in seen:
            seen.add(key)
            deduped.append(lead)
    if deduped:
        try:
            ids = [l["vertex_id"] for l in deduped]
            placeholders = ", ".join(f"${i+1}" for i in range(len(ids)))
            rows = await fetch(
                f"SELECT vertex_id FROM vertex_kyber_lead WHERE vertex_id IN ({placeholders}) LIMIT {len(ids)}",
                *ids,
            )
            existing = {r["vertex_id"] for r in rows}
            deduped = [l for l in deduped if l["vertex_id"] not in existing]
        except Exception as e:
            _log.warning("[kyber.lead_discovery] filter DB check failed: %s", e)
    _log.info("[kyber.lead_discovery] new leads after filter: %d", len(deduped))
    return {**state, "new_leads": deduped}


async def ingest(state: LeadDiscoveryState) -> LeadDiscoveryState:
    new_leads = state.get("new_leads") or []
    ingested = 0
    for lead in new_leads:
        try:
            await execute(
                """
                INSERT INTO vertex_kyber_lead
                  (vertex_id, org_did, source, domain, contact_email, company,
                   signal, tech_stack, outreach_status, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                """,
                lead["vertex_id"],
                "did:web:kyber.etzhayyim.com",
                lead.get("source", "discovery"),
                lead.get("domain", ""),
                lead.get("contact_email", ""),
                lead.get("company", ""),
                lead.get("signal", ""),
                lead.get("tech_stack", "unknown"),
                "new",
                datetime.now(timezone.utc),
            )
            ingested += 1
        except Exception as e:
            _log.warning("[kyber.lead_discovery] insert failed: %s", e)
    _log.info("[kyber.lead_discovery] ingested %d new leads", ingested)
    return {**state, "ingested": ingested}


async def report(state: LeadDiscoveryState) -> LeadDiscoveryState:
    run_date = state.get("run_date", "")
    ingested = state.get("ingested", 0)
    gh = len(state.get("gh_leads") or [])
    hn = len(state.get("hn_leads") or [])
    reddit = len(state.get("reddit_leads") or [])
    devto = len(state.get("devto_leads") or [])
    summary = (
        f"[{run_date}] kyber lead_discovery: GitHub={gh} HN={hn} Reddit={reddit} Dev.to={devto}"
        f" → {ingested}件新規ingested"
    )
    if ingested > 0:
        try:
            await execute(
                """
                INSERT INTO vertex_kyber_outbox
                  (vertex_id, org_did, kind, subject, body_text,
                   recipient_email, status, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """,
                str(uuid.uuid4()),
                "did:web:kyber.etzhayyim.com",
                "lead-discovery-report",
                f"kyber Lead Discovery {run_date}",
                summary,
                "jun@etzhayyim.group",
                "queued-no-recipient",
                datetime.now(timezone.utc),
            )
        except Exception as e:
            _log.warning("[kyber.lead_discovery] report insert failed: %s", e)
    _log.info("[kyber.lead_discovery] %s", summary)
    return {**state, "summary": summary}


def _build() -> Any:
    sg = StateGraph(LeadDiscoveryState)
    sg.add_node("search_github", search_github)
    sg.add_node("search_hn", search_hn)
    sg.add_node("search_reddit", search_reddit)
    sg.add_node("search_devto", search_devto)
    sg.add_node("filter_new", filter_new)
    sg.add_node("ingest", ingest)
    sg.add_node("report", report)
    sg.add_edge(START, "search_github")
    sg.add_edge("search_github", "search_hn")
    sg.add_edge("search_hn", "search_reddit")
    sg.add_edge("search_reddit", "search_devto")
    sg.add_edge("search_devto", "filter_new")
    sg.add_edge("filter_new", "ingest")
    sg.add_edge("ingest", "report")
    sg.add_edge("report", END)
    return sg.compile()


GRAPH = _build()
