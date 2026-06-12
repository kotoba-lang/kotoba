use crate::chunker::{split, strategy_for};
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use kotoba_store::car_bundle::CarBundleWriter;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

const BLOB_MANIFEST_KIND: &str = "kotoba.blobManifest.v1";
pub const MAX_BLOB_MANIFEST_CBOR_BYTES: usize = 8 * 1024 * 1024;
pub const MAX_BLOB_MIME_TYPE_BYTES: usize = 256;
pub const MAX_BLOB_MANIFEST_CHUNKS: usize = 65_536;
pub const MAX_BLOB_TOTAL_BYTES: u64 = 1024 * 1024 * 1024;

/// BlobRef — reference to a content-addressed blob (or blob manifest).
///
/// When the blob is split into multiple chunks, `cid` is the CID of a
/// CBOR-encoded `BlobManifest` block, not the raw data directly.
#[derive(Debug, Clone)]
pub struct BlobRef {
    pub cid: KotobaCid,
    pub size: usize,
    pub mime_type: Option<String>,
    /// `true` when `cid` points to a `BlobManifest` (chunked blob).
    pub chunked: bool,
}

/// CBOR-encoded manifest stored as a block when a blob is split into chunks.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlobManifest {
    /// Type marker for newly written manifests. Older manifests have this field
    /// absent and are still accepted when they look like real chunk manifests.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub kind: Option<String>,
    pub mime_type: String,
    pub total_size: u64,
    /// Ordered chunk CIDs (each chunk is a raw block in the store).
    pub chunks: Vec<KotobaCid>,
}

/// Vault — chunked, content-addressed binary blob store.
///
/// Blobs are split using a file-type–aware strategy before storage:
/// - **Fixed-length** (512 KB) for video/audio/opaque binary.
/// - **Gear-hash CDC** (~256 KB avg) for text/JSON/code.
/// - **CBOR item boundaries** for dag-cbor/cbor.
/// - **Single block** for blobs smaller than 128 KB.
///
/// When a blob is chunked, a `BlobManifest` block is stored and its CID is
/// returned as `BlobRef.cid`.  Single-chunk blobs skip the manifest.
pub struct Vault {
    /// In-memory cache: manifest/raw CID multibase → raw bytes (or manifest CBOR).
    blobs: Arc<RwLock<HashMap<String, Bytes>>>,
    store: Option<Arc<dyn BlockStore + Send + Sync>>,
}

impl Vault {
    /// In-memory only — no persistence.
    pub fn new() -> Self {
        Self {
            blobs: Arc::new(RwLock::new(HashMap::new())),
            store: None,
        }
    }

    /// Persistent — blobs are written to / read from the given block store.
    pub fn with_block_store(store: Arc<dyn BlockStore + Send + Sync>) -> Self {
        Self {
            blobs: Arc::new(RwLock::new(HashMap::new())),
            store: Some(store),
        }
    }

    /// Store a blob, choosing the chunking strategy from its MIME type.
    ///
    /// Returns a `BlobRef` whose `cid` is:
    /// - the raw data CID when the blob fits in a single chunk, or
    /// - the CID of a `BlobManifest` block when the blob is split.
    pub async fn put_typed(&self, data: Bytes, mime_type: impl Into<String>) -> BlobRef {
        let mime = mime_type.into();
        let strategy = strategy_for(&mime, data.len());
        let chunks = split(&data, &strategy);

        if chunks.len() == 1 {
            // Single chunk — store raw, no manifest overhead.
            let cid = KotobaCid::from_bytes(&data);
            let key = cid.to_multibase();
            let size = data.len();
            self.blobs.write().await.insert(key, data.clone());
            if let Some(s) = &self.store {
                s.put(&cid, &data).ok();
            }
            BlobRef {
                cid,
                size,
                mime_type: Some(mime),
                chunked: false,
            }
        } else {
            self.put_chunks(data.len(), mime, chunks).await
        }
    }

    /// Store a blob without MIME type (defaults to `ContentDefined` for large
    /// blobs, `Single` for small ones).
    pub async fn put(&self, data: Bytes) -> BlobRef {
        self.put_typed(data, "application/octet-stream").await
    }

