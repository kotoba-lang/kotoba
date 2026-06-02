//! Pure-Rust git packfile reader (pack v2 + idx v2, with OFS/REF delta
//! resolution).
//!
//! Most real repositories — anything cloned or `git gc`'d — keep the bulk of
//! their objects in `objects/pack/*.pack`, indexed by a sibling `*.idx`. This
//! module decodes them so [`crate::repo::import_repo`] can ingest a packed repo
//! and still guarantee byte-exact round-trip: every unpacked object is parsed
//! into a [`GitObject`] whose oid is recomputed and checked against the idx oid.
//!
//! On-disk packs are self-contained (not "thin"), so every `OBJ_REF_DELTA` base
//! resolves within the loaded pack set; we resolve across all packs to be safe.

use crate::error::GitError;
use crate::object::{GitObject, GitObjectKind};
use crate::oid::GitOid;
use crate::Result;
use flate2::read::ZlibDecoder;
use std::collections::HashMap;
use std::io::Read;
use std::path::Path;

const OBJ_COMMIT: u8 = 1;
const OBJ_TREE: u8 = 2;
const OBJ_BLOB: u8 = 3;
const OBJ_TAG: u8 = 4;
const OBJ_OFS_DELTA: u8 = 6;
const OBJ_REF_DELTA: u8 = 7;

struct Pack {
    data: Vec<u8>,
    /// oid → byte offset into `data`.
    by_oid: HashMap<GitOid, u64>,
}

/// All packs found under `objects/pack/`.
pub struct PackSet {
    packs: Vec<Pack>,
}

impl PackSet {
    /// Open every `*.pack` (with matching `*.idx`) under `git_dir/objects/pack`.
    pub fn open(git_dir: &Path) -> Result<Self> {
        let pack_dir = git_dir.join("objects").join("pack");
        let mut packs = Vec::new();
        let Ok(entries) = std::fs::read_dir(&pack_dir) else {
            return Ok(Self { packs });
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().map(|e| e == "idx").unwrap_or(false) {
                let pack_path = path.with_extension("pack");
                if !pack_path.exists() {
                    continue;
                }
                let idx = std::fs::read(&path)?;
                let data = std::fs::read(&pack_path)?;
                let by_oid = parse_idx(&idx)?;
                packs.push(Pack { data, by_oid });
            }
        }
        Ok(Self { packs })
    }

    /// True if no packs are present.
    pub fn is_empty(&self) -> bool {
        self.packs.is_empty()
    }

    /// All oids across all packs.
    pub fn oids(&self) -> Vec<GitOid> {
        let mut out = Vec::new();
        for pack in &self.packs {
            out.extend(pack.by_oid.keys().copied());
        }
        out
    }

    /// Resolve and parse the object for `oid`, if present in any pack.
    /// Verifies the recomputed oid matches `oid`.
    pub fn get(&self, oid: GitOid) -> Result<Option<GitObject>> {
        for (i, pack) in self.packs.iter().enumerate() {
            if let Some(&offset) = pack.by_oid.get(&oid) {
                let (kind, body) = self.unpack_at(i, offset)?;
                let obj = GitObject::new(kind, body);
                if obj.oid() != oid {
                    return Err(GitError::OidMismatch {
                        oid: oid.to_hex(),
                        recomputed: obj.oid().to_hex(),
                    });
                }
                return Ok(Some(obj));
            }
        }
        Ok(None)
    }

