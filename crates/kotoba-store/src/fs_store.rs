//! `FsBlockStore` — embedded, durable, in-process content-addressed block store.
//!
//! The keystone of the "kotoba is its own IPFS block store + pinner" design
//! (ADR-2606041151 Decision A): a local-disk durable tier that writes blocks
//! directly (no Kubo-over-HTTP round-trip), so micro-batch synchronous commit is
//! cheap and the separate Journal WAL becomes unnecessary (the CommitDag is the
//! WAL). Re-introduces the durability the `sled` store provided before its
//! 2026-05-26 removal, without an embedded DB dependency — flatfs-style layout
//! over `std::fs` only.
//!
//! Layout (content-addressed, sharded by the CID's multibase):
//! ```text
//!   <root>/blocks/<shard>/<multibase>     one file per block (raw bytes)
//!   <root>/pins/<multibase>               empty marker = pinned
//! ```
//! Writes are crash-safe: data is written to a temp file in the same directory
//! then `rename`d into place (atomic on a single filesystem). `put_durable`
//! additionally `fsync`s the file and its parent directory.

use bytes::Bytes;
use dashmap::DashMap;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Arc;

/// 4-byte self-describing header prefixed to a zstd-compressed block on disk.
/// dag-cbor blocks start with a CBOR map major byte (`0xA_`), never this magic,
/// so a stored block is unambiguously "compressed" iff it starts with `ZBLK`.
/// Blocks written without compression carry no header and are returned verbatim,
/// keeping the format backward-compatible with stores written before this change.
const ZSTD_MAGIC: &[u8; 4] = b"ZBL1";

#[derive(Clone)]
pub struct FsBlockStore {
    root: Arc<PathBuf>,
    /// In-memory pin set, hydrated from `<root>/pins/` on open and mirrored to
    /// marker files so pins survive restart.
    pinned: Arc<DashMap<[u8; 36], ()>>,
    /// zstd compression level for on-disk blocks. `None` = store raw (legacy).
    /// The CID is always the hash of the *uncompressed* block, so compression is
    /// transparent: `get` decompresses, callers still verify against the CID.
    zstd_level: Option<i32>,
}

impl FsBlockStore {
    /// Open (creating if absent) a durable block store rooted at `root`.
    ///
    /// On-disk block compression is opt-in via `KOTOBA_FS_ZSTD` (the zstd level,
    /// e.g. `KOTOBA_FS_ZSTD=3`; unset or `0` stores blocks uncompressed). Reads
    /// auto-detect per block, so toggling the level only affects newly written
    /// blocks and never breaks existing ones.
    pub fn open(root: impl AsRef<Path>) -> anyhow::Result<Self> {
        let zstd_level = std::env::var("KOTOBA_FS_ZSTD")
            .ok()
            .and_then(|v| v.trim().parse::<i32>().ok())
            .filter(|l| *l > 0);
        Self::open_with_zstd(root, zstd_level)
    }

    /// Open with an explicit zstd level (`None` = uncompressed). Used by tests
    /// and callers that configure compression directly rather than via env.
    pub fn open_with_zstd(root: impl AsRef<Path>, zstd_level: Option<i32>) -> anyhow::Result<Self> {
        let root = root.as_ref().to_path_buf();
        fs::create_dir_all(root.join("blocks"))?;
        fs::create_dir_all(root.join("pins"))?;
        let pinned = DashMap::new();
        // hydrate the pin set from marker files.
        if let Ok(rd) = fs::read_dir(root.join("pins")) {
            for ent in rd.flatten() {
                if let Some(name) = ent.file_name().to_str() {
                    if let Some(cid) = KotobaCid::from_multibase(name) {
                        pinned.insert(cid.0, ());
                    }
                }
            }
        }
        if let Some(level) = zstd_level {
            tracing::info!(level, "FsBlockStore: on-disk zstd block compression ENABLED");
        }
        Ok(Self {
            root: Arc::new(root),
            pinned: Arc::new(pinned),
            zstd_level,
        })
    }

    /// Encode a logical block for on-disk storage: `ZBL1` + zstd frame when
    /// compression is enabled, otherwise the raw bytes unchanged.
    fn encode_block(&self, data: &[u8]) -> std::io::Result<Vec<u8>> {
        match self.zstd_level {
            Some(level) => {
                let mut out = Vec::with_capacity(data.len() / 2 + 8);
                out.extend_from_slice(ZSTD_MAGIC);
                out.extend_from_slice(&zstd::encode_all(data, level)?);
                Ok(out)
            }
            None => Ok(data.to_vec()),
        }
    }

    /// Decode an on-disk block back to its logical bytes (CID preimage).
    fn decode_block(raw: Vec<u8>) -> std::io::Result<Vec<u8>> {
        if raw.len() >= 4 && &raw[..4] == ZSTD_MAGIC {
            zstd::decode_all(&raw[4..])
        } else {
            Ok(raw)
        }
    }

