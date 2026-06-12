//! CAR-on-B2 export queue — the async, at-least-once path that uploads each
//! sealed commit's CAR bundle to Backblaze B2.
//!
//! Flow:
//! 1. `commit()` (synchronous) calls [`CarExportQueue::enqueue`], which **stages
//!    the CAR bytes on local disk** under `<dir>/<car_key>` (atomic rename) and
//!    sends the `car_key` over a channel. The bytes live on disk, not in the
//!    channel, so the queue is bounded and crash-durable.
//! 2. [`run_exporter`] (async task, owns the [`B2Client`]) receives keys, reads
//!    the staged file, `PUT`s it to B2, and deletes the file on success.
//! 3. On startup, [`reconcile`] re-enqueues any staged files left by a crash
//!    between stage and upload — giving at-least-once delivery without a mutable
//!    global manifest (which would race under concurrent commits). Restore
//!    enumeration is by `ListObjectsV2`, not a manifest.
//!
//! `car_key` is the commit CID's multibase string, so re-uploads are idempotent
//! (same content-addressed bytes overwrite the same key).

use crate::b2_car_store::B2CarBlockStore;
use crate::b2_client::{b2_spawn, B2Client, B2Config};
use crate::car_bundle::parse_verified_index;
use crate::car_index::CarIndex;
use kotoba_core::cid::KotobaCid;
use std::path::{Path, PathBuf};
use std::sync::{Arc, OnceLock};
use tokio::sync::mpsc;

/// Process-global CAR export queue. Set once at startup by [`CarExportQueue::start`]
/// so every commit path (`QuadStore::commit`, the distributed
/// `DistributedCommitWriter::commit_datoms`, …) can reach it without threading
/// it through each call site. `None` (default) keeps export disabled.
static GLOBAL: OnceLock<Arc<CarExportQueue>> = OnceLock::new();

/// The installed global export queue, if any. Commit paths call this and
/// enqueue their CAR when it returns `Some`.
pub fn global() -> Option<&'static CarExportQueue> {
    GLOBAL.get().map(|a| a.as_ref())
}

/// Sender half held by `QuadStore`. Staging dir + bounded channel.
#[derive(Clone)]
pub struct CarExportQueue {
    tx: mpsc::Sender<String>,
    dir: PathBuf,
}

impl CarExportQueue {
    /// Create the queue and its staging dir. Returns the sender wrapper and the
    /// receiver to hand to [`run_exporter`].
    pub fn new(
        dir: impl AsRef<Path>,
        capacity: usize,
    ) -> std::io::Result<(Self, mpsc::Receiver<String>)> {
        let dir = dir.as_ref().to_path_buf();
        std::fs::create_dir_all(&dir)?;
        let (tx, rx) = mpsc::channel(capacity);
        Ok((Self { tx, dir }, rx))
    }

    /// Self-contained startup: enable the CAR-on-B2 tier iff B2 is configured
    /// (`KOTOBA_B2_*`) and a persistent `store_path` is available for
    /// crash-durable staging + the read index. Installs the global export queue
    /// (consulted by the commit paths), spawns the exporter on the dedicated
    /// `b2-io` runtime, reconciles crash-staged CARs, and returns the
    /// [`B2CarBlockStore`] **read tier** for the server to nest as the coldest
    /// tier. `None` when disabled.
    pub fn start(store_path: Option<&str>) -> Option<Arc<B2CarBlockStore>> {
        let cfg = B2Config::from_env()?;
        let Some(base) = store_path else {
            tracing::warn!("KOTOBA_B2_* set but KOTOBA_STORE_PATH absent — CAR-on-B2 disabled (needs persistent staging + index dir)");
            return None;
        };
        let dir = PathBuf::from(base).join("car_export_pending");
        let (queue, rx) = match Self::new(&dir, 1024) {
            Ok(v) => v,
            Err(e) => {
                tracing::warn!("CAR-on-B2 disabled — staging dir {dir:?}: {e}");
                return None;
            }
        };
        let index = match CarIndex::open(PathBuf::from(base).join("carindex")) {
            Ok(i) => Arc::new(i),
            Err(e) => {
                tracing::warn!("CAR-on-B2 disabled — index dir: {e}");
                return None;
            }
        };
        let client = Arc::new(B2Client::new(cfg));
        let bucket = client.bucket().to_string();
        reconcile(&dir, &queue.tx);
        b2_spawn(run_exporter(
            rx,
            Arc::clone(&client),
            dir,
            Arc::clone(&index),
        ));
        let _ = GLOBAL.set(Arc::new(queue)); // first install wins (one per process)
        tracing::info!(bucket, "CAR-on-B2 cold export + serve enabled");
        Some(Arc::new(B2CarBlockStore::new(client, index)))
    }