    /// Fully resolve the object at `(pack_index, offset)` into `(kind, body)`,
    /// recursing through OFS/REF deltas.
    fn unpack_at(&self, pack_index: usize, offset: u64) -> Result<(GitObjectKind, Vec<u8>)> {
        let pack = &self.packs[pack_index];
        let data = &pack.data;
        let mut pos = offset as usize;
        if pos >= data.len() {
            return Err(GitError::MalformedHeader);
        }

        // object header: type (3 bits) + size (variable)
        let first = data[pos];
        pos += 1;
        let obj_type = (first >> 4) & 0x07;
        let mut _size = (first & 0x0f) as u64;
        let mut shift = 4;
        let mut byte = first;
        while byte & 0x80 != 0 {
            byte = *data.get(pos).ok_or(GitError::MalformedHeader)?;
            pos += 1;
            _size |= ((byte & 0x7f) as u64) << shift;
            shift += 7;
        }

        match obj_type {
            OBJ_COMMIT | OBJ_TREE | OBJ_BLOB | OBJ_TAG => {
                let body = inflate(&data[pos..])?;
                Ok((pack_type_to_kind(obj_type)?, body))
            }
            OBJ_OFS_DELTA => {
                // negative offset to base within this pack
                let (neg, consumed) = read_ofs_varint(&data[pos..])?;
                pos += consumed;
                let base_offset = offset
                    .checked_sub(neg)
                    .ok_or(GitError::MalformedHeader)?;
                let delta = inflate(&data[pos..])?;
                let (base_kind, base_body) = self.unpack_at(pack_index, base_offset)?;
                let body = apply_delta(&base_body, &delta)?;
                Ok((base_kind, body))
            }
            OBJ_REF_DELTA => {
                let base_oid = GitOid::from_raw(
                    data.get(pos..pos + 20).ok_or(GitError::MalformedHeader)?,
                )?;
                pos += 20;
                let delta = inflate(&data[pos..])?;
                let (base_kind, base_body) = self.resolve_ref_base(base_oid)?;
                let body = apply_delta(&base_body, &delta)?;
                Ok((base_kind, body))
            }
            other => Err(GitError::UnknownObjectKind(format!("pack type {other}"))),
        }
    }

    /// Resolve a REF_DELTA base oid across all packs.
    fn resolve_ref_base(&self, oid: GitOid) -> Result<(GitObjectKind, Vec<u8>)> {
        for (i, pack) in self.packs.iter().enumerate() {
            if let Some(&offset) = pack.by_oid.get(&oid) {
                return self.unpack_at(i, offset);
            }
        }
        Err(GitError::ObjectNotFound(oid.to_hex()))
    }
}

fn pack_type_to_kind(t: u8) -> Result<GitObjectKind> {
    Ok(match t {
        OBJ_COMMIT => GitObjectKind::Commit,
        OBJ_TREE => GitObjectKind::Tree,
        OBJ_BLOB => GitObjectKind::Blob,
        OBJ_TAG => GitObjectKind::Tag,
        other => return Err(GitError::UnknownObjectKind(format!("pack type {other}"))),
    })
}

/// Inflate a zlib stream that begins at the start of `buf` (consuming only as
/// many bytes as the stream needs).
fn inflate(buf: &[u8]) -> Result<Vec<u8>> {
    let mut decoder = ZlibDecoder::new(buf);
    let mut out = Vec::new();
    decoder.read_to_end(&mut out).map_err(GitError::Io)?;
    Ok(out)
}

/// Parse a pack idx v2 file into an `oid → offset` map.
fn parse_idx(idx: &[u8]) -> Result<HashMap<GitOid, u64>> {
    // header: magic \377tOc + version 2
    if idx.len() < 8 || idx[0..4] != [0xff, b't', b'O', b'c'] {
        return Err(GitError::MalformedHeader);
    }
    let version = read_u32_be(idx, 4)?;
    if version != 2 {
        return Err(GitError::UnknownObjectKind(format!("idx version {version}")));
    }
    // fanout[255] = object count
    let n = read_u32_be(idx, 8 + 255 * 4)? as usize;

    let oids_off = 8 + 256 * 4;
    let crc_off = oids_off + n * 20;
    let offsets_off = crc_off + n * 4;
    let large_off = offsets_off + n * 4;

    if idx.len() < large_off {
        return Err(GitError::MalformedHeader);
    }

    let mut map = HashMap::with_capacity(n);
    for i in 0..n {
        let oid = GitOid::from_raw(&idx[oids_off + i * 20..oids_off + i * 20 + 20])?;
        let raw = read_u32_be(idx, offsets_off + i * 4)?;
        let offset = if raw & 0x8000_0000 != 0 {
            // high bit set → index into the 8-byte large-offset table
            let large_index = (raw & 0x7fff_ffff) as usize;
            read_u64_be(idx, large_off + large_index * 8)?
        } else {
            raw as u64
        };
        map.insert(oid, offset);
    }
    Ok(map)
}

/// OFS_DELTA base-offset varint (big-endian, with the `+1` continuation trick).
fn read_ofs_varint(buf: &[u8]) -> Result<(u64, usize)> {
    let mut i = 0;
    let mut b = *buf.get(i).ok_or(GitError::MalformedHeader)?;
    i += 1;
    let mut value = (b & 0x7f) as u64;
    while b & 0x80 != 0 {
        b = *buf.get(i).ok_or(GitError::MalformedHeader)?;
        i += 1;
        value = ((value + 1) << 7) | (b & 0x7f) as u64;
    }
    Ok((value, i))
}

