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

#[derive(Clone)]
pub struct FsBlockStore {
    root: Arc<PathBuf>,
    /// In-memory pin set, hydrated from `<root>/pins/` on open and mirrored to
    /// marker files so pins survive restart.
    pinned: Arc<DashMap<[u8; 36], ()>>,
}

impl FsBlockStore {
    /// Open (creating if absent) a durable block store rooted at `root`.
    pub fn open(root: impl AsRef<Path>) -> anyhow::Result<Self> {
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
        Ok(Self {
            root: Arc::new(root),
            pinned: Arc::new(pinned),
        })
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

    fn write_atomic(
        &self,
        cid: &KotobaCid,
        path: &Path,
        data: &[u8],
        sync: bool,
    ) -> anyhow::Result<()> {
        anyhow::ensure!(
            KotobaCid::from_bytes(data) == *cid,
            "cid mismatch: expected {}, got {}",
            cid.to_multibase(),
            KotobaCid::from_bytes(data).to_multibase()
        );
        let dir = path.parent().expect("block path has a parent");
        fs::create_dir_all(dir)?;
        // already present (content-addressed ⇒ identical bytes): nothing to do.
        if path.exists() {
            match fs::read(path) {
                Ok(existing) if KotobaCid::from_bytes(&existing) == *cid => return Ok(()),
                Ok(_) => {
                    tracing::warn!(cid = %cid, path = %path.display(), "repairing corrupt fs block on put");
                    let _ = fs::remove_file(path);
                }
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                Err(e) => return Err(e.into()),
            }
        }
        let tmp = dir.join(format!(
            "{}.tmp",
            path.file_name().and_then(|s| s.to_str()).unwrap_or("blk")
        ));
        {
            let mut f = fs::File::create(&tmp)?;
            f.write_all(data)?;
            if sync {
                f.sync_all()?;
            }
        }
        fs::rename(&tmp, path)?;
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
        self.write_atomic(cid, &self.block_path(cid), data, false)
    }

    fn put_durable(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.write_atomic(cid, &self.block_path(cid), data, true)
    }

    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        let path = self.block_path(cid);
        match fs::read(&path) {
            Ok(v) => {
                if KotobaCid::from_bytes(&v) != *cid {
                    tracing::warn!(cid = %cid, path = %path.display(), "fs block failed CID verification");
                    let _ = fs::remove_file(path);
                    return Ok(None);
                }
                Ok(Some(Bytes::from(v)))
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(e) => Err(e.into()),
        }
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.get(cid).ok().flatten().is_some()
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
                        if self.get(&cid).ok().flatten().is_some() {
                            out.push(cid);
                        }
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
    fn all_cids_skips_and_removes_corrupted_block_file() {
        let root = tmp_root("allcids-corrupt");
        let s = FsBlockStore::open(&root).unwrap();
        let good = b"valid fs block";
        let good_cid = KotobaCid::from_bytes(good);
        let corrupt_cid = KotobaCid::from_bytes(b"expected fs block");
        s.put(&good_cid, good).unwrap();
        let corrupt_path = s.block_path(&corrupt_cid);
        fs::create_dir_all(corrupt_path.parent().unwrap()).unwrap();
        fs::write(&corrupt_path, b"corrupted fs block").unwrap();

        let cids = s.all_cids();

        assert_eq!(cids, vec![good_cid]);
        assert!(
            !corrupt_path.exists(),
            "all_cids should remove files that fail CID verification"
        );
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
    fn put_repairs_corrupt_existing_block_file() {
        let root = tmp_root("put-repair");
        let s = FsBlockStore::open(&root).unwrap();
        let data = b"repair fs block";
        let c = KotobaCid::from_bytes(data);
        let path = s.block_path(&c);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, b"corrupted fs block").unwrap();

        s.put(&c, data).unwrap();

        assert_eq!(fs::read(&path).unwrap(), data);
        assert_eq!(s.get(&c).unwrap().unwrap().as_ref(), data);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn put_durable_repairs_corrupt_existing_block_file() {
        let root = tmp_root("put-durable-repair");
        let s = FsBlockStore::open(&root).unwrap();
        let data = b"durable repair fs block";
        let c = KotobaCid::from_bytes(data);
        let path = s.block_path(&c);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, b"corrupted fs block").unwrap();

        s.put_durable(&c, data).unwrap();

        assert_eq!(fs::read(&path).unwrap(), data);
        assert_eq!(s.get(&c).unwrap().unwrap().as_ref(), data);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn put_rejects_mismatched_cid_without_writing_file() {
        let root = tmp_root("put-mismatch");
        let s = FsBlockStore::open(&root).unwrap();
        let c = KotobaCid::from_bytes(b"expected fs block");

        let err = s.put(&c, b"different fs block").unwrap_err();

        assert!(err.to_string().contains("cid mismatch"));
        assert!(!s.block_path(&c).exists());
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn put_durable_rejects_mismatched_cid_without_writing_file() {
        let root = tmp_root("put-durable-mismatch");
        let s = FsBlockStore::open(&root).unwrap();
        let c = KotobaCid::from_bytes(b"expected fs block");

        let err = s.put_durable(&c, b"different fs block").unwrap_err();

        assert!(err.to_string().contains("cid mismatch"));
        assert!(!s.block_path(&c).exists());
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn get_rejects_and_removes_corrupted_block_file() {
        let root = tmp_root("corrupt");
        let s = FsBlockStore::open(&root).unwrap();
        let data = b"expected fs block";
        let c = KotobaCid::from_bytes(data);
        let path = s.block_path(&c);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, b"corrupted fs block").unwrap();

        assert!(s.get(&c).unwrap().is_none());
        assert!(
            !path.exists(),
            "corrupted block file should be removed after verification failure"
        );

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn has_rejects_corrupted_block_file() {
        let root = tmp_root("corrupt-has");
        let s = FsBlockStore::open(&root).unwrap();
        let data = b"expected fs block";
        let c = KotobaCid::from_bytes(data);
        let path = s.block_path(&c);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, b"corrupted fs block").unwrap();

        assert!(!s.has(&c));
        assert!(
            !path.exists(),
            "has() should remove a block file that fails CID verification"
        );

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
        assert!(
            fs2.has(&c),
            "put_durable must land the block on the FS tier"
        );
        assert_eq!(fs2.get(&c).unwrap().unwrap().as_ref(), data);
        let _ = fs::remove_dir_all(&root);
    }
}
