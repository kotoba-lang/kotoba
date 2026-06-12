/// SecureVault — AEAD-encrypted wrapper around `Vault`.
/// Plaintext bytes are AES-256-GCM sealed before being stored in the underlying Vault.
/// The `signal:v1:` envelope is used for the wire format.
///
/// This satisfies the Vault zero-knowledge invariant: the store only ever holds ciphertext.
///
/// `put_with_policy()` additionally returns a `DataPolicy::Encrypted` so that callers can
/// attach the policy directly to `ChainEntry` / `QuadObject::Encrypted` without having to
/// re-derive the CID.
use crate::vault::{BlobRef, Vault};
use bytes::Bytes;
use kotoba_core::{DataPolicy, EnvelopeKeyWrap, EnvelopeManifest, KotobaCid};
use kotoba_crypto::key_wrap::{unwrap_key, wrap_key};
use rand_core::RngCore;
use zeroize::Zeroizing;

pub const MAX_ENVELOPE_MANIFEST_CBOR_BYTES: usize = 8 * 1024 * 1024;

/// AEAD-encrypted Vault.  Callers must supply the 32-byte vault key.
pub struct SecureVault {
    inner: Vault,
}

impl SecureVault {
    pub fn new() -> Self {
        Self {
            inner: Vault::new(),
        }
    }

    pub fn with_vault(vault: Vault) -> Self {
        Self { inner: vault }
    }

    /// Encrypt `plaintext` with `key` and store the ciphertext.
    /// Returns a `BlobRef` keyed on the ciphertext CID (NOT the plaintext CID).
    pub async fn put(
        &self,
        key: &[u8; 32],
        plaintext: Bytes,
    ) -> Result<BlobRef, kotoba_crypto::aead::CryptoError> {
        let ct = kotoba_crypto::aead::seal(key, &plaintext)?;
        Ok(self.inner.put(Bytes::from(ct)).await)
    }

    /// Encrypt `plaintext`, store it, and return both the `BlobRef` and a
    /// `DataPolicy::Encrypted` that can be attached to a `ChainEntry` or
    /// `QuadObject::Encrypted`.
    ///
    /// `policy_cid`: CID of the PRE key-registry entry that controls who can
    /// decrypt (e.g. the CID returned by `PreKeyRegistry::grant()`).
    /// Pass `blob_ref.cid` as `policy_cid` for single-key blobs (no PRE delegation).
    pub async fn put_with_policy(
        &self,
        key: &[u8; 32],
        plaintext: Bytes,
        policy_cid: kotoba_core::cid::KotobaCid,
    ) -> Result<(BlobRef, DataPolicy), kotoba_crypto::aead::CryptoError> {
        let blob_ref = self.put(key, plaintext).await?;
        let policy = DataPolicy::Encrypted {
            ct_cid: blob_ref.cid.clone(),
            policy_cid,
        };
        Ok((blob_ref, policy))
    }

    /// Encrypt `plaintext` bound to `aad` and store the ciphertext.
    ///
    /// `aad` is a caller-supplied **logical context** — e.g. the owning graph
    /// CID, the owning datom subject CID, or the account DID — NOT the ciphertext
    /// blob CID (that would be circular, since the blob CID is derived from the
    /// ciphertext). Because `aad` is authenticated, a blob sealed for one logical
    /// slot cannot be silently swapped into another: `get_bound` with a different
    /// `aad` fails. Prefer this over `put` for any 要配慮 / PII-bearing blob
    /// (ADR-2606014000 D2). The reader independently knows `aad` from the datom
    /// that references the blob, so no extra state is needed.
    pub async fn put_bound(
        &self,
        key: &[u8; 32],
        plaintext: Bytes,
        aad: &[u8],
    ) -> Result<BlobRef, kotoba_crypto::aead::CryptoError> {
        let ct = kotoba_crypto::aead::seal_with_aad(key, &plaintext, aad)?;
        Ok(self.inner.put(Bytes::from(ct)).await)
    }

    /// AAD-bound counterpart to `put_with_policy` (ADR-2606014000 D2).
    pub async fn put_with_policy_bound(
        &self,
        key: &[u8; 32],
        plaintext: Bytes,
        aad: &[u8],
        policy_cid: kotoba_core::cid::KotobaCid,
    ) -> Result<(BlobRef, DataPolicy), kotoba_crypto::aead::CryptoError> {
        let blob_ref = self.put_bound(key, plaintext, aad).await?;
        let policy = DataPolicy::Encrypted {
            ct_cid: blob_ref.cid.clone(),
            policy_cid,
        };
        Ok((blob_ref, policy))
    }

    /// Retrieve ciphertext by CID and decrypt with `key`.
    pub async fn get(
        &self,
        key: &[u8; 32],
        blob_ref: &BlobRef,
    ) -> Result<Option<Bytes>, kotoba_crypto::aead::CryptoError> {
        let Some(ct) = self.inner.get(&blob_ref.cid).await else {
            return Ok(None);
        };
        let pt = kotoba_crypto::aead::open(key, &ct)?;
        Ok(Some(Bytes::from(pt.to_vec())))
    }

