from __future__ import annotations


import hashlib
import html as _html
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as _ET
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

# ── Constants ──────────────────────────────────────────────────────────────

_OWNER_DID = "did:web:news.etzhayyim.com"
_FETCH_TIMEOUT = 30
_MAX_BODY_BYTES = 1_000_000
_MAX_ARTICLES = 30
_MAX_SNIPPET = 2_000
_UA = "etzhayyim-ir-scrape/1.0 (mailto:jun@etzhayyim.com)"

# Built-in seed: (company_name, company_name_ja, ir_url, exchange, securities_code, country_code)
# TSE Prime + major US NASDAQ. LEI populated later via GLEIF bulk ingest.
_SEED_COMPANIES: list[tuple[str, str, str, str, str, str]] = [
    # ── Japan TSE Prime ──────────────────────────────────────────────────
    ("Toyota Motor Corporation",          "トヨタ自動車",               "https://global.toyota/jp/ir/library/",                    "TSE",    "7203", "JP"),
    ("Sony Group Corporation",            "ソニーグループ",              "https://www.sony.com/en/SonyInfo/News/Press/",             "TSE",    "6758", "JP"),
    ("SoftBank Group Corp.",              "ソフトバンクグループ",        "https://group.softbank/en/news/press/",                   "TSE",    "9984", "JP"),
    ("Nippon Telegraph and Telephone",    "日本電信電話",                "https://group.ntt/jp/newsrelease/",                       "TSE",    "9432", "JP"),
    ("Honda Motor Co., Ltd.",             "本田技研工業",                "https://www.honda.co.jp/news/",                           "TSE",    "7267", "JP"),
    ("Panasonic Holdings Corporation",    "パナソニックホールディングス", "https://news.panasonic.com/jp/",                          "TSE",    "6752", "JP"),
    ("Canon Inc.",                        "キヤノン",                   "https://global.canon/ja/news/",                           "TSE",    "7751", "JP"),
    ("Hitachi, Ltd.",                     "日立製作所",                  "https://www.hitachi.co.jp/New/cnews/",                    "TSE",    "6501", "JP"),
    ("Recruit Holdings Co., Ltd.",        "リクルートホールディングス",  "https://recruit-holdings.com/ja/newsroom/",               "TSE",    "6098", "JP"),
    ("Keyence Corporation",               "キーエンス",                 "https://www.keyence.com/news/",                          "TSE",    "6861", "JP"),
    ("Nintendo Co., Ltd.",                "任天堂",                     "https://www.nintendo.co.jp/corporate/release/",           "TSE",    "7974", "JP"),
    ("Fast Retailing Co., Ltd.",          "ファーストリテイリング",      "https://www.fastretailing.com/jp/ir/news/",               "TSE",    "9983", "JP"),
    ("Shin-Etsu Chemical Co., Ltd.",      "信越化学工業",                "https://www.shinetsu.co.jp/jp/news/",                    "TSE",    "4063", "JP"),
    ("Tokyo Electron Limited",            "東京エレクトロン",            "https://www.tel.com/news/",                              "TSE",    "8035", "JP"),
    ("Mitsubishi UFJ Financial Group",    "三菱UFJフィナンシャルグループ","https://ir.mufg.jp/english/news/",                        "TSE",    "8306", "JP"),
    ("Mitsubishi Corporation",            "三菱商事",                   "https://www.mitsubishicorp.com/jp/ja/pr/",                "TSE",    "8058", "JP"),
    ("KDDI Corporation",                  "KDDI",                      "https://newsroom.kddi.com/",                              "TSE",    "9433", "JP"),
    ("Nippon Steel Corporation",          "日本製鉄",                   "https://www.nipponsteel.com/news/",                      "TSE",    "5401", "JP"),
    ("Denso Corporation",                 "デンソー",                   "https://www.denso.com/global/en/news/press-releases/",   "TSE",    "6902", "JP"),
    ("Sumitomo Mitsui Financial Group",   "三井住友フィナンシャルグループ","https://www.smfg.co.jp/news/",                           "TSE",    "8316", "JP"),
    ("Mizuho Financial Group",            "みずほフィナンシャルグループ", "https://www.mizuhogroup.com/news",                       "TSE",    "8411", "JP"),
    ("Daiichi Sankyo Co., Ltd.",          "第一三共",                   "https://www.daiichisankyo.co.jp/media/press_release/",   "TSE",    "4568", "JP"),
    ("Takeda Pharmaceutical",             "武田薬品工業",                "https://www.takeda.com/newsroom/press-releases/",        "TSE",    "4502", "JP"),
    ("Fujitsu Limited",                   "富士通",                     "https://www.fujitsu.com/jp/about/resources/news/press-releases/", "TSE", "6702", "JP"),
    ("Murata Manufacturing Co., Ltd.",    "村田製作所",                  "https://corporate.murata.com/ja-jp/newsroom/",           "TSE",    "6981", "JP"),
    ("Renesas Electronics Corporation",   "ルネサスエレクトロニクス",    "https://www.renesas.com/en/about/press-room",            "TSE",    "6723", "JP"),
    ("Lasertec Corporation",              "レーザーテック",              "https://www.lasertec.co.jp/news/",                       "TSE",    "6920", "JP"),
    ("Disco Corporation",                 "ディスコ",                   "https://www.disco.co.jp/jp/news/",                       "TSE",    "6146", "JP"),
    ("Advantest Corporation",             "アドバンテスト",              "https://www.advantest.com/ja/news/",                    "TSE",    "6857", "JP"),
    # ── Japan TSE Prime (additional) ────────────────────────────────────────
    ("Komatsu Ltd.",                      "コマツ",                     "https://home.komatsu/jp/press/",                          "TSE",    "6301", "JP"),
    ("Daikin Industries, Ltd.",           "ダイキン工業",                "https://www.daikin.com/news/",                           "TSE",    "6367", "JP"),
    ("Nidec Corporation",                 "ニデック",                   "https://www.nidec.com/en/ir/news/",                      "TSE",    "6594", "JP"),
    ("Kyocera Corporation",               "京セラ",                    "https://global.kyocera.com/news/",                       "TSE",    "6971", "JP"),
    ("Eisai Co., Ltd.",                   "エーザイ",                   "https://www.eisai.co.jp/news/",                          "TSE",    "4523", "JP"),
    ("Shionogi & Co., Ltd.",              "塩野義製薬",                 "https://www.shionogi.com/global/en/news/",               "TSE",    "4507", "JP"),
    ("Kubota Corporation",                "クボタ",                    "https://www.kubota.co.jp/news/",                         "TSE",    "6326", "JP"),
    ("ITOCHU Corporation",                "伊藤忠商事",                 "https://www.itochu.co.jp/en/news/press/",                "TSE",    "8001", "JP"),
    ("Mitsui & Co., Ltd.",                "三井物産",                   "https://www.mitsui.com/jp/ja/release/",                  "TSE",    "8031", "JP"),
    ("Sumitomo Corporation",              "住友商事",                   "https://www.sumitomocorp.com/en/jp/news/",               "TSE",    "8053", "JP"),
    ("Marubeni Corporation",              "丸紅",                     "https://www.marubeni.com/en/news/",                      "TSE",    "8002", "JP"),
    ("Dai-ichi Life Holdings, Inc.",      "第一生命ホールディングス",    "https://www.dai-ichi-life-hd.com/en/news/",              "TSE",    "8750", "JP"),
    ("Olympus Corporation",               "オリンパス",                 "https://www.olympus.co.jp/en/news/",                     "TSE",    "7733", "JP"),
    ("JFE Holdings, Inc.",                "JFEホールディングス",        "https://www.jfe-holdings.co.jp/en/release/",             "TSE",    "5411", "JP"),
    ("SoftBank Corp.",                    "ソフトバンク",               "https://www.softbank.jp/en/corp/news/press/",            "TSE",    "9434", "JP"),
    # ── US NASDAQ / NYSE ──────────────────────────────────────────────────
    ("Apple Inc.",                        "Apple",                     "https://www.apple.com/newsroom/rss-feed.rss",            "NASDAQ", "AAPL", "US"),
    ("Microsoft Corporation",             "Microsoft",                 "https://news.microsoft.com/feed/",                      "NASDAQ", "MSFT", "US"),
    ("NVIDIA Corporation",                "NVIDIA",                   "https://nvidianews.nvidia.com/rss/news",                 "NASDAQ", "NVDA", "US"),
    ("Alphabet Inc.",                     "Google",                   "https://blog.google/rss/",                              "NASDAQ", "GOOGL","US"),
    ("Meta Platforms, Inc.",              "Meta",                     "https://about.fb.com/news/feed/",                       "NASDAQ", "META", "US"),
    ("Amazon.com, Inc.",                  "Amazon",                   "https://press.aboutamazon.com/",                        "NASDAQ", "AMZN", "US"),
    ("Tesla, Inc.",                       "Tesla",                    "https://ir.tesla.com/news",                             "NASDAQ", "TSLA", "US"),
    ("Taiwan Semiconductor Mfg. Co.",    "TSMC",                     "https://ir.tsmc.com/english/shareholders/press-releases","NYSE",  "TSM",  "TW"),
    ("Samsung Electronics Co., Ltd.",    "サムスン電子",               "https://news.samsung.com/global/feed",                  "KRX",    "005930","KR"),
    ("ASML Holding N.V.",                "ASML",                     "https://www.asml.com/en/news/press-releases/",          "NASDAQ", "ASML", "NL"),
    # ── US NASDAQ / NYSE (additional) ────────────────────────────────────────
    ("Intel Corporation",                "インテル",                   "https://newsroom.intel.com/feed/",                       "NASDAQ", "INTC", "US"),
    ("Qualcomm Incorporated",            "クアルコム",                 "https://www.qualcomm.com/news",                          "NASDAQ", "QCOM", "US"),
    ("Advanced Micro Devices, Inc.",     "AMD",                       "https://ir.amd.com/news-releases",                       "NASDAQ", "AMD",  "US"),
    ("International Business Machines", "IBM",                       "https://newsroom.ibm.com/",                              "NYSE",   "IBM",  "US"),
    ("Arm Holdings plc",                 "Arm",                       "https://newsroom.arm.com/",                              "NASDAQ", "ARM",  "US"),
    ("Salesforce, Inc.",                 "セールスフォース",            "https://www.salesforce.com/news/press-releases/",        "NYSE",   "CRM",  "US"),
    # ── Europe ───────────────────────────────────────────────────────────────
    ("SAP SE",                           "SAP",                       "https://news.sap.com/feed/",                             "NYSE",   "SAP",  "DE"),
    ("Siemens AG",                       "シーメンス",                 "https://press.siemens.com/global/en/rss.xml",            "OTC",    "SIEGY","DE"),
    ("Infineon Technologies AG",         "インフィニオン",             "https://www.infineon.com/cms/en/about-infineon/press/press-releases/","OTC","IFNNY","DE"),
    ("STMicroelectronics N.V.",          "STマイクロ",                 "https://newsroom.st.com/",                               "NYSE",   "STM",  "CH"),
    # ── Korea KRX (additional) ───────────────────────────────────────────────
    ("SK Hynix Inc.",                    "SKハイニックス",             "https://news.skhynix.com/news/",                         "KRX",    "000660","KR"),
    ("Hyundai Motor Company",            "現代自動車",                 "https://www.hyundai.com/worldwide/en/news",              "KRX",    "005380","KR"),
    ("LG Electronics Inc.",              "LGエレクトロニクス",         "https://www.lgcorp.com/media/release",                   "KRX",    "066570","KR"),
]

