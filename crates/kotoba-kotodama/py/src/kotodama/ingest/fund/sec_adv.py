from __future__ import annotations

import csv
import io
from typing import Any

from .ids import clean, fund_id, manager_id
from .types import FundSourceConfig, NormalizedFund, NormalizedFundManager

SEC_ADV_SOURCE_ID = "sec-adv"
SEC_ADV_LICENSE = "sec-public"


def plan_sec_adv_shards(mode: str = "delta", limit: int = 10) -> list[FundSourceConfig]:
    """Return deterministic pilot shards without doing network work."""
    count = max(1, min(int(limit or 1), 50))
    return [
        FundSourceConfig(
            source_id=SEC_ADV_SOURCE_ID,
            source_kind="sec-form-adv",
            shard_key=f"adv-{i:02d}",
            source_url="https://www.sec.gov/help/foiadocsinvafoiahtm.html",
            source_license=SEC_ADV_LICENSE,
            mode=mode or "delta",
        )
        for i in range(count)
    ]


def _first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = clean(row.get(key))
        if value:
            return value
    return ""


def _float_or_none(value: Any) -> float | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_sec_adv_rows(
    rows: list[dict[str, Any]],
    *,
    source_url: str = "",
    source_license: str = SEC_ADV_LICENSE,
) -> tuple[list[NormalizedFundManager], list[NormalizedFund]]:
    managers_by_id: dict[str, NormalizedFundManager] = {}
    funds: list[NormalizedFund] = []

    for row in rows:
        name = _first(row, "Primary Business Name", "Legal Name", "1A", "adviser_name", "name")
        if not name:
            continue
        cik = _first(row, "CIK", "cik")
        crd = _first(row, "CRD Number", "crd")
        lei = _first(row, "LEI", "lei")
        mid = manager_id(source_id=SEC_ADV_SOURCE_ID, cik=cik, crd=crd, lei=lei, name=name)
        manager = NormalizedFundManager(
            manager_id=mid,
            manager_name=name,
            manager_type="investment_adviser",
            jurisdiction=_first(row, "State", "Country", "jurisdiction"),
            regulator="SEC",
            aum_amount=_float_or_none(_first(row, "Regulatory Assets Under Management", "aum")),
            currency="USD",
            website=_first(row, "Website Address", "website"),
            source_url=source_url,
            source_license=source_license,
            confidence=0.75,
        )
        managers_by_id[mid] = manager

        private_fund_name = _first(row, "Private Fund Name", "fund_name")
        if private_fund_name:
            fid = fund_id(
                source_id=SEC_ADV_SOURCE_ID,
                adviser_id=mid,
                native_fund_id=_first(row, "Private Fund ID", "fund_id"),
                name=private_fund_name,
            )
            funds.append(
                NormalizedFund(
                    fund_id=fid,
                    name=private_fund_name,
                    manager_id=mid,
                    manager_name=name,
                    fund_kind="private_fund",
                    status=_first(row, "Fund Status", "status") or "unknown",
                    jurisdiction=manager.jurisdiction,
                    currency="USD",
                    aum_amount=_float_or_none(_first(row, "Gross Asset Value", "fund_aum")),
                    source_url=source_url,
                    source_license=source_license,
                    confidence=0.7,
                )
            )

    return list(managers_by_id.values()), funds


def normalize_sec_adv_csv(
    csv_text: str,
    *,
    source_url: str = "",
    source_license: str = SEC_ADV_LICENSE,
) -> tuple[list[NormalizedFundManager], list[NormalizedFund]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    return normalize_sec_adv_rows(
        [dict(row) for row in reader],
        source_url=source_url,
        source_license=source_license,
    )
