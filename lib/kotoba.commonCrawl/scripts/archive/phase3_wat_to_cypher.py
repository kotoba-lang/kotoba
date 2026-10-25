#!/usr/bin/env python3
"""Phase 3: WAT → Pattern B DID Cypher (Domain DID + Page/WET AT Record).

Design B: Domain DID (repo) + Page Record + WET Record
  - ~1M domain DIDs (manageable)
  - Pages = AT Records under domain DID (rkey = url_hash)
  - WET chunks = AT Records for RAG embedding (rkey = {url_hash}_{chunk_idx})
  - Link graph = outlinks stored as page record properties + domain-level edges

Output Cypher schema:
  (:DomainDID {did, domain, slug, pageCount, firstSeen, topic})
    -[:HOSTS_PAGE]->(:PageRecord {rkey, url, title, language, contentType, outlinkCount, domainDid})
    -[:LINKS_TO]->(:PageRecord)  — cross-domain links
  (:DomainDID)-[:LINKS_TO_DOMAIN]->(:DomainDID)  — aggregated domain link graph
  (:TopicCoordinator {slug})<-[:TAGGED_WITH]-(:DomainDID)  — auto-classified

Resume: checkpoint per WAT file in .phase3_state.json.

Usage:
  python3 scripts/archive/phase3_wat_to_cypher.py --source full [--batch-size 10000] [--resume]
  etzhayyim common-crawler graph --source full --batch-size 10000

Env:
  CC_DOMAIN_FILTER         Domain csv filter (e.g. *.go.jp,nlftp.mlit.go.jp)
  CC_CDX_CACHE_TTL_SEC     CDX cache TTL in seconds (default: 604800)
  CC_CDX_RETRIES           CDX retry count (default: 4)
  CC_CDX_BACKOFF_BASE_SEC  Exponential backoff base seconds (default: 1.5)
"""

import gzip
import hashlib
import json
import logging
import os
import random
import signal
import sys
import time
from collections import Counter, defaultdict
from fnmatch import fnmatch
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from warcio.archiveiterator import ArchiveIterator

# ── Config ──
BASE_DIR = Path(os.environ.get("CC_DATA_DIR", "/Volumes/251220/CC/2603"))
GRAPH_DIR = BASE_DIR / "graph"
STATE_FILE = BASE_DIR / "scripts" / ".phase3_state.json"
CRAWL_ID = os.environ.get("CC_CRAWL_ID", "CC-MAIN-2026-12")
CDX_CACHE_FILE = BASE_DIR / "scripts" / ".phase3_cdx_cache.json"
CDX_CACHE_TTL_SEC = int(os.environ.get("CC_CDX_CACHE_TTL_SEC", str(7 * 24 * 60 * 60)))
CDX_RETRIES = int(os.environ.get("CC_CDX_RETRIES", "4"))
CDX_BACKOFF_BASE_SEC = float(os.environ.get("CC_CDX_BACKOFF_BASE_SEC", "1.5"))

# 14 Topic heuristics (TLD + keyword)
TOPIC_RULES: list[tuple[str, list[str], list[str]]] = [
    ("government", [".gov", ".go.jp", ".gc.ca", ".gov.uk", ".gov.au", ".europa.eu"], ["government", "ministry", "省", "庁"]),
    ("legal", [".courts"], ["court", "law", "legal", "裁判", "判例", "法令"]),
    ("academic", [".edu", ".ac.jp", ".ac.uk"], ["university", "research", "journal", "大学", "学会"]),
    ("science", [], ["science", "biology", "physics", "chemistry", "genome", "ncbi", "pubmed"]),
    ("technology", [".io", ".dev"], ["github", "stackoverflow", "developer", "api", "sdk", "docker"]),
    ("news_media", [], ["news", "times", "post", "herald", "ニュース", "新聞"]),
    ("health", [], ["health", "medical", "hospital", "pharma", "who.int", "医療", "厚生"]),
    ("commerce", [".shop", ".store"], ["shop", "buy", "price", "amazon", "ebay", "楽天"]),
    ("finance", [".bank"], ["bank", "finance", "invest", "stock", "insurance", "金融", "銀行"]),
    ("security", [], ["security", "cve", "malware", "threat", "vulnerability", "cyber"]),
    ("culture", [".museum"], ["museum", "art", "culture", "heritage", "文化", "芸術"]),
    ("education", [], ["learn", "course", "tutorial", "education", "学習", "教育"]),
    ("infrastructure", [], ["transport", "railway", "energy", "telecom", "道路", "鉄道"]),
    ("jp_classics", [".aozora.gr.jp"], ["青空文庫", "古典", "文学"]),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "scripts" / "phase3.log"),
    ],
)
log = logging.getLogger(__name__)