    fn block_path(&self, cid: &KotobaCid) -> PathBuf {
        let mb = cid.to_multibase();
        // shard by the 2 chars after the 'b' multibase prefix (base32 → 1024 dirs)
        let shard = mb.get(1..3).unwrap_or("__");
        self.root.join("blocks").join(shard).join(mb)
    }

    fn pin_path(&self, cid: &KotobaCid) -> PathBuf {
        self.root.join("pins").join(cid.to_multibase())
    }

    fn write_atomic(&self, path: &Path, data: &[u8], sync: bool) -> anyhow::Result<()> {
        let dir = path.parent().expect("block path has a parent");
        fs::create_dir_all(dir)?;
        // already present (content-addressed ⇒ identical bytes): nothing to do.
        if path.exists() {
            return Ok(());
        }
        // Unique temp name per call: the FsBlockStore is written concurrently
        // (synchronous `put_many_durable` on the commit path races the async
        // hot→cold copy spawned by TieredBlockStore::put for the *same* CID).
        // A deterministic `{cid}.tmp` name made the two writers share one temp
        // file, so the second `rename` hit ENOENT after the first renamed it.
        // Salt with a process-global counter to keep each writer's temp private.
        use std::sync::atomic::{AtomicU64, Ordering};
        static TMP_SEQ: AtomicU64 = AtomicU64::new(0);
        let nonce = TMP_SEQ.fetch_add(1, Ordering::Relaxed);
        let tmp = dir.join(format!(
            "{}.{}.tmp",
            path.file_name().and_then(|s| s.to_str()).unwrap_or("blk"),
            nonce
        ));
        // Encode (optionally zstd-compress) before hitting disk. The CID is the
        // hash of `data` (uncompressed), so on-disk form is purely a storage
        // detail that `get` reverses.
        let stored = self.encode_block(data)?;
        {
            let mut f = fs::File::create(&tmp)?;
            f.write_all(&stored)?;
            if sync {
                f.sync_all()?;
            }
        }
        // Another writer may have landed the same content-addressed block
        // between our `exists()` check and here; rename is still correct
        // (identical bytes), but tolerate the winner having removed our race.
        match fs::rename(&tmp, path) {
            Ok(()) => {}
            Err(_) if path.exists() => {
                let _ = fs::remove_file(&tmp);
            }
            Err(e) => return Err(e.into()),
        }
        if sync {
            // fsync the directory so the rename is durable.
            if let Ok(d) = fs::File::open(dir) {
                let _ = d.sync_all();
            }
        }
        Ok(())
    }

    pub fn block_count(&self) -> usize {
        self.all_cids().len()
    }
}

