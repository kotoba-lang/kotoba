"""NDL image-first ingest primitives.

This path is intentionally separate from isbn.etzhayyim.com. NDL Digital
Collections and Online Publications are keyed by NDL pid/provider, and many
records do not have ISBNs. The durable image body is WebP in B2; RisingWave
stores catalog metadata, page image hashes, OCR text, and run/cursor state.
"""

from datetime import datetime, date, timezone
from typing import Any
from xml.etree import ElementTree as ET

import httpx
from PIL import Image

from kotodama.kotoba_datomic import get_kotoba_client

_ACTOR = "did:web:ndl.etzhayyim.com"
_B2_BUCKET = os.environ.get("B2_NDL_BUCKET", "etzhayyim-ndl").strip() or "etzhayyim-ndl"
_B2_PREFIX = os.environ.get("B2_NDL_PREFIX", "ndl/").strip().strip("/") + "/"

_SRU_NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}

_OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

_OAI_ONLINE_SET_SPECS = {
    "B00000",
    "ndl-dl-online",
    "jpro-online",
    "jpro-online-repository",
    "jpro-online-tts",
    "jpro-audiobook",
    "ndl-article-online",
    "zassaku-online",
}

_OCR_PROMPT = """\
OCR this NDL page image.
Return ONLY valid JSON:
{
  "pageText": "<full OCR text preserving line breaks>",
  "warnings": ["<uncertainty or layout note>"]
}
Do not summarize. Do not infer unreadable characters. Preserve Japanese text, ruby, punctuation, and line breaks as much as possible."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _today_date() -> str:
    return date.today().isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _http_get(url: str, *, timeout: float = 60.0, accept: str = "*/*") -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ndl.etzhayyim.com/0.1", "Accept": accept},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {exc.code} GET {url}: {detail}") from exc


def _text_or_empty(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag, _SRU_NS)
    return _element_text(el) if el is not None else ""


def _element_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    parts = [(el.text or "").strip()]
    for child in el:
        parts.append(_element_text(child))
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(part for part in parts if part).strip()


def _record_description(record_data: ET.Element) -> ET.Element:
    desc = record_data.find(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description")
    if desc is not None:
        return desc

    # NDL Search SRU may pack dcndl RDF as escaped XML text inside recordData.
    packed = html.unescape("".join(record_data.itertext()).strip())
    if packed.startswith("<"):
        try:
            packed_root = ET.fromstring(packed.encode("utf-8"))
            desc = packed_root.find(".//{http://ndl.go.jp/dcndl/terms/}BibResource")
            if desc is not None:
                return desc
            desc = packed_root.find(".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description")
            if desc is not None:
                return desc
            return packed_root
        except ET.ParseError:
            pass
    return record_data


def _extract_pid(text: str) -> str:
    for pat in (
        r"dl\.ndl\.go\.jp/(?:pid|info:ndljp/pid)/(\d+)",
        r"info:ndljp/pid/(\d+)",
        r"/iiif/(\d+)/",
    ):
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return ""


def _record_to_item(record_data: ET.Element, provider_id: str) -> dict[str, str]:
    raw = ET.tostring(record_data, encoding="utf-8")
    desc = _record_description(record_data)

    identifiers = " ".join(
        _element_text(el)
        for el in [*desc.findall("dc:identifier", _SRU_NS), *desc.findall("dcterms:identifier", _SRU_NS)]
    )
    source = _text_or_empty(desc, "dc:source")
    relation = _text_or_empty(desc, "dc:relation")
    title = _text_or_empty(desc, "dcterms:title") or _text_or_empty(desc, "dc:title")
    source_url = ""
    pid = _extract_pid(" ".join([identifiers, source, relation]))
    for el in desc.iter():
        txt = (el.text or "").strip()
        if not source_url and "ndlsearch.ndl.go.jp" in txt:
            source_url = txt
        if not pid:
            pid = _extract_pid(txt)

    if not source_url and pid:
        source_url = f"https://dl.ndl.go.jp/pid/{pid}"

    return {
        "pid": pid,
        "provider_id": provider_id,
        "title": title,
        "creator": _text_or_empty(desc, "dc:creator"),
        "issued": _text_or_empty(desc, "dcterms:issued") or _text_or_empty(desc, "dcterms:date") or _text_or_empty(desc, "dc:date"),
        "language": _text_or_empty(desc, "dc:language"),
        "material_type": _text_or_empty(desc, "dcterms:description") or _text_or_empty(desc, "dc:type"),
        "access_scope": _text_or_empty(desc, "dcterms:accessRights"),
        "content_license": _text_or_empty(desc, "dcterms:license"),
        "source_url": source_url,
        "manifest_url": f"https://dl.ndl.go.jp/api/iiif/{pid}/manifest.json" if pid else "",
        "record_xml_sha256": _sha256(raw),
    }


def _sru_page(provider_id: str, query: str, start_record: int, max_records: int) -> tuple[list[dict[str, str]], int]:
    effective_query = query.strip() or f"dpid={provider_id}"
    params = urllib.parse.urlencode(
        {
            "operation": "searchRetrieve",
            "version": "1.2",
            "recordSchema": "dcndl",
            "query": effective_query,
            "maximumRecords": str(min(max(1, int(max_records)), 200)),
            "startRecord": str(max(1, int(start_record))),
        }
    )
    raw = _http_get(f"https://ndlsearch.ndl.go.jp/api/sru?{params}", accept="application/xml")
    root = ET.fromstring(raw)
    items = [
        _record_to_item(record, provider_id)
        for record in root.findall(".//srw:record/srw:recordData", _SRU_NS)
    ]
    items = [item for item in items if item.get("pid")]
    next_el = root.find("srw:nextRecordPosition", _SRU_NS)
    next_start = int(next_el.text) if next_el is not None and (next_el.text or "").isdigit() else 0
    return items, next_start


def _oai_url(params: dict[str, str]) -> str:
    return f"https://ndlsearch.ndl.go.jp/api/oaipmh?{urllib.parse.urlencode(params)}"


def _oai_text(parent: ET.Element, path: str) -> str:
    return (parent.findtext(path, namespaces=_OAI_NS) or "").strip()


def _oai_values(parent: ET.Element, path: str) -> list[str]:
    return [(el.text or "").strip() for el in parent.findall(path, _OAI_NS) if (el.text or "").strip()]


def _oai_pid(identifier: str) -> str:
    for pat in (r"R100000039-I(\d+)$", r"I([^:]+)$"):
        m = re.search(pat, identifier)
        if m:
            return m.group(1)
    return hashlib.sha1(identifier.encode("utf-8")).hexdigest()[:24]


def _oai_record_to_item(record: ET.Element, provider_id: str, target_sets: set[str]) -> dict[str, str] | None:
    header = record.find("oai:header", _OAI_NS)
    if header is None or header.get("status") == "deleted":
        return None
    set_specs = {str(el.text or "").strip() for el in header.findall("oai:setSpec", _OAI_NS)}
    hit = set_specs.intersection(target_sets)
    if not hit:
        return None
    metadata = record.find("oai:metadata", _OAI_NS)
    if metadata is None:
        return None
    identifier = _oai_text(header, "oai:identifier")
    pid = _oai_pid(identifier)
    dates = _oai_values(metadata, ".//dc:date")
    material = "; ".join(_oai_values(metadata, ".//dc:type") or sorted(hit))
    effective_provider = provider_id
    if provider_id == "ndl-dl-online" and "ndl-dl-online" not in hit and "B00000" not in hit:
        effective_provider = sorted(hit)[0]
    source_url = f"https://ndlsearch.ndl.go.jp/books/{identifier.split(':')[-1]}" if identifier else ""
    if pid.isdigit():
        source_url = f"https://dl.ndl.go.jp/pid/{pid}"
    raw = ET.tostring(record, encoding="utf-8")
    return {
        "pid": pid,
        "provider_id": effective_provider,
        "title": _oai_text(metadata, ".//dc:title"),
        "creator": "; ".join(_oai_values(metadata, ".//dc:creator")),
        "issued": dates[0] if dates else "",
        "language": "; ".join(_oai_values(metadata, ".//dc:language")),
        "material_type": material,
        "access_scope": "",
        "content_license": "",
        "source_url": source_url,
        "manifest_url": f"https://dl.ndl.go.jp/api/iiif/{pid}/manifest.json" if pid.isdigit() else "",
        "record_xml_sha256": _sha256(raw),
    }


def _month_windows(start_year: int = 2022, start_month: int = 10) -> list[tuple[str, str]]:
    today = date.today()
    y, m = int(start_year), int(start_month)
    out: list[tuple[str, str]] = []
    while (y, m) <= (today.year, today.month):
        last = calendar.monthrange(y, m)[1]
        end = date(y, m, last)
        if end > today:
            end = today
        out.append((date(y, m, 1).isoformat(), end.isoformat()))
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def _oai_checkpoint_vertex_id(
    provider_id: str,
    set_group: str,
    window_start: str,
    window_end: str,
    pages_seen: int | None = None,
    records_seen: int | None = None,
    token: str = "",
) -> str:
    key = hashlib.sha1(f"{provider_id}|{set_group}|{window_start}|{window_end}".encode("utf-8")).hexdigest()[:20]
    if pages_seen is not None and records_seen is not None:
        token_key = hashlib.sha1(token.encode("utf-8")).hexdigest()[:12]
        return f"at://{_ACTOR}/com.etzhayyim.apps.ndl.oaiCheckpoint/{key}/{int(pages_seen)}-{int(records_seen)}-{token_key}"
    return f"at://{_ACTOR}/com.etzhayyim.apps.ndl.oaiCheckpoint/{key}"


def _read_oai_checkpoint(provider_id: str, set_group: str, window_start: str, window_end: str) -> tuple[str, int, int, int, str] | None:
    row = get_kotoba_client().select_first_where(
        "vertex_ndl_oai_checkpoint",
        "provider_id",
        provider_id,
        columns=[
            "resumption_token",
            "pages_seen",
            "records_seen",
            "items_inserted",
            "status",
        ],
        filters={
            "set_group": set_group,
            "window_start": window_start,
            "window_end": window_end,
        },
        order_by=[
            ("pages_seen", "desc"),
            ("records_seen", "desc"),
            ("updated_at", "desc"),
        ],
    )
    if row is None:
        return None
    return (
        str(row.get("resumption_token") or ""),
        int(row.get("pages_seen") or 0),
        int(row.get("records_seen") or 0),
        int(row.get("items_inserted") or 0),
        str(row.get("status") or ""),
    )


def _manifest_canvases(manifest_url: str) -> list[dict[str, Any]]:
    raw = _http_get(manifest_url, timeout=60.0, accept="application/json")
    data = json.loads(raw.decode("utf-8", errors="replace"))
    if isinstance(data.get("sequences"), list):
        seq = data["sequences"][0] if data["sequences"] else {}
        canvases = seq.get("canvases") or []
    else:
        canvases = data.get("items") or []
    return canvases if isinstance(canvases, list) else []


def _canvas_image_url(canvas: dict[str, Any], pid: str, page_index: int, image_width: int) -> str:
    url = ""
    images = canvas.get("images")
    if isinstance(images, list) and images:
        res = images[0].get("resource") if isinstance(images[0], dict) else {}
        url = str(res.get("@id") or res.get("id") or "")
    if not url:
        items = canvas.get("items")
        if isinstance(items, list) and items:
            subitems = items[0].get("items") if isinstance(items[0], dict) else []
            if isinstance(subitems, list) and subitems:
                body = subitems[0].get("body") if isinstance(subitems[0], dict) else {}
                url = str(body.get("id") or body.get("@id") or "")
    if not url:
        url = f"https://dl.ndl.go.jp/api/iiif/{pid}/R{page_index + 1:07d}/full/{image_width},/0/default.jpg"
    return _iiif_resized(url, image_width)


def _iiif_resized(url: str, image_width: int) -> str:
    pat = re.compile(r"^(https?://.+/iiif/[^/]+/R\d+)/(full|[^/]+)/([^/]+)/(\d+)/(default|bitonal|gray|color)\.(jpg|jpeg|png|webp)$")
    m = pat.match(url)
    if m:
        return f"{m.group(1)}/full/{int(image_width)},/{m.group(4)}/{m.group(5)}.jpg"
    return url


def _webp_from_image_bytes(data: bytes, quality: int) -> tuple[bytes, int | None, int | None]:
    with Image.open(io.BytesIO(data)) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        width, height = img.size
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=max(1, min(int(quality), 100)), method=6)
        return out.getvalue(), width, height


def _b2_put_webp(pid: str, page_index: int, webp: bytes) -> tuple[str, str, str]:
    from kotodama.primitives.isbn import _b2_put, _cidv1_raw_sha256

    sha = _sha256(webp)
    key = f"{_B2_PREFIX}webp/{pid}/{page_index + 1:06d}-{sha}.webp"
    _b2_put(_B2_BUCKET, key, webp, "image/webp")
    return sha, _cidv1_raw_sha256(webp), key


def _parse_ocr_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else {"pageText": str(parsed)}


def _cursor_vertex_id(provider_id: str, query: str) -> str:
    key = hashlib.sha1(f"{provider_id}|{query}".encode("utf-8")).hexdigest()[:16]
    return f"at://{_ACTOR}/com.etzhayyim.apps.ndl.ingestCursor/{provider_id}-{key}"


def _resume_start_record(provider_id: str, query: str, requested_start: int) -> int:
    if int(requested_start) > 1:
        return int(requested_start)
    row = get_kotoba_client().select_first_where(
        "vertex_ndl_ingest_cursor",
        "vertex_id",
        _cursor_vertex_id(provider_id, query),
        columns=["next_start_record"],
        filters={"status": "active"},
    )
    if row and row.get("next_start_record"):
        return max(1, int(row["next_start_record"]))
    return max(1, int(requested_start))


def _page_has_completed_ocr(pid: str, page_index: int) -> bool:
    # R0: This uses a raw Datalog query for a join equivalent.
    query_edn = f"""
    [:find ?page-id
     :where
     [?page-id :vertex_ndl_digital_page/pid "{pid}"]
     [?page-id :vertex_ndl_digital_page/page_index {page_index}]
     [?page-id :vertex_ndl_digital_page/ocr_status "completed"]
     [?page-id :vertex_ndl_digital_page/status "active"]
     [?ocr-id :vertex_ndl_ocr_text/pid "{pid}"]
     [?ocr-id :vertex_ndl_ocr_text/page_index {page_index}]
     [?ocr-id :vertex_ndl_ocr_text/status "active"]]
    """
    results = get_kotoba_client().q(query_edn)
    return bool(results)


async def _ocr_webp(webp: bytes) -> dict[str, Any]:
    engine = (os.environ.get("NDL_OCR_ENGINE") or "llm").strip().lower()
    if engine == "tesseract":
        return _ocr_webp_tesseract(webp)

    image_url = ""
    if os.environ.get("NDL_OCR_UPLOAD_IPFS", "1").lower() not in ("0", "false", "off", "no"):
        try:
            from kotodama.primitives.ipfs_ingest import add_content

            cid = await add_content(webp, f"ndl-page-{_sha256(webp)[:16]}.webp")
            image_url = f"https://ipfs.etzhayyim.com/ipfs/{cid}"
        except Exception:
            image_url = ""
    if not image_url:
        b64 = base64.b64encode(webp).decode("ascii")
        image_url = f"data:image/webp;base64,{b64}"

    model = os.environ.get("NDL_OCR_MODEL") or os.environ.get("JP_CORP_FINANCE_OCR_MODEL") or "gemma-4-e2b-it"
    llm_url = os.environ.get("NDL_OCR_URL") or os.environ.get("LLM_CHAT_COMPLETIONS_URL") or os.environ.get("etzhayyim_LLM_URL") or "https://llm.etzhayyim.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "x-kotoba-kotodama-verified": "true"}
    token = os.environ.get("LLM_etzhayyim_BEARER") or os.environ.get("etzhayyim_LLM_API_KEY") or os.environ.get("LLM_API_KEY") or ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": int(os.environ.get("NDL_OCR_MAX_TOKENS", "6000")),
    }
    async with httpx.AsyncClient(timeout=240, follow_redirects=True) as client:
        res = await client.post(llm_url, headers=headers, json=payload)
    res.raise_for_status()
    data = res.json()
    content = str(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    parsed = _parse_ocr_json(content)
    parsed["_model"] = model
    parsed["_engine"] = "llm-vision"
    return parsed


def _ocr_webp_tesseract(webp: bytes) -> dict[str, Any]:
    langs = os.environ.get("NDL_TESSERACT_LANGS", "jpn+eng")
    timeout = float(os.environ.get("NDL_TESSERACT_TIMEOUT_SEC", "180"))
    with tempfile.NamedTemporaryFile(suffix=".webp") as img:
        img.write(webp)
        img.flush()
        proc = subprocess.run(
            ["tesseract", img.name, "stdout", "-l", langs, "--psm", "6"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
    warnings = []
    stderr = (proc.stderr or "").strip()
    if stderr:
        warnings.append(stderr[:1000])
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract failed rc={proc.returncode}: {stderr[:500]}")
    return {
        "pageText": proc.stdout or "",
        "warnings": warnings,
        "_engine": "tesseract",
        "_model": f"tesseract:{langs}",
    }


def _item_insert_row(item: dict[str, str], now: str) -> dict[str, Any]:
    pid = item["pid"]
    return {
        "vertex_id": f"at://{_ACTOR}/com.etzhayyim.apps.ndl.digitalItem/{pid}",
        "created_date": _today_date(),
        "owner_did": _ACTOR,
        "pid": pid,
        "provider_id": item.get("provider_id") or "",
        "repository_no": "R100000039",
        "title": item.get("title", ""),
        "creator": item.get("creator", ""),
        "issued": item.get("issued", ""),
        "language": item.get("language", ""),
        "material_type": item.get("material_type", ""),
        "access_scope": item.get("access_scope", ""),
        "content_license": item.get("content_license", ""),
        "source_url": item.get("source_url", ""),
        "manifest_url": item.get("manifest_url", ""),
        "record_xml_sha256": item.get("record_xml_sha256", ""),
        "discovered_at": now,
        "updated_at": now,
        "org_id": _ACTOR,
        "user_id": _ACTOR,
        "actor_id": "sys.langgraph.ndl-image-ocr",
    }


def _write_oai_checkpoint(
    *,
    provider_id: str,
    set_group: str,
    metadata_prefix: str,
    window_start: str,
    window_end: str,
    resumption_token: str,
    pages_seen: int,
    records_seen: int,
    items_inserted: int,
    status: str,
    error: str = "",
) -> None:
    vertex_id = _oai_checkpoint_vertex_id(
        provider_id,
        set_group,
        window_start,
        window_end,
        pages_seen=pages_seen,
        records_seen=records_seen,
        token=resumption_token,
    )
    now = _now_iso()
    row = {
        "vertex_id": vertex_id,
        "created_date": _today_date(),
        "owner_did": _ACTOR,
        "provider_id": provider_id,
        "set_group": set_group,
        "metadata_prefix": metadata_prefix,
        "window_start": window_start,
        "window_end": window_end,
        "resumption_token": resumption_token,
        "pages_seen": int(pages_seen),
        "records_seen": int(records_seen),
        "items_inserted": int(items_inserted),
        "status": status,
        "error": error,
        "updated_at": now,
        "org_id": _ACTOR,
        "user_id": _ACTOR,
        "actor_id": "sys.langgraph.ndl-online-oai",
    }
    get_kotoba_client().insert_row("vertex_ndl_oai_checkpoint", row)


def _write_run_and_cursor(
    *,
    run_id: str,
    provider_id: str,
    query: str,
    start_record: int,
    max_records: int,
    max_items: int,
    max_pages_per_item: int,
    stats: dict[str, Any],
    status: str,
    error: str = "",
    started_at: str,
) -> None:
    finished = _now_iso()
    get_kotoba_client().insert_row(
        "vertex_ndl_ingest_run",
        {
            "vertex_id": f"at://{_ACTOR}/com.etzhayyim.apps.ndl.ingestRun/{run_id}",
            "created_date": _today_date(),
            "owner_did": _ACTOR,
            "run_id": run_id,
            "provider_id": provider_id,
            "query": query,
            "start_record": start_record,
            "max_records": max_records,
            "max_items": max_items,
            "max_pages_per_item": max_pages_per_item,
            "items_seen": int(stats.get("itemsSeen") or 0),
            "items_inserted": int(stats.get("itemsInserted") or 0),
            "pages_inserted": int(stats.get("pagesInserted") or 0),
            "pages_processed": int(stats.get("pagesProcessed") or 0),
            "ocr_inserted": int(stats.get("ocrInserted") or 0),
            "bytes_webp": int(stats.get("bytesWebp") or 0),
            "status": status,
            "error": error,
            "started_at": started_at,
            "finished_at": finished,
            "org_id": _ACTOR,
            "user_id": _ACTOR,
            "actor_id": "sys.langgraph.ndl-image-ocr",
        },
    )
    next_start = int(stats.get("nextStartRecord") or 0)
    if status == "completed" and next_start > 0:
        vertex_id = _cursor_vertex_id(provider_id, query)
        get_kotoba_client().insert_row(
            "vertex_ndl_ingest_cursor",
            {
                "vertex_id": vertex_id,
                "created_date": _today_date(),
                "owner_did": _ACTOR,
                "provider_id": provider_id,
                "query": query,
                "next_start_record": next_start,
                "last_run_id": run_id,
                "status": "active",
                "updated_at": finished,
                "org_id": _ACTOR,
                "user_id": _ACTOR,
                "actor_id": "sys.langgraph.ndl-image-ocr",
            },
        )


async def task_ndl_image_ocr_ingest(
    providerId: str = "ndl-dl-online",
    query: str = "",
    startRecord: int = 1,
    maxRecords: int = 50,
    maxItems: int = 10,
    maxPagesPerItem: int = 3,
    imageWidth: int = 1280,
    webpQuality: int = 82,
    ocr: bool = True,
    pids: list[str] | None = None,
    resume: bool = True,
) -> dict[str, Any]:
    """Collect NDL records, persist page WebP images, and OCR pages into RW."""
    run_id = f"ndl-{int(time.time())}-{providerId}"
    started = _now_iso()
    stats = {
        "runId": run_id,
        "providerId": providerId,
        "itemsSeen": 0,
        "itemsInserted": 0,
        "pagesInserted": 0,
        "pagesProcessed": 0,
        "ocrInserted": 0,
        "bytesWebp": 0,
        "nextStartRecord": 0,
    }
    try:
        pid_list = [str(pid).strip() for pid in (pids or []) if str(pid).strip()]
        effective_start_record = int(startRecord)
        if pid_list:
            items = [
                {
                    "pid": pid,
                    "provider_id": providerId,
                    "title": "",
                    "creator": "",
                    "issued": "",
                    "language": "",
                    "material_type": "",
                    "access_scope": "",
                    "content_license": "",
                    "source_url": f"https://dl.ndl.go.jp/pid/{pid}",
                    "manifest_url": f"https://dl.ndl.go.jp/api/iiif/{pid}/manifest.json",
                    "record_xml_sha256": "",
                }
                for pid in pid_list
            ]
            next_start = 0
        else:
            effective_start_record = _resume_start_record(providerId, query, int(startRecord)) if resume else int(startRecord)
            items, next_start = _sru_page(providerId, query, effective_start_record, int(maxRecords))
            if items and next_start <= effective_start_record:
                next_start = effective_start_record + len(items)
        stats["itemsSeen"] = len(items)
        stats["nextStartRecord"] = next_start
        page_limit = max(0, int(maxPagesPerItem))
        selected_items = items[: max(1, int(maxItems))]
        if page_limit <= 0:
            now = _now_iso()
            rows = [_item_insert_row(item, now) for item in selected_items]
            _rw_replace_vertices(
                "vertex_ndl_digital_item",
                [str(row["vertex_id"]) for row in rows],
                _INSERT_ITEM,
                rows,
            )
            stats["itemsInserted"] += len(rows)
            _write_run_and_cursor(
                run_id=run_id,
                provider_id=providerId,
                query=query,
                start_record=effective_start_record,
                max_records=int(maxRecords),
                max_items=int(maxItems),
                max_pages_per_item=int(maxPagesPerItem),
                stats=stats,
                status="completed",
                started_at=started,
            )
            return {"ok": True, **stats}
        for item in selected_items:
            now = _now_iso()
            pid = item["pid"]
            item_vid = f"at://{_ACTOR}/com.etzhayyim.apps.ndl.digitalItem/{pid}"
            _rw_replace_vertex(
                "vertex_ndl_digital_item",
                item_vid,
                _INSERT_ITEM,
                _item_insert_row(item, now),
            )
            stats["itemsInserted"] += 1
            try:
                canvases = _manifest_canvases(item["manifest_url"])
            except Exception:
                continue
            for page_index, canvas in enumerate(canvases[:page_limit]):
                if ocr and _page_has_completed_ocr(pid, page_index):
                    continue
                image_url = _canvas_image_url(canvas, pid, page_index, int(imageWidth))
                try:
                    img = _http_get(image_url, timeout=90.0, accept="image/*")
                    webp, width, height = _webp_from_image_bytes(img, int(webpQuality))
                    webp_sha, cid, b2_key = _b2_put_webp(pid, page_index, webp)
                    now = _now_iso()
                    page_vid = f"at://{_ACTOR}/com.etzhayyim.apps.ndl.digitalPage/{pid}-{page_index + 1:06d}"
                    page_row = {
                        "vertex_id": page_vid,
                        "created_date": _today_date(),
                        "owner_did": _ACTOR,
                        "pid": pid,
                        "provider_id": providerId,
                        "page_index": page_index,
                        "source_image_url": image_url,
                        "webp_sha256": webp_sha,
                        "webp_cid_v1": cid,
                        "webp_b2_bucket": _B2_BUCKET,
                        "webp_b2_key": b2_key,
                        "webp_byte_size": len(webp),
                        "width_px": width,
                        "height_px": height,
                        "ocr_status": "skipped" if not ocr else "pending",
                        "created_at": now,
                        "updated_at": now,
                        "org_id": _ACTOR,
                        "user_id": _ACTOR,
                        "actor_id": "sys.langgraph.ndl-image-ocr",
                    }
                    ocr_row: dict[str, Any] | None = None
                    if ocr:
                        parsed = await _ocr_webp(webp)
                        text = str(parsed.get("pageText") or "")
                        warnings = json.dumps(parsed.get("warnings") or [], ensure_ascii=False)
                        raw_json = json.dumps(parsed, ensure_ascii=False)
                        text_bytes = text.encode("utf-8")
                        ocr_vid = f"at://{_ACTOR}/com.etzhayyim.apps.ndl.ocrText/{pid}-{page_index + 1:06d}"
                        ocr_row = {
                            "vertex_id": ocr_vid,
                            "created_date": _today_date(),
                            "owner_did": _ACTOR,
                            "pid": pid,
                            "page_index": page_index,
                            "ocr_engine": str(parsed.get("_engine") or "unknown"),
                            "ocr_model": str(parsed.get("_model") or ""),
                            "ocr_text": text,
                            "ocr_json": raw_json,
                            "warnings": warnings,
                            "text_sha256": _sha256(text_bytes),
                            "text_byte_size": len(text_bytes),
                            "created_at": _now_iso(),
                            "org_id": _ACTOR,
                            "user_id": _ACTOR,
                            "actor_id": "sys.langgraph.ndl-image-ocr",
                        }
                        page_row["ocr_status"] = "completed"
                    _rw_replace_vertex(
                        "vertex_ndl_digital_page",
                        page_vid,
                        _INSERT_PAGE,
                        page_row,
                    )
                    stats["pagesInserted"] += 1
                    stats["pagesProcessed"] += 1
                    stats["bytesWebp"] += len(webp)
                    if ocr_row is not None:
                        _rw_replace_vertex(
                            "vertex_ndl_ocr_text",
                            str(ocr_row["vertex_id"]),
                            _INSERT_OCR,
                            ocr_row,
                        )
                        stats["ocrInserted"] += 1
                except Exception:
                    continue
        _write_run_and_cursor(
            run_id=run_id,
            provider_id=providerId,
            query=query,
            start_record=effective_start_record,
            max_records=int(maxRecords),
            max_items=int(maxItems),
            max_pages_per_item=int(maxPagesPerItem),
            stats=stats,
            status="completed",
            started_at=started,
        )
        return {"ok": True, **stats}
    except Exception as exc:
        try:
            _write_run_and_cursor(
                run_id=run_id,
                provider_id=providerId,
                query=query,
                start_record=effective_start_record if "effective_start_record" in locals() else int(startRecord),
                max_records=int(maxRecords),
                max_items=int(maxItems),
                max_pages_per_item=int(maxPagesPerItem),
                stats=stats,
                status="failed",
                error=str(exc),
                started_at=started,
            )
        except Exception:
            pass
        return {"ok": False, "error": str(exc), **stats, "startedAt": started, "finishedAt": _now_iso()}


async def task_ndl_online_oai_metadata_ingest(
    providerId: str = "ndl-dl-online",
    setGroup: str = "online",
    windowStart: str = "",
    windowEnd: str = "",
    metadataPrefix: str = "oai_dc",
    maxPages: int = 25,
    resume: bool = True,
) -> dict[str, Any]:
    """Ingest one OAI-PMH date window with durable resumptionToken checkpointing."""
    if not windowStart or not windowEnd:
        raise ValueError("windowStart and windowEnd are required")
    target_sets = _OAI_ONLINE_SET_SPECS if setGroup == "online" else {setGroup}
    checkpoint = _read_oai_checkpoint(providerId, setGroup, windowStart, windowEnd) if resume else None
    token = ""
    pages_seen = records_seen = items_inserted = 0
    if checkpoint is not None:
        token, pages_seen, records_seen, items_inserted, status = checkpoint
        if status == "completed":
            return {
                "ok": True,
                "providerId": providerId,
                "setGroup": setGroup,
                "windowStart": windowStart,
                "windowEnd": windowEnd,
                "pagesSeen": pages_seen,
                "recordsSeen": records_seen,
                "itemsInserted": items_inserted,
                "completed": True,
            }

    pages_this_run = 0
    try:
        while pages_this_run < max(1, int(maxPages)):
            if token:
                url = _oai_url({"verb": "ListRecords", "resumptionToken": token})
            else:
                url = _oai_url(
                    {
                        "verb": "ListRecords",
                        "metadataPrefix": metadataPrefix,
                        "from": windowStart,
                        "until": windowEnd,
                    }
                )
            root = ET.fromstring(_http_get(url, timeout=120.0, accept="application/xml"))
            error = root.findtext(".//oai:error", namespaces=_OAI_NS) or ""
            if error:
                if "no record match" in error:
                    _write_oai_checkpoint(
                        provider_id=providerId,
                        set_group=setGroup,
                        metadata_prefix=metadataPrefix,
                        window_start=windowStart,
                        window_end=windowEnd,
                        resumption_token="",
                        pages_seen=pages_seen,
                        records_seen=records_seen,
                        items_inserted=items_inserted,
                        status="completed",
                    )
                    break
                raise RuntimeError(error)

            records = root.findall(".//oai:record", _OAI_NS)
            now = _now_iso()
            items = [
                item
                for item in (_oai_record_to_item(record, providerId, target_sets) for record in records)
                if item is not None
            ]
            rows = [_item_insert_row(item, now) for item in items]
            _rw_replace_vertices(
                "vertex_ndl_digital_item",
                [str(row["vertex_id"]) for row in rows],
                _INSERT_ITEM,
                rows,
            )
            pages_seen += 1
            pages_this_run += 1
            records_seen += len(records)
            items_inserted += len(rows)
            token = root.findtext(".//oai:resumptionToken", namespaces=_OAI_NS) or ""
            _write_oai_checkpoint(
                provider_id=providerId,
                set_group=setGroup,
                metadata_prefix=metadataPrefix,
                window_start=windowStart,
                window_end=windowEnd,
                resumption_token=token,
                pages_seen=pages_seen,
                records_seen=records_seen,
                items_inserted=items_inserted,
                status="running" if token else "completed",
            )
            if not token:
                break
        return {
            "ok": True,
            "providerId": providerId,
            "setGroup": setGroup,
            "windowStart": windowStart,
            "windowEnd": windowEnd,
            "pagesSeen": pages_seen,
            "recordsSeen": records_seen,
            "itemsInserted": items_inserted,
            "pagesThisRun": pages_this_run,
            "hasCursor": bool(token),
            "completed": not bool(token),
        }
    except Exception as exc:
        _write_oai_checkpoint(
            provider_id=providerId,
            set_group=setGroup,
            metadata_prefix=metadataPrefix,
            window_start=windowStart,
            window_end=windowEnd,
            resumption_token=token,
            pages_seen=pages_seen,
            records_seen=records_seen,
            items_inserted=items_inserted,
            status="failed",
            error=str(exc),
        )
        return {
            "ok": False,
            "error": str(exc),
            "providerId": providerId,
            "setGroup": setGroup,
            "windowStart": windowStart,
            "windowEnd": windowEnd,
            "pagesSeen": pages_seen,
            "recordsSeen": records_seen,
            "itemsInserted": items_inserted,
            "hasCursor": bool(token),
        }


__all__ = ["task_ndl_image_ocr_ingest", "task_ndl_online_oai_metadata_ingest"]
