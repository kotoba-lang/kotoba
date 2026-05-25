/// IrohBlockStore — daemon-less, content-addressed cold-tier block store.
///
/// Targets iroh-blobs 0.30. Uses an in-process iroh blobs store (no Kubo daemon).
/// The blake3 hash is extracted from KotobaCid bytes[4..36] to produce an iroh Hash.
///
/// Requires feature `iroh-cold`.
///
/// Sync BlockStore methods bridge to async iroh via `tokio::task::block_in_place`.
#[cfg(feature = "iroh-cold")]
pub mod inner {
    use std::sync::Arc;
    use bytes::Bytes;
    use anyhow::Result;
    use kotoba_core::cid::KotobaCid;
    use kotoba_core::store::BlockStore;
    use iroh_blobs::{
        store::{mem::Store as MemStore, Store as StoreT, Map},
        BlobFormat,
        Hash,
    };

    fn kotoba_to_iroh(cid: &KotobaCid) -> Hash {
        // KotobaCid layout: [version(1), codec(1), mh_type(1), hash_len(1), hash(32)]
        let mut bytes = [0u8; 32];
        bytes.copy_from_slice(&cid.0[4..36]);
        Hash::from_bytes(bytes)
    }

    /// In-memory iroh blob store implementing BlockStore.
    /// For persistent cold storage, replace MemStore with iroh_blobs::store::flat::Store.
    pub struct IrohBlockStore {
        store: Arc<MemStore>,
    }

    impl IrohBlockStore {
        pub fn new() -> Self {
            Self { store: Arc::new(MemStore::new()) }
        }
    }

    impl Default for IrohBlockStore {
        fn default() -> Self { Self::new() }
    }

    impl Clone for IrohBlockStore {
        fn clone(&self) -> Self {
            Self { store: Arc::clone(&self.store) }
        }
    }

    impl BlockStore for IrohBlockStore {
        fn put(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
            let store = Arc::clone(&self.store);
            let buf   = Bytes::copy_from_slice(data);
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async move {
                    let _tag = store.import_bytes(buf, BlobFormat::Raw).await?;
                    Ok::<_, anyhow::Error>(())
                })
            })
        }

        fn get(&self, cid: &KotobaCid) -> Result<Option<Bytes>> {
            let store = Arc::clone(&self.store);
            let hash  = kotoba_to_iroh(cid);
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async move {
                    match store.get(&hash).await? {
                        None => Ok(None),
                        Some(entry) => {
                            use tokio::io::AsyncReadExt;
                            let mut reader = entry.data_reader().await?;
                            let mut buf = Vec::new();
                            reader.read_to_end(&mut buf).await?;
                            Ok(Some(Bytes::from(buf)))
                        }
                    }
                })
            })
        }

        fn has(&self, cid: &KotobaCid) -> bool {
            let store = Arc::clone(&self.store);
            let hash  = kotoba_to_iroh(cid);
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async move {
                    store.has(&hash).await.unwrap_or(false)
                })
            })
        }

        fn delete(&self, cid: &KotobaCid) -> Result<()> {
            let store = Arc::clone(&self.store);
            let hash  = kotoba_to_iroh(cid);
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async move {
                    store.delete(hash).await?;
                    Ok::<_, anyhow::Error>(())
                })
            })
        }
    }
}

#[cfg(feature = "iroh-cold")]
pub use inner::IrohBlockStore;
