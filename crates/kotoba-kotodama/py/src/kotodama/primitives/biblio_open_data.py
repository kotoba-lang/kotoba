"""Global bibliographic open-data ingest primitives.

The durable schema is a property graph over official library/cultural metadata:
source -> raw record -> normalized entities -> identifiers/relations.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import io
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from PIL import Image
from kotodama.kotoba_datomic import get_kotoba_client





_ACTOR = "did:web:biblio.etzhayyim.com"
_B2_BUCKET = os.environ.get("B2_BIBLIO_BUCKET", "etzhayyim-biblio").strip() or "etzhayyim-biblio"
_B2_PREFIX = os.environ.get("B2_BIBLIO_PREFIX", "biblio/").strip().strip("/") + "/"

_OCR_PROMPT = """\
OCR this bibliographic source page image.
Return ONLY valid JSON:
{
  "pageText": "<full OCR text preserving line breaks>",
  "warnings": ["<uncertainty or layout note>"]
}
Do not summarize. Preserve original script, punctuation, and line breaks as much
as possible. The page may contain English, Hindi, Chinese, Korean, Sanskrit, or
mixed catalogue text."""


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _plain_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _first_match(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return _plain_text(match.group(1))
    return ""


def _abs_url(base: str, url: str) -> str:
    return urllib.parse.urljoin(base, html.unescape(url))


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: int = 5000) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except Exception:
        value = default
    return max(minimum, min(value, maximum))




















_SOURCES: list[dict[str, str]] = [
    {
        "source_id": "jpn-ndl-search",
        "country_code": "JPN",
        "country_name": "Japan",
        "institution_name": "National Diet Library",
        "service_name": "NDL Search",
        "base_url": "https://ndlsearch.ndl.go.jp/",
        "api_base_url": "https://ndlsearch.ndl.go.jp/api/",
        "access_protocols": "SRU,OAI-PMH,OpenSearch,LOD",
        "metadata_formats": "DC-NDL,Dublin Core,RDF",
        "machine_readability": "high",
        "geopolitical_group": "japan",
    },
    {
        "source_id": "usa-loc",
        "country_code": "USA",
        "country_name": "United States",
        "institution_name": "Library of Congress",
        "service_name": "Library of Congress APIs",
        "base_url": "https://www.loc.gov/",
        "api_base_url": "https://www.loc.gov/apis/",
        "access_protocols": "JSON API,Linked Data",
        "metadata_formats": "MARC,BIBFRAME,RDF,JSON",
        "machine_readability": "high",
        "geopolitical_group": "west",
    },
    {
        "source_id": "fra-bnf",
        "country_code": "FRA",
        "country_name": "France",
        "institution_name": "Bibliotheque nationale de France",
        "service_name": "data.bnf.fr / BnF API",
        "base_url": "https://data.bnf.fr/",
        "api_base_url": "https://www.bnf.fr/fr/portail-bnf-api-et-jeux-de-donnees",
        "access_protocols": "SPARQL,RDF,OAI-PMH,API",
        "metadata_formats": "RDF,SKOS,INTERMARC,Dublin Core",
        "machine_readability": "high",
        "geopolitical_group": "west",
    },
    {
        "source_id": "deu-dnb",
        "country_code": "DEU",
        "country_name": "Germany",
        "institution_name": "Deutsche Nationalbibliothek",
        "service_name": "DNB Metadata Services",
        "base_url": "https://www.dnb.de/",
        "api_base_url": "https://services.dnb.de/sru/",
        "access_protocols": "SRU,OAI-PMH,RDF",
        "metadata_formats": "MARC21,RDF,Dublin Core",
        "machine_readability": "high",
        "geopolitical_group": "west",
    },
    {
        "source_id": "gbr-bl-bnb",
        "country_code": "GBR",
        "country_name": "United Kingdom",
        "institution_name": "British Library",
        "service_name": "British National Bibliography / collection metadata services",
        "base_url": "https://www.bl.uk/",
        "api_base_url": "https://www.bl.uk/more/collection-metadata-services/",
        "access_protocols": "Linked Data,Z39.50,Share Family beta portal",
        "metadata_formats": "MARC21,RDF,Linked Data",
        "machine_readability": "high",
        "geopolitical_group": "west",
    },
    {
        "source_id": "aus-trove",
        "country_code": "AUS",
        "country_name": "Australia",
        "institution_name": "National Library of Australia",
        "service_name": "Trove",
        "base_url": "https://trove.nla.gov.au/",
        "api_base_url": "https://trove.nla.gov.au/about/create-something/using-api",
        "access_protocols": "JSON API",
        "metadata_formats": "JSON,MARC,Dublin Core",
        "machine_readability": "high",
        "geopolitical_group": "west",
    },
    {
        "source_id": "ind-nli-opac",
        "country_code": "IND",
        "country_name": "India",
        "institution_name": "National Library of India",
        "service_name": "National Library of India OPAC",
        "base_url": "https://nationallibrary.gov.in/",
        "api_base_url": "https://nationallibraryopac.nvli.in/",
        "access_protocols": "Koha OPAC,catalog search",
        "metadata_formats": "MARC21,Koha bibliographic records",
        "machine_readability": "medium",
        "geopolitical_group": "south-asia",
    },
    {
        "source_id": "ind-crl-inb",
        "country_code": "IND",
        "country_name": "India",
        "institution_name": "Central Reference Library",
        "service_name": "Indian National Bibliography",
        "base_url": "https://crlindia.gov.in/",
        "api_base_url": "https://crlindia.gov.in/",
        "access_protocols": "national bibliography,catalog publication",
        "metadata_formats": "MARC21,bibliographic index",
        "machine_readability": "medium-low",
        "geopolitical_group": "south-asia",
    },
    {
        "source_id": "ind-ndli",
        "country_code": "IND",
        "country_name": "India",
        "institution_name": "National Digital Library of India",
        "service_name": "NDLI Web Portal",
        "base_url": "https://www.ndl.gov.in/",
        "api_base_url": "https://www.ndl.gov.in/",
        "access_protocols": "metadata aggregation portal,repository hosting",
        "metadata_formats": "Dublin Core,source-native repository metadata",
        "machine_readability": "medium",
        "geopolitical_group": "south-asia",
    },
    {
        "source_id": "chn-nlc",
        "country_code": "CHN",
        "country_name": "China",
        "institution_name": "National Library of China",
        "service_name": "NLC search / linked-data services",
        "base_url": "https://www.nlc.cn/",
        "api_base_url": "https://www.nlc.cn/",
        "access_protocols": "catalog search,limited public linked-data endpoints",
        "metadata_formats": "CNMARC,RDF,Dublin Core",
        "machine_readability": "medium",
        "geopolitical_group": "east",
    },
    {
        "source_id": "kor-nlk-openapi",
        "country_code": "KOR",
        "country_name": "Korea",
        "institution_name": "National Library of Korea",
        "service_name": "NLK holdings and national bibliography OpenAPI",
        "base_url": "https://www.nl.go.kr/",
        "api_base_url": "https://www.data.go.kr/",
        "access_protocols": "OpenAPI,JSON,XML",
        "metadata_formats": "KORMARC,JSON,XML,Linked Open Data",
        "machine_readability": "high",
        "geopolitical_group": "east-asia",
    },
    {
        "source_id": "kor-nlk-lod",
        "country_code": "KOR",
        "country_name": "Korea",
        "institution_name": "National Library of Korea",
        "service_name": "National Bibliography Linked Open Data",
        "base_url": "https://lod.nl.go.kr/",
        "api_base_url": "https://lod.nl.go.kr/",
        "access_protocols": "LOD,SPARQL,RDF",
        "metadata_formats": "RDF,SKOS,KORMARC-derived linked data",
        "machine_readability": "high",
        "geopolitical_group": "east-asia",
    },
    {
        "source_id": "kor-nld-accessible",
        "country_code": "KOR",
        "country_name": "Korea",
        "institution_name": "National Library for the Disabled",
        "service_name": "National accessible materials union catalog OpenAPI",
        "base_url": "https://www.nld.go.kr/",
        "api_base_url": "https://dream.nld.go.kr/newApp/app/book/",
        "access_protocols": "OpenAPI,XML",
        "metadata_formats": "XML,catalog metadata",
        "machine_readability": "medium-high",
        "geopolitical_group": "east-asia",
    },
    {
        "source_id": "rus-rsl",
        "country_code": "RUS",
        "country_name": "Russia",
        "institution_name": "Russian State Library",
        "service_name": "RSL electronic catalogue",
        "base_url": "https://www.rsl.ru/",
        "api_base_url": "https://www.rsl.ru/",
        "access_protocols": "catalog search,limited public API",
        "metadata_formats": "RUSMARC,MARC,Dublin Core",
        "machine_readability": "medium-low",
        "geopolitical_group": "east",
    },
    {
        "source_id": "rus-nlr",
        "country_code": "RUS",
        "country_name": "Russia",
        "institution_name": "National Library of Russia",
        "service_name": "NLR online catalogues",
        "base_url": "https://nlr.ru/",
        "api_base_url": "https://nlr.ru/",
        "access_protocols": "catalog search,limited public API",
        "metadata_formats": "RUSMARC,MARC",
        "machine_readability": "medium-low",
        "geopolitical_group": "east",
    },
    {
        "source_id": "irn-nlai",
        "country_code": "IRN",
        "country_name": "Iran",
        "institution_name": "National Library and Archives of Iran",
        "service_name": "NLAI national bibliography/catalogue",
        "base_url": "https://www.nlai.ir/",
        "api_base_url": "https://www.nlai.ir/",
        "access_protocols": "catalog search,limited public API",
        "metadata_formats": "MARC,FRBR-oriented authority data",
        "machine_readability": "medium-low",
        "geopolitical_group": "east",
    },
    {
        "source_id": "eur-europeana",
        "country_code": "EUR",
        "country_name": "Europe",
        "institution_name": "Europeana Foundation",
        "service_name": "Europeana APIs",
        "base_url": "https://www.europeana.eu/",
        "api_base_url": "https://www.europeana.eu/en/apis",
        "access_protocols": "JSON API,SPARQL,OAI-PMH",
        "metadata_formats": "EDM,RDF,Dublin Core",
        "machine_readability": "high",
        "geopolitical_group": "aggregator",
    },
]

_COUNTRY_SOURCE_IDS: dict[str, list[str]] = {
    "india": ["ind-nli-opac", "ind-crl-inb", "ind-ndli"],
    "ind": ["ind-nli-opac", "ind-crl-inb", "ind-ndli"],
    "china": ["chn-nlc"],
    "chn": ["chn-nlc"],
    "korea": ["kor-nlk-openapi", "kor-nlk-lod", "kor-nld-accessible"],
    "kor": ["kor-nlk-openapi", "kor-nlk-lod", "kor-nld-accessible"],
}


def _insert(table: Table, row: dict[str, Any]) -> int:
    return sa_rowcount(table.insert().values(**row))


def _http_get(url: str, *, timeout: float = 60.0, accept: str = "*/*") -> bytes:
    timeout_max = os.environ.get("BIBLIO_HTTP_TIMEOUT_MAX_SEC", "").strip()
    if timeout_max:
        try:
            timeout = min(float(timeout), float(timeout_max))
        except Exception:
            pass
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "biblio.etzhayyim.com/0.1", "Accept": accept},
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


def _webp_from_image_bytes(data: bytes, quality: int) -> tuple[bytes, int | None, int | None]:
    with Image.open(io.BytesIO(data)) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        width, height = img.size
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=max(1, min(int(quality), 100)), method=6)
        return out.getvalue(), width, height


def _b2_put_webp(
    source_id: str,
    source_record_id: str,
    page_index: int,
    webp: bytes,
) -> tuple[str, str, str]:
    from kotodama.primitives.isbn import _b2_put, _cidv1_raw_sha256

    sha = _sha256(webp)
    safe_record_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", source_record_id)[:120] or sha[:16]
    key = f"{_B2_PREFIX}webp/{source_id}/{safe_record_id}/{page_index + 1:06d}-{sha}.webp"
    try:
        _b2_put(_B2_BUCKET, key, webp, "image/webp")
    except Exception:
        if os.environ.get("BIBLIO_OCR_REQUIRE_B2", "0").lower() in {"1", "true", "yes"}:
            raise
        return sha, _cidv1_raw_sha256(webp), ""
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


async def _ocr_webp(webp: bytes) -> dict[str, Any]:
    engine = (os.environ.get("BIBLIO_OCR_ENGINE") or "llm").strip().lower()
    if engine == "tesseract":
        return _ocr_webp_tesseract(webp)

    image_url = ""
    if os.environ.get("BIBLIO_OCR_UPLOAD_IPFS", "1").lower() not in {
        "0",
        "false",
        "off",
        "no",
    }:
        try:
            from kotodama.primitives.ipfs_ingest import add_content

            cid = await add_content(webp, f"biblio-page-{_sha256(webp)[:16]}.webp")
            image_url = f"https://ipfs.etzhayyim.com/ipfs/{cid}"
        except Exception:
            image_url = ""
    if not image_url:
        b64 = base64.b64encode(webp).decode("ascii")
        image_url = f"data:image/webp;base64,{b64}"

    model = (
        os.environ.get("BIBLIO_OCR_MODEL")
        or os.environ.get("NDL_OCR_MODEL")
        or os.environ.get("JP_CORP_FINANCE_OCR_MODEL")
        or "gemma-4-e2b-it"
    )
    llm_url = (
        os.environ.get("BIBLIO_OCR_URL")
        or os.environ.get("NDL_OCR_URL")
        or os.environ.get("LLM_CHAT_COMPLETIONS_URL")
        or os.environ.get("etzhayyim_LLM_URL")
        or "https://llm.etzhayyim.com/v1/chat/completions"
    )
    headers = {"Content-Type": "application/json", "x-kotoba-kotodama-verified": "true"}
    token = (
        os.environ.get("LLM_etzhayyim_BEARER")
        or os.environ.get("etzhayyim_LLM_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or ""
    )
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
        "max_tokens": int(os.environ.get("BIBLIO_OCR_MAX_TOKENS", "6000")),
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
    langs = os.environ.get("BIBLIO_TESSERACT_LANGS", "eng+hin+chi_sim+kor")
    timeout = float(os.environ.get("BIBLIO_TESSERACT_TIMEOUT_SEC", "180"))
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


def _run_coro_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: dict[str, Any] = {}

    def _target() -> None:
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:
            box["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _base_row(vertex_id: str, now: str) -> dict[str, Any]:
    return {
        "vertex_id": vertex_id,
        "_seq": 0,
        "sensitivity_ord": 2,
        "owner_did": _ACTOR,
        "org_id": _ACTOR,
        "user_id": _ACTOR,
        "actor_id": "sys.langgraph.biblio-open-data",
        "created_at": now,
    }


def _seed_sources(only: set[str] | None = None) -> int:
    now = _now_iso()
    inserted = 0
    for src in _SOURCES:
        if only and src["source_id"] not in only:
            continue
        row = {
            "vertex_id": f"at://{_ACTOR}/com.etzhayyim.apps.biblio.source/{src['source_id']}",
            "_seq": 0,
            "sensitivity_ord": 2,
            "owner_did": _ACTOR,
            "status": "active",
            "discovered_at": now,
            "updated_at": now,
            "rights_note": "verify source-specific reuse terms before redistribution",
            "org_id": _ACTOR,
            "user_id": _ACTOR,
            "actor_id": "sys.langgraph.biblio-open-data",
            **src,
        }
        inserted += _insert(vertex_biblio_source, row)
    return inserted


def _raw_record_id(source_id: str, payload: dict[str, Any]) -> str:
    explicit = (
        payload.get("id")
        or payload.get("source_record_id")
        or payload.get("identifier")
        or payload.get("url")
    )
    if explicit:
        return str(explicit)
    return _sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))[:32]


def _raw_record_row(source_id: str, run_id: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    now = _now_iso()
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    source_record_id = _raw_record_id(source_id, payload)
    record_hash = _sha256_text(source_record_id)[:24]
    vertex_id = f"at://{_ACTOR}/com.etzhayyim.apps.biblio.rawRecord/{source_id}/{record_hash}"
    return source_record_id, {
        "vertex_id": vertex_id,
        "_seq": 0,
        "sensitivity_ord": 2,
        "owner_did": _ACTOR,
        "source_id": source_id,
        "source_record_id": source_record_id,
        "harvest_run_id": run_id,
        "protocol": str(payload.get("_protocol") or "manual-json"),
        "record_schema": str(payload.get("_schema") or "source-native-json"),
        "content_type": "application/json",
        "raw_payload": raw,
        "raw_sha256": _sha256_text(raw),
        "fetched_at": now,
        "source_updated_at": str(payload.get("updated") or payload.get("updated_at") or ""),
        "status": "active",
        "error": "",
        "org_id": _ACTOR,
        "user_id": _ACTOR,
        "actor_id": "sys.langgraph.biblio-open-data",
    }


def _insert_raw_record(source_id: str, run_id: str, payload: dict[str, Any]) -> tuple[str, int]:
    source_record_id, row = _raw_record_row(source_id, run_id, payload)
    return source_record_id, _insert(vertex_biblio_raw_record, row)


def _entity_identifier_rows(
    source_id: str,
    source_record_id: str,
    payload: dict[str, Any],
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    now = _now_iso()
    title = str(payload.get("title") or payload.get("name") or source_record_id)
    entity_type = str(payload.get("entity_type") or "Manifestation")
    entity_hash = _sha256_text(source_record_id + entity_type)[:24]
    entity_id = f"at://{_ACTOR}/com.etzhayyim.apps.biblio.entity/{source_id}/{entity_hash}"
    publication_year = payload.get("publication_year") or payload.get("year")
    try:
        publication_year_int = int(publication_year) if publication_year else None
    except Exception:
        publication_year_int = None
    entity_row = {
        **_base_row(entity_id, now),
        "entity_type": entity_type,
        "canonical_label": title,
        "original_label": title,
        "normalized_label": _normalize(title),
        "language": str(payload.get("language") or ""),
        "country_code": str(payload.get("country_code") or ""),
        "publication_year": publication_year_int,
        "source_id": source_id,
        "source_record_id": source_record_id,
        "source_url": str(payload.get("url") or payload.get("source_url") or ""),
        "metadata_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "confidence": 0.85,
        "status": "active",
        "updated_at": now,
    }
    identifier_rows: list[dict[str, Any]] = []
    for scheme in ("isbn", "issn", "doi", "oclc", "ndl_id", "loc_id", "source_record_id"):
        value = payload.get(scheme)
        if scheme == "source_record_id":
            value = source_record_id
        if not value:
            continue
        value_s = str(value)
        ident_hash = _sha256_text(value_s)[:24]
        ident_id = f"at://{_ACTOR}/com.etzhayyim.apps.biblio.identifier/{scheme}/{ident_hash}"
        identifier_rows.append({
            **_base_row(ident_id, now),
            "identifier_scheme": scheme,
            "identifier_value": value_s,
            "normalized_value": _normalize(value_s).replace("-", ""),
            "entity_vertex_id": entity_id,
            "source_id": source_id,
            "status": "active",
        })
    return entity_id, entity_row, identifier_rows


def _insert_entity_from_raw(
    source_id: str,
    source_record_id: str,
    payload: dict[str, Any],
) -> tuple[str, int, int]:
    entity_id, entity_row, identifier_rows = _entity_identifier_rows(
        source_id,
        source_record_id,
        payload,
    )
    entities = _insert(vertex_biblio_entity, entity_row)
    identifiers = 0
    for row in identifier_rows:
        identifiers += _insert(vertex_biblio_identifier, row)
    return entity_id, entities, identifiers


def _insert_run(row: dict[str, Any]) -> int:
    return _insert(vertex_biblio_ingest_run, row)


def _assert_run_visible(run_id: str) -> None:
    timeout_seconds = _env_int(
        "BIBLIO_RUN_VISIBILITY_TIMEOUT_SECONDS",
        240,
        minimum=1,
        maximum=900,
    )
    poll_seconds = _env_int(
        "BIBLIO_RUN_VISIBILITY_POLL_SECONDS",
        5,
        minimum=1,
        maximum=60,
    )

    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while True:
        try:
            row = get_kotoba_client().select_first_where("vertex_biblio_ingest_run", "run_id", run_id)
        except Exception as exc:
            row = None
            last_error = str(exc)
        if row:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            detail = f"; last visibility check error: {last_error}" if last_error else ""
            raise RuntimeError(
                f"ingest run {run_id} not visible after insert within "
                f"{timeout_seconds}s; kotoba Datomic client read visibility may be stalled{detail}"
            )
        time.sleep(min(poll_seconds, remaining))


def _source_ids_for_countries(countries: list[str] | None) -> list[str]:
    wanted = countries or ["india", "china", "korea"]
    source_ids: list[str] = []
    seen: set[str] = set()
    for country in wanted:
        for source_id in _COUNTRY_SOURCE_IDS.get(str(country).strip().lower(), []):
            if source_id not in seen:
                source_ids.append(source_id)
                seen.add(source_id)
    return source_ids


def _adapter_plan(source_id: str, max_records: int) -> dict[str, Any]:
    plans: dict[str, dict[str, Any]] = {
        "ind-nli-opac": {
            "adapter": "koha-opac",
            "entrypoint": "https://nationallibraryopac.nvli.in/",
            "status": "catalog-probe",
            "notes": "Koha OPAC is public; bounded HTML/MARC extraction is a follow-up adapter.",
        },
        "ind-crl-inb": {
            "adapter": "national-bibliography-page",
            "entrypoint": "https://crlindia.gov.in/",
            "status": "catalog-probe",
            "notes": "INB is authoritative but public machine API is not confirmed.",
        },
        "ind-ndli": {
            "adapter": "metadata-aggregation-portal",
            "entrypoint": "https://www.ndl.gov.in/",
            "status": "catalog-probe",
            "notes": "NDLI aggregates metadata; API/key policy must be verified per tenant.",
        },
        "chn-nlc": {
            "adapter": "nlc-catalog-lod-probe",
            "entrypoint": "https://www.nlc.cn/",
            "status": "catalog-probe",
            "notes": (
                "NLC public machine endpoints are limited; prefer official "
                "LOD/API where available."
            ),
        },
        "kor-nlk-openapi": {
            "adapter": "data-go-kr-openapi",
            "entrypoint": "https://www.data.go.kr/",
            "status": "credentialed-openapi",
            "env": "DATA_GO_KR_SERVICE_KEY",
            "notes": "Use Public Data Portal key; normalize JSON/XML to raw/entity rows.",
        },
        "kor-nlk-lod": {
            "adapter": "nlk-lod",
            "entrypoint": "https://lod.nl.go.kr/",
            "status": "lod",
            "notes": "Use RDF/SPARQL adapter for national bibliography linked data.",
        },
        "kor-nld-accessible": {
            "adapter": "nld-accessible-materials-openapi",
            "entrypoint": "https://dream.nld.go.kr/newApp/app/book/",
            "status": "public-xml-openapi",
            "notes": "XML catalog API for accessible materials union catalog.",
        },
    }
    plan = dict(plans.get(source_id, {"adapter": "manual-json", "status": "manual"}))
    plan["sourceId"] = source_id
    plan["maxRecords"] = max(1, min(int(max_records), _env_int("BIBLIO_MAX_RECORDS_HARD_LIMIT", 1000)))
    return plan


def _extract_links(base_url: str, html_text: str, *, same_host: bool = True) -> list[tuple[str, str]]:
    base_host = urllib.parse.urlparse(base_url).netloc.lower()
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r"(?is)<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", html_text):
        href = html.unescape(match.group(1)).strip()
        if href.startswith(("mailto:", "javascript:", "tel:")):
            continue
        url = _abs_url(base_url, href)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if same_host and parsed.netloc.lower() != base_host:
            continue
        normalized = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))
        if normalized in seen:
            continue
        seen.add(normalized)
        label = _plain_text(match.group(2)) or normalized
        links.append((normalized, label[:300]))
    return links


def _extract_image_urls(base_url: str, html_text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"(?is)<img\b[^>]*(?:src|data-src)=[\"']([^\"']+)[\"'][^>]*>", html_text):
        value = html.unescape(match.group(1)).strip()
        if not value or value.startswith("data:"):
            continue
        url = _abs_url(base_url, value)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        lowered = parsed.path.lower()
        if not lowered.endswith((".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")):
            continue
        if url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def _record_from_html_detail(
    *,
    source_id: str,
    url: str,
    html_text: str,
    fallback_title: str,
    protocol: str,
) -> dict[str, Any]:
    title = _first_match(
        [
            r"<h1[^>]*>(.*?)</h1>",
            r"<title[^>]*>(.*?)</title>",
            r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)",
            r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:title[\"']",
        ],
        html_text,
    ) or fallback_title
    isbn = _first_match(
        [
            r"ISBN(?:-13|-10)?\s*:?\s*</?[^>]*>\s*([0-9Xx\-\s]{10,20})",
            r"\bISBN(?:-13|-10)?\s*:?\s*([0-9Xx\-\s]{10,20})",
        ],
        html_text,
    )
    year = _first_match(
        [
            r"Publication details[^<]*</?[^>]*>\s*([^<]*\b(18|19|20)\d{2}[^<]*)",
            r"\b((18|19|20)\d{2})\b",
        ],
        html_text,
    )
    publication_year = ""
    year_match = re.search(r"\b(18|19|20)\d{2}\b", year)
    if year_match:
        publication_year = year_match.group(0)
    record = {
        "source_id": source_id,
        "source_record_id": f"{source_id}:{_sha256_text(url)[:24]}",
        "title": title,
        "isbn": isbn.replace(" ", "").replace("-", "") if isbn else "",
        "publication_year": publication_year,
        "url": url,
        "_protocol": protocol,
        "_schema": "html-catalog-detail",
        "_fetched_content_sha256": _sha256_text(html_text),
        "_fetched_sample": html_text[:20000],
    }
    image_urls = _extract_image_urls(url, html_text)
    if image_urls:
        record["imageUrls"] = image_urls[:5]
    return record


def _fetch_koha_opac_records(source_id: str, max_records: int) -> list[dict[str, Any]]:
    base = "https://nationallibraryopac.nvli.in/"
    queries = [
        "india",
        "history",
        "science",
        "literature",
        "language",
        "economics",
        "education",
        "law",
        "medicine",
        "technology",
    ]
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_size = max(20, min(max_records, 50))
    detail_limit = _env_int("BIBLIO_KOHA_DETAIL_LIMIT", 40, minimum=0, maximum=500)
    details_fetched = 0
    for query in queries:
        if len(records) >= max_records:
            break
        for offset in range(0, max_records, page_size):
            if len(records) >= max_records:
                break
            url = (
                base
                + "cgi-bin/koha/opac-search.pl?"
                + urllib.parse.urlencode({"q": query, "count": page_size, "offset": offset})
            )
            try:
                page = _http_get(url, timeout=45.0, accept="text/html,*/*").decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception as exc:
                records.append({
                    "source_id": source_id,
                    "source_record_id": f"{source_id}:search-error:{_sha256_text(query + str(exc))[:16]}",
                    "title": f"Koha search error for {query}",
                    "url": url,
                    "_protocol": "koha-opac-search",
                    "_schema": "adapter-error",
                    "error": str(exc),
                })
                break
            result_links: list[tuple[str, str]] = []
            for match in re.finditer(
                r"(?is)<a\b[^>]*href=[\"']([^\"']*biblionumber=(\d+)[^\"']*)[\"'][^>]*>(.*?)</a>",
                page,
            ):
                href, bib, label = match.groups()
                if bib not in seen:
                    result_links.append((bib, _plain_text(label) or f"National Library of India record {bib}"))
            if not result_links:
                result_links = [
                    (bib, f"National Library of India record {bib}")
                    for bib in re.findall(r"biblionumber=(\d+)", page)
                    if bib not in seen
                ]
            new_bibs = [bib for bib, _label in result_links if bib not in seen]
            if not new_bibs:
                break
            for bib, label in result_links:
                if len(records) >= max_records:
                    break
                if bib in seen:
                    continue
                seen.add(bib)
                detail_url = base + f"cgi-bin/koha/opac-detail.pl?biblionumber={bib}"
                if details_fetched >= detail_limit:
                    records.append({
                        "source_id": source_id,
                        "source_record_id": f"{source_id}:koha:{bib}",
                        "title": label,
                        "url": detail_url,
                        "koha_biblionumber": bib,
                        "_protocol": "koha-opac-search",
                        "_schema": "koha-search-result",
                        "_search_query": query,
                        "_search_offset": offset,
                    })
                    continue
                try:
                    detail = _http_get(
                        detail_url,
                        timeout=15.0,
                        accept="text/html,*/*",
                    ).decode("utf-8", errors="replace")
                    rec = _record_from_html_detail(
                        source_id=source_id,
                        url=detail_url,
                        html_text=detail,
                        fallback_title=f"National Library of India record {bib}",
                        protocol="koha-opac-html",
                    )
                    rec["koha_biblionumber"] = bib
                    records.append(rec)
                    details_fetched += 1
                except Exception as exc:
                    records.append({
                        "source_id": source_id,
                        "source_record_id": f"{source_id}:detail-error:{bib}",
                        "title": label,
                        "url": detail_url,
                        "_protocol": "koha-opac-html",
                        "_schema": "adapter-error",
                        "error": str(exc),
                    })
    return records[:max_records]


def _fetch_static_catalog_records(source_id: str, max_records: int) -> list[dict[str, Any]]:
    src = _source_by_id(source_id)
    url = src.get("api_base_url") or src.get("base_url") or ""
    if not url:
        return []
    try:
        raw = _http_get(url, timeout=45.0, accept="text/html,application/xml,*/*")
        text = raw.decode("utf-8", errors="replace")
        records = [
            {
                "source_id": source_id,
                "source_record_id": f"{source_id}:portal:{_sha256(raw)[:16]}",
                "title": _first_match([r"<title[^>]*>(.*?)</title>"], text)
                or f"{src.get('service_name') or source_id} portal snapshot",
                "url": url,
                "_protocol": "portal-crawl",
                "_schema": "html-portal-root",
                "_fetched_content_sha256": _sha256(raw),
                "_fetched_sample": text[:20000],
                "_adapter_note": "Official portal has no confirmed unauthenticated bibliographic item API; persisted official portal crawl records.",
            }
        ]
        for link_url, link_title in _extract_links(url, text):
            if len(records) >= max_records:
                break
            records.append({
                "source_id": source_id,
                "source_record_id": f"{source_id}:portal-link:{_sha256_text(link_url)[:24]}",
                "title": link_title or f"{src.get('service_name') or source_id} linked page",
                "url": link_url,
                "_protocol": "portal-crawl",
                "_schema": "html-portal-link",
                "_parent_url": url,
            })
        return records[:max_records]
    except Exception as exc:
        return [
            {
                "source_id": source_id,
                "source_record_id": f"{source_id}:portal-error:{_sha256_text(str(exc))[:16]}",
                "title": f"{src.get('service_name') or source_id} portal fetch error",
                "url": url,
                "_protocol": "bounded-portal-snapshot",
                "_schema": "adapter-error",
                "error": str(exc),
            }
        ]


def _xml_find_text(node: ET.Element, names: tuple[str, ...]) -> str:
    lowered = {name.lower() for name in names}
    for elem in node.iter():
        name = elem.tag.rsplit("}", 1)[-1].lower()
        if name in lowered and elem.text:
            value = elem.text.strip()
            if value:
                return value
    return ""


def _fetch_data_go_kr_records(source_id: str, max_records: int) -> list[dict[str, Any]]:
    service_key = (
        os.environ.get("DATA_GO_KR_SERVICE_KEY")
        or os.environ.get("KOREA_DATA_GO_KR_SERVICE_KEY")
        or ""
    ).strip()
    endpoint = (
        os.environ.get(f"BIBLIO_{source_id.upper().replace('-', '_')}_URL")
        or "https://www.nl.go.kr/korcis/openAPI/contents.do"
    )
    if not service_key:
        return [
            {
                "source_id": source_id,
                "source_record_id": f"{source_id}:credential-required",
                "title": "Korea public data OpenAPI credential required",
                "url": endpoint,
                "_protocol": "data-go-kr-openapi",
                "_schema": "credential-required",
                "error": "DATA_GO_KR_SERVICE_KEY is not configured",
            }
        ][:max_records]
    page_size = max(1, min(max_records, 100))
    records: list[dict[str, Any]] = []
    try:
        for page_no in range(1, (max_records + page_size - 1) // page_size + 1):
            params = {
                "serviceKey": service_key,
                "ServiceKey": service_key,
                "pageNo": str(page_no),
                "numOfRows": str(page_size),
                "type": "xml",
            }
            url = endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode(params)
            raw = _http_get(url, timeout=60.0, accept="application/xml,text/xml,*/*")
            root = ET.fromstring(raw)
            item_nodes = [
                node
                for node in root.iter()
                if node.tag.rsplit("}", 1)[-1].lower() in {"item", "record", "doc", "data"}
            ]
            if not item_nodes and page_no == 1:
                item_nodes = [root]
            if not item_nodes:
                break
            before = len(records)
            for idx, item in enumerate(item_nodes):
                if len(records) >= max_records:
                    break
                title = _xml_find_text(item, ("title", "titleInfo", "ttl", "name", "bookname"))
                author = _xml_find_text(item, ("author", "creator", "writer", "authr"))
                publisher = _xml_find_text(item, ("publisher", "pub", "pubPlace"))
                year = _xml_find_text(item, ("year", "pubYear", "publicationYear", "date"))
                identifier = (
                    _xml_find_text(item, ("isbn", "issn", "id", "controlNo", "regNo"))
                    or f"page-{page_no}-row-{idx}"
                )
                records.append({
                    "source_id": source_id,
                    "source_record_id": f"{source_id}:{_sha256_text(identifier)[:24]}",
                    "title": title or f"{source_id} OpenAPI item {len(records) + 1}",
                    "author": author,
                    "publisher": publisher,
                    "publication_year": (re.search(r"(18|19|20)\d{2}", year or "") or [""])[0],
                    "isbn": _xml_find_text(item, ("isbn",)),
                    "url": endpoint,
                    "_protocol": "data-go-kr-openapi",
                    "_schema": "xml-openapi-item",
                    "_page_no": page_no,
                    "_raw_xml": ET.tostring(item, encoding="unicode")[:20000],
                })
            if len(records) == before or len(item_nodes) < page_size:
                break
        return records
    except Exception as exc:
        return [
            {
                "source_id": source_id,
                "source_record_id": f"{source_id}:openapi-error:{_sha256_text(str(exc))[:16]}",
                "title": f"{source_id} OpenAPI fetch error",
                "url": endpoint,
                "_protocol": "data-go-kr-openapi",
                "_schema": "adapter-error",
                "error": str(exc),
            }
        ]


def _fetch_lod_records(source_id: str, max_records: int) -> list[dict[str, Any]]:
    endpoint = (
        os.environ.get("BIBLIO_KOR_NLK_LOD_SPARQL_URL")
        or "https://lod.nl.go.kr/sparql"
    )
    page_size = max(1, min(max_records, 100))
    records: list[dict[str, Any]] = []
    try:
        for offset in range(0, max_records, page_size):
            query = f"""
                SELECT ?s ?title WHERE {{
                  ?s ?p ?title .
                  FILTER(isLiteral(?title))
                }} LIMIT {page_size} OFFSET {offset}
            """
            url = endpoint + "?" + urllib.parse.urlencode({"query": query, "format": "application/sparql-results+json"})
            raw = _http_get(url, timeout=60.0, accept="application/sparql-results+json,application/json,*/*")
            data = json.loads(raw.decode("utf-8", errors="replace"))
            bindings = ((data.get("results") or {}).get("bindings") or [])
            if not bindings:
                break
            for binding in bindings:
                if len(records) >= max_records:
                    break
                subject = str((binding.get("s") or {}).get("value") or f"row-{len(records)}")
                title = str((binding.get("title") or {}).get("value") or subject)
                records.append({
                    "source_id": source_id,
                    "source_record_id": f"{source_id}:{_sha256_text(subject)[:24]}",
                    "title": title,
                    "url": subject if subject.startswith("http") else endpoint,
                    "_protocol": "sparql-lod",
                    "_schema": "sparql-json-binding",
                    "_sparql_binding": binding,
                    "_sparql_offset": offset,
                })
        return records or _fetch_static_catalog_records(source_id, max_records)
    except Exception as exc:
        recs = _fetch_static_catalog_records(source_id, max_records)
        for rec in recs:
            rec["_sparql_error"] = str(exc)
        return recs


def _fetch_source_records(source_id: str, max_records: int) -> list[dict[str, Any]]:
    bounded = max(1, min(int(max_records), _env_int("BIBLIO_MAX_RECORDS_HARD_LIMIT", 1000)))
    if source_id == "ind-nli-opac":
        return _fetch_koha_opac_records(source_id, bounded)
    if source_id in {"ind-crl-inb", "ind-ndli", "chn-nlc"}:
        return _fetch_static_catalog_records(source_id, bounded)
    if source_id in {"kor-nlk-openapi", "kor-nld-accessible"}:
        return _fetch_data_go_kr_records(source_id, bounded)
    if source_id == "kor-nlk-lod":
        return _fetch_lod_records(source_id, bounded)
    return _fetch_static_catalog_records(source_id, bounded)


def _source_by_id(source_id: str) -> dict[str, str]:
    for src in _SOURCES:
        if src["source_id"] == source_id:
            return src
    return {}


def _probe_source_entrypoint(source_id: str, run_id: str, timeout: float = 30.0) -> dict[str, Any]:
    src = _source_by_id(source_id)
    url = src.get("api_base_url") or src.get("base_url") or ""
    if not url:
        return {
            "source_id": source_id,
            "source_record_id": f"{source_id}:missing-entrypoint",
            "title": f"{source_id} missing entrypoint",
            "_protocol": "entrypoint-probe",
            "_schema": "probe-error",
            "error": "source has no api_base_url/base_url",
        }
    max_bytes = int(os.environ.get("BIBLIO_PROBE_MAX_BYTES", "200000"))
    try:
        raw = _http_get(
            url,
            timeout=timeout,
            accept="text/html,application/json,application/xml,*/*",
        )
        sample = raw[:max_bytes].decode("utf-8", errors="replace")
        return {
            "source_id": source_id,
            "source_record_id": f"{source_id}:entrypoint:{_sha256(raw)[:16]}",
            "title": f"{src.get('service_name') or source_id} entrypoint probe",
            "url": url,
            "_protocol": "entrypoint-probe",
            "_schema": "html-json-xml-sample",
            "_fetched_content_sha256": _sha256(raw),
            "_fetched_sample": sample,
            "_fetched_bytes": len(raw),
            "_harvest_run_id": run_id,
        }
    except Exception as exc:
        return {
            "source_id": source_id,
            "source_record_id": f"{source_id}:entrypoint-error:{_sha256_text(str(exc))[:16]}",
            "title": f"{src.get('service_name') or source_id} entrypoint probe error",
            "url": url,
            "_protocol": "entrypoint-probe",
            "_schema": "probe-error",
            "error": str(exc),
            "_harvest_run_id": run_id,
        }


def _record_image_urls(record: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for key in ("ocrImageUrls", "imageUrls", "pageImageUrls", "images"):
        value = record.get(key)
        if isinstance(value, list):
            urls.extend(str(v) for v in value if str(v).startswith(("http://", "https://")))
    for key in ("ocrImageUrl", "imageUrl", "pageImageUrl", "sourceImageUrl"):
        value = str(record.get(key) or "")
        if value.startswith(("http://", "https://")):
            urls.append(value)
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


def _insert_page_asset(
    *,
    source_id: str,
    source_record_id: str,
    page_index: int,
    image_url: str,
    webp: bytes,
    width: int | None,
    height: int | None,
    ocr_status: str,
) -> int:
    now = _now_iso()
    webp_sha, cid, b2_key = _b2_put_webp(source_id, source_record_id, page_index, webp)
    page_hash = _sha256_text(f"{source_id}|{source_record_id}|{page_index}|{image_url}")[:24]
    return _insert(
        vertex_biblio_page_asset,
        {
            **_base_row(f"at://{_ACTOR}/com.etzhayyim.apps.biblio.pageAsset/{page_hash}", now),
            "source_id": source_id,
            "source_record_id": source_record_id,
            "page_index": page_index,
            "source_image_url": image_url,
            "webp_sha256": webp_sha,
            "webp_cid_v1": cid,
            "webp_b2_bucket": _B2_BUCKET if b2_key else "",
            "webp_b2_key": b2_key,
            "webp_byte_size": len(webp),
            "width_px": width,
            "height_px": height,
            "ocr_status": ocr_status,
            "status": "active",
            "updated_at": now,
        },
    )


def _insert_ocr_text(
    *,
    source_id: str,
    source_record_id: str,
    page_index: int,
    parsed: dict[str, Any],
) -> int:
    now = _now_iso()
    text = str(parsed.get("pageText") or "")
    raw_json = json.dumps(parsed, ensure_ascii=False)
    warnings = json.dumps(parsed.get("warnings") or [], ensure_ascii=False)
    text_bytes = text.encode("utf-8")
    ocr_hash = _sha256_text(f"{source_id}|{source_record_id}|{page_index}")[:24]
    return _insert(
        vertex_biblio_ocr_text,
        {
            **_base_row(f"at://{_ACTOR}/com.etzhayyim.apps.biblio.ocrText/{ocr_hash}", now),
            "source_id": source_id,
            "source_record_id": source_record_id,
            "page_index": page_index,
            "ocr_engine": str(parsed.get("_engine") or "unknown"),
            "ocr_model": str(parsed.get("_model") or ""),
            "ocr_text": text,
            "ocr_json": raw_json,
            "warnings": warnings,
            "text_sha256": _sha256(text_bytes),
            "text_byte_size": len(text_bytes),
            "status": "active",
        },
    )


def _ocr_records(
    records: list[dict[str, Any]],
    *,
    max_pages_per_source: int,
    webp_quality: int,
    ocr: bool,
) -> dict[str, int]:
    pages_by_source: dict[str, int] = {}
    stats = {"pageAssetsInserted": 0, "ocrTextsInserted": 0, "ocrErrors": 0}
    for record in records:
        source_id = str(record.get("source_id") or "manual-biblio")
        source_record_id = _raw_record_id(source_id, record)
        for image_url in _record_image_urls(record):
            used = pages_by_source.get(source_id, 0)
            if used >= max(0, int(max_pages_per_source)):
                continue
            page_index = used
            pages_by_source[source_id] = used + 1
            try:
                img = _http_get(image_url, timeout=90.0, accept="image/*")
                webp, width, height = _webp_from_image_bytes(img, int(webp_quality))
                stats["pageAssetsInserted"] += _insert_page_asset(
                    source_id=source_id,
                    source_record_id=source_record_id,
                    page_index=page_index,
                    image_url=image_url,
                    webp=webp,
                    width=width,
                    height=height,
                    ocr_status="pending" if ocr else "skipped",
                )
                if ocr:
                    parsed = _run_coro_sync(_ocr_webp(webp))
                    stats["ocrTextsInserted"] += _insert_ocr_text(
                        source_id=source_id,
                        source_record_id=source_record_id,
                        page_index=page_index,
                        parsed=parsed,
                    )
            except Exception:
                stats["ocrErrors"] += 1
    return stats


def task_biblio_open_data_ingest(
    sourceIds: list[str] | None = None,
    rawRecords: list[dict[str, Any]] | None = None,
    mode: str = "source_catalog",
) -> dict[str, Any]:
    """Seed source metadata and optionally normalize provided raw records."""
    run_id = f"biblio-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    started = _now_iso()
    selected = set(sourceIds or [])
    raw_inserted = 0
    entities_inserted = 0
    identifiers_inserted = 0
    edges_inserted = 0
    records = rawRecords or []
    source_id = next(iter(selected), "manual-biblio")
    try:
        source_rows = _seed_sources(selected or None)
        raw_rows: list[dict[str, Any]] = []
        entity_rows: list[dict[str, Any]] = []
        identifier_rows: list[dict[str, Any]] = []
        for payload in records:
            rec_source = str(payload.get("source_id") or source_id)
            source_record_id, raw_row = _raw_record_row(rec_source, run_id, payload)
            raw_rows.append(raw_row)
            _, entity_row, ident_rows = _entity_identifier_rows(
                rec_source,
                source_record_id,
                payload,
            )
            entity_rows.append(entity_row)
            identifier_rows.extend(ident_rows)
        if raw_rows:
            raw_inserted = len(get_kotoba_client().insert_rows("vertex_biblio_raw_record", raw_rows))
        if entity_rows:
            entities_inserted = len(get_kotoba_client().insert_rows("vertex_biblio_entity", entity_rows))
        if identifier_rows:
            identifiers_inserted = len(get_kotoba_client().insert_rows(
                "vertex_biblio_identifier",
                identifier_rows,
            ))
        _insert_run({
            "vertex_id": f"at://{_ACTOR}/com.etzhayyim.apps.biblio.ingestRun/{run_id}",
            "_seq": 0,
            "sensitivity_ord": 2,
            "owner_did": _ACTOR,
            "run_id": run_id,
            "source_id": source_id,
            "protocol": mode,
            "query_key": ",".join(sorted(selected)) or "all-sources",
            "cursor_start": "",
            "cursor_end": "",
            "raw_records_seen": len(records),
            "raw_records_inserted": raw_inserted,
            "entities_inserted": entities_inserted,
            "identifiers_inserted": identifiers_inserted,
            "edges_inserted": edges_inserted,
            "status": "success",
            "error": "",
            "started_at": started,
            "finished_at": _now_iso(),
            "org_id": _ACTOR,
            "user_id": _ACTOR,
            "actor_id": "sys.langgraph.biblio-open-data",
        })
        _assert_run_visible(run_id)
        return {
            "ok": True,
            "runId": run_id,
            "sourceRows": source_rows,
            "rawRecordsSeen": len(records),
            "rawRecordsInserted": raw_inserted,
            "entitiesInserted": entities_inserted,
            "identifiersInserted": identifiers_inserted,
            "edgesInserted": edges_inserted,
            "mode": mode,
        }
    except Exception as exc:
        return {"ok": False, "runId": run_id, "error": str(exc)}


def task_biblio_asia_open_data_actor(
    countries: list[str] | None = None,
    sourceIds: list[str] | None = None,
    rawRecordsBySource: dict[str, list[dict[str, Any]]] | None = None,
    maxRecordsPerSource: int = 200,
    fetchEntrypoints: bool = True,
    ocr: bool = False,
    maxOcrPagesPerSource: int = 2,
    webpQuality: int = 82,
    dryRun: bool = False,
) -> dict[str, Any]:
    """Plan and run bounded India/China/Korea bibliographic ingest.

    This actor seeds the source catalog every run and records any caller-supplied
    raw records. Source-specific network adapters are represented in the adapter
    plan so credentials and scraping policy can be enabled one source at a time.
    """
    selected = sourceIds or _source_ids_for_countries(countries)
    effective_max_records = max(
        1,
        min(int(maxRecordsPerSource or 200), _env_int("BIBLIO_MAX_RECORDS_HARD_LIMIT", 1000)),
    )
    adapter_plan = [_adapter_plan(source_id, effective_max_records) for source_id in selected]
    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "countries": countries or ["india", "china", "korea"],
            "sourceIds": selected,
            "adapterPlan": adapter_plan,
            "rawRecordsPlanned": len(selected) * effective_max_records
            if fetchEntrypoints
            else 0,
            "fetchEntrypoints": fetchEntrypoints,
            "ocr": ocr,
        }

    raw_records: list[dict[str, Any]] = []
    probe_run_id = f"biblio-asia-probe-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    if fetchEntrypoints:
        for source_id in selected:
            fetched = _fetch_source_records(source_id, effective_max_records)
            if fetched:
                raw_records.extend(fetched[:effective_max_records])
            else:
                raw_records.append(_probe_source_entrypoint(source_id, probe_run_id))
    for source_id, records in (rawRecordsBySource or {}).items():
        for record in records[:effective_max_records]:
            raw_records.append({"source_id": source_id, **record})

    result = task_biblio_open_data_ingest(
        sourceIds=selected,
        rawRecords=raw_records,
        mode="asia-langserver-actor",
    )
    ocr_stats = _ocr_records(
        raw_records,
        max_pages_per_source=maxOcrPagesPerSource,
        webp_quality=webpQuality,
        ocr=ocr,
    )
    return {
        **result,
        "countries": countries or ["india", "china", "korea"],
        "sourceIds": selected,
        "adapterPlan": adapter_plan,
        "fetchEntrypoints": fetchEntrypoints,
        "ocr": ocr,
        **ocr_stats,
    }


__all__ = [
    "task_biblio_asia_open_data_actor",
    "task_biblio_open_data_ingest",
]

