"""ISBN / global library digital ingest primitives.

Pipeline coverage (ADR-0056 BPMN-as-actor + ISBN registry CLAUDE.md):
  ingestOpenLibrary.bpmn  → isbn.openLibrary.ingest
  ingestAozora.bpmn       → isbn.aozora.ingest
  ingestGutenberg.bpmn    → isbn.gutenberg.ingest
  ingestNdl.bpmn          → isbn.ndl.ingest
  ingestHathiTrust.bpmn   → isbn.hathitrust.ingest
  refreshDaily.bpmn       (timer-start, reuses isbn.aozora.ingest + isbn.gutenberg.ingest)

Output target tables (created by 20260505100000_vertex_isbn_book.ts):
  vertex_isbn_book              — bibliographic master
  vertex_isbn_publisher         — publisher prefix registry (best-effort)
  vertex_isbn_book_chapter      — chunked plain text (optional, fulltext sources)
  vertex_isbn_book_fulltext     — fulltext metadata + B2 location (optional)
  vertex_isbn_book_copyright    — PD / CC status per jurisdiction

Env vars (optional — only required for fulltext B2 persistence):
  B2_ACCESS_KEY_ID         Backblaze B2 application key ID
  B2_SECRET_ACCESS_KEY     Backblaze B2 application key
  B2_ENDPOINT              e.g. https://s3.us-west-004.backblazeb2.com
  B2_ISBN_BUCKET           default: etzhayyim-isbn

The ingest path follows the patent pattern: stream the upstream catalog,
parse → batch → INSERT into RisingWave with `_rw_executemany`. Rows
collide on PK (`vertex_id`) so re-runs are idempotent — RisingWave's
PK semantics overwrite (per CLAUDE.md `[[conventions]] rw-bulk-insert-throttle`,
re-INSERT on the same PK is the intended upsert).
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import csv
import gzip
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import Any
from xml.etree import ElementTree as ET


# ──────────────────────────────────────────────────────────────────────
# Constants / env
# ──────────────────────────────────────────────────────────────────────

_ISBN_ACTOR = "did:web:isbn.etzhayyim.com"

_B2_KEY_ID = os.environ.get("B2_ACCESS_KEY_ID", "").strip()
_B2_KEY = os.environ.get("B2_SECRET_ACCESS_KEY", "").strip()
_B2_ENDPOINT = os.environ.get("B2_ENDPOINT", "https://s3.us-west-004.backblazeb2.com").rstrip("/")
_B2_BUCKET = os.environ.get("B2_ISBN_BUCKET", "etzhayyim-isbn").strip() or "etzhayyim-isbn"

# Aozora author death year cutoff for guaranteed-PD on the Japanese
# 70-year post-mortem rule (2018 amendment).  death_year ≤ 1953 is safe
# in the strictest interpretation; Aozora self-curates already.
_AOZORA_PD_CUTOFF_YEAR = 1953

# Chapter chunking — keep chapters under ~ 8 KiB so the 50-cell observer
# expansion in dispatcher stays bounded.
_CHAPTER_BYTE_TARGET = 8000
# Hard cap on a single chapter body persisted inline (RW varchar safety).
_CHAPTER_BYTE_HARDCAP = 64_000

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _rw_executemany(sql: str, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    if True:
        client = get_kotoba_client()
        for row in rows:
            _res = client.q(sql, row)


def _http_get(url: str, headers: dict[str, str] | None = None, timeout: float = 120.0) -> bytes:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "isbn.etzhayyim.com/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} GET {url}: {detail}") from e


def _normalize_isbn13(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"[^0-9Xx]", "", raw)
    if len(digits) == 13 and digits.isdigit():
        return digits
    if len(digits) == 10:
        return _isbn10_to_13(digits)
    return None


def _isbn10_to_13(isbn10: str) -> str | None:
    body = isbn10[:9]
    if not body.isdigit():
        return None
    base = "978" + body
    total = 0
    for i, ch in enumerate(base):
        n = int(ch)
        total += n if i % 2 == 0 else n * 3
    check = (10 - total % 10) % 10
    return base + str(check)


def _synthetic_isbn13(source_digit: str, stable_key: str) -> str:
    """Return a valid numeric synthetic ISBN-13 in the unassigned 97990 range."""
    digest = hashlib.sha1(stable_key.encode("utf-8")).hexdigest()
    digits = "".join(c for c in digest if c.isdigit())[:6].ljust(6, "0")
    body12 = f"97990{source_digit}{digits}"
    total = sum(int(c) if i % 2 == 0 else int(c) * 3 for i, c in enumerate(body12))
    check = (10 - total % 10) % 10
    return body12 + str(check)


def _registration_group(isbn13: str) -> str:
    """Best-effort group extraction (single-digit groups: 0/1=eng, 2=fra, 3=ger, 4=jpn, 5=rus, 7=cn).
    For multi-digit groups we return empty (downstream resolver can fill in)."""
    body = isbn13[3:]
    if not body or not body[0].isdigit():
        return ""
    g0 = body[0]
    if g0 in "01234579":
        return g0
    return ""


def _publisher_prefix(isbn13: str) -> str:
    """Return the EAN+group+publisher span. We can't know the exact
    publisher boundary without the Range Message DB, so we approximate
    by taking the first 7 chars (978 + group(1) + 3 digits of publisher),
    which is sufficient for grouping/registry-keying."""
    return isbn13[:7] if len(isbn13) >= 7 else isbn13


def _b2_put(bucket: str, key: str, data: bytes, content_type: str) -> str:
    """AWS sigv4 PUT to B2 S3-compatible endpoint. Returns b2:// URI."""
    import hmac
    import hashlib as _hl

    if not _B2_KEY_ID or not _B2_KEY:
        raise RuntimeError("B2_ACCESS_KEY_ID / B2_SECRET_ACCESS_KEY not set")

    url = f"{_B2_ENDPOINT}/{bucket}/{key}"
    now = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    date = now[:8]
    service = "s3"
    region = (_B2_ENDPOINT.split(".")[1] if _B2_ENDPOINT.count(".") >= 2 else "us-west-004")

    payload_hash = _hl.sha256(data).hexdigest()
    host = _B2_ENDPOINT.replace("https://", "").replace("http://", "")
    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{now}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_uri = f"/{bucket}/{urllib.parse.quote(key, safe='/')}"
    canonical_req = f"PUT\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    scope = f"{date}/{region}/{service}/aws4_request"
    string_to_sign = f"AWS4-HMAC-SHA256\n{now}\n{scope}\n{_hl.sha256(canonical_req.encode()).hexdigest()}"

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), _hl.sha256).digest()

    k_date = _sign(("AWS4" + _B2_KEY).encode("utf-8"), date)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), _hl.sha256).hexdigest()

    auth = (
        f"AWS4-HMAC-SHA256 Credential={_B2_KEY_ID}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    req = urllib.request.Request(
        url, data=data, method="PUT",
        headers={
            "Content-Type": content_type,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": now,
            "Authorization": auth,
        },
    )
    with urllib.request.urlopen(req, timeout=120.0) as resp:
        if resp.status not in (200, 204):
            raise RuntimeError(f"B2 PUT failed: {resp.status}")
    return f"b2://{bucket}/{key}"