impl BlockStore for FsBlockStore {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.write_atomic(&self.block_path(cid), data, false)
    }

    fn put_durable(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.write_atomic(&self.block_path(cid), data, true)
    }

    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        match fs::read(self.block_path(cid)) {
            Ok(v) => Ok(Some(Bytes::from(Self::decode_block(v)?))),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(e.into()),
        }
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.block_path(cid).exists()
    }

    fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
        match fs::remove_file(self.block_path(cid)) {
            Ok(()) => Ok(()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(e) => Err(e.into()),
        }
    }

    fn pin(&self, cid: &KotobaCid) {
        self.pinned.insert(cid.0, ());
        // best-effort durable marker
        let _ = fs::File::create(self.pin_path(cid));
    }

    fn unpin(&self, cid: &KotobaCid) {
        self.pinned.remove(&cid.0);
        let _ = fs::remove_file(self.pin_path(cid));
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.pinned.contains_key(&cid.0)
    }

    fn all_cids(&self) -> Vec<KotobaCid> {
        let mut out = Vec::new();
        let blocks = self.root.join("blocks");
        let Ok(shards) = fs::read_dir(&blocks) else {
            return out;
        };
        for shard in shards.flatten() {
            let Ok(files) = fs::read_dir(shard.path()) else {
                continue;
            };
            for f in files.flatten() {
                if let Some(name) = f.file_name().to_str() {
                    if name.ends_with(".tmp") {
                        continue;
                    }
                    if let Some(cid) = KotobaCid::from_multibase(name) {
                        out.push(cid);
                    }
                }
            }
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp_root(tag: &str) -> PathBuf {
        let mut p = std::env::temp_dir();
        // unique-ish without Date/rand (both banned in this codebase's scripts,
        // but fine here in tests): use the tag + a static counter via env addr.
        p.push(format!("kotoba-fsstore-test-{tag}-{:p}", &tag));
        let _ = fs::remove_dir_all(&p);
        p
    }

    #[test]
    fn put_get_has_roundtrip() {
        let root = tmp_root("roundtrip");
        let s = FsBlockStore::open(&root).unwrap();
        let data = b"hello kotoba fs";
        let c = KotobaCid::from_bytes(data);
        assert!(!s.has(&c));
        s.put(&c, data).unwrap();
        assert!(s.has(&c));
        assert_eq!(s.get(&c).unwrap().unwrap().as_ref(), data);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn zstd_roundtrip_and_shrinks_on_disk() {
        let root = tmp_root("zstd");
        // Highly compressible payload (repeated text, like kotoba's EDN datoms).
        let data = "kotoba datom :person/name \"Alice\" ".repeat(200);
        let data = data.as_bytes();
        let c = KotobaCid::from_bytes(data);
        let s = FsBlockStore::open_with_zstd(&root, Some(3)).unwrap();
        s.put_durable(&c, data).unwrap();
        // get() returns the logical (decompressed) bytes → CID preimage intact.
        assert_eq!(s.get(&c).unwrap().unwrap().as_ref(), data);
        // on-disk file is the compressed form (header + zstd) and much smaller.
        let on_disk = fs::metadata(s.block_path(&c)).unwrap().len() as usize;
        assert!(on_disk < data.len() / 2, "expected compression, got {on_disk} vs {}", data.len());
        // a fresh handle WITHOUT compression still reads the compressed block
        // (auto-detected via the ZBL1 header) — toggling the level is safe.
        let s2 = FsBlockStore::open_with_zstd(&root, None).unwrap();
        assert_eq!(s2.get(&c).unwrap().unwrap().as_ref(), data);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn survives_reopen() {
        let root = tmp_root("reopen");
        let data = b"durable block";
        let c = KotobaCid::from_bytes(data);
        {
            let s = FsBlockStore::open(&root).unwrap();
            s.put_durable(&c, data).unwrap();
            s.pin(&c);
        }
        // fresh handle on the same root = simulated restart
        let s2 = FsBlockStore::open(&root).unwrap();
        assert!(s2.has(&c), "block must survive reopen");
        assert_eq!(s2.get(&c).unwrap().unwrap().as_ref(), data);
        assert!(s2.is_pinned(&c), "pin must survive reopen");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn delete_and_unpin() {
        let root = tmp_root("delete");
        let s = FsBlockStore::open(&root).unwrap();
        let data = b"deleteme";
        let c = KotobaCid::from_bytes(data);
        s.put(&c, data).unwrap();
        s.pin(&c);
        assert!(s.has(&c) && s.is_pinned(&c));
        s.unpin(&c);
        s.delete(&c).unwrap();
        assert!(!s.has(&c));
        assert!(!s.is_pinned(&c));
        // idempotent delete of an absent block
        s.delete(&c).unwrap();
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn all_cids_enumerates_blocks() {
        let root = tmp_root("allcids");
        let s = FsBlockStore::open(&root).unwrap();
        let mut want = Vec::new();
        for i in 0..5u8 {
            let d = vec![i; 32];
            let c = KotobaCid::from_bytes(&d);
            s.put(&c, &d).unwrap();
            want.push(c.0);
        }
        let mut got: Vec<[u8; 36]> = s.all_cids().iter().map(|c| c.0).collect();
        got.sort();
        want.sort();
        assert_eq!(got, want, "all_cids must round-trip every stored block");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn put_is_idempotent_for_same_content() {
        let root = tmp_root("idem");
        let s = FsBlockStore::open(&root).unwrap();
        let data = b"same bytes";
        let c = KotobaCid::from_bytes(data);
        s.put(&c, data).unwrap();
        s.put(&c, data).unwrap(); // must not error or duplicate
        assert_eq!(s.all_cids().len(), 1);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn tiered_over_fs_is_durable() {
        use crate::{BudgetedBlockStore, MemoryBlockStore, TieredBlockStore};
        let root = tmp_root("tiered");
        let data = b"tiered durable block";
        let c = KotobaCid::from_bytes(data);
        {
            // hot = in-memory cache, durable tier = FsBlockStore (ADR-2606041151 A shape)
            let hot = BudgetedBlockStore::new(MemoryBlockStore::new(), 1 << 20);
            let fs = FsBlockStore::open(&root).unwrap();
            let tiered = TieredBlockStore::new(hot, fs);
            tiered.put_durable(&c, data).unwrap();
            assert_eq!(tiered.get(&c).unwrap().unwrap().as_ref(), data);
        }
        // a fresh FsBlockStore on the same root sees the block — durability is on
        // disk, independent of the in-memory cache (no Kubo / no HTTP involved).
        let fs2 = FsBlockStore::open(&root).unwrap();
        assert!(fs2.has(&c), "put_durable must land the block on the FS tier");
        assert_eq!(fs2.get(&c).unwrap().unwrap().as_ref(), data);
        let _ = fs::remove_dir_all(&root);
    }
}
