use bytes::Bytes;
use object_store::path::Path;
use std::sync::Arc;

pub const MAX_KSE_STORE_PREFIX_BYTES: usize = 512;
pub const MAX_KSE_STORE_KEY_BYTES: usize = 1024;
pub const MAX_KSE_STORE_VALUE_BYTES: usize = 8 * 1024 * 1024;

/// KseStore — thin wrapper around an ObjectStore with a fixed key prefix.
///
/// In production: wraps an `AmazonS3` (B2 S3-compat) instance.
/// In dev/test: wraps `LocalFileSystem`.
pub struct KseStore {
    inner: Arc<dyn object_store::ObjectStore>,
    prefix: String,
}

impl KseStore {
    /// Construct from any ObjectStore implementation.
    pub fn new(store: Arc<dyn object_store::ObjectStore>, prefix: impl Into<String>) -> Self {
        let prefix = prefix.into();
        if let Err(err) = validate_prefix(&prefix) {
            panic!("invalid KseStore prefix: {err}");
        }
        Self {
            inner: store,
            prefix,
        }
    }

    fn path(&self, key: &str) -> object_store::Result<Path> {
        validate_key(key)?;
        Ok(Path::from(format!("{}{}", self.prefix, key)))
    }

    /// Write bytes at `{prefix}{key}`.
    pub async fn put(&self, key: &str, data: Bytes) -> object_store::Result<()> {
        validate_value_len(data.len())?;
        self.inner.put(&self.path(key)?, data.into()).await?;
        Ok(())
    }

    /// Read bytes at `{prefix}{key}`.
    pub async fn get(&self, key: &str) -> object_store::Result<Bytes> {
        self.inner.get(&self.path(key)?).await?.bytes().await
    }

    /// Return true if the object exists.
    pub async fn exists(&self, key: &str) -> bool {
        let Ok(path) = self.path(key) else {
            return false;
        };
        self.inner.head(&path).await.is_ok()
    }

    /// Delete the object at `{prefix}{key}`.
    pub async fn delete_key(&self, key: &str) -> object_store::Result<()> {
        self.inner.delete(&self.path(key)?).await
    }

    /// List all keys under `{prefix}{sub_prefix}`, returning them relative to `self.prefix`.
    ///
    /// E.g. with `self.prefix = "journal/"` and `sub_prefix = "seq/"`, returns strings like
    /// `"seq/00000000000000000001"`.
    pub async fn list_prefix(&self, sub_prefix: &str) -> Vec<String> {
        use tokio_stream::StreamExt as _;
        if validate_sub_prefix(sub_prefix).is_err() {
            return Vec::new();
        }
        let full_prefix = format!("{}{}", self.prefix, sub_prefix);
        let prefix_path = Path::from(full_prefix.as_str());
        let mut stream = self.inner.list(Some(&prefix_path));
        let store_prefix = self.prefix.as_str();
        let mut keys = Vec::new();
        while let Some(item) = stream.next().await {
            if let Ok(meta) = item {
                let location = meta.location.to_string();
                if let Some(relative) = location.strip_prefix(store_prefix) {
                    keys.push(relative.to_string());
                }
            }
        }
        keys
    }
}

fn store_error(message: impl Into<String>) -> object_store::Error {
    object_store::Error::Generic {
        store: "KseStore",
        source: Box::new(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            message.into(),
        )),
    }
}

fn validate_prefix(prefix: &str) -> object_store::Result<()> {
    if prefix.len() > MAX_KSE_STORE_PREFIX_BYTES {
        return Err(store_error("prefix too large"));
    }
    validate_path_like(prefix, true)
}

fn validate_key(key: &str) -> object_store::Result<()> {
    if key.is_empty() {
        return Err(store_error("key must not be empty"));
    }
    if key.len() > MAX_KSE_STORE_KEY_BYTES {
        return Err(store_error("key too large"));
    }
    validate_path_like(key, false)
}

fn validate_sub_prefix(prefix: &str) -> object_store::Result<()> {
    if prefix.len() > MAX_KSE_STORE_KEY_BYTES {
        return Err(store_error("list prefix too large"));
    }
    validate_path_like(prefix, true)
}

