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
use crate::car_bundle::{extract_block, parse_index};

/// Download every CAR under `prefix` ("" = whole bucket) and re-import its blocks
/// into `store` via `put_durable`. Returns `(cars, blocks)` imported.
pub async fn restore_all(
    client: &B2Client,
    store: &dyn BlockStore,
    prefix: &str,
) -> anyhow::Result<(usize, usize)> {
    let keys = client.list_objects(prefix).await?;
    let mut blocks = 0usize;
    for key in &keys {
        let car = client.get_object(key).await?;
        let (_root, entries) = match parse_index(&car) {
            Ok(v) => v,
            Err(e) => {
                tracing::warn!(key, "skipping unparseable CAR: {e}");
                continue;
            }
        };
        for (cid, off, len) in entries {
            let block = extract_block(&car, off, len)?;
            store.put_durable(&cid, &block)?;
            blocks += 1;
        }
        tracing::debug!(key, "restored CAR");
    }
    tracing::info!(cars = keys.len(), blocks, "b2 restore complete");
    Ok((keys.len(), blocks))
}