_RSS_LINK_RE = re.compile(
    r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']'
    r'|<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/(?:rss|atom)\+xml["\']',
    re.IGNORECASE,
)
_NEWS_PATH_RE = re.compile(
    r"(?:press[_-]?release|news[_-]?release|newsroom|pressroom|ir[/-]news"
    r"|プレスリリース|ニュースリリース|お知らせ|適時開示|investor-?relations/news)",
    re.IGNORECASE,
)
_KIND_KW: dict[str, list[str]] = {
    "earnings":     ["決算", "業績", "earnings", "quarterly result", "annual result", "profit", "revenue", "EPS", "fiscal"],
    "acquisition":  ["買収", "合併", "M&A", "acquisition", "merger", "takeover", "TOB", "tender offer"],
    "dividend":     ["配当", "dividend", "distribution"],
    "personnel":    ["人事", "役員", "代表取締役", "appointment", "resignation", "CEO", "CFO", "board"],
    "partnership":  ["提携", "協業", "partnership", "collaboration", "joint venture", "alliance", "MOU"],
    "product":      ["新製品", "発売", "launch", "new product", "新機能"],
}
_ATOM_NS = "http://www.w3.org/2005/Atom"

# ── Helpers ────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _company_vid(exchange: str, sec_code: str) -> str:
    h = hashlib.sha256(f"{exchange}:{sec_code}".encode()).hexdigest()[:16]
    return f"at://did:web:news.etzhayyim.com/com.etzhayyim.apps.irScrape.company/{h}"


