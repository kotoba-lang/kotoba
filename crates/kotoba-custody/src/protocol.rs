//! R3b custodian protocol core (`/kotoba/key/1`), transport-agnostic.
//!
//! The wire types and the one invariant that makes the whole X-Road design
//! hold: **a custodian releases its share ONLY after authorization succeeds**,
//! and authorization is exactly where the CACAO/purpose check happens and the
//! receipt is written. "no receipt, no key" is enforced here by control flow —
//! `handle_key_share_request` calls the injected `authorize` closure first and
//! returns `Denied` (with no share material) on any error.
//!
//! Authorization itself (CACAO chain verification, purpose policy, nonce
//! replay, receipt commit) lives in the server layer and is injected as a
//! closure, so this crate stays a leaf primitive (no kotoba-auth /
//! kotoba-datomic dependency, same seam discipline as the R2c import check).
//!
//! The actual libp2p request-response Behaviour (PeerID = did:key at the Noise
//! layer, one `KeyShareRequest`/`KeyShareResponse` round-trip per custodian)
//! is a thin shell over these types — deferred like the kotoba-turn
//! socket-free core (#102).

use serde::{Deserialize, Serialize};
use thiserror::Error;
use x25519_dalek::{PublicKey, StaticSecret};
use zeroize::Zeroizing;

use crate::shares::{open_share, CustodianShare};

#[derive(Debug, Error)]
pub enum ProtocolError {
    #[error("authorization denied: {0}")]
    Denied(String),
    #[error("share open: {0}")]
    ShareOpen(#[from] crate::shares::CustodyError),
    #[error("hpke: {0}")]
    Hpke(String),
    #[error("requester pubkey: not 32 bytes")]
    BadRequesterKey,
    #[error("combine: need {need} granted shares, got {got}")]
    NotEnough { need: u8, got: usize },
}

/// A read request a client sends to each custodian for one graph's key.
/// Carries the requester's EPHEMERAL X25519 pubkey: the custodian re-wraps the
/// share to it, so a share in flight is readable only by this requester (the
/// at-rest share was wrapped to the custodian; this hop re-targets it).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeyShareRequest {
    /// Multibase CID of the graph whose key is being requested.
    pub graph_cid_mb: String,
    /// CACAO delegation chain (base64), if the graph is Private.
    pub cacao_b64: Option<String>,
    /// Declared purpose (`x-kotoba-purpose` equivalent).
    pub purpose: Option<String>,
    /// Anti-replay nonce (the custodian's authorize step registers it).
    pub nonce: String,
    /// Requester's X25519 pubkey to re-wrap the share to.
    #[serde(with = "serde_bytes")]
    pub requester_x25519_pk: Vec<u8>,
}

/// One custodian's grant: the share re-wrapped to the requester.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GrantedShare {
    pub custodian_did: String,
    pub index: u8,
    pub threshold: u8,
    /// HPKE envelope of the share bytes, sealed to the requester's pubkey.
    #[serde(with = "serde_bytes")]
    pub sealed_for_requester: Vec<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum KeyShareResponse {
    Granted(GrantedShare),
    Denied { reason: String },
}

/// Custodian-side handler. `authorize` is the server-injected gate that
/// verifies CACAO + purpose + nonce AND writes the access receipt; it MUST
/// return `Err(reason)` to refuse. Only on `Ok` does the custodian open its
/// own share and re-wrap it to the requester — so no authorized-but-unlogged
/// release is possible through this path.
pub fn handle_key_share_request(
    req: &KeyShareRequest,
    my_share: &CustodianShare,
    my_x25519_sk: &StaticSecret,
    authorize: &dyn Fn(&KeyShareRequest) -> Result<(), String>,
) -> KeyShareResponse {
    // 1. Authorize FIRST (receipt is written here). No share touched on failure.
    if let Err(reason) = authorize(req) {
        return KeyShareResponse::Denied { reason };
    }
    // 2. Open our at-rest share (HPKE to us + commitment check).
    let recovered = match open_share(my_share, my_x25519_sk) {
        Ok(r) => r,
        Err(e) => {
            return KeyShareResponse::Denied {
                reason: format!("custodian share open failed: {e}"),
            }
        }
    };
    // 3. Re-wrap the share plaintext to the requester's ephemeral pubkey.
    let pk_arr: [u8; 32] = match req.requester_x25519_pk.as_slice().try_into() {
        Ok(a) => a,
        Err(_) => {
            return KeyShareResponse::Denied {
                reason: "requester pubkey not 32 bytes".into(),
            }
        }
    };
    let requester_pk = PublicKey::from(pk_arr);
    match kotoba_crypto::hpke_seal(&requester_pk, &recovered.bytes) {
        Ok(sealed) => KeyShareResponse::Granted(GrantedShare {
            custodian_did: my_share.recipient_did.clone(),
            index: my_share.index,
            threshold: my_share.threshold,
            sealed_for_requester: sealed,
        }),
        Err(e) => KeyShareResponse::Denied {
            reason: format!("re-wrap failed: {e}"),
        },
    }
}

