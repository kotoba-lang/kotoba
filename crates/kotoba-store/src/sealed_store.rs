use anyhow::{anyhow, bail, Context, Result};
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::PathBuf;
use std::sync::{Arc, Mutex, RwLock};

/// SealedBlockStore<C> — encrypt-at-rest wrapper for cold tiers whose blocks
/// leave the node (KuboBlockStore → bitswap/DHT + kotobase.net pin fanout).
/// ADR-2606112200.
///
/// What the inner store (and therefore the public IPFS network) sees is ONLY
/// the sealed envelope `b"KSB1" || nonce || AES-256-GCM(ciphertext+tag)`,
/// stored under `sealed_cid = KotobaCid::from_bytes(envelope)` so Kubo's
/// recompute-the-CID `block/put` keeps working unchanged. Holders of a sealed
/// CID can replicate/pin the bytes but cannot read them without the block key
/// — "アクセスはできるが、読解には鍵(=監査点)が要る".
///
/// Nonce derivation is deterministic: `nonce = HKDF(block_key, "…/nonce/v1")
/// expanded over the plaintext CID`. Because the store is content-addressed
/// (`cid = sha2-256(plaintext)`), a repeated `(key, nonce)` pair implies an
/// identical plaintext, so GCM nonce reuse cannot occur across distinct
/// plaintexts. Determinism buys idempotent re-puts (same sealed CID, no cold
/// garbage) and lets a node that still holds the plaintext recompute the
/// sealed CID without the index.
///
/// The plaintext-CID → sealed-CID index is an append-only sidecar file
/// (72-byte records). It is a CACHE for retrieval routing, not a trust root:
/// integrity comes from GCM + the post-decrypt `sha2(pt) == cid` check. If the
/// index is lost, every sealed block remains recoverable by decrypt-and-rehash
/// (the AAD is a constant, deliberately NOT the plaintext CID, so a key holder
/// can rebuild the full index from cold bytes alone).
///
/// Reads fall back to a legacy plaintext fetch on index miss so a store that
/// predates sealing keeps serving its old blocks.
///
/// NOT covered by this wrapper (documented limitations): the CAR-on-B2 export
/// queue and the KOTOBA_DURABILITY_DHT NeighborhoodBlockStore peer replication
/// sit at other seams and still move plaintext — follow-ups in the ADR.
const ENVELOPE_MAGIC: &[u8; 4] = b"KSB1";
const SEAL_AAD: &[u8] = b"kotoba/sealed-block/v1";
const NONCE_INFO: &[u8] = b"kotoba/sealed-block/nonce/v1";
/// One index record: plaintext CID (36) || sealed CID (36).
const INDEX_RECORD_LEN: usize = 72;
pub const SEALED_INDEX_FILE: &str = "sealed_index.bin";

/// The 32-byte block key, parsed from the environment.
/// `KOTOBA_BLOCK_KEY` = 64 hex chars, or `KOTOBA_BLOCK_KEY_FILE` = path to a
/// file containing the hex string (trailing whitespace ignored). Neither set →
/// `Ok(None)` (sealing disabled, current plaintext behaviour).
pub struct SealedKeyConfig {
    key: [u8; 32],
}

impl SealedKeyConfig {
    pub fn from_env() -> Result<Option<Self>> {
        let hex_str = match std::env::var("KOTOBA_BLOCK_KEY") {
            Ok(v) if !v.trim().is_empty() => v.trim().to_string(),
            _ => match std::env::var("KOTOBA_BLOCK_KEY_FILE") {
                Ok(path) if !path.trim().is_empty() => std::fs::read_to_string(path.trim())
                    .with_context(|| format!("read KOTOBA_BLOCK_KEY_FILE {path}"))?
                    .trim()
                    .to_string(),
                _ => return Ok(None),
            },
        };
        Ok(Some(Self::from_hex(&hex_str)?))
    }

    pub fn from_hex(hex_str: &str) -> Result<Self> {
        let bytes = hex::decode(hex_str.trim()).context("KOTOBA_BLOCK_KEY: invalid hex")?;
        let key: [u8; 32] = bytes
            .try_into()
            .map_err(|v: Vec<u8>| anyhow!("KOTOBA_BLOCK_KEY: need 32 bytes, got {}", v.len()))?;
        Ok(Self { key })
    }

    pub fn from_key(key: [u8; 32]) -> Self {
        Self { key }
    }
}