def _run_vid(company_vid: str, ts: str) -> str:
    key = f"{company_vid}:{ts}"
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f"at://did:web:news.etzhayyim.com/com.etzhayyim.apps.irScrape.run/{h}"


def _pr_vid(url: str) -> str:
    h = hashlib.sha256(url.encode()).hexdigest()[:20]
    return f"at://did:web:news.etzhayyim.com/com.etzhayyim.apps.irScrape.pressrelease/{h}"


def _fetch(url: str, timeout: int = _FETCH_TIMEOUT) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(_MAX_BODY_BYTES)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


def _discover_rss(body: bytes, base: str) -> str | None:
    text = body.decode("utf-8", errors="replace")
    m = _RSS_LINK_RE.search(text)
    if m:
        href = m.group(1) or m.group(2)
        return urllib.parse.urljoin(base, href)
    return None


def _parse_rss(body: bytes, base: str) -> list[dict[str, str]]:
    try:
        root = _ET.fromstring(body)
    except Exception:
        return []
    items: list[dict[str, str]] = []
    for el in root.iter("item"):  # RSS 2.0
        url = (el.findtext("link") or "").strip()
        if not url:
            continue
        items.append({
            "title": (el.findtext("title") or "").strip()[:500],
            "url": urllib.parse.urljoin(base, url),
            "published_raw": (el.findtext("pubDate") or el.findtext("date") or "").strip(),
            "snippet": _html.unescape((el.findtext("description") or ""))[:_MAX_SNIPPET].strip(),
        })
    for el in root.iter(f"{{{_ATOM_NS}}}entry"):  # Atom
        link_el = el.find(f"{{{_ATOM_NS}}}link")
        url = (link_el.get("href", "") if link_el is not None else "").strip()
        if not url:
            continue
        items.append({
            "title": (el.findtext(f"{{{_ATOM_NS}}}title") or "").strip()[:500],
            "url": urllib.parse.urljoin(base, url),
            "published_raw": (el.findtext(f"{{{_ATOM_NS}}}published") or el.findtext(f"{{{_ATOM_NS}}}updated") or "").strip(),
            "snippet": _html.unescape((el.findtext(f"{{{_ATOM_NS}}}summary") or ""))[:_MAX_SNIPPET].strip(),
        })
    return items[:_MAX_ARTICLES]


