from __future__ import annotations

import hashlib
import re
from typing import Any

FUND_DID = "did:web:fund.etzhayyim.com"


def clean(value: Any) -> str:
    return str(value or "").strip()


def slug(value: Any, *, max_len: int = 180) -> str:
    text = clean(value).lower()
    out: list[str] = []
    for ch in text:
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            out.append(ch)
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    compact = "-".join(part for part in "".join(out).split("-") if part)
    return (compact[:max_len] or "unknown").strip("-") or "unknown"


def digest_slug(*parts: Any, size: int = 8) -> str:
    payload = "|".join(clean(part) for part in parts)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=size).hexdigest()


def cik_key(value: Any) -> str:
    digits = re.sub(r"\D+", "", clean(value))
    return digits.lstrip("0") or ""


def manager_id(
    *,
    source_id: str,
    cik: Any = "",
    crd: Any = "",
    lei: Any = "",
    name: Any = "",
) -> str:
    if lei:
        return f"lei-{slug(lei)}"
    if crd:
        return f"crd-{slug(crd)}"
    cik = cik_key(cik)
    if cik:
        return f"sec-cik-{cik}"
    return f"{slug(source_id)}-{digest_slug(name, size=8)}"


def fund_id(*, source_id: str, adviser_id: str, native_fund_id: Any = "", name: Any = "") -> str:
    if native_fund_id:
        return f"{slug(source_id)}-{slug(native_fund_id)}"
    return f"{slug(source_id)}-{slug(adviser_id)}-{digest_slug(name, size=8)}"


def manager_vertex_id(value: str) -> str:
    return f"at://{FUND_DID}/com.etzhayyim.apps.fund.manager/{slug(value)}"


def fund_vertex_id(value: str) -> str:
    return f"at://{FUND_DID}/com.etzhayyim.apps.fund.fund/{slug(value)}"


def investor_vertex_id(value: str) -> str:
    return f"at://{FUND_DID}/com.etzhayyim.apps.fund.investor/{slug(value)}"


def investee_vertex_id(value: str) -> str:
    return f"at://{FUND_DID}/com.etzhayyim.apps.fund.investee/{slug(value)}"


def edge_id(kind: str, src_vid: str, dst_vid: str, *parts: Any) -> str:
    return f"{slug(kind)}-{digest_slug(src_vid, dst_vid, *parts, size=10)}"