    /// Retrieve the raw bytes for a blob previously stored via `put` / `put_typed`.
    ///
    /// Handles both single-block blobs and chunked manifests transparently.
    pub async fn get(&self, cid: &KotobaCid) -> Option<Bytes> {
        let key = cid.to_multibase();

        // Fast path: raw blob in cache
        if let Some(blob) = self.blobs.read().await.get(&key).cloned() {
            // If this is a manifest, reassemble from chunks.
            if let Some(manifest) = decode_blob_manifest(&blob) {
                return self.read_manifest_or_legacy_raw(manifest, blob).await;
            }
            return Some(blob);
        }

        // Fallback: block store
        if let Some(store) = &self.store {
            if let Some(bytes) = store_get_verified(store.as_ref(), cid) {
                // Might be a manifest or raw data.
                if let Some(manifest) = decode_blob_manifest(&bytes) {
                    self.blobs.write().await.insert(key, bytes.clone());
                    return self.read_manifest_or_legacy_raw(manifest, bytes).await;
                }
                self.blobs.write().await.insert(key, bytes.clone());
                return Some(bytes);
            }
        }

        None
    }

    pub async fn contains(&self, cid: &KotobaCid) -> bool {
        let key = cid.to_multibase();
        if self.blobs.read().await.contains_key(&key) {
            return true;
        }
        if let Some(s) = &self.store {
            return s.has(cid);
        }
        false
    }

    /// Delete a raw block by CID from the in-memory cache and backing store.
    ///
    /// This intentionally operates at block granularity. Deleting a chunked blob
    /// manifest does not recursively delete its chunks; callers that need graph
    /// reachability semantics must manage that at a higher layer.
    pub async fn delete_block(&self, cid: &KotobaCid) -> bool {
        let key = cid.to_multibase();
        let removed_from_cache = self.blobs.write().await.remove(&key).is_some();
        let removed_from_store = self.store.as_ref().is_some_and(|store| {
            let existed = store.has(cid);
            existed && store.delete(cid).is_ok()
        });
        removed_from_cache || removed_from_store
    }

    /// Bundle all blocks currently pinned in `cids` into a single CAR file.
    ///
    /// Useful for batch-flushing a session's blobs to a single S3 PUT.
    /// The returned `Bytes` is a valid CAR v1 file.
    pub async fn flush_as_car(&self, root_cid: &KotobaCid, cids: &[KotobaCid]) -> Option<Bytes> {
        let store = self.store.as_ref()?;
        let mut writer = CarBundleWriter::new(root_cid.clone());
        for cid in cids {
            if let Some(data) = store_get_verified(store.as_ref(), cid) {
                writer.append(cid, &data);
            }
        }
        if writer.block_count() == 0 {
            return None;
        }
        let (car_bytes, _index) = writer.finish();
        Some(Bytes::from(car_bytes))
    }

    // ── internals ────────────────────────────────────────────────────────────

