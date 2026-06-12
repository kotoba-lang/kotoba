//! `SovereignCrypto` — agent-sovereign key management (Layer 2).
//!
//! The vault key (`[u8; 32]`) is:
//!   1. Generated randomly at genesis,
//!   2. Wrapped (ECIES) with the agent's X25519 public key,
//!   3. Stored as a block in the `BlockStore`,
//!   4. A key-ref JSON `{ cid, version }` is written to `VaultStore`.
//!
//! The agent can encrypt/decrypt but **never** exposes raw key bytes.
//!
//! ## Key Pointer Storage
//! ```text
//! VaultStore key: "agent/crypto/{did_slug}/current.json"
//! VaultStore key: "agent/crypto/{did_slug}/v{N}.json"
//! ```
//!
//! Each pointer JSON: `{ "cid": "<multibase>", "version": N }`
//!
//! ## Key Rotation
//! Generate a new random vault key, wrap it, store the block, update the
//! `current.json` pointer, and archive the old pointer as `v{N}.json`.
//! Old wrapped-key blocks are retained for historical decryption.

use std::sync::Arc;

use anyhow::{anyhow, Context, Result};
use async_trait::async_trait;
use bytes::Bytes;
use serde::{Deserialize, Serialize};
use zeroize::Zeroizing;

use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use kotoba_crypto::hpke::{hpke_open, hpke_seal};
use kotoba_crypto::{AgentCrypto, CryptoError, VaultKeyedCrypto};

use crate::agent_identity::AgentIdentity;
use crate::store::VaultStore;

// ── Key pointer JSON ──────────────────────────────────────────────────────────

#[derive(Serialize, Deserialize, Debug, Clone)]
struct KeyRef {
    cid: String,
    version: u64,
}

// ── SovereignCrypto ──────────────────────────────────────────────────────────

/// Agent-sovereign crypto engine.
///
/// Wraps a `VaultKeyedCrypto` and manages key lifecycle (genesis, load,
/// rotation) against a `BlockStore` + `VaultStore`.
pub struct SovereignCrypto {
    inner: VaultKeyedCrypto,
}

impl SovereignCrypto {
    // ── Lifecycle ─────────────────────────────────────────────────────────

