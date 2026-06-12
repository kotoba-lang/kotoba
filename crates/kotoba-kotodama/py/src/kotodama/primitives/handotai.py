"""handotai semiconductor intelligence primitives (ADR-0056 BPMN-as-actor).

3 Zeebe task types for handotai.etzhayyim.com:
  handotai.seed.writers    — idempotent upsert of 6 built-in RSS writer sources
  handotai.collect.rssAll  — fetch all enabled sources, parse items, write articles
  handotai.generate.digest — read today's articles, LLM-summarize, write digest

Tables: vertex_handotai_source / vertex_handotai_article / vertex_handotai_digest
"""

from __future__ import annotations

import datetime
import hashlib
import xml.etree.ElementTree as ET
from typing import Any

import aiohttp

from kotodama import llm as _llm
from kotodama.kotoba_datomic import get_kotoba_client


_OWNER_DID = "did:web:handotai.etzhayyim.com"
_COL_SRC = "com.etzhayyim.apps.handotai.source"
_COL_ART = "com.etzhayyim.apps.handotai.article"
_COL_DIG = "com.etzhayyim.apps.handotai.digest"

_WRITERS: list[dict[str, str]] = [
    {"source_id": "src-pcw",  "name": "PC Watch",                  "url": "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf", "language": "ja", "category": "fabrication"},
    {"source_id": "src-itm",  "name": "ITmedia NEWS",               "url": "https://rss.itmedia.co.jp/rss/2.0/newsBursts.xml",         "language": "ja", "category": "market"},
    {"source_id": "src-pubk", "name": "Publickey",                  "url": "https://www.publickey1.jp/atom.xml",                       "language": "ja", "category": "design"},
    {"source_id": "src-semia","name": "SemiAnalysis",               "url": "https://www.semianalysis.com/feed",                        "language": "en", "category": "market"},
    {"source_id": "src-semie","name": "Semiconductor Engineering",  "url": "https://semiengineering.com/feed/",                        "language": "en", "category": "design"},
    {"source_id": "src-eet",  "name": "EE Times",                   "url": "https://www.eetimes.com/feed/",                            "language": "en", "category": "market"},
]

# Semiconductor keyword → category hint (used for fast T1 categorisation)
_CAT_KEYWORDS: list[tuple[list[str], str]] = [
    (["tsmc", "samsung", "intel foundry", "globalfoundries", "smic", "rapidus", "foundry", "fab ", "node", "nm "], "fabrication"),
    (["dram", "hbm", "nand", "memory", "kioxia", "micron", "sk hynix", "flash"], "materials"),
    (["asml", "applied materials", "tokyo electron", "lam research", "kla", "screen holdings", "lasertec", "disco"], "equipment"),
    (["arm", "cadence", "synopsys", "siemens eda", "eda ", "ip core", "risc-v", "verilog", "rtl "], "design"),
    (["supply chain", "chip shortage", "export control", "tariff", "trade"], "supply_chain"),
    (["gpu", "ai chip", "ai accelerator", "nvidia", "amd ", "tpu", "npu", "inference", "training"], "market"),
    (["automotive", "ev ", "electric vehicle", "power device", "sic ", "gan "], "market"),
    (["policy", "chips act", "government", "subsidy", "経産省", "meti", "regulation"], "policy"),
    (["quantum", "photonic", "research", "university", "lab "], "research"),
]


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _src_vid(source_id: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_SRC}/{source_id}"


def _art_vid(article_id: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_ART}/{article_id}"


def _dig_vid(date: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_DIG}/{date}"


def _article_id(url: str) -> str:
    return "art-" + hashlib.sha256(url.encode()).hexdigest()[:16]


def _guess_category(text: str, default: str) -> str:
    low = (text or "").lower()
    for keywords, cat in _CAT_KEYWORDS:
        if any(kw in low for kw in keywords):
            return cat
    return default


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"<[^>]+>", "", raw).strip()[:1000]


# ---------------------------------------------------------------------------
# RSS / Atom feed parser
# ---------------------------------------------------------------------------

