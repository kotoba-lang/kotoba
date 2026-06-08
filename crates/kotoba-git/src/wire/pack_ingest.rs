//! Streaming **packfile ingest** — parse a pack received over the wire (from
//! `git push`) into [`GitObject`]s.
//!
//! Unlike [`crate::pack`], which is driven by an on-disk `*.idx` (random access
//! by offset), a pushed pack arrives as a single self-describing byte stream
//! with no index: a `PACK` header, `N` objects laid out sequentially, then a
//! 20-byte SHA-1 trailer. We must walk it front-to-back, recording each
//! object's byte offset so that `OBJ_OFS_DELTA` (negative offset to base) and
//! `OBJ_REF_DELTA` (base by oid) can be resolved.
//!
//! Bases may legitimately appear *after* their deltas, and a pushed pack may be
//! **thin** (a `REF_DELTA` whose base is an object the server already has, not
//! in the pack). We therefore resolve by fixpoint: repeatedly sweep the
//! unresolved objects, applying any whose base is now available (in-pack or via
//! the `resolve_external` callback), until everything resolves or a sweep makes
//! no progress (a genuinely broken/incomplete pack).

use crate::error::GitError;
use crate::object::{GitObject, GitObjectKind};
use crate::oid::GitOid;
use crate::pack::{
    apply_delta, inflate_counted, pack_type_to_kind, read_ofs_varint, OBJ_BLOB, OBJ_COMMIT,
    OBJ_OFS_DELTA, OBJ_REF_DELTA, OBJ_TAG, OBJ_TREE,
};
use crate::Result;
use sha1::{Digest, Sha1};
use std::collections::HashMap;

/// A raw, not-yet-resolved pack object record.
enum Raw {
    Full {
        kind: GitObjectKind,
        body: Vec<u8>,
    },
    OfsDelta {
        base_offset: usize,
        delta: Vec<u8>,
    },
    RefDelta {
        base_oid: GitOid,
        delta: Vec<u8>,
    },
}

