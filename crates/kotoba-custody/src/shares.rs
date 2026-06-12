//! kotoba-custody — t-of-N key custody for the sealed cold tier
//! (ADR-sealed-cold-tier R3a).
//!
//! Splits the 32-byte block key (KOTOBA_BLOCK_KEY, the only path to reading
//! sealed blocks) into N Shamir shares, each HPKE-wrapped to one custodian's
//! X25519 key. Any t custodians can reconstruct the key; t−1 learn NOTHING
//! (information-theoretic, Shamir over GF(2^8) via the `sharks` crate — not
//! hand-rolled, per the R0 review note).
//!
//! This is the X-Road security-server decentralisation move: the single key
//! broker becomes "t-of-N custodians who don't collude", so 「ログを書かずに
//! 鍵を出す」 requires t conspirators, not one operator.
//!
//! R3a scope = the SHARE PLANE only: split / wrap / open / combine, with
//! per-share SHA-256 commitments so a corrupted or substituted share is
//! detected at open time (commitment verification, NOT yet Feldman VSS —
//! the curve-commitment upgrade is R3c, see the ADR). The network protocol
//! (`/kotoba/key/1`: CACAO + purpose + receipt per custodian before a share
//! is released) and MLS-epoch rotation are R3b/R3c.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use sharks::{Share, Sharks};
use thiserror::Error;
use x25519_dalek::{PublicKey, StaticSecret};
use zeroize::Zeroizing;

pub const KEY_LEN: usize = 32;

#[derive(Debug, Error)]
pub enum CustodyError {
    #[error("threshold must satisfy 1 < t <= n (got t={t}, n={n})")]
    BadThreshold { t: u8, n: usize },
    #[error("at most 255 custodians (got {0})")]
    TooManyCustodians(usize),
    #[error("hpke: {0}")]
    Hpke(String),
    #[error("share commitment mismatch for custodian {0} — corrupted or substituted share")]
    CommitmentMismatch(String),
    #[error("share decode: {0}")]
    ShareDecode(String),
    #[error("need {t} shares to combine, got {got}")]
    NotEnoughShares { t: u8, got: usize },
    #[error("combine failed: {0}")]
    Combine(String),
    #[error("combined secret has wrong length {0} (expected 32)")]
    BadSecretLen(usize),
    #[error(
        "shares come from different dealings (mixed epoch/custodian-set) — refusing to combine"
    )]
    MixedDealing,
}

/// One custodian's wrapped share. Safe to store/replicate anywhere: the share
/// bytes are HPKE-sealed to the custodian's X25519 key, and the cleartext
/// commitment binds what the custodian must eventually present.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CustodianShare {
    /// 1-based Shamir x-coordinate (sharks encodes it in the share itself;
    /// kept here for display/audit).
    pub index: u8,
    /// The custodian this share is wrapped for.
    pub recipient_did: String,
    /// HPKE envelope (`ephemeral_pk || nonce || AES-256-GCM`) of the share bytes.
    #[serde(with = "serde_bytes")]
    pub sealed_share: Vec<u8>,
    /// SHA-256 of the cleartext share bytes — verified at `open_share`, and
    /// usable by third parties to check a presented share without the key.
    pub commitment: [u8; 32],
    /// Threshold this share set was dealt with (every share carries it so a
    /// quorum knows when it is complete).
    pub threshold: u8,
    /// Rotation epoch (R3c). Bumped each time the key is re-dealt to a new
    /// custodian set; revocation granularity = epoch. `#[serde(default)]` so
    /// pre-R3c deposited shares decode as epoch 0.
    #[serde(default)]
    pub epoch: u64,
    /// Binds this share to ONE dealing: sha256(epoch || t || sorted recipient
    /// DIDs). Shares from different dealings have different deal_ids, so
    /// `combine_key` rejects a mixed-epoch quorum instead of silently
    /// reconstructing garbage (the R3a non-goal, now an explicit error).
    #[serde(default, with = "serde_bytes")]
    pub deal_id: Vec<u8>,
}

/// An opened (decrypted, commitment-checked) share, ready for `combine_key`.
pub struct RecoveredShare {
    pub recipient_did: String,
    pub bytes: Zeroizing<Vec<u8>>,
    /// The dealing this share belongs to (R3c) — `combine_key` requires all
    /// shares to agree, so a mixed-epoch quorum is rejected.
    pub deal_id: Vec<u8>,
}