    /// Load the current vault key from storage, or generate a new one (genesis).
    ///
    /// Algorithm:
    ///   1. Check VaultStore for `agent/crypto/{slug}/current.json`
    ///   2. If present: load wrapped blob from BlockStore, HPKE-unwrap with agent sk
    ///   3. If absent: generate random key, wrap, store, write pointer
    pub async fn load_or_genesis(
        identity: &AgentIdentity,
        kse_store: &VaultStore,
        block_store: &Arc<dyn BlockStore + Send + Sync>,
    ) -> Result<Self> {
        let slug = identity.did_slug();
        let cur_key = format!("agent/crypto/{slug}/current.json");

        if kse_store.exists(&cur_key).await {
            // Bootstrap: try to load existing key.  If the referenced block is
            // gone (e.g. backing IPFS daemon was wiped between runs but the
            // VaultStore pointer file survived), fall through to genesis instead
            // of bricking the startup.
            // Returns `Ok(Some(_))` on success, `Ok(None)` ONLY when the wrapped
            // block is *confirmed missing* (store reachable, block absent), and
            // `Err` for everything else (pointer/CID unparseable, store
            // unreachable, block present-but-corrupt, HPKE unwrap failed). Re-genesis
            // fires ONLY on `Ok(None)` — see the match below.
            let result: Result<Option<Self>> = (async {
                let data = kse_store
                    .get(&cur_key)
                    .await
                    .context("read key-ref pointer")?;
                let key_ref: KeyRef =
                    serde_json::from_slice(&data).context("parse key-ref JSON")?;
                let cid = KotobaCid::from_multibase(&key_ref.cid)
                    .ok_or_else(|| anyhow!("parse key ref CID: {}", key_ref.cid))?;
                // Symmetric retry with store_block_durable: the cold IPFS
                // sidecar (Kubo) often isn't bound to localhost:5001 yet
                // when init_crypto runs at t≈0.4s after process start.
                // load_block_durable distinguishes a *confirmed-absent* block
                // (`Ok(None)`) from an *unreachable* store (`Err`) so we only
                // re-genesis on the former, never on a transient outage.
                let block = match load_block_durable(block_store, &cid)
                    .await
                    .context("load wrapped key block")?
                {
                    Some(b) => b,
                    None => return Ok(None), // confirmed missing → caller re-genesises
                };
                // The block IS present: any failure from here is corruption,
                // tampering, or a wrong-identity load — NOT a missing block. It must
                // be a hard error so we never re-genesis OVER a recoverable key and
                // orphan every blob encrypted under it.
                let wrapped = decode_wrapped_block(&block).context("decode wrapped key block")?;
                let vault_key_bytes =
                    hpke_open(&identity.dh_secret, &wrapped).context("HPKE unwrap vault key")?;
                if vault_key_bytes.len() != 32 {
                    return Err(anyhow!(
                        "vault key has wrong length: {}",
                        vault_key_bytes.len()
                    ));
                }
                let mut arr = Zeroizing::new([0u8; 32]);
                arr.copy_from_slice(&vault_key_bytes);
                tracing::info!(
                    did = %identity.did,
                    version = key_ref.version,
                    cid = %key_ref.cid,
                    "SovereignCrypto: vault key loaded from store"
                );
                Ok(Some(Self {
                    inner: VaultKeyedCrypto::new(arr),
                }))
            })
            .await;

            match result {
                Ok(Some(c)) => Ok(c),
                Ok(None) => {
                    tracing::warn!(
                        did = %identity.did,
                        "SovereignCrypto: pointer found but wrapped key block confirmed \
                         missing — re-genesising (backing block-store may have been wiped)"
                    );
                    Self::genesis(identity, kse_store, block_store).await
                }
                // Pointer/CID unparseable, store unreachable, or block present but
                // corrupt/unwrappable: fail loud rather than silently minting a new
                // key over a recoverable one.
                Err(e) => Err(e).context(
                    "SovereignCrypto: refusing to re-genesis over a present-but-unreadable \
                     vault key (corruption, tampering, or wrong identity)",
                ),
            }
        } else {
            // Genesis: generate and persist
            Self::genesis(identity, kse_store, block_store).await
        }
    }

    /// Genesis flow: generate a new random vault key, wrap it, persist.
    ///
    /// The wrapped-key block is critical: if it is lost (e.g. the cold tier
    /// silently dropped it because the IPFS sidecar wasn't ready when this pod
    /// fired the put), the next restart sees a stale pointer + missing block
    /// and re-genesises, losing every prior encrypted blob.  To avoid that
    /// dead-loop we (a) write the pointer ONLY after `block_store.has(cid)`
    /// confirms the block has actually landed, and (b) retry the put with
    /// backoff for up to ~30 s before giving up.
    async fn genesis(
        identity: &AgentIdentity,
        kse_store: &VaultStore,
        block_store: &Arc<dyn BlockStore + Send + Sync>,
    ) -> Result<Self> {
        // Generate 32-byte random vault key
        let mut raw_key = Zeroizing::new([0u8; 32]);
        rand_core::RngCore::fill_bytes(&mut rand_core::OsRng, raw_key.as_mut());

        // HPKE-wrap with agent's X25519 public key
        let pk = identity.x25519_public_key();
        let wrapped = hpke_seal(&pk, raw_key.as_ref()).context("HPKE wrap vault key")?;
        // The block store labels every put with cid-codec=dag-cbor, so the
        // bytes MUST be valid DAG-CBOR or Kubo's `pin/add` rejects the block
        // ("pin: unexpected content after end of cbor object").  Wrap the raw
        // HPKE bytes in a CBOR byte string so the on-the-wire payload parses.
        let block = encode_wrapped_block(&wrapped)
            .context("CBOR-encode wrapped key block for IPFS storage")?;

        // Store wrapped blob under an IPFS-compatible content CID — retried
        // until the block is durably present in the BlockStore (which for the
        // production TieredBlockStore<Memory, Kubo> means landed in Kubo).
        let cid = store_block_durable(block_store, &block).await?;
        let cid_mb = cid.to_multibase();

        // Write key-ref pointer ONLY after durability is confirmed.
        let key_ref = KeyRef {
            cid: cid_mb.clone(),
            version: 1,
        };
        let slug = identity.did_slug();
        write_key_ref(kse_store, &slug, &key_ref).await?;

        tracing::info!(
            did      = %identity.did,
            cid      = %cid_mb,
            "SovereignCrypto: genesis — new vault key generated and wrapped"
        );

        Ok(Self {
            inner: VaultKeyedCrypto::new(raw_key),
        })
    }

