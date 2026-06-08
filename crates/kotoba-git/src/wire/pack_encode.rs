//! git **packfile encoder** (pack v2, full objects, no delta compression).
//!
//! [`crate::pack`] decodes packs; this is the write side, used to serve `git
//! clone` / `git fetch`: the server gathers the objects a client wants and
//! serialises them into a single pack stream.
//!
//! We emit every object *undeltified* (pack type = its real kind, body inflated
//! in full). git accepts such packs — delta compression is purely a size
//! optimisation, never a correctness requirement — so this is a complete,
//! spec-valid encoder. The trade-off is wire size, not interoperability.

use crate::object::{GitObject, GitObjectKind};
use crate::oid::GitOid;
use crate::pack::{OBJ_BLOB, OBJ_COMMIT, OBJ_TAG, OBJ_TREE};
use crate::Result;
use flate2::write::ZlibEncoder;
use flate2::Compression;
use sha1::{Digest, Sha1};
use std::io::Write;

fn kind_to_pack_type(kind: GitObjectKind) -> u8 {
    match kind {
        GitObjectKind::Commit => OBJ_COMMIT,
        GitObjectKind::Tree => OBJ_TREE,
        GitObjectKind::Blob => OBJ_BLOB,
        GitObjectKind::Tag => OBJ_TAG,
    }
}

/// Encode the variable-length pack object header: 3-bit type + size, where the
/// size's low 4 bits ride in the first byte and the rest are little-endian
/// 7-bit groups with MSB as the continuation flag.
fn write_obj_header(out: &mut Vec<u8>, pack_type: u8, mut size: usize) {
    let mut byte = (pack_type << 4) | ((size & 0x0f) as u8);
    size >>= 4;
    if size > 0 {
        byte |= 0x80;
    }
    out.push(byte);
    while size > 0 {
        let mut b = (size & 0x7f) as u8;
        size >>= 7;
        if size > 0 {
            b |= 0x80;
        }
        out.push(b);
    }
}

fn deflate(body: &[u8]) -> Result<Vec<u8>> {
    let mut enc = ZlibEncoder::new(Vec::new(), Compression::default());
    enc.write_all(body).map_err(crate::error::GitError::Io)?;
    enc.finish().map_err(crate::error::GitError::Io)
}

/// Serialise `objects` into a complete pack v2 stream (`PACK` header, each
/// object undeltified, 20-byte SHA-1 trailer over everything preceding).
///
/// Object order is preserved; for clone/fetch it does not matter because every
/// object is self-contained (no OFS/REF deltas referencing neighbours).
pub fn encode_pack(objects: &[GitObject]) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    out.extend_from_slice(b"PACK");
    out.extend_from_slice(&2u32.to_be_bytes());
    out.extend_from_slice(&(objects.len() as u32).to_be_bytes());

    for obj in objects {
        write_obj_header(&mut out, kind_to_pack_type(obj.kind), obj.body.len());
        out.extend_from_slice(&deflate(&obj.body)?);
    }

    // Trailer: SHA-1 of all preceding pack bytes (git verifies this on receive).
    let mut hasher = Sha1::new();
    hasher.update(&out);
    out.extend_from_slice(&hasher.finalize());
    Ok(out)
}

/// Convenience: the git oids of `objects`, in encode order (handy for tests and
/// for ref-advertisement bookkeeping).
pub fn oids(objects: &[GitObject]) -> Vec<GitOid> {
    objects.iter().map(GitObject::oid).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::object::TreeEntry;

    #[test]
    fn pack_header_is_well_formed() {
        let pack = encode_pack(&[GitObject::blob(b"hello\n".to_vec())]).unwrap();
        assert_eq!(&pack[0..4], b"PACK");
        assert_eq!(&pack[4..8], &2u32.to_be_bytes()); // version 2
        assert_eq!(&pack[8..12], &1u32.to_be_bytes()); // 1 object
        assert_eq!(pack.len() >= 12 + 20, true); // header + at least the trailer
    }

    #[test]
    fn trailer_is_sha1_of_body() {
        let pack = encode_pack(&[GitObject::blob(b"xyz".to_vec())]).unwrap();
        let (body, trailer) = pack.split_at(pack.len() - 20);
        let mut h = Sha1::new();
        h.update(body);
        assert_eq!(trailer, h.finalize().as_slice());
    }

    #[test]
    fn obj_header_size_encoding_small_and_large() {
        // size 6 → single byte: (type<<4)|6, no continuation
        let mut out = Vec::new();
        write_obj_header(&mut out, OBJ_BLOB, 6);
        assert_eq!(out, vec![(OBJ_BLOB << 4) | 6]);

        // size 0x1234: low nibble 0x4 in byte0; remaining 0x123 = 291 → 7-bit groups.
        // 0x1234 >> 4 = 0x123 (291). 291 & 0x7f = 0x23, 291>>7 = 2.
        let mut out = Vec::new();
        write_obj_header(&mut out, OBJ_TREE, 0x1234);
        assert_eq!(out, vec![(OBJ_TREE << 4) | 0x04 | 0x80, 0x23 | 0x80, 0x02]);
    }

    #[test]
    fn pack_roundtrips_through_the_decoder() {
        // Encode a blob/tree/commit set, then decode it back via the on-disk
        // reader path by writing an idx — but simpler: assert the decoder's
        // streaming ingest (super::super::pack_ingest) reproduces the objects.
        let blob = GitObject::blob(b"hello\n".to_vec());
        let tree = GitObject::tree(&[TreeEntry {
            mode: b"100644".to_vec(),
            name: b"f.txt".to_vec(),
            oid: blob.oid(),
        }]);
        let objs = vec![blob.clone(), tree.clone()];
        let pack = encode_pack(&objs).unwrap();

        let decoded = crate::wire::pack_ingest::parse_pack(&pack, |_| Ok(None)).unwrap();
        let mut got: Vec<_> = decoded.into_iter().map(|(o, _)| o).collect();
        got.sort_by_key(|o| o.oid());
        let mut want = objs;
        want.sort_by_key(|o| o.oid());
        assert_eq!(got, want);
    }
}
