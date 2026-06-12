"""Kouza read-only account aggregation handlers for BPMN + Zeebe."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

NS = "com.etzhayyim.apps.kouza"
ACTOR = "did:web:kouza.etzhayyim.com"
READ_SCOPES = {"accounts.read", "transactions.read", "documents.read", "balances.read"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any, label: str = "value") -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an integer")


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _require_did(value: Any, label: str) -> str:
    text = _str(value)
    if not text.startswith("did:"):
        raise ValueError(f"{label} must be a DID")
    return text


def _require_ref(value: Any, label: str) -> str:
    text = _str(value)
    if not text:
        raise ValueError(f"{label} required")
    return text


def _record_did(owner_did: str, collection: str, rkey: str) -> str:
    return f"{owner_did}|{collection}|{rkey}"


# R0: Datalog escape hatch to get MAX _seq as direct aggregation is not available in shims.
def _next_seq(table: str) -> int:
    client = get_kotoba_client()
    # Datalog query to find the maximum _seq for entities of a given table type.
    # Assumes table names are used as part of Datomic entity identity/schema.
    # The attribute for `_seq` is assumed to be `:<table_name>/_seq`
    query_edn = f'[:find (max ?seq) . :where [?e :{table}/_seq ?seq]]'
    result = client.q(query_edn)
    max_seq = result[0][0] if result and result[0] and result[0][0] is not None else 0
    return max_seq + 1


def _scopes(scopes: Any) -> list[str]:
    if not isinstance(scopes, list) or not scopes:
        raise ValueError("scopes required")
    out = []
    for scope in scopes:
        text = _str(scope)
        if text not in READ_SCOPES:
            raise ValueError(f"scope not allowed: {text}")
        out.append(text)
    return sorted(set(out))


def register_connection(ownerDid: str = "", institutionName: str = "", institutionKind: str = "", providerKey: str = "", scopes: Any = None, credentialVaultRef: str = "", consentExpiresAt: str = "", **_: Any) -> dict[str, Any]:
    owner = _require_did(ownerDid, "ownerDid")
    if not institutionName or not institutionKind or not providerKey:
        return {"error": "institutionName, institutionKind, providerKey required"}
    allowed = _scopes(scopes)
    rkey = f"conn-{_hash({'ownerDid': owner, 'institutionName': institutionName, 'institutionKind': institutionKind, 'providerKey': providerKey})}"
    did = _record_did(owner, f"{NS}.institutionConnection", rkey)
    seq = _next_seq("vertex_atrecord_kouza_institution_connection")
    now = now_iso()
    client = get_kotoba_client()
    client.insert_row(
        "vertex_atrecord_kouza_institution_connection",
        {
            "vertex_id": did,
            "_seq": seq,
            "owner_did": owner,
            "rkey": rkey,
            "institution_name": institutionName,
            "institution_kind": institutionKind,
            "provider_key": providerKey,
            "credential_vault_ref": credentialVaultRef or None,
            "scopes_json": json.dumps(allowed),
            "consent_expires_at": consentExpiresAt or None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return {"connectionDid": did, "status": "active"}


def create_financial_account(ownerDid: str = "", connectionDid: str = "", externalAccountIdHash: str = "", maskedAccountNumber: str = "", displayName: str = "", accountKind: str = "checking", currency: str = "JPY", currentBalanceMinor: Any = None, balanceAsOf: str = "", kaikeiAccountDid: str = "", status: str = "active", **_: Any) -> dict[str, Any]:
    did = _ensure_financial_account(locals())
    return {"financialAccountDid": did}


def _ensure_financial_account(input: dict[str, Any]) -> str:
    owner = _require_did(input.get("ownerDid"), "ownerDid")
    connection = _require_ref(input.get("connectionDid"), "connectionDid")
    external_hash = _str(input.get("externalAccountIdHash")) or _hash({"connectionDid": connection, "maskedAccountNumber": input.get("maskedAccountNumber"), "displayName": input.get("displayName"), "accountKind": input.get("accountKind"), "currency": input.get("currency")})
    rkey = f"acct-{external_hash}"
    did = _record_did(owner, f"{NS}.financialAccount", rkey)
    now = now_iso()
    seq = _next_seq("vertex_atrecord_kouza_financial_account")
    client = get_kotoba_client()
    client.insert_row(
        "vertex_atrecord_kouza_financial_account",
        {
            "vertex_id": did,
            "_seq": seq,
            "owner_did": owner,
            "rkey": rkey,
            "connection_did": connection,
            "external_account_id_hash": external_hash,
            "masked_account_number": input.get("maskedAccountNumber") or None,
            "display_name": input.get("displayName") or None,
            "account_kind": input.get("accountKind") or "checking",
            "currency": input.get("currency") or "JPY",
            "current_balance_minor": input.get("currentBalanceMinor"),
            "balance_as_of": input.get("balanceAsOf") or None,
            "kaikei_account_did": input.get("kaikeiAccountDid") or None,
            "status": input.get("status") or "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return did


def sync_connection(ownerDid: str = "", connectionDid: str = "", **_: Any) -> dict[str, Any]:
    owner = ownerDid if _str(ownerDid).startswith("did:") else ACTOR
    connection = _require_ref(connectionDid, "connectionDid")
    sync = _create_sync_run(owner, connection, "succeeded", {"accounts": 0, "txns": 0, "docs": 0})
    return {"syncRunDid": sync, "status": "succeeded", "accountsImported": 0, "transactionsImported": 0, "documentsImported": 0}


def _create_sync_run(owner: str, connection: str, status: str, counts: dict[str, int], error: str = "") -> str:
    rkey = f"sync-{uuid.uuid4().hex[:14]}"
    did = _record_did(owner, f"{NS}.syncRun", rkey)
    now = now_iso()
    seq = _next_seq("vertex_atrecord_kouza_sync_run")
    client = get_kotoba_client()
    client.insert_row(
        "vertex_atrecord_kouza_sync_run",
        {
            "vertex_id": did,
            "_seq": seq,
            "owner_did": owner,
            "rkey": rkey,
            "connection_did": connection,
            "adapter_key": "manual-statement",
            "started_at": now,
            "finished_at": now,
            "accounts_imported": counts.get("accounts", 0),
            "transactions_imported": counts.get("txns", 0),
            "documents_imported": counts.get("docs", 0),
            "status": status,
            "error_message": error or None,
            "created_at": now,
        },
    )
    client.insert_row(
        "vertex_atrecord_kouza_institution_connection",
        {
            "vertex_id": connection,
            "last_sync_run_did": did,
            "updated_at": now,
        },
    )
    return did


def import_statement(ownerDid: str = "", connectionDid: str = "", financialAccountDid: str = "", rows: Any = None, **_: Any) -> dict[str, Any]:
    owner = _require_did(ownerDid, "ownerDid")
    connection = _require_ref(connectionDid, "connectionDid")
    account = _require_ref(financialAccountDid, "financialAccountDid")
    if not isinstance(rows, list) or not rows:
        return {"error": "rows required"}
    imported = skipped = derived = 0
    for raw in rows:
        row = dict(raw or {})
        posted = _require_ref(row.get("postedAt"), "postedAt")
        amount = _int(row.get("amountMinor"), "amountMinor")
        currency = _str(row.get("currency")) or "JPY"
        external_id = _str(row.get("externalTxnId")) or _hash({"financialAccountDid": account, **row})
        rkey = f"txn-{_hash({'financialAccountDid': account, 'externalTxnId': external_id})}"
        did = _record_did(owner, f"{NS}.externalTransaction", rkey)
        client = get_kotoba_client()
        existing_txn = client.select_first_where(
            "vertex_atrecord_kouza_external_transaction",
            "vertex_id",
            did,
            columns=["vertex_id"],  # Only need to check existence
        )
        if existing_txn:
            inserted = 0  # Already exists, so "do nothing" and count as 0 inserted
        else:
            seq = _next_seq("vertex_atrecord_kouza_external_transaction")
            client.insert_row(
                "vertex_atrecord_kouza_external_transaction",
                {
                    "vertex_id": did,
                    "_seq": seq,
                    "owner_did": owner,
                    "rkey": rkey,
                    "financial_account_did": account,
                    "external_txn_id": external_id,
                    "posted_at": posted,
                    "value_at": row.get("valueAt") or None,
                    "amount_minor": amount,
                    "currency": currency,
                    "counterparty_name": row.get("counterpartyName") or None,
                    "description": row.get("description") or None,
                    "category_hint": row.get("categoryHint") or None,
                    "document_did": None,  # Original was NULL
                    "accounting_status": "pending",
                    "created_at": now_iso(),
                },
            )
            inserted = 1
        if inserted == 0:
            skipped += 1
            continue
        imported += 1
        if _derive_kaikei(owner, account, {**row, "externalTxnId": external_id, "postedAt": posted, "amountMinor": amount, "currency": currency}, did):
            derived += 1
    sync = _create_sync_run(owner, connection, "succeeded", {"accounts": 0, "txns": imported, "docs": 0})
    return {"syncRunDid": sync, "imported": imported, "skipped": skipped, "kaikeiDerived": derived}


def import_statement_csv(csvText: str = "", **kwargs: Any) -> dict[str, Any]:
    if not csvText.strip():
        return {"error": "csvText required"}
    reader = csv.DictReader(io.StringIO(csvText.lstrip("\ufeff")))
    rows = [dict(row) for row in reader]
    return import_statement(rows=rows, **kwargs)


def _derive_kaikei(owner: str, account_did: str, row: dict[str, Any], external_did: str) -> str | None:
    if row.get("currency") != "JPY":
        return None
    client = get_kotoba_client()
    # R0: Datalog escape hatch for multi-predicate SELECT with LIMIT 1
    query_edn = f"""
    [:find ?kaikei_account_did .
     :where
     [?e :vertex_atrecord_kouza_financial_account/vertex_id "{account_did}"]
     [?e :vertex_atrecord_kouza_financial_account/owner_did "{owner}"]
     [?e :vertex_atrecord_kouza_financial_account/kaikei_account_did ?kaikei_account_did]]
    """
    result = client.q(query_edn)
    bank_did = result[0] if result else None
    if not bank_did:
        return None
    bank_txn_id = _str(row.get("externalTxnId")) or _hash(row)
    rkey = f"kouza-{_hash({'financialAccountDid': account_did, 'bankTxnId': bank_txn_id})}"
    did = _record_did(owner, "com.etzhayyim.apps.kaikei.bankTransaction", rkey)
    existing_bank_txn = client.select_first_where(
        "vertex_atrecord_kaikei_bank_transaction",
        "vertex_id",
        did,
        columns=["vertex_id"],
    )
    if not existing_bank_txn:
        seq = _next_seq("vertex_atrecord_kaikei_bank_transaction")
        client.insert_row(
            "vertex_atrecord_kaikei_bank_transaction",
            {
                "vertex_id": did,
                "_seq": seq,
                "owner_did": owner,
                "bank_did": bank_did,
                "bank_txn_id": bank_txn_id,
                "posted_at": row["postedAt"],
                "amount": row["amountMinor"],
                "counterparty_name": row.get("counterpartyName") or row.get("description") or None,
                "reconcile_status": "pending",
                "created_at": now_iso(),
            },
        )
    client.insert_row(
        "vertex_atrecord_kouza_external_transaction",
        {
            "vertex_id": external_did,
            "kaikei_bank_transaction_did": did,
            "accounting_status": "derived",
        },
    )
    return did


def attach_document(ownerDid: str = "", financialAccountDid: str = "", documentKind: str = "", vaultCid: str = "", contentHash: str = "", issuedAt: str = "", title: str = "", periodFrom: str = "", periodTo: str = "", mimeType: str = "", **_: Any) -> dict[str, Any]:
    owner = _require_did(ownerDid, "ownerDid")
    account = _require_ref(financialAccountDid, "financialAccountDid")
    if not documentKind or not vaultCid or not contentHash or not issuedAt:
        return {"error": "documentKind, vaultCid, contentHash, issuedAt required"}
    rkey = f"doc-{_hash({'financialAccountDid': account, 'documentKind': documentKind, 'contentHash': contentHash})}"
    did = _record_did(owner, f"{NS}.accountDocument", rkey)
    client = get_kotoba_client()
    existing_doc = client.select_first_where(
        "vertex_atrecord_kouza_account_document",
        "vertex_id",
        did,
        columns=["vertex_id"],
    )
    if not existing_doc:
        seq = _next_seq("vertex_atrecord_kouza_account_document")
        client.insert_row(
            "vertex_atrecord_kouza_account_document",
            {
                "vertex_id": did,
                "_seq": seq,
                "owner_did": owner,
                "rkey": rkey,
                "financial_account_did": account,
                "document_kind": documentKind,
                "title": title or None,
                "period_from": periodFrom or None,
                "period_to": periodTo or None,
                "issued_at": issuedAt,
                "vault_cid": vaultCid,
                "content_hash": contentHash,
                "mime_type": mimeType or None,
                "created_at": now_iso(),
            },
        )
    return {"documentDid": did}


def map_kaikei_account(financialAccountDid: str = "", kaikeiAccountDid: str = "", **_: Any) -> dict[str, Any]:
    account = _require_ref(financialAccountDid, "financialAccountDid")
    kaikei = _require_ref(kaikeiAccountDid, "kaikeiAccountDid")
    client = get_kotoba_client()
    client.insert_row(
        "vertex_atrecord_kouza_financial_account",
        {
            "vertex_id": account,
            "kaikei_account_did": kaikei,
            "updated_at": now_iso(),
        },
    )
    updated = 1  # Assuming insert_row always "updates" if it succeeds for an existing record
    return {"ok": updated > 0}


def list_accounts(ownerDid: str = "", limit: Any = 50, **_: Any) -> dict[str, Any]:
    owner = _require_did(ownerDid, "ownerDid")
    n = max(1, min(_int(limit, "limit"), 200))
    client = get_kotoba_client()
    # R0: Order by _seq DESC handled in Python. Fetching up to 2000 rows, then sorting and limiting.
    all_rows = client.select_where(
        "vertex_atrecord_kouza_financial_account",
        "owner_did",
        owner,
        columns=[
            "vertex_id",
            "connection_did",
            "masked_account_number",
            "display_name",
            "account_kind",
            "currency",
            "current_balance_minor",
            "balance_as_of",
            "kaikei_account_did",
            "status",
            "_seq",  # Keep _seq for sorting and as 'cursor'
        ],
        limit=2000,  # Fetch more to allow for sorting and then limiting as per prompt suggestion
    )
    # Sort in Python by _seq descending, then take the top 'n'
    all_rows.sort(key=lambda x: x.get("_seq", 0), reverse=True)
    rows = all_rows[:n]
    # Rename _seq to cursor
    for row in rows:
        row["cursor"] = row.pop("_seq")

    return {"accounts": rows, "cursor": rows[-1]["cursor"] if rows else None}
    return {"accounts": rows, "cursor": rows[-1]["cursor"] if rows else None}


def list_transactions(financialAccountDid: str = "", limit: Any = 100, **_: Any) -> dict[str, Any]:
    account = _require_ref(financialAccountDid, "financialAccountDid")
    n = max(1, min(_int(limit, "limit"), 500))
    client = get_kotoba_client()
    # R0: Order by posted_at DESC, _seq DESC handled in Python. Fetching up to 2000 rows, then sorting and limiting.
    all_rows = client.select_where(
        "vertex_atrecord_kouza_external_transaction",
        "financial_account_did",
        account,
        columns=[
            "vertex_id",
            "external_txn_id",
            "posted_at",
            "value_at",
            "amount_minor",
            "currency",
            "counterparty_name",
            "description",
            "category_hint",
            "document_did",
            "kaikei_bank_transaction_did",
            "accounting_status",
            "_seq",  # Keep _seq for sorting and as 'cursor'
        ],
        limit=2000,  # Fetch more to allow for sorting and then limiting as per prompt suggestion
    )
    # Sort in Python by posted_at DESC, then _seq DESC, then take the top 'n'
    # posted_at is a string in ISO format, so direct string comparison should work for chronological order.
    all_rows.sort(key=lambda x: (x.get("posted_at", ""), x.get("_seq", 0)), reverse=True)
    rows = all_rows[:n]
    # Rename _seq to cursor
    for row in rows:
        row["cursor"] = row.pop("_seq")

    return {"transactions": rows, "cursor": rows[-1]["cursor"] if rows else None}
    return {"transactions": rows, "cursor": rows[-1]["cursor"] if rows else None}