    /// Rotate the vault key.
    ///
    /// Archives the current pointer as `v{N}.json`, generates a new vault key,
    /// wraps it, stores it, and updates `current.json`.
    pub async fn rotate(
        &self,
        identity: &AgentIdentity,
        kse_store: &VaultStore,
        block_store: &Arc<dyn BlockStore + Send + Sync>,
    ) -> Result<Self> {
        let slug = identity.did_slug();
        let cur_key = format!("agent/crypto/{slug}/current.json");

        // Read current pointer for archiving
        let current_version = if kse_store.exists(&cur_key).await {
            let data = kse_store
                .get(&cur_key)
                .await
                .context("read current key-ref")?;
            let kr: KeyRef = serde_json::from_slice(&data).context("parse current key-ref")?;
            // Archive as v{N}
            let archive_key = format!("agent/crypto/{slug}/v{}.json", kr.version);
            kse_store
                .put(&archive_key, data)
                .await
                .context("archive key-ref")?;
            kr.version
        } else {
            0
        };

        // Generate new vault key
        let mut raw_key = Zeroizing::new([0u8; 32]);
        rand_core::RngCore::fill_bytes(&mut rand_core::OsRng, raw_key.as_mut());

        // Wrap and store
        let pk = identity.x25519_public_key();
        let wrapped = hpke_seal(&pk, raw_key.as_ref()).context("HPKE wrap rotated vault key")?;
        let block =
            encode_wrapped_block(&wrapped).context("CBOR-encode rotated wrapped key block")?;
        let cid = store_block(block_store, &block)?;
        let cid_mb = cid.to_multibase();

        let new_version = current_version + 1;
        let key_ref = KeyRef {
            cid: cid_mb.clone(),
            version: new_version,
        };
        write_key_ref(kse_store, &slug, &key_ref).await?;

        tracing::info!(
            did     = %identity.did,
            version = new_version,
            cid     = %cid_mb,
            "SovereignCrypto: vault key rotated"
        );

        Ok(Self {
            inner: VaultKeyedCrypto::new(raw_key),
        })
    }

    /// Re-encrypt a blob after key rotation.
    ///
    /// Decrypts `old_ciphertext` with `old_crypto` (the pre-rotation instance),
    /// then encrypts the result with `self` (the post-rotation instance).
    /// The intermediate plaintext is held in a `Zeroizing` buffer and wiped on drop.
    ///
    /// Typical call pattern:
    // let new_crypto = old_crypto.rotate(&id, &kse, &blk).await?;
    // let new_ct = new_crypto.reencrypt_blob(&old_crypto, b"blob", &old_ct).await?;
    pub async fn reencrypt_blob(
        &self,
        old_crypto: &SovereignCrypto,
        scope: &[u8],
        old_ciphertext: &[u8],
    ) -> Result<Vec<u8>, CryptoError> {
        let plaintext = old_crypto.inner.decrypt(scope, old_ciphertext).await?;
        self.inner.encrypt(scope, &plaintext).await
    }
}

// ── AgentCrypto delegation ────────────────────────────────────────────────────