def _extract_news_links(body: bytes, base: str) -> list[dict[str, str]]:
    text = body.decode("utf-8", errors="replace")
    seen: set[str] = set()
    found: list[dict[str, str]] = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\'#][^"\']*)["\'][^>]*>(.*?)</a>', text, re.IGNORECASE | re.DOTALL):
        href = m.group(1).strip()
        anchor = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        full = urllib.parse.urljoin(base, href)
        if full in seen:
            continue
        if _NEWS_PATH_RE.search(full) or _NEWS_PATH_RE.search(anchor):
            seen.add(full)
            found.append({"url": full, "title": anchor[:200], "snippet": "", "published_raw": ""})
    return found[:_MAX_ARTICLES]


def _classify(title: str, snippet: str) -> str:
    txt = (title + " " + snippet).lower()
    for kind, kws in _KIND_KW.items():
        if any(k.lower() in txt for k in kws):
            return kind
    return "other"


def _parse_date(raw: str) -> str:
    raw = raw.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    m = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", raw)
    if m:
        months = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                  "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
        d, mon, y = int(m.group(1)), months.get(m.group(2), 1), m.group(3)
        return f"{y}-{mon:02d}-{d:02d}"
    return _utc_now()[:10]


def _insert_ignore(table: str, row: dict[str, Any]) -> int:
    row = {k: v for k, v in row.items() if v is not None}
    if not row.get("vertex_id"):
        return 0 # `insert_row` requires vertex_id for upsert logic

    client = get_kotoba_client()
    return client.insert_row(table, row)


