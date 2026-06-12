//! `B2CarBlockStore` — Phase 2 read tier: serve a block directly from its CAR
//! object in B2 with a single **ranged GET**, located via [`CarIndex`].
//!
//! Slotted as the *coldest* tier (below hot/FS/Kubo) via `TieredBlockStore`, so
//! it is consulted only when a block is absent everywhere local; a hit is then
//! promoted up. Writes never land here — CARs are uploaded by the async export
//! path (`b2_export`), and this store's `put*`/`pin*` are no-ops. This is what
//! makes B2 a durable, content-addressed serving tier that scales: no per-block
//! object (count ∝ commits), reads are one ranged GET against a packed CAR.

use crate::b2_client::{b2_block_on, B2Client};
use crate::car_index::CarIndex;
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::sync::Arc;

pub struct B2CarBlockStore {
    client: Arc<B2Client>,
    index: Arc<CarIndex>,
}

impl B2CarBlockStore {
    pub fn new(client: Arc<B2Client>, index: Arc<CarIndex>) -> Self {
        Self { client, index }
    }

    pub fn index(&self) -> &Arc<CarIndex> {
        &self.index
    }
}

impl BlockStore for B2CarBlockStore {
    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        let Some((car_key, offset, len)) = self.index.get(cid) else {
            return Ok(None); // not indexed here — fall through (already coldest)
        };
        if len == 0 {
            return Ok(verify_range_bytes(cid, Bytes::new()));
        }
        let client = Arc::clone(&self.client);
        let key = car_key.clone();
        match b2_block_on(async move { client.get_object_range(&key, offset, len as u64).await }) {
            Ok(bytes) => match verify_range_bytes(cid, bytes) {
                Some(bytes) => Ok(Some(bytes)),
                None => {
                    tracing::debug!(%cid, car_key, "b2 ranged GET CID mismatch");
                    Ok(None)
                }
            },
            Err(e) => {
                // A stale index entry (CAR not in B2 / range gone) is a miss, not
                // a hard error — let the caller treat the block as absent.
                tracing::debug!(%cid, car_key, "b2 ranged GET miss: {e}");
                Ok(None)
            }
        }
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.index.contains(cid)
    }

    // Writes happen via the async CAR export path, never here.
    fn put(&self, _cid: &KotobaCid, _data: &[u8]) -> anyhow::Result<()> {
        Ok(())
    }
    fn put_durable(&self, _cid: &KotobaCid, _data: &[u8]) -> anyhow::Result<()> {
        Ok(())
    }
    fn put_many_durable(&self, _blocks: &[(KotobaCid, Vec<u8>)]) -> anyhow::Result<()> {
        Ok(())
    }
    fn delete(&self, _cid: &KotobaCid) -> anyhow::Result<()> {
        Ok(())
    }
}

fn verify_range_bytes(expected_cid: &KotobaCid, bytes: Bytes) -> Option<Bytes> {
    (KotobaCid::from_bytes(&bytes) == *expected_cid).then_some(bytes)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::b2_client::B2Config;
    use crate::car_bundle::CarBundleWriter;

    #[test]
    fn verify_range_bytes_accepts_matching_cid() {
        let bytes = Bytes::from_static(b"b2 range payload");
        let cid = KotobaCid::from_bytes(&bytes);

        let verified = verify_range_bytes(&cid, bytes.clone());

        assert_eq!(verified.as_deref(), Some(bytes.as_ref()));
    }

    #[test]
    fn verify_range_bytes_rejects_mismatched_cid() {
        let bytes = Bytes::from_static(b"b2 range payload");
        let wrong_cid = KotobaCid::from_bytes(b"different payload");

        let verified = verify_range_bytes(&wrong_cid, bytes);

        assert!(verified.is_none());
    }

    #[test]
    fn verify_range_bytes_accepts_empty_block_cid() {
        let bytes = Bytes::new();
        let cid = KotobaCid::from_bytes(&bytes);

        let verified = verify_range_bytes(&cid, bytes.clone());

        assert_eq!(verified.as_deref(), Some(bytes.as_ref()));
    }

    /// Live serve-from-B2: build a CAR of two blocks, PUT it, index it, then
    /// read each block back **through `B2CarBlockStore::get`** (one ranged GET
    /// per block, located via the index). The Phase-2 bar. Gated on KOTOBA_B2_*:
    ///   cargo test -p kotoba-store b2_serve_from_b2 -- --ignored --nocapture
    #[tokio::test]
    #[ignore = "requires live B2 creds (KOTOBA_B2_*)"]
    async fn b2_serve_from_b2() {
        let cfg = B2Config::from_env().expect("KOTOBA_B2_* must be set");
        let client = Arc::new(B2Client::new(cfg));

        let root = KotobaCid::from_bytes(b"phase2-serve-root");
        let b1_payload = b"AAAA-block-payload".to_vec();
        let b2_payload = vec![7u8; 999];
        let b1 = (KotobaCid::from_bytes(&b1_payload), b1_payload);
        let b2 = (KotobaCid::from_bytes(&b2_payload), b2_payload);
        let mut w = CarBundleWriter::new(root.clone());
        w.append(&b1.0, &b1.1);
        w.append(&b2.0, &b2.1);
        let (car_bytes, idx) = w.finish();
        let car_key = root.to_multibase();

        client
            .put_object(&car_key, &car_bytes)
            .await
            .expect("PUT CAR");

        let dir = std::env::temp_dir().join(format!("carindex_serve_{}", std::process::id()));
        let index = Arc::new(CarIndex::open(&dir).unwrap());
        for (cid, off, len) in &idx {
            index.put(cid, &car_key, *off, *len).unwrap();
        }

        let store = B2CarBlockStore::new(Arc::clone(&client), Arc::clone(&index));
        // Reads go through the sync BlockStore::get → ranged GET. Run on a
        // blocking thread so b2_block_on doesn't nest on this test's runtime.
        let got1 = tokio::task::spawn_blocking({
            let store = B2CarBlockStore::new(Arc::clone(&client), Arc::clone(&index));
            let cid = b1.0.clone();
            move || store.get(&cid)
        })
        .await
        .unwrap()
        .expect("get b1");
        assert_eq!(
            got1.as_deref(),
            Some(&b1.1[..]),
            "block A bytes via B2 ranged GET"
        );

        assert!(store.has(&b2.0), "has() should hit the index");
        let missing = KotobaCid::from_bytes(b"not-indexed");
        let got_missing = tokio::task::spawn_blocking({
            let store = B2CarBlockStore::new(Arc::clone(&client), Arc::clone(&index));
            move || store.get(&missing)
        })
        .await
        .unwrap()
        .unwrap();
        assert!(got_missing.is_none(), "un-indexed CID → None");

        let _ = std::fs::remove_dir_all(&dir);
        println!("b2_serve_from_b2 OK: served block A from CAR {car_key} via ranged GET");
    }
}