/// Little-endian "size" varint used in delta headers and copy sizes.
fn read_size_varint(buf: &[u8], pos: &mut usize) -> Result<u64> {
    let mut value: u64 = 0;
    let mut shift = 0;
    loop {
        let b = *buf.get(*pos).ok_or(GitError::MalformedTree)?;
        *pos += 1;
        value |= ((b & 0x7f) as u64) << shift;
        if b & 0x80 == 0 {
            break;
        }
        shift += 7;
    }
    Ok(value)
}

/// Apply a git delta (`base` + `delta` → result).
fn apply_delta(base: &[u8], delta: &[u8]) -> Result<Vec<u8>> {
    let mut pos = 0;
    let _src_size = read_size_varint(delta, &mut pos)?;
    let dst_size = read_size_varint(delta, &mut pos)? as usize;
    let mut out = Vec::with_capacity(dst_size);

    while pos < delta.len() {
        let op = delta[pos];
        pos += 1;
        if op & 0x80 != 0 {
            // copy from base: variable offset (4) + size (3) fields
            let mut copy_offset: usize = 0;
            for shift in [0u32, 8, 16, 24] {
                if op & (1 << (shift / 8)) != 0 {
                    let b = *delta.get(pos).ok_or(GitError::MalformedTree)?;
                    pos += 1;
                    copy_offset |= (b as usize) << shift;
                }
            }
            let mut copy_size: usize = 0;
            for (j, shift) in [0u32, 8, 16].into_iter().enumerate() {
                if op & (1 << (4 + j)) != 0 {
                    let b = *delta.get(pos).ok_or(GitError::MalformedTree)?;
                    pos += 1;
                    copy_size |= (b as usize) << shift;
                }
            }
            if copy_size == 0 {
                copy_size = 0x10000;
            }
            let end = copy_offset
                .checked_add(copy_size)
                .ok_or(GitError::MalformedTree)?;
            let slice = base
                .get(copy_offset..end)
                .ok_or(GitError::MalformedTree)?;
            out.extend_from_slice(slice);
        } else if op != 0 {
            // insert `op` literal bytes
            let n = op as usize;
            let slice = delta.get(pos..pos + n).ok_or(GitError::MalformedTree)?;
            out.extend_from_slice(slice);
            pos += n;
        } else {
            return Err(GitError::MalformedTree); // op 0 is reserved
        }
    }

    if out.len() != dst_size {
        return Err(GitError::SizeMismatch {
            declared: dst_size,
            actual: out.len(),
        });
    }
    Ok(out)
}

fn read_u32_be(buf: &[u8], at: usize) -> Result<u32> {
    let b = buf.get(at..at + 4).ok_or(GitError::MalformedHeader)?;
    Ok(u32::from_be_bytes([b[0], b[1], b[2], b[3]]))
}

fn read_u64_be(buf: &[u8], at: usize) -> Result<u64> {
    let b = buf.get(at..at + 8).ok_or(GitError::MalformedHeader)?;
    Ok(u64::from_be_bytes([
        b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7],
    ]))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn apply_delta_insert_only() {
        // delta: src_size=0, dst_size=5, then insert "hello"
        let delta = [0x00, 0x05, 0x05, b'h', b'e', b'l', b'l', b'o'];
        let out = apply_delta(b"", &delta).unwrap();
        assert_eq!(out, b"hello");
    }

    #[test]
    fn apply_delta_copy_then_insert() {
        // base = "hello world"; produce "hello!!" =
        //   copy offset=0 size=5 ("hello") + insert "!!"
        let base = b"hello world";
        // copy op: 0x80 | offset-bit0 (0x01) | size-bit0 (0x10) = 0x91
        //   offset byte = 0, size byte = 5
        let delta = [
            0x0b, // src_size = 11
            0x07, // dst_size = 7
            0x91, 0x00, 0x05, // copy base[0..5] = "hello"
            0x02, b'!', b'!', // insert "!!"
        ];
        let out = apply_delta(base, &delta).unwrap();
        assert_eq!(out, b"hello!!");
    }

    #[test]
    fn ofs_varint_roundtrip_small() {
        // single byte, no continuation
        let (v, n) = read_ofs_varint(&[0x05]).unwrap();
        assert_eq!((v, n), (5, 1));
    }

    #[test]
    fn idx_rejects_bad_magic() {
        assert!(parse_idx(&[0, 0, 0, 0, 0, 0, 0, 2]).is_err());
    }
}