    fn staged_path(&self, car_key: &str) -> PathBuf {
        // car_key is a multibase CID — filesystem-safe (base32, no '/').
        self.dir.join(car_key)
    }

    /// Stage `car_bytes` on disk and enqueue `car_key`. Synchronous (called from
    /// the commit path). Best-effort: a full channel still leaves the staged
    /// file, which `reconcile` will pick up on the next startup.
    pub fn enqueue(&self, car_key: &str, car_bytes: &[u8]) {
        if let Err(e) = parse_car_key(car_key) {
            tracing::warn!(car_key, "b2 export: refusing invalid CAR key: {e}");
            return;
        }
        if let Err(e) = write_atomic(&self.staged_path(car_key), car_bytes) {
            tracing::warn!(car_key, "b2 export: staging write failed: {e}");
            return;
        }
        match self.tx.try_send(car_key.to_string()) {
            Ok(()) => {}
            Err(mpsc::error::TrySendError::Full(_)) => {
                // Staged on disk; reconcile() will retry it. Don't block commit.
                tracing::debug!(
                    car_key,
                    "b2 export channel full — left staged for reconcile"
                );
            }
            Err(mpsc::error::TrySendError::Closed(_)) => {
                tracing::warn!(car_key, "b2 export channel closed");
            }
        }
    }
}

/// Atomic file write: temp file in the same dir + rename (POSIX atomic on one FS).
fn write_atomic(path: &Path, data: &[u8]) -> std::io::Result<()> {
    use std::io::Write;
    let tmp = path.with_extension("tmp");
    {
        let mut f = std::fs::File::create(&tmp)?;
        f.write_all(data)?;
        f.flush()?;
    }
    std::fs::rename(&tmp, path)
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

fn verify_staged_car(
    car_key: &str,
    car_bytes: &[u8],
) -> anyhow::Result<Vec<(KotobaCid, u64, u32)>> {
    let expected_root = parse_car_key(car_key)?;
    let (root, entries) = parse_verified_index(car_bytes)?;
    anyhow::ensure!(
        root == expected_root,
        "CAR root CID mismatch: key {}, header {}",
        expected_root.to_multibase(),
        root.to_multibase()
    );
    Ok(entries)
}

/// Re-enqueue any staged CARs left over from a crash. Call once at startup
/// before/while the exporter runs. Returns the number re-enqueued.
pub fn reconcile(dir: &Path, tx: &mpsc::Sender<String>) -> usize {
    let mut n = 0;
    let Ok(entries) = std::fs::read_dir(dir) else {
        return 0;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) == Some("tmp") {
            let _ = std::fs::remove_file(&path); // discard partial stages
            continue;
        }
        if let Some(car_key) = path.file_name().and_then(|f| f.to_str()) {
            if let Err(e) = parse_car_key(car_key) {
                tracing::warn!(car_key, "b2 export: removing invalid staged CAR key: {e}");
                let _ = std::fs::remove_file(&path);
                continue;
            }
            if tx.try_send(car_key.to_string()).is_ok() {
                n += 1;
            }
        }
    }
    if n > 0 {
        tracing::info!(
            reenqueued = n,
            "b2 export: reconciled staged CARs after restart"
        );
    }
    n
}

