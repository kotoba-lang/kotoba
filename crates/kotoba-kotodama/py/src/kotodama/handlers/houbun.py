"""
ADR-0052 houbun.etzhayyim.com — statute / regulation / treaty ingest on the
shared UDF pool.

Handlers:
- `com.etzhayyim.apps.houbun.ingestStatuteJpn`  (Phase 1, JPN e-Gov, live)
- `com.etzhayyim.apps.houbun.ingestStatuteUsa`  (Phase 2, USA GovInfo CFR/USC)
- `com.etzhayyim.apps.houbun.ingestEurLex`      (Phase 2, EU EUR-Lex SPARQL)
- `com.etzhayyim.apps.houbun.ingestTreatyUn`    (Phase 2, UN Treaty Collection)

Design notes:
- The article DID is content-addressed via blake2b-48 over
  `jurisdiction|statuteId|articleNo|amendedAt`, following ADR-0052.
  Amendments mint a new DID; lineage lives in `edge_houbun_amends`
  (not modeled in this Phase 1 MVP — inserted lazily once the source
  emits structured diffs).
- The full XML parser is intentionally narrow — it extracts `<Article>`
  nodes and their flattened text. A richer per-paragraph / per-item
  breakdown is future work; the `section` column accepts sub-structure
  when we graduate.
- e-Gov returns Shift_JIS-ish XML in the legacy v1 endpoint; v2 returns
  UTF-8 JSON. We target v2 only.
- aiohttp is used directly rather than the shared UDF pool's retry
  helper so the handler can run unit tests without a full server boot.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from kotodama import udf
from kotodama.context import Context

try:
    import aiohttp
except ImportError:  # pragma: no cover — aiohttp is a runtime dep
    aiohttp = None  # type: ignore[assignment]

ACTOR_NAME = "houbun"
ACTOR_DID = f"did:web:{ACTOR_NAME}.etzhayyim.com"
JPN_PATH_DID = f"{ACTOR_DID}:jpn:e-gov"

EGOV_V2_BASE = "https://laws.e-gov.go.jp/api/2"
EGOV_LAW_DATA = f"{EGOV_V2_BASE}/law_data"
EGOV_LAW_LIST = f"{EGOV_V2_BASE}/lawlists/all"
EGOV_TIMEOUT_SEC = 30.0

# ---------------------------------------------------------------------------
# Article DID — content-addressed blake2b-48 (12 hex chars)
# ---------------------------------------------------------------------------


def _blake3_prefix12(jurisdiction: str, statute_id: str, article_no: str, amended_at: str) -> str:
    """12-char hex prefix — stable across reingestion. See ADR-0052."""
    payload = "|".join((jurisdiction or "", statute_id or "", article_no or "", amended_at or ""))
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=6).hexdigest()


def _article_did(jurisdiction: str, statute_id: str, article_no: str, amended_at: str) -> str:
    h = _blake3_prefix12(jurisdiction, statute_id, article_no, amended_at)
    return f"{ACTOR_DID}:article:{h}"


# ---------------------------------------------------------------------------
# Inserts — Hyperdrive direct (ADR-0036)
# ---------------------------------------------------------------------------

_INSERT_STATUTE = """
    INSERT INTO vertex_houbun_statute (
        vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo,
        jurisdiction, statute_id, title, title_native, statute_type,
        enacted_date, effective_date, repealed_date,
        source, source_url, license, language, article_count, last_verified,
        created_at, org_id, user_id, actor_id
    ) VALUES (
        $1, NULL, $2, 1, $3, $4, $3,
        $5, $6, $7, $8, $9,
        $10, $11, $12,
        $13, $14, $15, $16, $17, $18,
        $19, 'etzhayyim', 'system', $20
    )
    ON CONFLICT (vertex_id) DO UPDATE SET
        title           = EXCLUDED.title,
        title_native    = EXCLUDED.title_native,
        effective_date  = EXCLUDED.effective_date,
        repealed_date   = EXCLUDED.repealed_date,
        article_count   = EXCLUDED.article_count,
        last_verified   = EXCLUDED.last_verified
    RETURNING vertex_id