/// Parse a complete pack byte stream into `(object, oid)` pairs.
///
/// `resolve_external` supplies the body of a base object the server already
/// stores (for thin packs); return `Ok(None)` if it is unknown. Every returned
/// object's oid is recomputed from its framed bytes — the caller can trust it.
pub fn parse_pack<F>(pack: &[u8], resolve_external: F) -> Result<Vec<(GitObject, GitOid)>>
where
    F: Fn(GitOid) -> Result<Option<(GitObjectKind, Vec<u8>)>>,
{
    // Header + trailer integrity.
    if pack.len() < 12 + 20 || &pack[0..4] != b"PACK" {
        return Err(GitError::MalformedHeader);
    }
    let version = u32::from_be_bytes([pack[4], pack[5], pack[6], pack[7]]);
    if version != 2 {
        return Err(GitError::UnknownObjectKind(format!("pack version {version}")));
    }
    let count = u32::from_be_bytes([pack[8], pack[9], pack[10], pack[11]]) as usize;

    let body_end = pack.len() - 20;
    let mut hasher = Sha1::new();
    hasher.update(&pack[..body_end]);
    if hasher.finalize()[..] != pack[body_end..] {
        return Err(GitError::MalformedHeader); // trailer checksum mismatch
    }

    // ── Pass 1: split the stream into raw records, keyed by byte offset. ──────
    let mut raws: Vec<(usize, Raw)> = Vec::with_capacity(count);
    let mut pos = 12;
    for _ in 0..count {
        let obj_offset = pos;
        let (obj_type, _size, hdr_len) = parse_obj_header(pack, pos)?;
        pos += hdr_len;
        match obj_type {
            OBJ_COMMIT | OBJ_TREE | OBJ_BLOB | OBJ_TAG => {
                let (body, consumed) = inflate_counted(&pack[pos..])?;
                pos += consumed;
                raws.push((
                    obj_offset,
                    Raw::Full {
                        kind: pack_type_to_kind(obj_type)?,
                        body,
                    },
                ));
            }
            OBJ_OFS_DELTA => {
                let (neg, used) = read_ofs_varint(&pack[pos..])?;
                pos += used;
                let base_offset = obj_offset
                    .checked_sub(neg as usize)
                    .ok_or(GitError::MalformedHeader)?;
                let (delta, consumed) = inflate_counted(&pack[pos..])?;
                pos += consumed;
                raws.push((obj_offset, Raw::OfsDelta { base_offset, delta }));
            }
            OBJ_REF_DELTA => {
                let base_oid =
                    GitOid::from_raw(pack.get(pos..pos + 20).ok_or(GitError::MalformedHeader)?)?;
                pos += 20;
                let (delta, consumed) = inflate_counted(&pack[pos..])?;
                pos += consumed;
                raws.push((obj_offset, Raw::RefDelta { base_oid, delta }));
            }
            other => return Err(GitError::UnknownObjectKind(format!("pack type {other}"))),
        }
    }
    if pos != body_end {
        return Err(GitError::MalformedHeader); // trailing junk or short read
    }

    // ── Pass 2: resolve by fixpoint (handles out-of-order + thin bases). ─────
    let mut by_offset: HashMap<usize, (GitObjectKind, Vec<u8>)> = HashMap::with_capacity(count);
    let mut by_oid: HashMap<GitOid, (GitObjectKind, Vec<u8>)> = HashMap::with_capacity(count);
    let mut pending: Vec<usize> = (0..raws.len()).collect();

    while !pending.is_empty() {
        let mut next_pending = Vec::new();
        let mut progressed = false;

        for &i in &pending {
            let (offset, raw) = &raws[i];
            let resolved: Option<(GitObjectKind, Vec<u8>)> = match raw {
                Raw::Full { kind, body } => Some((*kind, body.clone())),
                Raw::OfsDelta { base_offset, delta } => by_offset
                    .get(base_offset)
                    .map(|(k, b)| apply_delta(b, delta).map(|body| (*k, body)))
                    .transpose()?,
                Raw::RefDelta { base_oid, delta } => {
                    let base = by_oid
                        .get(base_oid)
                        .cloned()
                        .map(Ok)
                        .or_else(|| resolve_external(*base_oid).transpose())
                        .transpose()?;
                    base.map(|(k, b)| apply_delta(&b, delta).map(|body| (k, body)))
                        .transpose()?
                }
            };

            match resolved {
                Some((kind, body)) => {
                    let obj = GitObject::new(kind, body.clone());
                    let oid = obj.oid();
                    by_offset.insert(*offset, (kind, body.clone()));
                    by_oid.insert(oid, (kind, body));
                    progressed = true;
                }
                None => next_pending.push(i),
            }
        }

        if !progressed {
            // A whole sweep resolved nothing → an unresolvable base (broken or
            // incomplete thin pack). Report the first missing base oid.
            let missing = pending.first().map(|&i| match &raws[i].1 {
                Raw::RefDelta { base_oid, .. } => base_oid.to_hex(),
                _ => "ofs-delta base".to_string(),
            });
            return Err(GitError::ObjectNotFound(
                missing.unwrap_or_else(|| "delta base".into()),
            ));
        }
        pending = next_pending;
    }

    // Materialise final objects in a stable (oid-sorted) order.
    let mut out: Vec<(GitObject, GitOid)> = by_oid
        .into_iter()
        .map(|(oid, (kind, body))| (GitObject::new(kind, body), oid))
        .collect();
    out.sort_by_key(|(_, oid)| *oid);
    Ok(out)
}