shutdown_requested = False


def handle_signal(signum, frame):
    global shutdown_requested
    shutdown_requested = True


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def extract_domain(url: str) -> str:
    try:
        h = urlparse(url).hostname
        return h.lower() if h else ""
    except Exception:
        return ""


def domain_to_slug(domain: str) -> str:
    return domain.replace(".", "-").replace("_", "-")


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def classify_topic(domain: str, title: str) -> str:
    """Auto-classify domain+title into topic slug via heuristics."""
    dl = domain.lower()
    tl = (title or "").lower()
    for slug, tld_patterns, keywords in TOPIC_RULES:
        for tld in tld_patterns:
            if dl.endswith(tld) or tld in dl:
                return slug
        for kw in keywords:
            if kw in dl or kw in tl:
                return slug
    return ""


def parse_domain_filters(raw: str) -> list[str]:
    if not raw:
        return []
    filters = []
    for part in raw.split(","):
        p = part.strip().lower()
        if p:
            filters.append(p)
    return filters


def domain_matches(domain: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    dl = (domain or "").lower()
    if not dl:
        return False
    for pat in patterns:
        p = pat.lower()
        if "*" in p or "?" in p:
            if fnmatch(dl, p):
                return True
            # "*.go.jp" should also match nested hosts
            if p.startswith("*.") and (dl == p[2:] or dl.endswith("." + p[2:])):
                return True
        else:
            if dl == p or dl.endswith("." + p):
                return True
    return False


def _domain_to_cdx_url(domain_pat: str) -> str:
    p = domain_pat.strip()
    if not p:
        return ""
    if "/" in p:
        u = p
    else:
        u = p + "/*"
    return f"https://index.commoncrawl.org/{CRAWL_ID}-index?url={u}&output=json&fl=filename"


def load_cdx_cache() -> dict:
    if not CDX_CACHE_FILE.exists():
        return {}
    try:
        with open(CDX_CACHE_FILE) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as e:
        log.warning(f"CDX cache load failed: {e}")
    return {}


def save_cdx_cache(cache: dict):
    try:
        CDX_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CDX_CACHE_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(cache, f)
        os.replace(tmp, CDX_CACHE_FILE)
    except Exception as e:
        log.warning(f"CDX cache save failed: {e}")


def _fetch_cdx_filenames_with_retry(query_pattern: str, timeout_sec: int, retries: int) -> set[str]:
    query_files = set()
    url = _domain_to_cdx_url(query_pattern)
    if not url:
        return query_files

    for attempt in range(1, max(1, retries) + 1):
        try:
            req = Request(url, headers={"User-Agent": "etzhayyim-cc-phase3/1.1"})
            with urlopen(req, timeout=timeout_sec) as resp:
                for raw in resp:
                    try:
                        row = json.loads(raw.decode("utf-8", errors="replace"))
                    except Exception:
                        continue
                    fname = str(row.get("filename", "")).strip()
                    if not fname:
                        continue
                    base = os.path.basename(fname)
                    # Index filename is usually *.warc.gz; local WAT files are *.warc.wat.gz.
                    if base.endswith(".warc.gz"):
                        query_files.add(base.replace(".warc.gz", ".warc.wat.gz"))
                    elif base.endswith(".warc.wat.gz"):
                        query_files.add(base)
            return query_files
        except Exception as e:
            if attempt >= retries:
                log.warning(f"CDX lookup failed for pattern={query_pattern} after {attempt} attempts: {e}")
                return set()
            backoff = CDX_BACKOFF_BASE_SEC * (2 ** (attempt - 1))
            jitter = random.uniform(0, max(0.25, backoff * 0.25))
            sleep_sec = backoff + jitter
            log.warning(
                f"CDX lookup retry {attempt}/{retries} for pattern={query_pattern}: {e}; "
                f"sleeping {sleep_sec:.2f}s"
            )
            time.sleep(sleep_sec)
    return set()


def fetch_wat_basename_candidates(domain_filters: list[str], timeout_sec: int = 20) -> set[str]:
    """Fetch candidate WAT basenames for domains via Common Crawl Index (CDX)."""
    if not domain_filters:
        return set()

    now = int(time.time())
    cache = load_cdx_cache()
    cache_changed = False
    candidates = set()
    for pat in domain_filters:
        # CDX may not support wildcard as expected for all patterns; try both pattern and plain host fallback.
        query_patterns = [pat]
        if pat.startswith("*."):
            query_patterns.append(pat[2:])
        for qp in query_patterns:
            cache_key = f"{CRAWL_ID}:{qp}"
            cached = cache.get(cache_key)
            if isinstance(cached, dict):
                ts = int(cached.get("ts", 0))
                files = cached.get("files", [])
                if now - ts <= CDX_CACHE_TTL_SEC and isinstance(files, list):
                    candidates.update(f for f in files if isinstance(f, str) and f)
                    log.info(
                        f"CDX cache hit pattern={qp}: {len(files)} files (ttl_remaining={CDX_CACHE_TTL_SEC - (now - ts)}s)"
                    )
                    continue

            files = _fetch_cdx_filenames_with_retry(qp, timeout_sec=timeout_sec, retries=CDX_RETRIES)
            if files:
                candidates.update(files)
            cache[cache_key] = {"ts": now, "files": sorted(files)}
            cache_changed = True

    if cache_changed:
        save_cdx_cache(cache)
    return candidates


def parse_wat_record(content: bytes) -> dict | None:
    """Parse WAT JSON envelope → page metadata."""
    try:
        text = content.decode("utf-8", errors="replace")
        idx = text.find("{")
        if idx < 0:
            return None
        data = json.loads(text[idx:])
        envelope = data.get("Envelope", {})
        payload = envelope.get("Payload-Metadata", {})
        http_meta = payload.get("HTTP-Response-Metadata", {})
        html_meta = http_meta.get("HTML-Metadata", {})
        headers = http_meta.get("Headers", {})
        if not isinstance(headers, dict):
            headers = {}

        target_uri = envelope.get("WARC-Header-Metadata", {}).get("WARC-Target-URI", "")
        if not target_uri or not target_uri.startswith("http"):
            return None

        title = html_meta.get("Head", {}).get("Title", "") if isinstance(html_meta, dict) else ""

        metas = html_meta.get("Head", {}).get("Metas", []) if isinstance(html_meta, dict) else []
        if not isinstance(metas, list):
            metas = []
        og_desc = ""
        language = ""
        for m in metas:
            if not isinstance(m, dict):
                continue
            prop = m.get("property", "")
            name = m.get("name", "").lower()
            if prop == "og:description":
                og_desc = m.get("content", "")[:500]
            if name in ("language", "lang", "content-language"):
                language = m.get("content", "")[:10]
        if not language:
            language = headers.get("Content-Language", "")[:10]

        links = html_meta.get("Links", []) if isinstance(html_meta, dict) else []
        if not isinstance(links, list):
            links = []
        outlinks = []
        for lnk in links:
            if isinstance(lnk, dict):
                href = lnk.get("url", "")
                if href and isinstance(href, str) and href.startswith("http"):
                    outlinks.append(href)

        return {
            "url": target_uri,
            "domain": extract_domain(target_uri),
            "title": (title or "")[:500] if isinstance(title, str) else "",
            "description": og_desc,
            "language": language,
            "status_code": str(headers.get("HTTP-Status-Code", "")),
            "content_type": headers.get("Content-Type", "")[:100],
            "outlinks": outlinks[:500],
            "outlink_count": len(outlinks),
        }
    except Exception:
        return None


def esc(s) -> str:
    if not isinstance(s, str):
        return str(s)
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")


def generate_cypher_batch(pages: list[dict], batch_id: int, domain_topics: dict[str, str]) -> str:
    """Generate Pattern B Cypher."""
    stmts = []
    seen_domains = set()
    domain_links = Counter()

    for page in pages:
        if not page["url"] or not page["domain"]:
            continue

        domain = page["domain"]
        slug = domain_to_slug(domain)
        did = f"did:web:site.etzhayyim.com:{slug}"
        rkey = url_hash(page["url"])

        # DomainDID
        if domain not in seen_domains:
            seen_domains.add(domain)
            topic = domain_topics.get(domain, "")
            topic_prop = f', d.topic = "{esc(topic)}"' if topic else ""
            stmts.append(
                f'MERGE (d:DomainDID {{did: "{esc(did)}"}}) '
                f'ON CREATE SET d.domain = "{esc(domain)}", d.slug = "{esc(slug)}", '
                f'd.firstSeen = datetime(), d.pageCount = 0{topic_prop} '
                f'ON MATCH SET d.pageCount = d.pageCount + 1'
            )
            if topic:
                stmts.append(f'MERGE (t:TopicCoordinator {{slug: "{esc(topic)}"}})')
                stmts.append(
                    f'MATCH (d:DomainDID {{did: "{esc(did)}"}}), '
                    f'(t:TopicCoordinator {{slug: "{esc(topic)}"}}) '
                    f'MERGE (d)-[:TAGGED_WITH]->(t)'
                )

        # PageRecord
        stmts.append(
            f'MERGE (p:PageRecord {{rkey: "{rkey}"}}) '
            f'ON CREATE SET p.url = "{esc(page["url"][:2000])}", '
            f'p.domainDid = "{esc(did)}", p.domain = "{esc(domain)}", '
            f'p.title = "{esc(page["title"][:200])}", '
            f'p.description = "{esc(page["description"][:300])}", '
            f'p.language = "{esc(page["language"])}", '
            f'p.contentType = "{esc(page["content_type"])}", '
            f'p.statusCode = "{esc(page["status_code"])}", '
            f'p.outlinkCount = {page["outlink_count"]}, '
            f'p.crawl = "{CRAWL_ID}"'
        )

        # HOSTS_PAGE
        stmts.append(
            f'MATCH (d:DomainDID {{did: "{esc(did)}"}}), (p:PageRecord {{rkey: "{rkey}"}}) '
            f'MERGE (d)-[:HOSTS_PAGE]->(p)'
        )

        # Cross-domain page links (sample 10)
        for outlink in page["outlinks"][:10]:
            out_domain = extract_domain(outlink)
            if out_domain and out_domain != domain:
                out_rkey = url_hash(outlink)
                out_slug = domain_to_slug(out_domain)
                out_did = f"did:web:site.etzhayyim.com:{out_slug}"
                stmts.append(
                    f'MERGE (tp:PageRecord {{rkey: "{out_rkey}"}}) '
                    f'ON CREATE SET tp.url = "{esc(outlink[:2000])}", '
                    f'tp.domainDid = "{esc(out_did)}", tp.domain = "{esc(out_domain)}"'
                )
                stmts.append(
                    f'MATCH (s:PageRecord {{rkey: "{rkey}"}}), (t:PageRecord {{rkey: "{out_rkey}"}}) '
                    f'MERGE (s)-[:LINKS_TO]->(t)'
                )
                domain_links[(did, out_did)] += 1

    # Domain-level link edges
    for (src, dst), count in domain_links.items():
        if count >= 2:
            stmts.append(f'MERGE (sd:DomainDID {{did: "{esc(src)}"}})')
            stmts.append(f'MERGE (td:DomainDID {{did: "{esc(dst)}"}})')
            stmts.append(
                f'MATCH (sd:DomainDID {{did: "{esc(src)}"}}), (td:DomainDID {{did: "{esc(dst)}"}}) '
                f'MERGE (sd)-[r:LINKS_TO_DOMAIN]->(td) '
                f'ON CREATE SET r.count = {count} ON MATCH SET r.count = r.count + {count}'
            )

    return "\n".join(stmts)


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"files_done": [], "batch_id": 0, "total_pages": 0, "total_domains": 0}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def process_wat_files(source_dir: Path, batch_size: int, resume: bool, domain_filters: list[str]):
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state() if resume else {"files_done": [], "batch_id": 0, "total_pages": 0, "total_domains": 0}
    files_done = set(state["files_done"])
    batch_id = state["batch_id"]

    wat_files = sorted(source_dir.rglob("*.warc.wat.gz"))
    remaining = [f for f in wat_files if f.name not in files_done]

    # Pre-filter candidate files via Common Crawl Index to avoid full WAT sweep.
    # This is best-effort: if index lookup fails, we continue with local filtering only.
    if domain_filters:
        before = len(remaining)
        cdx_candidates = fetch_wat_basename_candidates(domain_filters)
        if cdx_candidates:
            remaining = [f for f in remaining if f.name in cdx_candidates]
            log.info(
                f"Domain prefilter via CDX: filters={domain_filters}, "
                f"candidate_files={len(cdx_candidates)}, selected={len(remaining)}/{before}"
            )
        else:
            log.warning(
                f"Domain prefilter via CDX returned no candidates for {domain_filters}; "
                f"falling back to record-level domain filtering (may scan many files)"
            )
    log.info(
        f"WAT files: {len(wat_files)} total, {len(remaining)} remaining, "
        f"resume batch_id={batch_id}, domain_filters={domain_filters or ['<none>']}"
    )

    domain_stats = Counter()
    domain_titles = defaultdict(list)
    domain_topics = {}
    batch_pages = []

    for fi, wat_file in enumerate(remaining):
        if shutdown_requested:
            break

        log.info(f"Processing {fi + 1}/{len(remaining)}: {wat_file.name}")
        try:
            with open(wat_file, "rb") as fh:
                for record in ArchiveIterator(fh):
                    if shutdown_requested:
                        break
                    if record.rec_type not in ("metadata", "response"):
                        continue
                    content = record.content_stream().read()
                    page = parse_wat_record(content)
                    if not page or not page["url"] or not page["domain"]:
                        continue
                    if domain_filters and not domain_matches(page["domain"], domain_filters):
                        continue

                    state["total_pages"] += 1
                    domain = page["domain"]
                    domain_stats[domain] += 1

                    if domain not in domain_topics:
                        topic = classify_topic(domain, page["title"])
                        if topic:
                            domain_topics[domain] = topic

                    if len(domain_titles[domain]) < 5 and page["title"]:
                        domain_titles[domain].append(page["title"][:100])

                    batch_pages.append(page)

                    if len(batch_pages) >= batch_size:
                        cypher = generate_cypher_batch(batch_pages, batch_id, domain_topics)
                        cypher_file = GRAPH_DIR / f"batch_{batch_id:06d}.cypher"
                        with open(cypher_file, "w") as f:
                            f.write(cypher)
                        log.info(f"  Batch {batch_id}: {len(batch_pages)} pages → {cypher_file.name}")
                        batch_pages = []
                        batch_id += 1

        except Exception as e:
            log.error(f"Error: {wat_file.name}: {e}")

        state["files_done"].append(wat_file.name)
        state["batch_id"] = batch_id
        state["total_domains"] = len(domain_stats)
        files_done.add(wat_file.name)

        if (fi + 1) % 50 == 0:
            save_state(state)
            log.info(f"Checkpoint: {fi+1}/{len(remaining)}, pages={state['total_pages']}, domains={len(domain_stats)}, batches={batch_id}")

    if batch_pages:
        cypher = generate_cypher_batch(batch_pages, batch_id, domain_topics)
        with open(GRAPH_DIR / f"batch_{batch_id:06d}.cypher", "w") as f:
            f.write(cypher)
        batch_id += 1

    state["batch_id"] = batch_id
    save_state(state)

    # Domain JSONL for Phase 4
    with gzip.open(GRAPH_DIR / "domains_for_classification.jsonl.gz", "wt") as f:
        for domain, count in domain_stats.most_common():
            if domain:
                f.write(json.dumps({
                    "domain": domain,
                    "pageCount": count,
                    "sampleTitles": domain_titles.get(domain, []),
                    "topic": domain_topics.get(domain, ""),
                }) + "\n")

    topic_dist = Counter(domain_topics.values())
    stats = {
        "crawl": CRAWL_ID,
        "totalPages": state["total_pages"],
        "uniqueDomains": len(domain_stats),
        "cypherBatches": batch_id,
        "topicDistribution": topic_dist.most_common(),
        "topDomains": domain_stats.most_common(200),
    }
    with open(GRAPH_DIR / "link_graph_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    log.info(f"Done: {state['total_pages']} pages, {len(domain_stats)} domains, {batch_id} batches, {len(domain_topics)} topic-classified")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase 3: WAT → Pattern B DID Cypher")
    parser.add_argument("--source", choices=["full", "filtered"], default="full")
    parser.add_argument("--batch-size", type=int, default=10000)
    parser.add_argument("--domain", type=str, default=os.environ.get("CC_DOMAIN_FILTER", ""), help="domain filter csv (e.g. *.go.jp,nlftp.mlit.go.jp)")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    source_dir = BASE_DIR / ("filtered/wat" if args.source == "filtered" else "wat-full")
    domain_filters = parse_domain_filters(args.domain)
    log.info(f"Phase 3 Pattern B: source={source_dir}, batch_size={args.batch_size}, domain_filters={domain_filters or ['<none>']}")
    process_wat_files(source_dir, args.batch_size, resume=not args.no_resume, domain_filters=domain_filters)