fn validate_path_like(value: &str, allow_empty: bool) -> object_store::Result<()> {
    if value.is_empty() {
        return if allow_empty {
            Ok(())
        } else {
            Err(store_error("path must not be empty"))
        };
    }
    if value.starts_with('/') || value.starts_with('\\') {
        return Err(store_error("absolute paths are not allowed"));
    }
    if value
        .bytes()
        .any(|byte| byte.is_ascii_control() || byte == b'\\')
    {
        return Err(store_error(
            "control characters and backslashes are not allowed",
        ));
    }
    for segment in value.split('/') {
        if segment == "." || segment == ".." {
            return Err(store_error("relative path segments are not allowed"));
        }
    }
    Ok(())
}

fn validate_value_len(len: usize) -> object_store::Result<()> {
    if len > MAX_KSE_STORE_VALUE_BYTES {
        return Err(store_error("value too large"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use object_store::local::LocalFileSystem;

    fn tmp_dir(prefix: &str) -> std::path::PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("kotoba-{}-{}", prefix, nanos));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[tokio::test]
    async fn kse_store_put_get_roundtrip() {
        let dir = tmp_dir("kse");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "test/");
        store
            .put("hello", Bytes::from_static(b"world"))
            .await
            .unwrap();
        let got = store.get("hello").await.unwrap();
        assert_eq!(got.as_ref(), b"world");
    }

    #[tokio::test]
    async fn kse_store_exists_and_delete() {
        let dir = tmp_dir("kse-del");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "test/");
        assert!(!store.exists("key").await);
        store.put("key", Bytes::from_static(b"val")).await.unwrap();
        assert!(store.exists("key").await);
        store.delete_key("key").await.unwrap();
        assert!(!store.exists("key").await);
    }

    #[tokio::test]
    async fn kse_store_list_prefix_no_matches_returns_empty() {
        let dir = tmp_dir("kse-list-empty");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "pfx/");
        let keys = store.list_prefix("seq/").await;
        assert!(keys.is_empty(), "no objects → empty list");
    }

    #[tokio::test]
    async fn kse_store_list_prefix_returns_relative_keys() {
        let dir = tmp_dir("kse-list-keys");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "j/");
        store
            .put("seq/0001", Bytes::from_static(b"a"))
            .await
            .unwrap();
        store
            .put("seq/0002", Bytes::from_static(b"b"))
            .await
            .unwrap();
        store
            .put("other/x", Bytes::from_static(b"c"))
            .await
            .unwrap();

        let mut keys = store.list_prefix("seq/").await;
        keys.sort();
        assert_eq!(
            keys,
            vec!["seq/0001", "seq/0002"],
            "list_prefix must return only keys under seq/, relative to store prefix"
        );
    }

    #[tokio::test]
    async fn kse_store_binary_data_roundtrip() {
        let dir = tmp_dir("kse-binary");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "bin/");
        let data: Vec<u8> = (0u8..=255).collect();
        store
            .put("blob", Bytes::copy_from_slice(&data))
            .await
            .unwrap();
        let got = store.get("blob").await.unwrap();
        assert_eq!(got.as_ref(), data.as_slice());
    }

    #[tokio::test]
    async fn kse_store_overwrite_returns_new_value() {
        let dir = tmp_dir("kse-overwrite");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "ow/");
        store.put("k", Bytes::from_static(b"v1")).await.unwrap();
        store.put("k", Bytes::from_static(b"v2")).await.unwrap();
        let got = store.get("k").await.unwrap();
        assert_eq!(got.as_ref(), b"v2");
    }

    #[tokio::test]
    async fn kse_store_get_nonexistent_returns_error() {
        let dir = tmp_dir("kse-get-err");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "pfx/");
        let result = store.get("nonexistent-key").await;
        assert!(result.is_err(), "getting nonexistent key should return Err");
    }

    #[tokio::test]
    async fn kse_store_delete_nonexistent_returns_error() {
        let dir = tmp_dir("kse-del-err");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "pfx/");
        let result = store.delete_key("phantom").await;
        assert!(
            result.is_err(),
            "deleting nonexistent key should return Err"
        );
    }

    #[tokio::test]
    async fn kse_store_empty_value_roundtrip() {
        let dir = tmp_dir("kse-empty-val");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "e/");
        store.put("empty", Bytes::new()).await.unwrap();
        let got = store.get("empty").await.unwrap();
        assert_eq!(got.len(), 0, "empty value should round-trip as empty bytes");
        assert!(store.exists("empty").await);
    }

    #[tokio::test]
    async fn kse_store_prefix_isolation() {
        // Two stores with different prefixes must not see each other's keys
        let dir = tmp_dir("kse-prefix-isolation");
        let fs: Arc<dyn object_store::ObjectStore> =
            Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store_a = KseStore::new(Arc::clone(&fs), "ns-a/");
        let store_b = KseStore::new(Arc::clone(&fs), "ns-b/");

        store_a
            .put("key", Bytes::from_static(b"data-a"))
            .await
            .unwrap();

        // store_b with the same key should not see store_a's data
        assert!(
            !store_b.exists("key").await,
            "store_b must not see store_a's key"
        );
    }

    #[tokio::test]
    async fn kse_store_list_prefix_all_objects_returned() {
        let dir = tmp_dir("kse-list-all");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "root/");
        for i in 0..5u8 {
            store
                .put(&format!("items/{i:03}"), Bytes::from(vec![i]))
                .await
                .unwrap();
        }
        let mut keys = store.list_prefix("items/").await;
        keys.sort();
        assert_eq!(keys.len(), 5);
        assert_eq!(keys[0], "items/000");
        assert_eq!(keys[4], "items/004");
    }

    #[tokio::test]
    async fn kse_store_exists_false_after_delete() {
        let dir = tmp_dir("kse-exists-after-del");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "x/");
        store
            .put("the-key", Bytes::from_static(b"value"))
            .await
            .unwrap();
        assert!(store.exists("the-key").await);
        store.delete_key("the-key").await.unwrap();
        assert!(
            !store.exists("the-key").await,
            "key must not exist after deletion"
        );
    }

    #[tokio::test]
    async fn kse_store_rejects_unsafe_keys() {
        let dir = tmp_dir("kse-unsafe-key");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "safe/");

        for key in [
            "",
            "/absolute",
            "../escape",
            "nested/../escape",
            "has\\slash",
        ] {
            assert!(
                store.put(key, Bytes::from_static(b"x")).await.is_err(),
                "key must be rejected: {key:?}"
            );
            assert!(!store.exists(key).await);
            assert!(store.get(key).await.is_err());
            assert!(store.delete_key(key).await.is_err());
        }
    }

    #[tokio::test]
    async fn kse_store_rejects_control_and_oversized_keys() {
        let dir = tmp_dir("kse-key-caps");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "safe/");
        let oversized_key = "k".repeat(MAX_KSE_STORE_KEY_BYTES + 1);

        assert!(store
            .put("bad\nkey", Bytes::from_static(b"x"))
            .await
            .is_err());
        assert!(store
            .put(&oversized_key, Bytes::from_static(b"x"))
            .await
            .is_err());
    }

    #[tokio::test]
    async fn kse_store_rejects_oversized_values() {
        let dir = tmp_dir("kse-value-cap");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "safe/");
        let oversized = Bytes::from(vec![0u8; MAX_KSE_STORE_VALUE_BYTES + 1]);

        assert!(store.put("large", oversized).await.is_err());
        assert!(!store.exists("large").await);
    }

    #[tokio::test]
    async fn kse_store_list_prefix_rejects_escape_prefix() {
        let dir = tmp_dir("kse-list-escape");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let store = KseStore::new(fs, "safe/");
        store
            .put("seq/0001", Bytes::from_static(b"a"))
            .await
            .unwrap();

        assert!(store.list_prefix("../").await.is_empty());
        assert!(store.list_prefix("/").await.is_empty());
    }

    #[test]
    #[should_panic(expected = "invalid KseStore prefix")]
    fn kse_store_rejects_unsafe_prefix() {
        let dir = tmp_dir("kse-bad-prefix");
        let fs = Arc::new(LocalFileSystem::new_with_prefix(&dir).unwrap());
        let _ = KseStore::new(fs, "../escape/");
    }
}