def _upsert(table: str, row: dict[str, Any]) -> None:
    row = {k: v for k, v in row.items() if v is not None}
    # `insert_row` handles upsert logic based on the identity column (e.g., vertex_id)
    # The explicit DELETE is no longer needed.
    get_kotoba_client().insert_row(table, row)


# ── Task: queue seeds ──────────────────────────────────────────────────────

def task_ir_scrape_queue_seeds(
    maxSeeds: int = 200,
    **_: Any,
) -> dict[str, Any]:
    now = _utc_now()
    companies_added = 0
    queued = 0
    skipped = 0

    for name, name_ja, ir_url, exchange, sec_code, country in _SEED_COMPANIES[:int(maxSeeds)]:
        vid = _company_vid(exchange, sec_code)
        ir_host = urllib.parse.urlparse(ir_url).netloc

        companies_added += _insert_ignore("vertex_ir_company", {
            "vertex_id": vid,
            "owner_did": _OWNER_DID,
            "company_name": name,
            "company_name_ja": name_ja,
            "ir_url": ir_url,
            "ir_host": ir_host,
            "exchange": exchange,
            "securities_code": sec_code,
            "country_code": country,
            "ir_status": "active",
            "ir_crawl_interval_hours": 6,
            "sensitivity_ord": 1,
            "created_at": now,
        })

        # Skip if a queued or running run already exists
        client = get_kotoba_client()
        runs = client.select_where(
            "vertex_ir_scraper_run",
            "company_vertex_id",
            vid,
            columns=["status"],
            limit=2000 # R0: arbitrary limit, then filter in python
        )
        in_flight = 0
        for r in runs:
            if r.get("status") in ("queued", "running"):
                in_flight += 1

        if in_flight:
            skipped += 1
            continue

        _upsert("vertex_ir_scraper_run", {
            "vertex_id": _run_vid(vid, now),
            "owner_did": _OWNER_DID,
            "company_vertex_id": vid,
            "ir_url": ir_url,
            "status": "queued",
            "queued_at": now,
            "sensitivity_ord": 1,
            "created_at": now,
        })
        queued += 1

    return {"ok": True, "queued": queued, "skipped": skipped, "companiesAdded": companies_added}


# ── Task: process queue ────────────────────────────────────────────────────

_STALE_RUNNING_TIMEOUT_SEC = 600  # reclaim runs stuck in 'running' > 10 min


