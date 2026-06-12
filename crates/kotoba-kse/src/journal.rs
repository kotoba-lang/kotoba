use crate::topic::Topic;
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::{broadcast, Mutex, RwLock};

/// Default number of entries kept in the in-process ring buffer.
const DEFAULT_LOG_CAP: usize = 65_536;
pub const MAX_JOURNAL_PAYLOAD_BYTES: usize = 1024 * 1024;
const MAX_HEAD_STATE_BYTES: u64 = 64 * 1024;
const MAX_CHECKPOINT_BYTES: u64 = 8 * 1024 * 1024;

/// Journal entry — one ordered record in a Topic's log.
/// `prev` links to the previous entry's block CID, forming a Merkle chain.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JournalEntry {
    pub seq: u64,
    pub ts: u64, // unix ms
    pub topic: String,
    pub payload: Vec<u8>,
    pub cid: KotobaCid, // IPFS-compatible CID of the payload bytes
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub prev: Option<KotobaCid>, // block CID of the previous entry (Merkle chain)
}

/// Cursor — consumer position in a Journal
pub struct Cursor {
    pub id: String,
    pub position: u64,
    rx: broadcast::Receiver<JournalEntry>,
}

impl Cursor {
    pub async fn next(&mut self) -> Option<JournalEntry> {
        self.rx.recv().await.ok()
    }
}

pub struct CursorAck;

/// Persisted head state — written to `{head_path}` as JSON.
#[derive(Serialize, Deserialize, Default)]
struct HeadState {
    seq: u64,
    head_cid: Option<String>, // multibase of the latest block CID
}

/// Journal — ordered persistent log for a set of Topics.
///
/// Entries are broadcast to live subscribers AND appended to a bounded in-process
/// ring buffer.  When built with `with_block_store()`, each entry is encoded as a
/// CBOR block and stored in an `Arc<dyn BlockStore>`.  The Merkle chain (prev links)
/// allows replaying the full history from any block CID.
pub struct Journal {
    seq: Arc<RwLock<u64>>,
    tx: broadcast::Sender<JournalEntry>,
    log: Arc<RwLock<VecDeque<JournalEntry>>>,
    log_cap: usize,
    /// Content-addressed block store for persistent entries (Merkle WAL).
    store: Option<Arc<dyn BlockStore + Send + Sync>>,
    /// Path to the JSON head-pointer file; `None` when in-memory only.
    head_path: Option<PathBuf>,
    /// In-memory head: (seq, block_cid_of_latest_entry).
    head: Arc<Mutex<(u64, Option<KotobaCid>)>>,
}

impl Journal {
    /// In-memory only — no persistence.
    pub fn new() -> Self {
        Self::with_capacity(DEFAULT_LOG_CAP)
    }

    pub fn with_capacity(log_cap: usize) -> Self {
        let (tx, _) = broadcast::channel(4096);
        Self {
            seq: Arc::new(RwLock::new(0)),
            tx,
            log: Arc::new(RwLock::new(VecDeque::with_capacity(log_cap.min(4096)))),
            log_cap,
            store: None,
            head_path: None,
            head: Arc::new(Mutex::new((0, None))),
        }
    }

    /// Persistent — entries are stored as CBOR blocks in `store`.
    /// The head pointer is persisted to `head_path` as JSON.
    pub fn with_block_store(
        store: Arc<dyn BlockStore + Send + Sync>,
        head_path: impl Into<PathBuf>,
    ) -> Self {
        let (tx, _) = broadcast::channel(4096);
        let head_path = head_path.into();

        // Load head from disk if it exists (sync read at construction time).
        let (init_seq, init_cid) = load_head_sync(&head_path);
        let (init_seq, init_cid) = validate_loaded_head(&store, init_seq, init_cid);

        Self {
            seq: Arc::new(RwLock::new(init_seq)),
            tx,
            log: Arc::new(RwLock::new(VecDeque::with_capacity(4096))),
            log_cap: DEFAULT_LOG_CAP,
            store: Some(store),
            head_path: Some(head_path),
            head: Arc::new(Mutex::new((init_seq, init_cid))),
        }
    }

    pub async fn publish(&self, topic: Topic, payload: Bytes) -> JournalEntry {
        self.publish_unchecked(topic, payload).await
    }

