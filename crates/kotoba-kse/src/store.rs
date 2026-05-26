use bytes::Bytes;
use object_store::path::Path;
use std::sync::Arc;

/// KseStore — thin wrapper around an ObjectStore with a fixed key prefix.
///
/// In production: wraps an `AmazonS3` (B2 S3-compat) instance.
/// In dev/test: wraps `LocalFileSystem`.
pub struct KseStore {
    inner:  Arc<dyn object_store::ObjectStore>,
    prefix: String,
}

impl KseStore {
    /// Construct from any ObjectStore implementation.
    pub fn new(store: Arc<dyn object_store::ObjectStore>, prefix: impl Into<String>) -> Self {
        Self { inner: store, prefix: prefix.into() }
    }

    fn path(&self, key: &str) -> Path {
        Path::from(format!("{}{}", self.prefix, key))
    }

    /// Write bytes at `{prefix}{key}`.
    pub async fn put(&self, key: &str, data: Bytes) -> object_store::Result<()> {
        self.inner.put(&self.path(key), data.into()).await?;
        Ok(())
    }

    /// Read bytes at `{prefix}{key}`.
    pub async fn get(&self, key: &str) -> object_store::Result<Bytes> {
        self.inner.get(&self.path(key)).await?.bytes().await
    }

    /// Return true if the object exists.
    pub async fn exists(&self, key: &str) -> bool {
        self.inner.head(&self.path(key)).await.is_ok()
    }

    /// Delete the object at `{prefix}{key}`.
    pub async fn delete_key(&self, key: &str) -> object_store::Result<()> {
        self.inner.delete(&self.path(key)).await
    }

    /// List all keys under `{prefix}{sub_prefix}`, returning them relative to `self.prefix`.
    ///
    /// E.g. with `self.prefix = "journal/"` and `sub_prefix = "seq/"`, returns strings like
    /// `"seq/00000000000000000001"`.
    pub async fn list_prefix(&self, sub_prefix: &str) -> Vec<String> {
        use tokio_stream::StreamExt as _;
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
        store.put("hello", Bytes::from_static(b"world")).await.unwrap();
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
}
