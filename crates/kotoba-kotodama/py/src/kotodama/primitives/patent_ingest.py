"""USPTO PatentsView TSV ingest + EPO OPS citation fill (BPMN/LangServer).

Zeebe cadence: `ingestUsptoWeekly.bpmn` (R/P7D Sun 00:00 UTC).
Phase 1: metadata only — no PDF fetch (handled by patent-blob-converter pod).
The `patent.blob.convert` task type must NOT be registered here.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import csv
import datetime as _dt
import hashlib
import io
import json
import os
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from typing import Generator, Any



OWNER_DID = "did:web:patent.etzhayyim.com"
ACTOR_ID = "sys.langserver.patent.ingest"
JURISDICTION_USPTO = "US"
OFFICE_ORG_ID = "USPTO"
PDF_URL_TEMPLATE = "https://image.ppubs.uspto.gov/dirsearch-public/print/downloadPdf/{patent_number}"
STREAM_CHUNK = 65536  # 64 KiB per read

_EPO_OPS_KEY = os.environ.get("EPO_OPS_CLIENT_KEY", "").strip()
_EPO_OPS_SECRET = os.environ.get("EPO_OPS_CLIENT_SECRET", "").strip()
_EPO_OPS_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_EPO_OPS_BASE = "https://ops.epo.org/3.2/rest-services"

_epo_token: str = ""
_epo_token_expires: float = 0.0


# ─── helpers ─────────────────────────────────────────────────────────────


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return _utc_now()[:10]


def _patent_vid(patent_number: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.openPatent.patent/US-{patent_number}"


def _citation_vid(citing: str, cited: str, seq: str) -> str:
    raw = f"{citing}\x1f{cited}\x1f{seq}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"at://{OWNER_DID}/com.etzhayyim.apps.openPatent.citation/{h}"


def _citation_edge_id(citing: str, cited: str) -> str:
    raw = f"{citing}\x1f{cited}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"at://{OWNER_DID}/edge.openPatent.citationPair/{h}"


def _blob_vid(patent_number: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.patentBlob.doc/US-{patent_number}"


def _foreign_patent_vid(cc: str, number: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.openPatent.patent/{cc}-{number}"


def _family_edge_id(citing: str, member_cc: str, member_num: str) -> str:
    raw = f"{citing}\x1ffam\x1f{member_cc}-{member_num}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"at://{OWNER_DID}/edge.openPatent.citationPair/{h}"


# ─── EPO OPS auth ─────────────────────────────────────────────────────────


def _epo_get_token() -> str:
    global _epo_token, _epo_token_expires
    if _epo_token and time.time() < _epo_token_expires - 60:
        return _epo_token
    if not _EPO_OPS_KEY or not _EPO_OPS_SECRET:
        raise RuntimeError("EPO_OPS_CLIENT_KEY / EPO_OPS_CLIENT_SECRET not set")
    import base64
    creds = base64.b64encode(f"{_EPO_OPS_KEY}:{_EPO_OPS_SECRET}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        _EPO_OPS_AUTH_URL,
        data=body,
        headers={"Authorization": f"Basic {creds}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        data = json.loads(resp.read())
    _epo_token = str(data["access_token"])
    _epo_token_expires = time.time() + int(data.get("expires_in", 3600))
    return _epo_token


def _epo_http_get(url: str, headers: dict[str, str], timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers=headers, method="GET")
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


# ─── streaming ZIP TSV decompressor ──────────────────────────────────────


def _skip_zip_local_header(resp: Any) -> None:
    """Advance `resp` past the ZIP local file header to the raw deflate stream."""
    sig = resp.read(4)
    if sig != b"PK\x03\x04":
        raise ValueError(f"Not a ZIP local file header: {sig!r}")
    # skip version(2)+flags(2)+compression(2)+modtime(2)+moddate(2)+crc(4)+csize(4)+usize(4) = 22 bytes
    resp.read(22)
    fname_len, extra_len = struct.unpack("<HH", resp.read(4))
    resp.read(fname_len + extra_len)


def _stream_tsv_zip(
    url: str,
    max_rows: int | None = None,
    timeout_sec: float = 300.0,
) -> Generator[list[str], None, None]:
    """Stream TSV rows from a ZIP-compressed S3 URL without loading the whole file.

    Uses raw zlib deflate decompression (wbits=-15) on the local entry's
    compressed data stream. Stops after `max_rows` data rows if set (None = unlimited).
    Yields each row as a list of strings.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "kotodama/patent-ingest"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        _skip_zip_local_header(resp)
        decomp = zlib.decompressobj(wbits=-15)
        buf = b""
        header_parsed = False
        rows_yielded = 0

        while True:
            chunk = resp.read(STREAM_CHUNK)
            if not chunk:
                break
            buf += decomp.decompress(chunk)
            # Process complete lines
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\r")
                if not header_parsed:
                    header_parsed = True
                    continue  # skip header
                if not line:
                    continue
                row = next(csv.reader([line], delimiter="\t"))
                yield row
                rows_yielded += 1
                if max_rows and rows_yielded >= max_rows:
                    return

        # Flush remaining buffer
        if buf:
            remaining = decomp.flush() + buf
            for line_bytes in remaining.split(b"\n"):
                if max_rows and rows_yielded >= max_rows:
                    return
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\r")
                if not line or not header_parsed:
                    continue
                row = next(csv.reader([line], delimiter="\t"))
                yield row
                rows_yielded += 1