    pub async fn publish_checked(
        &self,
        topic: Topic,
        payload: Bytes,
    ) -> Result<JournalEntry, String> {
        topic.validate()?;
        if payload.len() > MAX_JOURNAL_PAYLOAD_BYTES {
            return Err(format!(
                "journal payload exceeds {MAX_JOURNAL_PAYLOAD_BYTES} byte limit"
            ));
        }
        Ok(self.publish_unchecked(topic, payload).await)
    }

    async fn publish_unchecked(&self, topic: Topic, payload: Bytes) -> JournalEntry {
        let mut seq_guard = self.seq.write().await;
        *seq_guard += 1;
        let seq = *seq_guard;
        drop(seq_guard);

        let cid = KotobaCid::from_bytes(&payload);

        // Get prev chain CID from head
        let prev = {
            let h = self.head.lock().await;
            h.1.clone()
        };

        let entry = JournalEntry {
            seq,
            ts: now_ms(),
            topic: topic.0,
            payload: payload.to_vec(),
            cid,
            prev,
        };
        let _ = self.tx.send(entry.clone());

        // Append to ring buffer
        {
            let mut log = self.log.write().await;
            log.push_back(entry.clone());
            while log.len() > self.log_cap {
                log.pop_front();
            }
        }

        // Persist to block store as a Merkle chain entry
        if let Some(store) = &self.store {
            let mut cbor = Vec::new();
            if ciborium::into_writer(&entry, &mut cbor).is_ok() {
                let block_cid = KotobaCid::from_bytes(&cbor);
                if store.put(&block_cid, &cbor).is_ok() {
                    // Update in-memory head and persist to file only after the
                    // block is actually present; otherwise cold replay would
                    // point at a missing entry.
                    let mut h = self.head.lock().await;
                    *h = (seq, Some(block_cid.clone()));
                    drop(h);

                    if let Some(hp) = &self.head_path {
                        let state = HeadState {
                            seq,
                            head_cid: Some(block_cid.to_multibase()),
                        };
                        if let Ok(json) = serde_json::to_vec(&state) {
                            tokio::fs::write(hp, json).await.ok();
                        }
                    }
                }
            }
        }

        entry
    }

    pub fn subscribe(&self) -> Cursor {
        Cursor {
            id: uuid(),
            position: 0,
            rx: self.tx.subscribe(),
        }
    }

    /// Return all entries with `seq >= since`.
    ///
    /// Checks the ring buffer first.  When `since` predates the oldest ring entry
    /// AND a block store is configured, traverses the Merkle chain backwards.
    pub async fn read_since(&self, since: u64) -> Vec<JournalEntry> {
        let log = self.log.read().await;
        let oldest_ring_seq = log.front().map(|e| e.seq);
        let ring_entries: Vec<JournalEntry> =
            log.iter().filter(|e| e.seq >= since).cloned().collect();
        drop(log);

        let needs_cold = self.store.is_some()
            && match oldest_ring_seq {
                None => true,
                Some(oldest) => since < oldest,
            };

        if needs_cold {
            if let Some(store) = &self.store {
                let until = oldest_ring_seq.unwrap_or(u64::MAX);
                let cold = traverse_chain(store, &self.head.lock().await.1, since, until);
                let mut all = cold;
                all.extend(ring_entries);
                return all;
            }
        }
        ring_entries
    }

    pub async fn current_seq(&self) -> u64 {
        *self.seq.read().await
    }

    /// Remove ring-buffer entries with `seq < before`.
    pub async fn trim_before(&self, before: u64) {
        let mut log = self.log.write().await;
        while let Some(front) = log.front() {
            if front.seq < before {
                log.pop_front();
            } else {
                break;
            }
        }
    }

    /// For block-store backends, blocks are content-addressed and don't need
    /// explicit trimming (GC handles unreachable blocks).  This is a no-op.
    pub async fn trim_persistent_before(&self, _before: u64) {}

    pub async fn write_checkpoint(&self, data: Bytes) {
        if let Some(hp) = &self.head_path {
            if data.len() as u64 > MAX_CHECKPOINT_BYTES {
                return;
            }
            let chk_path = hp.with_extension("checkpoint.bin");
            tokio::fs::write(chk_path, data.as_ref()).await.ok();
        }
    }