def _split_into_chapters(text: str) -> list[tuple[int, str, str]]:
    """Return [(chapter_number, title, body)]. Splits on common chapter
    markers (`第N章`, `Chapter N`, `CHAPTER N`, blank-line clusters).
    Falls back to fixed-size byte chunks when no marker found."""
    if not text:
        return []
    # Postgres text fields reject NUL bytes; some Shift-JIS / DjVu
    # decodes contain them as filler.
    text = text.replace("\x00", "")

    # Try chapter heading split first.
    chapter_pat = re.compile(
        r"(?m)^(第\s*[0-9一二三四五六七八九十百千]+\s*[章話節]|Chapter\s+\d+|CHAPTER\s+\d+|Part\s+\d+|PART\s+\d+).*$"
    )
    matches = list(chapter_pat.finditer(text))
    chapters: list[tuple[int, str, str]] = []
    if matches:
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            title = m.group(0).strip()[:200]
            body = text[start:end].strip()
            chapters.append((i + 1, title, body[:_CHAPTER_BYTE_HARDCAP]))
        return chapters

    # Fallback: paragraph-aware fixed chunks.
    paragraphs = re.split(r"\n\s*\n", text)
    buf = ""
    n = 0
    for p in paragraphs:
        if len(buf) + len(p) + 2 > _CHAPTER_BYTE_TARGET and buf:
            n += 1
            chapters.append((n, "", buf[:_CHAPTER_BYTE_HARDCAP]))
            buf = ""
        buf = buf + ("\n\n" if buf else "") + p
    if buf:
        n += 1
        chapters.append((n, "", buf[:_CHAPTER_BYTE_HARDCAP]))
    return chapters


# ──────────────────────────────────────────────────────────────────────
# Image helpers (Phase 2: cover + page scan)
# ──────────────────────────────────────────────────────────────────────


def _cidv1_raw_sha256(data: bytes) -> str:
    """CIDv1 raw codec (0x55) + sha2-256 multihash, multibase base32 lower.
    Matches the `ipfs.add` host import contract (see 50-infra notes)."""
    digest = hashlib.sha256(data).digest()
    multihash = b"\x12\x20" + digest  # 0x12 = sha2-256, 0x20 = 32-byte length
    cid_bytes = b"\x01\x55" + multihash  # version=1, codec=raw(0x55)

    # base32 lower (RFC 4648, no padding) prefixed with `b`.
    alphabet = "abcdefghijklmnopqrstuvwxyz234567"
    bits = "".join(f"{b:08b}" for b in cid_bytes)
    pad = (5 - len(bits) % 5) % 5
    bits += "0" * pad
    chunks = [bits[i:i + 5] for i in range(0, len(bits), 5)]
    return "b" + "".join(alphabet[int(c, 2)] for c in chunks)