"""

_INSERT_ARTICLE = """
    INSERT INTO vertex_houbun_article (
        vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo,
        statute_ref, article_no, section, title, text, language,
        article_did, blake3_hash, amended_at, source_url,
        created_at, org_id, user_id, actor_id
    ) VALUES (
        $1, NULL, $2, 1, $3, $4, $3,
        $5, $6, $7, $8, $9, $10,
        $11, $12, $13, $14,
        $15, 'etzhayyim', 'system', $16
    )
    ON CONFLICT (vertex_id) DO NOTHING
    RETURNING vertex_id
"""

_INSERT_EDGE_STATUTE_ARTICLE = """
    INSERT INTO edge_houbun_statute_article (
        edge_id, src_vid, dst_vid, _seq, created_date, sensitivity_ord, owner_did,
        article_no, order_key,
        created_at, org_id, user_id, actor_id
    ) VALUES (
        $1, $2, $3, NULL, $4, 1, $5,
        $6, $7,
        $8, 'etzhayyim', 'system', $9
    )
    ON CONFLICT (edge_id) DO NOTHING
"""


async def _write_statute_row(
    pool: Any,
    *,
    jurisdiction: str,
    statute_id: str,
    title: str,
    title_native: str | None,
    statute_type: str,
    enacted_date: str | None,
    effective_date: str | None,
    repealed_date: str | None,
    source: str,
    source_url: str,
    license_str: str,
    language: str,
    article_count: int,
) -> tuple[str, bool]:
    """Returns (statute_vertex_id, inserted)."""
    path_did = JPN_PATH_DID if source == "e-gov" else f"{ACTOR_DID}:{jurisdiction}:{source}"
    rkey = statute_id
    vertex_id = f"at://{path_did}/com.etzhayyim.apps.houbun.statute/{rkey}"
    now_iso = datetime.now(timezone.utc).isoformat()
    result = await pool.fetchval(
        _INSERT_STATUTE,
        vertex_id,  # $1
        now_iso[:10],  # $2
        path_did,  # $3  owner_did / repo
        rkey,  # $4
        jurisdiction,  # $5
        statute_id,  # $6
        title,  # $7
        title_native,  # $8
        statute_type,  # $9
        enacted_date,  # $10
        effective_date,  # $11
        repealed_date,  # $12
        source,  # $13
        source_url,  # $14
        license_str,  # $15
        language,  # $16
        article_count,  # $17
        now_iso,  # $18  last_verified
        now_iso,  # $19  created_at
        f"sys.{ACTOR_NAME}",  # $20
    )
    return vertex_id, result is not None


async def _write_article_row(
    pool: Any,
    *,
    jurisdiction: str,
    statute_id: str,
    statute_ref: str,
    article_no: str,
    section: str | None,
    title: str | None,
    text: str,
    language: str,
    amended_at: str | None,
    source_url: str,
    order_key: int,
) -> bool:
    """Returns True if a new article row was inserted."""
    article_did_str = _article_did(jurisdiction, statute_id, article_no, amended_at or "")
    blake_hash = article_did_str.rsplit(":", 1)[-1]
    rkey = blake_hash
    vertex_id = f"at://{article_did_str}/com.etzhayyim.apps.houbun.article/{rkey}"
    now_iso = datetime.now(timezone.utc).isoformat()

    ins = await pool.fetchval(
        _INSERT_ARTICLE,
        vertex_id,  # $1
        now_iso[:10],  # $2
        article_did_str,  # $3  owner_did / repo
        rkey,  # $4
        statute_ref,  # $5
        article_no,  # $6
        section,  # $7
        title,  # $8
        text,  # $9
        language,  # $10
        article_did_str,  # $11
        blake_hash,  # $12
        amended_at,  # $13
        source_url,  # $14
        now_iso,  # $15
        f"sys.{ACTOR_NAME}",  # $16
    )
    if ins is None:
        return False

    # Lazy edge write — only when the article row was new.
    edge_id = f"{statute_ref}::{vertex_id}"
    await pool.execute(
        _INSERT_EDGE_STATUTE_ARTICLE,
        edge_id,  # $1
        statute_ref,  # $2
        vertex_id,  # $3
        now_iso[:10],  # $4
        article_did_str,  # $5
        article_no,  # $6
        order_key,  # $7
        now_iso,  # $8
        f"sys.{ACTOR_NAME}",  # $9
    )
    return True


# ---------------------------------------------------------------------------
# e-Gov v2 fetch + parse
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def _flatten_text(obj: Any) -> str:
    """
    e-Gov v2 returns nested JSON where `ArticleCaption`/`Paragraph` etc.
    carry either string values or `{"#text": "..."}` shapes. Flatten any
    subtree into plain text, collapsing whitespace.
    """
    if obj is None:
        return ""
    if isinstance(obj, str):
        return _WS.sub(" ", obj).strip()
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, list):
        return " ".join(_flatten_text(x) for x in obj if x is not None).strip()
    if isinstance(obj, dict):
        # Common e-Gov attribute-style keys.
        if "#text" in obj:
            return _flatten_text(obj["#text"])
        if "$" in obj:
            return _flatten_text(obj["$"])
        parts: list[str] = []
        for key, value in obj.items():
            if key.startswith("@") or key.startswith("_"):
                continue
            parts.append(_flatten_text(value))
        return " ".join(p for p in parts if p).strip()
    return ""


def _iter_articles(law_body: Any) -> list[dict[str, Any]]:
    """
    Walk the LawBody tree and yield `{article_no, title, text, section}`
    per <Article> node. e-Gov nests articles under MainProvision/Chapter/
    Section/Subsection — we flatten the hierarchy; `section` carries the
    chapter label when the XPath has one.
    """
    out: list[dict[str, Any]] = []

    def visit(node: Any, section_label: str | None) -> None:
        if isinstance(node, list):
            for n in node:
                visit(n, section_label)
            return
        if not isinstance(node, dict):
            return

        # Track the nearest chapter/section title as we descend.
        local_label = section_label
        for key in ("Chapter", "Section", "Subsection", "Division"):
            sub = node.get(key)
            if sub is None:
                continue
            sub_list = sub if isinstance(sub, list) else [sub]
            for s in sub_list:
                label_obj = s.get(f"{key}Title") if isinstance(s, dict) else None
                label = _flatten_text(label_obj) if label_obj is not None else None
                visit(s, label or local_label)

        # Article nodes live anywhere in the tree.
        article = node.get("Article")
        if article is not None:
            art_list = article if isinstance(article, list) else [article]
            for a in art_list:
                if not isinstance(a, dict):
                    continue
                attrs = a.get("@") or {}
                num = attrs.get("Num") if isinstance(attrs, dict) else None
                title_raw = a.get("ArticleTitle") or a.get("@Title")
                caption_raw = a.get("ArticleCaption")
                body_raw = a.get("Paragraph") or a.get("ParagraphSentence") or a
                article_no = _flatten_text(title_raw) or (f"第{num}条" if num else "")
                caption = _flatten_text(caption_raw)
                body = _flatten_text(body_raw)
                if not article_no and not body:
                    continue
                out.append(
                    {
                        "article_no": article_no or f"art-{len(out) + 1}",
                        "title": caption or None,
                        "section": local_label,
                        "text": body,
                    }
                )

        # Recurse into everything else so deeply-nested Article nodes are caught.
        for key, value in node.items():
            if key in ("Article", "Chapter", "Section", "Subsection", "Division", "@"):
                continue
            if isinstance(value, (dict, list)):
                visit(value, local_label)

    visit(law_body, None)
    return out


async def _fetch_law_data(session: Any, law_id: str) -> dict[str, Any] | None:
    url = f"{EGOV_LAW_DATA}/{law_id}"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=EGOV_TIMEOUT_SEC)) as resp:
        if resp.status != 200:
            return None
        return await resp.json()


async def _fetch_law_list(session: Any, since: str | None, limit: int) -> list[str]:
    """Return the list of lawIds updated after `since` (best-effort)."""
    params: dict[str, str] = {}
    if since:
        params["updateDate"] = since
    async with session.get(
        EGOV_LAW_LIST,
        params=params,
        timeout=aiohttp.ClientTimeout(total=EGOV_TIMEOUT_SEC),
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
    # v2 shape: {"laws": [{"lawId": "...", "lawTitle": "...", ...}, ...]}
    laws = data.get("laws") if isinstance(data, dict) else None
    if not isinstance(laws, list):
        return []
    out: list[str] = []
    for entry in laws[:limit]:
        if isinstance(entry, dict):
            law_id = entry.get("lawId") or entry.get("LawId")
            if isinstance(law_id, str):
                out.append(law_id)
    return out


async def _ingest_one(session: Any, pool: Any, law_id: str) -> dict[str, int]:
    """Fetch + write one statute + its articles."""
    law = await _fetch_law_data(session, law_id)
    if law is None:
        return {"statutesFetched": 0, "statutesInserted": 0, "articlesInserted": 0, "articlesSkipped": 0, "errors": 1}

    law_full = law.get("lawFullText") or law.get("LawFullText") or {}
    law_header = law.get("lawInfo") or law.get("LawInfo") or {}
    title = _flatten_text(law_header.get("lawTitle") or law_full.get("LawTitle")) or law_id
    enacted = _flatten_text(law_header.get("enforcementDate"))
    effective = _flatten_text(law_header.get("effectiveDate")) or enacted or None
    statute_type = _flatten_text(law_header.get("lawType")) or "law"
    source_url = f"https://laws.e-gov.go.jp/law/{law_id}"

    law_body = (
        law_full.get("LawBody")
        or law.get("lawBody")
        or law.get("Law", {}).get("LawBody")
        if isinstance(law, dict)
        else None
    )
    articles = _iter_articles(law_body) if law_body is not None else []

    statute_ref, _ = await _write_statute_row(
        pool,
        jurisdiction="jpn",
        statute_id=law_id,
        title=title,
        title_native=title,
        statute_type=statute_type,
        enacted_date=enacted or None,
        effective_date=effective,
        repealed_date=None,
        source="e-gov",
        source_url=source_url,
        license_str="CC-BY-4.0",
        language="ja",
        article_count=len(articles),
    )

    inserted = 0
    skipped = 0
    for idx, art in enumerate(articles):
        try:
            if await _write_article_row(
                pool,
                jurisdiction="jpn",
                statute_id=law_id,
                statute_ref=statute_ref,
                article_no=art["article_no"],
                section=art.get("section"),
                title=art.get("title"),
                text=art["text"],
                language="ja",
                amended_at=None,
                source_url=source_url,
                order_key=idx,
            ):
                inserted += 1
            else:
                skipped += 1
        except Exception:  # noqa: BLE001 — row-level isolation
            skipped += 1

    return {
        "statutesFetched": 1,
        "statutesInserted": 1,
        "articlesInserted": inserted,
        "articlesSkipped": skipped,
        "errors": 0,
    }


# ---------------------------------------------------------------------------
# ingestStatuteJpn UDF entry
# ---------------------------------------------------------------------------


@udf(
    nsid="com.etzhayyim.apps.houbun.ingestStatuteJpn",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("houbun", "ingest", "jpn"),
    agent_tool=(
        "Crawl Japanese statutes from e-Gov 法令 API v2 and write "
        "statute / article rows to Hyperdrive. Pass lawId for a single "
        "statute, or `since` for a bounded delta."
    ),
)
async def ingest_statute_jpn(params_json: str) -> str:
    """
    Input JSON: {lawId?} | {since?, limit?}
    Output JSON: {ok, source, statutesFetched, statutesInserted,
                  articlesInserted, articlesSkipped, errors} | {error}
    """
    if aiohttp is None:
        return json.dumps({"error": "aiohttp not installed"})

    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    law_id = params.get("lawId")
    since = params.get("since")
    raw_limit = int(params.get("limit") or 10)
    limit = max(1, min(200, raw_limit))

    if not law_id and not since:
        return json.dumps({"error": "lawId or since required"})

    ctx = Context(nsid="com.etzhayyim.apps.houbun.ingestStatuteJpn")

    agg = {
        "statutesFetched": 0,
        "statutesInserted": 0,
        "articlesInserted": 0,
        "articlesSkipped": 0,
        "errors": 0,
    }

    async with aiohttp.ClientSession(
        headers={"User-Agent": "houbun.etzhayyim.com/0.1 (+https://houbun.etzhayyim.com)"},
    ) as session:
        if law_id:
            try:
                result = await _ingest_one(session, ctx.db, law_id)
                for k, v in result.items():
                    agg[k] += int(v)
            except Exception:  # noqa: BLE001
                ctx.logger().exception("ingestStatuteJpn single failed", lawId=law_id)
                agg["errors"] += 1
        else:
            law_ids = await _fetch_law_list(session, since, limit)
            for lid in law_ids:
                try:
                    result = await _ingest_one(session, ctx.db, lid)
                    for k, v in result.items():
                        agg[k] += int(v)
                except Exception:  # noqa: BLE001
                    ctx.logger().exception("ingestStatuteJpn delta row failed", lawId=lid)
                    agg["errors"] += 1

    return json.dumps({"ok": True, "source": "e-gov", **agg})


# =============================================================================
# Phase 2 — USA CFR / USC (GovInfo bulkdata)
# =============================================================================

GOVINFO_BASE = "https://www.govinfo.gov"
GOVINFO_JSON_CFR = f"{GOVINFO_BASE}/bulkdata/json/CFR"
GOVINFO_JSON_USCODE = f"{GOVINFO_BASE}/bulkdata/json/USCODE"
USA_PATH_DID_CFR = f"{ACTOR_DID}:usa:cfr"
USA_PATH_DID_USC = f"{ACTOR_DID}:usa:usc"


async def _fetch_govinfo_index(session: Any, url: str) -> dict[str, Any]:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=EGOV_TIMEOUT_SEC)) as resp:
        if resp.status != 200:
            return {}
        return await resp.json()


async def _ingest_one_usa_title(
    session: Any,
    pool: Any,
    *,
    collection: str,
    package_id: str,
    title_name: str,
    year: int | None,
    package_link: str,
) -> dict[str, int]:
    """
    Phase 2 MVP — one GovInfo package = one vertex_houbun_statute row.
    Full title XML (part / section / paragraph) parsing is deferred; we
    pin the contract and ingest metadata so citations can reference the
    title immediately.
    """
    source = "govinfo-cfr" if collection == "CFR" else "govinfo-usc"
    path_did = USA_PATH_DID_CFR if collection == "CFR" else USA_PATH_DID_USC
    statute_id = package_id  # GovInfo packageId is globally unique
    source_url = package_link or f"{GOVINFO_BASE}/app/details/{package_id}"

    _, inserted = await _write_statute_row(
        pool,
        jurisdiction="usa",
        statute_id=statute_id,
        title=title_name or package_id,
        title_native=title_name or None,
        statute_type="regulation" if collection == "CFR" else "law",
        enacted_date=None,
        effective_date=(f"{year}-01-01" if year else None),
        repealed_date=None,
        source=source,
        source_url=source_url,
        license_str="public-domain",
        language="en",
        article_count=0,
    )
    # path_did is recomputed inside _write_statute_row via the source
    # branch, so the path DID stays consistent across calls.
    _ = path_did
    return {
        "statutesFetched": 1,
        "statutesInserted": 1 if inserted else 0,
        "articlesInserted": 0,
        "articlesSkipped": 0,
        "errors": 0,
    }


@udf(
    nsid="com.etzhayyim.apps.houbun.ingestStatuteUsa",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("houbun", "ingest", "usa"),
    agent_tool=(
        "Crawl US CFR / USC title metadata from GovInfo bulkdata. "
        "Phase 2 MVP ingests title-level packages; full article text "
        "parse follows in a later PR."
    ),
)
async def ingest_statute_usa(params_json: str) -> str:
    """
    Input JSON: {collection?='CFR'|'USCODE', titleNumber?, year?, limit?}
    Output JSON: {ok, source, statutesFetched, statutesInserted,
                  articlesInserted, articlesSkipped, errors} | {error}
    """
    if aiohttp is None:
        return json.dumps({"error": "aiohttp not installed"})

    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    collection = str(params.get("collection") or "CFR").upper()
    if collection not in ("CFR", "USCODE"):
        return json.dumps({"error": "collection must be CFR or USCODE"})
    title_number = params.get("titleNumber")
    year = params.get("year")
    raw_limit = int(params.get("limit") or 50)
    limit = max(1, min(500, raw_limit))

    ctx = Context(nsid="com.etzhayyim.apps.houbun.ingestStatuteUsa")
    agg = {
        "statutesFetched": 0,
        "statutesInserted": 0,
        "articlesInserted": 0,
        "articlesSkipped": 0,
        "errors": 0,
    }

    index_url = GOVINFO_JSON_CFR if collection == "CFR" else GOVINFO_JSON_USCODE
    if year:
        index_url = f"{index_url}/{int(year)}"
    if title_number is not None:
        suffix = f"title-{int(title_number)}"
        index_url = f"{index_url}/{suffix}"

    async with aiohttp.ClientSession(
        headers={"User-Agent": "houbun.etzhayyim.com/0.1 (+https://houbun.etzhayyim.com)"},
    ) as session:
        try:
            data = await _fetch_govinfo_index(session, index_url)
        except Exception:  # noqa: BLE001
            ctx.logger().exception("ingestStatuteUsa index fetch failed", url=index_url)
            return json.dumps({"ok": False, "source": collection.lower(), "error": "index fetch failed"})

        children = data.get("childPackages") or data.get("packages") or data.get("children") or []
        if not isinstance(children, list):
            children = []

        for entry in children[:limit]:
            if not isinstance(entry, dict):
                continue
            package_id = entry.get("packageId") or entry.get("id")
            if not isinstance(package_id, str):
                continue
            title_name = entry.get("title") or entry.get("packageTitle") or ""
            link = entry.get("link") or entry.get("packageLink") or ""
            try:
                result = await _ingest_one_usa_title(
                    session,
                    ctx.db,
                    collection=collection,
                    package_id=package_id,
                    title_name=str(title_name),
                    year=(int(year) if year else None),
                    package_link=str(link),
                )
                for k, v in result.items():
                    agg[k] += int(v)
            except Exception:  # noqa: BLE001
                ctx.logger().exception("ingestStatuteUsa row failed", packageId=package_id)
                agg["errors"] += 1

    source_str = "govinfo-cfr" if collection == "CFR" else "govinfo-usc"
    return json.dumps({"ok": True, "source": source_str, **agg})


# =============================================================================
# Phase 2 — EU EUR-Lex (SPARQL endpoint)
# =============================================================================

EURLEX_SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
EU_PATH_DID = f"{ACTOR_DID}:eu:eur-lex"


def _eurlex_query_single(celex: str) -> str:
    """SPARQL — single act by CELEX."""
    return f"""
    PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    SELECT ?work ?title ?date_document ?type WHERE {{
      ?work cdm:resource_legal_id_celex "{celex}" .
      OPTIONAL {{ ?expr cdm:expression_belongs_to_work ?work ; cdm:expression_title ?title . FILTER(LANG(?title) = 'en') }}
      OPTIONAL {{ ?work cdm:work_date_document ?date_document }}
      OPTIONAL {{ ?work cdm:work_has_resource-type ?type }}
    }} LIMIT 1
    """


def _eurlex_query_delta(since: str, act_type: str | None, limit: int) -> str:
    """SPARQL — recent acts since cutoff."""
    type_filter = ""
    if act_type == "regulation":
        type_filter = 'FILTER(STRSTARTS(?celex, "3") && SUBSTR(?celex, 6, 1) = "R")'
    elif act_type == "directive":
        type_filter = 'FILTER(STRSTARTS(?celex, "3") && SUBSTR(?celex, 6, 1) = "L")'
    elif act_type == "decision":
        type_filter = 'FILTER(STRSTARTS(?celex, "3") && SUBSTR(?celex, 6, 1) = "D")'
    return f"""
    PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
    SELECT ?work ?celex ?title ?date_document WHERE {{
      ?work cdm:resource_legal_id_celex ?celex ;
            cdm:work_date_document ?date_document .
      OPTIONAL {{ ?expr cdm:expression_belongs_to_work ?work ; cdm:expression_title ?title . FILTER(LANG(?title) = 'en') }}
      FILTER(?date_document >= "{since}"^^<http://www.w3.org/2001/XMLSchema#date>)
      {type_filter}
    }} ORDER BY DESC(?date_document) LIMIT {limit}
    """


async def _run_sparql(session: Any, query: str) -> list[dict[str, Any]]:
    """Post SPARQL query, return bindings list."""
    async with session.post(
        EURLEX_SPARQL,
        data={"query": query, "format": "application/sparql-results+json"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=aiohttp.ClientTimeout(total=EGOV_TIMEOUT_SEC),
    ) as resp:
        if resp.status != 200:
            return []
        payload = await resp.json()
    results = payload.get("results", {}).get("bindings", [])
    return results if isinstance(results, list) else []


def _sparql_val(binding: dict[str, Any], key: str) -> str | None:
    """Extract a .value from a SPARQL JSON binding row."""
    v = binding.get(key)
    if isinstance(v, dict):
        val = v.get("value")
        return str(val) if val is not None else None
    return None


async def _ingest_one_eurlex(pool: Any, binding: dict[str, Any]) -> dict[str, int]:
    """One SPARQL binding → one vertex_houbun_statute row."""
    celex = _sparql_val(binding, "celex") or ""
    if not celex:
        # single-act query uses `work` URI — extract CELEX from the URI tail.
        work = _sparql_val(binding, "work") or ""
        celex = work.rsplit("/", 1)[-1]
    if not celex:
        return {"statutesFetched": 0, "statutesInserted": 0, "errors": 1}

    title = _sparql_val(binding, "title") or celex
    date_doc = _sparql_val(binding, "date_document")
    source_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

    _, inserted = await _write_statute_row(
        pool,
        jurisdiction="eu",
        statute_id=celex,
        title=title,
        title_native=title,
        statute_type="regulation",  # coarse default; refined once we add act-type parsing
        enacted_date=date_doc,
        effective_date=date_doc,
        repealed_date=None,
        source="eur-lex",
        source_url=source_url,
        license_str="©European Union (CC-BY-SA)",
        language="en",
        article_count=0,
    )
    return {"statutesFetched": 1, "statutesInserted": 1 if inserted else 0, "errors": 0}


@udf(
    nsid="com.etzhayyim.apps.houbun.ingestEurLex",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("houbun", "ingest", "eu"),
    agent_tool=(
        "Crawl EU legal acts from EUR-Lex via its public SPARQL "
        "endpoint. Pass celex for a single act or since for a delta."
    ),
)
async def ingest_eur_lex(params_json: str) -> str:
    """
    Input JSON: {celex?} | {since?, actType?, limit?}
    Output JSON: {ok, source, statutesFetched, statutesInserted, errors}
    """
    if aiohttp is None:
        return json.dumps({"error": "aiohttp not installed"})

    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    celex = params.get("celex")
    since = params.get("since")
    act_type = params.get("actType")
    raw_limit = int(params.get("limit") or 50)
    limit = max(1, min(500, raw_limit))

    if not celex and not since:
        return json.dumps({"error": "celex or since required"})

    ctx = Context(nsid="com.etzhayyim.apps.houbun.ingestEurLex")
    agg = {"statutesFetched": 0, "statutesInserted": 0, "errors": 0}

    query = _eurlex_query_single(celex) if celex else _eurlex_query_delta(since, act_type, limit)

    async with aiohttp.ClientSession(
        headers={"User-Agent": "houbun.etzhayyim.com/0.1 (+https://houbun.etzhayyim.com)"},
    ) as session:
        try:
            bindings = await _run_sparql(session, query)
        except Exception:  # noqa: BLE001
            ctx.logger().exception("ingestEurLex SPARQL failed")
            return json.dumps({"ok": False, "source": "eur-lex", "error": "SPARQL failed"})

        for b in bindings:
            try:
                result = await _ingest_one_eurlex(ctx.db, b)
                for k, v in result.items():
                    agg[k] += int(v)
            except Exception:  # noqa: BLE001
                ctx.logger().exception("ingestEurLex row failed")
                agg["errors"] += 1

    return json.dumps({"ok": True, "source": "eur-lex", **agg})


# =============================================================================
# Phase 2 — UN Treaty Collection (scaffold, parser TBD)
# =============================================================================

_INSERT_TREATY = """
    INSERT INTO vertex_houbun_treaty (
        vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo,
        title, title_native, parties_json, signed_date, entered_into_force_date,
        un_reg_no, depositary, source, source_record_id, source_url, language,
        created_at, org_id, user_id, actor_id
    ) VALUES (
        $1, NULL, $2, 1, $3, $4, $3,
        $5, $6, $7, $8, $9,
        $10, $11, $12, $13, $14, $15,
        $16, 'etzhayyim', 'system', $17
    )
    ON CONFLICT (vertex_id) DO NOTHING
    RETURNING vertex_id
"""


async def _write_treaty_row(pool: Any, row: dict[str, Any]) -> bool:
    un_reg = row.get("un_reg_no") or row.get("source_record_id") or "unknown"
    rkey = re.sub(r"[^a-zA-Z0-9]+", "-", str(un_reg)).strip("-").lower()[:64] or "unknown"
    path_did = f"{ACTOR_DID}:int:un-treaty"
    vertex_id = f"at://{path_did}/com.etzhayyim.apps.houbun.treaty/{rkey}"
    now_iso = datetime.now(timezone.utc).isoformat()
    parties = row.get("parties") or []
    parties_json = json.dumps(parties) if parties else None
    result = await pool.fetchval(
        _INSERT_TREATY,
        vertex_id,  # $1
        now_iso[:10],  # $2
        path_did,  # $3
        rkey,  # $4
        row.get("title"),  # $5
        row.get("title_native"),  # $6
        parties_json,  # $7
        row.get("signed_date"),  # $8
        row.get("entered_into_force_date"),  # $9
        row.get("un_reg_no"),  # $10
        row.get("depositary"),  # $11
        row.get("source") or "un-treaty",  # $12
        row.get("source_record_id") or un_reg,  # $13
        row.get("source_url"),  # $14
        row.get("language"),  # $15
        now_iso,  # $16
        f"sys.{ACTOR_NAME}",  # $17
    )
    return result is not None


async def _fetch_un_treaty_records(
    _session: Any, _un_reg_no: str | None, _since: str | None, _limit: int
) -> list[dict[str, Any]]:
    """
    TODO (phase-2-post-pilot): implement UN Treaty Collection scraper.
    The public surface is at https://treaties.un.org/ with recently-
    registered HTML tables plus a search API. Contract is pinned; the
    parser will be swapped in without touching callers.
    """
    return []


@udf(
    nsid="com.etzhayyim.apps.houbun.ingestTreatyUn",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("houbun", "ingest", "un"),
    agent_tool=(
        "Crawl international treaties from the UN Treaty Collection. "
        "Contract surface is pinned; the parser scaffold lands in a "
        "later PR."
    ),
)
async def ingest_treaty_un(params_json: str) -> str:
    """
    Input JSON: {unRegNo?} | {since?, limit?}
    Output JSON: {ok, source, treatiesFetched, treatiesInserted, errors}
    """
    if aiohttp is None:
        return json.dumps({"error": "aiohttp not installed"})

    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    un_reg_no = params.get("unRegNo")
    since = params.get("since")
    raw_limit = int(params.get("limit") or 50)
    limit = max(1, min(500, raw_limit))

    if not un_reg_no and not since:
        return json.dumps({"error": "unRegNo or since required"})

    ctx = Context(nsid="com.etzhayyim.apps.houbun.ingestTreatyUn")
    agg = {"treatiesFetched": 0, "treatiesInserted": 0, "errors": 0}

    async with aiohttp.ClientSession(
        headers={"User-Agent": "houbun.etzhayyim.com/0.1 (+https://houbun.etzhayyim.com)"},
    ) as session:
        records = await _fetch_un_treaty_records(session, un_reg_no, since, limit)
        agg["treatiesFetched"] = len(records)
        for rec in records:
            try:
                if await _write_treaty_row(ctx.db, rec):
                    agg["treatiesInserted"] += 1
            except Exception:  # noqa: BLE001
                ctx.logger().exception("ingestTreatyUn row failed")
                agg["errors"] += 1

    return json.dumps({"ok": True, "source": "un-treaty", **agg})