    /// Retrieve and decrypt a blob sealed with `put_bound`. `aad` MUST match the
    /// value used at seal time, else this returns an AEAD `OpenFailed`.
    pub async fn get_bound(
        &self,
        key: &[u8; 32],
        blob_ref: &BlobRef,
        aad: &[u8],
    ) -> Result<Option<Bytes>, kotoba_crypto::aead::CryptoError> {
        let Some(ct) = self.inner.get(&blob_ref.cid).await else {
            return Ok(None);
        };
        let pt = kotoba_crypto::aead::open_with_aad(key, &ct, aad)?;
        Ok(Some(Bytes::from(pt.to_vec())))
    }

    pub async fn contains(&self, blob_ref: &BlobRef) -> bool {
        self.inner.contains(&blob_ref.cid).await
    }

    /// Store plaintext using envelope encryption.
    ///
    /// A fresh random DEK encrypts the blob. The supplied `wrapping_key` only
    /// wraps that DEK for `recipient`, so future access-policy changes can
    /// publish a new manifest without re-encrypting the ciphertext block.
    pub async fn put_enveloped(
        &self,
        wrapping_key: &[u8; 32],
        recipient: &str,
        plaintext: Bytes,
        aad: &[u8],
    ) -> Result<(BlobRef, KotobaCid, EnvelopeManifest), kotoba_crypto::aead::CryptoError> {
        validate_envelope_recipient(recipient)?;
        validate_envelope_aad(aad)?;
        let mut dek = Zeroizing::new([0u8; 32]);
        rand_core::OsRng.fill_bytes(dek.as_mut());

        let ct = kotoba_crypto::aead::seal_with_aad(&dek, &plaintext, aad)?;
        let blob_ref = self.inner.put(Bytes::from(ct)).await;
        let wrap_aad = envelope_wrap_aad(&blob_ref.cid, recipient, aad)?;
        let wrapped_dek = wrap_key(wrapping_key, dek.as_ref(), &wrap_aad)?;
        let manifest = EnvelopeManifest::new(
            blob_ref.cid.clone(),
            aad.to_vec(),
            vec![EnvelopeKeyWrap::aes_256_gcm(recipient, wrapped_dek)],
        );
        let manifest_cid = self.put_envelope_manifest(&manifest).await?;
        Ok((blob_ref, manifest_cid, manifest))
    }

    /// Envelope-encrypt plaintext and return a `DataPolicy::Enveloped`.
    pub async fn put_enveloped_with_policy(
        &self,
        wrapping_key: &[u8; 32],
        recipient: &str,
        plaintext: Bytes,
        aad: &[u8],
    ) -> Result<(BlobRef, DataPolicy, EnvelopeManifest), kotoba_crypto::aead::CryptoError> {
        let (blob_ref, manifest_cid, manifest) = self
            .put_enveloped(wrapping_key, recipient, plaintext, aad)
            .await?;
        let policy = DataPolicy::Enveloped {
            ct_cid: blob_ref.cid.clone(),
            manifest_cid,
        };
        Ok((blob_ref, policy, manifest))
    }

    /// Add or replace one recipient wrap in an existing envelope manifest.
    ///
    /// The caller must provide the raw DEK. This method is intentionally small:
    /// policy engines can obtain the DEK via an authorized existing wrap, then
    /// publish the returned new manifest CID as the current policy pointer.
    pub async fn put_envelope_manifest_with_wrap(
        &self,
        mut manifest: EnvelopeManifest,
        wrapping_key: &[u8; 32],
        recipient: &str,
        dek: &[u8; 32],
    ) -> Result<(KotobaCid, EnvelopeManifest), kotoba_crypto::aead::CryptoError> {
        validate_envelope_recipient(recipient)?;
        let wrap_aad = envelope_wrap_aad(&manifest.ct_cid, recipient, &manifest.aad)?;
        let wrapped_dek = wrap_key(wrapping_key, dek, &wrap_aad)?;
        manifest
            .dek_wraps
            .retain(|wrap| wrap.recipient != recipient);
        manifest
            .dek_wraps
            .push(EnvelopeKeyWrap::aes_256_gcm(recipient, wrapped_dek));
        let manifest_cid = self.put_envelope_manifest(&manifest).await?;
        Ok((manifest_cid, manifest))
    }