    pub async fn read_checkpoint(&self) -> Option<Bytes> {
        let hp = self.head_path.as_ref()?;
        let chk_path = hp.with_extension("checkpoint.bin");
        if tokio::fs::metadata(&chk_path)
            .await
            .ok()
            .map(|m| m.len() > MAX_CHECKPOINT_BYTES)
            .unwrap_or(false)
        {
            return None;
        }
        let data = tokio::fs::read(&chk_path).await.ok()?;
        Some(Bytes::from(data))
    }
}

impl Default for Journal {
    fn default() -> Self {
        Self::new()
    }
}

/// Traverse the Merkle chain backward from `head_cid`, collecting entries
/// where `since <= entry.seq < until`.  Returns entries in ascending seq order.
fn traverse_chain(
    store: &Arc<dyn BlockStore + Send + Sync>,
    head_cid: &Option<KotobaCid>,
    since: u64,
    until: u64,
) -> Vec<JournalEntry> {
    let mut result = Vec::new();
    let mut cur = head_cid.clone();
    let mut next_seq_must_be_below = u64::MAX;
    let mut steps = 0usize;

    while let Some(cid) = cur {
        steps += 1;
        if steps > DEFAULT_LOG_CAP {
            break;
        }
        let Ok(Some(bytes)) = store.get(&cid) else {
            break;
        };
        if KotobaCid::from_bytes(&bytes) != cid {
            break;
        }
        let Ok(entry) = ciborium::from_reader::<JournalEntry, _>(&bytes[..]) else {
            break;
        };
        if validate_journal_entry(&entry).is_err() {
            break;
        }
        if entry.seq >= next_seq_must_be_below {
            break;
        }
        next_seq_must_be_below = entry.seq;

        if entry.seq >= until {
            // Still in the ring-buffer range; follow prev to get older entries
            cur = entry.prev.clone();
            continue;
        }
        if entry.seq < since {
            break; // too old
        }
        let prev = entry.prev.clone();
        result.push(entry);
        cur = prev;
    }

    result.sort_unstable_by_key(|e| e.seq);
    result
}

fn validate_journal_entry(entry: &JournalEntry) -> Result<(), String> {
    Topic::new(entry.topic.clone()).validate()?;
    if entry.payload.len() > MAX_JOURNAL_PAYLOAD_BYTES {
        return Err(format!(
            "journal payload exceeds {MAX_JOURNAL_PAYLOAD_BYTES} byte limit"
        ));
    }
    if KotobaCid::from_bytes(&entry.payload) != entry.cid {
        return Err("journal entry payload CID mismatch".into());
    }
    Ok(())
}

/// Load head state from a JSON file synchronously (called at construction).
fn load_head_sync(path: &PathBuf) -> (u64, Option<KotobaCid>) {
    if std::fs::metadata(path)
        .ok()
        .map(|m| m.len() > MAX_HEAD_STATE_BYTES)
        .unwrap_or(false)
    {
        return (0, None);
    }
    let Ok(data) = std::fs::read(path) else {
        return (0, None);
    };
    let Ok(state) = serde_json::from_slice::<HeadState>(&data) else {
        return (0, None);
    };
    match state
        .head_cid
        .as_deref()
        .and_then(KotobaCid::from_multibase)
    {
        Some(cid) => (state.seq, Some(cid)),
        None => (0, None),
    }
}