fn share_commitment(bytes: &[u8]) -> [u8; 32] {
    let mut out = [0u8; 32];
    out.copy_from_slice(&Sha256::digest(bytes));
    out
}

/// Bind a dealing: sha256(epoch || threshold || sorted commitments). Including
/// the per-share SHA-256 commitments — which derive from the random Shamir
/// polynomial — makes the id distinct not only across epochs / custodian sets
/// but across SEPARATE re-deals of the same parameters (a fresh polynomial ⇒
/// fresh commitments ⇒ fresh deal_id). All shares of one dealing share it; a
/// custodian just stores the dealer-assigned value (it cannot recompute it
/// without the other commitments, which is fine — combine only needs equality).
fn compute_deal_id(epoch: u64, threshold: u8, commitments: &[[u8; 32]]) -> Vec<u8> {
    let mut sorted: Vec<[u8; 32]> = commitments.to_vec();
    sorted.sort_unstable();
    let mut h = Sha256::new();
    h.update(epoch.to_le_bytes());
    h.update([threshold]);
    for c in sorted {
        h.update(c);
    }
    h.finalize().to_vec()
}

/// Split `key` into one share per custodian at epoch 0 (compat wrapper).
pub fn split_key(
    key: &[u8; KEY_LEN],
    threshold: u8,
    custodians: &[(String, PublicKey)],
) -> Result<Vec<CustodianShare>, CustodyError> {
    split_key_epoch(key, threshold, custodians, 0)
}

/// Split `key` into one share per custodian for a given rotation `epoch` (R3c);
/// any `threshold` of them combine back to the key, fewer learn nothing.
/// Every share carries the `epoch` and a `deal_id` binding it to THIS dealing.
pub fn split_key_epoch(
    key: &[u8; KEY_LEN],
    threshold: u8,
    custodians: &[(String, PublicKey)],
    epoch: u64,
) -> Result<Vec<CustodianShare>, CustodyError> {
    let n = custodians.len();
    if n > 255 {
        return Err(CustodyError::TooManyCustodians(n));
    }
    if threshold < 2 || (threshold as usize) > n {
        return Err(CustodyError::BadThreshold { t: threshold, n });
    }
    let sharks = Sharks(threshold);
    // Pass 1: deal + seal + commit; collect commitments to bind the deal_id.
    struct Dealt {
        index: u8,
        did: String,
        sealed: Vec<u8>,
        commitment: [u8; 32],
    }
    let mut dealt = Vec::with_capacity(n);
    for (i, ((did, pk), share)) in custodians.iter().zip(sharks.dealer(key)).enumerate() {
        let share_bytes: Vec<u8> = (&share).into();
        let sealed = kotoba_crypto::hpke_seal(pk, &share_bytes)
            .map_err(|e| CustodyError::Hpke(e.to_string()))?;
        dealt.push(Dealt {
            index: (i + 1) as u8,
            did: did.clone(),
            sealed,
            commitment: share_commitment(&share_bytes),
        });
    }
    let commitments: Vec<[u8; 32]> = dealt.iter().map(|d| d.commitment).collect();
    let deal_id = compute_deal_id(epoch, threshold, &commitments);
    // Pass 2: stamp every share with the shared deal_id.
    let out = dealt
        .into_iter()
        .map(|d| CustodianShare {
            index: d.index,
            recipient_did: d.did,
            sealed_share: d.sealed,
            commitment: d.commitment,
            threshold,
            epoch,
            deal_id: deal_id.clone(),
        })
        .collect();
    Ok(out)
}

/// Re-deal `key` to a NEW custodian set at `new_epoch` (R3c rotation). The
/// returned shares carry a fresh `deal_id`, so old-epoch shares can no longer
/// be combined with these — revocation granularity = epoch. `new_epoch` MUST
/// strictly exceed the current epoch (callers enforce monotonicity).
pub fn rotate_key(
    key: &[u8; KEY_LEN],
    threshold: u8,
    new_custodians: &[(String, PublicKey)],
    new_epoch: u64,
) -> Result<Vec<CustodianShare>, CustodyError> {
    split_key_epoch(key, threshold, new_custodians, new_epoch)
}