pub struct SealedBlockStore<C: BlockStore + 'static> {
    inner: Arc<C>,
    key: [u8; 32],
    /// HKDF-derived sub-key used ONLY for nonce derivation, so the nonce
    /// stream is independent of the AEAD key proper.
    nonce_key: [u8; 32],
    index: RwLock<HashMap<[u8; 36], [u8; 36]>>,
    index_file: Option<Mutex<File>>,
}

impl<C: BlockStore + 'static> SealedBlockStore<C> {
    /// `index_path = None` keeps the plaintext→sealed index in memory only
    /// (tests / ephemeral nodes); with a path the index is loaded from and
    /// appended to that file.
    pub fn new(inner: C, cfg: SealedKeyConfig, index_path: Option<PathBuf>) -> Result<Self> {
        let nonce_key = kotoba_crypto::derive_key(&cfg.key, NONCE_INFO);
        let mut index = HashMap::new();
        let index_file = match index_path {
            None => None,
            Some(path) => {
                if let Some(parent) = path.parent() {
                    std::fs::create_dir_all(parent)
                        .with_context(|| format!("create {}", parent.display()))?;
                }
                let mut f = OpenOptions::new()
                    .read(true)
                    .append(true)
                    .create(true)
                    .open(&path)
                    .with_context(|| format!("open sealed index {}", path.display()))?;
                let mut buf = Vec::new();
                f.read_to_end(&mut buf)
                    .with_context(|| format!("read sealed index {}", path.display()))?;
                // Tolerate a torn trailing record (crash mid-append): whole
                // records are authoritative, the tail is dropped.
                for rec in buf.chunks_exact(INDEX_RECORD_LEN) {
                    let mut plain = [0u8; 36];
                    let mut sealed = [0u8; 36];
                    plain.copy_from_slice(&rec[..36]);
                    sealed.copy_from_slice(&rec[36..]);
                    index.insert(plain, sealed);
                }
                let torn = buf.len() % INDEX_RECORD_LEN;
                if torn != 0 {
                    tracing::warn!(
                        path = %path.display(),
                        torn_bytes = torn,
                        "sealed index has a torn trailing record — ignored"
                    );
                }
                Some(Mutex::new(f))
            }
        };
        Ok(Self {
            inner: Arc::new(inner),
            key: cfg.key,
            nonce_key,
            index: RwLock::new(index),
            index_file,
        })
    }

    pub fn inner(&self) -> &Arc<C> {
        &self.inner
    }

    pub fn index_len(&self) -> usize {
        self.index.read().unwrap().len()
    }

    /// The sealed CID this plaintext CID is stored under, if known.
    pub fn sealed_cid(&self, cid: &KotobaCid) -> Option<KotobaCid> {
        self.index
            .read()
            .unwrap()
            .get(&cid.0)
            .copied()
            .map(KotobaCid)
    }

    /// Deterministic seal: same key + same plaintext → same envelope, so
    /// re-puts are idempotent in the cold tier.
    fn seal_block(&self, cid: &KotobaCid, data: &[u8]) -> Result<(KotobaCid, Vec<u8>)> {
        let nonce_bytes = kotoba_crypto::hkdf::derive_bytes(
            &self.nonce_key,
            &[],
            &cid.0,
            kotoba_crypto::NONCE_LEN,
        );
        let nonce: [u8; kotoba_crypto::NONCE_LEN] = nonce_bytes
            .try_into()
            .map_err(|_| anyhow!("nonce derivation length"))?;
        let ct = kotoba_crypto::seal_with_aad_nonce(&self.key, &nonce, data, SEAL_AAD)
            .map_err(|e| anyhow!("seal block {}: {e}", cid.to_multibase()))?;
        let mut envelope = Vec::with_capacity(ENVELOPE_MAGIC.len() + ct.len());
        envelope.extend_from_slice(ENVELOPE_MAGIC);
        envelope.extend_from_slice(&ct);
        let sealed_cid = KotobaCid::from_bytes(&envelope);
        Ok((sealed_cid, envelope))
    }

    /// Open an envelope and verify the plaintext hashes back to `cid` —
    /// end-to-end integrity independent of what the cold tier returned.
    fn open_envelope(&self, cid: &KotobaCid, envelope: &[u8]) -> Result<Bytes> {
        let body = envelope
            .strip_prefix(ENVELOPE_MAGIC.as_slice())
            .ok_or_else(|| anyhow!("sealed block {}: missing KSB1 magic", cid.to_multibase()))?;
        let pt = kotoba_crypto::open_with_aad(&self.key, body, SEAL_AAD)
            .map_err(|e| anyhow!("open sealed block {}: {e}", cid.to_multibase()))?;
        let computed = KotobaCid::from_bytes(&pt);
        if &computed != cid {
            bail!(
                "sealed block {}: decrypted bytes hash to {}",
                cid.to_multibase(),
                computed.to_multibase()
            );
        }
        Ok(Bytes::copy_from_slice(&pt))
    }

    /// Record plaintext→sealed in the in-memory map and (if configured) the
    /// append-only sidecar. Errors surface: losing the record would strand the
    /// block in the cold tier under a CID nobody remembers.
    fn record(&self, cid: &KotobaCid, sealed: &KotobaCid) -> Result<()> {
        {
            let map = self.index.read().unwrap();
            if map.get(&cid.0) == Some(&sealed.0) {
                return Ok(());
            }
        }
        self.index.write().unwrap().insert(cid.0, sealed.0);
        if let Some(f) = &self.index_file {
            let mut rec = [0u8; INDEX_RECORD_LEN];
            rec[..36].copy_from_slice(&cid.0);
            rec[36..].copy_from_slice(&sealed.0);
            let mut f = f.lock().unwrap();
            // Page-cache durability is sufficient (no fsync): the mapping is
            // deterministically rebuildable by re-sealing the plaintext, so a
            // crash-lost record costs one re-put, not data.
            f.write_all(&rec).context("append sealed index")?;
        }
        Ok(())
    }
}