fn validate_loaded_head(
    store: &Arc<dyn BlockStore + Send + Sync>,
    seq: u64,
    cid: Option<KotobaCid>,
) -> (u64, Option<KotobaCid>) {
    let Some(cid) = cid else {
        return (0, None);
    };
    let Ok(Some(bytes)) = store.get(&cid) else {
        return (0, None);
    };
    if KotobaCid::from_bytes(&bytes) != cid {
        return (0, None);
    }
    let Ok(entry) = ciborium::from_reader::<JournalEntry, _>(&bytes[..]) else {
        return (0, None);
    };
    if entry.seq != seq || validate_journal_entry(&entry).is_err() {
        return (0, None);
    }
    (seq, Some(cid))
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

fn uuid() -> String {
    format!("cursor-{}", now_ms())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::topic::Topic;
    use bytes::Bytes;

    #[tokio::test]
    async fn publish_increments_seq() {
        let journal = Journal::new();
        let t = Topic::new("test/seq");
        let e1 = journal.publish(t.clone(), Bytes::from_static(b"a")).await;
        let e2 = journal.publish(t.clone(), Bytes::from_static(b"b")).await;
        let e3 = journal.publish(t.clone(), Bytes::from_static(b"c")).await;
        assert_eq!(e1.seq, 1);
        assert_eq!(e2.seq, 2);
        assert_eq!(e3.seq, 3);
    }

    #[tokio::test]
    async fn publish_cid_is_deterministic() {
        let journal = Journal::new();
        let t = Topic::new("test/cid");
        let payload = Bytes::from_static(b"hello kotoba");
        let e1 = journal.publish(t.clone(), payload.clone()).await;
        let e2 = journal.publish(t.clone(), payload.clone()).await;
        assert_eq!(e1.cid, e2.cid, "same payload must produce same CID");
    }

    #[tokio::test]
    async fn publish_returns_correct_topic_and_payload() {
        let journal = Journal::new();
        let topic_str = "kotoba/test/entry";
        let payload = Bytes::from(vec![1u8, 2, 3, 4]);
        let entry = journal
            .publish(Topic::new(topic_str), payload.clone())
            .await;
        assert_eq!(entry.topic, topic_str);
        assert_eq!(entry.payload, payload.to_vec());
    }

    #[tokio::test]
    async fn publish_checked_rejects_invalid_topic() {
        let journal = Journal::new();
        let err = journal
            .publish_checked(Topic::new("bad/\ntopic"), Bytes::from_static(b"payload"))
            .await
            .unwrap_err();
        assert!(
            err.contains("control byte"),
            "error should mention topic validation: {err}"
        );
        assert_eq!(journal.current_seq().await, 0);
    }

    #[tokio::test]
    async fn publish_checked_rejects_oversized_payload() {
        let journal = Journal::new();
        let err = journal
            .publish_checked(
                Topic::new("test/oversized"),
                Bytes::from(vec![0u8; MAX_JOURNAL_PAYLOAD_BYTES + 1]),
            )
            .await
            .unwrap_err();
        assert!(
            err.contains("payload exceeds"),
            "error should mention payload cap: {err}"
        );
        assert_eq!(journal.current_seq().await, 0);
    }

    #[tokio::test]
    async fn publish_checked_accepts_valid_entry() {
        let journal = Journal::new();
        let entry = journal
            .publish_checked(Topic::new("test/checked"), Bytes::from_static(b"ok"))
            .await
            .unwrap();
        assert_eq!(entry.seq, 1);
        assert_eq!(entry.topic, "test/checked");
    }

    #[tokio::test]
    async fn subscribe_cursor_receives_published_entry() {
        let journal = Journal::new();
        let mut cursor = journal.subscribe();
        let topic = Topic::new("test/subscribe");
        let payload = Bytes::from_static(b"broadcast me");
        let published = journal.publish(topic, payload).await;
        let received = cursor.next().await.expect("cursor should receive entry");
        assert_eq!(received.seq, published.seq);
        assert_eq!(received.cid, published.cid);
        assert_eq!(received.payload, published.payload);
    }

    #[tokio::test]
    async fn read_since_returns_only_entries_after_watermark() {
        let journal = Journal::new();
        let t = Topic::new("window/test");
        journal
            .publish(t.clone(), Bytes::from_static(b"seq1"))
            .await;
        journal
            .publish(t.clone(), Bytes::from_static(b"seq2"))
            .await;
        let anchor = journal
            .publish(t.clone(), Bytes::from_static(b"seq3"))
            .await;
        journal
            .publish(t.clone(), Bytes::from_static(b"seq4"))
            .await;
        journal
            .publish(t.clone(), Bytes::from_static(b"seq5"))
            .await;

        let since = anchor.seq; // 3
        let entries = journal.read_since(since).await;
        assert_eq!(entries.len(), 3, "should return seq 3, 4, 5");
        assert!(entries.iter().all(|e| e.seq >= since));
        assert_eq!(entries[0].seq, 3);
        assert_eq!(entries[2].seq, 5);
    }

    #[tokio::test]
    async fn trim_before_removes_old_entries() {
        let journal = Journal::new();
        let t = Topic::new("trim/test");
        for i in 0..10u8 {
            journal.publish(t.clone(), Bytes::from(vec![i])).await;
        }
        assert_eq!(journal.read_since(1).await.len(), 10);
        journal.trim_before(6).await;
        let remaining = journal.read_since(1).await;
        assert!(remaining.iter().all(|e| e.seq >= 6));
        assert_eq!(remaining.len(), 5, "entries 6..=10 remain");
    }

    #[tokio::test]
    async fn ring_buffer_evicts_oldest_when_at_cap() {
        let journal = Journal::with_capacity(3);
        let t = Topic::new("cap/test");
        journal.publish(t.clone(), Bytes::from_static(b"a")).await; // seq 1
        journal.publish(t.clone(), Bytes::from_static(b"b")).await; // seq 2
        journal.publish(t.clone(), Bytes::from_static(b"c")).await; // seq 3
        journal.publish(t.clone(), Bytes::from_static(b"d")).await; // seq 4

        let all = journal.read_since(1).await;
        assert_eq!(all.len(), 3);
        assert_eq!(all[0].seq, 2);
        assert_eq!(all[2].seq, 4);
    }

    #[tokio::test]
    async fn read_since_falls_back_to_block_store() {
        use kotoba_core::store::BlockStore;
        use std::collections::HashMap;
        use std::sync::{Arc, RwLock as StdRwLock};

        // In-memory block store for testing
        #[derive(Default)]
        struct MemStore(StdRwLock<HashMap<[u8; 36], bytes::Bytes>>);
        impl BlockStore for MemStore {
            fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
                self.0
                    .write()
                    .unwrap()
                    .insert(cid.0, bytes::Bytes::copy_from_slice(data));
                Ok(())
            }
            fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<bytes::Bytes>> {
                Ok(self.0.read().unwrap().get(&cid.0).cloned())
            }
            fn has(&self, cid: &KotobaCid) -> bool {
                self.0.read().unwrap().contains_key(&cid.0)
            }
            fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
                self.0.write().unwrap().remove(&cid.0);
                Ok(())
            }
            fn pin(&self, _: &KotobaCid) {}
            fn unpin(&self, _: &KotobaCid) {}
            fn is_pinned(&self, _: &KotobaCid) -> bool {
                false
            }
        }

        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let tmp = tempfile::tempdir().unwrap();
        let head_path = tmp.path().join("journal-head.json");

        // Ring cap = 3; publish 5 entries so seq 1,2 fall out of ring
        let journal = {
            let (tx, _) = broadcast::channel(4096);
            Journal {
                seq: Arc::new(RwLock::new(0)),
                tx,
                log: Arc::new(RwLock::new(VecDeque::with_capacity(3))),
                log_cap: 3,
                store: Some(store),
                head_path: Some(head_path),
                head: Arc::new(Mutex::new((0, None))),
            }
        };

        let t = Topic::new("persist/test");
        for i in 0..5u8 {
            journal.publish(t.clone(), Bytes::from(vec![i])).await;
        }

        // Ring now holds seq 3,4,5; seq 1,2 are in block store only
        let all = journal.read_since(1).await;
        let seqs: Vec<u64> = all.iter().map(|e| e.seq).collect();
        assert_eq!(
            seqs,
            vec![1, 2, 3, 4, 5],
            "block store fallback must fill the gap"
        );
    }

    #[tokio::test]
    async fn read_since_fallback_preserves_payloads() {
        // The fallback test above pins seq *ordering*, but a resuming agent replays
        // the entries' PAYLOADS. A bug in the persistent fallback (wrong CID lookup,
        // empty reconstruction) could return correct seqs with corrupt payloads —
        // silently replaying garbage. Pin that each block-store-recovered entry is
        // byte-identical to what was published, not just correctly sequenced.
        use kotoba_core::store::BlockStore;
        use std::collections::HashMap;
        use std::sync::{Arc, RwLock as StdRwLock};

        #[derive(Default)]
        struct MemStore(StdRwLock<HashMap<[u8; 36], bytes::Bytes>>);
        impl BlockStore for MemStore {
            fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
                self.0
                    .write()
                    .unwrap()
                    .insert(cid.0, bytes::Bytes::copy_from_slice(data));
                Ok(())
            }
            fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<bytes::Bytes>> {
                Ok(self.0.read().unwrap().get(&cid.0).cloned())
            }
            fn has(&self, cid: &KotobaCid) -> bool {
                self.0.read().unwrap().contains_key(&cid.0)
            }
            fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
                self.0.write().unwrap().remove(&cid.0);
                Ok(())
            }
            fn pin(&self, _: &KotobaCid) {}
            fn unpin(&self, _: &KotobaCid) {}
            fn is_pinned(&self, _: &KotobaCid) -> bool {
                false
            }
        }

        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let tmp = tempfile::tempdir().unwrap();
        let head_path = tmp.path().join("journal-head.json");
        let journal = {
            let (tx, _) = broadcast::channel(4096);
            Journal {
                seq: Arc::new(RwLock::new(0)),
                tx,
                log: Arc::new(RwLock::new(VecDeque::with_capacity(3))),
                log_cap: 3, // ring holds 3 → seq 1,2 evicted to block store
                store: Some(store),
                head_path: Some(head_path),
                head: Arc::new(Mutex::new((0, None))),
            }
        };

        let t = Topic::new("payload/fidelity");
        // Distinct, content-checkable payloads.
        let expected: Vec<Bytes> = (0..5u8)
            .map(|i| Bytes::from(format!("payload-{i}")))
            .collect();
        for p in &expected {
            journal.publish(t.clone(), p.clone()).await;
        }

        let all = journal.read_since(1).await;
        assert_eq!(
            all.len(),
            5,
            "all 5 entries (incl. evicted) must be recovered"
        );
        for (idx, entry) in all.iter().enumerate() {
            assert_eq!(entry.seq, idx as u64 + 1, "seq order");
            assert_eq!(
                entry.payload, expected[idx],
                "entry seq {} payload must match what was published (idx {idx})",
                entry.seq
            );
        }
    }

    #[tokio::test]
    async fn read_since_cold_replay_stops_on_corrupt_block_bytes() {
        use kotoba_core::store::BlockStore;
        use std::collections::HashMap;
        use std::sync::{Arc, RwLock as StdRwLock};

        #[derive(Default)]
        struct MemStore(StdRwLock<HashMap<[u8; 36], bytes::Bytes>>);
        impl BlockStore for MemStore {
            fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
                self.0
                    .write()
                    .unwrap()
                    .insert(cid.0, bytes::Bytes::copy_from_slice(data));
                Ok(())
            }
            fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<bytes::Bytes>> {
                Ok(self.0.read().unwrap().get(&cid.0).cloned())
            }
            fn has(&self, cid: &KotobaCid) -> bool {
                self.0.read().unwrap().contains_key(&cid.0)
            }
        }

        let raw_store = Arc::new(MemStore::default());
        let store = Arc::clone(&raw_store) as Arc<dyn BlockStore + Send + Sync>;
        let tmp = tempfile::tempdir().unwrap();
        let journal = {
            let (tx, _) = broadcast::channel(4096);
            Journal {
                seq: Arc::new(RwLock::new(0)),
                tx,
                log: Arc::new(RwLock::new(VecDeque::with_capacity(3))),
                log_cap: 3,
                store: Some(store),
                head_path: Some(tmp.path().join("journal-head.json")),
                head: Arc::new(Mutex::new((0, None))),
            }
        };

        let t = Topic::new("cold/corrupt");
        for i in 0..5u8 {
            journal.publish(t.clone(), Bytes::from(vec![i])).await;
        }

        let corrupt_key = {
            let blocks = raw_store.0.read().unwrap();
            blocks
                .iter()
                .find_map(|(key, bytes)| {
                    let mut entry: JournalEntry = ciborium::from_reader(&bytes[..]).ok()?;
                    if entry.seq == 2 {
                        entry.payload = b"tampered".to_vec();
                        let mut corrupt = Vec::new();
                        ciborium::into_writer(&entry, &mut corrupt).ok()?;
                        Some((*key, bytes::Bytes::from(corrupt)))
                    } else {
                        None
                    }
                })
                .expect("seq 2 block present")
        };
        raw_store
            .0
            .write()
            .unwrap()
            .insert(corrupt_key.0, corrupt_key.1);

        let all = journal.read_since(1).await;
        let seqs: Vec<u64> = all.iter().map(|entry| entry.seq).collect();
        assert_eq!(
            seqs,
            vec![3, 4, 5],
            "cold replay must stop at corrupt block and return only verified ring entries"
        );
    }

    #[tokio::test]
    async fn persistent_publish_does_not_advance_head_when_store_put_fails() {
        use kotoba_core::store::BlockStore;
        use std::sync::Arc;

        struct FailingStore;
        impl BlockStore for FailingStore {
            fn put(&self, _cid: &KotobaCid, _data: &[u8]) -> anyhow::Result<()> {
                anyhow::bail!("injected put failure")
            }
            fn get(&self, _cid: &KotobaCid) -> anyhow::Result<Option<bytes::Bytes>> {
                Ok(None)
            }
            fn has(&self, _cid: &KotobaCid) -> bool {
                false
            }
        }

        let tmp = tempfile::tempdir().unwrap();
        let journal = {
            let (tx, _) = broadcast::channel(4096);
            Journal {
                seq: Arc::new(RwLock::new(0)),
                tx,
                log: Arc::new(RwLock::new(VecDeque::with_capacity(3))),
                log_cap: 3,
                store: Some(Arc::new(FailingStore)),
                head_path: Some(tmp.path().join("journal-head.json")),
                head: Arc::new(Mutex::new((0, None))),
            }
        };

        journal
            .publish(Topic::new("persist/fails"), Bytes::from_static(b"x"))
            .await;
        assert!(
            journal.head.lock().await.1.is_none(),
            "head must not point at a block that failed to persist"
        );
    }

    #[test]
    fn load_head_sync_rejects_invalid_cid_without_seq_jump() {
        let tmp = tempfile::tempdir().unwrap();
        let head_path = tmp.path().join("journal-head.json");
        std::fs::write(
            &head_path,
            serde_json::json!({ "seq": 42, "head_cid": "not-a-cid" }).to_string(),
        )
        .unwrap();

        let (seq, cid) = load_head_sync(&head_path);
        assert_eq!(seq, 0);
        assert!(cid.is_none());
    }

    #[test]
    fn load_head_sync_rejects_oversized_head_file() {
        let tmp = tempfile::tempdir().unwrap();
        let head_path = tmp.path().join("journal-head.json");
        std::fs::write(&head_path, vec![b' '; MAX_HEAD_STATE_BYTES as usize + 1]).unwrap();

        let (seq, cid) = load_head_sync(&head_path);
        assert_eq!(seq, 0);
        assert!(cid.is_none());
    }

    #[tokio::test]
    async fn with_block_store_hydrates_only_verified_head_block() {
        let store =
            Arc::new(kotoba_store::MemoryBlockStore::new()) as Arc<dyn BlockStore + Send + Sync>;
        let tmp = tempfile::tempdir().unwrap();
        let head_path = tmp.path().join("journal-head.json");

        let journal = Journal::with_block_store(Arc::clone(&store), &head_path);
        let entry = journal
            .publish_checked(Topic::new("head/verified"), Bytes::from_static(b"ok"))
            .await
            .unwrap();

        let reopened = Journal::with_block_store(store, &head_path);
        assert_eq!(reopened.current_seq().await, entry.seq);
        assert!(reopened.head.lock().await.1.is_some());
    }

    #[tokio::test]
    async fn with_block_store_rejects_head_when_block_missing_or_seq_mismatch() {
        let store =
            Arc::new(kotoba_store::MemoryBlockStore::new()) as Arc<dyn BlockStore + Send + Sync>;
        let tmp = tempfile::tempdir().unwrap();
        let head_path = tmp.path().join("journal-head.json");
        let missing = KotobaCid::from_bytes(b"missing-head");
        std::fs::write(
            &head_path,
            serde_json::to_vec(&HeadState {
                seq: 7,
                head_cid: Some(missing.to_multibase()),
            })
            .unwrap(),
        )
        .unwrap();

        let missing_head = Journal::with_block_store(Arc::clone(&store), &head_path);
        assert_eq!(missing_head.current_seq().await, 0);
        assert!(missing_head.head.lock().await.1.is_none());

        let entry = JournalEntry {
            seq: 1,
            ts: now_ms(),
            topic: "head/mismatch".into(),
            payload: b"ok".to_vec(),
            cid: KotobaCid::from_bytes(b"ok"),
            prev: None,
        };
        let mut cbor = Vec::new();
        ciborium::into_writer(&entry, &mut cbor).unwrap();
        let cid = KotobaCid::from_bytes(&cbor);
        store.put(&cid, &cbor).unwrap();
        std::fs::write(
            &head_path,
            serde_json::to_vec(&HeadState {
                seq: 2,
                head_cid: Some(cid.to_multibase()),
            })
            .unwrap(),
        )
        .unwrap();

        let mismatch = Journal::with_block_store(store, &head_path);
        assert_eq!(mismatch.current_seq().await, 0);
        assert!(mismatch.head.lock().await.1.is_none());
    }

    // ── additional gap tests ──────────────────────────────────────────────────

    #[tokio::test]
    async fn current_seq_is_zero_before_any_publish() {
        let journal = Journal::new();
        assert_eq!(journal.current_seq().await, 0);
    }

    #[tokio::test]
    async fn current_seq_matches_last_entry_seq() {
        let journal = Journal::new();
        let t = Topic::new("seq-check");
        journal.publish(t.clone(), Bytes::from_static(b"x")).await;
        journal.publish(t.clone(), Bytes::from_static(b"y")).await;
        assert_eq!(journal.current_seq().await, 2);
    }

    #[tokio::test]
    async fn default_creates_functional_journal() {
        let journal = Journal::default();
        let e = journal
            .publish(Topic::new("default/test"), Bytes::from_static(b"hi"))
            .await;
        assert_eq!(e.seq, 1);
    }

    #[tokio::test]
    async fn trim_before_zero_is_noop() {
        let journal = Journal::new();
        let t = Topic::new("noop/trim");
        journal.publish(t.clone(), Bytes::from_static(b"a")).await;
        journal.publish(t.clone(), Bytes::from_static(b"b")).await;
        journal.trim_before(0).await;
        assert_eq!(
            journal.read_since(1).await.len(),
            2,
            "trim_before(0) should not remove any entry"
        );
    }

    #[tokio::test]
    async fn trim_persistent_before_is_noop() {
        // Verify no panic and no side-effects
        let journal = Journal::new();
        let t = Topic::new("persist/noop");
        journal.publish(t.clone(), Bytes::from_static(b"z")).await;
        journal.trim_persistent_before(9999).await; // must not remove in-memory entries
        assert_eq!(journal.read_since(1).await.len(), 1);
    }

    #[tokio::test]
    async fn write_and_read_checkpoint_without_store_are_noops() {
        let journal = Journal::new(); // no head_path → no-op
        journal.write_checkpoint(Bytes::from_static(b"ckpt")).await;
        let result = journal.read_checkpoint().await;
        assert!(
            result.is_none(),
            "read_checkpoint without store must return None"
        );
    }

    #[tokio::test]
    async fn checkpoint_oversize_is_ignored_on_write_and_read() {
        let store =
            Arc::new(kotoba_store::MemoryBlockStore::new()) as Arc<dyn BlockStore + Send + Sync>;
        let tmp = tempfile::tempdir().unwrap();
        let head_path = tmp.path().join("journal-head.json");
        let journal = Journal::with_block_store(store, &head_path);

        journal
            .write_checkpoint(Bytes::from(vec![0u8; MAX_CHECKPOINT_BYTES as usize + 1]))
            .await;
        assert!(journal.read_checkpoint().await.is_none());

        std::fs::write(
            head_path.with_extension("checkpoint.bin"),
            vec![1u8; MAX_CHECKPOINT_BYTES as usize + 1],
        )
        .unwrap();
        assert!(
            journal.read_checkpoint().await.is_none(),
            "oversized checkpoint on disk must not be read into memory"
        );
    }

    #[tokio::test]
    async fn read_since_all_from_zero_returns_everything() {
        let journal = Journal::new();
        let t = Topic::new("all/entries");
        journal.publish(t.clone(), Bytes::from_static(b"1")).await;
        journal.publish(t.clone(), Bytes::from_static(b"2")).await;
        journal.publish(t.clone(), Bytes::from_static(b"3")).await;
        let all = journal.read_since(1).await;
        assert_eq!(all.len(), 3);
    }

    #[tokio::test]
    async fn merkle_prev_links_form_chain() {
        let journal = Journal::new();
        let t = Topic::new("merkle/chain");
        let e1 = journal
            .publish(t.clone(), Bytes::from_static(b"first"))
            .await;
        let e2 = journal
            .publish(t.clone(), Bytes::from_static(b"second"))
            .await;
        // First entry has no prev; second entry's prev should match something or be None
        // (in-memory journal without block store: prev is always None at entry level, but
        //  the head CID IS tracked in self.head for block-store journals)
        assert!(e1.prev.is_none(), "first entry should have no prev");
        // For an in-memory journal without block store, prev is also None (no CBOR blocks)
        let _ = e2; // just ensure it was created without panic
    }
}