/// Decrypt and commitment-check one custodian's share with their X25519 secret.
pub fn open_share(
    share: &CustodianShare,
    recipient_sk: &StaticSecret,
) -> Result<RecoveredShare, CustodyError> {
    let bytes = kotoba_crypto::hpke_open(recipient_sk, &share.sealed_share)
        .map_err(|e| CustodyError::Hpke(e.to_string()))?;
    if share_commitment(&bytes) != share.commitment {
        return Err(CustodyError::CommitmentMismatch(
            share.recipient_did.clone(),
        ));
    }
    Ok(RecoveredShare {
        recipient_did: share.recipient_did.clone(),
        bytes: Zeroizing::new(bytes.to_vec()),
        deal_id: share.deal_id.clone(),
    })
}

/// Combine `threshold` (or more) opened shares back into the 32-byte key.
pub fn combine_key(
    threshold: u8,
    shares: &[RecoveredShare],
) -> Result<Zeroizing<[u8; KEY_LEN]>, CustodyError> {
    if shares.len() < threshold as usize {
        return Err(CustodyError::NotEnoughShares {
            t: threshold,
            got: shares.len(),
        });
    }
    // R3c: all shares must belong to ONE dealing — a mixed-epoch quorum (e.g. a
    // revoked custodian's old share alongside post-rotation shares) is rejected
    // instead of silently reconstructing the wrong/garbage secret.
    if let Some(first) = shares.first() {
        if shares.iter().any(|s| s.deal_id != first.deal_id) {
            return Err(CustodyError::MixedDealing);
        }
    }
    let parsed: Vec<Share> = shares
        .iter()
        .map(|s| Share::try_from(s.bytes.as_slice()))
        .collect::<Result<_, _>>()
        .map_err(|e| CustodyError::ShareDecode(e.to_string()))?;
    let secret = Sharks(threshold)
        .recover(parsed.iter())
        .map_err(|e| CustodyError::Combine(e.to_string()))?;
    if secret.len() != KEY_LEN {
        return Err(CustodyError::BadSecretLen(secret.len()));
    }
    let mut key = Zeroizing::new([0u8; KEY_LEN]);
    key.copy_from_slice(&secret);
    Ok(key)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn custodian(seed: u8) -> (String, StaticSecret, PublicKey) {
        let sk = StaticSecret::from([seed; 32]);
        let pk = PublicKey::from(&sk);
        (format!("did:key:zCustodian{seed}"), sk, pk)
    }

    fn fleet(n: u8) -> Vec<(String, StaticSecret, PublicKey)> {
        (1..=n).map(custodian).collect()
    }

    #[test]
    fn three_of_five_roundtrip() {
        let key = [42u8; 32];
        let fleet = fleet(5);
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let shares = split_key(&key, 3, &pubs).unwrap();
        assert_eq!(shares.len(), 5);

        // Any 3 custodians reconstruct (take 2nd, 4th, 5th).
        let opened: Vec<RecoveredShare> = [1usize, 3, 4]
            .iter()
            .map(|&i| open_share(&shares[i], &fleet[i].1).unwrap())
            .collect();
        let recovered = combine_key(3, &opened).unwrap();
        assert_eq!(*recovered, key);
    }

    #[test]
    fn two_shares_are_not_enough() {
        let key = [7u8; 32];
        let fleet = fleet(5);
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let shares = split_key(&key, 3, &pubs).unwrap();
        let opened: Vec<RecoveredShare> = (0..2)
            .map(|i| open_share(&shares[i], &fleet[i].1).unwrap())
            .collect();
        assert!(matches!(
            combine_key(3, &opened),
            Err(CustodyError::NotEnoughShares { t: 3, got: 2 })
        ));
    }

    #[test]
    fn wrong_custodian_cannot_open_a_share() {
        let key = [9u8; 32];
        let fleet = fleet(3);
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let shares = split_key(&key, 2, &pubs).unwrap();
        // Custodian 2's secret cannot open custodian 1's share.
        assert!(open_share(&shares[0], &fleet[1].1).is_err());
    }

    #[test]
    fn corrupted_share_is_detected_by_commitment() {
        let key = [11u8; 32];
        let fleet = fleet(3);
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let mut shares = split_key(&key, 2, &pubs).unwrap();
        // Substitute share 0's ciphertext with share 1's (both valid HPKE for
        // different recipients — re-seal share 1's bytes for custodian 0 so
        // HPKE opens fine but the commitment no longer matches).
        let share1_bytes = open_share(&shares[1], &fleet[1].1).unwrap().bytes;
        shares[0].sealed_share = kotoba_crypto::hpke_seal(&fleet[0].2, &share1_bytes).unwrap();
        assert!(matches!(
            open_share(&shares[0], &fleet[0].1),
            Err(CustodyError::CommitmentMismatch(_))
        ));
    }

    #[test]
    fn split_is_randomized_but_both_dealings_recover() {
        let key = [13u8; 32];
        let fleet = fleet(3);
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let a = split_key(&key, 2, &pubs).unwrap();
        let b = split_key(&key, 2, &pubs).unwrap();
        assert_ne!(
            a[0].commitment, b[0].commitment,
            "fresh polynomial per dealing"
        );
        for shares in [&a, &b] {
            let opened: Vec<RecoveredShare> = (0..2)
                .map(|i| open_share(&shares[i], &fleet[i].1).unwrap())
                .collect();
            assert_eq!(*combine_key(2, &opened).unwrap(), key);
        }
    }

    #[test]
    fn mixed_dealings_do_not_combine_to_the_key() {
        // Shares from two different dealings must not silently reconstruct.
        let key = [17u8; 32];
        let fleet = fleet(3);
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let a = split_key(&key, 2, &pubs).unwrap();
        let b = split_key(&key, 2, &pubs).unwrap();
        let opened = vec![
            open_share(&a[0], &fleet[0].1).unwrap(),
            open_share(&b[1], &fleet[1].1).unwrap(),
        ];
        // R3c: cross-dealing combine is now an EXPLICIT error, not silent garbage.
        assert!(matches!(
            combine_key(2, &opened),
            Err(CustodyError::MixedDealing)
        ));
    }

    #[test]
    fn rotation_changes_deal_id_and_revokes_old_shares() {
        let key = [71u8; 32];
        let fleet_a = fleet(3);
        let pubs_a: Vec<(String, PublicKey)> =
            fleet_a.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let e0 = split_key_epoch(&key, 2, &pubs_a, 0).unwrap();

        // Rotate to a NEW custodian set at epoch 1 (custodian #1 removed,
        // #4 added) — same key, fresh deal_id.
        let fleet_b = [custodian(2), custodian(3), custodian(4)];
        let pubs_b: Vec<(String, PublicKey)> =
            fleet_b.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let e1 = rotate_key(&key, 2, &pubs_b, 1).unwrap();

        assert_eq!(e0[0].epoch, 0);
        assert_eq!(e1[0].epoch, 1);
        assert_ne!(e0[0].deal_id, e1[0].deal_id, "rotation = fresh dealing");

        // New epoch still recovers the key.
        let opened_new: Vec<RecoveredShare> = (0..2)
            .map(|i| open_share(&e1[i], &fleet_b[i].1).unwrap())
            .collect();
        assert_eq!(*combine_key(2, &opened_new).unwrap(), key);

        // A revoked (epoch-0) share cannot be mixed into an epoch-1 quorum.
        let revoked = open_share(&e0[1], &fleet_a[1].1).unwrap(); // custodian #2 held both
        let one_new = open_share(&e1[0], &fleet_b[0].1).unwrap();
        assert!(matches!(
            combine_key(2, &[revoked, one_new]),
            Err(CustodyError::MixedDealing)
        ));
    }

    #[test]
    fn pre_r3c_share_decodes_with_epoch_zero() {
        // A share JSON without epoch/deal_id (pre-R3c deposit) must decode.
        let legacy = r#"{"index":1,"recipient_did":"did:key:zL","sealed_share":[1,2,3],"commitment":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],"threshold":2}"#;
        let share: CustodianShare = serde_json::from_str(legacy).unwrap();
        assert_eq!(share.epoch, 0);
        assert!(share.deal_id.is_empty());
    }

    #[test]
    fn bad_threshold_rejected() {
        let fleet = fleet(3);
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        assert!(matches!(
            split_key(&[1u8; 32], 1, &pubs),
            Err(CustodyError::BadThreshold { .. })
        ));
        assert!(matches!(
            split_key(&[1u8; 32], 4, &pubs),
            Err(CustodyError::BadThreshold { .. })
        ));
    }

    #[test]
    fn custodian_share_serde_roundtrip() {
        let fleet = fleet(2);
        let pubs: Vec<(String, PublicKey)> =
            fleet.iter().map(|(d, _, p)| (d.clone(), *p)).collect();
        let shares = split_key(&[3u8; 32], 2, &pubs).unwrap();
        let json = serde_json::to_string(&shares[0]).unwrap();
        let back: CustodianShare = serde_json::from_str(&json).unwrap();
        assert_eq!(back, shares[0]);
        // And the deserialized share still opens.
        assert!(open_share(&back, &fleet[0].1).is_ok());
    }
}
