//! R3d enforcement — cross-audit a custodian-signed grant against the access
//! receipt log: a signed release with no matching `key:requestShare` receipt
//! within a time window is an UNRECEIPTED RELEASE, the slashable offence.
//!
//! Pure logic only (no I/O): the server layer resolves the custodian DID's
//! Ed25519 key, fetches receipts, and emits/persists the warrant. Keeping the
//! match rule here makes it independently testable and reusable by any node
//! doing the cross-audit (the requester, a watchdog, the custodian itself).

use crate::protocol::GrantedShare;

/// The slice of an access receipt this audit needs. Built by the caller from
/// the audit graph's datoms (`access/graph`, `access/accessor-did`,
/// `access/operation`, `access/ts-unix`).
#[derive(Debug, Clone)]
pub struct ReceiptRecord {
    pub graph_mb: String,
    pub operation: String,
    pub ts_unix: u64,
}

/// Why a grant is (not) covered by a receipt.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AuditVerdict {
    /// A matching `key:requestShare` receipt exists within the window.
    Receipted,
    /// No matching receipt — the custodian released without logging (slashable).
    UnreceiptedRelease,
}

/// Does the receipt log cover this grant? A match is a `key:requestShare`
/// receipt for the same graph whose timestamp is within `window_secs` of the
/// grant's `ts_unix` (clock skew + the receipt's async batch-flush delay). The
/// grant's own timestamp anchors the window, and the grant is non-repudiable
/// once `verify_grant_sig` has passed — so a clear verdict here is actionable.
pub fn audit_grant(
    grant: &GrantedShare,
    receipts: &[ReceiptRecord],
    window_secs: u64,
) -> AuditVerdict {
    let covered = receipts.iter().any(|r| {
        r.operation == "key:requestShare"
            && r.graph_mb == grant.graph_cid_mb
            && r.ts_unix.abs_diff(grant.ts_unix) <= window_secs
    });
    if covered {
        AuditVerdict::Receipted
    } else {
        AuditVerdict::UnreceiptedRelease
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn grant(graph: &str, ts: u64) -> GrantedShare {
        GrantedShare {
            custodian_did: "did:key:zCustodian".into(),
            index: 1,
            threshold: 2,
            epoch: 1,
            deal_id: vec![1, 2, 3],
            graph_cid_mb: graph.into(),
            requester_x25519_pk: vec![9u8; 32],
            ts_unix: ts,
            sealed_for_requester: vec![0u8; 60],
            grant_sig: None,
        }
    }

    fn receipt(graph: &str, op: &str, ts: u64) -> ReceiptRecord {
        ReceiptRecord {
            graph_mb: graph.into(),
            operation: op.into(),
            ts_unix: ts,
        }
    }

    #[test]
    fn matching_receipt_within_window_is_receipted() {
        let g = grant("bGraph", 1000);
        let receipts = vec![receipt("bGraph", "key:requestShare", 1003)];
        assert_eq!(audit_grant(&g, &receipts, 5), AuditVerdict::Receipted);
    }

    #[test]
    fn no_receipt_is_an_unreceipted_release() {
        let g = grant("bGraph", 1000);
        assert_eq!(
            audit_grant(&g, &[], 5),
            AuditVerdict::UnreceiptedRelease
        );
    }

    #[test]
    fn receipt_outside_window_does_not_cover() {
        let g = grant("bGraph", 1000);
        let receipts = vec![receipt("bGraph", "key:requestShare", 2000)];
        assert_eq!(
            audit_grant(&g, &receipts, 5),
            AuditVerdict::UnreceiptedRelease
        );
    }

    #[test]
    fn receipt_for_a_different_graph_does_not_cover() {
        let g = grant("bGraph", 1000);
        let receipts = vec![receipt("bOther", "key:requestShare", 1000)];
        assert_eq!(
            audit_grant(&g, &receipts, 5),
            AuditVerdict::UnreceiptedRelease
        );
    }

    #[test]
    fn a_read_receipt_does_not_count_as_a_key_release_receipt() {
        // Only key:requestShare receipts cover a share release.
        let g = grant("bGraph", 1000);
        let receipts = vec![receipt("bGraph", "datom:q", 1000)];
        assert_eq!(
            audit_grant(&g, &receipts, 5),
            AuditVerdict::UnreceiptedRelease
        );
    }
}
