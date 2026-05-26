use kotoba_core::cid::KotobaCid;
use thiserror::Error;

/// The canonical BlockStore trait lives in kotoba-core to avoid circular deps.
/// Re-export it here so callers can use `kotoba_store::BlockStore`.
pub use kotoba_core::store::BlockStore;

#[derive(Debug, Error)]
pub enum StoreError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}

/// Verify that `blake3(data) == cid`, then put.  Returns `Err` on CID mismatch.
pub fn put_verified(store: &dyn BlockStore, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
    let computed = KotobaCid::from_bytes(data);
    anyhow::ensure!(
        &computed == cid,
        "cid mismatch: expected {}, got {}",
        cid.to_multibase(),
        computed.to_multibase(),
    );
    store.put(cid, data)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::MemoryBlockStore;
    use std::sync::Arc;

    #[test]
    fn put_verified_succeeds_with_correct_cid() {
        let store = Arc::new(MemoryBlockStore::new());
        let data  = b"hello kotoba";
        let cid   = KotobaCid::from_bytes(data);
        put_verified(&*store, &cid, data).unwrap();
        assert!(store.has(&cid));
    }

    #[test]
    fn put_verified_fails_with_wrong_cid() {
        let store    = Arc::new(MemoryBlockStore::new());
        let data     = b"real data";
        let bad_cid  = KotobaCid::from_bytes(b"different data");
        let result   = put_verified(&*store, &bad_cid, data);
        assert!(result.is_err(), "must reject CID mismatch");
        // Block must NOT have been written
        assert!(!store.has(&bad_cid));
    }

    #[test]
    fn store_error_is_displayable() {
        let err = StoreError::Io(std::io::Error::new(std::io::ErrorKind::Other, "disk full"));
        let msg = err.to_string();
        assert!(msg.contains("io error") || msg.contains("disk full"), "got: {msg}");
    }
}
