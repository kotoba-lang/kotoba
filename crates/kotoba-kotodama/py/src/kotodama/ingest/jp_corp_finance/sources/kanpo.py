from __future__ import annotations

import hashlib
import html.parser
import re
import tempfile
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SOURCE_ID = "kanpo"
BASE_URL = "https://www.kanpo.go.jp"
USER_AGENT = "jp-corp-finance.etzhayyim.com/0.1 contact@etzhayyim.com"


@dataclass(frozen=True)
class KanpoIndexEntry:
    title: str
    page: int
    page_url: str
    issue_path: str
    issue_kind: str
    issue_no: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _AnchorParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._span_class = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: v or "" for k, v in attrs}
        if tag == "a" and attr.get("href"):
            self._current = {"href": attr["href"], "text": "", "date": ""}
        elif tag == "span" and self._current is not None:
            self._span_class = attr.get("class", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current is not None:
            self.anchors.append(self._current)
            self._current = None
        elif tag == "span":
            self._span_class = ""

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._span_class == "date":
            self._current["date"] = (self._current.get("date", "") + text).strip()
        else:
            self._current["text"] = (self._current.get("text", "") + text).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contents_url(target_date: str) -> str:
    ymd = target_date.replace("-", "")
    if not re.fullmatch(r"\d{8}", ymd):
        raise ValueError("target_date must be YYYY-MM-DD or YYYYMMDD")
    return f"{BASE_URL}/{ymd}/{ymd}.fullcontents.html"


def fetch_text(url: str, *, timeout_sec: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str, *, timeout_sec: int = 90) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,text/html,*/*"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
        content_type = resp.headers.get("Content-Type", "")
        return resp.read(), content_type


def _issue_from_href(href: str) -> tuple[str, str, str]:
    issue_path = href.split("/", 1)[0] if "/" in href else ""
    match = re.search(r"([hgcst])0*(\d+)$", issue_path)
    if not match:
        return issue_path, "unknown", ""
    kind_map = {
        "h": "honshi",
        "g": "gogai",
        "c": "chotatsu",
        "s": "tokubetsu-gogai",
        "t": "mokuroku",
    }
    return issue_path, kind_map.get(match.group(1), "unknown"), match.group(2)


def parse_contents(html: str, *, base_url: str = BASE_URL, keyword: str = "会社決算公告") -> list[KanpoIndexEntry]:
    parser = _AnchorParser()
    parser.feed(html)
    entries: list[KanpoIndexEntry] = []
    for anchor in parser.anchors:
        href = anchor.get("href", "")
        title = anchor.get("text", "")
        if keyword not in title:
            continue
        page_text = anchor.get("date", "")
        try:
            page = int(re.search(r"\d+", page_text or "0").group(0))  # type: ignore[union-attr]
        except Exception:
            page = 0
        issue_path, issue_kind, issue_no = _issue_from_href(href)
        entries.append(
            KanpoIndexEntry(
                title=title,
                page=page,
                page_url=urllib.parse.urljoin(base_url, href),
                issue_path=issue_path,
                issue_kind=issue_kind,
                issue_no=issue_no,
            )
        )
    return entries


def pdf_url_from_page_html(page_url: str, html: str) -> str:
    match = re.search(r"<embed[^>]+src=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE)
    if not match:
        if page_url.lower().endswith(".pdf"):
            return page_url
        raise ValueError("kanpo page html did not contain embedded PDF")
    return urllib.parse.urljoin(page_url, match.group(1))


def iframe_url_from_page_html(page_url: str, html: str) -> str:
    match = re.search(r"<iframe[^>]+src=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE)
    return urllib.parse.urljoin(page_url, match.group(1)) if match else ""


def materialize_bytes(content: bytes, *, filename: str) -> tuple[str, int, str]:
    suffix = Path(filename).suffix or ".bin"
    tmp_dir = Path(tempfile.gettempdir()) / "jp-corp-finance-kanpo"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(content)
    path = tmp_dir / f"{Path(filename).stem}-{digest[:12]}{suffix}"
    path.write_bytes(content)
    return str(path), len(content), digest


def _filename_from_url(url: str, default: str) -> str:
    name = Path(urllib.parse.urlparse(url).path).name
    return name or default


def discover_kessan_entries(target_date: str, *, keyword: str = "会社決算公告") -> tuple[str, list[KanpoIndexEntry]]:
    url = contents_url(target_date)
    html = fetch_text(url)
    return url, parse_contents(html, base_url=url, keyword=keyword)


def fetch_kanpo_source(
    *,
    target_date: str,
    source_url: str = "",
    dry_run: bool = False,
    keyword: str = "会社決算公告",
) -> dict[str, Any]:
    """Find and materialize a Kanpo company-financial-disclosure PDF page."""
    if source_url:
        page_url = source_url
        entries = [
            KanpoIndexEntry(
                title=keyword,
                page=0,
                page_url=page_url,
                issue_path="",
                issue_kind="direct",
                issue_no="",
            )
        ]
        index_url = ""
    else:
        index_url, entries = discover_kessan_entries(target_date, keyword=keyword)
        if not entries:
            return {
                "ok": True,
                "sourceId": SOURCE_ID,
                "targetDate": target_date,
                "indexUrl": index_url,
                "payload": {"results": []},
                "recordsRead": 0,
                "status": "not_found",
            }
        page_url = entries[0].page_url

    if dry_run:
        return {
            "ok": True,
            "sourceId": SOURCE_ID,
            "targetDate": target_date,
            "indexUrl": index_url,
            "payload": {"results": [entry.to_dict() for entry in entries]},
            "recordsRead": len(entries),
            "sourceUrl": page_url,
        }

    page_bytes, page_content_type = fetch_bytes(page_url)
    if "pdf" in page_content_type.lower() or page_url.lower().endswith(".pdf"):
        pdf_url = page_url
        pdf_bytes = page_bytes
    else:
        page_html = page_bytes.decode("utf-8", errors="replace")
        iframe_url = iframe_url_from_page_html(page_url, page_html)
        if iframe_url:
            iframe_bytes, _ = fetch_bytes(iframe_url)
            page_html = iframe_bytes.decode("utf-8", errors="replace")
            page_url = iframe_url
        pdf_url = pdf_url_from_page_html(page_url, page_html)
        pdf_bytes, _ = fetch_bytes(pdf_url)

    filename = _filename_from_url(pdf_url, "kanpo-kessan.pdf")
    source_path, byte_size, sha256 = materialize_bytes(pdf_bytes, filename=filename)
    return {
        "ok": True,
        "sourceId": SOURCE_ID,
        "targetDate": target_date,
        "indexUrl": index_url,
        "payload": {"results": [entry.to_dict() for entry in entries]},
        "recordsRead": len(entries),
        "sourceUrl": pdf_url,
        "sourcePath": source_path,
        "contentType": "application/pdf",
        "artifactUri": pdf_url,
        "sourceSha256": sha256,
        "sourceByteSize": byte_size,
    }
