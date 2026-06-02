//! `AgentCrypto` — opaque encryption engine trait.
//!
//! The agent can encrypt and decrypt data but never accesses raw key bytes.
//! Implementations hold vault key material in `Zeroizing<[u8;32]>` with no
//! public accessor.
//!
//! ## signal:v1: envelope
//! All encrypted text fields use the `signal:v1:<base64>` envelope so stored
//! ciphertext is identifiable and versioned.

use async_trait::async_trait;
use zeroize::Zeroizing;

use crate::{
    aead::{open, seal, CryptoError},
    envelope::{decode_envelope, encode_envelope},
    hkdf::derive_key_with_salt,
    key_tree::derive_storage_key,
};

/// Bind a caller context (`aad`) into a scope label so a ciphertext sealed for
/// one logical slot cannot be opened under another. Length-prefixing `scope`
/// makes the `(scope, aad)` pair unambiguous (ADR-2606014000 D2). Used by the
/// default `encrypt_bound` / `decrypt_bound` trait methods.
fn bind_scope(scope: &[u8], aad: &[u8]) -> Vec<u8> {
    let mut s = Vec::with_capacity(scope.len() + aad.len() + 4);
    s.extend_from_slice(&(scope.len() as u32).to_be_bytes());
    s.extend_from_slice(scope);
    s.extend_from_slice(aad);
    s
}

/// Opaque encryption-engine trait.
///
/// Implementors hold key material without exposing raw bytes.
/// All methods are `async` to allow future hardware-backed keys.
#[async_trait]
pub trait AgentCrypto: Send + Sync + 'static {
    /// Encrypt `plaintext` using a scope-derived key.
    ///
    /// `scope` is a domain label such as `"email/from"` used to derive a
    /// per-field subkey via HKDF.  The returned bytes are raw AES-GCM output
    /// (`nonce || ciphertext`) — NOT yet envelope-encoded.
    async fn encrypt(&self, scope: &[u8], plaintext: &[u8]) -> Result<Vec<u8>, CryptoError>;

    /// Decrypt bytes produced by `encrypt`.
    async fn decrypt(
        &self,
        scope: &[u8],
        ciphertext: &[u8],
    ) -> Result<Zeroizing<Vec<u8>>, CryptoError>;

    /// Derive a deterministic 32-byte wrapping key bound to this node's vault
    /// key and `owner_did`.
    ///
    /// Used by the operator-trusted PRE layer (ADR-2605240001 §28.4(a)) as the
    /// `owner_enc_key` argument to `PreKeyRegistry::grant`/`get_rekey_authed`.
    /// Only the node (the Consensys/Infura-layer operator) can derive this key,
    /// because it is bound to the node's opaque vault key; external or
    /// other-tenant principals cannot reconstruct it. Deterministic (no nonce)
    /// so the same `(node, owner_did)` pair always wraps and unwraps the same
    /// grants. This is intentionally NOT zero-knowledge from the operator —
    /// that property belongs to the kotoba/etzhayyim protocol layer, not this
    /// vendor-hosted (Infura-equivalent) service.
    fn derive_wrapping_key(&self, owner_did: &[u8]) -> Zeroizing<[u8; 32]>;

    /// Encrypt a UTF-8 text field and return a `signal:v1:<base64>` envelope.
    async fn seal_field(&self, scope: &[u8], text: &str) -> Result<String, CryptoError> {
        let ct = self.encrypt(scope, text.as_bytes()).await?;
        Ok(encode_envelope(&ct))
    }

    /// Decrypt a `signal:v1:<base64>` envelope and return the UTF-8 text.
    async fn open_field(&self, scope: &[u8], envelope: &str) -> Result<String, CryptoError> {
        let ct = decode_envelope(envelope)?;
        let mut pt = self.decrypt(scope, &ct).await?;
        // Move the inner Vec out without cloning to avoid an extra plaintext copy.
        // `pt` is left holding an empty Vec (zeroized on drop — no-op for empty).
        let inner = std::mem::take(&mut *pt);
        String::from_utf8(inner)
            .map_err(|e| CryptoError::InvalidEnvelope(format!("UTF-8 decode: {e}")))
    }

    /// Encrypt a blob directly (no envelope encoding — for vault blob storage).
    async fn encrypt_blob(&self, plaintext: &[u8]) -> Result<Vec<u8>, CryptoError> {
        self.encrypt(b"blob", plaintext).await
    }

    /// Decrypt a blob produced by `encrypt_blob`.
    async fn decrypt_blob(&self, ciphertext: &[u8]) -> Result<Zeroizing<Vec<u8>>, CryptoError> {
        self.decrypt(b"blob", ciphertext).await
    }

    /// Context-bound encrypt (ADR-2606014000 D2). `aad` is a logical slot — e.g.
    /// the owning graph/datom CID — folded into the scope-key derivation, so a
    /// ciphertext sealed for one slot cannot be opened under another. Default
    /// implementation requires no impl change (works through `dyn AgentCrypto`).
    async fn encrypt_bound(
        &self,
        scope: &[u8],
        aad: &[u8],
        plaintext: &[u8],
    ) -> Result<Vec<u8>, CryptoError> {
        self.encrypt(&bind_scope(scope, aad), plaintext).await
    }

    /// Context-bound decrypt. `aad` MUST equal the value used by `encrypt_bound`.
    async fn decrypt_bound(
        &self,
        scope: &[u8],
        aad: &[u8],
        ciphertext: &[u8],
    ) -> Result<Zeroizing<Vec<u8>>, CryptoError> {
        self.decrypt(&bind_scope(scope, aad), ciphertext).await
    }

    /// PII-blob encrypt bound to its owning context (`aad`). The intended call
    /// for manimani intake bodies: `encrypt_blob_bound(intake_subject_cid, body)`.
    async fn encrypt_blob_bound(
        &self,
        aad: &[u8],
        plaintext: &[u8],
    ) -> Result<Vec<u8>, CryptoError> {
        self.encrypt_bound(b"blob", aad, plaintext).await
    }

    /// Decrypt a blob produced by `encrypt_blob_bound`.
    async fn decrypt_blob_bound(
        &self,
        aad: &[u8],
        ciphertext: &[u8],
    ) -> Result<Zeroizing<Vec<u8>>, CryptoError> {
        self.decrypt_bound(b"blob", aad, ciphertext).await
    }
}