    /// Store an envelope manifest as a content-addressed CBOR block.
    pub async fn put_envelope_manifest(
        &self,
        manifest: &EnvelopeManifest,
    ) -> Result<KotobaCid, kotoba_crypto::aead::CryptoError> {
        manifest
            .validate()
            .map_err(|e| kotoba_crypto::aead::CryptoError::InvalidEnvelope(e.to_string()))?;
        let mut cbor = Vec::new();
        ciborium::into_writer(manifest, &mut cbor)
            .map_err(|e| kotoba_crypto::aead::CryptoError::InvalidEnvelope(e.to_string()))?;
        if cbor.len() > MAX_ENVELOPE_MANIFEST_CBOR_BYTES {
            return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
                "envelope manifest CBOR too large: {} bytes > {}",
                cbor.len(),
                MAX_ENVELOPE_MANIFEST_CBOR_BYTES
            )));
        }
        Ok(self
            .inner
            .put_typed(Bytes::from(cbor), "application/cbor")
            .await
            .cid)
    }

    /// Load an envelope manifest by CID.
    pub async fn get_envelope_manifest(
        &self,
        manifest_cid: &KotobaCid,
    ) -> Result<Option<EnvelopeManifest>, kotoba_crypto::aead::CryptoError> {
        let Some(bytes) = self.inner.get(manifest_cid).await else {
            return Ok(None);
        };
        let actual_cid = KotobaCid::from_bytes(&bytes);
        if actual_cid != *manifest_cid {
            return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
                "envelope manifest CID mismatch: expected {}, got {}",
                manifest_cid.to_multibase(),
                actual_cid.to_multibase()
            )));
        }
        if bytes.len() > MAX_ENVELOPE_MANIFEST_CBOR_BYTES {
            return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
                "envelope manifest CBOR too large: {} bytes > {}",
                bytes.len(),
                MAX_ENVELOPE_MANIFEST_CBOR_BYTES
            )));
        }
        let manifest = ciborium::from_reader::<EnvelopeManifest, _>(&bytes[..])
            .map_err(|e| kotoba_crypto::aead::CryptoError::InvalidEnvelope(e.to_string()))?;
        manifest
            .validate()
            .map_err(|e| kotoba_crypto::aead::CryptoError::InvalidEnvelope(e.to_string()))?;
        Ok(Some(manifest))
    }

    /// Delete an envelope manifest block without touching the ciphertext block.
    pub async fn delete_envelope_manifest(&self, manifest_cid: &KotobaCid) -> bool {
        self.inner.delete_block(manifest_cid).await
    }

    /// Unwrap the DEK for `recipient`.
    pub fn unwrap_envelope_dek(
        &self,
        manifest: &EnvelopeManifest,
        wrapping_key: &[u8; 32],
        recipient: &str,
    ) -> Result<Zeroizing<[u8; 32]>, kotoba_crypto::aead::CryptoError> {
        validate_envelope_recipient(recipient)?;
        manifest
            .validate()
            .map_err(|e| kotoba_crypto::aead::CryptoError::InvalidEnvelope(e.to_string()))?;
        let wrap = manifest.wrap_for(recipient).ok_or_else(|| {
            kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
                "missing envelope wrap for recipient: {recipient}"
            ))
        })?;
        if wrap.wrap_alg != EnvelopeKeyWrap::WRAP_ALG_AES_256_GCM {
            return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
                "unsupported wrap algorithm: {}",
                wrap.wrap_alg
            )));
        }
        let wrap_aad = envelope_wrap_aad(&manifest.ct_cid, recipient, &manifest.aad)?;
        let dek_bytes = unwrap_key(wrapping_key, &wrap.wrapped_dek, &wrap_aad)?;
        if dek_bytes.len() != 32 {
            return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
                "DEK has wrong length: {}",
                dek_bytes.len()
            )));
        }
        let mut dek = Zeroizing::new([0u8; 32]);
        dek.copy_from_slice(&dek_bytes);
        Ok(dek)
    }

    /// Retrieve and decrypt a blob described by an envelope manifest.
    pub async fn get_enveloped(
        &self,
        manifest: &EnvelopeManifest,
        wrapping_key: &[u8; 32],
        recipient: &str,
    ) -> Result<Option<Bytes>, kotoba_crypto::aead::CryptoError> {
        manifest
            .validate()
            .map_err(|e| kotoba_crypto::aead::CryptoError::InvalidEnvelope(e.to_string()))?;
        let Some(ct) = self.inner.get(&manifest.ct_cid).await else {
            return Ok(None);
        };
        let dek = self.unwrap_envelope_dek(manifest, wrapping_key, recipient)?;
        let pt = kotoba_crypto::aead::open_with_aad(&dek, &ct, &manifest.aad)?;
        Ok(Some(Bytes::from(pt.to_vec())))
    }

    /// Retrieve and decrypt a blob through `DataPolicy::Enveloped`.
    ///
    /// This is the intended upper-layer read path: the policy points to the
    /// current manifest, and the manifest must point back to the same
    /// ciphertext CID. A mismatch is rejected so a policy cannot be silently
    /// paired with a different manifest.
    pub async fn get_enveloped_policy(
        &self,
        policy: &DataPolicy,
        wrapping_key: &[u8; 32],
        recipient: &str,
    ) -> Result<Option<Bytes>, kotoba_crypto::aead::CryptoError> {
        let DataPolicy::Enveloped {
            ct_cid,
            manifest_cid,
        } = policy
        else {
            return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(
                "expected DataPolicy::Enveloped".to_string(),
            ));
        };
        let Some(manifest) = self.get_envelope_manifest(manifest_cid).await? else {
            return Ok(None);
        };
        if &manifest.ct_cid != ct_cid {
            return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
                "policy ct_cid {} does not match manifest ct_cid {}",
                ct_cid.to_multibase(),
                manifest.ct_cid.to_multibase()
            )));
        }
        self.get_enveloped(&manifest, wrapping_key, recipient).await
    }
}