# ─── patent ingest task ───────────────────────────────────────────────────


def task_patent_uspto_patentsview_ingest_patent(
    tsvUrl: str = "https://s3.amazonaws.com/data.patentsview.org/download/g_patent.tsv.zip",
    batchSize: int = 2000,
    table: str = "vertex_open_patent_patent",
    blobThresholdDate: str = "2010-01-01",
    blobTable: str = "vertex_patent_blob",
    maxRows: int | None = None,
    **_kwargs: Any,
) -> dict:
    """Stream g_patent.tsv → vertex_open_patent_patent + queue vertex_patent_blob rows."""

    now = _utc_now()
    today = _today()
    batch: list[tuple] = []
    blob_batch: list[tuple] = []
    rows_inserted = 0
    blobs_queued = 0

    # g_patent.tsv columns (0-indexed):
    # 0:patent_id 1:patent_type 2:patent_date 3:patent_title
    # 4:wipo_kind  5:num_claims   6:withdrawn   7:filename

    def _flush_patent(cur: Any, b: list[tuple]) -> int:
        if not b:
            return 0
        cols = "(vertex_id,_seq,created_date,sensitivity_ord,owner_did,office_org_id,patent_number,jurisdiction,title,ipc_classes,grant_date,verification,status,created_at,actor_id)"
        placeholders = ",".join("(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" for _ in b)
        flat = [v for row in b for v in row]
        _res = client.q(
            f"INSERT INTO {table} {cols} VALUES {placeholders}",
            flat,
        )
        return len(b)

    def _flush_blob(cur: Any, b: list[tuple]) -> int:
        if not b:
            return 0
        cols = "(vertex_id,patent_vertex_id,patent_number,jurisdiction,pdf_source_url,status,collected_at)"
        placeholders = ",".join("(%s,%s,%s,%s,%s,%s,%s)" for _ in b)
        flat = [v for row in b for v in row]
        _res = client.q(
            f"INSERT INTO {blobTable} {cols} VALUES {placeholders}",
            flat,
        )
        return len(b)

    if True:

        client = get_kotoba_client()
        _res = client.q("SET dml_rate_limit = 500")
        _res = client.q("SET statement_timeout = '300s'")

        for row in _stream_tsv_zip(tsvUrl, max_rows=maxRows, timeout_sec=1800.0):
            if len(row) < 7:
                continue
            patent_id = (row[0] or "").strip()
            patent_type = (row[1] or "").strip()
            grant_date = (row[2] or "").strip()
            title = (row[3] or "").strip()[:1024]
            wipo_kind = (row[4] or "").strip()
            withdrawn = (row[6] or "").strip()

            if not patent_id:
                continue

            status = "withdrawn" if withdrawn == "1" else ("granted" if grant_date else "pending")
            vid = _patent_vid(patent_id)

            batch.append((
                vid,          # vertex_id
                None,         # _seq
                today,        # created_date
                1,            # sensitivity_ord
                OWNER_DID,    # owner_did
                OFFICE_ORG_ID,
                patent_id,
                JURISDICTION_USPTO,
                title or None,
                wipo_kind or None,
                grant_date or None,
                "patentsview",
                status,
                now,          # created_at
                ACTOR_ID,     # actor_id
            ))

            # Queue PDF blob row for granted patents after threshold date
            if status == "granted" and grant_date >= blobThresholdDate:
                pdf_url = PDF_URL_TEMPLATE.format(patent_number=patent_id)
                blob_batch.append((
                    _blob_vid(patent_id),
                    vid,
                    patent_id,
                    JURISDICTION_USPTO,
                    pdf_url,
                    "pending",
                    now,
                ))

            if len(batch) >= batchSize:
                rows_inserted += _flush_patent(cur, batch)
                batch.clear()
            if len(blob_batch) >= batchSize:
                blobs_queued += _flush_blob(cur, blob_batch)
                blob_batch.clear()

        if batch:
            rows_inserted += _flush_patent(cur, batch)
        if blob_batch:
            blobs_queued += _flush_blob(cur, blob_batch)

    return {"ingest": {"result": {"rows": rows_inserted, "blobQueued": blobs_queued}}}


