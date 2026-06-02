//! Passkey-rooted key hierarchy (ADR-2606014000).
//!
//! ```text
//! L0  WebAuthn Passkey ── PRF/hmac-secret ──▶ S_prf  (32 B, device-resident)
//! L1  ARK (Account Root Key)  ── random 32 B, wrapped per-passkey under KDF(S_prf)
//! L2  k_storage / k_signal / k_session  = HKDF(ARK, <label>)
//! ```
//!
//! The server only ever stores the opaque `wrap_ark` ciphertext and (optionally)
//! guardian recovery shares. Neither reveals anything without a device-resident
//! PRF output or a quorum of guardians, so there is no server-held wrapping key
//! (ADR-2605231525 no-server-key invariant).

use crate::aead::{open_with_aad, seal_with_aad, CryptoError, KEY_LEN};
use crate::hkdf::derive_key;
use thiserror::Error;
use zeroize::Zeroizing;

/// Label HKDF-Expand'd from `S_prf` to derive the per-passkey ARK-wrapping key.
const LABEL_ARK_WRAP: &[u8] = b"kotoba/passkey/ark-wrap/v1";

/// L2 purpose labels. Each label is used for exactly one purpose, forever.
pub const LABEL_STORAGE: &[u8] = b"kotoba/storage/dek-wrap/v1";
pub const LABEL_SIGNAL: &[u8] = b"kotoba/signal/identity/v1";
pub const LABEL_SESSION: &[u8] = b"kotoba/session/sign/v1";

#[derive(Debug, Error)]
pub enum KeyTreeError {
    #[error("aead: {0}")]
    Aead(#[from] CryptoError),
    #[error("unwrapped ARK has wrong length: expected {KEY_LEN}, got {0}")]
    BadArkLen(usize),
}

/// Derive the per-passkey ARK-wrapping key from a WebAuthn PRF output.
///
/// `prf_output` = the secret returned by the authenticator's PRF / `hmac-secret`
/// extension for this credential + account salt. It never leaves the device.
fn passkey_wrap_key(prf_output: &[u8]) -> [u8; KEY_LEN] {
    derive_key(prf_output, LABEL_ARK_WRAP)
}

/// Generate a fresh random Account Root Key. Call once, at account enrollment.
/// Returned in a `Zeroizing` buffer so it is wiped from memory on drop.
pub fn generate_ark() -> Zeroizing<[u8; KEY_LEN]> {
    use aes_gcm::aead::rand_core::RngCore;
    use aes_gcm::aead::OsRng;
    let mut ark = Zeroizing::new([0u8; KEY_LEN]);
    OsRng.fill_bytes(ark.as_mut_slice());
    ark
}

/// Wrap the ARK under a passkey's PRF-derived key, bound to the account DID.
///
/// The output is safe to persist publicly (server-side): without the
/// device-resident `prf_output` it reveals nothing. Enrolling a new device is
/// "wrap the same ARK under the new passkey's PRF" — no server key involved.
pub fn wrap_ark(
    prf_output: &[u8],
    ark: &[u8; KEY_LEN],
    account_did: &str,
) -> Result<Vec<u8>, KeyTreeError> {
    let wk = passkey_wrap_key(prf_output);
    Ok(seal_with_aad(&wk, ark, account_did.as_bytes())?)
}

/// Recover the ARK from a wrapped blob using this device's passkey PRF output.
pub fn unwrap_ark(
    prf_output: &[u8],
    wrapped: &[u8],
    account_did: &str,
) -> Result<Zeroizing<[u8; KEY_LEN]>, KeyTreeError> {
    let wk = passkey_wrap_key(prf_output);
    let pt = open_with_aad(&wk, wrapped, account_did.as_bytes())?;
    if pt.len() != KEY_LEN {
        return Err(KeyTreeError::BadArkLen(pt.len()));
    }
    let mut ark = Zeroizing::new([0u8; KEY_LEN]);
    ark.copy_from_slice(&pt);
    Ok(ark)
}

/// L2: storage DEK-wrapping key — wraps per-graph/per-record data keys.
pub fn derive_storage_key(ark: &[u8; KEY_LEN]) -> [u8; KEY_LEN] {
    derive_key(ark, LABEL_STORAGE)
}

/// L2: Signal identity seed — deterministic seed for the libsignal IdentityKey,
/// so the same Signal identity is recoverable on any device that can recover ARK.
pub fn derive_signal_seed(ark: &[u8; KEY_LEN]) -> [u8; KEY_LEN] {
    derive_key(ark, LABEL_SIGNAL)
}

/// L2: session signing seed — seeds the CACAO session keypair (replaces any
/// server-held session key per ADR-2606014000 D3).
pub fn derive_session_seed(ark: &[u8; KEY_LEN]) -> [u8; KEY_LEN] {
    derive_key(ark, LABEL_SESSION)
}

/// Social recovery for the ARK via Shamir Secret Sharing over GF(256).
///
/// `split(ark, t, n)` produces `n` guardian shares; any `t` of them reconstruct
/// the ARK. Loss of all passkeys is survivable iff a `t`-quorum of guardians
/// cooperate — and no single guardian (or the server holding shares) learns
/// anything about the ARK. Each 33-byte share is `index_byte || 32 share bytes`.
pub mod recovery {
    use super::KEY_LEN;
    use zeroize::Zeroizing;