/// Requester-side: open `threshold` granted shares with the requester's
/// ephemeral X25519 secret and recombine them into the block key.
pub fn combine_granted(
    threshold: u8,
    grants: &[GrantedShare],
    requester_sk: &StaticSecret,
) -> Result<Zeroizing<[u8; crate::shares::KEY_LEN]>, ProtocolError> {
    if grants.len() < threshold as usize {
        return Err(ProtocolError::NotEnough {
            need: threshold,
            got: grants.len(),
        });
    }
    let mut recovered = Vec::with_capacity(grants.len());
    for g in grants {
        let bytes = kotoba_crypto::hpke_open(requester_sk, &g.sealed_for_requester)
            .map_err(|e| ProtocolError::Hpke(e.to_string()))?;
        recovered.push(crate::shares::RecoveredShare {
            recipient_did: g.custodian_did.clone(),
            bytes: Zeroizing::new(bytes.to_vec()),
        });
    }
    crate::shares::combine_key(threshold, &recovered).map_err(Into::into)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::shares::split_key;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn custodian(seed: u8) -> (String, StaticSecret, PublicKey) {
        let sk = StaticSecret::from([seed; 32]);
        let pk = PublicKey::from(&sk);
        (format!("did:key:zC{seed}"), sk, pk)
    }

    fn deal(key: &[u8; 32], t: u8, n: u8) -> (Vec<CustodianShare>, Vec<(String, StaticSecret, PublicKey)>) {
        let fleet: Vec<_> = (1..=n).map(custodian).collect();
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        (split_key(key, t, &pubs).unwrap(), fleet)
    }

    fn requester() -> (StaticSecret, [u8; 32]) {
        let sk = StaticSecret::from([0x99u8; 32]);
        let pk = PublicKey::from(&sk);
        (sk, *pk.as_bytes())
    }

    fn req(pk: [u8; 32]) -> KeyShareRequest {
        KeyShareRequest {
            graph_cid_mb: "btargetgraph".into(),
            cacao_b64: Some("fakecacao".into()),
            purpose: Some("billing-dispute".into()),
            nonce: "n-1".into(),
            requester_x25519_pk: pk.to_vec(),
        }
    }

    #[test]
    fn full_three_of_five_protocol_roundtrip() {
        let key = [55u8; 32];
        let (shares, fleet) = deal(&key, 3, 5);
        let (req_sk, req_pk) = requester();
        let allow = |_: &KeyShareRequest| Ok(());

        // Three custodians (0,2,4) each grant.
        let grants: Vec<GrantedShare> = [0usize, 2, 4]
            .iter()
            .map(|&i| {
                match handle_key_share_request(&req(req_pk), &shares[i], &fleet[i].1, &allow) {
                    KeyShareResponse::Granted(g) => g,
                    KeyShareResponse::Denied { reason } => panic!("denied: {reason}"),
                }
            })
            .collect();

        let recovered = combine_granted(3, &grants, &req_sk).unwrap();
        assert_eq!(*recovered, key, "client reconstructs the block key");
    }

    #[test]
    fn denial_releases_no_share_material() {
        let key = [56u8; 32];
        let (shares, fleet) = deal(&key, 2, 3);
        let (_, req_pk) = requester();
        let deny = |_: &KeyShareRequest| Err("no datom:read capability".to_string());
        let resp = handle_key_share_request(&req(req_pk), &shares[0], &fleet[0].1, &deny);
        match resp {
            KeyShareResponse::Denied { reason } => assert!(reason.contains("capability")),
            KeyShareResponse::Granted(_) => panic!("a denied request must yield NO share"),
        }
    }

    #[test]
    fn authorize_runs_before_any_share_access() {
        // The receipt-writing hook (authorize) must fire even when it ultimately
        // denies — proving "authorize before release" is control-flow-enforced.
        let key = [57u8; 32];
        let (shares, fleet) = deal(&key, 2, 3);
        let (_, req_pk) = requester();
        let calls = AtomicUsize::new(0);
        let gate = |_: &KeyShareRequest| {
            calls.fetch_add(1, Ordering::SeqCst);
            Err("deny after logging".to_string())
        };
        let _ = handle_key_share_request(&req(req_pk), &shares[0], &fleet[0].1, &gate);
        assert_eq!(calls.load(Ordering::SeqCst), 1, "authorize hook must run");
    }

    #[test]
    fn shares_in_flight_are_only_readable_by_the_requester() {
        // A granted share is sealed to the requester's pubkey: an eavesdropper
        // (or a different requester) with a different key cannot open it.
        let key = [58u8; 32];
        let (shares, fleet) = deal(&key, 2, 3);
        let (_, req_pk) = requester();
        let allow = |_: &KeyShareRequest| Ok(());
        let g = match handle_key_share_request(&req(req_pk), &shares[0], &fleet[0].1, &allow) {
            KeyShareResponse::Granted(g) => g,
            _ => panic!(),
        };
        let attacker_sk = StaticSecret::from([0x11u8; 32]);
        assert!(
            kotoba_crypto::hpke_open(&attacker_sk, &g.sealed_for_requester).is_err(),
            "only the requester key may open the in-flight share"
        );
    }

    #[test]
    fn fewer_than_threshold_grants_cannot_recombine() {
        let key = [59u8; 32];
        let (shares, fleet) = deal(&key, 3, 5);
        let (req_sk, req_pk) = requester();
        let allow = |_: &KeyShareRequest| Ok(());
        let grants: Vec<GrantedShare> = [0usize, 1]
            .iter()
            .map(|&i| match handle_key_share_request(&req(req_pk), &shares[i], &fleet[i].1, &allow) {
                KeyShareResponse::Granted(g) => g,
                _ => panic!(),
            })
            .collect();
        assert!(matches!(
            combine_granted(3, &grants, &req_sk),
            Err(ProtocolError::NotEnough { need: 3, got: 2 })
        ));
    }

    #[test]
    fn response_serde_roundtrip() {
        let key = [60u8; 32];
        let (shares, fleet) = deal(&key, 2, 2);
        let (_, req_pk) = requester();
        let allow = |_: &KeyShareRequest| Ok(());
        let resp = handle_key_share_request(&req(req_pk), &shares[0], &fleet[0].1, &allow);
        let bytes = serde_json::to_vec(&resp).unwrap();
        let back: KeyShareResponse = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(back, resp);
    }
}
