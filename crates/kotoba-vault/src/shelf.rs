use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::sync::RwLock;

pub const BUCKET_BLOCKS: &str = "KOTOBA_BLOCKS";
pub const BUCKET_GRAPHS: &str = "KOTOBA_GRAPHS";
pub const BUCKET_HEADS: &str = "KOTOBA_HEADS";
pub const BUCKET_UCANS: &str = "KOTOBA_UCANS";
pub const BUCKET_WARRANTS: &str = "KOTOBA_WARRANTS";
pub const BUCKET_WEIGHTS: &str = "KOTOBA_WEIGHTS"; // FP8 weight blob CIDs
pub const BUCKET_PRE_KEYS: &str = "KOTOBA_PRE_KEYS"; // PRE grant index
pub const BUCKET_VAULT_ENVELOPES: &str = "KOTOBA_VAULT_ENVELOPES"; // ciphertext CID -> current manifest CID
pub const BUCKET_VAULT_ENVELOPE_TOMBSTONES: &str = "KOTOBA_VAULT_ENVELOPE_TOMBSTONES"; // cleaned manifest CID -> cleanup record

pub const MAX_SHELF_BUCKET_BYTES: usize = 128;
pub const MAX_SHELF_KEY_BYTES: usize = 1024;
pub const MAX_SHELF_VALUE_BYTES: usize = 1024 * 1024;
pub const MAX_SHELF_BUCKETS: usize = 256;
pub const MAX_SHELF_ENTRIES: usize = 65_536;
pub const MAX_SHELF_SNAPSHOT_BYTES: u64 = 8 * 1024 * 1024;

/// Shelf — CID-keyed KV, built on LiveBus (clean room, inspired by NATS KV)
pub struct Shelf {
    buckets: Arc<RwLock<HashMap<String, ShelfBucket>>>,
    persist_path: Option<PathBuf>,
}

pub struct ShelfBucket {
    pub name: String,
    entries: HashMap<String, (Bytes, u64)>, // key → (value, revision)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ShelfCasError {
    pub current: Option<Bytes>,
    pub current_revision: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ShelfSnapshot {
    buckets: HashMap<String, HashMap<String, ShelfSnapshotEntry>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ShelfSnapshotEntry {
    value: Vec<u8>,
    revision: u64,
}

impl ShelfBucket {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            entries: HashMap::new(),
        }
    }

    pub fn get(&self, key: &str) -> Option<&Bytes> {
        if validate_shelf_key(key).is_err() {
            return None;
        }
        self.entries.get(key).map(|(v, _)| v)
    }

    pub fn get_with_revision(&self, key: &str) -> Option<(&Bytes, u64)> {
        if validate_shelf_key(key).is_err() {
            return None;
        }
        self.entries.get(key).map(|(v, r)| (v, *r))
    }

    pub fn put(&mut self, key: String, value: Bytes) -> u64 {
        if validate_shelf_key(&key).is_err() || validate_shelf_value(value.len()).is_err() {
            return 0;
        }
        let rev = self.entries.get(&key).map(|(_, r)| r + 1).unwrap_or(1);
        self.entries.insert(key, (value, rev));
        rev
    }

    pub fn compare_and_swap(
        &mut self,
        key: String,
        expected: Option<&[u8]>,
        value: Bytes,
    ) -> Result<u64, ShelfCasError> {
        if validate_shelf_key(&key).is_err() || validate_shelf_value(value.len()).is_err() {
            return Err(ShelfCasError {
                current: None,
                current_revision: None,
            });
        }
        let current = self.entries.get(&key);
        let matches = match (current, expected) {
            (None, None) => true,
            (Some((current, _)), Some(expected)) => current.as_ref() == expected,
            _ => false,
        };
        if !matches {
            return Err(ShelfCasError {
                current: current.map(|(v, _)| v.clone()),
                current_revision: current.map(|(_, r)| *r),
            });
        }
        Ok(self.put(key, value))
    }