fn envelope_wrap_aad(
    ct_cid: &KotobaCid,
    recipient: &str,
    aad: &[u8],
) -> Result<Vec<u8>, kotoba_crypto::aead::CryptoError> {
    let cid = ct_cid.to_multibase();
    let cid_len = u32::try_from(cid.len()).map_err(|_| {
        kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
            "ciphertext CID label too large for envelope wrap AAD: {} bytes",
            cid.len()
        ))
    })?;
    let recipient_len = u32::try_from(recipient.len()).map_err(|_| {
        kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
            "recipient too large for envelope wrap AAD: {} bytes",
            recipient.len()
        ))
    })?;
    let mut out = Vec::with_capacity(4 + cid.len() + 4 + recipient.len() + aad.len());
    out.extend_from_slice(&cid_len.to_be_bytes());
    out.extend_from_slice(cid.as_bytes());
    out.extend_from_slice(&recipient_len.to_be_bytes());
    out.extend_from_slice(recipient.as_bytes());
    out.extend_from_slice(aad);
    Ok(out)
}

fn validate_envelope_recipient(recipient: &str) -> Result<(), kotoba_crypto::aead::CryptoError> {
    if recipient.is_empty() {
        return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(
            "envelope recipient is empty".to_string(),
        ));
    }
    if recipient.len() > EnvelopeManifest::MAX_RECIPIENT_LEN {
        return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
            "envelope recipient too large: {} bytes > {}",
            recipient.len(),
            EnvelopeManifest::MAX_RECIPIENT_LEN
        )));
    }
    if !recipient.bytes().all(|byte| (0x21..=0x7e).contains(&byte)) {
        return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(
            "envelope recipient must be visible ASCII".to_string(),
        ));
    }
    Ok(())
}

fn validate_envelope_aad(aad: &[u8]) -> Result<(), kotoba_crypto::aead::CryptoError> {
    if aad.len() > EnvelopeManifest::MAX_AAD_LEN {
        return Err(kotoba_crypto::aead::CryptoError::InvalidEnvelope(format!(
            "envelope AAD too large: {} bytes > {}",
            aad.len(),
            EnvelopeManifest::MAX_AAD_LEN
        )));
    }
    Ok(())
}

impl Default for SecureVault {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::Bytes;

    fn random_key() -> [u8; 32] {
        let mut k = [0u8; 32];
        rand::RngCore::fill_bytes(&mut rand::thread_rng(), &mut k);
        k
    }

    #[test]
    fn envelope_wrap_aad_is_length_prefixed() {
        let cid = KotobaCid::from_bytes(b"ciphertext block");
        let cid_label = cid.to_multibase();

        let got = envelope_wrap_aad(&cid, "did:example:alice", b"slot").unwrap();

        let mut expected = Vec::new();
        expected.extend_from_slice(&(cid_label.len() as u32).to_be_bytes());
        expected.extend_from_slice(cid_label.as_bytes());
        expected.extend_from_slice(&(b"did:example:alice".len() as u32).to_be_bytes());
        expected.extend_from_slice(b"did:example:alice");
        expected.extend_from_slice(b"slot");
        assert_eq!(got, expected);
    }

    #[test]
    fn envelope_wrap_aad_keeps_tuple_boundaries_unambiguous() {
        let cid_a = KotobaCid::from_bytes(b"ciphertext");
        let cid_b = KotobaCid::from_bytes(b"ciphertextdid:example:a");

        let cid_boundary_a = envelope_wrap_aad(&cid_a, "did:example:a", b"b").unwrap();
        let cid_boundary_b = envelope_wrap_aad(&cid_b, "", b"b").unwrap();
        assert_ne!(cid_boundary_a, cid_boundary_b);

        let recipient_boundary_a = envelope_wrap_aad(&cid_a, "did:example:a", b"bc").unwrap();
        let recipient_boundary_b = envelope_wrap_aad(&cid_a, "did:example:ab", b"c").unwrap();
        assert_ne!(recipient_boundary_a, recipient_boundary_b);
    }

    #[tokio::test]
    async fn put_get_roundtrip() {
        let sv = SecureVault::new();
        let key = random_key();
        let data = Bytes::from_static(b"secret payload");
        let blob_ref = sv.put(&key, data.clone()).await.unwrap();
        let got = sv.get(&key, &blob_ref).await.unwrap().unwrap();
        assert_eq!(got, data);
    }