def _png_dims(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n":
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        return (w, h)
    return None


def _jpeg_dims(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xC3 or 0xC5 <= marker <= 0xC7 or 0xC9 <= marker <= 0xCB or 0xCD <= marker <= 0xCF:
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return (w, h)
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        i += 2 + seg_len
    return None


def _detect_image(data: bytes) -> tuple[str, int | None, int | None]:
    """Return (mime_type, width_px, height_px). Falls back to mime=octet-stream."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        wh = _png_dims(data)
        return ("image/png", wh[0] if wh else None, wh[1] if wh else None)
    if data[:2] == b"\xff\xd8":
        wh = _jpeg_dims(data)
        return ("image/jpeg", wh[0] if wh else None, wh[1] if wh else None)
    if data[:6] in (b"GIF87a", b"GIF89a"):
        if len(data) >= 10:
            w = int.from_bytes(data[6:8], "little")
            h = int.from_bytes(data[8:10], "little")
            return ("image/gif", w, h)
        return ("image/gif", None, None)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ("image/webp", None, None)
    return ("application/octet-stream", None, None)


def _persist_image(
    isbn13: str,
    *,
    role: str,
    page_index: int | None,
    image_bytes: bytes,
    source: str,
    source_url: str,
    license: str,
) -> tuple[Any, ...] | None:
    """Compute CID, upload to B2 (best-effort), return INSERT row tuple.

    Returns None if the bytes look invalid (e.g. zero-length, error page).
    """
    if not image_bytes or len(image_bytes) < 64:
        return None
    sha256 = hashlib.sha256(image_bytes).hexdigest()
    cid = _cidv1_raw_sha256(image_bytes)
    mime, w, h = _detect_image(image_bytes)
    # Filter HTML / "no image" placeholders that some catalogs return.
    head = image_bytes[:64].lower()
    if mime == "application/octet-stream" and (b"<html" in head or b"<!doc" in head or b"<svg" in head):
        return None

    b2_key = f"images/{sha256}"
    if _B2_KEY_ID and _B2_KEY:
        try:
            _b2_put(_B2_BUCKET, b2_key, image_bytes, mime)
        except Exception:
            b2_key = ""  # B2 unavailable; row still records hash + source URL

    vertex_id = f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_image/{isbn13}-{role}"
    if page_index is not None:
        vertex_id = f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_image/{isbn13}-{role}-{page_index:04d}"
    now = _now_iso()
    return (
        vertex_id, isbn13, role, page_index, sha256, cid,
        _B2_BUCKET if b2_key else "", b2_key, source, (source_url or "")[:500],
        mime, w, h, len(image_bytes), license, "active",
        _ISBN_ACTOR, 1, now, _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
    )


_INSERT_IMAGE = (
    "INSERT INTO vertex_isbn_book_image "
    "(vertex_id, isbn13, role, page_index, sha256, cid_v1, "
    " b2_bucket, b2_key, source, source_url, "
    " mime_type, width_px, height_px, byte_size, license, status, "
    " owner_did, sensitivity_ord, created_at, org_id, user_id, actor_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)


# Shared INSERT signatures.
_INSERT_BOOK = (
    "INSERT INTO vertex_isbn_book "
    "(vertex_id, isbn13, isbn10, title, subtitle, authors, publisher_prefix, "
    " publication_year, language, registration_group, page_count, bisac_subjects, "
    " source, source_url, status, owner_did, sensitivity_ord, created_at, "
    " org_id, user_id, actor_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)
_INSERT_PUBLISHER = (
    "INSERT INTO vertex_isbn_publisher "
    "(vertex_id, prefix, name, registration_group, country, website, status, "
    " owner_did, sensitivity_ord, created_at, org_id, user_id, actor_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)
_INSERT_CHAPTER = (
    "INSERT INTO vertex_isbn_book_chapter "
    "(vertex_id, isbn13, chapter_number, title, text, token_count, byte_size, "
    " language, b2_key, status, owner_did, sensitivity_ord, created_at, "
    " org_id, user_id, actor_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)
_INSERT_FULLTEXT = (
    "INSERT INTO vertex_isbn_book_fulltext "
    "(vertex_id, isbn13, source, source_url, format, total_chapters, total_tokens, "
    " total_bytes, b2_bucket, b2_prefix, license, sha256, status, owner_did, "
    " sensitivity_ord, created_at, org_id, user_id, actor_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)
_INSERT_COPYRIGHT = (
    "INSERT INTO vertex_isbn_book_copyright "
    "(vertex_id, isbn13, status, author_death_year, jurisdiction, pd_year, "
    " license_url, evidence_url, owner_did, sensitivity_ord, created_at, "
    " org_id, user_id, actor_id) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)


def _book_row(
    isbn13: str, *, isbn10: str | None, title: str, subtitle: str | None,
    authors: list[str], publication_year: int | None, language: str | None,
    page_count: int | None, source: str, source_url: str | None,
) -> tuple[Any, ...]:
    vertex_id = f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book/{isbn13}"
    now = _now_iso()
    return (
        vertex_id, isbn13, isbn10, (title or "")[:1000], (subtitle or "")[:1000],
        json.dumps(authors[:50], ensure_ascii=False), _publisher_prefix(isbn13),
        publication_year, (language or "").strip(),
        _registration_group(isbn13), page_count, "[]",
        source, (source_url or "")[:500], "active",
        _ISBN_ACTOR, 1, now, _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
    )


def _copyright_row(
    isbn13: str, *, status: str, jurisdiction: str | None,
    author_death_year: int | None, pd_year: int | None,
    license_url: str | None, evidence_url: str | None,
) -> tuple[Any, ...]:
    vertex_id = f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_copyright/{isbn13}"
    now = _now_iso()
    return (
        vertex_id, isbn13, status, author_death_year, jurisdiction, pd_year,
        license_url, evidence_url, _ISBN_ACTOR, 1, now,
        _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
    )


# ──────────────────────────────────────────────────────────────────────
# Task: isbn.openLibrary.ingest
# ──────────────────────────────────────────────────────────────────────


async def task_isbn_open_library_ingest(
    dumpUrl: str | None = None,
    batchSize: int = 2000,
    limit: int | None = None,
    fetchCovers: bool = True,
) -> dict:
    """Ingest Open Library editions dump.

    Open Library distributes monthly TSV dumps at
        https://openlibrary.org/data/ol_dump_editions_latest.txt.gz
    Each line is `type<TAB>key<TAB>revision<TAB>last_modified<TAB>JSON`.
    The JSON payload (5th column) is the edition record. We extract
    isbn_13 / isbn_10 / title / authors / publish_date / languages /
    number_of_pages and bulk-insert.
    """
    url = (dumpUrl or "https://openlibrary.org/data/ol_dump_editions_latest.txt.gz").strip()

    raw = _http_get(url, timeout=1800.0)
    if url.endswith(".gz"):
        raw = gzip.decompress(raw)

    rows_book: list[tuple[Any, ...]] = []
    rows_pub: list[tuple[Any, ...]] = []
    rows_img: list[tuple[Any, ...]] = []
    rows_inserted = 0
    images_inserted = 0
    skipped = 0
    seen_pub: set[str] = set()

    for line in io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split("\t", 4)
        if len(parts) < 5:
            skipped += 1
            continue
        try:
            edition = json.loads(parts[4])
        except Exception:
            skipped += 1
            continue

        isbn13_list = edition.get("isbn_13") or []
        isbn10_list = edition.get("isbn_10") or []
        isbn13 = _normalize_isbn13(isbn13_list[0] if isbn13_list else (isbn10_list[0] if isbn10_list else None))
        if not isbn13:
            skipped += 1
            continue

        title = (edition.get("title") or "")[:1000]
        subtitle = (edition.get("subtitle") or "")[:1000]
        authors = []
        for a in edition.get("authors") or []:
            if isinstance(a, dict) and "key" in a:
                authors.append(a["key"])
            elif isinstance(a, str):
                authors.append(a)
        pub_date = edition.get("publish_date") or ""
        year_match = re.search(r"\b(1\d{3}|20\d{2})\b", pub_date)
        publication_year = int(year_match.group(0)) if year_match else None
        languages = edition.get("languages") or []
        lang = ""
        if languages and isinstance(languages[0], dict):
            lang = (languages[0].get("key") or "").rsplit("/", 1)[-1]
        page_count = edition.get("number_of_pages")
        if not isinstance(page_count, int):
            page_count = None
        publishers = edition.get("publishers") or []
        pub_name = publishers[0] if publishers and isinstance(publishers[0], str) else None

        rows_book.append(_book_row(
            isbn13, isbn10=(isbn10_list[0] if isbn10_list else None),
            title=title, subtitle=subtitle, authors=authors,
            publication_year=publication_year, language=lang,
            page_count=page_count, source="openlibrary",
            source_url=f"https://openlibrary.org{edition.get('key', '')}",
        ))

        prefix = _publisher_prefix(isbn13)
        if pub_name and prefix not in seen_pub:
            seen_pub.add(prefix)
            rows_pub.append((
                f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.publisher/{prefix}",
                prefix, pub_name[:200], _registration_group(isbn13), "",
                "", "active", _ISBN_ACTOR, 1, _now_iso(),
                _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
            ))

        # Cover image — Open Library covers API.
        # https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg returns the
        # large cover; absent covers return a 1x1 transparent PNG (~104 B)
        # which our _persist_image filter rejects via the byte-size guard.
        if fetchCovers:
            try:
                img_bytes = _http_get(
                    f"https://covers.openlibrary.org/b/isbn/{isbn13}-L.jpg",
                    timeout=20.0,
                )
                row = _persist_image(
                    isbn13, role="cover", page_index=None,
                    image_bytes=img_bytes, source="openlibrary-covers",
                    source_url=f"https://covers.openlibrary.org/b/isbn/{isbn13}-L.jpg",
                    license="cc0",
                )
                if row:
                    rows_img.append(row)
            except Exception:
                pass

        if len(rows_book) >= batchSize:
            _rw_executemany(_INSERT_BOOK, rows_book)
            rows_inserted += len(rows_book)
            rows_book = []
        if len(rows_pub) >= batchSize:
            _rw_executemany(_INSERT_PUBLISHER, rows_pub)
            rows_pub = []
        if len(rows_img) >= 200:
            _rw_executemany(_INSERT_IMAGE, rows_img)
            images_inserted += len(rows_img)
            rows_img = []
        if limit and rows_inserted + len(rows_book) >= limit:
            break

    if rows_book:
        _rw_executemany(_INSERT_BOOK, rows_book)
        rows_inserted += len(rows_book)
    if rows_pub:
        _rw_executemany(_INSERT_PUBLISHER, rows_pub)
    if rows_img:
        _rw_executemany(_INSERT_IMAGE, rows_img)
        images_inserted += len(rows_img)

    return {"ok": True, "rows": rows_inserted, "images": images_inserted, "skipped": skipped}


# ──────────────────────────────────────────────────────────────────────
# Task: isbn.aozora.ingest
# ──────────────────────────────────────────────────────────────────────


async def task_isbn_aozora_ingest(
    catalogUrl: str | None = None,
    fulltext: bool = True,
    limit: int | None = None,
) -> dict:
    """Ingest Aozora Bunko catalog (CSV inside ZIP).

    Catalog columns (Japanese headers); we read by index based on the
    standard list_person_all_extended_utf8 layout:
       0  作品ID                       (work_id)
       1  作品名                       (title)
       2  作品名読み
       3  ソート用読み
       4  副題
       ...
       14 著者名
       15 著者ID
       18 生年月日
       19 没年月日
       45 テキストファイルURL
       50 XHTML/HTMLファイルURL
    The exact indices have been stable since 2022-12 — we re-read the
    header to remap if the upstream order changes.
    """
    url = (catalogUrl or "https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip").strip()

    raw = _http_get(url, timeout=300.0)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        csv_name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if not csv_name:
            raise RuntimeError("Aozora catalog ZIP contains no CSV")
        csv_bytes = zf.read(csv_name)

    reader = csv.reader(io.TextIOWrapper(io.BytesIO(csv_bytes), encoding="utf-8-sig", errors="replace"))
    header = next(reader, None) or []

    def _col(name: str, fallback: int) -> int:
        for i, h in enumerate(header):
            if h.strip() == name:
                return i
        return fallback

    idx_work_id = _col("作品ID", 0)
    idx_title = _col("作品名", 1)
    idx_subtitle = _col("副題", 4)
    idx_author_first = _col("姓", 15)
    idx_author_last = _col("名", 16)
    idx_death = _col("没年月日", 19)
    idx_text_url = _col("テキストファイルURL", 45)
    idx_html_url = _col("XHTML/HTMLファイルURL", 50)

    book_batch: list[tuple[Any, ...]] = []
    chap_batch: list[tuple[Any, ...]] = []
    full_batch: list[tuple[Any, ...]] = []
    cr_batch: list[tuple[Any, ...]] = []

    books_inserted = 0
    chapters_inserted = 0

    for row in reader:
        if len(row) <= idx_html_url:
            continue
        work_id = (row[idx_work_id] or "").strip()
        title = (row[idx_title] or "").strip()
        subtitle = (row[idx_subtitle] or "").strip() if idx_subtitle < len(row) else ""
        first = (row[idx_author_first] or "").strip() if idx_author_first < len(row) else ""
        last = (row[idx_author_last] or "").strip() if idx_author_last < len(row) else ""
        author = (first + last).strip() or "(unknown)"
        death_raw = (row[idx_death] or "").strip() if idx_death < len(row) else ""
        text_url = (row[idx_text_url] or "").strip() if idx_text_url < len(row) else ""

        if not work_id or not title:
            continue

        # Synthetic ISBN13 namespace for Aozora-only works (no published ISBN).
        isbn13 = _synthetic_isbn13("1", f"aozora:{work_id}")

        death_year = None
        m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", death_raw)
        if m:
            try:
                death_year = int(m.group(0))
            except ValueError:
                death_year = None

        book_batch.append(_book_row(
            isbn13, isbn10=None, title=title, subtitle=subtitle,
            authors=[author], publication_year=None, language="ja",
            page_count=None, source="aozora",
            source_url=text_url or f"https://www.aozora.gr.jp/cards/{work_id}.html",
        ))

        cr_batch.append(_copyright_row(
            isbn13,
            status="pd" if (death_year is not None and death_year <= _AOZORA_PD_CUTOFF_YEAR) else "unknown",
            jurisdiction="JP", author_death_year=death_year,
            pd_year=(death_year + 70) if death_year else None,
            license_url=None, evidence_url=text_url,
        ))

        if fulltext and text_url:
            try:
                body_bytes = _http_get(text_url, timeout=60.0)
                # Aozora text files are Shift-JIS or UTF-8.
                try:
                    body_text = body_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    body_text = body_bytes.decode("shift_jis", errors="replace")
                # Strip ruby markers and bibliographic tail.
                body_text = re.sub(r"《[^》]*》", "", body_text)
                body_text = re.sub(r"［[^］]*］", "", body_text)
                body_text = re.sub(r"｜", "", body_text)
                chapters = _split_into_chapters(body_text)

                b2_prefix = f"aozora/{work_id}/"
                b2_key = None
                if _B2_KEY_ID and _B2_KEY:
                    sha256 = hashlib.sha256(body_bytes).hexdigest()
                    try:
                        b2_key = _b2_put(_B2_BUCKET, f"{b2_prefix}original.txt",
                                         body_bytes, "text/plain; charset=utf-8")
                    except Exception:
                        b2_key = None

                for n, ctitle, ctext in chapters:
                    cvid = f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_chapter/{isbn13}-{n:04d}"
                    chap_batch.append((
                        cvid, isbn13, n, ctitle[:200], ctext,
                        len(ctext), len(ctext.encode("utf-8")), "ja",
                        f"{b2_prefix}ch{n:04d}.txt" if b2_key else "",
                        "active", _ISBN_ACTOR, 1, _now_iso(),
                        _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
                    ))

                full_batch.append((
                    f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_fulltext/{isbn13}",
                    isbn13, "aozora", text_url, "text/plain",
                    len(chapters), sum(len(c[2]) for c in chapters),
                    sum(len(c[2].encode("utf-8")) for c in chapters),
                    _B2_BUCKET, b2_prefix, "pd",
                    hashlib.sha256(body_bytes).hexdigest(), "active",
                    _ISBN_ACTOR, 1, _now_iso(),
                    _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
                ))

                chapters_inserted += len(chapters)
            except Exception:
                # Skip individual fetch failures; continue catalog walk.
                pass

        if len(book_batch) >= 500:
            _rw_executemany(_INSERT_BOOK, book_batch); books_inserted += len(book_batch); book_batch = []
        if len(cr_batch) >= 500:
            _rw_executemany(_INSERT_COPYRIGHT, cr_batch); cr_batch = []
        if len(chap_batch) >= 500:
            _rw_executemany(_INSERT_CHAPTER, chap_batch); chap_batch = []
        if len(full_batch) >= 500:
            _rw_executemany(_INSERT_FULLTEXT, full_batch); full_batch = []

        if limit and books_inserted + len(book_batch) >= limit:
            break

    if book_batch:
        _rw_executemany(_INSERT_BOOK, book_batch); books_inserted += len(book_batch)
    if cr_batch:
        _rw_executemany(_INSERT_COPYRIGHT, cr_batch)
    if chap_batch:
        _rw_executemany(_INSERT_CHAPTER, chap_batch)
    if full_batch:
        _rw_executemany(_INSERT_FULLTEXT, full_batch)

    return {"ok": True, "books": books_inserted, "chapters": chapters_inserted}


# ──────────────────────────────────────────────────────────────────────
# Task: isbn.gutenberg.ingest
# ──────────────────────────────────────────────────────────────────────


async def task_isbn_gutenberg_ingest(
    feedUrl: str | None = None,
    fulltext: bool = True,
    fetchCovers: bool = True,
    limit: int | None = None,
) -> dict:
    """Ingest Project Gutenberg using the GutenDex JSON API
    (https://gutendex.com), which reads the canonical RDF and provides
    paginated JSON. Pure RDF tar.bz2 parse is also supported via feedUrl
    if explicitly provided, but GutenDex is much cheaper.
    """
    base = (feedUrl or "https://gutendex.com/books/").strip()

    book_batch: list[tuple[Any, ...]] = []
    chap_batch: list[tuple[Any, ...]] = []
    full_batch: list[tuple[Any, ...]] = []
    cr_batch: list[tuple[Any, ...]] = []
    img_batch: list[tuple[Any, ...]] = []
    books_inserted = 0
    chapters_inserted = 0
    images_inserted = 0

    next_url: str | None = base
    while next_url:
        raw = _http_get(next_url, timeout=120.0)
        try:
            page = json.loads(raw)
        except Exception:
            break
        results = page.get("results") or []
        if not results:
            break

        for ed in results:
            gid = ed.get("id")
            if not gid:
                continue
            title = (ed.get("title") or "")[:1000]
            authors = [a.get("name") for a in (ed.get("authors") or []) if a.get("name")]
            languages = ed.get("languages") or []
            lang = languages[0] if languages else "en"
            # Synthesize an ISBN-13 namespace for Gutenberg-only entries.
            isbn13 = _synthetic_isbn13("2", f"gutenberg:{gid}")

            text_url = (
                ed.get("formats", {}).get("text/plain; charset=utf-8")
                or ed.get("formats", {}).get("text/plain")
                or ""
            )

            book_batch.append(_book_row(
                isbn13, isbn10=None, title=title, subtitle=None,
                authors=authors, publication_year=None, language=lang,
                page_count=None, source="gutenberg",
                source_url=f"https://www.gutenberg.org/ebooks/{gid}",
            ))

            # Gutenberg works are PD-US by default.
            author_death = None
            for a in (ed.get("authors") or []):
                if a.get("death_year"):
                    author_death = int(a["death_year"])
                    break
            cr_batch.append(_copyright_row(
                isbn13, status="pd", jurisdiction="US",
                author_death_year=author_death,
                pd_year=(author_death + 70) if author_death else None,
                license_url=None, evidence_url=f"https://www.gutenberg.org/ebooks/{gid}",
            ))

            if fulltext and text_url:
                try:
                    body_bytes = _http_get(text_url, timeout=60.0)
                    body_text = body_bytes.decode("utf-8", errors="replace")
                    chapters = _split_into_chapters(body_text)
                    b2_prefix = f"gutenberg/{gid}/"
                    sha256 = hashlib.sha256(body_bytes).hexdigest()
                    if _B2_KEY_ID and _B2_KEY:
                        try:
                            _b2_put(_B2_BUCKET, f"{b2_prefix}original.txt",
                                    body_bytes, "text/plain; charset=utf-8")
                        except Exception:
                            pass

                    for n, ctitle, ctext in chapters:
                        cvid = f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_chapter/{isbn13}-{n:04d}"
                        chap_batch.append((
                            cvid, isbn13, n, ctitle[:200], ctext,
                            len(ctext), len(ctext.encode("utf-8")), lang,
                            f"{b2_prefix}ch{n:04d}.txt", "active",
                            _ISBN_ACTOR, 1, _now_iso(),
                            _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
                        ))

                    full_batch.append((
                        f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_fulltext/{isbn13}",
                        isbn13, "gutenberg", text_url, "text/plain",
                        len(chapters), sum(len(c[2]) for c in chapters),
                        sum(len(c[2].encode("utf-8")) for c in chapters),
                        _B2_BUCKET, b2_prefix, "pd", sha256, "active",
                        _ISBN_ACTOR, 1, _now_iso(),
                        _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
                    ))
                    chapters_inserted += len(chapters)
                except Exception:
                    pass

            # Gutenberg cover image (formats[image/jpeg]).
            if fetchCovers:
                cover_url = ed.get("formats", {}).get("image/jpeg") or ""
                if cover_url:
                    try:
                        img_bytes = _http_get(cover_url, timeout=20.0)
                        row = _persist_image(
                            isbn13, role="cover", page_index=None,
                            image_bytes=img_bytes, source="gutenberg",
                            source_url=cover_url, license="pd",
                        )
                        if row:
                            img_batch.append(row)
                    except Exception:
                        pass

            if len(book_batch) >= 500:
                _rw_executemany(_INSERT_BOOK, book_batch); books_inserted += len(book_batch); book_batch = []
            if len(cr_batch) >= 500:
                _rw_executemany(_INSERT_COPYRIGHT, cr_batch); cr_batch = []
            if len(chap_batch) >= 500:
                _rw_executemany(_INSERT_CHAPTER, chap_batch); chap_batch = []
            if len(full_batch) >= 500:
                _rw_executemany(_INSERT_FULLTEXT, full_batch); full_batch = []
            if len(img_batch) >= 200:
                _rw_executemany(_INSERT_IMAGE, img_batch); images_inserted += len(img_batch); img_batch = []

            if limit and books_inserted + len(book_batch) >= limit:
                next_url = None
                break

        next_url = page.get("next") if next_url else None
        if not next_url:
            break

    if book_batch:
        _rw_executemany(_INSERT_BOOK, book_batch); books_inserted += len(book_batch)
    if cr_batch:
        _rw_executemany(_INSERT_COPYRIGHT, cr_batch)
    if chap_batch:
        _rw_executemany(_INSERT_CHAPTER, chap_batch)
    if full_batch:
        _rw_executemany(_INSERT_FULLTEXT, full_batch)
    if img_batch:
        _rw_executemany(_INSERT_IMAGE, img_batch); images_inserted += len(img_batch)

    return {"ok": True, "books": books_inserted, "chapters": chapters_inserted, "images": images_inserted}


# ──────────────────────────────────────────────────────────────────────
# Task: isbn.ndl.ingest
# ──────────────────────────────────────────────────────────────────────

_NDL_NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
}


async def task_isbn_ndl_ingest(
    sruEndpoint: str | None = None,
    query: str = "isbn=*",
    maxRecords: int = 200,
    startRecord: int = 1,
) -> dict:
    """Ingest one SRU page from NDL Search.

    NDL caps at 200 records per request. The caller is expected to
    re-trigger the BPMN with the returned `nextStartRecord` to walk
    further. Useful for narrow sweeps (publisher, year, subject).
    """
    base = (sruEndpoint or "https://ndlsearch.ndl.go.jp/api/sru").strip()
    params = urllib.parse.urlencode({
        "operation": "searchRetrieve",
        "version": "1.2",
        "recordSchema": "dcndl",
        "query": query,
        "maximumRecords": str(min(max(1, maxRecords), 200)),
        "startRecord": str(max(1, startRecord)),
    })
    url = f"{base}?{params}"

    raw = _http_get(url, timeout=60.0, headers={"Accept": "application/xml", "User-Agent": "isbn.etzhayyim.com/1.0"})
    root = ET.fromstring(raw)

    book_batch: list[tuple[Any, ...]] = []
    rows = 0
    for record in root.findall(".//srw:record/srw:recordData", _NDL_NS):
        # dcndl payload nests one Description per record.
        desc = record.find(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description")
        if desc is None:
            continue
        title_el = desc.find("dc:title", _NDL_NS)
        creator_el = desc.find("dc:creator", _NDL_NS)
        date_el = desc.find("dcterms:issued", _NDL_NS) or desc.find("dc:date", _NDL_NS)
        lang_el = desc.find("dc:language", _NDL_NS)
        isbn_el = None
        for ident in desc.findall("dc:identifier", _NDL_NS):
            txt = (ident.text or "").strip()
            if txt.lower().startswith("isbn") or re.match(r"^[0-9-]{10,17}$", txt):
                isbn_el = ident
                break
        if isbn_el is None:
            continue
        isbn13 = _normalize_isbn13(isbn_el.text or "")
        if not isbn13:
            continue
        title = (title_el.text or "").strip() if title_el is not None else ""
        author = (creator_el.text or "").strip() if creator_el is not None else ""
        lang = (lang_el.text or "ja").strip() if lang_el is not None else "ja"
        year = None
        if date_el is not None and date_el.text:
            m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", date_el.text)
            if m:
                year = int(m.group(0))

        book_batch.append(_book_row(
            isbn13, isbn10=None, title=title, subtitle=None,
            authors=[author] if author else [],
            publication_year=year, language=lang,
            page_count=None, source="ndl",
            source_url=f"https://ndlsearch.ndl.go.jp/search?cs=bib&keyword={isbn13}",
        ))
        rows += 1

    if book_batch:
        _rw_executemany(_INSERT_BOOK, book_batch)

    next_start = startRecord + rows if rows >= maxRecords else 0
    return {"ok": True, "rows": rows, "nextStartRecord": next_start}


# ──────────────────────────────────────────────────────────────────────
# Task: isbn.hathitrust.ingest
# ──────────────────────────────────────────────────────────────────────


async def task_isbn_hathitrust_ingest(
    hathifileUrl: str | None = None,
    publicDomainOnly: bool = True,
    limit: int | None = None,
) -> dict:
    """Ingest a HathiTrust hathifile (.txt.gz, TSV).

    Column layout (Hathifile spec):
       0  htid           24 ucm.b6...
       1  access         allow / deny
       2  rights         pd / pdus / cc-by / ic / ...
       3  ht_bib_key
       4  description
       5  source
       6  source_bib_num
       7  oclc_num
       8  isbn           ISBN list (semicolon-separated)
       9  issn
       10 lccn
       11 title
       12 imprint        publisher + year
       13 rights_reason_code
       14 rights_timestamp
       15 us_gov_doc_flag
       16 rights_date_used
       17 pub_place
       18 lang
       19 bib_fmt
       20 collection_code
       21 content_provider_code
       22 responsible_entity_code
       23 digitization_agent_code
       24 access_profile_code
       25 author
    """
    if not hathifileUrl:
        raise RuntimeError("hathifileUrl required (HathiTrust hathifile_full_*.txt.gz)")

    raw = _http_get(hathifileUrl, timeout=1800.0)
    if hathifileUrl.endswith(".gz"):
        raw = gzip.decompress(raw)

    book_batch: list[tuple[Any, ...]] = []
    cr_batch: list[tuple[Any, ...]] = []
    rows = 0
    pd_rows = 0

    reader = csv.reader(
        io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8", errors="replace"),
        delimiter="\t",
    )
    for parts in reader:
        if len(parts) < 26:
            continue
        access = parts[1]
        rights = parts[2]
        if publicDomainOnly and access != "allow":
            continue

        isbn_field = parts[8] or ""
        isbn13 = None
        for raw_isbn in re.split(r"[;\s,]+", isbn_field):
            isbn13 = _normalize_isbn13(raw_isbn)
            if isbn13:
                break
        if not isbn13:
            continue

        title = (parts[11] or "")[:1000]
        imprint = parts[12] or ""
        m_year = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", imprint)
        year = int(m_year.group(0)) if m_year else None
        lang = (parts[18] or "").strip()
        author = (parts[25] or "").strip()

        book_batch.append(_book_row(
            isbn13, isbn10=None, title=title, subtitle=None,
            authors=[author] if author else [],
            publication_year=year, language=lang,
            page_count=None, source="hathitrust",
            source_url=f"https://babel.hathitrust.org/cgi/pt?id={parts[0]}",
        ))

        cr_status = "pd" if rights in ("pd", "pdus") else (
            "cc_by" if rights == "cc-by" else (
                "cc_by_sa" if rights == "cc-by-sa" else (
                    "cc0" if rights == "cc-zero" else "© "
                )
            )
        )
        if cr_status in ("pd", "cc0", "cc_by", "cc_by_sa"):
            pd_rows += 1
        cr_batch.append(_copyright_row(
            isbn13, status=cr_status, jurisdiction="US",
            author_death_year=None, pd_year=year,
            license_url=None,
            evidence_url=f"https://catalog.hathitrust.org/Record/{parts[3]}",
        ))

        rows += 1
        if len(book_batch) >= 1000:
            _rw_executemany(_INSERT_BOOK, book_batch); book_batch = []
        if len(cr_batch) >= 1000:
            _rw_executemany(_INSERT_COPYRIGHT, cr_batch); cr_batch = []
        if limit and rows >= limit:
            break

    if book_batch:
        _rw_executemany(_INSERT_BOOK, book_batch)
    if cr_batch:
        _rw_executemany(_INSERT_COPYRIGHT, cr_batch)

    return {"ok": True, "rows": rows, "pd": pd_rows}


# ──────────────────────────────────────────────────────────────────────
# Task: isbn.internetArchive.ingest
# ──────────────────────────────────────────────────────────────────────


async def task_isbn_internet_archive_ingest(
    query: str = "mediatype:texts AND collection:opensource AND format:DjVuTXT",
    rows: int = 50,
    page: int = 1,
    fulltext: bool = True,
    fetchPageImages: bool = False,
    maxPagesPerBook: int = 10,
    fetchCovers: bool = True,
    license: str = "pd",
) -> dict:
    """Ingest from Internet Archive (archive.org).

    Uses the Advanced Search JSON API to enumerate texts items, then for
    each item:
      - covers   GET https://archive.org/services/img/{identifier}    (JPEG)
      - body     GET https://archive.org/download/{identifier}/{identifier}_djvu.txt
      - pages    IIIF: https://iiif.archive.org/iiif/2/{identifier}${page}/full/full/0/default.jpg
                 (only fetched when fetchPageImages=True; capped at maxPagesPerBook
                 because per-book page count can be hundreds)

    The default query targets the open-source / PD subset. Override
    `query` to target specific collections (e.g. `collection:americana`).
    Items without ISBN get a numeric synthetic ISBN-13 in the 97990 range.
    """
    api = (
        "https://archive.org/advancedsearch.php?"
        + urllib.parse.urlencode({
            "q": query,
            "fl[]": "identifier",
            "fl[]2": "title",
            "fl[]3": "creator",
            "fl[]4": "year",
            "fl[]5": "language",
            "fl[]6": "isbn",
            "fl[]7": "licenseurl",
            "rows": str(rows),
            "page": str(page),
            "output": "json",
        }).replace("fl%5B%5D2=", "fl%5B%5D=")
              .replace("fl%5B%5D3=", "fl%5B%5D=")
              .replace("fl%5B%5D4=", "fl%5B%5D=")
              .replace("fl%5B%5D5=", "fl%5B%5D=")
              .replace("fl%5B%5D6=", "fl%5B%5D=")
              .replace("fl%5B%5D7=", "fl%5B%5D=")
    )

    raw = _http_get(api, timeout=60.0)
    page_data = json.loads(raw)
    docs = (page_data.get("response") or {}).get("docs") or []

    book_batch: list[tuple[Any, ...]] = []
    cr_batch: list[tuple[Any, ...]] = []
    chap_batch: list[tuple[Any, ...]] = []
    full_batch: list[tuple[Any, ...]] = []
    img_batch: list[tuple[Any, ...]] = []
    books_inserted = 0
    chapters_inserted = 0
    images_inserted = 0

    for doc in docs:
        ident = doc.get("identifier")
        if not ident:
            continue

        title = (doc.get("title") or "")[:1000]
        creator_field = doc.get("creator")
        if isinstance(creator_field, list):
            authors = [str(a)[:200] for a in creator_field if a]
        elif isinstance(creator_field, str):
            authors = [creator_field[:200]]
        else:
            authors = []
        year = None
        y = doc.get("year")
        if y:
            m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(y))
            if m:
                year = int(m.group(0))
        language_field = doc.get("language")
        if isinstance(language_field, list) and language_field:
            lang = str(language_field[0])
        elif isinstance(language_field, str):
            lang = language_field
        else:
            lang = "en"
        license_url = doc.get("licenseurl") or ""

        # ISBN if available; otherwise synthesize from identifier hash.
        isbn13 = None
        isbns = doc.get("isbn") or []
        if isinstance(isbns, str):
            isbns = [isbns]
        for raw_isbn in isbns:
            isbn13 = _normalize_isbn13(raw_isbn)
            if isbn13:
                break
        if not isbn13:
            isbn13 = _synthetic_isbn13("3", f"internetarchive:{ident}")

        book_batch.append(_book_row(
            isbn13, isbn10=None, title=title, subtitle=None,
            authors=authors, publication_year=year, language=lang,
            page_count=None, source="internetarchive",
            source_url=f"https://archive.org/details/{ident}",
        ))
        cr_batch.append(_copyright_row(
            isbn13, status=license, jurisdiction="US",
            author_death_year=None, pd_year=year,
            license_url=license_url or None,
            evidence_url=f"https://archive.org/details/{ident}",
        ))

        # Cover image.
        if fetchCovers:
            try:
                img_bytes = _http_get(
                    f"https://archive.org/services/img/{ident}",
                    timeout=20.0,
                )
                row = _persist_image(
                    isbn13, role="cover", page_index=None,
                    image_bytes=img_bytes, source="internetarchive",
                    source_url=f"https://archive.org/services/img/{ident}",
                    license=license,
                )
                if row:
                    img_batch.append(row)
            except Exception:
                pass

        # Body text (DjVu OCR plain-text).
        if fulltext:
            try:
                body_bytes = _http_get(
                    f"https://archive.org/download/{ident}/{ident}_djvu.txt",
                    timeout=120.0,
                )
                body_text = body_bytes.decode("utf-8", errors="replace")
                chapters = _split_into_chapters(body_text)
                b2_prefix = f"internetarchive/{ident}/"
                sha256 = hashlib.sha256(body_bytes).hexdigest()
                if _B2_KEY_ID and _B2_KEY:
                    try:
                        _b2_put(_B2_BUCKET, f"{b2_prefix}original.txt",
                                body_bytes, "text/plain; charset=utf-8")
                    except Exception:
                        pass

                for n, ctitle, ctext in chapters:
                    cvid = f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_chapter/{isbn13}-{n:04d}"
                    chap_batch.append((
                        cvid, isbn13, n, ctitle[:200], ctext,
                        len(ctext), len(ctext.encode("utf-8")), lang,
                        f"{b2_prefix}ch{n:04d}.txt", "active",
                        _ISBN_ACTOR, 1, _now_iso(),
                        _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
                    ))

                full_batch.append((
                    f"at://{_ISBN_ACTOR}/com.etzhayyim.apps.isbn.book_fulltext/{isbn13}",
                    isbn13, "internetarchive",
                    f"https://archive.org/download/{ident}/{ident}_djvu.txt",
                    "text/plain", len(chapters),
                    sum(len(c[2]) for c in chapters),
                    sum(len(c[2].encode("utf-8")) for c in chapters),
                    _B2_BUCKET, b2_prefix, license, sha256, "active",
                    _ISBN_ACTOR, 1, _now_iso(),
                    _ISBN_ACTOR, _ISBN_ACTOR, "sys.bpmn.isbn",
                ))
                chapters_inserted += len(chapters)
            except Exception:
                pass

        # Per-page scan images (IIIF). Capped at maxPagesPerBook.
        if fetchPageImages and maxPagesPerBook > 0:
            for p in range(1, maxPagesPerBook + 1):
                page_url = (
                    f"https://iiif.archive.org/iiif/2/"
                    f"{ident}${p}/full/full/0/default.jpg"
                )
                try:
                    img_bytes = _http_get(page_url, timeout=20.0)
                    row = _persist_image(
                        isbn13, role="page", page_index=p,
                        image_bytes=img_bytes, source="internetarchive-iiif",
                        source_url=page_url, license=license,
                    )
                    if row:
                        img_batch.append(row)
                    else:
                        # Most likely past last page → stop iterating.
                        break
                except Exception:
                    break

        # Periodic flush to keep transaction sizes bounded.
        if len(book_batch) >= 200:
            _rw_executemany(_INSERT_BOOK, book_batch); books_inserted += len(book_batch); book_batch = []
        if len(cr_batch) >= 200:
            _rw_executemany(_INSERT_COPYRIGHT, cr_batch); cr_batch = []
        if len(chap_batch) >= 500:
            _rw_executemany(_INSERT_CHAPTER, chap_batch); chap_batch = []
        if len(full_batch) >= 200:
            _rw_executemany(_INSERT_FULLTEXT, full_batch); full_batch = []
        if len(img_batch) >= 200:
            _rw_executemany(_INSERT_IMAGE, img_batch); images_inserted += len(img_batch); img_batch = []

    if book_batch:
        _rw_executemany(_INSERT_BOOK, book_batch); books_inserted += len(book_batch)
    if cr_batch:
        _rw_executemany(_INSERT_COPYRIGHT, cr_batch)
    if chap_batch:
        _rw_executemany(_INSERT_CHAPTER, chap_batch)
    if full_batch:
        _rw_executemany(_INSERT_FULLTEXT, full_batch)
    if img_batch:
        _rw_executemany(_INSERT_IMAGE, img_batch); images_inserted += len(img_batch)

    return {
        "ok": True,
        "books": books_inserted,
        "chapters": chapters_inserted,
        "images": images_inserted,
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 21_600_000) -> None:
    """Wire all isbn task types onto the shared LangServer worker."""
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("isbn.openLibrary.ingest",     task_isbn_open_library_ingest)
    t("isbn.aozora.ingest",           task_isbn_aozora_ingest)
    t("isbn.gutenberg.ingest",        task_isbn_gutenberg_ingest)
    t("isbn.ndl.ingest",              task_isbn_ndl_ingest, ms=600_000)
    t("isbn.hathitrust.ingest",       task_isbn_hathitrust_ingest)
    t("isbn.internetArchive.ingest",  task_isbn_internet_archive_ingest)


__all__ = [
    "register",
    "task_isbn_open_library_ingest",
    "task_isbn_aozora_ingest",
    "task_isbn_gutenberg_ingest",
    "task_isbn_ndl_ingest",
    "task_isbn_hathitrust_ingest",
    "task_isbn_internet_archive_ingest",
]