    pub fn delete(&mut self, key: &str) -> bool {
        if validate_shelf_key(key).is_err() {
            return false;
        }
        self.entries.remove(key).is_some()
    }
}

impl Default for Shelf {
    fn default() -> Self {
        Self::new()
    }
}

impl Shelf {
    pub fn new() -> Self {
        Self::from_buckets(Self::default_buckets(), None)
    }

    /// Build a Shelf backed by a JSON snapshot file.
    ///
    /// This keeps mutable capability indexes and envelope head pointers durable
    /// across process restarts. The snapshot stores values as bytes; callers are
    /// still responsible for authenticating and validating higher-level records.
    pub fn persistent(path: impl AsRef<Path>) -> Self {
        let path = path.as_ref().to_path_buf();
        let buckets = Self::load_snapshot(&path).unwrap_or_else(Self::default_buckets);
        Self::from_buckets(buckets, Some(path))
    }

    fn from_buckets(buckets: HashMap<String, ShelfBucket>, persist_path: Option<PathBuf>) -> Self {
        Self {
            buckets: Arc::new(RwLock::new(buckets)),
            persist_path,
        }
    }

    fn default_buckets() -> HashMap<String, ShelfBucket> {
        let mut buckets = HashMap::new();
        for name in &[
            BUCKET_BLOCKS,
            BUCKET_GRAPHS,
            BUCKET_HEADS,
            BUCKET_UCANS,
            BUCKET_WARRANTS,
            BUCKET_WEIGHTS,
            BUCKET_PRE_KEYS,
            BUCKET_VAULT_ENVELOPES,
            BUCKET_VAULT_ENVELOPE_TOMBSTONES,
        ] {
            buckets.insert(name.to_string(), ShelfBucket::new(*name));
        }
        buckets
    }

    fn load_snapshot(path: &Path) -> Option<HashMap<String, ShelfBucket>> {
        if std::fs::metadata(path).ok()?.len() > MAX_SHELF_SNAPSHOT_BYTES {
            tracing::warn!(path = %path.display(), "Shelf: refusing oversized snapshot");
            return None;
        }
        let bytes = std::fs::read(path).ok()?;
        if bytes.len() as u64 > MAX_SHELF_SNAPSHOT_BYTES {
            tracing::warn!(path = %path.display(), "Shelf: refusing oversized snapshot");
            return None;
        }
        let snapshot: ShelfSnapshot = serde_json::from_slice(&bytes).ok()?;
        if validate_snapshot(&snapshot).is_err() {
            tracing::warn!(path = %path.display(), "Shelf: refusing invalid snapshot");
            return None;
        }
        let mut buckets = Self::default_buckets();
        for (name, entries) in snapshot.buckets {
            let mut bucket = ShelfBucket::new(name.clone());
            for (key, entry) in entries {
                bucket
                    .entries
                    .insert(key, (Bytes::from(entry.value), entry.revision));
            }
            buckets.insert(name, bucket);
        }
        Some(buckets)
    }

    fn to_snapshot(buckets: &HashMap<String, ShelfBucket>) -> ShelfSnapshot {
        let buckets = buckets
            .iter()
            .map(|(name, bucket)| {
                let entries = bucket
                    .entries
                    .iter()
                    .map(|(key, (value, revision))| {
                        (
                            key.clone(),
                            ShelfSnapshotEntry {
                                value: value.to_vec(),
                                revision: *revision,
                            },
                        )
                    })
                    .collect();
                (name.clone(), entries)
            })
            .collect();
        ShelfSnapshot { buckets }
    }

