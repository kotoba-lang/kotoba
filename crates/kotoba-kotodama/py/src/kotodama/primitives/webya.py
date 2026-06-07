"""
webya.etzhayyim.com — Zeebe task handlers (ADR-0056 + ADR-2605080200).

Task types registered under ZEEBE_WORKER_PROFILE=webya:
  webya.domain.provision          CF for SaaS Custom Hostname 発行
  webya.domain.checkAllPending    SSL ステータス一括確認 (R/PT30M BPMN)
  webya.seo.auditAllSites         週次 SEO 監査 (cron BPMN)

LangGraph-routed tasks (Zeebe 非実行 — dispatcher が直接 POST /runs):
  webya.site.generate             → assistant_id=webya_create_site
  webya.site.revise               → assistant_id=webya_revise_site

Coverage / query handlers:
  task_webya_get_site
  task_webya_list_sites
  task_webya_get_site_preview
  task_webya_coverage
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from typing import Any
from datetime import datetime, timezone

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama import llm

LOG = logging.getLogger(__name__)

# CF API settings (from env / K8s Secret)
_CF_API_TOKEN   = os.environ.get("CF_API_TOKEN", "")
_CF_ZONE_ID     = os.environ.get("WEBYA_CF_ZONE_ID", "")
_CF_PROXY_ORIGIN = "proxy-webya.etzhayyim.com"

ACTOR_DID = "did:web:webya.etzhayyim.com"


# ── Helpers ────────────────────────────────────────────────────────────────────




def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _slug_from_name(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower())
    s = re.sub(r"[\s_]+", "-", s)
    return s[:32].strip("-") or "site"


# ── task: webya.domain.provision ─────────────────────────────────────────────

async def task_webya_domain_provision(**kwargs: Any) -> dict[str, Any]:
    """CF for SaaS Custom Hostname を発行する。"""
    import httpx

    site_id = str(kwargs.get("siteId") or kwargs.get("site_id") or "")
    domain  = str(kwargs.get("domain") or "").strip().lower()

    if not site_id or not domain:
        return {"ok": False, "error": "siteId and domain are required"}

    if not _CF_API_TOKEN or not _CF_ZONE_ID:
        return {"ok": False, "error": "CF_API_TOKEN or WEBYA_CF_ZONE_ID not configured"}

    now = _now()
    domain_id = f"dom-{hashlib.sha256(f'{site_id}:{domain}'.encode()).hexdigest()[:16]}"
    vertex_id = f"at://{ACTOR_DID}/com.etzhayyim.apps.webya.domain/{domain_id}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.cloudflare.com/client/v4/zones/{_CF_ZONE_ID}/custom_hostnames",
                headers={"Authorization": f"Bearer {_CF_API_TOKEN}", "Content-Type": "application/json"},
                json={
                    "hostname": domain,
                    "ssl": {"method": "txt", "type": "dv", "settings": {"min_tls_version": "1.2"}},
                    "custom_origin_server": _CF_PROXY_ORIGIN,
                },
            )
        data = resp.json()
        if not data.get("success"):
            return {"ok": False, "error": str(data.get("errors", "CF API error"))}

        result = data["result"]
        cf_hostname_id = result["id"]
        ssl = result.get("ssl", {})
        verification = ssl.get("txt_name", ""), ssl.get("txt_value", "")
        txt_name, txt_value = verification

        get_kotoba_client().insert_row(
            "vertex_webya_domain",
            {
                "vertex_id": vertex_id,
                "domain_id": domain_id,
                "site_id": site_id,
                "domain": domain,
                "cf_hostname_id": cf_hostname_id,
                "ssl_status": "pending",
                "ownership_verified": False,
                "dns_cname_target": _CF_PROXY_ORIGIN,
                "verification_txt_name": txt_name,
                "verification_txt_value": txt_value,
                "provisioned_at": now,
            },
        )
        get_kotoba_client().insert_row(
            "vertex_webya_site",
            {
                "site_id": site_id,
                "custom_domain": domain,
                "cf_custom_hostname_id": cf_hostname_id,
            },
        )

        LOG.info("domain.provision ok site_id=%s domain=%s cf_id=%s", site_id, domain, cf_hostname_id)
        return {
            "ok":           True,
            "cfHostnameId": cf_hostname_id,
            "cnameTarget":  _CF_PROXY_ORIGIN,
            "txtName":      txt_name,
            "txtValue":     txt_value,
            "sslStatus":    "pending",
        }

    except Exception as exc:
        LOG.error("domain.provision failed: %s", exc)
        return {"ok": False, "error": str(exc)}


# ── task: webya.domain.checkAllPending ───────────────────────────────────────

async def task_webya_domain_check_all_pending(**kwargs: Any) -> dict[str, Any]:
    """SSL pending な全ドメインを CF API で確認し status を更新。"""
    import httpx

    if not _CF_API_TOKEN or not _CF_ZONE_ID:
        return {"ok": True, "pendingCount": 0, "activatedCount": 0, "errorCount": 0,
                "error": "CF not configured"}

    # R0: Using q() for "not equal" predicate, and slicing for LIMIT 100 as q() doesn't support limit directly.
    raw_results = get_kotoba_client().q(
        '[:find ?domain_id ?cf_hostname_id ?domain :where [?e :vertex_webya_domain/ssl_status ?status] (not= ?status "active") [?e :vertex_webya_domain/domain_id ?domain_id] [?e :vertex_webya_domain/cf_hostname_id ?cf_hostname_id] [?e :vertex_webya_domain/domain ?domain]]'
    )
    rows = raw_results[:100]
    pending_count  = len(rows)
    activated      = 0
    error_count    = 0

    async with httpx.AsyncClient(timeout=20) as client:
        for domain_id, cf_hostname_id, domain in rows:
            if not cf_hostname_id:
                continue
            try:
                resp = await client.get(
                    f"https://api.cloudflare.com/client/v4/zones/{_CF_ZONE_ID}/custom_hostnames/{cf_hostname_id}",
                    headers={"Authorization": f"Bearer {_CF_API_TOKEN}"},
                )
                data = resp.json()
                if not data.get("success"):
                    error_count += 1
                    continue
                result = data["result"]
                ssl_status = result.get("ssl", {}).get("status", "pending")
                ownership_verified = result.get("ownership_verification_http", {}).get("http_body") is not None

                get_kotoba_client().insert_row(
                    "vertex_webya_domain",
                    {
                        "domain_id": domain_id,
                        "ssl_status": ssl_status,
                        "ownership_verified": ownership_verified,
                    },
                )
                if ssl_status == "active":
                    activated += 1
                    # R0: Fetching site_id by custom_domain for update via insert_row.
                    site_row = get_kotoba_client().select_first_where(
                        "vertex_webya_site", "custom_domain", domain, columns=["site_id"]
                    )
                    if site_row:
                        get_kotoba_client().insert_row(
                            "vertex_webya_site",
                            {
                                "site_id": site_row["site_id"],
                                "ssl_status": "active",
                            },
                        )

            except Exception as exc:
                LOG.warning("checkAllPending domain_id=%s: %s", domain_id, exc)
                error_count += 1

    LOG.info("domain.checkAllPending pending=%d activated=%d errors=%d", pending_count, activated, error_count)
    return {"ok": True, "pendingCount": pending_count, "activatedCount": activated, "errorCount": error_count}


# ── task: webya.seo.auditAllSites ─────────────────────────────────────────────

async def task_webya_seo_audit_all_sites(**kwargs: Any) -> dict[str, Any]:
    """published サイトの全ページを SEO 監査し必要なら meta_description を更新。"""
    # R0: Using q() for JOIN and multiple WHERE conditions, and slicing for LIMIT 500.
    raw_results = get_kotoba_client().q(
        '[:find ?page_id ?site_id ?slug ?title ?meta_description :where [?page :vertex_webya_page/status "published"] [?site :vertex_webya_site/status "published"] [?page :vertex_webya_page/site_id ?site-id-ref] [?site :vertex_webya_site/site_id ?site-id-ref] [?page :vertex_webya_page/page_id ?page_id] [?page :vertex_webya_page/site_id ?site_id] [?page :vertex_webya_page/slug ?slug] [?page :vertex_webya_page/title ?title] [?page :vertex_webya_page/meta_description ?meta_description]]'
    )
    rows = raw_results[:500]
    pages_audited = 0
    pages_updated = 0
    issues_found  = 0

    for page_id, site_id, slug, title, meta_desc in rows:
        pages_audited += 1
        issues: list[str] = []

        if not meta_desc or len(meta_desc) < 50:
            issues.append("meta_description too short")
        if not title:
            issues.append("title missing")

        if issues:
            issues_found += len(issues)
            if "meta_description too short" in issues:
                prompt = f"「{title}」ページのメタディスクリプション(60〜120文字)を日本語で生成。JSON: {{\"meta_description\": \"...\"}}"
                try:
                    result = llm.call_tier_json("fast", prompt, max_tokens=150)
                    new_meta = result.get("meta_description", "")[:120]
                    if new_meta:
                        get_kotoba_client().insert_row(
                            "vertex_webya_page",
                            {
                                "page_id": page_id,
                                "meta_description": new_meta,
                                "updated_at": _now(),
                            },
                        )
                        pages_updated += 1
                except Exception as exc:
                    LOG.warning("seo_audit page_id=%s: %s", page_id, exc)

    LOG.info("seo.auditAllSites audited=%d updated=%d issues=%d", pages_audited, pages_updated, issues_found)
    return {"ok": True, "sitesAudited": pages_audited, "pagesUpdated": pages_updated, "issuesFound": issues_found}


# ── task: webya.coverage ──────────────────────────────────────────────────────

async def task_webya_coverage(**kwargs: Any) -> dict[str, Any]:
    total_rows   = int(get_kotoba_client().aggregate_where("vertex_webya_site", "count", "*"))
    published    = int(get_kotoba_client().aggregate_where("vertex_webya_site", "count", "*", "status", "published"))
    generating   = int(get_kotoba_client().aggregate_where("vertex_webya_site", "count", "*", "status", "generating"))

    # R0: Using q() for "not equal" predicate in aggregate.
    ssl_pending_raw = get_kotoba_client().q(
        '[:find (count ?e) :where [?e :vertex_webya_domain/ssl_status ?status] (not= ?status "active")]'
    )
    ssl_pending = ssl_pending_raw[0][0] if ssl_pending_raw else 0

    # R0: Using q() for "IN" predicate in aggregate.
    gen_queue_raw = get_kotoba_client().q(
        '[:find (count ?e) :where [?e :vertex_webya_generation_job/status ?status] (or (= ?status "pending") (= ?status "running"))]'
    )
    gen_queue = gen_queue_raw[0][0] if gen_queue_raw else 0

    # R0: Using q() to select all from mv_webya_sites_by_status as no equivalent shim exists.
    by_prof_rows = get_kotoba_client().q(
        '[:find ?profession_kind ?status ?site_count :where [?e :mv_webya_sites_by_status/profession_kind ?profession_kind] [?e :mv_webya_sites_by_status/status ?status] [?e :mv_webya_sites_by_status/site_count ?site_count]]'
    )

    return {
        "ok":              True,
        "totalSites":      total_rows,
        "publishedSites":  published,
        "generatingSites": generating,
        "sslPending":      ssl_pending,
        "generationQueue": gen_queue,
        "byProfession":    [
            {"professionKind": r[0], "status": r[1], "siteCount": r[2]} for r in by_prof_rows
        ],
    }


# ── task: webya.getSite ───────────────────────────────────────────────────────

async def task_webya_get_site(**kwargs: Any) -> dict[str, Any]:
    site_id = str(kwargs.get("siteId") or kwargs.get("site_id") or "")
    if not site_id:
        return {"ok": False, "error": "siteId required"}

    site_data = get_kotoba_client().select_first_where(
        "vertex_webya_site",
        "site_id",
        site_id,
        columns=["site_id", "site_name", "template_id", "custom_domain", "subdomain", "ssl_status", "status", "published_at"],
    )
    if not site_data:
        return {"ok": False, "error": "site not found"}

    pages_data = get_kotoba_client().select_where(
        "vertex_webya_page",
        "site_id",
        site_id,
        columns=["slug", "title", "status"],
    )

    # R0: Using q() for ORDER BY and LIMIT 1 to get the latest job.
    job_raw = get_kotoba_client().q(
        '[:find ?job_id ?status :where [?e :vertex_webya_generation_job/site_id ?site_id] [?e :vertex_webya_generation_job/job_id ?job_id] [?e :vertex_webya_generation_job/status ?status] [?e :vertex_webya_generation_job/started_at ?started_at] :in $ ?site_id :order-by desc ?started_at]',
        args=(site_id,)
    )
    job_data = job_raw[0] if job_raw else None

    # Get profession_kind from template mapping
    tmpl_data = get_kotoba_client().select_first_where(
        "vertex_webya_template", "template_id", site_data["template_id"], columns=["profession_kind"]
    )
    profession_kind = tmpl_data["profession_kind"] if tmpl_data else ""

    return {
        "ok": True,
        "site": {
            "siteId":        site_data["site_id"],
            "siteName":      site_data["site_name"],
            "professionKind": profession_kind,
            "status":        site_data["status"],
            "subdomain":     site_data["subdomain"],
            "customDomain":  site_data["custom_domain"],
            "sslStatus":     site_data["ssl_status"],
            "publishedAt":   site_data["published_at"],
            "pages":         [{"slug": p["slug"], "title": p["title"], "status": p["status"]} for p in pages_data],
            "latestJobId":   job_data[0] if job_data else None,
            "latestJobStatus": job_data[1] if job_data else None,
        },
    }


# ── task: webya.getSitePreview ────────────────────────────────────────────────

async def task_webya_get_site_preview(**kwargs: Any) -> dict[str, Any]:
    site_id = str(kwargs.get("siteId") or kwargs.get("site_id") or "")
    slug    = str(kwargs.get("slug") or "home")

    # R0: Using q() for multiple WHERE conditions with LIMIT 1.
    raw_results = get_kotoba_client().q(
        '[:find ?slug ?title ?html_content ?json_ld ?status ?updated_at :where [?e :vertex_webya_page/site_id ?in_site_id] [?e :vertex_webya_page/slug ?in_slug] (= ?in_site_id ?site_id) (= ?in_slug ?slug) [?e :vertex_webya_page/title ?title] [?e :vertex_webya_page/html_content ?html_content] [?e :vertex_webya_page/json_ld ?json_ld] [?e :vertex_webya_page/status ?status] [?e :vertex_webya_page/updated_at ?updated_at]]',
        args=(site_id, slug)
    )
    rows_data = raw_results[0] if raw_results else None

    if not rows_data:
        return {"ok": False, "error": f"page not found: {slug}"}

    return {
        "ok":          True,
        "slug":        rows_data[0],
        "htmlContent": rows_data[2] or "",
        "jsonLd":      rows_data[3] or "",
        "status":      rows_data[4],
        "updatedAt":   rows_data[5],
    }


# ── task: webya.listSites ─────────────────────────────────────────────────────

async def task_webya_list_sites(**kwargs: Any) -> dict[str, Any]:
    profession_kind = kwargs.get("professionKind") or kwargs.get("profession_kind") or None
    status          = kwargs.get("status") or None
    limit           = int(kwargs.get("limit") or 50)
    offset          = int(kwargs.get("offset") or 0)

    # Build Datalog query for sites
    query_find_part = '[:find ?site_id ?site_name ?s_status ?subdomain ?custom_domain ?published_at'
    query_where_part = ':where [?s :vertex_webya_site/site_id ?site_id] [?s :vertex_webya_site/site_name ?site_name] [?s :vertex_webya_site/status ?s_status] [?s :vertex_webya_site/subdomain ?subdomain] [?s :vertex_webya_site/custom_domain ?custom_domain] [?s :vertex_webya_site/published_at ?published_at] [?s :vertex_webya_site/created_at ?created_at]'
    query_in_part = ':in $'
    query_order_by = ':order-by desc ?created_at'

    args_for_q = []

    if profession_kind:
        query_where_part += ' [?s :vertex_webya_site/template_id ?t_id] [?t :vertex_webya_template/template_id ?t_id] [?t :vertex_webya_template/profession_kind ?in_profession_kind]'
        query_in_part += ' ?in_profession_kind'
        args_for_q.append(profession_kind)
    if status:
        query_where_part += ' (= ?s_status ?in_status)'
        query_in_part += ' ?in_status'
        args_for_q.append(status)

    full_query = f"{query_find_part} {query_where_part} {query_in_part} {query_order_by}]"
    
    # R0: Using q() for complex query with dynamic WHERE, JOIN, ORDER BY, and manual LIMIT/OFFSET.
    all_matching_sites = get_kotoba_client().q(full_query, args=tuple(args_for_q))
    
    # Apply limit and offset in Python
    rows_data = all_matching_sites[offset : offset + limit]

    # Build Datalog query for count
    count_query_find_part = '[:find (count ?s)'
    count_query_where_part = ':where [?s :vertex_webya_site/site_id]'
    count_query_in_part = ':in $'

    count_args_for_q = []
    
    if profession_kind:
        count_query_where_part += ' [?s :vertex_webya_site/template_id ?t_id] [?t :vertex_webya_template/template_id ?t_id] [?t :vertex_webya_template/profession_kind ?in_profession_kind]'
        count_query_in_part += ' ?in_profession_kind'
        count_args_for_q.append(profession_kind)
    if status:
        count_query_where_part += ' [?s :vertex_webya_site/status ?s_status] (= ?s_status ?in_status)'
        count_query_in_part += ' ?in_status'
        count_args_for_q.append(status)

    full_count_query = f"{count_query_find_part} {count_query_where_part} {count_query_in_part}]"
    
    # R0: Using q() for complex count query with dynamic WHERE and JOIN.
    count_raw = get_kotoba_client().q(full_count_query, args=tuple(count_args_for_q))
    total_count = count_raw[0][0] if count_raw else 0

    return {
        "ok":    True,
        "sites": [
            {
                "siteId":       r[0],
                "siteName":     r[1],
                "status":       r[2],
                "subdomain":    r[3],
                "customDomain": r[4],
                "publishedAt":  r[5],
            }
            for r in rows_data
        ],
        "total":  total_count,
        "limit":  limit,
        "offset": offset,
    }


# ── Registration helper ───────────────────────────────────────────────────────

def register(worker: Any) -> None:
    """webya Zeebe worker にタスクハンドラを登録する。"""
    worker.task("webya.domain.provision")(task_webya_domain_provision)
    worker.task("webya.domain.checkAllPending")(task_webya_domain_check_all_pending)
    worker.task("webya.seo.auditAllSites")(task_webya_seo_audit_all_sites)
    # Query helpers (dispatcher 経由で XRPC として公開)
    worker.task("webya.coverage")(task_webya_coverage)
    worker.task("webya.getSite")(task_webya_get_site)
    worker.task("webya.getSitePreview")(task_webya_get_site_preview)
    worker.task("webya.listSites")(task_webya_list_sites)
    LOG.info("webya primitives registered (7 tasks)")