impl<C: BlockStore + 'static> BlockStore for SealedBlockStore<C> {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
        let (sealed_cid, envelope) = self.seal_block(cid, data)?;
        self.inner.put(&sealed_cid, &envelope)?;
        self.record(cid, &sealed_cid)
    }

    fn put_durable(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
        let (sealed_cid, envelope) = self.seal_block(cid, data)?;
        self.inner.put_durable(&sealed_cid, &envelope)?;
        self.record(cid, &sealed_cid)
    }

    fn put_many_durable(&self, blocks: &[(KotobaCid, Vec<u8>)]) -> Result<()> {
        let mut sealed_blocks = Vec::with_capacity(blocks.len());
        let mut mappings = Vec::with_capacity(blocks.len());
        for (cid, data) in blocks {
            let (sealed_cid, envelope) = self.seal_block(cid, data)?;
            mappings.push((cid.clone(), sealed_cid.clone()));
            sealed_blocks.push((sealed_cid, envelope));
        }
        self.inner.put_many_durable(&sealed_blocks)?;
        for (cid, sealed) in &mappings {
            self.record(cid, sealed)?;
        }
        Ok(())
    }

    fn get(&self, cid: &KotobaCid) -> Result<Option<Bytes>> {
        if let Some(sealed) = self.sealed_cid(cid) {
            if let Some(envelope) = self.inner.get(&sealed)? {
                return Ok(Some(self.open_envelope(cid, &envelope)?));
            }
        }
        // Legacy fallback: blocks written before sealing was enabled live in
        // the inner store under their plaintext CID, as plaintext.
        self.inner.get(cid)
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        if let Some(sealed) = self.sealed_cid(cid) {
            if self.inner.has(&sealed) {
                return true;
            }
        }
        self.inner.has(cid)
    }

    fn delete(&self, cid: &KotobaCid) -> Result<()> {
        if let Some(sealed) = self.sealed_cid(cid) {
            self.inner.delete(&sealed)?;
            // The sidecar is append-only; dropping the in-memory entry is
            // enough — a reloaded stale entry routes to an inner miss and
            // falls through to the (also deleted) legacy path.
            self.index.write().unwrap().remove(&cid.0);
        }
        self.inner.delete(cid)
    }

    fn pin(&self, cid: &KotobaCid) {
        match self.sealed_cid(cid) {
            Some(sealed) => self.inner.pin(&sealed),
            None => self.inner.pin(cid),
        }
    }

    fn unpin(&self, cid: &KotobaCid) {
        match self.sealed_cid(cid) {
            Some(sealed) => self.inner.unpin(&sealed),
            None => self.inner.unpin(cid),
        }
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        match self.sealed_cid(cid) {
            Some(sealed) => self.inner.is_pinned(&sealed),
            None => self.inner.is_pinned(cid),
        }
    }

    /// Plaintext CIDs this store can serve from sealed blocks. (Inner stores
    /// that can list — Memory/Fs — would return sealed CIDs, which are
    /// meaningless to callers like gc_dead_blocks; the index IS the listing.)
    fn all_cids(&self) -> Vec<KotobaCid> {
        self.index
            .read()
            .unwrap()
            .keys()
            .map(|k| KotobaCid(*k))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::memory_store::MemoryBlockStore;

    fn test_key() -> SealedKeyConfig {
        SealedKeyConfig::from_key([7u8; 32])
    }

    fn sealed_mem() -> SealedBlockStore<MemoryBlockStore> {
        SealedBlockStore::new(MemoryBlockStore::new(), test_key(), None).unwrap()
    }

    fn tmp_index_path(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "kotoba-sealed-test-{}-{name}.bin",
            std::process::id()
        ))
    }

    #[test]
    fn put_get_roundtrip() {
        let store = sealed_mem();
        let data = b"sealed roundtrip";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        let got = store.get(&cid).unwrap().unwrap();
        assert_eq!(got.as_ref(), data);
    }

    #[test]
    fn inner_never_sees_plaintext_or_plaintext_cid() {
        let store = sealed_mem();
        let data = b"top secret datom block";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();

        // The plaintext CID must not exist in the inner store…
        assert!(!store.inner().has(&cid), "plaintext CID leaked to inner");
        // …and the bytes stored under the sealed CID must be an opaque
        // KSB1 envelope, not the plaintext.
        let sealed = store.sealed_cid(&cid).expect("mapping recorded");
        let env = store.inner().get(&sealed).unwrap().unwrap();
        assert!(env.starts_with(ENVELOPE_MAGIC));
        assert!(
            !env.windows(data.len()).any(|w| w == data),
            "plaintext bytes visible in envelope"
        );
        // Sealed CID must be the content address of the envelope (Kubo will
        // recompute exactly this).
        assert_eq!(KotobaCid::from_bytes(&env), sealed);
    }

    #[test]
    fn seal_is_deterministic_and_idempotent() {
        let store = sealed_mem();
        let data = b"same block twice";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        let sealed1 = store.sealed_cid(&cid).unwrap();
        store.put(&cid, data).unwrap();
        let sealed2 = store.sealed_cid(&cid).unwrap();
        assert_eq!(sealed1, sealed2, "re-put must map to the same sealed CID");
        assert_eq!(store.inner().block_count(), 1, "no duplicate cold blocks");
        assert_eq!(store.index_len(), 1);
    }

    #[test]
    fn different_keys_produce_different_sealed_cids() {
        let a = SealedBlockStore::new(MemoryBlockStore::new(), test_key(), None).unwrap();
        let b = SealedBlockStore::new(
            MemoryBlockStore::new(),
            SealedKeyConfig::from_key([8u8; 32]),
            None,
        )
        .unwrap();
        let data = b"same plaintext";
        let cid = KotobaCid::from_bytes(data);
        a.put(&cid, data).unwrap();
        b.put(&cid, data).unwrap();
        assert_ne!(a.sealed_cid(&cid), b.sealed_cid(&cid));
    }

    #[test]
    fn legacy_plaintext_block_is_served_on_index_miss() {
        let inner = MemoryBlockStore::new();
        let data = b"pre-sealing legacy block";
        let cid = KotobaCid::from_bytes(data);
        inner.put(&cid, data).unwrap();
        let store = SealedBlockStore::new(inner, test_key(), None).unwrap();
        assert!(store.has(&cid));
        assert_eq!(store.get(&cid).unwrap().unwrap().as_ref(), data);
    }

    #[test]
    fn tampered_envelope_is_rejected() {
        let store = sealed_mem();
        let data = b"integrity matters";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        let sealed = store.sealed_cid(&cid).unwrap();
        let mut env = store.inner().get(&sealed).unwrap().unwrap().to_vec();
        let last = env.len() - 1;
        env[last] ^= 0xFF;
        store.inner().insert_unchecked(&sealed, &env);
        assert!(
            store.get(&cid).unwrap().is_none(),
            "tampered envelope must not open"
        );
    }

    #[test]
    fn wrong_key_fails_to_open() {
        let inner = MemoryBlockStore::new();
        let data = b"sealed under key A";
        let cid = KotobaCid::from_bytes(data);
        let writer = SealedBlockStore::new(inner.clone(), test_key(), None).unwrap();
        writer.put(&cid, data).unwrap();
        let sealed = writer.sealed_cid(&cid).unwrap();

        let reader =
            SealedBlockStore::new(inner, SealedKeyConfig::from_key([9u8; 32]), None).unwrap();
        reader.record(&cid, &sealed).unwrap();
        assert!(reader.get(&cid).is_err(), "wrong key must not decrypt");
    }

    #[test]
    fn index_persists_across_reopen() {
        let path = tmp_index_path("persist");
        let _ = std::fs::remove_file(&path);
        let inner = MemoryBlockStore::new();
        let data = b"survives restart";
        let cid = KotobaCid::from_bytes(data);
        {
            let store =
                SealedBlockStore::new(inner.clone(), test_key(), Some(path.clone())).unwrap();
            store.put(&cid, data).unwrap();
        }
        let store = SealedBlockStore::new(inner, test_key(), Some(path.clone())).unwrap();
        assert_eq!(store.index_len(), 1, "index reloaded from sidecar");
        assert_eq!(store.get(&cid).unwrap().unwrap().as_ref(), data);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn torn_trailing_index_record_is_ignored() {
        let path = tmp_index_path("torn");
        let _ = std::fs::remove_file(&path);
        let inner = MemoryBlockStore::new();
        let data = b"whole record";
        let cid = KotobaCid::from_bytes(data);
        {
            let store =
                SealedBlockStore::new(inner.clone(), test_key(), Some(path.clone())).unwrap();
            store.put(&cid, data).unwrap();
        }
        // Simulate a crash mid-append: 10 stray bytes after the whole record.
        {
            let mut f = OpenOptions::new().append(true).open(&path).unwrap();
            f.write_all(&[0xAA; 10]).unwrap();
        }
        let store = SealedBlockStore::new(inner, test_key(), Some(path.clone())).unwrap();
        assert_eq!(store.index_len(), 1, "torn tail dropped, whole record kept");
        assert_eq!(store.get(&cid).unwrap().unwrap().as_ref(), data);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn put_many_durable_seals_every_block() {
        let store = sealed_mem();
        let blocks: Vec<(KotobaCid, Vec<u8>)> = (0..5u8)
            .map(|i| {
                let data = vec![i; 64];
                (KotobaCid::from_bytes(&data), data)
            })
            .collect();
        store.put_many_durable(&blocks).unwrap();
        assert_eq!(store.index_len(), 5);
        for (cid, data) in &blocks {
            assert!(!store.inner().has(cid), "plaintext CID leaked");
            assert_eq!(store.get(cid).unwrap().unwrap().as_ref(), &data[..]);
        }
    }

    #[test]
    fn delete_removes_sealed_block_and_mapping() {
        let store = sealed_mem();
        let data = b"to be deleted";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        let sealed = store.sealed_cid(&cid).unwrap();
        store.delete(&cid).unwrap();
        assert!(!store.inner().has(&sealed));
        assert!(store.sealed_cid(&cid).is_none());
        assert!(store.get(&cid).unwrap().is_none());
    }

    #[test]
    fn pin_translates_to_sealed_cid() {
        let store = sealed_mem();
        let data = b"pin me";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        let sealed = store.sealed_cid(&cid).unwrap();
        store.pin(&cid);
        assert!(
            store.inner().is_pinned(&sealed),
            "inner pin is on sealed CID"
        );
        assert!(!store.inner().is_pinned(&cid));
        assert!(store.is_pinned(&cid), "wrapper view stays plaintext-keyed");
        store.unpin(&cid);
        assert!(!store.is_pinned(&cid));
    }

    #[test]
    fn stale_index_entry_falls_back_and_returns_none() {
        // Mapping exists but the sealed block vanished from the inner store
        // (e.g. cold-tier GC) and there is no legacy plaintext block either:
        // get must degrade to Ok(None), not error.
        let store = sealed_mem();
        let data = b"stale mapping";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        let sealed = store.sealed_cid(&cid).unwrap();
        store.inner().delete(&sealed).unwrap();
        assert!(
            store.sealed_cid(&cid).is_some(),
            "mapping intentionally stale"
        );
        assert!(store.get(&cid).unwrap().is_none());
        assert!(!store.has(&cid));
    }

    #[test]
    fn all_cids_lists_plaintext_cids() {
        let store = sealed_mem();
        let data = b"listed";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        assert_eq!(store.all_cids(), vec![cid]);
    }

    #[test]
    fn key_config_from_hex_roundtrip_and_rejects_bad_input() {
        let cfg = SealedKeyConfig::from_hex(&"ab".repeat(32)).unwrap();
        assert_eq!(cfg.key, [0xABu8; 32]);
        assert!(SealedKeyConfig::from_hex("deadbeef").is_err(), "short key");
        assert!(SealedKeyConfig::from_hex("zz").is_err(), "non-hex");
    }
}