    /// GF(256) multiply (AES polynomial 0x11b), constant in structure.
    fn gf_mul(mut a: u8, mut b: u8) -> u8 {
        let mut p: u8 = 0;
        for _ in 0..8 {
            if b & 1 != 0 {
                p ^= a;
            }
            let hi = a & 0x80;
            a <<= 1;
            if hi != 0 {
                a ^= 0x1b;
            }
            b >>= 1;
        }
        p
    }

    /// GF(256) multiplicative inverse via exponentiation (a^254 = a^-1).
    fn gf_inv(a: u8) -> u8 {
        let mut result = 1u8;
        let mut base = a;
        // 254 = 0b1111_1110
        for bit in 1..8 {
            base = gf_mul(base, base);
            if (254 >> bit) & 1 == 1 {
                result = gf_mul(result, base);
            }
        }
        result
    }

    /// Split a 32-byte secret into `n` shares with threshold `t` (1 ≤ t ≤ n ≤ 255).
    /// Returns `n` shares, each `1 + KEY_LEN` bytes: `x_index || y_0..y_31`.
    pub fn split(secret: &[u8; KEY_LEN], t: u8, n: u8) -> Vec<Vec<u8>> {
        use aes_gcm::aead::rand_core::RngCore;
        use aes_gcm::aead::OsRng;
        assert!(t >= 1 && t <= n && n >= 1, "require 1 <= t <= n");

        // For each secret byte, a degree-(t-1) polynomial with f(0) = secret byte.
        // coeffs[byte][0] = secret byte; coeffs[byte][1..t] = random.
        let mut coeffs = vec![[0u8; 256]; KEY_LEN]; // only first `t` used
        for (i, sb) in secret.iter().enumerate() {
            coeffs[i][0] = *sb;
            let mut rnd = [0u8; 256];
            let t = t as usize;
            OsRng.fill_bytes(&mut rnd[..t]);
            // coeffs[i][1..t] = random; coeffs[i][0] stays the secret byte.
            coeffs[i][1..t].copy_from_slice(&rnd[1..t]);
        }

        let mut shares = Vec::with_capacity(n as usize);
        for s in 1..=n {
            let x = s; // share index (x != 0)
            let mut share = Vec::with_capacity(1 + KEY_LEN);
            share.push(x);
            for c in coeffs.iter().take(KEY_LEN) {
                // Horner eval of f(x) over GF(256).
                let mut acc = 0u8;
                for k in (0..(t as usize)).rev() {
                    acc = gf_mul(acc, x) ^ c[k];
                }
                share.push(acc);
            }
            shares.push(share);
        }
        shares
    }