    async fn put_chunks(&self, total_size: usize, mime: String, chunks: Vec<Bytes>) -> BlobRef {
        let mut chunk_cids = Vec::with_capacity(chunks.len());
        for chunk in &chunks {
            let cid = KotobaCid::from_bytes(chunk);
            self.blobs
                .write()
                .await
                .insert(cid.to_multibase(), chunk.clone());
            if let Some(s) = &self.store {
                s.put(&cid, chunk).ok();
            }
            chunk_cids.push(cid);
        }

        let manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: mime.clone(),
            total_size: total_size as u64,
            chunks: chunk_cids,
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&manifest, &mut cbor).expect("BlobManifest CBOR serialization");
        debug_assert!(cbor.len() <= MAX_BLOB_MANIFEST_CBOR_BYTES);
        let manifest_cid = KotobaCid::from_bytes(&cbor);
        let cbor_bytes = Bytes::from(cbor);
        self.blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), cbor_bytes.clone());
        if let Some(s) = &self.store {
            s.put(&manifest_cid, &cbor_bytes).ok();
        }

        BlobRef {
            cid: manifest_cid,
            size: total_size,
            mime_type: Some(mime),
            chunked: true,
        }
    }

    async fn reassemble(&self, manifest: &BlobManifest) -> Option<Bytes> {
        // `total_size` is an untrusted hint from the manifest block (which may have
        // been fetched from an arbitrary peer via the cold store). The buffer is
        // actually filled from the fetched chunks, so a manifest claiming a huge
        // total_size must not trigger an unbounded speculative allocation (OOM);
        // cap the pre-allocation and let the Vec grow to the real chunk total.
        const MAX_REASSEMBLE_PREALLOC: usize = 64 << 20; // 64 MiB
        let mut buf =
            Vec::with_capacity((manifest.total_size as usize).min(MAX_REASSEMBLE_PREALLOC));
        for chunk_cid in &manifest.chunks {
            let chunk = self.get_raw(chunk_cid).await?;
            buf.extend_from_slice(&chunk);
            if buf.len() as u64 > manifest.total_size || buf.len() as u64 > MAX_BLOB_TOTAL_BYTES {
                return None;
            }
        }
        if u64::try_from(buf.len()).ok()? != manifest.total_size {
            return None;
        }
        Some(Bytes::from(buf))
    }

    async fn read_manifest_or_legacy_raw(
        &self,
        manifest: DecodedBlobManifest,
        raw: Bytes,
    ) -> Option<Bytes> {
        match manifest {
            DecodedBlobManifest::Typed(manifest) => self.reassemble(&manifest).await,
            DecodedBlobManifest::Legacy(manifest) => self.reassemble(&manifest).await.or(Some(raw)),
            DecodedBlobManifest::InvalidTyped => None,
        }
    }

    async fn get_raw(&self, cid: &KotobaCid) -> Option<Bytes> {
        let key = cid.to_multibase();
        if let Some(b) = self.blobs.read().await.get(&key).cloned() {
            return Some(b);
        }
        if let Some(s) = &self.store {
            if let Some(b) = store_get_verified(s.as_ref(), cid) {
                self.blobs.write().await.insert(key, b.clone());
                return Some(b);
            }
        }
        None
    }
}

enum DecodedBlobManifest {
    Typed(BlobManifest),
    Legacy(BlobManifest),
    InvalidTyped,
}

fn decode_blob_manifest(bytes: &[u8]) -> Option<DecodedBlobManifest> {
    if bytes.len() > MAX_BLOB_MANIFEST_CBOR_BYTES {
        return None;
    }
    let manifest = ciborium::from_reader::<BlobManifest, _>(bytes).ok()?;
    match manifest.kind.as_deref() {
        Some(BLOB_MANIFEST_KIND) if is_valid_blob_manifest_shape(&manifest) => {
            Some(DecodedBlobManifest::Typed(manifest))
        }
        Some(BLOB_MANIFEST_KIND) => Some(DecodedBlobManifest::InvalidTyped),
        Some(_) => None,
        None if is_valid_blob_manifest_shape(&manifest) => {
            Some(DecodedBlobManifest::Legacy(manifest))
        }
        None => None,
    }
}

fn is_valid_blob_manifest_shape(manifest: &BlobManifest) -> bool {
    !manifest.mime_type.trim().is_empty()
        && manifest.mime_type.len() <= MAX_BLOB_MIME_TYPE_BYTES
        && !manifest.chunks.is_empty()
        && manifest.chunks.len() <= MAX_BLOB_MANIFEST_CHUNKS
        && manifest.total_size > 0
        && manifest.total_size <= MAX_BLOB_TOTAL_BYTES
}

fn store_get_verified(store: &(dyn BlockStore + Send + Sync), cid: &KotobaCid) -> Option<Bytes> {
    let bytes = store.get(cid).ok()??;
    if KotobaCid::from_bytes(&bytes) == *cid {
        Some(bytes)
    } else {
        None
    }
}

impl Default for Vault {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_core::store::BlockStore;
    use std::collections::HashMap;
    use std::sync::{Arc, RwLock as StdRwLock};

