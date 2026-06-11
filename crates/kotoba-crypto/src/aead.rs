use aes_gcm::{
    aead::{Aead, AeadCore, OsRng},
    Aes256Gcm, KeyInit,
};
use thiserror::Error;
use zeroize::Zeroizing;

pub const KEY_LEN: usize = 32; // AES-256
pub const NONCE_LEN: usize = 12; // GCM 96-bit nonce
pub const TAG_LEN: usize = 16; // GCM auth tag

#[derive(Debug, Error)]
pub enum CryptoError {
    #[error("AEAD seal failed")]
    SealFailed,
    #[error("AEAD open failed: ciphertext tampered or wrong key")]
    OpenFailed,
    #[error("ciphertext too short (< {0} bytes)")]
    TooShort(usize),
    #[error("invalid envelope: {0}")]
    InvalidEnvelope(String),
    #[error("base64 decode: {0}")]
    Base64(#[from] base64::DecodeError),
}

/// AES-256-GCM seal.
/// Returns `nonce || ciphertext_with_tag` (12 + plaintext.len() + 16 bytes).
///
/// This is `seal_with_aad` with empty AAD. For PII-bearing or content-addressed
/// blobs prefer `seal_with_aad` and bind the ciphertext to its logical context
/// (e.g. owning graph/datom CID) per ADR-2606014000 D2.
pub fn seal(key: &[u8; KEY_LEN], plaintext: &[u8]) -> Result<Vec<u8>, CryptoError> {
    seal_with_aad(key, plaintext, &[])
}

/// AES-256-GCM seal with associated data (AAD).
/// `aad` is authenticated but NOT encrypted; `open_with_aad` must be given the
/// identical `aad` or decryption fails. Binding `aad` to a ciphertext's logical
/// slot (graph CID, owning datom CID, account DID) prevents an at-rest blob from
/// being silently swapped into a different slot (ADR-2606014000 D2).
/// Returns `nonce || ciphertext_with_tag`.
pub fn seal_with_aad(
    key: &[u8; KEY_LEN],
    plaintext: &[u8],
    aad: &[u8],
) -> Result<Vec<u8>, CryptoError> {
    use aes_gcm::aead::Payload;
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| CryptoError::SealFailed)?;
    let nonce = Aes256Gcm::generate_nonce(&mut OsRng);
    let ct = cipher
        .encrypt(&nonce, Payload { msg: plaintext, aad })
        .map_err(|_| CryptoError::SealFailed)?;
    let mut out = Vec::with_capacity(NONCE_LEN + ct.len());
    out.extend_from_slice(&nonce);
    out.extend_from_slice(&ct);
    Ok(out)
}

/// AES-256-GCM seal with caller-supplied nonce + AAD.
/// Returns `nonce || ciphertext_with_tag` (interoperates with `open_with_aad`).
///
/// SAFETY CONTRACT: the caller MUST guarantee that a `(key, nonce)` pair is
/// never reused for two DIFFERENT plaintexts — reuse completely breaks AES-GCM
/// confidentiality and integrity. The only sanctioned use is content-derived
/// nonces over content-addressed blocks (`nonce = HKDF(key-derived, cid)` with
/// `cid = sha2-256(plaintext)`), where a `(key, nonce)` collision implies the
/// plaintexts are identical, so determinism is the worst-case leak
/// (ADR-2606112200 sealed cold tier). Everything else MUST use `seal` /
/// `seal_with_aad`, which draw a random nonce from OsRng.
pub fn seal_with_aad_nonce(
    key: &[u8; KEY_LEN],
    nonce: &[u8; NONCE_LEN],
    plaintext: &[u8],
    aad: &[u8],
) -> Result<Vec<u8>, CryptoError> {
    use aes_gcm::aead::Payload;
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| CryptoError::SealFailed)?;
    let n = aes_gcm::Nonce::from(*nonce);
    let ct = cipher
        .encrypt(&n, Payload { msg: plaintext, aad })
        .map_err(|_| CryptoError::SealFailed)?;
    let mut out = Vec::with_capacity(NONCE_LEN + ct.len());
    out.extend_from_slice(nonce);
    out.extend_from_slice(&ct);
    Ok(out)
}