    /// Reconstruct the secret from `t` (or more) shares via Lagrange interpolation at x=0.
    pub fn combine(shares: &[Vec<u8>]) -> Option<Zeroizing<[u8; KEY_LEN]>> {
        if shares.is_empty() {
            return None;
        }
        if shares.iter().any(|s| s.len() != 1 + KEY_LEN) {
            return None;
        }
        let xs: Vec<u8> = shares.iter().map(|s| s[0]).collect();
        let mut out = Zeroizing::new([0u8; KEY_LEN]);
        for (byte_idx, slot) in out.iter_mut().enumerate() {
            let mut secret_byte = 0u8;
            for (i, xi) in xs.iter().enumerate() {
                // Lagrange basis L_i(0) = Π_{j≠i} x_j / (x_j - x_i)  over GF(256).
                let yi = shares[i][1 + byte_idx];
                let mut num = 1u8;
                let mut den = 1u8;
                for (j, xj) in xs.iter().enumerate() {
                    if i == j {
                        continue;
                    }
                    num = gf_mul(num, *xj);
                    den = gf_mul(den, *xi ^ *xj); // (x_i - x_j) == (x_i ^ x_j) in GF(2^8)
                }
                let basis = gf_mul(num, gf_inv(den));
                secret_byte ^= gf_mul(yi, basis);
            }
            *slot = secret_byte;
        }
        Some(out)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ark_wrap_unwrap_roundtrip() {
        let prf = b"device-1 prf output 32 bytes....";
        let ark = generate_ark();
        let did = "did:web:etzhayyim.com:actor:alice";
        let wrapped = wrap_ark(prf, &ark, did).unwrap();
        let recovered = unwrap_ark(prf, &wrapped, did).unwrap();
        assert_eq!(recovered.as_slice(), ark.as_slice());
    }

    #[test]
    fn wrong_passkey_prf_cannot_unwrap() {
        let ark = generate_ark();
        let did = "did:web:etzhayyim.com:actor:bob";
        let wrapped = wrap_ark(b"device-1 prf", &ark, did).unwrap();
        assert!(unwrap_ark(b"device-2 prf", &wrapped, did).is_err());
    }

    #[test]
    fn wrong_account_did_cannot_unwrap() {
        let prf = b"shared prf";
        let ark = generate_ark();
        let wrapped = wrap_ark(prf, &ark, "did:web:a").unwrap();
        assert!(
            unwrap_ark(prf, &wrapped, "did:web:b").is_err(),
            "DID is the AAD; a different account DID must fail"
        );
    }

    #[test]
    fn second_device_enrollment_recovers_same_ark() {
        // Enroll device 1; "add device 2" = re-wrap the SAME ARK under device 2's PRF.
        let did = "did:web:multi";
        let ark = generate_ark();
        let wrap1 = wrap_ark(b"prf-device-1", &ark, did).unwrap();
        let wrap2 = wrap_ark(b"prf-device-2", &ark, did).unwrap();
        let a1 = unwrap_ark(b"prf-device-1", &wrap1, did).unwrap();
        let a2 = unwrap_ark(b"prf-device-2", &wrap2, did).unwrap();
        assert_eq!(a1.as_slice(), a2.as_slice(), "both devices recover one ARK");
    }

    #[test]
    fn purpose_keys_are_distinct_and_deterministic() {
        let ark = *generate_ark();
        let ks1 = derive_storage_key(&ark);
        let ks2 = derive_storage_key(&ark);
        let sig = derive_signal_seed(&ark);
        let ses = derive_session_seed(&ark);
        assert_eq!(ks1, ks2, "derivation is deterministic");
        assert_ne!(ks1, sig, "storage != signal");
        assert_ne!(sig, ses, "signal != session");
        assert_ne!(ks1, ses, "storage != session");
    }

    #[test]
    fn shamir_3_of_5_recovers_with_any_three() {
        let ark = generate_ark();
        let shares = recovery::split(&ark, 3, 5);
        assert_eq!(shares.len(), 5);
        // Any 3 shares reconstruct.
        let pick = vec![shares[0].clone(), shares[2].clone(), shares[4].clone()];
        let rec = recovery::combine(&pick).unwrap();
        assert_eq!(rec.as_slice(), ark.as_slice());
        // A different 3 also reconstruct.
        let pick2 = vec![shares[1].clone(), shares[3].clone(), shares[4].clone()];
        assert_eq!(recovery::combine(&pick2).unwrap().as_slice(), ark.as_slice());
    }

    #[test]
    fn shamir_below_threshold_does_not_recover() {
        let ark = generate_ark();
        let shares = recovery::split(&ark, 3, 5);
        // 2 shares (< t=3) must NOT yield the secret.
        let two = vec![shares[0].clone(), shares[1].clone()];
        let rec = recovery::combine(&two).unwrap();
        assert_ne!(
            rec.as_slice(),
            ark.as_slice(),
            "fewer than t shares must not reconstruct the ARK"
        );
    }

    #[test]
    fn shamir_all_shares_recover() {
        let ark = generate_ark();
        let shares = recovery::split(&ark, 2, 2);
        assert_eq!(recovery::combine(&shares).unwrap().as_slice(), ark.as_slice());
    }

    #[test]
    fn shamir_threshold_one_any_single_share_recovers() {
        // t=1: every share alone reconstructs (degenerate but valid).
        let ark = generate_ark();
        let shares = recovery::split(&ark, 1, 4);
        for sh in &shares {
            assert_eq!(recovery::combine(&[sh.clone()]).unwrap().as_slice(), ark.as_slice());
        }
    }

    #[test]
    fn shamir_more_than_threshold_shares_still_recover() {
        // Providing MORE than t shares (4 of a 3-of-5) must still reconstruct.
        let ark = generate_ark();
        let shares = recovery::split(&ark, 3, 5);
        let four = vec![shares[0].clone(), shares[1].clone(), shares[2].clone(), shares[4].clone()];
        assert_eq!(recovery::combine(&four).unwrap().as_slice(), ark.as_slice());
    }

    #[test]
    fn shamir_combine_rejects_malformed_share_length() {
        let ark = generate_ark();
        let mut shares = recovery::split(&ark, 2, 3);
        shares[0].truncate(10); // wrong length
        assert!(recovery::combine(&shares).is_none());
    }
}