_NS = {
    "atom":    "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc":      "http://purl.org/dc/elements/1.1/",
    "rss10":   "http://purl.org/rss/1.0/",
    "rdf":     "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}


def _parse_feed(xml_bytes: bytes, source_name: str, source_lang: str, category: str) -> list[dict[str, Any]]:
    """Parse RSS 1.0/2.0 or Atom feed into article dicts."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    tag = root.tag
    articles: list[dict[str, Any]] = []

    if "Atom" in tag or "atom" in tag or root.tag == "{http://www.w3.org/2005/Atom}feed":
        # Atom 1.0
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            link_el  = entry.find("{http://www.w3.org/2005/Atom}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            summ_el  = entry.find("{http://www.w3.org/2005/Atom}summary")
            cont_el  = entry.find("{http://www.w3.org/2005/Atom}content")
            pub_el   = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("{http://www.w3.org/2005/Atom}updated")
            title = title_el.text if title_el is not None else ""
            url   = link_el.get("href", "") if link_el is not None else ""
            if not url:
                url = link_el.text.strip() if (link_el is not None and link_el.text) else ""
            summary = _strip_html((summ_el.text or "") if summ_el is not None else (cont_el.text or "") if cont_el is not None else "")
            pub = pub_el.text if pub_el is not None else _utc_now()
            if url:
                articles.append({"title": title or "", "url": url, "summary": summary, "pub": pub or _utc_now()})

    else:
        # RSS 2.0 or RSS 1.0 (RDF-based)
        channel = root.find("channel")
        items = root.findall(".//item")
        if not items and channel is not None:
            items = channel.findall("item")

        for item in items:
            title_el = item.find("title")
            link_el  = item.find("link")
            desc_el  = item.find("description")
            pub_el   = item.find("pubDate") or item.find("{http://purl.org/dc/elements/1.1/}date")
            title = title_el.text if title_el is not None else ""
            url   = link_el.text.strip() if (link_el is not None and link_el.text) else ""
            summary = _strip_html(desc_el.text or "" if desc_el is not None else "")
            pub = pub_el.text if pub_el is not None else _utc_now()
            if url:
                articles.append({"title": title or "", "url": url, "summary": summary, "pub": pub or _utc_now()})

    result = []
    for a in articles[:20]:  # cap at 20 per source
        url = a["url"]
        title = a["title"]
        summary = a["summary"]
        cat = _guess_category(f"{title} {summary}", category)
        result.append({
            "article_id":       _article_id(url),
            "source_url":       url,
            "source_name":      source_name,
            "source_lang":      source_lang,
            "title_original":   title,
            "title_ja":         "" if source_lang != "ja" else title,
            "title_en":         "" if source_lang != "en" else title,
            "summary_original": summary,
            "summary_ja":       "" if source_lang != "ja" else summary,
            "summary_en":       "" if source_lang != "en" else summary,
            "category":         cat,
            "subcategory":      "",
            "entities":         "[]",
            "tags":             "[]",
            "sentiment":        "neutral",
            "importance":       3,
            "published_at":     (a["pub"] or _utc_now())[:64],
            "crawled_at":       _utc_now(),
            "visibility":       "free",
            "writer_did":       f"{_OWNER_DID}:writer:{source_name.lower().replace(' ', '_')}",
        })
    return result


# ---------------------------------------------------------------------------
# handotai.seed.writers
# ---------------------------------------------------------------------------

def task_handotai_seed_writers() -> dict:
    """Idempotent upsert of 6 built-in RSS writer entries into vertex_handotai_source."""
    now = _utc_now()
    written = 0
    kotoba_client = get_kotoba_client()
    for w in _WRITERS:
        vid = _src_vid(w["source_id"])
        row_dict = {
            "vertex_id": vid,
            "source_id": w["source_id"],
            "name": w["name"],
            "url": w["url"],
            "source_type": "rss",
            "language": w["language"],
            "category": w["category"],
            "crawl_interval_min": 15,
            "enabled": True,
            "writer_did": f"{_OWNER_DID}:writer:{w['source_id']}",
            "actor_did": _OWNER_DID,
            "org_did": _OWNER_DID,
            "created_at": now,
        }
        # insert_row handles upsert behavior for vertex_id automatically
        kotoba_client.insert_row("vertex_handotai_source", row_dict)
        written += 1
    return {"written": written, "total": len(_WRITERS)}
    return {"written": written, "total": len(_WRITERS)}


# ---------------------------------------------------------------------------
# handotai.collect.rssAll
# ---------------------------------------------------------------------------

async def task_handotai_collect_rss_all(maxPerSource: int = 20) -> dict:
    """Fetch all 6 RSS feeds, parse articles, write to vertex_handotai_article."""
    cap = max(1, min(int(maxPerSource or 20), 50))
    total_written = 0
    total_skipped = 0
    errors: list[str] = []
    now = _utc_now()

    async with aiohttp.ClientSession(
        headers={"User-Agent": "handotai.etzhayyim.com/1.0 contact@etzhayyim.com"},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as session:
        for w in _WRITERS:
            try:
                async with session.get(w["url"]) as resp:
                    if resp.status != 200:
                        errors.append(f"{w['source_id']}:http{resp.status}")
                        continue
                    body = await resp.read()
            except Exception as e:
                errors.append(f"{w['source_id']}:{type(e).__name__}")
                continue

            articles = _parse_feed(body, w["name"], w["language"], w["category"])
            articles = articles[:cap]

            kotoba_client = get_kotoba_client()
            for art in articles:
                vid = _art_vid(art["article_id"])
                row_dict = {
                    "vertex_id": vid,
                    "article_id": art["article_id"],
                    "source_url": art["source_url"],
                    "source_name": art["source_name"],
                    "source_lang": art["source_lang"],
                    "title_original": art["title_original"],
                    "title_ja": art["title_ja"],
                    "title_en": art["title_en"],
                    "summary_original": art["summary_original"],
                    "summary_ja": art["summary_ja"],
                    "summary_en": art["summary_en"],
                    "category": art["category"],
                    "subcategory": art["subcategory"],
                    "entities": art["entities"],
                    "tags": art["tags"],
                    "sentiment": art["sentiment"],
                    "importance": art["importance"],
                    "published_at": art["published_at"],
                    "crawled_at": now,
                    "visibility": art["visibility"],
                    "writer_did": art["writer_did"],
                    "actor_did": _OWNER_DID,
                    "org_did": _OWNER_DID,
                    "created_at": now,
                }
                # insert_row handles upsert behavior for vertex_id automatically
                try:
                    kotoba_client.insert_row("vertex_handotai_article", row_dict)
                    total_written += 1
                except Exception as e:
                    # R0: insert_row handles upsert internally, but we catch generic exceptions
                    #     for other potential errors.
                    total_skipped += 1 # Assume any error in insert_row for an existing primary key means skipped.
                    errors.append(f"insert:{art['article_id']}:{e!s:.60}")

    return {"written": total_written, "skipped": total_skipped, "errors": errors[:10]}


# ---------------------------------------------------------------------------
# handotai.generate.digest
# ---------------------------------------------------------------------------

def task_handotai_generate_digest(date: str = "") -> dict:
    """Read today's articles from vertex_handotai_article, LLM-summarize, upsert digest."""
    if not date:
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    articles: list[dict[str, Any]] = []
    kotoba_client = get_kotoba_client()
    # R0: Datalog `order-by` and `limit` not supported via `q()` shim; applying in Python.
    q_edn = f"""
    [:find ?title_original ?title_ja ?title_en ?category ?importance ?source_lang
     :where
     [?e :vertex/type "vertex_handotai_article"]
     [?e :crawled_at ?crawled_at]
     [(>= ?crawled_at "{date}T00:00:00Z")]
     [(< ?crawled_at "{date}T23:59:59Z")]
     [?e :title_original ?title_original]
     [?e :title_ja ?title_ja]
     [?e :title_en ?title_en]
     [?e :category ?category]
     [?e :importance ?importance]
     [?e :source_lang ?source_lang]]
    """
    raw_results = kotoba_client.q(q_edn)

    processed_articles = []
    for r in raw_results:
        processed_articles.append({
            "title_original": r[0],
            "title_ja": r[1],
            "title_en": r[2],
            "category": r[3],
            "importance": int(r[4]), # Ensure importance is an integer
            "source_lang": r[5],
        })

    # Sort by importance DESC and limit to 50
    articles = sorted(processed_articles, key=lambda x: x.get("importance", 0), reverse=True)[:50]

    if not articles:
        return {"date": date, "articles": 0, "status": "noArticles"}

    lines = []
    for a in articles:
        title = a.get("title_ja") or a.get("title_original") or a.get("title_en") or ""
        cat = a.get("category", "")
        imp = a.get("importance", 3)
        lines.append(f"- [{cat}] {title} (importance:{imp})")

    bullet_text = "\n".join(lines)
    try:
        result = _llm.call_tier(
            "structured",
            "You are a semiconductor industry analyst. Write a concise daily digest in Japanese (3-4 paragraphs). Focus on key trends.",
            f"Date: {date}\nArticles ({len(articles)}):\n{bullet_text}",
            max_tokens=600,
            temperature=0.3,
        )
        summary = result.get("content", "").strip()
    except Exception as e:
        summary = f"[digest generation failed: {e!s:.80}]"

    now = _utc_now()
    vid = _dig_vid(date)
    kotoba_client = get_kotoba_client()
    row_dict = {
        "vertex_id": vid,
        "date": date,
        "total_articles": len(articles),
        "summary_ja": summary,
        "generated_at": now,
        "actor_did": _OWNER_DID,
        "org_did": _OWNER_DID,
        "created_at": now,
    }
    # insert_row handles upsert behavior for vertex_id automatically
    kotoba_client.insert_row("vertex_handotai_digest", row_dict)

    return {"date": date, "articles": len(articles), "status": "generated"}


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(task_type="handotai.seed.writers",    single_value=False, timeout_ms=60_000)(task_handotai_seed_writers)
    worker.task(task_type="handotai.collect.rssAll",  single_value=False, timeout_ms=120_000)(task_handotai_collect_rss_all)
    worker.task(task_type="handotai.generate.digest", single_value=False, timeout_ms=60_000)(task_handotai_generate_digest)
