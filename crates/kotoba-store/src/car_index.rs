//! `CarIndex` — persistent `block_cid → (car_key, offset, len)` map for the
//! Phase 2 serve-from-B2 read path.
//!
//! Random-access reads from B2 need to know which CAR object holds a given
//! block and where inside it. Holding that map in RAM does not scale
//! (`car_bundle::CarBlockIndex` is a `HashMap` ≈ 30 GB at 400M blocks), so this
//! is an on-disk, sharded-by-multibase layout mirroring `FsBlockStore`:
//!
//! ```text
//!   <root>/<shard>/<block_multibase>   →  "<car_key>\n<offset>\n<len>"
//! ```
//!
//! One tiny record per block. Populated by the exporter after a CAR's PUT is
//! confirmed (and by restore), so an entry always points at a CAR that is
//! actually in B2. A `get` is one cheap local read; the block itself is then a
//! single ranged GET (`B2CarBlockStore`).

use kotoba_core::cid::KotobaCid;
use std::io::Write;
use std::path::{Path, PathBuf};

#[derive(Clone)]
pub struct CarIndex {
    root: PathBuf,
}

/// `(car_key, offset, len)` — where a block lives inside which CAR object.
pub type Location = (String, u64, u32);

impl CarIndex {
    pub fn open(root: impl AsRef<Path>) -> std::io::Result<Self> {
        let root = root.as_ref().to_path_buf();
        std::fs::create_dir_all(&root)?;
        Ok(Self { root })
    }

    fn path(&self, cid: &KotobaCid) -> PathBuf {
        let mb = cid.to_multibase();
        // shard by the 2 chars after the 'b' multibase prefix (mirrors FsBlockStore)
        let shard = mb.get(1..3).unwrap_or("__").to_string();
        self.root.join(shard).join(mb)
    }

    /// Record that `cid`'s block lives in `car_key` at `[offset, offset+len)`.
    /// Atomic (temp + rename); idempotent (content-addressed).
    pub fn put(&self, cid: &KotobaCid, car_key: &str, offset: u64, len: u32) -> std::io::Result<()> {
        let path = self.path(cid);
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        let tmp = path.with_extension("tmp");
        {
            let mut f = std::fs::File::create(&tmp)?;
            write!(f, "{car_key}\n{offset}\n{len}")?;
            f.flush()?;
        }
        std::fs::rename(&tmp, &path)
    }

    /// Look up where `cid`'s block lives, if known.
    pub fn get(&self, cid: &KotobaCid) -> Option<Location> {
        let s = std::fs::read_to_string(self.path(cid)).ok()?;
        let mut it = s.splitn(3, '\n');
        let car_key = it.next()?.to_string();
        let offset = it.next()?.parse().ok()?;
        let len = it.next()?.parse().ok()?;
        Some((car_key, offset, len))
    }

    pub fn contains(&self, cid: &KotobaCid) -> bool {
        self.path(cid).exists()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn put_get_roundtrip() {
        let dir = std::env::temp_dir().join(format!("carindex_test_{}", std::process::id()));
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        assert!(!idx.contains(&cid));
        idx.put(&cid, "bafycarkey", 72, 256).unwrap();
        assert!(idx.contains(&cid));
        assert_eq!(idx.get(&cid), Some(("bafycarkey".to_string(), 72, 256)));
        let missing = KotobaCid::from_bytes(b"nope");
        assert_eq!(idx.get(&missing), None);
        let _ = std::fs::remove_dir_all(&dir);
    }
}