/// A key-material-backed implementation of `AgentCrypto`.
///
/// The vault key is held in `Zeroizing<[u8;32]>` — no raw accessor is exposed.
/// Scope subkeys are derived with HKDF: `scope_key = HKDF(vault_key, salt=scope, info=b"kotoba/scope-key/v1")`.
pub struct VaultKeyedCrypto {
    vault_key: Zeroizing<[u8; 32]>,
}

impl VaultKeyedCrypto {
    /// Wrap an existing 32-byte vault key.  The caller must already hold the
    /// key in a `Zeroizing` allocation; this moves ownership in.
    pub fn new(vault_key: Zeroizing<[u8; 32]>) -> Self {
        Self { vault_key }
    }

    /// Construct the storage-encryption engine from the passkey-rooted Account
    /// Root Key (ADR-2606014000): `vault_key = k_storage = HKDF(ARK, "storage")`.
    /// This sources the PII engine from the device-derived key hierarchy instead
    /// of a server-held key or env var, satisfying the no-server-key invariant.
    pub fn from_ark(ark: &[u8; 32]) -> Self {
        Self {
            vault_key: Zeroizing::new(derive_storage_key(ark)),
        }
    }

    fn scope_key(&self, scope: &[u8]) -> [u8; 32] {
        derive_key_with_salt(self.vault_key.as_ref(), scope, b"kotoba/scope-key/v1")
    }
}

#[async_trait]
impl AgentCrypto for VaultKeyedCrypto {
    async fn encrypt(&self, scope: &[u8], plaintext: &[u8]) -> Result<Vec<u8>, CryptoError> {
        let sk = self.scope_key(scope);
        seal(&sk, plaintext)
    }

    async fn decrypt(
        &self,
        scope: &[u8],
        ciphertext: &[u8],
    ) -> Result<Zeroizing<Vec<u8>>, CryptoError> {
        let sk = self.scope_key(scope);
        open(&sk, ciphertext)
    }

