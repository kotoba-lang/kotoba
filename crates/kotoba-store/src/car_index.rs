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

use crate::car_bundle::{HEADER_LEN, MAX_CAR_BLOCK_BYTES, MAX_CAR_BYTES};
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
    pub fn put(
        &self,
        cid: &KotobaCid,
        car_key: &str,
        offset: u64,
        len: u32,
    ) -> std::io::Result<()> {
        if !valid_car_key(car_key) {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "car_key must be a canonical Kotoba CID",
            ));
        }
        if !valid_location(offset, len) {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "car index location is outside supported CAR bounds",
            ));
        }
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
        parse_location_record(&s)
    }

    pub fn contains(&self, cid: &KotobaCid) -> bool {
        self.get(cid).is_some()
    }
}

fn valid_car_key(car_key: &str) -> bool {
    KotobaCid::from_multibase(car_key)
        .map(|cid| cid.to_multibase() == car_key)
        .unwrap_or(false)
}

fn parse_location_record(record: &str) -> Option<Location> {
    let mut it = record.split('\n');
    let car_key = it.next()?;
    if !valid_car_key(car_key) {
        return None;
    }
    let offset = it.next()?.parse().ok()?;
    let len = it.next()?.parse().ok()?;
    if it.next().is_some() {
        return None;
    }
    if !valid_location(offset, len) {
        return None;
    }
    Some((car_key.to_string(), offset, len))
}

fn valid_location(offset: u64, len: u32) -> bool {
    if offset < HEADER_LEN as u64 || len > MAX_CAR_BLOCK_BYTES {
        return false;
    }
    let Some(end) = offset.checked_add(len as u64) else {
        return false;
    };
    end <= MAX_CAR_BYTES as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(name: &str) -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("{name}_{}_{}", std::process::id(), nanos))
    }

    #[test]
    fn put_get_roundtrip() {
        let dir = temp_dir("carindex_test");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        let car_key = KotobaCid::from_bytes(b"car-1").to_multibase();
        assert!(!idx.contains(&cid));
        idx.put(&cid, &car_key, 72, 256).unwrap();
        assert!(idx.contains(&cid));
        assert_eq!(idx.get(&cid), Some((car_key, 72, 256)));
        let missing = KotobaCid::from_bytes(b"nope");
        assert_eq!(idx.get(&missing), None);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn contains_ignores_corrupt_record_file() {
        let dir = temp_dir("carindex_corrupt");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        let path = idx.path(&cid);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        let car_key = KotobaCid::from_bytes(b"car-1").to_multibase();
        std::fs::write(&path, format!("{car_key}\nnot-an-offset\n256")).unwrap();

        assert_eq!(idx.get(&cid), None);
        assert!(!idx.contains(&cid));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn put_rejects_location_outside_supported_car_bounds() {
        let dir = temp_dir("carindex_bad_location_put");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        let car_key = KotobaCid::from_bytes(b"car-1").to_multibase();

        for (offset, len) in [
            (HEADER_LEN as u64 - 1, 1),
            (HEADER_LEN as u64, MAX_CAR_BLOCK_BYTES + 1),
            (MAX_CAR_BYTES as u64, 1),
            (u64::MAX, 1),
        ] {
            let err = idx.put(&cid, &car_key, offset, len).unwrap_err();
            assert_eq!(err.kind(), std::io::ErrorKind::InvalidInput);
        }
        assert!(!idx.contains(&cid));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn get_rejects_record_with_location_outside_supported_car_bounds() {
        let dir = temp_dir("carindex_bad_location_get");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        let path = idx.path(&cid);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        let car_key = KotobaCid::from_bytes(b"car-1").to_multibase();

        for (offset, len) in [
            (HEADER_LEN as u64 - 1, 1),
            (HEADER_LEN as u64, MAX_CAR_BLOCK_BYTES + 1),
            (MAX_CAR_BYTES as u64, 1),
            (u64::MAX, 1),
        ] {
            std::fs::write(&path, format!("{car_key}\n{offset}\n{len}")).unwrap();
            assert_eq!(
                idx.get(&cid),
                None,
                "bad location should be ignored: offset={offset}, len={len}"
            );
            assert!(!idx.contains(&cid));
        }

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn get_rejects_record_with_empty_car_key() {
        let dir = temp_dir("carindex_empty_key");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        let path = idx.path(&cid);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(&path, "\n72\n256").unwrap();

        assert_eq!(idx.get(&cid), None);
        assert!(!idx.contains(&cid));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn get_rejects_record_with_extra_fields() {
        let dir = temp_dir("carindex_extra_fields");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        let path = idx.path(&cid);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        let car_key = KotobaCid::from_bytes(b"car-1").to_multibase();
        std::fs::write(&path, format!("{car_key}\n72\n256\nextra")).unwrap();

        assert_eq!(idx.get(&cid), None);
        assert!(!idx.contains(&cid));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn get_rejects_record_with_trailing_newline() {
        let dir = temp_dir("carindex_trailing_newline");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        let path = idx.path(&cid);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        let car_key = KotobaCid::from_bytes(b"car-1").to_multibase();
        std::fs::write(&path, format!("{car_key}\n72\n256\n")).unwrap();

        assert_eq!(idx.get(&cid), None);
        assert!(!idx.contains(&cid));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn put_rejects_non_canonical_car_key() {
        let dir = temp_dir("carindex_bad_key");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");

        let empty = idx.put(&cid, "", 72, 256).unwrap_err();
        let newline = idx.put(&cid, "car\nkey", 72, 256).unwrap_err();
        let pathish = idx.put(&cid, "../escape", 72, 256).unwrap_err();
        let legacy = idx.put(&cid, "bafycarkey", 72, 256).unwrap_err();

        assert_eq!(empty.kind(), std::io::ErrorKind::InvalidInput);
        assert_eq!(newline.kind(), std::io::ErrorKind::InvalidInput);
        assert_eq!(pathish.kind(), std::io::ErrorKind::InvalidInput);
        assert_eq!(legacy.kind(), std::io::ErrorKind::InvalidInput);
        assert!(!idx.contains(&cid));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn get_rejects_record_with_non_canonical_car_key() {
        let dir = temp_dir("carindex_non_canonical_key");
        let idx = CarIndex::open(&dir).unwrap();
        let cid = KotobaCid::from_bytes(b"block-1");
        let path = idx.path(&cid);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(&path, "../escape\n72\n256").unwrap();

        assert_eq!(idx.get(&cid), None);
        assert!(!idx.contains(&cid));

        let _ = std::fs::remove_dir_all(&dir);
    }
}
