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

use crate::b2_client::{b2_spawn, B2Client, B2Config};
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
    pub fn new(dir: impl AsRef<Path>, capacity: usize) -> std::io::Result<(Self, mpsc::Receiver<String>)> {
        let dir = dir.as_ref().to_path_buf();
        std::fs::create_dir_all(&dir)?;
        let (tx, rx) = mpsc::channel(capacity);
        Ok((Self { tx, dir }, rx))
    }

    /// Self-contained startup: enable the CAR-on-B2 exporter iff B2 is
    /// configured (`KOTOBA_B2_*`) and a persistent `store_path` is available
    /// for crash-durable staging. Spawns the exporter on the dedicated `b2-io`
    /// runtime and reconciles any CARs staged before a previous crash. Returns
    /// the queue to attach via `QuadStore::with_car_export`, or `None` (disabled).
    pub fn start(store_path: Option<&str>) -> Option<Arc<Self>> {
        let cfg = B2Config::from_env()?;
        let Some(base) = store_path else {
            tracing::warn!("KOTOBA_B2_* set but KOTOBA_STORE_PATH absent — CAR-on-B2 export disabled (needs persistent staging dir)");
            return None;
        };
        let dir = PathBuf::from(base).join("car_export_pending");
        let (queue, rx) = match Self::new(&dir, 1024) {
            Ok(v) => v,
            Err(e) => {
                tracing::warn!("CAR-on-B2 export disabled — staging dir {dir:?}: {e}");
                return None;
            }
        };
        let client = B2Client::new(cfg);
        let bucket = client.bucket().to_string();
        reconcile(&dir, &queue.tx);
        b2_spawn(run_exporter(rx, client, dir));
        let arc = Arc::new(queue);
        let _ = GLOBAL.set(Arc::clone(&arc)); // first install wins (one per process)
        tracing::info!(bucket, "CAR-on-B2 cold export enabled");
        Some(arc)
    }

    fn staged_path(&self, car_key: &str) -> PathBuf {
        // car_key is a multibase CID — filesystem-safe (base32, no '/').
        self.dir.join(car_key)
    }

    /// Stage `car_bytes` on disk and enqueue `car_key`. Synchronous (called from
    /// the commit path). Best-effort: a full channel still leaves the staged
    /// file, which `reconcile` will pick up on the next startup.
    pub fn enqueue(&self, car_key: &str, car_bytes: &[u8]) {
        if let Err(e) = write_atomic(&self.staged_path(car_key), car_bytes) {
            tracing::warn!(car_key, "b2 export: staging write failed: {e}");
            return;
        }
        match self.tx.try_send(car_key.to_string()) {
            Ok(()) => {}
            Err(mpsc::error::TrySendError::Full(_)) => {
                // Staged on disk; reconcile() will retry it. Don't block commit.
                tracing::debug!(car_key, "b2 export channel full — left staged for reconcile");
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
            if tx.try_send(car_key.to_string()).is_ok() {
                n += 1;
            }
        }
    }
    if n > 0 {
        tracing::info!(reenqueued = n, "b2 export: reconciled staged CARs after restart");
    }
    n
}

/// The exporter task: drain the channel, upload staged CARs to B2, delete on
/// success. Runs on the caller's async runtime (typically the server's); the
/// B2 HTTP itself uses the client's own `b2-io` runtime via `b2_block_on` only
/// when called from sync code — here we `await` the async client directly.
pub async fn run_exporter(mut rx: mpsc::Receiver<String>, client: B2Client, dir: PathBuf) {
    tracing::info!(bucket = client.bucket(), dir = %dir.display(), "b2 CAR exporter started");
    while let Some(car_key) = rx.recv().await {
        let path = dir.join(&car_key);
        let bytes = match std::fs::read(&path) {
            Ok(b) => b,
            Err(_) => continue, // already uploaded + removed, or never staged
        };
        match client.put_object(&car_key, &bytes).await {
            Ok(()) => {
                let _ = std::fs::remove_file(&path);
                tracing::debug!(car_key, bytes = bytes.len(), "b2 CAR uploaded");
            }
            Err(e) => {
                // Leave the staged file; reconcile retries on next startup.
                tracing::warn!(car_key, "b2 CAR upload failed (left staged): {e}");
            }
        }
    }
    tracing::info!("b2 CAR exporter stopped");
}