    fn persist_snapshot(path: &Path, snapshot: &ShelfSnapshot) {
        let Some(parent) = path.parent() else {
            return;
        };
        if std::fs::create_dir_all(parent).is_err() {
            tracing::warn!(path = %path.display(), "Shelf: failed to create persistence directory");
            return;
        }
        let Ok(json) = serde_json::to_vec(snapshot) else {
            tracing::warn!("Shelf: failed to serialize snapshot");
            return;
        };
        if json.len() as u64 > MAX_SHELF_SNAPSHOT_BYTES {
            tracing::warn!("Shelf: refusing to persist oversized snapshot");
            return;
        }
        let tmp_path = path.with_extension("tmp");
        if std::fs::write(&tmp_path, json).is_err() {
            tracing::warn!(path = %tmp_path.display(), "Shelf: failed to write snapshot");
            return;
        }
        if std::fs::rename(&tmp_path, path).is_err() {
            tracing::warn!(
                from = %tmp_path.display(),
                to = %path.display(),
                "Shelf: failed to install snapshot"
            );
        }
    }

    pub async fn get(&self, bucket: &str, key: &str) -> Option<Bytes> {
        if validate_bucket_and_key(bucket, key).is_err() {
            return None;
        }
        self.buckets.read().await.get(bucket)?.get(key).cloned()
    }

    pub async fn get_with_revision(&self, bucket: &str, key: &str) -> Option<(Bytes, u64)> {
        if validate_bucket_and_key(bucket, key).is_err() {
            return None;
        }
        self.buckets
            .read()
            .await
            .get(bucket)?
            .get_with_revision(key)
            .map(|(v, r)| (v.clone(), r))
    }

    pub async fn list(&self, bucket: &str) -> Vec<(String, Bytes)> {
        if validate_shelf_bucket(bucket).is_err() {
            return Vec::new();
        }
        let mut entries: Vec<(String, Bytes)> = self
            .buckets
            .read()
            .await
            .get(bucket)
            .map(|bucket| {
                bucket
                    .entries
                    .iter()
                    .map(|(key, (value, _))| (key.clone(), value.clone()))
                    .collect()
            })
            .unwrap_or_default();
        entries.sort_by(|a, b| a.0.cmp(&b.0));
        entries
    }

    pub async fn put(&self, bucket: &str, key: String, value: Bytes) -> u64 {
        if validate_bucket_and_key(bucket, &key).is_err()
            || validate_shelf_value(value.len()).is_err()
        {
            return 0;
        }
        let mut buckets = self.buckets.write().await;
        let rev = buckets
            .entry(bucket.to_string())
            .or_insert_with(|| ShelfBucket::new(bucket))
            .put(key, value);
        let snapshot = self
            .persist_path
            .as_ref()
            .map(|_| Self::to_snapshot(&buckets));
        if let (Some(path), Some(snapshot)) = (&self.persist_path, snapshot) {
            Self::persist_snapshot(path, &snapshot);
        }
        drop(buckets);

        rev
    }

    pub async fn compare_and_swap(
        &self,
        bucket: &str,
        key: String,
        expected: Option<&[u8]>,
        value: Bytes,
    ) -> Result<u64, ShelfCasError> {
        if validate_bucket_and_key(bucket, &key).is_err()
            || validate_shelf_value(value.len()).is_err()
        {
            return Err(ShelfCasError {
                current: None,
                current_revision: None,
            });
        }
        let mut buckets = self.buckets.write().await;
        let result = buckets
            .entry(bucket.to_string())
            .or_insert_with(|| ShelfBucket::new(bucket))
            .compare_and_swap(key, expected, value);
        let snapshot = result
            .as_ref()
            .ok()
            .and(self.persist_path.as_ref())
            .map(|_| Self::to_snapshot(&buckets));
        if let (Some(path), Some(snapshot)) = (&self.persist_path, snapshot) {
            Self::persist_snapshot(path, &snapshot);
        }
        drop(buckets);

        result
    }

    pub async fn delete(&self, bucket: &str, key: &str) -> bool {
        if validate_bucket_and_key(bucket, key).is_err() {
            return false;
        }
        let mut buckets = self.buckets.write().await;
        let deleted = buckets
            .get_mut(bucket)
            .map(|bucket| bucket.delete(key))
            .unwrap_or(false);
        let snapshot = deleted
            .then_some(self.persist_path.as_ref())
            .flatten()
            .map(|_| Self::to_snapshot(&buckets));
        if let (Some(path), Some(snapshot)) = (&self.persist_path, snapshot) {
            Self::persist_snapshot(path, &snapshot);
        }
        drop(buckets);

        deleted
    }