# ─── citation ingest task ─────────────────────────────────────────────────


def task_patent_uspto_patentsview_ingest_citation(
    tsvUrl: str = "https://s3.amazonaws.com/data.patentsview.org/download/g_us_patent_citation.tsv.zip",
    batchSize: int = 2000,
    vertexTable: str = "vertex_open_patent_citation",
    edgeTable: str = "edge_open_patent_citation_pair",
    maxRows: int | None = None,
    **_kwargs: Any,
) -> dict:
    """Stream g_us_patent_citation.tsv → vertex_open_patent_citation + edge_open_patent_citation_pair."""

    # g_us_patent_citation.tsv columns (0-indexed):
    # 0:patent_id  1:citation_sequence  2:citation_patent_id
    # 3:citation_date  4:record_name  5:wipo_kind  6:citation_category

    now = _utc_now()
    today = _today()
    v_batch: list[tuple] = []
    e_batch: list[tuple] = []
    rows_inserted = 0

    def _flush_vertex(cur: Any, b: list[tuple]) -> None:
        if not b:
            return
        cols = "(vertex_id,_seq,created_date,sensitivity_ord,owner_did,citing_patent,cited_patent,citation_type,source,status,created_at,actor_id)"
        placeholders = ",".join("(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" for _ in b)
        flat = [v for row in b for v in row]
        _res = client.q(
            f"INSERT INTO {vertexTable} {cols} VALUES {placeholders}",
            flat,
        )

    def _flush_edge(cur: Any, b: list[tuple]) -> None:
        if not b:
            return
        cols = "(edge_id,_seq,created_date,sensitivity_ord,owner_did,src_vid,dst_vid,role,created_at,actor_id)"
        placeholders = ",".join("(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" for _ in b)
        flat = [v for row in b for v in row]
        _res = client.q(
            f"INSERT INTO {edgeTable} {cols} VALUES {placeholders}",
            flat,
        )

    if True:

        client = get_kotoba_client()
        _res = client.q("SET dml_rate_limit = 500")
        _res = client.q("SET statement_timeout = '300s'")

        for row in _stream_tsv_zip(tsvUrl, max_rows=maxRows, timeout_sec=1800.0):
            if len(row) < 3:
                continue
            citing = (row[0] or "").strip()
            seq = (row[1] or "").strip()
            cited = (row[2] or "").strip()
            citation_category = (row[6] or "cited_by_examiner").strip() if len(row) > 6 else "cited_by_examiner"

            if not citing or not cited:
                continue

            citing_vid = _patent_vid(citing)
            cited_vid = _patent_vid(cited)
            cit_vid = _citation_vid(citing, cited, seq)
            edge_id = _citation_edge_id(citing, cited)

            v_batch.append((
                cit_vid,
                None,
                today,
                1,
                OWNER_DID,
                citing,
                cited,
                citation_category,
                "patentsview",
                "active",
                now,
                ACTOR_ID,
            ))
            e_batch.append((
                edge_id,
                None,
                today,
                1,
                OWNER_DID,
                citing_vid,
                cited_vid,
                "cites",
                now,
                ACTOR_ID,
            ))
            rows_inserted += 1

            if len(v_batch) >= batchSize:
                _flush_vertex(cur, v_batch)
                _flush_edge(cur, e_batch)
                v_batch.clear()
                e_batch.clear()

        if v_batch:
            _flush_vertex(cur, v_batch)
            _flush_edge(cur, e_batch)

    return {"citation": {"result": {"rows": rows_inserted}}}


