//! CAR-on-B2 restore — rebuild a node's local block store from the CAR bundles
//! archived in B2.
//!
//! Each CAR holds one commit's delta (`ProllyTree::apply_batch` emits only
//! changed nodes), so a single CAR is **not** a snapshot — a full restore
//! re-imports *every* CAR. Order is irrelevant because blocks are
//! content-addressed; once all blocks (including the commit blocks, which the
//! exporter now packs into each CAR) are present, the CommitDag is rebuilt by
//! the normal startup replay.

use crate::b2_client::B2Client;
use crate::block_store::BlockStore;
use crate::car_bundle::{extract_verified_block, parse_index};
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;

/// Download every CAR under `prefix` ("" = whole bucket) and re-import its blocks
/// into `store` via `put_durable`. Returns `(cars, blocks)` imported.
pub async fn restore_all(
    client: &B2Client,
    store: &dyn BlockStore,
    prefix: &str,
) -> anyhow::Result<(usize, usize)> {
    let keys = client.list_objects(prefix).await?;
    let mut cars = 0usize;
    let mut blocks = 0usize;
    for key in &keys {
        if let Err(e) = parse_car_key(key) {
            tracing::warn!(key, "skipping non-CAR B2 object before download: {e}");
            continue;
        }
        let car = client.get_object(key).await?;
        let verified_blocks = match verify_keyed_car_blocks(key, &car) {
            Ok(v) => v,
            Err(e) => {
                tracing::warn!(key, "skipping unverifiable CAR: {e}");
                continue;
            }
        };
        for (cid, block) in verified_blocks {
            store.put_durable(&cid, &block)?;
            blocks += 1;
        }
        cars += 1;
        tracing::debug!(key, "restored CAR");
    }
    tracing::info!(
        cars,
        blocks,
        skipped = keys.len() - cars,
        "b2 restore complete"
    );
    Ok((cars, blocks))
}

fn parse_car_key(car_key: &str) -> anyhow::Result<KotobaCid> {
    let cid = KotobaCid::from_multibase(car_key)
        .ok_or_else(|| anyhow::anyhow!("car_key is not a canonical Kotoba CID"))?;
    anyhow::ensure!(
        cid.to_multibase() == car_key,
        "car_key is not in canonical multibase form"
    );
    Ok(cid)
}

fn verify_keyed_car_blocks(key: &str, car: &[u8]) -> anyhow::Result<Vec<(KotobaCid, Bytes)>> {
    let expected_root = parse_car_key(key)?;
    let (root, blocks) = verify_car_blocks(car)?;
    anyhow::ensure!(
        root == expected_root,
        "CAR root CID mismatch: key {}, header {}",
        expected_root.to_multibase(),
        root.to_multibase()
    );
    Ok(blocks)
}

fn verify_car_blocks(car: &[u8]) -> anyhow::Result<(KotobaCid, Vec<(KotobaCid, Bytes)>)> {
    let (root, entries) = parse_index(car)?;
    let mut blocks = Vec::with_capacity(entries.len());
    for (cid, off, len) in entries {
        let block = extract_verified_block(car, &cid, off, len)?;
        blocks.push((cid, block));
    }
    Ok((root, blocks))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::car_bundle::CarBundleWriter;

    #[test]
    fn verify_car_blocks_returns_all_matching_blocks() {
        let first = b"restore block one";
        let second = b"restore block two";
        let mut writer = CarBundleWriter::new(KotobaCid::from_bytes(b"root"));
        writer.append(&KotobaCid::from_bytes(first), first);
        writer.append(&KotobaCid::from_bytes(second), second);
        let (car, _index) = writer.finish();

        let (_root, blocks) = verify_car_blocks(&car).unwrap();

        assert_eq!(blocks.len(), 2);
        assert_eq!(blocks[0].1.as_ref(), first);
        assert_eq!(blocks[1].1.as_ref(), second);
    }

    #[test]
    fn verify_car_blocks_rejects_corrupted_car_before_restore_writes() {
        let first = b"restore block one";
        let second = b"restore block two";
        let mut writer = CarBundleWriter::new(KotobaCid::from_bytes(b"root"));
        writer.append(&KotobaCid::from_bytes(first), first);
        writer.append(&KotobaCid::from_bytes(second), second);
        let (mut car, _index) = writer.finish();
        car[72 + first.len()] ^= 0xff;

        let err = verify_car_blocks(&car).unwrap_err();

        assert!(
            err.to_string().contains("CID mismatch"),
            "restore verification must reject corrupted CAR contents: {err}"
        );
    }

    #[test]
    fn verify_keyed_car_blocks_accepts_matching_root_key() {
        let first = b"restore block one";
        let root = KotobaCid::from_bytes(b"root");
        let mut writer = CarBundleWriter::new(root.clone());
        writer.append(&KotobaCid::from_bytes(first), first);
        let (car, _index) = writer.finish();

        let blocks = verify_keyed_car_blocks(&root.to_multibase(), &car).unwrap();

        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0].1.as_ref(), first);
    }

    #[test]
    fn verify_keyed_car_blocks_rejects_root_key_mismatch() {
        let first = b"restore block one";
        let root = KotobaCid::from_bytes(b"root");
        let wrong_key = KotobaCid::from_bytes(b"wrong root").to_multibase();
        let mut writer = CarBundleWriter::new(root);
        writer.append(&KotobaCid::from_bytes(first), first);
        let (car, _index) = writer.finish();

        let err = verify_keyed_car_blocks(&wrong_key, &car).unwrap_err();

        assert!(
            err.to_string().contains("root CID mismatch"),
            "restore must reject CARs stored under a mismatched key: {err}"
        );
    }

    #[test]
    fn parse_car_key_accepts_only_canonical_root_cids() {
        let root = KotobaCid::from_bytes(b"root");
        let canonical = root.to_multibase();

        assert_eq!(parse_car_key(&canonical).unwrap(), root);

        for key in ["", "kotoba/cars/object.kcar", "../escape", "bafycarkey"] {
            assert!(
                parse_car_key(key).is_err(),
                "restore should skip non-CAR object keys before download: {key:?}"
            );
        }
    }
}