#[async_trait]
impl AgentCrypto for SovereignCrypto {
    async fn encrypt(&self, scope: &[u8], plaintext: &[u8]) -> Result<Vec<u8>, CryptoError> {
        self.inner.encrypt(scope, plaintext).await
    }

    async fn decrypt(
        &self,
        scope: &[u8],
        ciphertext: &[u8],
    ) -> Result<Zeroizing<Vec<u8>>, CryptoError> {
        self.inner.decrypt(scope, ciphertext).await
    }

    fn derive_wrapping_key(&self, owner_did: &[u8]) -> Zeroizing<[u8; 32]> {
        self.inner.derive_wrapping_key(owner_did)
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/// Write a `KeyRef` as `current.json` (always overwrites).
async fn write_key_ref(kse_store: &VaultStore, slug: &str, key_ref: &KeyRef) -> Result<()> {
    let json = serde_json::to_vec(key_ref).context("serialize key-ref")?;
    let cur_key = format!("agent/crypto/{slug}/current.json");
    kse_store
        .put(&cur_key, Bytes::from(json))
        .await
        .context("write key-ref pointer")?;
    Ok(())
}

/// Symmetric to `store_block_durable`: retry `block_store.get` with
/// exponential backoff so the wrapped-key load path can wait for the IPFS
/// sidecar to come up at pod startup.  Returns `Ok(None)` only when Kubo
/// affirmatively reports the block as missing; transient connection
/// failures keep retrying within the budget.
async fn load_block_durable(
    block_store: &Arc<dyn BlockStore + Send + Sync>,
    cid: &KotobaCid,
) -> Result<Option<bytes::Bytes>> {
    // ~60 s total budget — pod1 cleared the bar at 15.6 s in production but
    // pod2 needed just over 15.5 s and fell through, so we extend the tail
    // out to 30 s singles to absorb worse-case Kubo restart latency
    // (PVC attach, lock cleanup loop, sled WAL replay).
    let backoffs_ms: [u64; 8] = [500, 1_000, 2_000, 4_000, 8_000, 15_000, 15_000, 15_000];
    let mut last_err: Option<anyhow::Error> = None;
    for (i, wait_ms) in std::iter::once(0u64).chain(backoffs_ms).enumerate() {
        if wait_ms > 0 {
            tokio::time::sleep(std::time::Duration::from_millis(wait_ms)).await;
        }
        match block_store.get(cid) {
            Ok(Some(b)) => {
                if i > 0 {
                    tracing::info!(cid = %cid.to_multibase(), attempts = i + 1,
                        "load_block_durable: retrieved after retry");
                }
                return Ok(Some(b));
            }
            Ok(None) => return Ok(None),
            Err(e) => {
                tracing::warn!(cid = %cid.to_multibase(), attempt = i, err = %e,
                    "load_block_durable: cold get failed, will retry");
                last_err = Some(e);
            }
        }
    }
    Err(last_err.unwrap_or_else(|| anyhow!("load_block_durable exhausted retries")))
}

/// Wrap raw HPKE-sealed bytes in a DAG-CBOR byte string so the resulting
/// block parses cleanly as DAG-CBOR.  Kubo's `pin/add` validates the block
/// against the codec announced at put time (we use `cid-codec=dag-cbor`);
/// if the bytes aren't valid CBOR, pin/add returns 500 "pin: unexpected
/// content after end of cbor object".  This wrapper makes the wrapped vault
/// key a single `bytes(...)` CBOR atom — parseable, no children, eligible
/// for direct pinning.
fn encode_wrapped_block(wrapped: &[u8]) -> Result<Vec<u8>> {
    let mut buf = Vec::with_capacity(wrapped.len() + 16);
    ciborium::into_writer(&serde_bytes::Bytes::new(wrapped), &mut buf)
        .map_err(|e| anyhow!("cbor encode wrapped key block: {e}"))?;
    Ok(buf)
}

/// Inverse of `encode_wrapped_block`.  Falls back to returning the input
/// verbatim when decoding fails so legacy blocks (written before the
/// CBOR-wrapping fix) remain loadable across the upgrade.
fn decode_wrapped_block(block: &[u8]) -> Result<Vec<u8>> {
    let decoded: Result<serde_bytes::ByteBuf, _> = ciborium::from_reader(block);
    match decoded {
        Ok(buf) => Ok(buf.into_vec()),
        Err(_) => Ok(block.to_vec()),
    }
}

/// Store raw bytes in the BlockStore and return the CID.
fn store_block(block_store: &Arc<dyn BlockStore + Send + Sync>, data: &[u8]) -> Result<KotobaCid> {
    // CID = IPFS-compatible content-address of the stored bytes.
    let cid = KotobaCid::from_bytes(data);
    block_store
        .put(&cid, data)
        .context("write wrapped key block")?;
    Ok(cid)
}

/// Store raw bytes using the BlockStore's `put_durable` path (= synchronous
/// across every tier).  Retries with exponential backoff for ~30 s to absorb
/// the pod-startup window where the cold IPFS sidecar isn't bound yet.
///
/// Used for the wrapped-key block at genesis time, where a silent cold-tier
/// drop would cause the next restart to re-genesis and lose every prior
/// encrypted blob.
async fn store_block_durable(
    block_store: &Arc<dyn BlockStore + Send + Sync>,
    data: &[u8],
) -> Result<KotobaCid> {
    let cid = KotobaCid::from_bytes(data);
    let backoffs_ms: [u64; 5] = [1_000, 2_000, 4_000, 8_000, 15_000];
    let mut last_err: Option<anyhow::Error> = None;

    for (i, wait_ms) in std::iter::once(0u64).chain(backoffs_ms).enumerate() {
        if wait_ms > 0 {
            tokio::time::sleep(std::time::Duration::from_millis(wait_ms)).await;
        }
        match block_store.put_durable(&cid, data) {
            Ok(()) => {
                if i > 0 {
                    tracing::info!(cid = %cid.to_multibase(), attempts = i + 1,
                        "store_block_durable: confirmed after retry");
                }
                // Pin the block so the cold tier (Kubo) does not GC it under
                // storage pressure.  Without this, the durable put protects
                // against the startup-race drop but not against Kubo's
                // background GC of unpinned blocks.
                block_store.pin(&cid);
                return Ok(cid);
            }
            Err(e) => {
                tracing::warn!(cid = %cid.to_multibase(), attempt = i, err = %e,
                    "store_block_durable: cold put failed, will retry");
                last_err = Some(e);
            }
        }
    }
    Err(last_err
        .unwrap_or_else(|| anyhow!("store_block_durable exhausted retries"))
        .context(format!(
            "wrapped key block never landed in cold tier (cid={})",
            cid.to_multibase()
        )))
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_store::{BudgetedBlockStore, MemoryBlockStore};
    use object_store::local::LocalFileSystem;
    use std::sync::Arc;

    fn tmp_dir(prefix: &str) -> std::path::PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("kotoba-sov-{}-{}", prefix, nanos));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn make_stores(dir: &std::path::Path) -> (VaultStore, Arc<dyn BlockStore + Send + Sync>) {
        let fs = Arc::new(LocalFileSystem::new_with_prefix(dir).unwrap());
        let kse = VaultStore::new(fs, "");
        let blk = Arc::new(BudgetedBlockStore::new(
            MemoryBlockStore::new(),
            64 * 1024 * 1024,
        )) as Arc<dyn BlockStore + Send + Sync>;
        (kse, blk)
    }

    #[tokio::test]
    async fn genesis_creates_key_and_pointer() {
        let dir = tmp_dir("genesis");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();
        let crypto = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();

        let slug = id.did_slug();
        let cur_key = format!("agent/crypto/{slug}/current.json");
        assert!(
            kse.exists(&cur_key).await,
            "current.json should exist after genesis"
        );

        // Can encrypt/decrypt
        let ct = crypto.encrypt(b"test", b"hello").await.unwrap();
        let pt = crypto.decrypt(b"test", &ct).await.unwrap();
        assert_eq!(pt.as_slice(), b"hello");
    }

    #[tokio::test]
    async fn load_or_genesis_is_idempotent() {
        let dir = tmp_dir("idempotent");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();

        let c1 = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();
        // Second call should load the same key
        let c2 = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();

        // Both should decrypt the same ciphertext
        let ct = c1.encrypt(b"scope", b"data").await.unwrap();
        let pt = c2.decrypt(b"scope", &ct).await.unwrap();
        assert_eq!(pt.as_slice(), b"data");
    }

    #[tokio::test]
    async fn rotate_produces_new_key() {
        let dir = tmp_dir("rotate");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();

        let c1 = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();
        // Encrypt with original key
        let ct_old = c1.encrypt(b"scope", b"original data").await.unwrap();

        let c2 = c1.rotate(&id, &kse, &blk).await.unwrap();

        // Old ciphertext cannot be decrypted by new key (different vault key)
        assert!(
            c2.decrypt(b"scope", &ct_old).await.is_err(),
            "rotated key should not decrypt old ciphertext"
        );

        // Archive file should exist
        let slug = id.did_slug();
        assert!(kse.exists(&format!("agent/crypto/{slug}/v1.json")).await);
        // Current pointer should be at version 2
        let data: KeyRef = serde_json::from_slice(
            &kse.get(&format!("agent/crypto/{slug}/current.json"))
                .await
                .unwrap(),
        )
        .unwrap();
        assert_eq!(data.version, 2);
    }

    #[tokio::test]
    async fn rotate_and_reencrypt_blob_is_accessible_with_new_key() {
        let dir = tmp_dir("reencrypt");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();

        let old_crypto = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();

        // Encrypt with old key
        let plaintext = b"sensitive payload";
        let old_ct = old_crypto.encrypt(b"blob", plaintext).await.unwrap();

        // Rotate
        let new_crypto = old_crypto.rotate(&id, &kse, &blk).await.unwrap();

        // Old ciphertext not decryptable with new key
        assert!(new_crypto.decrypt(b"blob", &old_ct).await.is_err());

        // Re-encrypt produces ciphertext decryptable with new key
        let new_ct = new_crypto
            .reencrypt_blob(&old_crypto, b"blob", &old_ct)
            .await
            .unwrap();
        let recovered = new_crypto.decrypt(b"blob", &new_ct).await.unwrap();
        assert_eq!(recovered.as_slice(), plaintext);

        // New ciphertext is NOT the same bytes as old (different key)
        assert_ne!(new_ct, old_ct);
    }

    #[tokio::test]
    async fn different_scopes_produce_different_ciphertexts() {
        let dir = tmp_dir("scopes");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();
        let crypto = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();

        let ct1 = crypto.encrypt(b"scope-a", b"hello").await.unwrap();
        let ct2 = crypto.encrypt(b"scope-b", b"hello").await.unwrap();
        // Different scopes → different AEAD AD → different ciphertexts
        assert_ne!(ct1, ct2);
        // Wrong scope decryption fails
        assert!(crypto.decrypt(b"scope-a", &ct2).await.is_err());
        assert!(crypto.decrypt(b"scope-b", &ct1).await.is_err());
    }

    #[tokio::test]
    async fn encrypt_same_plaintext_twice_gives_different_ciphertexts() {
        let dir = tmp_dir("nonce");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();
        let crypto = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();

        // Random nonce → different ciphertexts for same plaintext
        let ct1 = crypto.encrypt(b"scope", b"repeat").await.unwrap();
        let ct2 = crypto.encrypt(b"scope", b"repeat").await.unwrap();
        assert_ne!(ct1, ct2, "nonce must differ between calls");

        // Both should decrypt to the same plaintext
        let pt1 = crypto.decrypt(b"scope", &ct1).await.unwrap();
        let pt2 = crypto.decrypt(b"scope", &ct2).await.unwrap();
        assert_eq!(pt1.as_slice(), b"repeat");
        assert_eq!(pt2.as_slice(), b"repeat");
    }

    #[tokio::test]
    async fn multiple_rotations_increment_version() {
        let dir = tmp_dir("multi-rotate");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();

        let c1 = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();
        let c2 = c1.rotate(&id, &kse, &blk).await.unwrap();
        let _c3 = c2.rotate(&id, &kse, &blk).await.unwrap();

        let slug = id.did_slug();
        let data = kse
            .get(&format!("agent/crypto/{slug}/current.json"))
            .await
            .unwrap();
        let key_ref: serde_json::Value = serde_json::from_slice(&data).unwrap();
        assert_eq!(
            key_ref["version"], 3,
            "three rotations should yield version 3"
        );
    }

    #[tokio::test]
    async fn two_independent_identities_have_isolated_keys() {
        let dir1 = tmp_dir("iso-1");
        let dir2 = tmp_dir("iso-2");
        let (kse1, blk1) = make_stores(&dir1);
        let (kse2, blk2) = make_stores(&dir2);

        let id1 = AgentIdentity::generate_ephemeral();
        let id2 = AgentIdentity::generate_ephemeral();

        let c1 = SovereignCrypto::load_or_genesis(&id1, &kse1, &blk1)
            .await
            .unwrap();
        let c2 = SovereignCrypto::load_or_genesis(&id2, &kse2, &blk2)
            .await
            .unwrap();

        let ct = c1.encrypt(b"s", b"data").await.unwrap();
        // id2 should not be able to decrypt id1's ciphertext
        assert!(
            c2.decrypt(b"s", &ct).await.is_err(),
            "different identity keys must not decrypt each other's ciphertext"
        );
    }

    #[tokio::test]
    async fn empty_plaintext_roundtrip() {
        let dir = tmp_dir("empty-pt");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();
        let crypto = SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();

        let ct = crypto.encrypt(b"s", b"").await.unwrap();
        let pt = crypto.decrypt(b"s", &ct).await.unwrap();
        assert_eq!(
            pt.as_slice(),
            b"",
            "empty plaintext must round-trip correctly"
        );
    }

    #[tokio::test]
    async fn corrupt_wrapped_key_block_fails_loud_does_not_regenesis() {
        let dir = tmp_dir("corrupt");
        let (kse, blk) = make_stores(&dir);
        let id = AgentIdentity::generate_ephemeral();

        // Genesis writes the pointer + the HPKE-wrapped vault key block.
        SovereignCrypto::load_or_genesis(&id, &kse, &blk)
            .await
            .unwrap();

        // Resolve the wrapped-block CID from the pointer, then corrupt the block
        // IN PLACE (overwrite at its CID with a flipped tag byte) — present, but bad.
        let slug = id.did_slug();
        let cur_key = format!("agent/crypto/{slug}/current.json");
        let ptr = kse.get(&cur_key).await.expect("pointer present");
        let key_ref: KeyRef = serde_json::from_slice(&ptr).unwrap();
        let cid = KotobaCid::from_multibase(&key_ref.cid).unwrap();
        let block = blk.get(&cid).unwrap().expect("wrapped block present");
        let mut corrupt = block.to_vec();
        let n = corrupt.len();
        corrupt[n - 1] ^= 0xFF; // flip the AEAD tag region of the wrapped blob
        blk.put(&cid, &corrupt).unwrap();

        // A fresh load (simulating a restart) against a PRESENT-but-corrupt block
        // must FAIL — never silently re-genesis a new key (which would orphan every
        // blob previously encrypted under the recoverable one).
        let reload = SovereignCrypto::load_or_genesis(&id, &kse, &blk).await;
        assert!(
            reload.is_err(),
            "corrupt-but-present wrapped key block must fail loud, not re-genesis"
        );
    }
}