/// Parse a pack object header at `pos`: 3-bit type + variable size.
/// Returns `(pack_type, size, header_byte_len)`.
fn parse_obj_header(buf: &[u8], pos: usize) -> Result<(u8, u64, usize)> {
    let first = *buf.get(pos).ok_or(GitError::MalformedHeader)?;
    let obj_type = (first >> 4) & 0x07;
    let mut size = (first & 0x0f) as u64;
    let mut shift = 4;
    let mut i = pos + 1;
    let mut byte = first;
    while byte & 0x80 != 0 {
        byte = *buf.get(i).ok_or(GitError::MalformedHeader)?;
        size |= ((byte & 0x7f) as u64) << shift;
        shift += 7;
        i += 1;
    }
    Ok((obj_type, size, i - pos))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::object::TreeEntry;
    use crate::wire::pack_encode::encode_pack;

    #[test]
    fn full_objects_roundtrip_encode_then_ingest() {
        let blob = GitObject::blob(b"hello\n".to_vec());
        let tree = GitObject::tree(&[TreeEntry {
            mode: b"100644".to_vec(),
            name: b"f.txt".to_vec(),
            oid: blob.oid(),
        }]);
        let commit = GitObject::new(
            GitObjectKind::Commit,
            format!("tree {}\n\nmsg\n", tree.oid()).into_bytes(),
        );
        let objs = vec![blob, tree, commit];

        let pack = encode_pack(&objs).unwrap();
        let got = parse_pack(&pack, |_| Ok(None)).unwrap();

        // every returned oid is the real recomputed oid
        for (obj, oid) in &got {
            assert_eq!(obj.oid(), *oid);
        }
        let got_oids: std::collections::HashSet<_> = got.iter().map(|(_, o)| *o).collect();
        let want_oids: std::collections::HashSet<_> = objs.iter().map(|o| o.oid()).collect();
        assert_eq!(got_oids, want_oids);
    }

    #[test]
    fn rejects_corrupt_trailer() {
        let mut pack = encode_pack(&[GitObject::blob(b"x".to_vec())]).unwrap();
        let last = pack.len() - 1;
        pack[last] ^= 0xff; // flip a trailer byte
        assert!(parse_pack(&pack, |_| Ok(None)).is_err());
    }

    #[test]
    fn rejects_bad_magic() {
        let mut pack = encode_pack(&[GitObject::blob(b"x".to_vec())]).unwrap();
        pack[0] = b'X';
        assert!(parse_pack(&pack, |_| Ok(None)).is_err());
    }

    #[test]
    fn thin_pack_ref_delta_resolves_via_external_base() {
        // Build a REF_DELTA-bearing pack by hand: base "hello world" lives in the
        // store (external), the pack carries only a delta producing "hello!!".
        let base = GitObject::blob(b"hello world".to_vec());
        let base_oid = base.oid();

        // delta: src_size=11, dst_size=7, copy base[0..5], insert "!!"
        let delta = vec![0x0b, 0x07, 0x91, 0x00, 0x05, 0x02, b'!', b'!'];
        let expected = GitObject::blob(b"hello!!".to_vec());

        let pack = build_ref_delta_pack(base_oid, &delta);
        let resolver = |oid: GitOid| -> Result<Option<(GitObjectKind, Vec<u8>)>> {
            if oid == base_oid {
                Ok(Some((GitObjectKind::Blob, b"hello world".to_vec())))
            } else {
                Ok(None)
            }
        };
        let got = parse_pack(&pack, resolver).unwrap();
        assert_eq!(got.len(), 1);
        assert_eq!(got[0].0, expected);
    }

    #[test]
    fn missing_thin_base_errors_cleanly() {
        let base_oid = GitObject::blob(b"hello world".to_vec()).oid();
        let delta = vec![0x0b, 0x07, 0x91, 0x00, 0x05, 0x02, b'!', b'!'];
        let pack = build_ref_delta_pack(base_oid, &delta);
        // resolver knows nothing → unresolved base, clean Err (not a panic/loop)
        let err = parse_pack(&pack, |_| Ok(None)).unwrap_err();
        assert!(matches!(err, GitError::ObjectNotFound(_)));
    }

    // ── A flexible hand-roller for multi-object packs (full / ofs / ref). ─────
    enum E<'a> {
        Full(u8, &'a [u8]),       // (pack type, body)
        Ofs(usize, &'a [u8]),     // (index of an already-emitted base, delta)
        Ref(GitOid, &'a [u8]),    // (base oid, delta)
    }

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

    /// Inverse of `read_ofs_varint` (the `+1`-continuation big-endian form).
    fn write_ofs_varint(out: &mut Vec<u8>, mut n: u64) {
        let mut tmp = vec![(n & 0x7f) as u8];
        n >>= 7;
        while n > 0 {
            n -= 1;
            tmp.push((n & 0x7f) as u8);
            n >>= 7;
        }
        let len = tmp.len();
        for (i, b) in tmp.iter().rev().enumerate() {
            out.push(if i < len - 1 { b | 0x80 } else { *b });
        }
    }

    fn deflate(data: &[u8]) -> Vec<u8> {
        use flate2::{write::ZlibEncoder, Compression};
        use std::io::Write;
        let mut enc = ZlibEncoder::new(Vec::new(), Compression::default());
        enc.write_all(data).unwrap();
        enc.finish().unwrap()
    }

    fn build_pack(entries: &[E]) -> Vec<u8> {
        let mut out = Vec::new();
        out.extend_from_slice(b"PACK");
        out.extend_from_slice(&2u32.to_be_bytes());
        out.extend_from_slice(&(entries.len() as u32).to_be_bytes());
        let mut offsets = Vec::new();
        for e in entries {
            let off = out.len();
            match e {
                E::Full(t, body) => {
                    write_obj_header(&mut out, *t, body.len());
                    out.extend_from_slice(&deflate(body));
                }
                E::Ofs(base_idx, delta) => {
                    write_obj_header(&mut out, OBJ_OFS_DELTA, delta.len());
                    write_ofs_varint(&mut out, (off - offsets[*base_idx]) as u64);
                    out.extend_from_slice(&deflate(delta));
                }
                E::Ref(oid, delta) => {
                    write_obj_header(&mut out, OBJ_REF_DELTA, delta.len());
                    out.extend_from_slice(oid.raw());
                    out.extend_from_slice(&deflate(delta));
                }
            }
            offsets.push(off);
        }
        let mut h = Sha1::new();
        h.update(&out);
        out.extend_from_slice(&h.finalize());
        out
    }

    // delta over "hello world" (src 11) producing "hello!!" (dst 7):
    // copy base[0..5] then insert "!!".
    const HELLO_DELTA: &[u8] = &[0x0b, 0x07, 0x91, 0x00, 0x05, 0x02, b'!', b'!'];

    #[test]
    fn ofs_delta_resolves_against_in_pack_base() {
        // [ full "hello world" , ofs_delta → that base ]
        let pack = build_pack(&[
            E::Full(OBJ_BLOB, b"hello world"),
            E::Ofs(0, HELLO_DELTA),
        ]);
        let got = parse_pack(&pack, |_| Ok(None)).unwrap();
        let blobs: std::collections::HashSet<Vec<u8>> =
            got.into_iter().map(|(o, _)| o.body).collect();
        assert!(blobs.contains(&b"hello world".to_vec()));
        assert!(blobs.contains(&b"hello!!".to_vec()));
    }

    #[test]
    fn ref_delta_base_appearing_after_delta_resolves_via_fixpoint() {
        // Base is emitted *after* the delta that needs it — the fixpoint sweep
        // must still resolve it (packs do not guarantee base-before-delta order).
        let base_oid = GitObject::blob(b"hello world".to_vec()).oid();
        let pack = build_pack(&[
            E::Ref(base_oid, HELLO_DELTA),
            E::Full(OBJ_BLOB, b"hello world"),
        ]);
        let got = parse_pack(&pack, |_| Ok(None)).unwrap();
        let blobs: std::collections::HashSet<Vec<u8>> =
            got.into_iter().map(|(o, _)| o.body).collect();
        assert!(blobs.contains(&b"hello!!".to_vec()), "out-of-order base must resolve");
    }

    #[test]
    fn rejects_unsupported_version_and_trailing_junk() {
        // version 3 → rejected
        let mut p = build_pack(&[E::Full(OBJ_BLOB, b"x")]);
        p[7] = 3;
        // (trailer no longer matches either, but version is checked first)
        assert!(parse_pack(&p, |_| Ok(None)).is_err());

        // trailing junk between last object and trailer → pos != body_end
        let mut p = build_pack(&[E::Full(OBJ_BLOB, b"x")]);
        let trailer = p.split_off(p.len() - 20);
        p.extend_from_slice(b"JUNK");
        // recompute trailer over the (now longer) body so the checksum passes and
        // the *structural* `pos != body_end` check is what fails.
        let mut h = Sha1::new();
        h.update(&p);
        let _ = trailer; // old trailer discarded
        let new_trailer = h.finalize();
        p.extend_from_slice(&new_trailer);
        assert!(parse_pack(&p, |_| Ok(None)).is_err());
    }

    /// Hand-build a 1-object pack whose sole object is an OBJ_REF_DELTA.
    fn build_ref_delta_pack(base_oid: GitOid, delta: &[u8]) -> Vec<u8> {
        use flate2::{write::ZlibEncoder, Compression};
        use std::io::Write;

        let mut out = Vec::new();
        out.extend_from_slice(b"PACK");
        out.extend_from_slice(&2u32.to_be_bytes());
        out.extend_from_slice(&1u32.to_be_bytes());

        // object header: type=OBJ_REF_DELTA(7), size = delta.len()
        let size = delta.len();
        let mut byte = (OBJ_REF_DELTA << 4) | ((size & 0x0f) as u8);
        let mut rest = size >> 4;
        if rest > 0 {
            byte |= 0x80;
        }
        out.push(byte);
        while rest > 0 {
            let mut b = (rest & 0x7f) as u8;
            rest >>= 7;
            if rest > 0 {
                b |= 0x80;
            }
            out.push(b);
        }
        out.extend_from_slice(base_oid.raw());
        let mut enc = ZlibEncoder::new(Vec::new(), Compression::default());
        enc.write_all(delta).unwrap();
        out.extend_from_slice(&enc.finish().unwrap());

        let mut h = Sha1::new();
        h.update(&out);
        let trailer = h.finalize();
        out.extend_from_slice(&trailer);
        out
    }
}