    #[tokio::test]
    async fn wrong_key_returns_error() {
        let sv = SecureVault::new();
        let key = random_key();
        let wrong = random_key();
        let blob_ref = sv
            .put(&key, Bytes::from_static(b"top secret"))
            .await
            .unwrap();
        assert!(sv.get(&wrong, &blob_ref).await.is_err());
    }

    #[tokio::test]
    async fn put_with_policy_returns_encrypted_data_policy() {
        use kotoba_core::{cid::KotobaCid, DataPolicy};
        let sv = SecureVault::new();
        let key = random_key();
        let plaintext = Bytes::from_static(b"policy test");
        let policy_cid = KotobaCid::from_bytes(b"fake-pre-key-registry-entry");
        let (blob_ref, policy) = sv
            .put_with_policy(&key, plaintext.clone(), policy_cid.clone())
            .await
            .unwrap();
        match policy {
            DataPolicy::Encrypted {
                ct_cid,
                policy_cid: pcid,
            } => {
                assert_eq!(ct_cid, blob_ref.cid);
                assert_eq!(pcid, policy_cid);
            }
            other => panic!("expected Encrypted policy, got {other:?}"),
        }
        // Decrypt must still work via the existing get() path.
        let got = sv.get(&key, &blob_ref).await.unwrap().unwrap();
        assert_eq!(got, plaintext);
    }

    #[tokio::test]
    async fn raw_vault_holds_ciphertext_not_plaintext() {
        let sv = SecureVault::new();
        let key = random_key();
        let plaintext = Bytes::from_static(b"must not be plaintext in store");
        let blob_ref = sv.put(&key, plaintext.clone()).await.unwrap();
        // Read raw bytes from the underlying vault — should differ from plaintext
        let raw = sv.inner.get(&blob_ref.cid).await.unwrap();
        assert_ne!(raw, plaintext);
    }

    #[tokio::test]
    async fn default_creates_valid_vault() {
        let sv = SecureVault::default();
        let key = random_key();
        let data = Bytes::from_static(b"default test");
        let blob_ref = sv.put(&key, data.clone()).await.unwrap();
        let got = sv.get(&key, &blob_ref).await.unwrap().unwrap();
        assert_eq!(got, data);
    }

    #[tokio::test]
    async fn contains_returns_true_after_put() {
        let sv = SecureVault::new();
        let key = random_key();
        let blob_ref = sv
            .put(&key, Bytes::from_static(b"check contains"))
            .await
            .unwrap();
        assert!(sv.contains(&blob_ref).await);
    }

    #[tokio::test]
    async fn contains_returns_false_for_missing() {
        use crate::vault::BlobRef;
        use kotoba_core::cid::KotobaCid;

        let sv = SecureVault::new();
        let fake_ref = BlobRef {
            cid: KotobaCid::from_bytes(b"nonexistent"),
            size: 0,
            mime_type: None,
            chunked: false,
        };
        assert!(!sv.contains(&fake_ref).await);
    }

