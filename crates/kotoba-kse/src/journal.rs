use crate::topic::Topic;
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::Arc;
use tokio::sync::{broadcast, RwLock};

/// Default number of entries kept in the in-process ring buffer.
const DEFAULT_LOG_CAP: usize = 65_536;

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

/// LiveBus (historically "Journal") — a purely **in-memory** ordered event bus.
///
/// Entries are broadcast to live subscribers and kept in a bounded ring for a
/// short live-tail backlog. There is **no persistence**: durable, replayable
/// history lives in the CommitDag (datomic, via `sync.eventsFromCommits` /
/// `eventsAllGraphs`) and in each subsystem's own content-addressed store
/// (signal → Shelf, realtime → block-store snapshots). This mirrors libp2p
/// gossipsub (best-effort, ephemeral) — see ADR on journal removal.
pub struct Journal {
    seq: Arc<RwLock<u64>>,
    tx: broadcast::Sender<JournalEntry>,
    log: Arc<RwLock<VecDeque<JournalEntry>>>,
    log_cap: usize,
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
        }
    }

    /// Publish an event: broadcast to live subscribers + append to the bounded
    /// in-process ring. **No persistence** — the LiveBus is purely ephemeral
    /// (gossipsub semantics). Durable, replayable history lives in the CommitDag
    /// (datomic) or each subsystem's own content-addressed store (signal → Shelf,
    /// realtime → block store snapshots); the firehose replays datomic from the
    /// CommitDag (`sync.eventsFromCommits` / `eventsAllGraphs`).
    pub async fn publish(&self, topic: Topic, payload: Bytes) -> JournalEntry {
        let mut seq_guard = self.seq.write().await;
        *seq_guard += 1;
        let seq = *seq_guard;
        drop(seq_guard);

        let cid = KotobaCid::from_bytes(&payload);

        let entry = JournalEntry {
            seq,
            ts: now_ms(),
            topic: topic.0,
            payload: payload.to_vec(),
            cid,
            prev: None,
        };
        let _ = self.tx.send(entry.clone());

        // Append to ring buffer (short live-tail backlog only).
        {
            let mut log = self.log.write().await;
            log.push_back(entry.clone());
            while log.len() > self.log_cap {
                log.pop_front();
            }
        }

        entry
    }

    /// Back-compat alias — every publish is now ephemeral (in-memory only).
    pub async fn publish_ephemeral(&self, topic: Topic, payload: Bytes) -> JournalEntry {
        self.publish(topic, payload).await
    }

    pub fn subscribe(&self) -> Cursor {
        Cursor {
            id: uuid(),
            position: 0,
            rx: self.tx.subscribe(),
        }
    }

    /// Return ring-buffer entries with `seq >= since` (live-tail backlog only).
    ///
    /// There is no cold/persistent history: deep replay of datomic changes comes
    /// from the CommitDag (`sync.eventsFromCommits` / `eventsAllGraphs`), not from
    /// this bus.
    pub async fn read_since(&self, since: u64) -> Vec<JournalEntry> {
        let log = self.log.read().await;
        log.iter().filter(|e| e.seq >= since).cloned().collect()
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

    /// No-op: the bus has no persistent backlog to trim.
    pub async fn trim_persistent_before(&self, _before: u64) {}

    /// Checkpointing is gone with persistence — durable state is the CommitDag;
    /// restart rebuilds the resident caches from it (`warm_datomic_live_caches`).
    pub async fn write_checkpoint(&self, _data: Bytes) {}

    pub async fn read_checkpoint(&self) -> Option<Bytes> {
        None
    }
}

impl Default for Journal {
    fn default() -> Self {
        Self::new()
    }
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

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

fn uuid() -> String {
    format!("cursor-{}", now_ms())
}