    fn derive_wrapping_key(&self, owner_did: &[u8]) -> Zeroizing<[u8; 32]> {
        // Distinct `info` from scope_key so a PRE wrapping key never collides
        // with a field-encryption scope key derived for the same label.
        Zeroizing::new(derive_key_with_salt(
            self.vault_key.as_ref(),
            owner_did,
            b"kotoba/pre-wrap/v1",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_crypto() -> VaultKeyedCrypto {
        let key = Zeroizing::new([0x42u8; 32]);
        VaultKeyedCrypto::new(key)
    }

    #[tokio::test]
    async fn encrypt_decrypt_roundtrip() {
        let c = test_crypto();
        let scope = b"email/body";
        let msg = b"Hello, world!";
        let ct = c.encrypt(scope, msg).await.unwrap();
        let pt = c.decrypt(scope, &ct).await.unwrap();
        assert_eq!(pt.as_slice(), msg);
    }

    #[test]
    fn derive_wrapping_key_is_deterministic_and_owner_bound() {
        let c = test_crypto();
        let k1 = c.derive_wrapping_key(b"did:plc:alice");
        let k2 = c.derive_wrapping_key(b"did:plc:alice");
        let k_other = c.derive_wrapping_key(b"did:plc:bob");
        // Deterministic: same (node, owner) → same wrapping key (wrap/unwrap parity).
        assert_eq!(k1.as_ref(), k2.as_ref());
        // Owner-bound: different owner → different key.
        assert_ne!(k1.as_ref(), k_other.as_ref());
    }

    #[test]
    fn derive_wrapping_key_is_bound_to_vault_key() {
        let a = VaultKeyedCrypto::new(Zeroizing::new([0x11u8; 32]));
        let b = VaultKeyedCrypto::new(Zeroizing::new([0x22u8; 32]));
        // Different node vault keys → different wrapping key for the same owner.
        // (External principals cannot reconstruct the node's wrapping key.)
        assert_ne!(
            a.derive_wrapping_key(b"did:plc:alice").as_ref(),
            b.derive_wrapping_key(b"did:plc:alice").as_ref()
        );
    }

    #[test]
    fn derive_wrapping_key_differs_from_scope_key_same_label() {
        // Distinct HKDF `info` must keep a PRE wrapping key separate from a
        // field-encryption scope key derived for the same label.
        let c = test_crypto();
        let label = b"did:plc:alice";
        assert_ne!(c.derive_wrapping_key(label).as_ref(), &c.scope_key(label));
    }

    #[tokio::test]
    async fn different_scopes_produce_different_ciphertext() {
        let c = test_crypto();
        let msg = b"same message";
        let ct1 = c.encrypt(b"scope-a", msg).await.unwrap();
        let ct2 = c.encrypt(b"scope-b", msg).await.unwrap();
        // Different scope keys → different nonces or key, so ct differs
        assert_ne!(ct1, ct2);
    }

    #[tokio::test]
    async fn wrong_scope_fails_decrypt() {
        let c = test_crypto();
        let ct = c.encrypt(b"scope-a", b"secret").await.unwrap();
        // Decrypting with different scope → wrong key → OpenFailed
        assert!(c.decrypt(b"scope-b", &ct).await.is_err());
    }

    #[tokio::test]
    async fn seal_open_field_roundtrip() {
        let c = test_crypto();
        let text = "test@example.com";
        let envelope = c.seal_field(b"email/from", text).await.unwrap();
        assert!(envelope.starts_with("signal:v1:"), "envelope={envelope}");
        let recovered = c.open_field(b"email/from", &envelope).await.unwrap();
        assert_eq!(recovered, text);
    }

    #[tokio::test]
    async fn blob_encrypt_decrypt() {
        let c = test_crypto();
        let data = b"binary blob data";
        let ct = c.encrypt_blob(data).await.unwrap();
        let pt = c.decrypt_blob(&ct).await.unwrap();
        assert_eq!(pt.as_slice(), data);
    }

    #[tokio::test]
    async fn encrypt_empty_plaintext_roundtrip() {
        let c = test_crypto();
        let ct = c.encrypt(b"scope", b"").await.unwrap();
        let pt = c.decrypt(b"scope", &ct).await.unwrap();
        assert!(pt.is_empty(), "empty plaintext must round-trip");
    }

    #[tokio::test]
    async fn seal_field_starts_with_signal_prefix() {
        let c = test_crypto();
        let env = c.seal_field(b"any-scope", "test value").await.unwrap();
        assert!(
            env.starts_with("signal:v1:"),
            "envelope must start with signal:v1:"
        );
    }

    #[tokio::test]
    async fn open_field_wrong_scope_returns_error() {
        let c = test_crypto();
        let env = c.seal_field(b"scope-correct", "hello").await.unwrap();
        let result = c.open_field(b"scope-wrong", &env).await;
        assert!(result.is_err(), "wrong scope must fail to open field");
    }

    #[tokio::test]
    async fn same_plaintext_different_scope_different_blob_ciphertext() {
        let c = test_crypto();
        let ct1 = c.encrypt_blob(b"same data").await.unwrap();
        let ct2 = c.encrypt_blob(b"same data").await.unwrap();
        // Nonces are random → ciphertexts differ even with same scope (b"blob")
        assert_ne!(ct1, ct2, "random nonces ensure ciphertexts differ");
    }

    #[tokio::test]
    async fn scope_key_derivation_produces_different_keys_per_scope() {
        let c = test_crypto();
        let msg = b"payload";
        let ct_a = c.encrypt(b"alpha", msg).await.unwrap();
        let ct_b = c.encrypt(b"beta", msg).await.unwrap();
        // Ciphertexts differ because scope keys differ (plus random nonces)
        assert_ne!(ct_a, ct_b);
    }

    #[tokio::test]
    async fn open_field_invalid_envelope_prefix_returns_error() {
        let c = test_crypto();
        let result = c.open_field(b"scope", "not-a-signal-value").await;
        assert!(result.is_err(), "must reject invalid envelope prefix");
    }

    // ── ARK-sourced engine + context-bound blobs (ADR-2606014000) ──────────

    #[tokio::test]
    async fn from_ark_is_deterministic_for_same_ark() {
        let ark = [0x11u8; 32];
        let c1 = VaultKeyedCrypto::from_ark(&ark);
        let c2 = VaultKeyedCrypto::from_ark(&ark);
        // Same ARK → same storage key → c2 can decrypt c1's bound blob.
        let aad = b"kotoba://graph/intake-1";
        let ct = c1.encrypt_blob_bound(aad, b"private body").await.unwrap();
        let pt = c2.decrypt_blob_bound(aad, &ct).await.unwrap();
        assert_eq!(pt.as_slice(), b"private body");
    }

    #[tokio::test]
    async fn from_ark_differs_per_ark() {
        let a = VaultKeyedCrypto::from_ark(&[0x01u8; 32]);
        let b = VaultKeyedCrypto::from_ark(&[0x02u8; 32]);
        let aad = b"slot";
        let ct = a.encrypt_blob_bound(aad, b"x").await.unwrap();
        // Different ARK → different storage key → cannot decrypt.
        assert!(b.decrypt_blob_bound(aad, &ct).await.is_err());
    }

    #[tokio::test]
    async fn encrypt_bound_wrong_aad_fails() {
        let c = test_crypto();
        let ct = c.encrypt_bound(b"blob", b"slot-A", b"data").await.unwrap();
        // Same engine + scope, different logical slot → must not decrypt.
        assert!(c.decrypt_bound(b"blob", b"slot-B", &ct).await.is_err());
    }

    #[tokio::test]
    async fn encrypt_bound_empty_aad_roundtrips() {
        // Empty AAD is a valid degenerate binding (equivalent to unbound scope).
        let c = test_crypto();
        let ct = c.encrypt_bound(b"blob", b"", b"data").await.unwrap();
        let pt = c.decrypt_bound(b"blob", b"", &ct).await.unwrap();
        assert_eq!(pt.as_slice(), b"data");
    }

    #[tokio::test]
    async fn encrypt_blob_bound_large_payload_roundtrips() {
        let c = test_crypto();
        let aad = b"kotoba://graph/big";
        let payload: Vec<u8> = (0u8..=255).cycle().take(8192).collect();
        let ct = c.encrypt_blob_bound(aad, &payload).await.unwrap();
        let pt = c.decrypt_blob_bound(aad, &ct).await.unwrap();
        assert_eq!(pt.as_slice(), payload.as_slice());
    }

    #[tokio::test]
    async fn bound_and_unbound_blob_use_distinct_keys() {
        // encrypt_blob (scope "blob", no aad) and encrypt_blob_bound (scope "blob"
        // folded with aad) must NOT cross-decrypt — the aad changes the key.
        let c = test_crypto();
        let unbound = c.encrypt_blob(b"x").await.unwrap();
        assert!(c.decrypt_blob_bound(b"slot", &unbound).await.is_err());
        let bound = c.encrypt_blob_bound(b"slot", b"x").await.unwrap();
        assert!(c.decrypt_blob(&bound).await.is_err());
    }

    #[tokio::test]
    async fn encrypt_blob_bound_roundtrip_via_dyn_trait() {
        // Confirm the bound methods work through a trait object (the ingest path
        // holds `Arc<dyn AgentCrypto>`).
        let c: std::sync::Arc<dyn AgentCrypto> =
            std::sync::Arc::new(VaultKeyedCrypto::from_ark(&[0x42u8; 32]));
        let aad = b"kotoba://datom/bafyIntakeSubject";
        let ct = c.encrypt_blob_bound(aad, b"email body PII").await.unwrap();
        let pt = c.decrypt_blob_bound(aad, &ct).await.unwrap();
        assert_eq!(pt.as_slice(), b"email body PII");
    }
}