    #[tokio::test]
    async fn get_returns_none_for_missing_blob() {
        use crate::vault::BlobRef;
        use kotoba_core::cid::KotobaCid;

        let sv = SecureVault::new();
        let key = random_key();
        let fake_ref = BlobRef {
            cid: KotobaCid::from_bytes(b"absent"),
            size: 0,
            mime_type: None,
            chunked: false,
        };
        let result = sv.get(&key, &fake_ref).await.unwrap();
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn different_plaintexts_different_blob_refs() {
        let sv = SecureVault::new();
        let key = random_key();
        let ref1 = sv.put(&key, Bytes::from_static(b"alpha")).await.unwrap();
        let ref2 = sv.put(&key, Bytes::from_static(b"beta")).await.unwrap();
        // Different plaintexts → different CIDs (AES-GCM nonce is random)
        assert_ne!(ref1.cid, ref2.cid);
    }

    #[tokio::test]
    async fn put_bound_get_bound_roundtrip() {
        let sv = SecureVault::new();
        let key = random_key();
        let aad = b"kotoba://graph/bafyManimaniIntake";
        let data = Bytes::from_static(b"private email body");
        let blob_ref = sv.put_bound(&key, data.clone(), aad).await.unwrap();
        let got = sv.get_bound(&key, &blob_ref, aad).await.unwrap().unwrap();
        assert_eq!(got, data);
    }

    #[tokio::test]
    async fn put_with_policy_bound_returns_encrypted_policy_and_decrypts() {
        use kotoba_core::{cid::KotobaCid, DataPolicy};
        let sv = SecureVault::new();
        let key = random_key();
        let aad = b"kotoba://graph/intake-policy";
        let plaintext = Bytes::from_static(b"bound policy payload");
        let policy_cid = KotobaCid::from_bytes(b"pre-key-registry-entry");
        let (blob_ref, policy) = sv
            .put_with_policy_bound(&key, plaintext.clone(), aad, policy_cid.clone())
            .await
            .unwrap();
        match policy {
            DataPolicy::Encrypted {
                ct_cid,
                policy_cid: pcid,
            } => {
                assert_eq!(ct_cid, blob_ref.cid);
                assert_eq!(pcid, policy_cid);
            }
            other => panic!("expected Encrypted policy, got {other:?}"),
        }
        // Same aad decrypts; wrong aad fails.
        let got = sv.get_bound(&key, &blob_ref, aad).await.unwrap().unwrap();
        assert_eq!(got, plaintext);
        assert!(sv.get_bound(&key, &blob_ref, b"other").await.is_err());
    }

    #[tokio::test]
    async fn put_bound_empty_plaintext_roundtrips() {
        let sv = SecureVault::new();
        let key = random_key();
        let blob_ref = sv.put_bound(&key, Bytes::new(), b"slot").await.unwrap();
        let got = sv
            .get_bound(&key, &blob_ref, b"slot")
            .await
            .unwrap()
            .unwrap();
        assert_eq!(got.len(), 0);
    }

    #[tokio::test]
    async fn get_bound_wrong_aad_fails() {
        // A blob sealed for one logical slot must not decrypt under another slot.
        let sv = SecureVault::new();
        let key = random_key();
        let blob_ref = sv
            .put_bound(&key, Bytes::from_static(b"slot A"), b"slot-A")
            .await
            .unwrap();
        assert!(sv.get_bound(&key, &blob_ref, b"slot-B").await.is_err());
    }

    #[tokio::test]
    async fn empty_plaintext_roundtrip() {
        let sv = SecureVault::new();
        let key = random_key();
        let blob_ref = sv.put(&key, Bytes::new()).await.unwrap();
        let got = sv.get(&key, &blob_ref).await.unwrap().unwrap();
        assert_eq!(got.len(), 0);
    }

    // ── Cross-method binding: the slot-AAD cannot be stripped by switching getters ──

    #[tokio::test]
    async fn bound_blob_not_readable_by_plain_get() {
        // A blob sealed for a logical slot (non-empty AAD) must NOT be decryptable
        // via the unbound `get`, which uses an empty AAD. Otherwise a caller could
        // strip the slot-binding simply by calling the wrong getter — defeating the
        // D2 binding even with the correct key.
        let sv = SecureVault::new();
        let key = random_key();
        let blob_ref = sv
            .put_bound(&key, Bytes::from_static(b"personal record"), b"slot-A")
            .await
            .unwrap();
        assert!(
            sv.get(&key, &blob_ref).await.is_err(),
            "slot-bound blob must not decrypt under the unbound (empty-AAD) getter"
        );
        // The correctly-bound read still works (not a vacuous rejection).
        assert_eq!(
            sv.get_bound(&key, &blob_ref, b"slot-A")
                .await
                .unwrap()
                .unwrap(),
            Bytes::from_static(b"personal record")
        );
    }

    #[tokio::test]
    async fn plain_blob_not_readable_by_get_bound_with_nonempty_aad() {
        // The converse: a plain (unbound) blob must not decrypt under a non-empty
        // slot AAD — a caller can't retroactively claim it belongs to a slot.
        let sv = SecureVault::new();
        let key = random_key();
        let blob_ref = sv.put(&key, Bytes::from_static(b"loose")).await.unwrap();
        assert!(
            sv.get_bound(&key, &blob_ref, b"slot-A").await.is_err(),
            "unbound blob must not decrypt under a non-empty slot AAD"
        );
    }

    #[tokio::test]
    async fn plain_blob_readable_by_get_bound_empty_aad() {
        // Consistency boundary: empty AAD is the identity, so a plain blob is exactly
        // a slot-bound blob with the empty slot. get_bound(b"") must equal plain get.
        // This pins the equivalence the two methods rely on at the vault layer.
        let sv = SecureVault::new();
        let key = random_key();
        let blob_ref = sv.put(&key, Bytes::from_static(b"loose")).await.unwrap();
        assert_eq!(
            sv.get_bound(&key, &blob_ref, b"").await.unwrap().unwrap(),
            Bytes::from_static(b"loose"),
            "empty-AAD bound read must match the plain read"
        );
    }

    #[tokio::test]
    async fn put_get_enveloped_roundtrip() {
        let sv = SecureVault::new();
        let wrapping_key = random_key();
        let plaintext = Bytes::from_static(b"future-rotatable secret");
        let aad = b"kotoba://graph/envelope";

        let (blob_ref, manifest_cid, manifest) = sv
            .put_enveloped(&wrapping_key, "did:example:alice", plaintext.clone(), aad)
            .await
            .unwrap();

        assert_eq!(manifest.ct_cid, blob_ref.cid);
        assert_ne!(
            manifest_cid, blob_ref.cid,
            "manifest and ciphertext are separate blocks"
        );
        assert_eq!(manifest.aad, aad);

        let loaded = sv
            .get_envelope_manifest(&manifest_cid)
            .await
            .unwrap()
            .expect("manifest must be stored");
        assert_eq!(loaded, manifest);

        let got = sv
            .get_enveloped(&manifest, &wrapping_key, "did:example:alice")
            .await
            .unwrap()
            .unwrap();
        assert_eq!(got, plaintext);
    }

    #[tokio::test]
    async fn put_enveloped_with_policy_returns_manifest_policy() {
        let sv = SecureVault::new();
        let wrapping_key = random_key();
        let (blob_ref, policy, manifest) = sv
            .put_enveloped_with_policy(
                &wrapping_key,
                "did:example:alice",
                Bytes::from_static(b"policy-bound envelope"),
                b"policy-slot",
            )
            .await
            .unwrap();

        match &policy {
            DataPolicy::Enveloped {
                ct_cid,
                manifest_cid,
            } => {
                assert_eq!(ct_cid, &blob_ref.cid);
                let loaded = sv
                    .get_envelope_manifest(manifest_cid)
                    .await
                    .unwrap()
                    .expect("manifest must be stored");
                assert_eq!(loaded, manifest);
            }
            other => panic!("expected Enveloped policy, got {other:?}"),
        }

        let got = sv
            .get_enveloped_policy(&policy, &wrapping_key, "did:example:alice")
            .await
            .unwrap()
            .unwrap();
        assert_eq!(got, Bytes::from_static(b"policy-bound envelope"));
    }

    #[tokio::test]
    async fn envelope_rewrap_changes_manifest_not_ciphertext() {
        let sv = SecureVault::new();
        let alice_key = random_key();
        let bob_key = random_key();
        let plaintext = Bytes::from_static(b"do not rewrite ciphertext");

        let (blob_ref, manifest_cid_a, manifest_a) = sv
            .put_enveloped(
                &alice_key,
                "did:example:alice",
                plaintext.clone(),
                b"slot-1",
            )
            .await
            .unwrap();

        let dek = sv
            .unwrap_envelope_dek(&manifest_a, &alice_key, "did:example:alice")
            .unwrap();
        let (manifest_cid_b, manifest_b) = sv
            .put_envelope_manifest_with_wrap(manifest_a.clone(), &bob_key, "did:example:bob", &dek)
            .await
            .unwrap();

        assert_eq!(manifest_b.ct_cid, blob_ref.cid);
        assert_eq!(manifest_b.ct_cid, manifest_a.ct_cid);
        assert_ne!(manifest_cid_a, manifest_cid_b);
        assert_eq!(manifest_b.dek_wraps.len(), 2);

        let got_bob = sv
            .get_enveloped(&manifest_b, &bob_key, "did:example:bob")
            .await
            .unwrap()
            .unwrap();
        assert_eq!(got_bob, plaintext);
    }

    #[tokio::test]
    async fn delete_envelope_manifest_leaves_ciphertext_block_readable_with_retained_manifest() {
        let sv = SecureVault::new();
        let wrapping_key = random_key();
        let plaintext = Bytes::from_static(b"delete only manifest");

        let (_blob_ref, manifest_cid, manifest) = sv
            .put_enveloped(
                &wrapping_key,
                "did:example:alice",
                plaintext.clone(),
                b"slot-delete",
            )
            .await
            .unwrap();

        assert!(sv.delete_envelope_manifest(&manifest_cid).await);
        assert!(sv
            .get_envelope_manifest(&manifest_cid)
            .await
            .unwrap()
            .is_none());

        let got = sv
            .get_enveloped(&manifest, &wrapping_key, "did:example:alice")
            .await
            .unwrap()
            .unwrap();
        assert_eq!(got, plaintext);
    }

    #[tokio::test]
    async fn envelope_wrong_recipient_or_key_fails() {
        let sv = SecureVault::new();
        let wrapping_key = random_key();
        let wrong_key = random_key();
        let (_blob_ref, _manifest_cid, manifest) = sv
            .put_enveloped(
                &wrapping_key,
                "did:example:alice",
                Bytes::from_static(b"secret"),
                b"slot-2",
            )
            .await
            .unwrap();

        assert!(sv
            .get_enveloped(&manifest, &wrapping_key, "did:example:bob")
            .await
            .is_err());
        assert!(sv
            .get_enveloped(&manifest, &wrong_key, "did:example:alice")
            .await
            .is_err());
    }

    #[tokio::test]
    async fn envelope_tampered_aad_fails() {
        let sv = SecureVault::new();
        let wrapping_key = random_key();
        let (_blob_ref, _manifest_cid, mut manifest) = sv
            .put_enveloped(
                &wrapping_key,
                "did:example:alice",
                Bytes::from_static(b"slot-bound"),
                b"original-slot",
            )
            .await
            .unwrap();
        manifest.aad = b"tampered-slot".to_vec();

        assert!(sv
            .get_enveloped(&manifest, &wrapping_key, "did:example:alice")
            .await
            .is_err());
    }

    #[tokio::test]
    async fn get_enveloped_policy_rejects_ct_manifest_mismatch() {
        let sv = SecureVault::new();
        let wrapping_key = random_key();
        let (_blob_ref, policy, _manifest) = sv
            .put_enveloped_with_policy(
                &wrapping_key,
                "did:example:alice",
                Bytes::from_static(b"policy mismatch"),
                b"policy-mismatch-slot",
            )
            .await
            .unwrap();

        let DataPolicy::Enveloped { manifest_cid, .. } = policy else {
            panic!("expected enveloped policy");
        };
        let tampered_policy = DataPolicy::Enveloped {
            ct_cid: KotobaCid::from_bytes(b"different ciphertext"),
            manifest_cid,
        };

        assert!(sv
            .get_enveloped_policy(&tampered_policy, &wrapping_key, "did:example:alice")
            .await
            .is_err());
    }

    #[tokio::test]
    async fn put_enveloped_rejects_invalid_recipient_and_oversized_aad_before_storing() {
        let sv = SecureVault::new();
        let wrapping_key = random_key();

        assert!(sv
            .put_enveloped(
                &wrapping_key,
                "did:example:bad recipient",
                Bytes::from_static(b"secret"),
                b"slot",
            )
            .await
            .is_err());
        assert!(sv
            .put_enveloped(
                &wrapping_key,
                "did:example:alice",
                Bytes::from_static(b"secret"),
                &vec![0u8; EnvelopeManifest::MAX_AAD_LEN + 1],
            )
            .await
            .is_err());
    }

    #[tokio::test]
    async fn put_envelope_manifest_rejects_oversized_cbor_block() {
        let sv = SecureVault::new();
        let manifest = EnvelopeManifest::new(
            KotobaCid::from_bytes(b"large envelope ciphertext"),
            Vec::new(),
            (0..EnvelopeManifest::MAX_DEK_WRAP_COUNT)
                .map(|idx| {
                    EnvelopeKeyWrap::aes_256_gcm(
                        format!("did:example:user{idx}"),
                        vec![idx as u8; 9 * 1024],
                    )
                })
                .collect(),
        );

        assert!(manifest.validate().is_ok());
        assert!(sv.put_envelope_manifest(&manifest).await.is_err());
    }

    #[tokio::test]
    async fn put_envelope_manifest_stores_large_cbor_as_raw_manifest_cid() {
        let sv = SecureVault::new();
        let manifest = EnvelopeManifest::new(
            KotobaCid::from_bytes(b"large readable envelope ciphertext"),
            Vec::new(),
            (0..96)
                .map(|idx| {
                    EnvelopeKeyWrap::aes_256_gcm(
                        format!("did:example:large{idx}"),
                        vec![idx as u8; 2 * 1024],
                    )
                })
                .collect(),
        );
        let mut cbor = Vec::new();
        ciborium::into_writer(&manifest, &mut cbor).expect("manifest CBOR");
        assert!(
            cbor.len() > 128 * 1024,
            "test setup must exceed Vault's single-block threshold"
        );
        assert!(
            cbor.len() < MAX_ENVELOPE_MANIFEST_CBOR_BYTES,
            "test setup must stay within the envelope manifest size cap"
        );
        let expected_cid = KotobaCid::from_bytes(&cbor);

        let manifest_cid = sv
            .put_envelope_manifest(&manifest)
            .await
            .expect("put large readable manifest");
        assert_eq!(
            manifest_cid, expected_cid,
            "envelope manifest CID must be the raw CBOR CID, not a Vault chunk-manifest CID"
        );
        let loaded = sv
            .get_envelope_manifest(&manifest_cid)
            .await
            .expect("get large readable manifest")
            .expect("manifest exists");
        assert_eq!(loaded, manifest);
    }

    #[tokio::test]
    async fn get_envelope_manifest_rejects_oversized_cbor_block_before_decoding() {
        let sv = SecureVault::new();
        let blob_ref = sv
            .inner
            .put(Bytes::from(vec![0u8; MAX_ENVELOPE_MANIFEST_CBOR_BYTES + 1]))
            .await;

        assert!(sv.get_envelope_manifest(&blob_ref.cid).await.is_err());
    }

    #[tokio::test]
    async fn get_envelope_manifest_rejects_cid_mismatch_before_decoding() {
        let sv = SecureVault::new();
        let blob_ref = sv
            .inner
            .put_typed(Bytes::from(vec![7u8; 600 * 1024]), "video/mp4".to_string())
            .await;
        assert!(blob_ref.chunked, "test setup must produce a chunked blob");

        let err = sv
            .get_envelope_manifest(&blob_ref.cid)
            .await
            .expect_err("CID-mismatched manifest bytes must be rejected");
        assert!(
            err.to_string().contains("envelope manifest CID mismatch"),
            "unexpected error: {err}"
        );
    }
}
