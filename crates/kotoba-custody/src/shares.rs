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
}

/// An opened (decrypted, commitment-checked) share, ready for `combine_key`.
pub struct RecoveredShare {
    pub recipient_did: String,
    pub bytes: Zeroizing<Vec<u8>>,
}

fn share_commitment(bytes: &[u8]) -> [u8; 32] {
    let mut out = [0u8; 32];
    out.copy_from_slice(&Sha256::digest(bytes));
    out
}

/// Split `key` into one share per custodian; any `threshold` of them combine
/// back to the key, fewer learn nothing.
pub fn split_key(
    key: &[u8; KEY_LEN],
    threshold: u8,
    custodians: &[(String, PublicKey)],
) -> Result<Vec<CustodianShare>, CustodyError> {
    let n = custodians.len();
    if n > 255 {
        return Err(CustodyError::TooManyCustodians(n));
    }
    if threshold < 2 || (threshold as usize) > n {
        return Err(CustodyError::BadThreshold { t: threshold, n });
    }
    let sharks = Sharks(threshold);
    let dealer = sharks.dealer(key);
    let mut out = Vec::with_capacity(n);
    for (i, ((did, pk), share)) in custodians.iter().zip(dealer).enumerate() {
        let share_bytes: Vec<u8> = (&share).into();
        let sealed = kotoba_crypto::hpke_seal(pk, &share_bytes)
            .map_err(|e| CustodyError::Hpke(e.to_string()))?;
        out.push(CustodianShare {
            index: (i + 1) as u8,
            recipient_did: did.clone(),
            sealed_share: sealed,
            commitment: share_commitment(&share_bytes),
            threshold,
        });
    }
    Ok(out)
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
        shares[0].sealed_share =
            kotoba_crypto::hpke_seal(&fleet[0].2, &share1_bytes).unwrap();
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
        if let Ok(recovered) = combine_key(2, &opened) {
            assert_ne!(*recovered, key, "cross-dealing combine must not yield the key");
        }
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