/// AES-256-GCM seal with explicit nonce (for deterministic tests only).
/// Only available under `#[cfg(test)]` — production code MUST use `seal` which
/// generates a random nonce via OsRng.  Nonce reuse under a fixed key completely
/// breaks AES-GCM confidentiality and integrity.
#[cfg(test)]
pub fn seal_with_nonce(
    key: &[u8; KEY_LEN],
    nonce: &[u8; NONCE_LEN],
    plaintext: &[u8],
) -> Result<Vec<u8>, CryptoError> {
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| CryptoError::SealFailed)?;
    let n = aes_gcm::Nonce::from(*nonce);
    let ct = cipher
        .encrypt(&n, plaintext)
        .map_err(|_| CryptoError::SealFailed)?;
    let mut out = Vec::with_capacity(NONCE_LEN + ct.len());
    out.extend_from_slice(nonce);
    out.extend_from_slice(&ct);
    Ok(out)
}

/// AES-256-GCM open.
/// Expects `nonce || ciphertext_with_tag` (as produced by `seal`).
pub fn open(key: &[u8; KEY_LEN], data: &[u8]) -> Result<Zeroizing<Vec<u8>>, CryptoError> {
    open_with_aad(key, data, &[])
}

/// AES-256-GCM open with associated data (AAD).
/// `aad` MUST equal the value passed to `seal_with_aad`, else this returns
/// `OpenFailed`. Expects `nonce || ciphertext_with_tag`.
pub fn open_with_aad(
    key: &[u8; KEY_LEN],
    data: &[u8],
    aad: &[u8],
) -> Result<Zeroizing<Vec<u8>>, CryptoError> {
    use aes_gcm::aead::Payload;
    if data.len() < NONCE_LEN + TAG_LEN {
        return Err(CryptoError::TooShort(NONCE_LEN + TAG_LEN));
    }
    let cipher = Aes256Gcm::new_from_slice(key).map_err(|_| CryptoError::OpenFailed)?;
    let nonce_arr: [u8; NONCE_LEN] = data[..NONCE_LEN]
        .try_into()
        .map_err(|_| CryptoError::TooShort(NONCE_LEN))?;
    let nonce = aes_gcm::Nonce::from(nonce_arr);
    let pt = cipher
        .decrypt(
            &nonce,
            Payload {
                msg: &data[NONCE_LEN..],
                aad,
            },
        )
        .map_err(|_| CryptoError::OpenFailed)?;
    Ok(Zeroizing::new(pt))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn random_key() -> [u8; KEY_LEN] {
        let mut k = [0u8; KEY_LEN];
        rand::RngCore::fill_bytes(&mut rand::thread_rng(), &mut k);
        k
    }

    #[test]
    fn seal_open_roundtrip() {
        let key = random_key();
        let msg = b"hello kotoba-crypto";
        let ct = seal(&key, msg).unwrap();
        let pt = open(&key, &ct).unwrap();
        assert_eq!(pt.as_slice(), msg);
    }

    #[test]
    fn open_with_wrong_key_fails() {
        let key = random_key();
        let ct = seal(&key, b"secret").unwrap();
        let wrong = random_key();
        assert!(open(&wrong, &ct).is_err());
    }

    #[test]
    fn open_with_tampered_data_fails() {
        let key = random_key();
        let mut ct = seal(&key, b"secret").unwrap();
        ct[NONCE_LEN] ^= 0xFF;
        assert!(open(&key, &ct).is_err());
    }

    #[test]
    fn ciphertext_is_longer_than_plaintext() {
        let key = random_key();
        let pt = b"short";
        let ct = seal(&key, pt).unwrap();
        assert!(ct.len() > pt.len());
        assert_eq!(ct.len(), NONCE_LEN + pt.len() + TAG_LEN);
    }

    #[test]
    fn seal_open_empty_plaintext() {
        // AES-256-GCM must handle zero-length plaintext (auth-only mode).
        let key = random_key();
        let ct = seal(&key, b"").unwrap();
        assert_eq!(ct.len(), NONCE_LEN + TAG_LEN, "empty pt: only nonce+tag");
        let pt = open(&key, &ct).unwrap();
        assert_eq!(pt.as_slice(), b"");
    }

    #[test]
    fn open_data_too_short_returns_error() {
        let key = random_key();
        // 27 bytes < NONCE_LEN(12) + TAG_LEN(16) = 28
        let short = vec![0u8; NONCE_LEN + TAG_LEN - 1];
        assert!(open(&key, &short).is_err());
        // Empty data
        assert!(open(&key, &[]).is_err());
    }

    #[test]
    fn successive_seals_use_distinct_nonces() {
        // Each `seal` call must generate a unique 96-bit nonce via OsRng.
        // Two seals of the same plaintext must produce distinct ciphertexts.
        let key = random_key();
        let ct1 = seal(&key, b"same plaintext").unwrap();
        let ct2 = seal(&key, b"same plaintext").unwrap();
        // nonces (first 12 bytes) must differ with overwhelming probability.
        assert_ne!(
            &ct1[..NONCE_LEN],
            &ct2[..NONCE_LEN],
            "nonce reuse detected — OsRng should produce distinct nonces"
        );
    }

    #[test]
    fn truncated_tag_is_rejected() {
        let key = random_key();
        let mut ct = seal(&key, b"important").unwrap();
        // Remove last byte of the auth tag.
        ct.pop();
        assert!(open(&key, &ct).is_err(), "truncated tag must be rejected");
    }

    // ---- New tests --------------------------------------------------------

    #[test]
    fn key_nonce_tag_len_constants() {
        assert_eq!(KEY_LEN, 32, "AES-256 requires 32-byte key");
        assert_eq!(NONCE_LEN, 12, "GCM 96-bit nonce = 12 bytes");
        assert_eq!(TAG_LEN, 16, "GCM auth tag = 16 bytes");
    }

    #[test]
    fn seal_with_nonce_is_deterministic() {
        let key = random_key();
        let nonce = [0xABu8; NONCE_LEN];
        let ct1 = seal_with_nonce(&key, &nonce, b"deterministic").unwrap();
        let ct2 = seal_with_nonce(&key, &nonce, b"deterministic").unwrap();
        assert_eq!(
            ct1, ct2,
            "same key+nonce+pt must produce identical ciphertext"
        );
    }

    #[test]
    fn seal_with_nonce_open_roundtrip() {
        let key = random_key();
        let nonce = [0x01u8; NONCE_LEN];
        let ct = seal_with_nonce(&key, &nonce, b"nonce-roundtrip").unwrap();
        let pt = open(&key, &ct).unwrap();
        assert_eq!(pt.as_slice(), b"nonce-roundtrip");
    }

    #[test]
    fn too_short_error_display_contains_threshold() {
        let threshold = NONCE_LEN + TAG_LEN;
        let err = CryptoError::TooShort(threshold);
        let s = err.to_string();
        assert!(
            s.contains(&threshold.to_string()),
            "TooShort display must include the threshold, got: {s}"
        );
    }

    #[test]
    fn invalid_envelope_error_display() {
        let err = CryptoError::InvalidEnvelope("bad header".to_string());
        let s = err.to_string();
        assert!(
            s.contains("bad header"),
            "InvalidEnvelope display must include reason, got: {s}"
        );
    }

    #[test]
    fn seal_open_large_plaintext() {
        let key = random_key();
        let pt: Vec<u8> = (0u8..=255).cycle().take(4096).collect();
        let ct = seal(&key, &pt).unwrap();
        assert_eq!(ct.len(), NONCE_LEN + pt.len() + TAG_LEN);
        let recovered = open(&key, &ct).unwrap();
        assert_eq!(recovered.as_slice(), pt.as_slice());
    }

    // ---- AAD binding (ADR-2606014000 D2) ---------------------------------

    #[test]
    fn seal_with_aad_nonce_is_deterministic_and_opens() {
        let key = random_key();
        let nonce = [0x42u8; NONCE_LEN];
        let aad = b"kotoba/sealed-block/v1";
        let ct1 = seal_with_aad_nonce(&key, &nonce, b"block bytes", aad).unwrap();
        let ct2 = seal_with_aad_nonce(&key, &nonce, b"block bytes", aad).unwrap();
        assert_eq!(ct1, ct2, "same key+nonce+pt+aad must be deterministic");
        let pt = open_with_aad(&key, &ct1, aad).unwrap();
        assert_eq!(pt.as_slice(), b"block bytes");
        assert!(
            open_with_aad(&key, &ct1, b"other-aad").is_err(),
            "wrong AAD must fail"
        );
    }

    #[test]
    fn seal_with_aad_open_with_same_aad_roundtrips() {
        let key = random_key();
        let aad = b"kotoba://graph/bafyGraphCid";
        let ct = seal_with_aad(&key, b"pii payload", aad).unwrap();
        let pt = open_with_aad(&key, &ct, aad).unwrap();
        assert_eq!(pt.as_slice(), b"pii payload");
    }

    #[test]
    fn open_with_wrong_aad_fails() {
        // A blob sealed for one logical slot must not decrypt under another.
        let key = random_key();
        let ct = seal_with_aad(&key, b"slot A data", b"slot-A").unwrap();
        assert!(
            open_with_aad(&key, &ct, b"slot-B").is_err(),
            "swapping the AAD (logical slot) must fail AEAD verification"
        );
    }

    #[test]
    fn seal_with_aad_empty_plaintext_roundtrips() {
        let key = random_key();
        let aad = b"ctx";
        let ct = seal_with_aad(&key, b"", aad).unwrap();
        assert_eq!(ct.len(), NONCE_LEN + TAG_LEN, "empty pt: nonce+tag only");
        assert_eq!(open_with_aad(&key, &ct, aad).unwrap().as_slice(), b"");
    }

    #[test]
    fn open_with_aad_too_short_fails() {
        let key = random_key();
        assert!(open_with_aad(&key, &[0u8; NONCE_LEN + TAG_LEN - 1], b"a").is_err());
        assert!(open_with_aad(&key, &[], b"a").is_err());
    }

    #[test]
    fn seal_with_aad_large_plaintext_roundtrips() {
        let key = random_key();
        let aad = b"kotoba://graph/big";
        let pt: Vec<u8> = (0u8..=255).cycle().take(4096).collect();
        let ct = seal_with_aad(&key, &pt, aad).unwrap();
        assert_eq!(open_with_aad(&key, &ct, aad).unwrap().as_slice(), pt.as_slice());
    }

    #[test]
    fn seal_empty_aad_equals_plain_seal_open() {
        // seal()/open() are the empty-AAD case; they must interoperate with the
        // _with_aad variants given an empty AAD.
        let key = random_key();
        let ct = seal(&key, b"x").unwrap();
        let pt = open_with_aad(&key, &ct, &[]).unwrap();
        assert_eq!(pt.as_slice(), b"x");
        let ct2 = seal_with_aad(&key, b"x", &[]).unwrap();
        let pt2 = open(&key, &ct2).unwrap();
        assert_eq!(pt2.as_slice(), b"x");
    }

    #[test]
    fn open_only_nonce_no_ciphertext_fails() {
        // Exactly NONCE_LEN bytes — below minimum NONCE_LEN + TAG_LEN.
        let key = random_key();
        let data = vec![0u8; NONCE_LEN];
        assert!(
            open(&key, &data).is_err(),
            "bare nonce without tag must be rejected"
        );
    }
}