    #[derive(Default)]
    struct MemStore(StdRwLock<HashMap<[u8; 36], Bytes>>);
    impl BlockStore for MemStore {
        fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
            self.0
                .write()
                .unwrap()
                .insert(cid.0, Bytes::copy_from_slice(data));
            Ok(())
        }
        fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
            Ok(self.0.read().unwrap().get(&cid.0).cloned())
        }
        fn has(&self, cid: &KotobaCid) -> bool {
            self.0.read().unwrap().contains_key(&cid.0)
        }
        fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
            self.0.write().unwrap().remove(&cid.0);
            Ok(())
        }
        fn pin(&self, _: &KotobaCid) {}
        fn unpin(&self, _: &KotobaCid) {}
        fn is_pinned(&self, _: &KotobaCid) -> bool {
            false
        }
    }

    #[tokio::test]
    async fn put_returns_blob_ref_with_correct_size() {
        let vault = Vault::new();
        let data = Bytes::from_static(b"size test payload");
        let blob_ref = vault.put(data.clone()).await;
        assert_eq!(blob_ref.size, data.len());
    }

    #[tokio::test]
    async fn put_then_get_returns_same_bytes() {
        let vault = Vault::new();
        let data = Bytes::from(vec![0xDE, 0xAD, 0xBE, 0xEF]);
        let blob_ref = vault.put(data.clone()).await;
        let retrieved = vault.get(&blob_ref.cid).await;
        assert_eq!(retrieved, Some(data));
    }

    #[tokio::test]
    async fn empty_blob_roundtrips_as_single_raw_block() {
        let vault = Vault::new();
        let data = Bytes::new();
        let blob_ref = vault.put(data.clone()).await;

        assert_eq!(blob_ref.size, 0);
        assert!(
            !blob_ref.chunked,
            "empty blobs must not be represented as empty chunk manifests"
        );
        assert_eq!(vault.get(&blob_ref.cid).await, Some(data));
    }

    #[tokio::test]
    async fn get_on_unknown_cid_returns_none() {
        let vault = Vault::new();
        let unknown_cid = KotobaCid::from_bytes(b"this was never stored");
        assert!(vault.get(&unknown_cid).await.is_none());
    }

    #[tokio::test]
    async fn contains_returns_true_after_put_false_before() {
        let vault = Vault::new();
        let data = Bytes::from_static(b"contains check");
        let cid = KotobaCid::from_bytes(&data);
        assert!(!vault.contains(&cid).await);
        vault.put(data).await;
        assert!(vault.contains(&cid).await);
    }

    #[tokio::test]
    async fn delete_block_removes_cached_and_backing_store_block() {
        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let vault = Vault::with_block_store(store.clone());

        let blob_ref = vault.put(Bytes::from_static(b"delete me")).await;
        assert!(vault.contains(&blob_ref.cid).await);
        assert!(store.has(&blob_ref.cid));

        assert!(vault.delete_block(&blob_ref.cid).await);
        assert!(!vault.contains(&blob_ref.cid).await);
        assert!(!store.has(&blob_ref.cid));

        let reopened = Vault::with_block_store(store);
        assert_eq!(reopened.get(&blob_ref.cid).await, None);
    }

    #[tokio::test]
    async fn delete_block_returns_false_when_block_was_absent() {
        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let vault = Vault::with_block_store(store);
        let absent = KotobaCid::from_bytes(b"absent delete should not count");

        assert!(!vault.contains(&absent).await);
        assert!(
            !vault.delete_block(&absent).await,
            "delete_block must only report true when a block existed"
        );
    }

    #[tokio::test]
    async fn different_content_produces_different_cids() {
        let vault = Vault::new();
        let ref_a = vault.put(Bytes::from_static(b"content alpha")).await;
        let ref_b = vault.put(Bytes::from_static(b"content beta")).await;
        assert_ne!(ref_a.cid, ref_b.cid);
    }

    #[tokio::test]
    async fn block_store_vault_survives_cache_eviction() {
        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let vault = Vault::with_block_store(store.clone());

        let data = Bytes::from_static(b"persistent blob");
        let blob_ref = vault.put(data.clone()).await;

        // Fresh vault with same block store (empty in-memory cache)
        let vault2 = Vault::with_block_store(store);
        let retrieved = vault2.get(&blob_ref.cid).await;
        assert_eq!(retrieved, Some(data));
    }

    #[tokio::test]
    async fn block_store_vault_rejects_bytes_that_do_not_match_requested_cid() {
        let store = Arc::new(MemStore::default());
        let expected_cid = KotobaCid::from_bytes(b"expected block bytes");
        store
            .0
            .write()
            .unwrap()
            .insert(expected_cid.0, Bytes::from_static(b"tampered block bytes"));
        let vault = Vault::with_block_store(store);

        assert_eq!(
            vault.get(&expected_cid).await,
            None,
            "Vault must not cache or return backing-store bytes whose CID does not match the key"
        );
    }

    #[tokio::test]
    async fn chunk_reassembly_rejects_chunk_bytes_that_do_not_match_chunk_cid() {
        let store = Arc::new(MemStore::default());
        let chunk_cid = KotobaCid::from_bytes(b"expected chunk bytes");
        store
            .0
            .write()
            .unwrap()
            .insert(chunk_cid.0, Bytes::from_static(b"tampered chunk bytes"));

        let manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "application/octet-stream".to_string(),
            total_size: "expected chunk bytes".len() as u64,
            chunks: vec![chunk_cid],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&manifest, &mut cbor).expect("serialize manifest");
        let manifest_cid = KotobaCid::from_bytes(&cbor);
        store
            .0
            .write()
            .unwrap()
            .insert(manifest_cid.0, Bytes::from(cbor));
        let vault = Vault::with_block_store(store);

        assert_eq!(
            vault.get(&manifest_cid).await,
            None,
            "chunked reads must verify each fetched chunk against its CID"
        );
    }

    #[tokio::test]
    async fn empty_blob_survives_cache_eviction() {
        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let vault = Vault::with_block_store(store.clone());

        let blob_ref = vault.put(Bytes::new()).await;
        assert_eq!(blob_ref.size, 0);
        assert!(!blob_ref.chunked);
        assert!(store.has(&blob_ref.cid));

        let reopened = Vault::with_block_store(store);
        assert_eq!(reopened.get(&blob_ref.cid).await, Some(Bytes::new()));
    }

    #[tokio::test]
    async fn put_typed_small_is_single_block() {
        let vault = Vault::new();
        let data = Bytes::from_static(b"small text blob");
        let blob_ref = vault.put_typed(data.clone(), "text/plain").await;
        assert!(!blob_ref.chunked);
        assert_eq!(blob_ref.mime_type.as_deref(), Some("text/plain"));
        assert_eq!(vault.get(&blob_ref.cid).await, Some(data));
    }

    #[tokio::test]
    async fn put_typed_large_binary_is_chunked_and_reassembled() {
        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let vault = Vault::with_block_store(store);

        // ~1.5 MB of pseudo-random bytes (> SINGLE_THRESHOLD, triggers FixedLen for video/mp4)
        let mut data = Vec::with_capacity(1_500_000);
        let mut v: u8 = 7;
        for _ in 0..data.capacity() {
            v = v.wrapping_mul(13).wrapping_add(37);
            data.push(v);
        }
        let data = Bytes::from(data);

        let blob_ref = vault.put_typed(data.clone(), "video/mp4").await;
        assert!(blob_ref.chunked, "large video should be chunked");
        assert_eq!(blob_ref.size, 1_500_000);

        let retrieved = vault.get(&blob_ref.cid).await.expect("get must succeed");
        assert_eq!(retrieved, data);
    }

    #[tokio::test]
    async fn flush_as_car_produces_non_empty_bytes() {
        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let vault = Vault::with_block_store(store);

        let ref1 = vault.put(Bytes::from_static(b"block one")).await;
        let ref2 = vault.put(Bytes::from_static(b"block two")).await;

        let car = vault
            .flush_as_car(&ref1.cid, &[ref1.cid.clone(), ref2.cid.clone()])
            .await;
        assert!(car.is_some());
        assert!(car.unwrap().len() > 16); // CAR header + at least one block
    }

    #[tokio::test]
    async fn flush_as_car_returns_none_when_no_verified_blocks_are_written() {
        let store = Arc::new(MemStore::default());
        let vault = Vault::with_block_store(store.clone());
        let missing = KotobaCid::from_bytes(b"missing car block");
        let tampered = KotobaCid::from_bytes(b"expected car block");
        store
            .0
            .write()
            .unwrap()
            .insert(tampered.0, Bytes::from_static(b"tampered car block"));

        let car = vault
            .flush_as_car(&missing, &[missing.clone(), tampered])
            .await;

        assert!(
            car.is_none(),
            "flush_as_car must not return an empty CAR when every requested block is missing or CID-invalid"
        );
    }

    #[tokio::test]
    async fn flush_as_car_includes_verified_empty_block() {
        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let vault = Vault::with_block_store(store);
        let empty_ref = vault.put(Bytes::new()).await;

        let car = vault
            .flush_as_car(&empty_ref.cid, std::slice::from_ref(&empty_ref.cid))
            .await
            .expect("empty raw block is still a verified block");
        let (_root, index) = kotoba_store::car_bundle::parse_index(&car).expect("parse CAR index");

        assert_eq!(index.len(), 1);
        assert_eq!(index[0].0, empty_ref.cid);
        assert_eq!(index[0].2, 0);
    }

    // ── additional gap tests ──────────────────────────────────────────────────

    #[tokio::test]
    async fn vault_default_is_functional() {
        let vault = Vault::default();
        let blob_ref = vault.put(Bytes::from_static(b"default vault test")).await;
        assert!(vault.contains(&blob_ref.cid).await);
    }

    #[tokio::test]
    async fn flush_as_car_without_store_returns_none() {
        let vault = Vault::new(); // no block store
        let blob_ref = vault.put(Bytes::from_static(b"no-store")).await;
        let car = vault
            .flush_as_car(&blob_ref.cid, std::slice::from_ref(&blob_ref.cid))
            .await;
        assert!(
            car.is_none(),
            "flush_as_car without a block store must return None"
        );
    }

    #[test]
    fn blob_manifest_cbor_roundtrip() {
        let cid1 = KotobaCid::from_bytes(b"chunk1");
        let cid2 = KotobaCid::from_bytes(b"chunk2");
        let manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "video/mp4".to_string(),
            total_size: 1_048_576,
            chunks: vec![cid1.clone(), cid2.clone()],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&manifest, &mut cbor).expect("serialize BlobManifest");
        let recovered: BlobManifest =
            ciborium::from_reader(&cbor[..]).expect("deserialize BlobManifest");
        assert_eq!(recovered.kind.as_deref(), Some(BLOB_MANIFEST_KIND));
        assert_eq!(recovered.mime_type, manifest.mime_type);
        assert_eq!(recovered.total_size, manifest.total_size);
        assert_eq!(recovered.chunks.len(), 2);
        assert_eq!(recovered.chunks[0], cid1);
        assert_eq!(recovered.chunks[1], cid2);
    }

    #[tokio::test]
    async fn get_unknown_cid_returns_none() {
        let vault = Vault::new();
        let unknown = KotobaCid::from_bytes(b"not-stored");
        assert!(vault.get(&unknown).await.is_none());
    }

    #[tokio::test]
    async fn typed_manifest_huge_total_size_does_not_oom_and_fails_closed() {
        // A manifest fetched from an untrusted source can claim total_size = u64::MAX
        // while pointing at a few small chunks. Before the pre-alloc cap, get() →
        // reassemble() would `Vec::with_capacity(u64::MAX as usize)` and OOM/abort.
        // It must now fail closed without OOM because the manifest size is corrupt.
        let vault = Vault::new();
        // Insert two small raw chunk blobs directly under their CIDs.
        let c1 = KotobaCid::from_bytes(b"chunk-aaa");
        let c2 = KotobaCid::from_bytes(b"chunk-bbb");
        vault
            .blobs
            .write()
            .await
            .insert(c1.to_multibase(), Bytes::from_static(b"hello"));
        vault
            .blobs
            .write()
            .await
            .insert(c2.to_multibase(), Bytes::from_static(b"world"));

        // A manifest with a wildly inflated total_size but only the two small chunks.
        let manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "application/octet-stream".to_string(),
            total_size: u64::MAX,
            chunks: vec![c1, c2],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&manifest, &mut cbor).unwrap();
        let manifest_cid = KotobaCid::from_bytes(b"evil-manifest");
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), Bytes::from(cbor));

        let out = vault.get(&manifest_cid).await;
        assert!(
            out.is_none(),
            "typed manifests must reject a lying total_size without OOM"
        );
    }

    #[tokio::test]
    async fn single_block_cbor_that_looks_like_empty_legacy_manifest_roundtrips_as_raw() {
        let vault = Vault::new();
        let raw = BlobManifest {
            kind: None,
            mime_type: "application/octet-stream".to_string(),
            total_size: 0,
            chunks: Vec::new(),
        };
        let mut raw_cbor = Vec::new();
        ciborium::into_writer(&raw, &mut raw_cbor).expect("serialize raw CBOR payload");
        let raw_cbor = Bytes::from(raw_cbor);

        let blob_ref = vault.put(raw_cbor.clone()).await;

        assert!(
            !blob_ref.chunked,
            "small CBOR payload must be stored as a single raw block"
        );
        assert_eq!(
            vault.get(&blob_ref.cid).await.as_deref(),
            Some(raw_cbor.as_ref()),
            "raw single-block CBOR must not be silently reinterpreted as an empty chunk manifest"
        );
    }

    #[tokio::test]
    async fn typed_manifest_with_missing_chunk_fails_instead_of_returning_manifest_bytes() {
        let vault = Vault::new();
        let missing_chunk = KotobaCid::from_bytes(b"missing typed manifest chunk");
        let manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "application/octet-stream".to_string(),
            total_size: 1024,
            chunks: vec![missing_chunk],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&manifest, &mut cbor).expect("serialize typed manifest");
        let manifest_cid = KotobaCid::from_bytes(&cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), Bytes::from(cbor));

        assert!(
            vault.get(&manifest_cid).await.is_none(),
            "typed manifests are authoritative; missing chunks must fail closed"
        );
    }

    #[tokio::test]
    async fn typed_manifest_with_wrong_total_size_fails_closed() {
        let vault = Vault::new();
        let chunk = KotobaCid::from_bytes(b"typed manifest chunk with wrong total size");
        vault
            .blobs
            .write()
            .await
            .insert(chunk.to_multibase(), Bytes::from_static(b"actual bytes"));
        let manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "application/octet-stream".to_string(),
            total_size: 999,
            chunks: vec![chunk],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&manifest, &mut cbor).expect("serialize typed manifest");
        let manifest_cid = KotobaCid::from_bytes(&cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), Bytes::from(cbor));

        assert!(
            vault.get(&manifest_cid).await.is_none(),
            "typed manifests must reject total_size mismatches"
        );
    }

    #[tokio::test]
    async fn legacy_manifest_with_missing_chunk_falls_back_to_raw_bytes() {
        let vault = Vault::new();
        let missing_chunk = KotobaCid::from_bytes(b"missing legacy manifest chunk");
        let legacy_manifest = BlobManifest {
            kind: None,
            mime_type: "application/octet-stream".to_string(),
            total_size: 1024,
            chunks: vec![missing_chunk],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&legacy_manifest, &mut cbor).expect("serialize legacy manifest");
        let raw_cbor = Bytes::from(cbor);
        let manifest_cid = KotobaCid::from_bytes(&raw_cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), raw_cbor.clone());

        assert_eq!(
            vault.get(&manifest_cid).await.as_deref(),
            Some(raw_cbor.as_ref()),
            "legacy manifest-looking blobs keep raw fallback for backward compatibility"
        );
    }

    #[tokio::test]
    async fn legacy_manifest_with_wrong_total_size_falls_back_to_raw_bytes() {
        let vault = Vault::new();
        let chunk = KotobaCid::from_bytes(b"legacy manifest chunk with wrong total size");
        vault
            .blobs
            .write()
            .await
            .insert(chunk.to_multibase(), Bytes::from_static(b"actual bytes"));
        let legacy_manifest = BlobManifest {
            kind: None,
            mime_type: "application/octet-stream".to_string(),
            total_size: 999,
            chunks: vec![chunk],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&legacy_manifest, &mut cbor).expect("serialize legacy manifest");
        let raw_cbor = Bytes::from(cbor);
        let manifest_cid = KotobaCid::from_bytes(&raw_cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), raw_cbor.clone());

        assert_eq!(
            vault.get(&manifest_cid).await.as_deref(),
            Some(raw_cbor.as_ref()),
            "legacy manifest-looking blobs keep raw fallback on total_size mismatch"
        );
    }

    #[tokio::test]
    async fn malformed_typed_manifest_shape_fails_closed() {
        let vault = Vault::new();
        let malformed_manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "application/octet-stream".to_string(),
            total_size: 0,
            chunks: Vec::new(),
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&malformed_manifest, &mut cbor)
            .expect("serialize malformed typed manifest");
        let raw_cbor = Bytes::from(cbor);
        let manifest_cid = KotobaCid::from_bytes(&raw_cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), raw_cbor.clone());

        assert!(
            vault.get(&manifest_cid).await.is_none(),
            "typed manifest marker is authoritative; malformed typed manifests must fail closed"
        );
    }

    #[tokio::test]
    async fn typed_manifest_with_empty_mime_fails_closed() {
        let vault = Vault::new();
        let chunk = KotobaCid::from_bytes(b"typed manifest chunk with empty mime");
        let malformed_manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "   ".to_string(),
            total_size: 128,
            chunks: vec![chunk],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&malformed_manifest, &mut cbor)
            .expect("serialize empty-mime typed manifest");
        let raw_cbor = Bytes::from(cbor);
        let manifest_cid = KotobaCid::from_bytes(&raw_cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), raw_cbor.clone());

        assert!(
            vault.get(&manifest_cid).await.is_none(),
            "typed manifests with invalid shape must fail closed"
        );
    }

    #[tokio::test]
    async fn typed_manifest_with_oversized_mime_fails_closed() {
        let vault = Vault::new();
        let chunk = KotobaCid::from_bytes(b"typed manifest chunk with oversized mime");
        let malformed_manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "x".repeat(MAX_BLOB_MIME_TYPE_BYTES + 1),
            total_size: 128,
            chunks: vec![chunk],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&malformed_manifest, &mut cbor)
            .expect("serialize oversized-mime typed manifest");
        let raw_cbor = Bytes::from(cbor);
        let manifest_cid = KotobaCid::from_bytes(&raw_cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), raw_cbor);

        assert!(vault.get(&manifest_cid).await.is_none());
    }

    #[tokio::test]
    async fn typed_manifest_with_too_many_chunks_fails_closed() {
        let vault = Vault::new();
        let malformed_manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "application/octet-stream".to_string(),
            total_size: MAX_BLOB_MANIFEST_CHUNKS as u64 + 1,
            chunks: (0..=MAX_BLOB_MANIFEST_CHUNKS)
                .map(|idx| KotobaCid::from_bytes(format!("chunk-{idx}").as_bytes()))
                .collect(),
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&malformed_manifest, &mut cbor)
            .expect("serialize too-many-chunks typed manifest");
        let raw_cbor = Bytes::from(cbor);
        let manifest_cid = KotobaCid::from_bytes(&raw_cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), raw_cbor);

        assert!(vault.get(&manifest_cid).await.is_none());
    }

    #[tokio::test]
    async fn typed_manifest_with_oversized_total_size_fails_closed() {
        let vault = Vault::new();
        let chunk = KotobaCid::from_bytes(b"typed manifest chunk with oversized total");
        let malformed_manifest = BlobManifest {
            kind: Some(BLOB_MANIFEST_KIND.to_string()),
            mime_type: "application/octet-stream".to_string(),
            total_size: MAX_BLOB_TOTAL_BYTES + 1,
            chunks: vec![chunk],
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&malformed_manifest, &mut cbor)
            .expect("serialize oversized-total typed manifest");
        let raw_cbor = Bytes::from(cbor);
        let manifest_cid = KotobaCid::from_bytes(&raw_cbor);
        vault
            .blobs
            .write()
            .await
            .insert(manifest_cid.to_multibase(), raw_cbor);

        assert!(vault.get(&manifest_cid).await.is_none());
    }
}