    pub async fn get_head(&self, graph_cid: &KotobaCid) -> Option<KotobaCid> {
        let bytes = self.get(BUCKET_HEADS, &graph_cid.to_multibase()).await?;
        if bytes.len() == 36 {
            let mut arr = [0u8; 36];
            arr.copy_from_slice(&bytes);
            Some(KotobaCid(arr))
        } else {
            None
        }
    }

    pub async fn set_head(&self, graph_cid: &KotobaCid, commit_cid: &KotobaCid) {
        self.put(
            BUCKET_HEADS,
            graph_cid.to_multibase(),
            Bytes::copy_from_slice(&commit_cid.0),
        )
        .await;
    }
}

fn validate_snapshot(snapshot: &ShelfSnapshot) -> Result<(), &'static str> {
    if snapshot.buckets.len() > MAX_SHELF_BUCKETS {
        return Err("too many buckets");
    }
    let mut entries_seen = 0usize;
    for (bucket, entries) in &snapshot.buckets {
        validate_shelf_bucket(bucket)?;
        entries_seen = entries_seen
            .checked_add(entries.len())
            .ok_or("too many entries")?;
        if entries_seen > MAX_SHELF_ENTRIES {
            return Err("too many entries");
        }
        for (key, entry) in entries {
            validate_shelf_key(key)?;
            validate_shelf_value(entry.value.len())?;
            if entry.revision == 0 {
                return Err("zero revision");
            }
        }
    }
    Ok(())
}

fn validate_bucket_and_key(bucket: &str, key: &str) -> Result<(), &'static str> {
    validate_shelf_bucket(bucket)?;
    validate_shelf_key(key)
}

fn validate_shelf_bucket(bucket: &str) -> Result<(), &'static str> {
    if bucket.is_empty() {
        return Err("empty bucket");
    }
    if bucket.len() > MAX_SHELF_BUCKET_BYTES {
        return Err("bucket too large");
    }
    if bucket
        .bytes()
        .any(|byte| byte.is_ascii_control() || byte == b'/' || byte == b'\\')
    {
        return Err("invalid bucket byte");
    }
    Ok(())
}

fn validate_shelf_key(key: &str) -> Result<(), &'static str> {
    if key.is_empty() {
        return Err("empty key");
    }
    if key.len() > MAX_SHELF_KEY_BYTES {
        return Err("key too large");
    }
    if key
        .bytes()
        .any(|byte| byte.is_ascii_control() || byte == b'\\')
    {
        return Err("invalid key byte");
    }
    for segment in key.split('/') {
        if segment == "." || segment == ".." {
            return Err("relative key segment");
        }
    }
    Ok(())
}