def task_ir_scrape_process_queue(
    maxRuns: int = 5,
    fetchTimeoutSec: int = _FETCH_TIMEOUT,
    **_: Any,
) -> dict[str, Any]:
    now = _utc_now()

    # Reclaim runs stuck in 'running' for longer than the stale timeout.
    client = get_kotoba_client()
    # Reclaim runs stuck in 'running' for longer than the stale timeout.
    stale_cutoff = datetime.now(timezone.utc) - datetime.timedelta(
        seconds=_STALE_RUNNING_TIMEOUT_SEC
    )
    stale_cutoff_str = stale_cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    stale_runs_raw = client.select_where(
        "vertex_ir_scraper_run",
        "status",
        "running",
        columns=["vertex_id", "company_vertex_id", "ir_url", "started_at"],
        limit=2000 # R0: arbitrary limit, then filter in python
    )
    stale = []
    for r in stale_runs_raw:
        if r.get("started_at") and r["started_at"] < stale_cutoff_str:
            stale.append(r)
        if len(stale) >= 20: # Apply the limit as well
            break
    for s in stale:
        _upsert("vertex_ir_scraper_run", {
            "vertex_id": s["vertex_id"],
            "owner_did": _OWNER_DID,
            "company_vertex_id": s.get("company_vertex_id") or "",
            "ir_url": s.get("ir_url") or "",
            "status": "failed",
            "error_message": "stale running timeout",
            "completed_at": now,
            "sensitivity_ord": 1,
            "created_at": now,
        })

    queued_runs_raw = client.select_where(
        "vertex_ir_scraper_run",
        "status",
        "queued",
        columns=["vertex_id", "company_vertex_id", "ir_url", "queued_at"],
        limit=2000 # R0: arbitrary limit, then sort and limit in python
    )
    # Sort by queued_at ASC, handling NULLS LAST (Python's None is smaller than string, so needs custom sort key)
    # Datalog doesn't have NULLS LAST directly, so we sort by `is None` first.
    runs = sorted(queued_runs_raw, key=lambda x: (x.get("queued_at") is None, x.get("queued_at")))
    runs = runs[:int(maxRuns)]

    processed = 0
    total_inserted = 0
    errors = 0

    for run in runs:
        run_vid: str = run["vertex_id"]
        ir_url: str = run.get("ir_url") or ""
        company_vid: str = run.get("company_vertex_id") or ""

        # Mark as running
        _upsert("vertex_ir_scraper_run", {
            "vertex_id": run_vid,
            "owner_did": _OWNER_DID,
            "company_vertex_id": company_vid,
            "ir_url": ir_url,
            "status": "running",
            "started_at": now,
            "sensitivity_ord": 1,
            "created_at": now,
        })

        try:
            status_code, body = _fetch(ir_url, timeout=int(fetchTimeoutSec))
            if status_code not in (200, 301, 302):
                _upsert("vertex_ir_scraper_run", {
                    "vertex_id": run_vid,
                    "owner_did": _OWNER_DID,
                    "company_vertex_id": company_vid,
                    "ir_url": ir_url,
                    "status": "failed",
                    "error_message": f"HTTP {status_code}",
                    "completed_at": _utc_now(),
                    "sensitivity_ord": 1,
                    "created_at": now,
                })
                errors += 1
                processed += 1
                continue

            rss_url = _discover_rss(body, ir_url)
            articles: list[dict[str, str]]
            method: str

            if rss_url:
                _, feed_body = _fetch(rss_url, timeout=int(fetchTimeoutSec))
                articles = _parse_rss(feed_body, rss_url)
                method = "rss"
            else:
                articles = _extract_news_links(body, ir_url)
                method = "html"

            inserted = 0
            for art in articles:
                url = art.get("url", "")
                if not url:
                    continue
                title = art.get("title", "")
                snippet = art.get("snippet", "")
                pub_raw = art.get("published_raw", "")
                published_at = _parse_date(pub_raw) if pub_raw else now[:10]

                inserted += _insert_ignore("vertex_ir_pressrelease", {
                    "vertex_id": _pr_vid(url),
                    "owner_did": _OWNER_DID,
                    "company_vertex_id": company_vid,
                    "title": title,
                    "url": url,
                    "published_at": published_at,
                    "body_snippet": snippet,
                    "kind": _classify(title, snippet),
                    "method": method,
                    "crawled_at": now,
                    "sensitivity_ord": 1,
                    "created_at": now,
                })

            _upsert("vertex_ir_scraper_run", {
                "vertex_id": run_vid,
                "owner_did": _OWNER_DID,
                "company_vertex_id": company_vid,
                "ir_url": ir_url,
                "ir_rss_url": rss_url,
                "status": "completed",
                "method": method,
                "articles_found": len(articles),
                "articles_inserted": inserted,
                "completed_at": _utc_now(),
                "sensitivity_ord": 1,
                "created_at": now,
            })
            total_inserted += inserted
            processed += 1

        except Exception as exc:
            _upsert("vertex_ir_scraper_run", {
                "vertex_id": run_vid,
                "owner_did": _OWNER_DID,
                "company_vertex_id": company_vid,
                "ir_url": ir_url,
                "status": "failed",
                "error_message": str(exc)[:500],
                "completed_at": _utc_now(),
                "sensitivity_ord": 1,
                "created_at": now,
            })
            errors += 1
            processed += 1

    return {
        "ok": True,
        "processed": processed,
        "inserted": total_inserted,
        "errors": errors,
        "runId": now,
    }


# ── Registration ───────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="irScrape.queueSeeds",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_ir_scrape_queue_seeds)
    worker.task(
        task_type="irScrape.processQueue",
        single_value=False,
        timeout_ms=max(timeout_ms, 300_000),
    )(task_ir_scrape_process_queue)
