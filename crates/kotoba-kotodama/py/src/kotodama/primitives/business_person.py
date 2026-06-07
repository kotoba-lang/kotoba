from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import html as html_lib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse



BUSINESS_PERSON_DID = "did:web:business-person.etzhayyim.com"
FETCH_USER_AGENT = "business-person.etzhayyim.com/0.1 (+https://etzhayyim.com)"
PUBLIC_SOURCES = {
    "edinet",
    "gbizinfo",
    "sec-edgar",
    "companies-house",
    "handelsregister",
    "corporate-hp",
}
ROLE_KEYWORDS = (
    "ceo",
    "cfo",
    "coo",
    "cto",
    "chief",
    "chair",
    "chairman",
    "chairperson",
    "president",
    "director",
    "board",
    "founder",
    "secretary",
    "treasurer",
    "officer",
    "executive",
)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    out = [char if char.isalnum() else "-" for char in text]
    slug = "-".join(part for part in "".join(out).split("-") if part)
    return slug[:96] or "unknown"


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [row for row in parsed if isinstance(row, dict)]
    return []


def _as_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        return json.loads(value)
    return None


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _source_id(value: Any) -> str:
    source = str(value or "").strip().lower()
    return source if source in PUBLIC_SOURCES else "corporate-hp"


def _is_public_http_url(value: Any) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _compact_cik(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _bounded_page_size(value: Any) -> int:
    return max(1, min(int(value or 100), 1000))


def _with_query(url: str, **params: Any) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value is not None and str(value) != "":
            query[key] = str(value)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _source_request_url(
    *,
    source: str,
    source_url: str,
    company_number: str,
    corporate_number: str,
    doc_id: str,
    cik: str,
    register_number: str,
    cursor: str = "",
    page_size: int = 100,
) -> str:
    if source_url:
        base = source_url
    elif source == "companies-house" and company_number:
        base = f"https://api.company-information.service.gov.uk/company/{quote_plus(company_number)}/officers"
    elif source == "gbizinfo" and corporate_number:
        base = f"https://info.gbiz.go.jp/hojin/v1/hojin/{quote_plus(corporate_number)}"
    elif source == "edinet" and doc_id:
        base = f"https://disclosure2.edinet-fsa.go.jp/api/v2/documents/{quote_plus(doc_id)}"
    elif source == "sec-edgar" and cik:
        compact = _compact_cik(cik)
        base = f"https://data.sec.gov/submissions/CIK{compact}.json" if compact else ""
    elif source == "handelsregister" and register_number:
        base = f"https://www.handelsregister.de/rp_web/search.do?registerNummer={quote_plus(register_number)}"
    else:
        base = ""
    if not base:
        return ""
    if source == "companies-house":
        return _with_query(base, items_per_page=page_size, start_index=cursor or 0)
    if source == "gbizinfo" and cursor:
        return _with_query(base, pageToken=cursor)
    if source == "edinet" and cursor:
        return _with_query(base, page=cursor)
    return base


def _fetch_headers_for_source(source: str) -> dict[str, str]:
    headers = {"User-Agent": os.getenv("BUSINESS_PERSON_FETCH_USER_AGENT", FETCH_USER_AGENT)}
    if source == "sec-edgar":
        headers["User-Agent"] = os.getenv("SEC_USER_AGENT", headers["User-Agent"])
    if source == "gbizinfo":
        token = os.getenv("GBIZINFO_API_TOKEN") or os.getenv("G_BIZINFO_API_TOKEN")
        if token:
            headers["X-hojinInfo-api-token"] = token
    return headers


def _fetch_auth_for_source(source: str) -> Any:
    if source != "companies-house":
        return None
    api_key = os.getenv("COMPANIES_HOUSE_API_KEY")
    if not api_key:
        return None
    import aiohttp

    return aiohttp.BasicAuth(api_key, "")


async def _http_get_public_source(
    url: str,
    *,
    timeout_sec: int = 20,
    headers: dict[str, str] | None = None,
    auth: Any = None,
) -> dict[str, Any]:
    import aiohttp

    async with aiohttp.ClientSession(headers=headers or {"User-Agent": FETCH_USER_AGENT}, auth=auth) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as resp:
            text = await resp.text()
            content_type = resp.headers.get("content-type", "")
            body: Any = text
            if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
                try:
                    body = json.loads(text)
                except json.JSONDecodeError:
                    body = text
            return {
                "httpStatus": resp.status,
                "contentType": content_type,
                "body": body,
                "bytesFetched": len(text.encode("utf-8")),
            }


def _payload_target_for_source(source: str, content_type: str, body: Any) -> tuple[str, Any]:
    if source == "companies-house":
        return "companiesHouseJson", body
    if source == "gbizinfo":
        return "gbizInfoJson", body
    if source == "edinet":
        return "edinetJson", body
    if source == "sec-edgar":
        return "secEdgarJson", body
    if source == "handelsregister":
        return "handelsregisterJson", body
    if isinstance(body, str) and ("html" in content_type.lower() or "<html" in body[:512].lower()):
        return "htmlText", body
    if isinstance(body, str):
        return "text", body
    return "rows", body if isinstance(body, list) else []


def _next_page_for_source(source: str, source_url: str, body: Any, page_size: int) -> tuple[str, str]:
    if not isinstance(body, dict):
        return "", ""
    if source == "companies-house":
        total = int(body.get("total_results") or body.get("totalResults") or 0)
        current = int(body.get("start_index") or body.get("startIndex") or 0)
        count = int(body.get("items_per_page") or body.get("itemsPerPage") or page_size)
        next_start = current + count
        if total and next_start < total:
            return str(next_start), _with_query(source_url, start_index=next_start, items_per_page=count)
    if source == "gbizinfo":
        token = _as_text(body.get("nextPageToken") or body.get("next_page_token") or body.get("next"))
        if token:
            return token, _with_query(source_url, pageToken=token)
    if source == "edinet":
        next_page = _as_text(body.get("nextPage") or body.get("next_page"))
        if next_page:
            return next_page, _with_query(source_url, page=next_page)
    return "", ""


def _flatten_jsonld(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            out.extend(_flatten_jsonld(item))
    elif isinstance(value, dict):
        out.append(value)
        graph = value.get("@graph")
        if isinstance(graph, list):
            out.extend(_flatten_jsonld(graph))
    return out


def _jsonld_nodes(html_text: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    pattern = re.compile(
        r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html_text):
        body = html_lib.unescape(match.group(1)).strip()
        if not body:
            continue
        try:
            nodes.extend(_flatten_jsonld(json.loads(body)))
        except json.JSONDecodeError:
            continue
    return nodes


def _node_type(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type") or node.get("type")
    if isinstance(raw, list):
        return {str(item).lower() for item in raw}
    return {str(raw).lower()} if raw else set()


def _org_name(value: Any) -> str:
    if isinstance(value, dict):
        return _as_text(value.get("name"))
    if isinstance(value, list):
        for item in value:
            name = _org_name(item)
            if name:
                return name
    return _as_text(value)


def _person_row_from_jsonld(
    node: dict[str, Any],
    *,
    source_url: str,
    jurisdiction: str,
    fallback_org_name: str,
) -> dict[str, Any] | None:
    if "person" not in _node_type(node):
        return None
    name = _as_text(node.get("name"))
    title = _as_text(node.get("jobTitle") or node.get("roleName") or node.get("description"))
    if not name or not title:
        return None
    return {
        "fullName": name,
        "title": title,
        "orgName": _org_name(node.get("worksFor") or node.get("affiliation")) or fallback_org_name,
        "sourceId": "corporate-hp",
        "sourceUrl": source_url,
        "country": jurisdiction,
        "description": _as_text(node.get("description")),
    }


def _strip_html(html_text: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "\n", html_text)
    text = re.sub(r"(?is)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"[ \t]+", " ", text)


def _looks_like_role(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in ROLE_KEYWORDS)


def _person_rows_from_text(
    text: str,
    *,
    source_url: str,
    jurisdiction: str,
    fallback_org_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" -|")
        if len(line) < 8 or len(line) > 180 or not _looks_like_role(line):
            continue
        match = re.match(r"^([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){1,4})\s*[-|,]\s*(.{3,120})$", line)
        if not match:
            match = re.match(r"^(.{3,120}?)\s*[-|,]\s*([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){1,4})$", line)
            if match and _looks_like_role(match.group(1)):
                name, title = match.group(2), match.group(1)
            else:
                continue
        else:
            name, title = match.group(1), match.group(2)
        key = (name.lower(), title.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "fullName": name,
                "title": title,
                "orgName": fallback_org_name,
                "sourceId": "corporate-hp",
                "sourceUrl": source_url,
                "country": jurisdiction,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _companies_house_items(payload: Any) -> list[dict[str, Any]]:
    data = _as_json(payload)
    if isinstance(data, dict):
        items = data.get("items")
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _companies_house_role(value: Any) -> str:
    role = _as_text(value).replace("-", " ")
    return role or "officer"


def _person_rows_from_companies_house(
    payload: Any,
    *,
    source_url: str,
    jurisdiction: str,
    fallback_org_name: str,
    company_number: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _companies_house_items(payload):
        name = _as_text(item.get("name"))
        if not name:
            continue
        appointed_on = _as_text(item.get("appointed_on"))
        resigned_on = _as_text(item.get("resigned_on"))
        address = item.get("address") if isinstance(item.get("address"), dict) else {}
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        officer_link = links.get("officer") if isinstance(links.get("officer"), dict) else {}
        rows.append(
            {
                "fullName": name,
                "title": _companies_house_role(item.get("officer_role")),
                "orgName": fallback_org_name,
                "sourceId": "companies-house",
                "sourceUrl": source_url,
                "country": _as_text(address.get("country")) or jurisdiction or "GBR",
                "registryId": _as_text(item.get("person_number") or item.get("officer_id") or officer_link.get("appointments") or company_number),
                "registryType": "companies-house-officer",
                "appointedAt": appointed_on,
                "since": appointed_on,
                "until": resigned_on,
                "status": "resigned" if resigned_on else "active",
                "description": _as_text(item.get("occupation") or item.get("nationality")),
                "url": source_url,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _gbizinfo_records(payload: Any) -> list[dict[str, Any]]:
    data = _as_json(payload)
    if isinstance(data, dict):
        for key in ("hojin-infos", "hojinInfos", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _edinet_records(payload: Any) -> list[dict[str, Any]]:
    data = _as_json(payload)
    if isinstance(data, dict):
        for key in ("results", "items", "documents", "docInfos", "edinetReports"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _sec_edgar_records(payload: Any) -> list[dict[str, Any]]:
    data = _as_json(payload)
    if isinstance(data, dict):
        records: list[dict[str, Any]] = []
        for key in ("officers", "executives", "directors", "items", "reportingOwners", "reportingOwner"):
            value = data.get(key)
            if isinstance(value, list):
                records.extend(item for item in value if isinstance(item, dict))
            elif isinstance(value, dict):
                records.append(value)
        owner = data.get("owner")
        if isinstance(owner, dict):
            records.append(owner)
        return records or [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _handelsregister_records(payload: Any) -> list[dict[str, Any]]:
    data = _as_json(payload)
    if isinstance(data, dict):
        records: list[dict[str, Any]] = []
        for key in ("items", "results", "entries", "officers", "vertretungsberechtigte", "persons"):
            value = data.get(key)
            if isinstance(value, list):
                records.extend(item for item in value if isinstance(item, dict))
            elif isinstance(value, dict):
                records.append(value)
        return records or [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _first_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value:
            return _as_text(value)
    return ""


def _first_nested_text(record: dict[str, Any], *paths: str) -> str:
    for path in paths:
        current: Any = record
        for part in path.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        if current:
            return _as_text(current)
    return ""


def _person_rows_from_gbizinfo(
    payload: Any,
    *,
    source_url: str,
    jurisdiction: str,
    fallback_org_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in _gbizinfo_records(payload):
        rep_name = _first_text(
            record,
            "representativeName",
            "representative_name",
            "representative",
            "name_of_representative",
            "daihyoName",
            "daihyo_name",
        )
        if not rep_name:
            continue
        org_name = _first_text(record, "name", "corporateName", "corporate_name", "hojinName") or fallback_org_name
        corp_no = _first_text(record, "corporateNumber", "corporate_number", "hojinNumber", "hojin_number")
        title = _first_text(record, "representativePosition", "representative_position", "position", "yakushoku") or "representative"
        rows.append(
            {
                "fullName": rep_name,
                "title": title,
                "orgName": org_name,
                "sourceId": "gbizinfo",
                "sourceUrl": source_url,
                "country": jurisdiction or "JPN",
                "registryId": corp_no,
                "registryType": "gbizinfo-corporate-number",
                "appointedAt": _first_text(record, "updateDate", "updatedDate", "lastUpdateDate"),
                "status": _first_text(record, "status") or "active",
                "description": _first_text(record, "businessSummary", "summary", "industry"),
                "url": source_url or _first_text(record, "url", "homepage"),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _person_rows_from_edinet(
    payload: Any,
    *,
    source_url: str,
    jurisdiction: str,
    fallback_org_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in _edinet_records(payload):
        name = _first_text(
            record,
            "representativeName",
            "officerName",
            "directorName",
            "name",
            "役員名",
            "代表者氏名",
        )
        name = name or _first_nested_text(
            record,
            "issuer.representativeName",
            "filer.representativeName",
            "company.representativeName",
        )
        if not name:
            continue
        org_name = (
            _first_text(record, "filerName", "issuerName", "companyName", "提出者名", "会社名")
            or _first_nested_text(record, "issuer.name", "filer.name", "company.name")
            or fallback_org_name
        )
        doc_id = _first_text(record, "docID", "docId", "documentId", "seqNumber", "edinetCode")
        title = _first_text(record, "title", "role", "position", "役職名") or "officer"
        rows.append(
            {
                "fullName": name,
                "title": title,
                "orgName": org_name,
                "sourceId": "edinet",
                "sourceUrl": source_url,
                "country": jurisdiction or "JPN",
                "registryId": doc_id,
                "registryType": "edinet-document",
                "appointedAt": _first_text(record, "submitDateTime", "submitDate", "periodEnd"),
                "status": "active",
                "description": _first_text(record, "docDescription", "formCode", "ordinanceCode"),
                "filingTypes": _first_text(record, "formCode", "docTypeCode", "ordinanceCode"),
                "url": source_url,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _person_rows_from_sec_edgar(
    payload: Any,
    *,
    source_url: str,
    jurisdiction: str,
    fallback_org_name: str,
    cik: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in _sec_edgar_records(payload):
        name = _first_text(record, "name", "ownerName", "reportingOwnerName", "personName", "fullName")
        name = name or _first_nested_text(record, "reportingOwner.name", "owner.name")
        if not name:
            continue
        title = (
            _first_text(record, "title", "officerTitle", "relationship", "role")
            or _first_nested_text(record, "reportingOwner.relationship")
            or "officer"
        )
        org_name = _first_text(record, "issuerName", "companyName", "entityName") or fallback_org_name
        issuer_cik = _first_text(record, "issuerCik", "issuerCIK", "cik", "CIK") or cik
        rows.append(
            {
                "fullName": name,
                "title": title,
                "orgName": org_name,
                "sourceId": "sec-edgar",
                "sourceUrl": source_url,
                "country": jurisdiction or "USA",
                "registryId": issuer_cik,
                "registryType": "sec-edgar-cik",
                "appointedAt": _first_text(record, "filedAt", "filingDate", "periodOfReport", "acceptanceDatetime"),
                "status": "active",
                "description": _first_text(record, "form", "formType", "documentType"),
                "filingTypes": _first_text(record, "form", "formType", "documentType"),
                "url": source_url,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _person_rows_from_handelsregister(
    payload: Any,
    *,
    source_url: str,
    jurisdiction: str,
    fallback_org_name: str,
    register_number: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in _handelsregister_records(payload):
        name = _first_text(
            record,
            "name",
            "fullName",
            "personName",
            "officerName",
            "vertreterName",
            "geschaeftsfuehrer",
            "geschäftsführer",
            "prokurist",
        )
        if not name:
            continue
        source_name = ""
        if _first_text(record, "geschaeftsfuehrer", "geschäftsführer"):
            source_name = "managing director"
        elif _first_text(record, "prokurist"):
            source_name = "procurist"
        title = _first_text(record, "role", "title", "position", "funktion", "officerRole") or source_name or "officer"
        org_name = _first_text(record, "companyName", "firma", "nameOfCompany", "entityName") or fallback_org_name
        registry_id = _first_text(record, "registerNumber", "register_number", "registernummer", "registryId") or register_number
        court = _first_text(record, "court", "registerCourt", "amtsgericht")
        rows.append(
            {
                "fullName": name,
                "title": title,
                "orgName": org_name,
                "sourceId": "handelsregister",
                "sourceUrl": source_url,
                "country": jurisdiction or "DEU",
                "registryId": registry_id,
                "registryType": "handelsregister-register-number",
                "appointedAt": _first_text(record, "date", "effectiveDate", "registeredAt", "appointmentDate"),
                "status": "inactive" if _first_text(record, "resignedAt", "deletedAt", "endedAt") else "active",
                "description": court,
                "url": source_url or _first_text(record, "url", "sourceUrl"),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _role_from_row(
    row: dict[str, Any],
    *,
    source_id: str,
    source_url: str,
    jurisdiction: str,
) -> dict[str, Any]:
    full_name = str(
        row.get("fullName")
        or row.get("displayName")
        or row.get("name")
        or row.get("personName")
        or ""
    ).strip()
    org_name = str(row.get("orgName") or row.get("entityName") or row.get("companyName") or "").strip()
    title = str(row.get("title") or row.get("role") or row.get("primaryRole") or "").strip()
    country = str(row.get("country") or jurisdiction or "").strip().lower()
    registry_id = str(row.get("registryId") or row.get("registry_id") or row.get("lei") or "").strip()
    source = _source_id(row.get("sourceId") or row.get("source") or source_id)
    row_source_url = str(row.get("sourceUrl") or row.get("url") or source_url or "").strip()
    person_id = str(row.get("personId") or "").strip() or _stable_id(
        "bp", full_name, org_name, title, country, registry_id, row_source_url
    )
    vertex_id = f"at://{BUSINESS_PERSON_DID}/com.etzhayyim.apps.businessPerson.person/{_slug(person_id)}"
    return {
        "vertex_id": vertex_id,
        "_seq": None,
        "created_date": _today(),
        "sensitivity_ord": 1,
        "owner_did": BUSINESS_PERSON_DID,
        "rkey": _slug(person_id),
        "repo": BUSINESS_PERSON_DID,
        "label": full_name or person_id,
        "did": f"{BUSINESS_PERSON_DID}:bp:{_slug(person_id)}",
        "person_id": person_id,
        "display_name": full_name or None,
        "description": row.get("description") or None,
        "title": title or None,
        "name": full_name or None,
        "name_en": row.get("nameEn") or row.get("name_en") or None,
        "name_ja": row.get("nameJa") or row.get("name_ja") or None,
        "code": row.get("code") or None,
        "level": row.get("level") or None,
        "org_name": org_name or None,
        "registry_id": registry_id or None,
        "registry_type": row.get("registryType") or row.get("registry_type") or source,
        "country": country or None,
        "source": source,
        "source_url": row_source_url or None,
        "url": row.get("url") or row_source_url or None,
        "change_type": row.get("changeType") or row.get("change_type") or "public-role",
        "from_title": row.get("fromTitle") or row.get("from_title") or None,
        "to_title": row.get("toTitle") or row.get("to_title") or None,
        "effective_date": row.get("effectiveDate") or row.get("appointedAt") or None,
        "since": row.get("since") or row.get("appointedAt") or None,
        "until": row.get("until") or None,
        "filing_types": row.get("filingTypes") or row.get("filing_types") or None,
        "status": row.get("status") or "active",
        "props": json.dumps(
            {
                "publicOnly": True,
                "primaryEntityDid": row.get("primaryEntityDid") or row.get("legalEntityDid"),
                "lei": row.get("lei"),
                "raw": row,
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
    }


def _insert_ignore(cur: Any, table: str, pk_col: str, values: dict[str, Any]) -> int:
    values = {k: v for k, v in values.items() if v is not None}
    cols = list(values)
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(cols)
    _res = client.q(
        f"INSERT INTO {table} ({col_sql}) "
        f"SELECT {placeholders} "
        f"WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE {pk_col} = %s)",
        (*[values[col] for col in cols], values[pk_col]),
    )
    return int((len(_res) if isinstance(_res, list) else 1) or 0)


def _update_by_pk(cur: Any, table: str, pk_col: str, values: dict[str, Any]) -> int:
    clean_values = {
        k: v
        for k, v in values.items()
        if k != pk_col and k not in {"_seq", "created_date"} and v is not None
    }
    if not clean_values:
        return 0
    set_sql = ", ".join(f"{k} = %s" for k in clean_values)
    _res = client.q(
        f"UPDATE {table} SET {set_sql} WHERE {pk_col} = %s",
        (*clean_values.values(), values[pk_col]),
    )
    return int((len(_res) if isinstance(_res, list) else 1) or 0)


def _count_visible(cur: Any, ids: list[str]) -> int:
    if not ids:
        return 0
    placeholders = ", ".join(["%s"] * len(ids))
    _res = client.q(f"SELECT COUNT(*) FROM vertex_business_person WHERE vertex_id IN ({placeholders})", tuple(ids))
    row = (_res[0] if _res else None)
    return int(row[0] if row else 0)


def upsert_graph_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    inserted = 0
    updated = 0
    ids = [str(row["vertex_id"]) for row in rows if row.get("vertex_id")]
    if True:
        client = get_kotoba_client()
        for row in rows:
            inserted += _insert_ignore(cur, "vertex_business_person", "vertex_id", row)
            updated += _update_by_pk(cur, "vertex_business_person", "vertex_id", row)
        visible = _count_visible(cur, ids)
    return {
        "ok": visible >= len(ids),
        "recordsPrepared": len(rows),
        "recordsInserted": inserted,
        "recordsUpdated": updated,
        "recordsVisible": visible,
    }


def task_business_person_plan_public_role_sources(
    sourceId: str = "corporate-hp",
    jurisdiction: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    source = _source_id(sourceId)
    bounded_limit = max(1, min(int(limit or 100), 10_000))
    return {
        "ok": True,
        "sourceId": source,
        "jurisdiction": jurisdiction,
        "limit": bounded_limit,
        "publicOnly": True,
        "jobsPlanned": 1,
    }


async def task_business_person_fetch_public_source(
    sourceId: str = "corporate-hp",
    sourceUrl: str = "",
    timeoutSec: int = 20,
    fetch: bool = True,
) -> dict[str, Any]:
    source = _source_id(sourceId)
    if not fetch or not sourceUrl:
        return {
            "ok": True,
            "sourceId": source,
            "publicOnly": True,
            "fetched": False,
            "reason": "fetch disabled or sourceUrl absent",
        }
    if not _is_public_http_url(sourceUrl):
        return {
            "ok": False,
            "sourceId": source,
            "publicOnly": True,
            "fetched": False,
            "error": "sourceUrl must be http(s)",
        }
    try:
        result = await _http_get_public_source(
            sourceUrl,
            timeout_sec=max(1, min(int(timeoutSec or 20), 60)),
            headers=_fetch_headers_for_source(source),
            auth=_fetch_auth_for_source(source),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "sourceId": source,
            "publicOnly": True,
            "fetched": False,
            "error": f"businessPerson.fetchPublicSource failed: {exc}",
        }
    target, payload = _payload_target_for_source(source, result["contentType"], result["body"])
    ok = 200 <= int(result["httpStatus"]) < 300
    return {
        "ok": ok,
        "sourceId": source,
        "publicOnly": True,
        "fetched": ok,
        "sourceUrl": sourceUrl,
        "httpStatus": result["httpStatus"],
        "contentType": result["contentType"],
        "bytesFetched": result["bytesFetched"],
        target: payload if ok else None,
    }


def task_business_person_prepare_source_request(
    sourceId: str = "corporate-hp",
    sourceUrl: str = "",
    companyNumber: str = "",
    corporateNumber: str = "",
    docId: str = "",
    cik: str = "",
    registerNumber: str = "",
    cursor: str = "",
    pageSize: int = 100,
    fetch: bool = True,
) -> dict[str, Any]:
    source = _source_id(sourceId)
    bounded_page_size = _bounded_page_size(pageSize)
    prepared_url = _source_request_url(
        source=source,
        source_url=_as_text(sourceUrl),
        company_number=_as_text(companyNumber),
        corporate_number=_as_text(corporateNumber),
        doc_id=_as_text(docId),
        cik=_as_text(cik),
        register_number=_as_text(registerNumber),
        cursor=_as_text(cursor),
        page_size=bounded_page_size,
    )
    if not fetch:
        return {
            "ok": True,
            "sourceId": source,
            "publicOnly": True,
            "fetch": False,
            "sourceUrl": prepared_url,
            "requestPrepared": False,
        }
    if not prepared_url:
        return {
            "ok": True,
            "sourceId": source,
            "publicOnly": True,
            "fetch": False,
            "requestPrepared": False,
            "reason": "no sourceUrl or source-specific identifier supplied",
        }
    return {
        "ok": True,
        "sourceId": source,
        "publicOnly": True,
        "fetch": True,
        "sourceUrl": prepared_url,
        "requestPrepared": True,
        "cursor": _as_text(cursor),
        "pageSize": bounded_page_size,
        "requiresAuthEnv": "COMPANIES_HOUSE_API_KEY" if source == "companies-house" else "",
        "usesHeaderEnv": "SEC_USER_AGENT" if source == "sec-edgar" else "",
    }


def task_business_person_advance_source_cursor(
    sourceId: str = "corporate-hp",
    sourceUrl: str = "",
    pageSize: int = 100,
    pagesFetched: int = 0,
    maxPages: int = 1,
    companiesHouseJson: Any = None,
    gbizInfoJson: Any = None,
    edinetJson: Any = None,
    secEdgarJson: Any = None,
    handelsregisterJson: Any = None,
) -> dict[str, Any]:
    source = _source_id(sourceId)
    payload_by_source = {
        "companies-house": companiesHouseJson,
        "gbizinfo": gbizInfoJson,
        "edinet": edinetJson,
        "sec-edgar": secEdgarJson,
        "handelsregister": handelsregisterJson,
    }
    payload = _as_json(payload_by_source.get(source))
    bounded_page_size = _bounded_page_size(pageSize)
    next_cursor, next_source_url = _next_page_for_source(source, sourceUrl, payload, bounded_page_size)
    next_page_index = int(pagesFetched or 0) + 1
    can_continue = bool(next_source_url) and next_page_index < max(1, int(maxPages or 1))
    return {
        "ok": True,
        "sourceId": source,
        "publicOnly": True,
        "pageSize": bounded_page_size,
        "pagesFetched": next_page_index,
        "cursor": next_cursor,
        "nextSourceUrl": next_source_url,
        "hasNextPage": can_continue,
    }


def task_business_person_schedule_next_page(
    sourceId: str = "corporate-hp",
    nextSourceUrl: str = "",
    hasNextPage: bool = False,
    cursor: str = "",
    pageSize: int = 100,
    pagesFetched: int = 0,
    maxPages: int = 1,
    jurisdiction: str = "",
    operatorDid: str = "",
    companyNumber: str = "",
    corporateNumber: str = "",
    docId: str = "",
    cik: str = "",
    registerNumber: str = "",
) -> dict[str, Any]:
    source = _source_id(sourceId)
    if not hasNextPage or not nextSourceUrl:
        return {
            "ok": True,
            "sourceId": source,
            "publicOnly": True,
            "nextPageScheduled": False,
            "reason": "no next page",
        }
    record = {
        "sourceId": source,
        "sourceUrl": nextSourceUrl,
        "jurisdiction": jurisdiction,
        "cursor": cursor,
        "pageSize": _bounded_page_size(pageSize),
        "pagesFetched": int(pagesFetched or 0),
        "maxPages": int(maxPages or 1),
        "publicOnly": True,
        "requestedBy": operatorDid,
        "companyNumber": companyNumber,
        "corporateNumber": corporateNumber,
        "docId": docId,
        "cik": cik,
        "registerNumber": registerNumber,
    }
    record = {key: value for key, value in record.items() if value not in {"", None}}
    return {
        "ok": True,
        "sourceId": source,
        "publicOnly": True,
        "nextPageScheduled": True,
        "nextPageJob": {
            "type": "com.atproto.repo.createRecord",
            "payload": {
                "repo": BUSINESS_PERSON_DID,
                "collection": "com.etzhayyim.apps.businessPerson.collectionJob",
                "record": record,
            },
        },
    }


def task_business_person_normalize_public_roles(
    sourceId: str = "corporate-hp",
    sourceUrl: str = "",
    jurisdiction: str = "",
    rows: Any = None,
) -> dict[str, Any]:
    source = _source_id(sourceId)
    normalized = [
        _role_from_row(row, source_id=source, source_url=sourceUrl, jurisdiction=jurisdiction)
        for row in _as_rows(rows)
    ]
    return {
        "ok": True,
        "sourceId": source,
        "publicOnly": True,
        "roles": normalized,
        "recordsPrepared": len(normalized),
    }


def task_business_person_extract_corporate_hp_roles(
    sourceUrl: str = "",
    jurisdiction: str = "",
    htmlText: str = "",
    text: str = "",
    rows: Any = None,
    orgName: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    supplied_rows = _as_rows(rows)
    bounded_limit = max(1, min(int(limit or 100), 1000))
    extracted: list[dict[str, Any]] = []
    html_text = _as_text(htmlText)
    plain_text = _as_text(text)

    if supplied_rows:
        extracted.extend({**row, "sourceId": row.get("sourceId") or "corporate-hp"} for row in supplied_rows)

    if html_text:
        for node in _jsonld_nodes(html_text):
            row = _person_row_from_jsonld(
                node,
                source_url=sourceUrl,
                jurisdiction=jurisdiction,
                fallback_org_name=orgName,
            )
            if row:
                extracted.append(row)
        plain_text = plain_text or _strip_html(html_text)

    if plain_text:
        extracted.extend(
            _person_rows_from_text(
                plain_text,
                source_url=sourceUrl,
                jurisdiction=jurisdiction,
                fallback_org_name=orgName,
                limit=bounded_limit,
            )
        )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in extracted:
        key = (
            _as_text(row.get("fullName") or row.get("name")).lower(),
            _as_text(row.get("title") or row.get("role")).lower(),
            _as_text(row.get("sourceUrl") or sourceUrl).lower(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append({**row, "publicOnly": True})
        if len(deduped) >= bounded_limit:
            break

    return {
        "ok": True,
        "sourceId": "corporate-hp",
        "publicOnly": True,
        "rows": deduped,
        "recordsExtracted": len(deduped),
    }


def task_business_person_extract_companies_house_officers(
    companiesHouseJson: Any = None,
    sourceUrl: str = "",
    jurisdiction: str = "GBR",
    rows: Any = None,
    orgName: str = "",
    companyNumber: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit or 100), 1000))
    existing = _as_rows(rows)
    extracted = _person_rows_from_companies_house(
        companiesHouseJson,
        source_url=sourceUrl,
        jurisdiction=jurisdiction,
        fallback_org_name=orgName,
        company_number=companyNumber,
        limit=bounded_limit,
    )
    combined: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in [*existing, *extracted]:
        key = (
            _as_text(row.get("fullName") or row.get("name")).lower(),
            _as_text(row.get("title") or row.get("role")).lower(),
            _as_text(row.get("registryId") or row.get("sourceUrl") or sourceUrl).lower(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        combined.append({**row, "publicOnly": True})
        if len(combined) >= bounded_limit:
            break
    return {
        "ok": True,
        "sourceId": "companies-house",
        "publicOnly": True,
        "rows": combined,
        "recordsExtracted": len(extracted),
    }


def task_business_person_extract_gbizinfo_representatives(
    gbizInfoJson: Any = None,
    sourceUrl: str = "",
    jurisdiction: str = "JPN",
    rows: Any = None,
    orgName: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit or 100), 1000))
    existing = _as_rows(rows)
    extracted = _person_rows_from_gbizinfo(
        gbizInfoJson,
        source_url=sourceUrl,
        jurisdiction=jurisdiction,
        fallback_org_name=orgName,
        limit=bounded_limit,
    )
    combined: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in [*existing, *extracted]:
        key = (
            _as_text(row.get("fullName") or row.get("name")).lower(),
            _as_text(row.get("title") or row.get("role")).lower(),
            _as_text(row.get("registryId") or row.get("sourceUrl") or sourceUrl).lower(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        combined.append({**row, "publicOnly": True})
        if len(combined) >= bounded_limit:
            break
    return {
        "ok": True,
        "sourceId": "gbizinfo",
        "publicOnly": True,
        "rows": combined,
        "recordsExtracted": len(extracted),
    }


def task_business_person_extract_edinet_officers(
    edinetJson: Any = None,
    sourceUrl: str = "",
    jurisdiction: str = "JPN",
    rows: Any = None,
    orgName: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit or 100), 1000))
    existing = _as_rows(rows)
    extracted = _person_rows_from_edinet(
        edinetJson,
        source_url=sourceUrl,
        jurisdiction=jurisdiction,
        fallback_org_name=orgName,
        limit=bounded_limit,
    )
    combined: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in [*existing, *extracted]:
        key = (
            _as_text(row.get("fullName") or row.get("name")).lower(),
            _as_text(row.get("title") or row.get("role")).lower(),
            _as_text(row.get("registryId") or row.get("sourceUrl") or sourceUrl).lower(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        combined.append({**row, "publicOnly": True})
        if len(combined) >= bounded_limit:
            break
    return {
        "ok": True,
        "sourceId": "edinet",
        "publicOnly": True,
        "rows": combined,
        "recordsExtracted": len(extracted),
    }


def task_business_person_extract_sec_edgar_officers(
    secEdgarJson: Any = None,
    sourceUrl: str = "",
    jurisdiction: str = "USA",
    rows: Any = None,
    orgName: str = "",
    cik: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit or 100), 1000))
    existing = _as_rows(rows)
    extracted = _person_rows_from_sec_edgar(
        secEdgarJson,
        source_url=sourceUrl,
        jurisdiction=jurisdiction,
        fallback_org_name=orgName,
        cik=cik,
        limit=bounded_limit,
    )
    combined: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in [*existing, *extracted]:
        key = (
            _as_text(row.get("fullName") or row.get("name")).lower(),
            _as_text(row.get("title") or row.get("role")).lower(),
            _as_text(row.get("registryId") or row.get("sourceUrl") or sourceUrl).lower(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        combined.append({**row, "publicOnly": True})
        if len(combined) >= bounded_limit:
            break
    return {
        "ok": True,
        "sourceId": "sec-edgar",
        "publicOnly": True,
        "rows": combined,
        "recordsExtracted": len(extracted),
    }


def task_business_person_extract_handelsregister_officers(
    handelsregisterJson: Any = None,
    sourceUrl: str = "",
    jurisdiction: str = "DEU",
    rows: Any = None,
    orgName: str = "",
    registerNumber: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit or 100), 1000))
    existing = _as_rows(rows)
    extracted = _person_rows_from_handelsregister(
        handelsregisterJson,
        source_url=sourceUrl,
        jurisdiction=jurisdiction,
        fallback_org_name=orgName,
        register_number=registerNumber,
        limit=bounded_limit,
    )
    combined: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in [*existing, *extracted]:
        key = (
            _as_text(row.get("fullName") or row.get("name")).lower(),
            _as_text(row.get("title") or row.get("role")).lower(),
            _as_text(row.get("registryId") or row.get("sourceUrl") or sourceUrl).lower(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        combined.append({**row, "publicOnly": True})
        if len(combined) >= bounded_limit:
            break
    return {
        "ok": True,
        "sourceId": "handelsregister",
        "publicOnly": True,
        "rows": combined,
        "recordsExtracted": len(extracted),
    }


def task_business_person_write_graph(
    roles: Any = None,
    rwHealthy: bool = False,
    dryRun: bool = True,
) -> dict[str, Any]:
    normalized = _as_rows(roles)
    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "recordsPrepared": len(normalized),
            "tables": {"vertex_business_person": normalized},
        }
    if not rwHealthy:
        return {
            "ok": False,
            "degraded": True,
            "recordsPrepared": len(normalized),
            "error": "rwHealthy required before graph write",
        }
    try:
        result = upsert_graph_rows(normalized)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "recordsPrepared": len(normalized), "error": f"businessPerson.writeGraph failed: {exc}"}
    return {"dryRun": False, **result}


def task_business_person_verify_coverage(
    recordsPrepared: int = 0,
    recordsVisible: int = 0,
    recordsWritten: int = 0,
) -> dict[str, Any]:
    visible = int(recordsVisible or recordsWritten or 0)
    prepared = int(recordsPrepared or 0)
    return {
        "ok": visible >= 0 and prepared >= visible,
        "recordsPrepared": prepared,
        "recordsVisible": visible,
        "publicOnly": True,
    }


# ─── Influence scoring tasks (scoreInfluence.bpmn R/PT24H) ──────────────────

def task_business_person_select_persons_from_centrality_mv() -> dict[str, Any]:
    """Read mv_influence_centrality and return all person rows."""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT person_id, name_ja, org_name, out_degree, in_degree, hub_score, "
            "gov_score, bridge_score, strong_tie_count, career_event_count "
            "FROM mv_influence_centrality "
            "ORDER BY hub_score DESC"
        )
        rows = _res
        cols = [d[0] for d in []]
    persons = [dict(zip(cols, row)) for row in rows]
    return {"persons": persons, "personsCount": len(persons)}


def _assign_faction(person: dict[str, Any]) -> str:
    org = str(person.get("org_name") or "").lower()
    if "softbank" in org:
        return "SoftBank派"
    if "kddi" in org or "au" in org:
        return "KDDI派"
    if "ntt" in org or "docomo" in org:
        return "NTT派"
    hub = float(person.get("hub_score") or 0)
    bridge = float(person.get("bridge_score") or 0)
    if bridge >= 2:
        return "cross-industry-bridge"
    if hub >= 3:
        return "hub-high"
    return "independent"


def task_business_person_compute_influence_scores(
    persons: Any = None,
) -> dict[str, Any]:
    """Compute faction_label and normalised scores from centrality MV rows."""
    rows = _as_rows(persons) if persons else []
    scores = []
    today = _today()
    for p in rows:
        hub = float(p.get("hub_score") or 0)
        bridge = float(p.get("bridge_score") or 0)
        gov = float(p.get("gov_score") or 0)
        out_deg = int(p.get("out_degree") or 0)
        in_deg = int(p.get("in_degree") or 0)
        career = int(p.get("career_event_count") or 0)
        faction = _assign_faction(p)
        person_vertex_id = str(p.get("person_id") or "")
        vertex_id = _stable_id("vis", person_vertex_id, today)
        scores.append({
            "vertex_id": f"at://did:web:business-person.etzhayyim.com/com.etzhayyim.apps.businessPerson.influenceScore/{vertex_id}",
            "_seq": None,
            "created_date": today,
            "sensitivity_ord": 200,
            "owner_did": BUSINESS_PERSON_DID,
            "person_vertex_id": person_vertex_id,
            "faction_label": faction,
            "hub_score": hub,
            "bridge_score": bridge,
            "gov_score": gov,
            "out_degree": out_deg,
            "in_degree": in_deg,
            "cross_faction_edges": int(p.get("strong_tie_count") or 0),
            "career_span_years": max(0, career // 2),
            "computed_at": today,
        })
    return {"scores": scores, "scoresCount": len(scores)}


def task_business_person_write_influence_scores(
    scores: Any = None,
) -> dict[str, Any]:
    """Insert/update vertex_influence_score rows (delete-then-insert per RW upsert pattern)."""
    rows = _as_rows(scores) if scores else []
    if not rows:
        return {"ok": True, "recordsWritten": 0}
    written = 0
    if True:
        client = get_kotoba_client()
        for row in rows:
            pk = row.get("vertex_id")
            if not pk:
                continue
            _res = client.q("DELETE FROM vertex_influence_score WHERE vertex_id = %s", (pk,))
            clean = {k: v for k, v in row.items() if v is not None and k != "_seq"}
            cols = list(clean)
            placeholders = ", ".join(["%s"] * len(cols))
            col_sql = ", ".join(cols)
            _res = client.q(
                f"INSERT INTO vertex_influence_score ({col_sql}) VALUES ({placeholders})",
                [clean[c] for c in cols],
            )
            written += 1
    return {"ok": True, "recordsWritten": written}


# ─── LLM career enrichment tasks (enrichCareerLLM.bpmn R/PT7D) ──────────────

_NEWS_SEARCH_TMPL = "https://news.google.com/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
_CORP_HP_TMPL = "https://www.{domain}/management"

_TELECOM_DOMAINS = {
    "softbank": "softbank.jp",
    "kddi": "kddi.com",
    "ntt": "ntt.com",
    "docomo": "docomo.ne.jp",
}


def _news_url_for_person(name_ja: str, org_name: str) -> str:
    query = quote_plus(f"{name_ja} {org_name} 人事 経歴".strip())
    return _NEWS_SEARCH_TMPL.format(query=query)


def task_business_person_select_stale_persons(
    staleDays: int = 7,
) -> dict[str, Any]:
    """Select persons whose career enrichment is older than staleDays or missing."""
    cutoff = _today()
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT p.vertex_id, p.name_ja, p.name_en, p.org_name, p.org_did "
            "FROM vertex_business_person p "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM vertex_business_person_career_event e "
            "  WHERE e.person_vertex_id = p.vertex_id "
            "    AND e.ingested_at >= %s"
            ")"
            "ORDER BY p.vertex_id "
            "LIMIT 10",
            (cutoff,),
        )
        rows = _res
        cols = [d[0] for d in []]
    persons = [dict(zip(cols, row)) for row in rows]
    return {"persons": persons, "personsCount": len(persons)}


def task_business_person_fetch_news_career(
    persons: Any = None,
) -> dict[str, Any]:
    """Fetch Google News search result pages for each person (plain-text snippet only)."""
    import urllib.request as _req

    rows = _as_rows(persons) if persons else []
    page_texts = []
    headers = {
        "User-Agent": FETCH_USER_AGENT,
        "Accept-Language": "ja,en;q=0.8",
    }
    for p in rows:
        name_ja = str(p.get("name_ja") or "")
        org_name = str(p.get("org_name") or "")
        person_vertex_id = str(p.get("vertex_id") or "")
        if not name_ja:
            continue
        url = _news_url_for_person(name_ja, org_name)
        try:
            request = _req.Request(url, headers=headers)
            with _req.urlopen(request, timeout=10) as resp:
                raw = resp.read(65536)
                text = raw.decode("utf-8", errors="replace")
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text)[:4000]
        except Exception:  # noqa: BLE001
            text = ""
        page_texts.append({
            "person_vertex_id": person_vertex_id,
            "name_ja": name_ja,
            "org_name": org_name,
            "text": text,
            "source_url": url,
        })
    return {"pageTexts": page_texts}


_CAREER_EXTRACT_SYSTEM = (
    "あなたは日本のIT/通信業界の人事・経歴情報を抽出するアナリストです。"
    "与えられたテキストから、指定された人物の職歴イベント（在籍組織、役職、期間）を抽出してください。"
    "必ずJSON形式で回答してください。"
)

_CAREER_EXTRACT_PROMPT = """
以下のテキストから {name_ja}（{org_name}）の職歴イベントを抽出してください。

テキスト:
{text}

以下のJSON形式で回答してください（複数ある場合は配列）:
{{
  "events": [
    {{
      "org_name": "組織名",
      "title": "役職名",
      "since": "YYYY-MM（任意）",
      "until": "YYYY-MM（任意、現職なら空文字）",
      "description": "説明（任意）"
    }}
  ]
}}
テキストに職歴情報がない場合は {{"events": []}} を返してください。
"""


def task_business_person_extract_career_llm(
    pageTexts: Any = None,
    persons: Any = None,
) -> dict[str, Any]:
    """Call RunPod LLM to extract career events. Provenance: confidence=0.6, llm_inferred."""
    from kotodama import llm as _llm

    page_list = _as_rows(pageTexts) if pageTexts else []
    extractions: list[dict[str, Any]] = []
    today = _today()

    for page in page_list:
        person_vertex_id = str(page.get("person_vertex_id") or "")
        name_ja = str(page.get("name_ja") or "")
        org_name = str(page.get("org_name") or "")
        text = str(page.get("text") or "")
        if not text.strip() or not person_vertex_id:
            continue
        prompt = _CAREER_EXTRACT_PROMPT.format(
            name_ja=name_ja,
            org_name=org_name,
            text=text[:3000],
        )
        try:
            result = _llm.call_tier_json(
                tier="structured",
                system=_CAREER_EXTRACT_SYSTEM,
                user=prompt,
                max_tokens=512,
                temperature=0.1,
            )
            events = result.get("data", result).get("events", []) if isinstance(result, dict) else []
        except Exception:  # noqa: BLE001
            events = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            ev_org = str(ev.get("org_name") or org_name)
            ev_title = str(ev.get("title") or "")
            if not ev_title:
                continue
            vertex_id_raw = _stable_id("bpce-llm", person_vertex_id, ev_org, ev_title, today)
            extractions.append({
                "vertex_id": f"at://did:web:business-person.etzhayyim.com/com.etzhayyim.apps.businessPerson.careerEvent/{vertex_id_raw}",
                "created_date": today,
                "sensitivity_ord": 200,
                "owner_did": BUSINESS_PERSON_DID,
                "person_vertex_id": person_vertex_id,
                "org_name": ev_org,
                "title": ev_title,
                "since": str(ev.get("since") or ""),
                "until": str(ev.get("until") or ""),
                "description": str(ev.get("description") or "")[:500],
                "source": "llm_inferred",
                "ingested_at": today,
                "confidence": 0.6,
                "verification_status": "llm_inferred",
            })
    return {"extractions": extractions, "extractionsCount": len(extractions)}


def task_business_person_write_career_enrichment(
    extractions: Any = None,
) -> dict[str, Any]:
    """Write LLM-inferred career events to vertex_business_person_career_event."""
    rows = _as_rows(extractions) if extractions else []
    if not rows:
        return {"ok": True, "recordsWritten": 0}
    written = 0
    # confidence goes on edge_business_person_skill / career events have no confidence col —
    # store in props field as JSON.
    if True:
        client = get_kotoba_client()
        for row in rows:
            pk = row.get("vertex_id")
            if not pk:
                continue
            # props encodes confidence + verification_status for career events
            props_data = {
                "confidence": row.pop("confidence", 0.6),
                "verification_status": row.pop("verification_status", "llm_inferred"),
            }
            row["props"] = json.dumps(props_data, ensure_ascii=False)
            _res = client.q(
                "SELECT 1 FROM vertex_business_person_career_event WHERE vertex_id = %s",
                (pk,),
            )
            if (_res[0] if _res else None):
                continue
            clean = {k: v for k, v in row.items() if v is not None and k not in {"_seq"}}
            cols = list(clean)
            placeholders = ", ".join(["%s"] * len(cols))
            col_sql = ", ".join(cols)
            _res = client.q(
                f"INSERT INTO vertex_business_person_career_event ({col_sql}) VALUES ({placeholders})",
                [clean[c] for c in cols],
            )
            written += 1
    return {"ok": True, "recordsWritten": written}


# ─── Relation mining tasks ────────────────────────────────────────────────


def _news_url_for_pair(name_ja1: str, name_ja2: str, org1: str = "", org2: str = "") -> str:
    query = f'"{name_ja1}" "{name_ja2}"'
    if org1 or org2:
        query += f' ({org1} OR {org2})'
    params = urlencode({"q": query, "hl": "ja", "gl": "JP", "ceid": "JP:ja"})
    return f"https://news.google.com/rss?{params}"


def task_business_person_mine_relations(
    persons: Any = None,
) -> dict[str, Any]:
    """Fetch Google News RSS for pairs of executives and collect raw news text for relation mining."""
    import urllib.request as _req

    rows = _as_rows(persons) if persons else []
    if not rows:
        return {"pairs": []}

    headers = {
        "User-Agent": FETCH_USER_AGENT,
        "Accept-Language": "ja,en;q=0.8",
    }

    pairs = []
    seen = set()
    for i, p1 in enumerate(rows):
        for j, p2 in enumerate(rows):
            if i >= j:
                continue
            pair_key = (p1.get("vertex_id", ""), p2.get("vertex_id", ""))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            if len(pairs) >= 10:
                break

            name_ja1 = str(p1.get("name_ja") or "")
            name_ja2 = str(p2.get("name_ja") or "")
            org1 = str(p1.get("org_name") or "")
            org2 = str(p2.get("org_name") or "")
            if not name_ja1 or not name_ja2:
                continue

            url = _news_url_for_pair(name_ja1, name_ja2, org1, org2)
            try:
                request = _req.Request(url, headers=headers)
                with _req.urlopen(request, timeout=10) as resp:
                    raw = resp.read(65536)
                    text = raw.decode("utf-8", errors="replace")
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text)[:4000]
            except Exception:  # noqa: BLE001
                text = ""

            if not text.strip():
                continue

            pairs.append({
                "src_vertex_id": pair_key[0],
                "dst_vertex_id": pair_key[1],
                "src_name_ja": name_ja1,
                "dst_name_ja": name_ja2,
                "news_text": text,
            })

        if len(pairs) >= 10:
            break

    return {"pairs": pairs, "pairsCount": len(pairs)}


_RELATION_EXTRACT_SYSTEM = (
    "あなたは日本のIT/通信業界の人物関係を分析するアナリストです。"
    "与えられたニューステキストから、2人の人物の関係性を抽出してください。"
    "必ずJSON形式で回答してください。"
)

_RELATION_EXTRACT_PROMPT = """
以下のニューステキストから、{src_name_ja} と {dst_name_ja} の関係を分析してください。

テキスト:
{news_text}

以下のJSON形式で回答してください:
{{
  "relations": [
    {{
      "relation_type": "hierarchical|peer|consortium_member|conference_co_speaker|government_advisory|corporate_group|mentor_mentee|former_colleague",
      "org_context": "関係が生じた組織・文脈",
      "strength": "strong|moderate|weak",
      "confidence": 0.0から1.0の数値,
      "description": "関係の説明（日本語）"
    }}
  ]
}}
テキストに関係情報がない場合は {{"relations": []}} を返してください。
"""


def task_business_person_extract_relations_llm(
    pairs: Any = None,
) -> dict[str, Any]:
    """Use LLM to extract relation types from news text for each person pair."""
    from kotodama import llm as _llm

    pair_list = _as_rows(pairs) if pairs else []
    relations: list[dict[str, Any]] = []

    for pair in pair_list:
        src_vertex_id = str(pair.get("src_vertex_id") or "")
        dst_vertex_id = str(pair.get("dst_vertex_id") or "")
        src_name_ja = str(pair.get("src_name_ja") or "")
        dst_name_ja = str(pair.get("dst_name_ja") or "")
        news_text = str(pair.get("news_text") or "")
        if not news_text.strip() or not src_vertex_id or not dst_vertex_id:
            continue

        prompt = _RELATION_EXTRACT_PROMPT.format(
            src_name_ja=src_name_ja,
            dst_name_ja=dst_name_ja,
            news_text=news_text[:3000],
        )
        try:
            result = _llm.call_tier_json(
                tier="structured",
                system=_RELATION_EXTRACT_SYSTEM,
                user=prompt,
                max_tokens=512,
                temperature=0.1,
            )
            extracted = result.get("data", result).get("relations", []) if isinstance(result, dict) else []
        except Exception:  # noqa: BLE001
            extracted = []

        for rel in extracted:
            if not isinstance(rel, dict):
                continue
            rel_type = str(rel.get("relation_type") or "peer")
            relations.append({
                "src_vertex_id": src_vertex_id,
                "dst_vertex_id": dst_vertex_id,
                "relation_type": rel_type,
                "org_context": str(rel.get("org_context") or "")[:200],
                "strength": str(rel.get("strength") or "moderate"),
                "confidence": float(rel.get("confidence") or 0.5),
                "description": str(rel.get("description") or "")[:500],
            })

    return {"relations": relations, "relationsCount": len(relations)}


def task_business_person_write_relations(
    relations: Any = None,
) -> dict[str, Any]:
    """Write extracted relations to edge_business_person_relation."""
    rows = _as_rows(relations) if relations else []
    if not rows:
        return {"ok": True, "written": 0}

    today = _today()
    written = 0
    if True:
        client = get_kotoba_client()
        for row in rows:
            src = str(row.get("src_vertex_id") or "")
            dst = str(row.get("dst_vertex_id") or "")
            rel_type = str(row.get("relation_type") or "peer")
            if not src or not dst:
                continue

            edge_id = _stable_id("rel", src, dst, rel_type)

            _res = client.q(
                "SELECT 1 FROM edge_business_person_relation WHERE edge_id = %s",
                (edge_id,),
            )
            if (_res[0] if _res else None):
                continue

            _res = client.q(
                "INSERT INTO edge_business_person_relation "
                "(edge_id, src_person_id, dst_person_id, relation_type, org_context, "
                "direction, strength, description, source, ingested_at, confidence, verification_status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    edge_id,
                    src,
                    dst,
                    rel_type,
                    str(row.get("org_context") or ""),
                    "undirected",
                    str(row.get("strength") or "moderate"),
                    str(row.get("description") or ""),
                    "llm_inferred",
                    today,
                    float(row.get("confidence") or 0.5),
                    "llm_inferred",
                ),
            )
            written += 1

    return {"ok": True, "written": written}


# ─── LEI / public-company enrichment tasks (enrichOrgLei.bpmn R/PT24H) ──────

GLEIF_API = "https://api.gleif.org/api/v1"
_LEI_SEARCH_ALIASES: dict[str, str] = {
    # JP
    "KDDI Corp.": "KDDI株式会社",
    "NTT Group / NTT Security Holdings": "ＮＴＴ株式会社",
    "NTTコミュニケーションズ株式会社": "NTTコミュニケーションズ",
    "SB Technology Corp. (SBテクノロジー)": "SBテクノロジー株式会社",
    "SoftBank Corp.": "ソフトバンク株式会社",
    "パロアルトネットワークス株式会社": "パロアルトネットワークス株式会社",
    "株式会社NTTドコモ": "株式会社NTTドコモ",
    # Global — GLEIF registered legal names
    "Google LLC": "Google LLC",
    "Microsoft Corporation": "Microsoft Corporation",
    "Amazon Web Services Inc.": "Amazon Web Services, Inc.",
    "Meta Platforms Inc.": "Meta Platforms, Inc.",
    "Apple Inc.": "Apple Inc.",
    "AT&T Inc.": "AT&T Inc.",
    "Verizon Communications Inc.": "Verizon Communications Inc.",
    "T-Mobile US Inc.": "T-Mobile USA, Inc.",
    "CrowdStrike Holdings Inc.": "CrowdStrike Holdings, Inc.",
    "Palo Alto Networks Inc.": "Palo Alto Networks, Inc.",
    "Mandiant Inc.": "Mandiant, Inc.",
    "Cisco Systems Inc.": "Cisco Systems, Inc.",
    "Deutsche Telekom AG": "Deutsche Telekom AG",
    "Vodafone Group Plc": "Vodafone Group Public Limited Company",
    "Orange SA": "Orange",
    "Telecom Italia SpA": "Telecom Italia S.p.A.",
    "SK Telecom Co. Ltd.": "SK텔레콤 주식회사",
    "KT Corporation": "주식회사 케이티",
    "Samsung SDS Co. Ltd.": "삼성에스디에스 주식회사",
    "Singtel Group": "Singapore Telecommunications Limited",
    "Telstra Corporation Limited": "Telstra Corporation Limited",
    "China Telecom Corporation Limited": "China Telecom Corporation Limited",
    "Huawei Technologies Co. Ltd.": "华为技术有限公司",
}


def task_business_person_select_orgs_needing_lei() -> dict[str, Any]:
    """Return distinct org_names from vertex_business_person that have no LEI yet."""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT DISTINCT org_name FROM vertex_business_person "
            "WHERE org_name IS NOT NULL AND org_name != '' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM vertex_lei_entity v "
            "  WHERE v.legal_name = org_name OR v.legal_name_local = org_name"
            ")"
        )
        rows = _res
    orgs = [{"org_name": r[0]} for r in rows if r[0]]
    return {"orgs": orgs, "orgsCount": len(orgs)}


def task_business_person_resolve_lei(
    orgs: Any = None,
) -> dict[str, Any]:
    """Query GLEIF API to resolve each org_name to a LEI code."""
    import urllib.request as _req

    org_list = _as_rows(orgs) if orgs else []
    resolved: list[dict[str, Any]] = []

    for item in org_list:
        org_name = str(item.get("org_name") or "")
        if not org_name:
            continue
        # Apply alias normalization for GLEIF search
        search_name = _LEI_SEARCH_ALIASES.get(org_name, org_name)
        # Try JP jurisdiction first, then global
        for jurisdiction in ("JP", ""):
            params = urlencode(
                {
                    k: v
                    for k, v in {
                        "filter[entity.legalName]": search_name,
                        "filter[entity.jurisdiction]": jurisdiction,
                        "page[number]": "1",
                        "page[size]": "3",
                    }.items()
                    if v
                }
            )
            url = f"{GLEIF_API}/lei-records?{params}"
            try:
                req = _req.Request(url, headers={"Accept": "application/vnd.api+json"})
                with _req.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                hits = data.get("data", [])
                if hits:
                    best = hits[0]
                    attr = best.get("attributes", {})
                    entity = attr.get("entity", {})
                    resolved.append({
                        "org_name": org_name,
                        "lei": attr.get("lei", ""),
                        "legal_name": entity.get("legalName", {}).get("name", ""),
                        "legal_name_local": (entity.get("legalName", {}).get("otherNames") or [{}])[0].get("name", "") if entity.get("legalName", {}).get("otherNames") else "",
                        "jurisdiction": entity.get("jurisdiction", ""),
                        "entity_status": entity.get("status", ""),
                        "entity_category": entity.get("category", ""),
                        "legal_form_id": entity.get("legalForm", {}).get("id", "") if entity.get("legalForm") else "",
                        "hq_country": entity.get("headquartersAddress", {}).get("country", "") if entity.get("headquartersAddress") else "",
                        "registered_country": entity.get("registeredAddress", {}).get("country", "") if entity.get("registeredAddress") else "",
                        "registration_status": attr.get("registration", {}).get("status", ""),
                        "initially_registered": attr.get("registration", {}).get("initialRegistrationDate", ""),
                        "last_updated": attr.get("registration", {}).get("lastUpdateDate", ""),
                        "next_renewal": attr.get("registration", {}).get("nextRenewalDate", ""),
                        "managing_lou": attr.get("registration", {}).get("managingLou", ""),
                    })
                    break
            except Exception:  # noqa: BLE001
                continue

    return {"resolved": resolved, "resolvedCount": len(resolved)}


def task_business_person_fetch_lei_hierarchy(
    resolved: Any = None,
) -> dict[str, Any]:
    """Fetch parent and ultimate-parent LEI for each resolved entity."""
    import urllib.request as _req

    rows = _as_rows(resolved) if resolved else []
    enriched: list[dict[str, Any]] = []

    for item in rows:
        lei = str(item.get("lei") or "")
        if not lei:
            enriched.append(item)
            continue

        # Direct parent
        parent_lei = ""
        try:
            url = f"{GLEIF_API}/lei-records/{lei}/direct-parent-relationship"
            req = _req.Request(url, headers={"Accept": "application/vnd.api+json"})
            with _req.urlopen(req, timeout=8) as resp:
                d = json.loads(resp.read())
            rels = d.get("data", {}).get("attributes", {}).get("relationships", {})
            parent_lei = rels.get("lei", "") if isinstance(rels, dict) else ""
        except Exception:  # noqa: BLE001
            pass

        # Ultimate parent
        ultimate_parent_lei = ""
        try:
            url = f"{GLEIF_API}/lei-records/{lei}/ultimate-parent-relationship"
            req = _req.Request(url, headers={"Accept": "application/vnd.api+json"})
            with _req.urlopen(req, timeout=8) as resp:
                d = json.loads(resp.read())
            rels = d.get("data", {}).get("attributes", {}).get("relationships", {})
            ultimate_parent_lei = rels.get("lei", "") if isinstance(rels, dict) else ""
        except Exception:  # noqa: BLE001
            pass

        enriched.append({**item, "parent_lei": parent_lei, "ultimate_parent_lei": ultimate_parent_lei})

    return {"enriched": enriched, "enrichedCount": len(enriched)}


def task_business_person_write_lei_entities(
    enriched: Any = None,
) -> dict[str, Any]:
    """Write resolved LEI entities to vertex_lei_entity and link persons."""
    rows = _as_rows(enriched) if enriched else []
    if not rows:
        return {"ok": True, "entitiesWritten": 0, "edgesWritten": 0}

    today = _today()
    entities_written = 0
    edges_written = 0

    if True:

        client = get_kotoba_client()
        # Write each LEI entity
        for item in rows:
            lei = str(item.get("lei") or "")
            if not lei:
                continue

            vertex_id = f"at://did:web:business-person.etzhayyim.com/com.etzhayyim.apps.businessPerson.leiEntity/{lei}"

            _res = client.q("SELECT 1 FROM vertex_lei_entity WHERE vertex_id = %s", (vertex_id,))
            if not (_res[0] if _res else None):
                _res = client.q(
                    "INSERT INTO vertex_lei_entity "
                    "(vertex_id, lei, legal_name, legal_name_local, legal_form_id, "
                    "jurisdiction, entity_status, entity_category, registered_country, hq_country, "
                    "parent_lei, ultimate_parent_lei, registration_status, initially_registered, "
                    "last_updated, next_renewal, managing_lou, source, ingested_at, actor_did, org_did, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        vertex_id, lei,
                        str(item.get("legal_name") or ""),
                        str(item.get("legal_name_local") or ""),
                        str(item.get("legal_form_id") or ""),
                        str(item.get("jurisdiction") or ""),
                        str(item.get("entity_status") or ""),
                        str(item.get("entity_category") or ""),
                        str(item.get("registered_country") or ""),
                        str(item.get("hq_country") or ""),
                        str(item.get("parent_lei") or ""),
                        str(item.get("ultimate_parent_lei") or ""),
                        str(item.get("registration_status") or ""),
                        str(item.get("initially_registered") or ""),
                        str(item.get("last_updated") or ""),
                        str(item.get("next_renewal") or ""),
                        str(item.get("managing_lou") or ""),
                        "gleif",
                        today,
                        "", "", today,
                    ),
                )
                entities_written += 1

            # Link persons with matching org_name → this LEI
            org_name = str(item.get("org_name") or "")
            if org_name:
                _res = client.q(
                    "SELECT vertex_id FROM vertex_business_person WHERE org_name = %s",
                    (org_name,),
                )
                person_rows = _res
                for (person_vid,) in person_rows:
                    edge_id = _stable_id("plei", person_vid, vertex_id)
                    _res = client.q(
                        "SELECT 1 FROM edge_person_lei_entity WHERE edge_id = %s",
                        (edge_id,),
                    )
                    if not (_res[0] if _res else None):
                        _res = client.q(
                            "INSERT INTO edge_person_lei_entity "
                            "(edge_id, person_vertex_id, lei_vertex_id, role, confidence, source, ingested_at) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (edge_id, person_vid, vertex_id, "employee", 0.9, "gleif", today),
                        )
                        edges_written += 1

    return {"ok": True, "entitiesWritten": entities_written, "edgesWritten": edges_written}


# ─── Global executive discovery (enrichGlobalPersons.bpmn R/PT168H) ──────────

_GLOBAL_TARGET_ORGS: list[dict[str, str]] = [
    # US Big Tech
    {"org_name": "Google LLC", "country": "US", "sector": "tech"},
    {"org_name": "Microsoft Corporation", "country": "US", "sector": "tech"},
    {"org_name": "Amazon Web Services Inc.", "country": "US", "sector": "tech"},
    {"org_name": "Meta Platforms Inc.", "country": "US", "sector": "tech"},
    {"org_name": "Apple Inc.", "country": "US", "sector": "tech"},
    # US Telco
    {"org_name": "AT&T Inc.", "country": "US", "sector": "telco"},
    {"org_name": "Verizon Communications Inc.", "country": "US", "sector": "telco"},
    {"org_name": "T-Mobile US Inc.", "country": "US", "sector": "telco"},
    # US Cybersecurity
    {"org_name": "CrowdStrike Holdings Inc.", "country": "US", "sector": "cybersecurity"},
    {"org_name": "Palo Alto Networks Inc.", "country": "US", "sector": "cybersecurity"},
    {"org_name": "Mandiant Inc.", "country": "US", "sector": "cybersecurity"},
    {"org_name": "Cisco Systems Inc.", "country": "US", "sector": "tech"},
    # EU Telco
    {"org_name": "Deutsche Telekom AG", "country": "DE", "sector": "telco"},
    {"org_name": "Vodafone Group Plc", "country": "GB", "sector": "telco"},
    {"org_name": "Orange SA", "country": "FR", "sector": "telco"},
    {"org_name": "Telecom Italia SpA", "country": "IT", "sector": "telco"},
    # KR
    {"org_name": "SK Telecom Co. Ltd.", "country": "KR", "sector": "telco"},
    {"org_name": "KT Corporation", "country": "KR", "sector": "telco"},
    {"org_name": "Samsung SDS Co. Ltd.", "country": "KR", "sector": "tech"},
    # SG / AU
    {"org_name": "Singtel Group", "country": "SG", "sector": "telco"},
    {"org_name": "Telstra Corporation Limited", "country": "AU", "sector": "telco"},
    # CN
    {"org_name": "China Telecom Corporation Limited", "country": "CN", "sector": "telco"},
    {"org_name": "Huawei Technologies Co. Ltd.", "country": "CN", "sector": "tech"},
    # Wave 2 — India IT/Telco
    {"org_name": "Reliance Jio Infocomm Limited", "country": "IN", "sector": "telco"},
    {"org_name": "Bharti Airtel Limited", "country": "IN", "sector": "telco"},
    {"org_name": "Tata Consultancy Services Limited", "country": "IN", "sector": "tech"},
    {"org_name": "Infosys Limited", "country": "IN", "sector": "tech"},
    {"org_name": "Wipro Limited", "country": "IN", "sector": "tech"},
    {"org_name": "HCL Technologies Limited", "country": "IN", "sector": "tech"},
    # Wave 2 — SE Asia
    {"org_name": "Maxis Communications Berhad", "country": "MY", "sector": "telco"},
    {"org_name": "Telkom Indonesia", "country": "ID", "sector": "telco"},
    {"org_name": "Advanced Info Service Public Company Limited", "country": "TH", "sector": "telco"},
    # Wave 2 — Middle East
    {"org_name": "Saudi Telecom Company", "country": "SA", "sector": "telco"},
    {"org_name": "Etisalat Group", "country": "AE", "sector": "telco"},
    # Wave 2 — Africa / LATAM
    {"org_name": "MTN Group Limited", "country": "ZA", "sector": "telco"},
    {"org_name": "America Movil SAB de CV", "country": "MX", "sector": "telco"},
    # Wave 2 — More EU
    {"org_name": "BT Group Plc", "country": "GB", "sector": "telco"},
    {"org_name": "Telefonica SA", "country": "ES", "sector": "telco"},
    {"org_name": "Swisscom AG", "country": "CH", "sector": "telco"},
    # Wave 2 — Network infra vendors
    {"org_name": "Nokia Corporation", "country": "FI", "sector": "tech"},
    {"org_name": "Ericsson AB", "country": "SE", "sector": "tech"},
    # Wave 2 — US/IL cybersec expansion
    {"org_name": "Check Point Software Technologies Ltd.", "country": "IL", "sector": "cybersecurity"},
    {"org_name": "SentinelOne Inc.", "country": "US", "sector": "cybersecurity"},
    {"org_name": "IBM Corporation", "country": "US", "sector": "tech"},
    {"org_name": "Fortinet Inc.", "country": "US", "sector": "cybersecurity"},
    # Wave 3 — more APAC
    {"org_name": "Globe Telecom Inc.", "country": "PH", "sector": "telco"},
    {"org_name": "Taiwan Mobile Co. Ltd.", "country": "TW", "sector": "telco"},
    {"org_name": "VNPT Group", "country": "VN", "sector": "telco"},
    {"org_name": "HCL Technologies Limited", "country": "IN", "sector": "tech"},
    {"org_name": "Qualys Inc.", "country": "US", "sector": "cybersecurity"},
    # Wave 3 — more LATAM / EU / TR / RU
    {"org_name": "Vivo (Telefonica Brasil SA)", "country": "BR", "sector": "telco"},
    {"org_name": "Claro Brasil (America Movil)", "country": "BR", "sector": "telco"},
    {"org_name": "Proximus Group", "country": "BE", "sector": "telco"},
    {"org_name": "MTS (Mobile TeleSystems PJSC)", "country": "RU", "sector": "telco"},
    {"org_name": "Turkcell Iletisim Hizmetleri AS", "country": "TR", "sector": "telco"},
    # Wave 4 — Africa / LATAM depth
    {"org_name": "Safaricom PLC", "country": "KE", "sector": "telco"},
    {"org_name": "Airtel Africa PLC", "country": "GB", "sector": "telco"},
    {"org_name": "Telecom Egypt SAE", "country": "EG", "sector": "telco"},
    {"org_name": "Claro Colombia (America Movil)", "country": "CO", "sector": "telco"},
    {"org_name": "Telefonica Chile SA", "country": "CL", "sector": "telco"},
    {"org_name": "Telefonica Argentina SA", "country": "AR", "sector": "telco"},
    # Wave 4 — EU depth
    {"org_name": "KPN NV", "country": "NL", "sector": "telco"},
    {"org_name": "Orange Polska SA", "country": "PL", "sector": "telco"},
    # Wave 4 — US cybersec depth
    {"org_name": "Zscaler Inc.", "country": "US", "sector": "cybersecurity"},
    {"org_name": "Tenable Holdings Inc.", "country": "US", "sector": "cybersecurity"},
    {"org_name": "Okta Inc.", "country": "US", "sector": "cybersecurity"},
    {"org_name": "Rapid7 Inc.", "country": "US", "sector": "cybersecurity"},
    {"org_name": "Splunk Inc.", "country": "US", "sector": "tech"},
    {"org_name": "Varonis Systems Inc.", "country": "US", "sector": "cybersecurity"},
    # Wave 5 — South Asia / Oceania
    {"org_name": "Jazz (Veon Ltd Pakistan)", "country": "PK", "sector": "telco"},
    {"org_name": "Grameenphone Ltd", "country": "BD", "sector": "telco"},
    {"org_name": "MTN Nigeria Communications PLC", "country": "NG", "sector": "telco"},
    {"org_name": "Spark New Zealand Limited", "country": "NZ", "sector": "telco"},
    # Wave 5 — LATAM depth
    {"org_name": "Movistar Peru (Telefonica del Peru)", "country": "PE", "sector": "telco"},
    {"org_name": "Entel Chile SA", "country": "CL", "sector": "telco"},
    # Wave 5 — Eastern EU
    {"org_name": "O2 Czech Republic AS", "country": "CZ", "sector": "telco"},
    {"org_name": "Orange Romania SA", "country": "RO", "sector": "telco"},
    # Wave 5 — Cloud/identity security
    {"org_name": "Cloudflare Inc.", "country": "US", "sector": "tech"},
    {"org_name": "CyberArk Software Ltd.", "country": "IL", "sector": "cybersecurity"},
]

_DISCOVER_EXECS_SYSTEM = (
    "You are a cybersecurity intelligence analyst. "
    "Given an organization, identify its senior cybersecurity and technology leadership. "
    "Return a JSON object with key 'persons', an array of objects each with: "
    "name_en (full name in English), title (current or most recent title), "
    "org_name (exactly as provided), country (2-letter ISO code), "
    "source (brief description: e.g. 'public LinkedIn', 'company press release'). "
    "Focus on CISO, CSO, CTO, VP Security, Head of Cybersecurity, or equivalent roles. "
    "Return between 1 and 5 persons per organization. "
    "Only include persons whose current or recent role you are confident about. "
    "Return only the JSON object, no markdown fences."
)

_DISCOVER_EXECS_PROMPT = (
    "Identify the current senior cybersecurity and technology leadership "
    "(CISO, CSO, CTO, VP Security, Head of Security, or equivalent) "
    "at {org_name} ({country}). "
    'Return exactly: {{"persons": [{{"name_en": "...", "title": "...", '
    '"org_name": "{org_name}", "country": "{country}", "source": "..."}}]}}'
)


def task_business_person_select_global_target_orgs() -> dict[str, Any]:
    """Return global target orgs not yet covered in vertex_business_person."""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT DISTINCT org_name FROM vertex_business_person WHERE country != 'JP'"
        )
        covered = {row[0] for row in (_res or [])}

    pending = [o for o in _GLOBAL_TARGET_ORGS if o["org_name"] not in covered]
    return {"orgs": pending, "total": len(_GLOBAL_TARGET_ORGS), "pending": len(pending)}


def task_business_person_discover_global_execs(
    orgs: list[dict[str, Any]],
) -> dict[str, Any]:
    """LLM-discover CISO/CSO/CTO per global target org."""
    import logging

    from kotodama import llm as _llm

    log = logging.getLogger(__name__)
    orgs_list = _as_rows(orgs)
    all_persons: list[dict[str, Any]] = []

    for org in orgs_list:
        org_name = org.get("org_name", "")
        country = org.get("country", "")
        if not org_name:
            continue
        prompt = _DISCOVER_EXECS_PROMPT.format(org_name=org_name, country=country)
        try:
            result = _llm.call_tier_json(
                tier="structured",
                system=_DISCOVER_EXECS_SYSTEM,
                user=prompt,
                max_tokens=1024,
                temperature=0.1,
            )
            persons = (
                result.get("data", result).get("persons", [])
                if isinstance(result, dict)
                else []
            )
            for p in persons:
                if isinstance(p, dict) and p.get("name_en"):
                    p.setdefault("org_name", org_name)
                    p.setdefault("country", country)
                    all_persons.append(p)
        except Exception as exc:
            log.warning("discover_global_execs %s: %s", org_name, exc)

    return {"persons": all_persons, "discovered": len(all_persons)}


def task_business_person_write_global_execs(
    persons: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deduplicate by name_en+org_name and insert new persons into vertex_business_person."""
    import datetime

    persons_list = _as_rows(persons)
    today = datetime.date.today().isoformat()
    written = 0
    skipped = 0

    if True:

        client = get_kotoba_client()
        for p in persons_list:
            name_en = (p.get("name_en") or "").strip()
            org_name = (p.get("org_name") or "").strip()
            if not name_en or not org_name:
                skipped += 1
                continue

            vertex_id = _stable_id("business_person", name_en, org_name)
            title = (p.get("title") or "").strip()
            country = (p.get("country") or "").strip().upper()
            source = (p.get("source") or "llm-discovery").strip()

            _res = client.q(
                "SELECT 1 FROM vertex_business_person WHERE vertex_id = %s",
                (vertex_id,),
            )
            if (_res[0] if _res else None):
                skipped += 1
                continue

            _res = client.q(
                "INSERT INTO vertex_business_person "
                "(vertex_id, name_ja, name_en, org_name, title, country, source, created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (vertex_id, name_en, name_en, org_name, title, country, source, today),
            )
            written += 1

    return {"ok": True, "written": written, "skipped": skipped}


def register(worker: Any, timeout_ms: int = 180_000) -> None:
    worker.task(
        task_type="businessPerson.planPublicRoleSources",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_plan_public_role_sources)
    worker.task(
        task_type="businessPerson.fetchPublicSource",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_fetch_public_source)
    worker.task(
        task_type="businessPerson.prepareSourceRequest",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_prepare_source_request)
    worker.task(
        task_type="businessPerson.advanceSourceCursor",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_advance_source_cursor)
    worker.task(
        task_type="businessPerson.scheduleNextPage",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_schedule_next_page)
    worker.task(
        task_type="businessPerson.normalizePublicRoles",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_normalize_public_roles)
    worker.task(
        task_type="businessPerson.extractCorporateHpRoles",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_extract_corporate_hp_roles)
    worker.task(
        task_type="businessPerson.extractCompaniesHouseOfficers",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_extract_companies_house_officers)
    worker.task(
        task_type="businessPerson.extractGbizinfoRepresentatives",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_extract_gbizinfo_representatives)
    worker.task(
        task_type="businessPerson.extractEdinetOfficers",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_extract_edinet_officers)
    worker.task(
        task_type="businessPerson.extractSecEdgarOfficers",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_extract_sec_edgar_officers)
    worker.task(
        task_type="businessPerson.extractHandelsregisterOfficers",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_extract_handelsregister_officers)
    worker.task(
        task_type="businessPerson.writeGraph",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_write_graph)
    worker.task(
        task_type="businessPerson.verifyCoverage",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_verify_coverage)
    # scoreInfluence.bpmn tasks
    worker.task(
        task_type="businessPerson.selectPersonsFromCentralityMv",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_select_persons_from_centrality_mv)
    worker.task(
        task_type="businessPerson.computeInfluenceScores",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_compute_influence_scores)
    worker.task(
        task_type="businessPerson.writeInfluenceScores",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_write_influence_scores)
    # enrichCareerLLM.bpmn tasks
    worker.task(
        task_type="businessPerson.selectStalePersons",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_select_stale_persons)
    worker.task(
        task_type="businessPerson.fetchNewsCareer",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_fetch_news_career)
    worker.task(
        task_type="businessPerson.extractCareerLLM",
        single_value=False,
        timeout_ms=timeout_ms * 2,
    )(task_business_person_extract_career_llm)
    worker.task(
        task_type="businessPerson.writeCareerEnrichment",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_write_career_enrichment)
    # mineRelations.bpmn tasks
    worker.task(
        task_type="businessPerson.mineRelations",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_mine_relations)
    worker.task(
        task_type="businessPerson.extractRelationsLlm",
        single_value=False,
        timeout_ms=timeout_ms * 2,
    )(task_business_person_extract_relations_llm)
    worker.task(
        task_type="businessPerson.writeRelations",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_write_relations)
    # enrichOrgLei.bpmn tasks (R/PT24H)
    worker.task(
        task_type="businessPerson.selectOrgsNeedingLei",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_select_orgs_needing_lei)
    worker.task(
        task_type="businessPerson.resolveLei",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_resolve_lei)
    worker.task(
        task_type="businessPerson.fetchLeiHierarchy",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_fetch_lei_hierarchy)
    worker.task(
        task_type="businessPerson.writeLeiEntities",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_write_lei_entities)
    # enrichGlobalPersons.bpmn tasks (R/PT168H)
    worker.task(
        task_type="businessPerson.selectGlobalTargetOrgs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_select_global_target_orgs)
    worker.task(
        task_type="businessPerson.discoverGlobalExecs",
        single_value=False,
        timeout_ms=timeout_ms * 3,
    )(task_business_person_discover_global_execs)
    worker.task(
        task_type="businessPerson.writeGlobalExecs",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_business_person_write_global_execs)