fn validate_shelf_value(len: usize) -> Result<(), &'static str> {
    if len > MAX_SHELF_VALUE_BYTES {
        return Err("value too large");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_core::cid::KotobaCid;

    #[tokio::test]
    async fn get_on_unknown_key_returns_none() {
        let shelf = Shelf::new();
        let result = shelf.get(BUCKET_BLOCKS, "no-such-key").await;
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn put_then_get_returns_value() {
        let shelf = Shelf::new();
        let value = Bytes::from_static(b"hello shelf");
        shelf
            .put(BUCKET_BLOCKS, "key1".to_string(), value.clone())
            .await;
        let got = shelf.get(BUCKET_BLOCKS, "key1").await;
        assert_eq!(got, Some(value));
    }

    #[tokio::test]
    async fn put_increments_revision_on_re_put() {
        let shelf = Shelf::new();
        let rev1 = shelf
            .put(BUCKET_GRAPHS, "k".to_string(), Bytes::from_static(b"v1"))
            .await;
        let rev2 = shelf
            .put(BUCKET_GRAPHS, "k".to_string(), Bytes::from_static(b"v2"))
            .await;
        assert_eq!(rev1, 1);
        assert_eq!(rev2, 2);
    }

    #[tokio::test]
    async fn list_returns_bucket_entries_sorted_by_key() {
        let shelf = Shelf::new();
        shelf
            .put(BUCKET_GRAPHS, "b".to_string(), Bytes::from_static(b"two"))
            .await;
        shelf
            .put(BUCKET_GRAPHS, "a".to_string(), Bytes::from_static(b"one"))
            .await;

        assert_eq!(
            shelf.list(BUCKET_GRAPHS).await,
            vec![
                ("a".to_string(), Bytes::from_static(b"one")),
                ("b".to_string(), Bytes::from_static(b"two")),
            ]
        );
        assert!(shelf.list(BUCKET_BLOCKS).await.is_empty());
    }

    #[tokio::test]
    async fn compare_and_swap_updates_only_expected_value() {
        let shelf = Shelf::new();
        let missing = shelf.get_with_revision(BUCKET_GRAPHS, "k").await;
        assert_eq!(missing, None);

        let rev1 = shelf
            .compare_and_swap(BUCKET_GRAPHS, "k".into(), None, Bytes::from_static(b"v1"))
            .await
            .expect("create by CAS");
        assert_eq!(rev1, 1);
        assert_eq!(
            shelf.get_with_revision(BUCKET_GRAPHS, "k").await,
            Some((Bytes::from_static(b"v1"), 1))
        );

        let err = shelf
            .compare_and_swap(
                BUCKET_GRAPHS,
                "k".into(),
                Some(b"not-v1"),
                Bytes::from_static(b"bad"),
            )
            .await
            .expect_err("mismatched CAS must fail");
        assert_eq!(err.current, Some(Bytes::from_static(b"v1")));
        assert_eq!(err.current_revision, Some(1));
        assert_eq!(
            shelf.get_with_revision(BUCKET_GRAPHS, "k").await,
            Some((Bytes::from_static(b"v1"), 1))
        );

        let rev2 = shelf
            .compare_and_swap(
                BUCKET_GRAPHS,
                "k".into(),
                Some(b"v1"),
                Bytes::from_static(b"v2"),
            )
            .await
            .expect("matching CAS");
        assert_eq!(rev2, 2);
        assert_eq!(
            shelf.get_with_revision(BUCKET_GRAPHS, "k").await,
            Some((Bytes::from_static(b"v2"), 2))
        );
    }

    #[tokio::test]
    async fn delete_removes_key() {
        let mut bucket = ShelfBucket::new("test-bucket");
        bucket.put("del-key".to_string(), Bytes::from_static(b"to-delete"));
        assert!(bucket.get("del-key").is_some());
        assert!(bucket.delete("del-key"));
        assert!(!bucket.delete("del-key"));
        assert!(bucket.get("del-key").is_none());
    }

    #[tokio::test]
    async fn get_head_set_head_roundtrip() {
        let shelf = Shelf::new();
        let graph_cid = KotobaCid::from_bytes(b"graph-cid-data");
        let commit_cid = KotobaCid::from_bytes(b"commit-cid-data");
        // Before set_head, get_head returns None
        assert!(shelf.get_head(&graph_cid).await.is_none());
        shelf.set_head(&graph_cid, &commit_cid).await;
        let retrieved = shelf
            .get_head(&graph_cid)
            .await
            .expect("head should be set");
        assert_eq!(retrieved, commit_cid);
    }

    #[tokio::test]
    async fn put_to_unknown_bucket_creates_bucket_on_demand() {
        let shelf = Shelf::new();
        let custom_bucket = "KOTOBA_CUSTOM";
        let rev = shelf
            .put(
                custom_bucket,
                "some-key".to_string(),
                Bytes::from_static(b"val"),
            )
            .await;
        assert_eq!(rev, 1);
        let got = shelf.get(custom_bucket, "some-key").await;
        assert_eq!(got, Some(Bytes::from_static(b"val")));
    }

    #[tokio::test]
    async fn same_key_in_different_buckets_is_isolated() {
        // Buckets must be independent keyspaces: the account store (KOTOBA_ACCOUNT)
        // and signal store (KOTOBA_SIGNAL) use the SAME key shapes, so a shared
        // keyspace would leak one member's wrapped ARK into the other's surface.
        let shelf = Shelf::new();
        shelf
            .put(
                "bucket-a",
                "shared-key".into(),
                Bytes::from_static(b"value-a"),
            )
            .await;
        shelf
            .put(
                "bucket-b",
                "shared-key".into(),
                Bytes::from_static(b"value-b"),
            )
            .await;

        assert_eq!(
            shelf.get("bucket-a", "shared-key").await,
            Some(Bytes::from_static(b"value-a")),
            "bucket-a keeps its own value"
        );
        assert_eq!(
            shelf.get("bucket-b", "shared-key").await,
            Some(Bytes::from_static(b"value-b")),
            "bucket-b's same-named key is a distinct entry"
        );

        // Re-putting in one bucket must not bleed into the other.
        shelf
            .put(
                "bucket-a",
                "shared-key".into(),
                Bytes::from_static(b"value-a2"),
            )
            .await;
        assert_eq!(
            shelf.get("bucket-a", "shared-key").await,
            Some(Bytes::from_static(b"value-a2"))
        );
        assert_eq!(
            shelf.get("bucket-b", "shared-key").await,
            Some(Bytes::from_static(b"value-b")),
            "updating bucket-a must not touch bucket-b"
        );
    }

    #[tokio::test]
    async fn persistent_shelf_survives_reopen() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("shelf.json");

        {
            let shelf = Shelf::persistent(&path);
            let rev = shelf
                .put(
                    BUCKET_VAULT_ENVELOPES,
                    "ct-cid".into(),
                    Bytes::from_static(b"manifest-cid-v1"),
                )
                .await;
            assert_eq!(rev, 1);
            let rev = shelf
                .put(
                    BUCKET_VAULT_ENVELOPES,
                    "ct-cid".into(),
                    Bytes::from_static(b"manifest-cid-v2"),
                )
                .await;
            assert_eq!(rev, 2);
        }

        let reopened = Shelf::persistent(&path);
        assert_eq!(
            reopened.get(BUCKET_VAULT_ENVELOPES, "ct-cid").await,
            Some(Bytes::from_static(b"manifest-cid-v2"))
        );
        let rev = reopened
            .put(
                BUCKET_VAULT_ENVELOPES,
                "ct-cid".into(),
                Bytes::from_static(b"manifest-cid-v3"),
            )
            .await;
        assert_eq!(rev, 3);
    }

    #[tokio::test]
    async fn persistent_compare_and_swap_persists_only_on_success() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("shelf.json");

        let shelf = Shelf::persistent(&path);
        shelf
            .compare_and_swap(
                BUCKET_VAULT_ENVELOPES,
                "ct-cid".into(),
                None,
                Bytes::from_static(b"manifest-cid-v1"),
            )
            .await
            .expect("initial CAS");
        shelf
            .compare_and_swap(
                BUCKET_VAULT_ENVELOPES,
                "ct-cid".into(),
                Some(b"stale-manifest"),
                Bytes::from_static(b"manifest-cid-bad"),
            )
            .await
            .expect_err("stale CAS must fail");

        let reopened = Shelf::persistent(&path);
        assert_eq!(
            reopened.get(BUCKET_VAULT_ENVELOPES, "ct-cid").await,
            Some(Bytes::from_static(b"manifest-cid-v1"))
        );
    }

    #[tokio::test]
    async fn persistent_delete_survives_reopen() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("shelf.json");

        let shelf = Shelf::persistent(&path);
        shelf
            .put(
                BUCKET_VAULT_ENVELOPES,
                "ct-cid".into(),
                Bytes::from_static(b"manifest-cid"),
            )
            .await;
        assert!(shelf.delete(BUCKET_VAULT_ENVELOPES, "ct-cid").await);
        assert!(!shelf.delete(BUCKET_VAULT_ENVELOPES, "ct-cid").await);

        let reopened = Shelf::persistent(&path);
        assert_eq!(reopened.get(BUCKET_VAULT_ENVELOPES, "ct-cid").await, None);
    }

    #[tokio::test]
    async fn persistent_envelope_tombstone_survives_reopen() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("shelf.json");

        {
            let shelf = Shelf::persistent(&path);
            shelf
                .put(
                    BUCKET_VAULT_ENVELOPE_TOMBSTONES,
                    "manifest-cid".into(),
                    Bytes::from_static(br#"{"reason":"grant_old_manifest","deleted":true}"#),
                )
                .await;
        }

        let reopened = Shelf::persistent(&path);
        assert_eq!(
            reopened
                .get(BUCKET_VAULT_ENVELOPE_TOMBSTONES, "manifest-cid")
                .await,
            Some(Bytes::from_static(
                br#"{"reason":"grant_old_manifest","deleted":true}"#
            ))
        );
    }

    #[tokio::test]
    async fn shelf_rejects_invalid_bucket_and_key() {
        let shelf = Shelf::new();

        assert_eq!(
            shelf
                .put("", "key".into(), Bytes::from_static(b"value"))
                .await,
            0
        );
        assert_eq!(
            shelf
                .put("bad/bucket", "key".into(), Bytes::from_static(b"value"))
                .await,
            0
        );
        assert_eq!(
            shelf
                .put(
                    BUCKET_GRAPHS,
                    "../escape".into(),
                    Bytes::from_static(b"value")
                )
                .await,
            0
        );
        assert_eq!(
            shelf
                .put(
                    BUCKET_GRAPHS,
                    "bad\nkey".into(),
                    Bytes::from_static(b"value")
                )
                .await,
            0
        );
        assert!(shelf.get(BUCKET_GRAPHS, "../escape").await.is_none());
        assert!(shelf.list("bad/bucket").await.is_empty());
        assert!(!shelf.delete(BUCKET_GRAPHS, "../escape").await);
    }

    #[tokio::test]
    async fn shelf_rejects_oversized_key_and_value() {
        let shelf = Shelf::new();
        let oversized_key = "k".repeat(MAX_SHELF_KEY_BYTES + 1);
        let oversized_value = Bytes::from(vec![0u8; MAX_SHELF_VALUE_BYTES + 1]);

        assert_eq!(
            shelf
                .put(BUCKET_GRAPHS, oversized_key, Bytes::from_static(b"value"))
                .await,
            0
        );
        assert_eq!(
            shelf
                .put(BUCKET_GRAPHS, "large".into(), oversized_value.clone())
                .await,
            0
        );
        assert!(shelf
            .compare_and_swap(BUCKET_GRAPHS, "large".into(), None, oversized_value)
            .await
            .is_err());
        assert!(shelf.get(BUCKET_GRAPHS, "large").await.is_none());
    }

    #[tokio::test]
    async fn persistent_shelf_rejects_invalid_snapshot() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("shelf.json");
        std::fs::write(
            &path,
            br#"{"buckets":{"KOTOBA_GRAPHS":{"../escape":{"value":[1],"revision":1}}}}"#,
        )
        .unwrap();

        let reopened = Shelf::persistent(&path);
        assert!(reopened.get(BUCKET_GRAPHS, "../escape").await.is_none());
        assert!(reopened.list(BUCKET_GRAPHS).await.is_empty());
    }

    #[tokio::test]
    async fn persistent_shelf_rejects_oversized_snapshot() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join("shelf.json");
        std::fs::write(&path, vec![b' '; MAX_SHELF_SNAPSHOT_BYTES as usize + 1]).unwrap();

        let reopened = Shelf::persistent(&path);
        assert!(reopened.list(BUCKET_GRAPHS).await.is_empty());
    }
}
