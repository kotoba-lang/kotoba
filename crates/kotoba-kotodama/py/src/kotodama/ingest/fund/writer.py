from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

from .ids import FUND_DID, edge_id, fund_vertex_id, manager_vertex_id, slug
from .types import NormalizedFund, NormalizedFundManager


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def manager_row(manager: NormalizedFundManager) -> dict[str, Any]:
    vid = manager_vertex_id(manager.manager_id)
    return {
        "vertex_id": vid,
        "created_date": today(),
        "sensitivity_ord": 1,
        "owner_did": FUND_DID,
        "rkey": slug(manager.manager_id),
        "repo": FUND_DID,
        "did": f"{FUND_DID}:manager:{slug(manager.manager_id)}",
        "manager_id": manager.manager_id,
        "manager_name": manager.manager_name,
        "manager_type": manager.manager_type,
        "jurisdiction": manager.jurisdiction or None,
        "domicile": manager.domicile or None,
        "regulator": manager.regulator or None,
        "legal_entity_did": manager.legal_entity_did or None,
        "aum_amount": manager.aum_amount,
        "currency": manager.currency or None,
        "website": manager.website or None,
        "source_url": manager.source_url or None,
        "source_license": manager.source_license or None,
        "confidence": manager.confidence,
        "notes": manager.notes or None,
    }


def fund_row(fund: NormalizedFund) -> dict[str, Any]:
    vid = fund_vertex_id(fund.fund_id)
    manager_vid = manager_vertex_id(fund.manager_id)
    return {
        "vertex_id": vid,
        "created_date": today(),
        "sensitivity_ord": 1,
        "owner_did": FUND_DID,
        "rkey": slug(fund.fund_id),
        "repo": FUND_DID,
        "did": f"{FUND_DID}:fund:{slug(fund.fund_id)}",
        "fund_id": fund.fund_id,
        "name": fund.name,
        "fund_kind": fund.fund_kind,
        "strategy": fund.strategy or None,
        "status": fund.status or None,
        "jurisdiction": fund.jurisdiction or None,
        "domicile": fund.domicile or None,
        "vintage_year": fund.vintage_year,
        "manager_name": fund.manager_name or None,
        "manager_did": manager_vid,
        "currency": fund.currency or None,
        "aum_amount": fund.aum_amount,
        "committed_capital": fund.committed_capital,
        "called_capital": fund.called_capital,
        "distributed_capital": fund.distributed_capital,
        "dry_powder": fund.dry_powder,
        "target_size": fund.target_size,
        "source_url": fund.source_url or None,
        "source_license": fund.source_license or None,
        "confidence": fund.confidence,
        "notes": fund.notes or None,
    }


def managed_by_edge(fund: NormalizedFund) -> dict[str, Any]:
    src = fund_vertex_id(fund.fund_id)
    dst = manager_vertex_id(fund.manager_id)
    return {
        "edge_id": edge_id("fund-managed-by", src, dst, fund.source_url),
        "src_vid": src,
        "dst_vid": dst,
        "relationship": "managed_by",
        "role": "investment_adviser",
        "source_url": fund.source_url or None,
        "source_license": fund.source_license or None,
        "confidence": fund.confidence,
        "created_at": now_iso(),
    }


def graph_rows(
    managers: list[NormalizedFundManager],
    funds: list[NormalizedFund],
) -> dict[str, list[dict[str, Any]]]:
    return {
        "vertex_fund_manager": [manager_row(manager) for manager in managers],
        "vertex_fund": [fund_row(fund) for fund in funds],
        "edge_fund_managed_by": [managed_by_edge(fund) for fund in funds],
    }





def upsert_graph_rows(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Idempotently write prepared fund graph rows and verify visibility using kotoba Datom log."""
    kotoba_client = get_kotoba_client()
    table_pk = {
        "vertex_fund_manager": "vertex_id",
        "vertex_fund": "vertex_id",
        "edge_fund_managed_by": "edge_id",
    }
    prepared = sum(len(items) for items in rows.values())
    visibility: dict[str, dict[str, int]] = {}

    for table, items in rows.items():
        for item in items:
            # insert_row handles both insert and update (upsert) based on the identity column
            kotoba_client.insert_row(table, item)

    for table, items in rows.items():
        pk_col = table_pk[table]
        ids = [str(item[pk_col]) for item in items if item.get(pk_col)]
        visible = 0
        if ids:
            # R0: Using Datalog for multi-ID count, as shims do not support 'IN' clauses directly.
            # Datalog's `contains?` with a set literal allows checking for multiple IDs efficiently.
            id_literals = " ".join(f'"{_id}"' for _id in ids)
            datalog_query = f"""
            [:find (count ?e) .
             :where
             [?e :{table}/{pk_col} ?pk]
             [(contains? #{{{id_literals}}} ?pk)]]
            """
            result = kotoba_client.q(datalog_query)
            visible = int(result[0]) if result else 0
        visibility[table] = {"expected": len(ids), "visible": visible}

    visible_total = sum(v["visible"] for v in visibility.values())
    return {
        "ok": visible_total >= prepared,
        "recordsPrepared": prepared,
        "recordsInserted": 0,  # kotoba_datomic's insert_row does not return specific inserted/updated counts
        "recordsUpdated": 0,  # kotoba_datomic's insert_row does not return specific inserted/updated counts
        "recordsVisible": visible_total,
        "visibility": visibility,
    }