/// The exporter task: drain the channel, upload staged CARs to B2, populate the
/// read [`CarIndex`] from the confirmed-uploaded CAR, then delete the staging
/// file. Indexing only after a successful PUT guarantees every index entry
/// points at a CAR that is actually in B2.
pub async fn run_exporter(
    mut rx: mpsc::Receiver<String>,
    client: Arc<B2Client>,
    dir: PathBuf,
    index: Arc<CarIndex>,
) {
    tracing::info!(bucket = client.bucket(), dir = %dir.display(), "b2 CAR exporter started");
    while let Some(car_key) = rx.recv().await {
        if let Err(e) = parse_car_key(&car_key) {
            tracing::warn!(car_key, "b2 export: dropping invalid queued CAR key: {e}");
            continue;
        }
        let path = dir.join(&car_key);
        let bytes = match std::fs::read(&path) {
            Ok(b) => b,
            Err(_) => continue, // already uploaded + removed, or never staged
        };
        let entries = match verify_staged_car(&car_key, &bytes) {
            Ok(entries) => entries,
            Err(e) => {
                tracing::warn!(car_key, "skipping unverifiable staged CAR: {e}");
                let _ = std::fs::remove_file(&path);
                continue;
            }
        };
        match client.put_object(&car_key, &bytes).await {
            Ok(()) => {
                // Index every block in this CAR for the serve-from-B2 read path.
                for (bcid, off, len) in entries {
                    if let Err(e) = index.put(&bcid, &car_key, off, len) {
                        tracing::warn!(car_key, "car index write failed: {e}");
                    }
                }
                let _ = std::fs::remove_file(&path);
                tracing::debug!(car_key, bytes = bytes.len(), "b2 CAR uploaded + indexed");
            }
            Err(e) => {
                // Leave the staged file; reconcile retries on next startup.
                tracing::warn!(car_key, "b2 CAR upload failed (left staged): {e}");
            }
        }
    }
    tracing::info!("b2 CAR exporter stopped");
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::car_bundle::CarBundleWriter;

    #[test]
    fn verify_staged_car_accepts_valid_car() {
        let first = b"b2 export block one".to_vec();
        let second = b"b2 export block two".to_vec();
        let first_cid = KotobaCid::from_bytes(&first);
        let second_cid = KotobaCid::from_bytes(&second);
        let root = KotobaCid::from_bytes(b"b2-export-root");
        let mut writer = CarBundleWriter::new(root.clone());
        writer.append(&first_cid, &first);
        writer.append(&second_cid, &second);

        let (car, _index) = writer.finish();
        let entries = verify_staged_car(&root.to_multibase(), &car).unwrap();

        assert_eq!(entries.len(), 2);
        assert_eq!(entries[0].0, first_cid);
        assert_eq!(entries[1].0, second_cid);
    }

    #[test]
    fn verify_staged_car_rejects_corrupt_car() {
        let payload = b"b2 export block".to_vec();
        let cid = KotobaCid::from_bytes(&payload);
        let root = KotobaCid::from_bytes(b"b2-export-root");
        let mut writer = CarBundleWriter::new(root.clone());
        writer.append(&cid, &payload);

        let (mut car, index) = writer.finish();
        let data_offset = index[0].1 as usize;
        car[data_offset] ^= 0xff;

        let err = verify_staged_car(&root.to_multibase(), &car).unwrap_err();
        assert!(
            err.to_string().contains("CID mismatch"),
            "unexpected error: {err}"
        );
    }

    #[test]
    fn verify_staged_car_rejects_root_key_mismatch() {
        let payload = b"b2 export block".to_vec();
        let cid = KotobaCid::from_bytes(&payload);
        let root = KotobaCid::from_bytes(b"b2-export-root");
        let wrong_key = KotobaCid::from_bytes(b"different-export-root").to_multibase();
        let mut writer = CarBundleWriter::new(root);
        writer.append(&cid, &payload);

        let (car, _index) = writer.finish();
        let err = verify_staged_car(&wrong_key, &car).unwrap_err();

        assert!(
            err.to_string().contains("root CID mismatch"),
            "unexpected error: {err}"
        );
    }

    #[test]
    fn enqueue_rejects_non_cid_car_key_without_staging() {
        let temp =
            std::env::temp_dir().join(format!("kotoba-b2-export-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&temp);
        std::fs::create_dir_all(&temp).unwrap();
        let outside = temp.join("escape");
        let (queue, _rx) = CarExportQueue::new(temp.join("pending"), 1).unwrap();

        queue.enqueue("../escape", b"not a CAR");

        assert!(!outside.exists());
        assert_eq!(std::fs::read_dir(temp.join("pending")).unwrap().count(), 0);
        let _ = std::fs::remove_dir_all(&temp);
    }

    #[test]
    fn reconcile_reenqueues_only_canonical_car_keys_and_removes_junk() {
        let temp = std::env::temp_dir().join(format!(
            "kotoba-b2-export-reconcile-test-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&temp);
        std::fs::create_dir_all(&temp).unwrap();
        let valid_key = KotobaCid::from_bytes(b"staged root").to_multibase();
        let valid_path = temp.join(&valid_key);
        let invalid_path = temp.join("not-a-cid");
        let tmp_path = temp.join("partial.tmp");
        std::fs::write(&valid_path, b"valid").unwrap();
        std::fs::write(&invalid_path, b"invalid").unwrap();
        std::fs::write(&tmp_path, b"partial").unwrap();
        let (tx, mut rx) = mpsc::channel(4);

        let reenqueued = reconcile(&temp, &tx);
        drop(tx);

        assert_eq!(reenqueued, 1);
        assert_eq!(rx.try_recv().unwrap(), valid_key);
        assert!(
            valid_path.exists(),
            "valid staged CAR should remain for upload"
        );
        assert!(
            !invalid_path.exists(),
            "invalid staged filename should be discarded at reconcile"
        );
        assert!(!tmp_path.exists(), "partial tmp stage should be discarded");
        assert!(rx.try_recv().is_err());
        let _ = std::fs::remove_dir_all(&temp);
    }
}