# ─── EPO OPS citation fill ────────────────────────────────────────────────


def task_patent_epo_ops_fill_citations(
    batchSize: int = 100,
    rateLimitPerMin: int = 100,
    vertexTable: str = "vertex_open_patent_citation",
    edgeTable: str = "edge_open_patent_citation_pair",
    patentTable: str = "vertex_open_patent_patent",
    maxRows: int | None = None,
    **_kwargs: Any,
) -> dict:
    """Enrich US patents with EPO OPS citations + family edges.

    Selects up to `batchSize` granted US patents that have no EPO citations yet,
    fetches citations and patent-family from EPO OPS, and writes to
    vertex_open_patent_citation + edge_open_patent_citation_pair.
    Skips gracefully when EPO credentials are absent.
    """
    if not _EPO_OPS_KEY or not _EPO_OPS_SECRET:
        return {
            "skipped": True,
            "reason": "EPO OPS credentials not provisioned",
            "citationsAdded": 0,
            "familyEdgesAdded": 0,
        }

    try:
        token = _epo_get_token()
    except RuntimeError as e:
        return {"ok": False, "error": str(e), "citationsAdded": 0, "familyEdgesAdded": 0}

    now = _utc_now()
    today = _today()
    limit = min(batchSize, maxRows) if maxRows else batchSize
    interval_sec = 60.0 / max(1, rateLimitPerMin)
    citations_added = 0
    family_edges_added = 0

    if True:

        client = get_kotoba_client()
        _res = client.q("SET statement_timeout = '300s'")
        _res = client.q(
            f"""
            SELECT p.patent_number, p.vertex_id
            FROM {patentTable} p
            WHERE p.jurisdiction = %s
              AND p.status = 'granted'
              AND NOT EXISTS (
                  SELECT 1 FROM {vertexTable} c
                  WHERE c.citing_patent = p.patent_number
                    AND c.source = 'epo_ops'
              )
            LIMIT %s
            """,
            (JURISDICTION_USPTO, limit),
        )
        pending = _res

    if not pending:
        return {"ok": True, "citationsAdded": 0, "familyEdgesAdded": 0}

    def _flush_vertex(cur: Any, b: list[tuple]) -> int:
        if not b:
            return 0
        cols = (
            "(vertex_id,_seq,created_date,sensitivity_ord,owner_did,"
            "citing_patent,cited_patent,citation_type,source,status,created_at,actor_id)"
        )
        placeholders = ",".join("(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" for _ in b)
        _res = client.q(
            f"INSERT INTO {vertexTable} {cols} VALUES {placeholders}",
            [v for row in b for v in row],
        )
        return len(b)

    def _flush_edge(cur: Any, b: list[tuple]) -> int:
        if not b:
            return 0
        cols = "(edge_id,_seq,created_date,sensitivity_ord,owner_did,src_vid,dst_vid,role,created_at,actor_id)"
        placeholders = ",".join("(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" for _ in b)
        _res = client.q(
            f"INSERT INTO {edgeTable} {cols} VALUES {placeholders}",
            [v for row in b for v in row],
        )
        return len(b)

    if True:

        client = get_kotoba_client()
        _res = client.q("SET dml_rate_limit = 500")
        _res = client.q("SET statement_timeout = '300s'")

        for patent_number, citing_vid in pending:
            patent_number = str(patent_number or "").strip()
            if not patent_number:
                continue

            pub_ref = f"US.{patent_number}.A"
            auth_headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }

            # — citations ——————————————————————————————————————————————————
            cit_url = f"{_EPO_OPS_BASE}/published-data/publication/docdb/{pub_ref}/citations"
            try:
                raw = _epo_http_get(cit_url, headers=auth_headers)
                cit_data = json.loads(raw)
            except (RuntimeError, json.JSONDecodeError):
                time.sleep(interval_sec)
                continue

            ops_cits = (
                cit_data
                .get("ops:world-patent-data", {})
                .get("exchange-documents", {})
                .get("exchange-document", {})
                .get("citations", {})
                .get("citation", [])
            )
            if isinstance(ops_cits, dict):
                ops_cits = [ops_cits]

            v_batch: list[tuple] = []
            e_batch: list[tuple] = []

            for cit in ops_cits:
                cited_doc = cit.get("patcit", {}).get("document-id", {})
                cited_num = str(cited_doc.get("doc-number", {}).get("$", "") or "").strip()
                cited_cc = str(cited_doc.get("country", {}).get("$", "US") or "US").strip()
                if not cited_num:
                    continue

                full_cited = f"{cited_cc}-{cited_num}"
                cited_vid = (
                    _patent_vid(cited_num) if cited_cc == JURISDICTION_USPTO
                    else _foreign_patent_vid(cited_cc, cited_num)
                )
                cit_vid = _citation_vid(patent_number, full_cited, "epo")
                edge_id = _citation_edge_id(patent_number, full_cited)

                v_batch.append((
                    cit_vid, None, today, 1, OWNER_DID,
                    patent_number, full_cited,
                    "epo_ops", "epo_ops", "active", now, ACTOR_ID,
                ))
                e_batch.append((
                    edge_id, None, today, 1, OWNER_DID,
                    citing_vid, cited_vid, "cites", now, ACTOR_ID,
                ))

            citations_added += _flush_vertex(cur, v_batch)
            _flush_edge(cur, e_batch)

            # — family members ————————————————————————————————————————————
            fam_url = f"{_EPO_OPS_BASE}/family/publication/docdb/{pub_ref}"
            try:
                raw_fam = _epo_http_get(fam_url, headers=auth_headers)
                fam_data = json.loads(raw_fam)
            except (RuntimeError, json.JSONDecodeError):
                time.sleep(interval_sec)
                continue

            members = (
                fam_data.get("ops:world-patent-data", {})
                .get("ops:patent-family", {})
                .get("ops:family-member", [])
            )
            if isinstance(members, dict):
                members = [members]

            fam_batch: list[tuple] = []
            for member in members:
                pub_ref_obj = member.get("publication-reference", {}).get("document-id", {})
                if isinstance(pub_ref_obj, list):
                    pub_ref_obj = pub_ref_obj[0] if pub_ref_obj else {}
                member_num = str(pub_ref_obj.get("doc-number", {}).get("$", "") or "").strip()
                member_cc = str(pub_ref_obj.get("country", {}).get("$", "") or "").strip()
                if not member_num or not member_cc:
                    continue

                member_vid = (
                    _patent_vid(member_num) if member_cc == JURISDICTION_USPTO
                    else _foreign_patent_vid(member_cc, member_num)
                )
                fam_eid = _family_edge_id(patent_number, member_cc, member_num)
                fam_batch.append((
                    fam_eid, None, today, 1, OWNER_DID,
                    citing_vid, member_vid, "family_member", now, ACTOR_ID,
                ))

            family_edges_added += _flush_edge(cur, fam_batch)
            time.sleep(interval_sec)

    return {
        "ok": True,
        "citationsAdded": citations_added,
        "familyEdgesAdded": family_edges_added,
    }


# ─── registration ─────────────────────────────────────────────────────────


def register(worker: Any, timeout_ms: int) -> None:
    worker.task(
        task_type="patent.usptoPatentsview.ingestPatent",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_patent_uspto_patentsview_ingest_patent)

    worker.task(
        task_type="patent.usptoPatentsview.ingestCitation",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_patent_uspto_patentsview_ingest_citation)

    worker.task(
        task_type="patent.epoOps.fillCitations",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_patent_epo_ops_fill_citations)
