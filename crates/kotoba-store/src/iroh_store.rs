/// IrohBlockStore — daemon-less, content-addressed block store.
///
/// Targets iroh-blobs 0.30.  Supports an in-memory store (for tests) and a
/// persistent `fs::Store` (for production via `IrohBlockStore::open(path)`).
/// No Kubo/IPFS daemon required.
///
/// Sync BlockStore methods bridge to async iroh via `tokio::task::block_in_place`.
use std::collections::HashSet;
use std::sync::{Arc, RwLock};
use bytes::Bytes;
use anyhow::Result;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use iroh_blobs::{
    store::{
        fs::Store as FsStore,
        mem::Store as MemStore,
        Map,
        MapEntry,
        Store as StoreT,
    },
    BlobFormat,
    Hash,
};
use iroh_io::AsyncSliceReaderExt;

fn kotoba_to_iroh(cid: &KotobaCid) -> Hash {
    // KotobaCid layout: [version(1), codec(1), mh_type(1), hash_len(1), hash(32)]
    let mut bytes = [0u8; 32];
    bytes.copy_from_slice(&cid.0[4..36]);
    Hash::from_bytes(bytes)
}

enum IrohInner {
    Mem(Arc<MemStore>),
    Fs(FsStore),
}

pub struct IrohBlockStore {
    inner:  Arc<IrohInner>,
    pinned: Arc<RwLock<HashSet<[u8; 36]>>>,
}

impl IrohBlockStore {
    pub fn new() -> Self {
        Self {
            inner:  Arc::new(IrohInner::Mem(Arc::new(MemStore::new()))),
            pinned: Arc::new(RwLock::new(HashSet::new())),
        }
    }

    /// Open (or create) a persistent `fs::Store` at `path`.
    /// Blocks the current thread until the store is ready.
    pub fn open(path: impl AsRef<std::path::Path>) -> Result<Self> {
        let store = tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(FsStore::load(path))
        })
        .map_err(|e| anyhow::anyhow!("iroh fs::Store::load: {e}"))?;
        Ok(Self {
            inner:  Arc::new(IrohInner::Fs(store)),
            pinned: Arc::new(RwLock::new(HashSet::new())),
        })
    }
}

impl Default for IrohBlockStore {
    fn default() -> Self { Self::new() }
}

impl Clone for IrohBlockStore {
    fn clone(&self) -> Self {
        Self {
            inner:  Arc::clone(&self.inner),
            pinned: Arc::clone(&self.pinned),
        }
    }
}

impl BlockStore for IrohBlockStore {
    fn put(&self, _cid: &KotobaCid, data: &[u8]) -> Result<()> {
        let inner = Arc::clone(&self.inner);
        let buf   = Bytes::copy_from_slice(data);
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async move {
                // import_bytes returns a TempTag; drop it here.
                // GC must be run explicitly — not automatic on drop.
                match inner.as_ref() {
                    IrohInner::Mem(s) => { s.import_bytes(buf, BlobFormat::Raw).await?; }
                    IrohInner::Fs(s)  => { s.import_bytes(buf, BlobFormat::Raw).await?; }
                }
                Ok::<_, anyhow::Error>(())
            })
        })
    }

    fn get(&self, cid: &KotobaCid) -> Result<Option<Bytes>> {
        let inner = Arc::clone(&self.inner);
        let hash  = kotoba_to_iroh(cid);
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async move {
                match inner.as_ref() {
                    IrohInner::Mem(s) => {
                        match s.get(&hash).await? {
                            None => Ok(None),
                            Some(entry) => {
                                let mut r = MapEntry::data_reader(&entry).await?;
                                Ok(Some(r.read_to_end().await?))
                            }
                        }
                    }
                    IrohInner::Fs(s) => {
                        match s.get(&hash).await? {
                            None => Ok(None),
                            Some(entry) => {
                                // fs::Entry has an inherent sync data_reader() that
                                // conflicts with the trait method; call the inherent one.
                                let mut r = entry.data_reader();
                                Ok(Some(r.read_to_end().await?))
                            }
                        }
                    }
                }
            })
        })
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        let inner = Arc::clone(&self.inner);
        let hash  = kotoba_to_iroh(cid);
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async move {
                match inner.as_ref() {
                    IrohInner::Mem(s) => s.get(&hash).await.map(|o| o.is_some()).unwrap_or(false),
                    IrohInner::Fs(s)  => s.get(&hash).await.map(|o| o.is_some()).unwrap_or(false),
                }
            })
        })
    }

    fn delete(&self, cid: &KotobaCid) -> Result<()> {
        let inner = Arc::clone(&self.inner);
        let hash  = kotoba_to_iroh(cid);
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async move {
                match inner.as_ref() {
                    IrohInner::Mem(s) => s.delete(vec![hash]).await?,
                    IrohInner::Fs(s)  => s.delete(vec![hash]).await?,
                }
                Ok::<_, anyhow::Error>(())
            })
        })
    }

    fn pin(&self, cid: &KotobaCid) {
        self.pinned.write().unwrap().insert(cid.0);
    }

    fn unpin(&self, cid: &KotobaCid) {
        self.pinned.write().unwrap().remove(&cid.0);
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.pinned.read().unwrap().contains(&cid.0)
    }
}
