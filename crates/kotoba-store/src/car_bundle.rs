use anyhow::{bail, Result};
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
/// CAR (Content Addressable aRchive) bundle — Hummock-style SST analogue.
///
/// Packs all ProllyTree blocks from a single commit into one flat file so they can
/// be uploaded to S3/B2 with a **single PUT** instead of ~15K individual PUTs.
///
/// # Format (kotoba-car v1)
///
/// ```text
/// ┌─────────────────────────────────────── HEADER (72 bytes) ──┐
/// │ magic[4]  "KCAR"                                           │
/// │ version[4] = 1u32 LE                                       │
/// │ block_count[8]  u64 LE                                     │
/// │ index_offset[8] u64 LE  (byte offset of index section)     │
/// │ root_cid[36]    commit root CID (for IPFS pinning)         │
/// │ _reserved[12]   zeroed                                     │
/// └────────────────────────────────────────────────────────────┘
/// ┌─────────────────────────── BLOCKS section ─────────────────┐
/// │ block_0_data ... block_N_data  (variable, concatenated)    │
/// └────────────────────────────────────────────────────────────┘
/// ┌─────────────────────────── INDEX section ──────────────────┐
/// │ For each block i: cid[36] + data_offset[8] + data_len[4]  │
/// │ Entry size = 48 bytes, total = block_count × 48            │
/// └────────────────────────────────────────────────────────────┘
/// ```
///
/// Random-access read: fetch index → range GET `data_offset..data_offset+data_len`.
/// Sequential scan: read blocks section start→index_offset.
///
/// The in-memory [`CarBlockIndex`] maps `KotobaCid → (car_key, data_offset, data_len)`.
use std::collections::HashMap;

/// `(cid, absolute_byte_offset, data_length)` triple returned by `parse_index`.
type IndexEntry = (KotobaCid, u64, u32);

const MAGIC: &[u8; 4] = b"KCAR";
const VERSION: u32 = 1;
pub(crate) const HEADER_LEN: usize = 72;
const INDEX_ENTRY: usize = 48; // 36 (cid) + 8 (offset) + 4 (len)
pub(crate) const MAX_CAR_BYTES: usize = 2 * 1024 * 1024 * 1024;
const MAX_CAR_BLOCKS: usize = 1_000_000;
pub(crate) const MAX_CAR_BLOCK_BYTES: u32 = 64 * 1024 * 1024;

// ─── CarBundleWriter ─────────────────────────────────────────────────────────

/// Accumulates blocks in memory and serializes to a single CAR byte buffer.
///
/// Usage:
/// ```ignore
/// let mut w = CarBundleWriter::new(commit_root_cid);
/// for (cid, data) in blocks { w.append(&cid, &data); }
/// let (car_bytes, index) = w.finish();
/// ```
pub struct CarBundleWriter {
    root_cid: KotobaCid,
    blocks_buf: Vec<u8>,                 // raw block bytes, concatenated
    offsets: Vec<(KotobaCid, u64, u32)>, // (cid, data_offset, data_len)
}

impl CarBundleWriter {
    pub fn new(root_cid: KotobaCid) -> Self {
        Self {
            root_cid,
            blocks_buf: Vec::new(),
            offsets: Vec::new(),
        }
    }

    /// Append one block. Returns the byte offset within the blocks section.
    pub fn append(&mut self, cid: &KotobaCid, data: &[u8]) -> u64 {
        let data_offset = self.blocks_buf.len() as u64;
        self.blocks_buf.extend_from_slice(data);
        self.offsets
            .push((cid.clone(), data_offset, data.len() as u32));
        data_offset
    }

    pub fn block_count(&self) -> usize {
        self.offsets.len()
    }
    pub fn blocks_bytes(&self) -> usize {
        self.blocks_buf.len()
    }

    /// Serialize to a flat CAR byte buffer and return the per-block index.
    /// The returned index offsets are relative to the start of the CAR file
    /// (i.e. `HEADER_LEN + data_offset`).
    pub fn finish(self) -> (Vec<u8>, Vec<(KotobaCid, u64, u32)>) {
        let block_count = self.offsets.len() as u64;
        let blocks_size = self.blocks_buf.len();
        let index_offset = HEADER_LEN + blocks_size;
        let total_size = index_offset + self.offsets.len() * INDEX_ENTRY;

        let mut buf = Vec::with_capacity(total_size);

        // ── Header ──────────────────────────────────────────────────────────
        buf.extend_from_slice(MAGIC); // [0..4]
        buf.extend_from_slice(&VERSION.to_le_bytes()); // [4..8]
        buf.extend_from_slice(&block_count.to_le_bytes()); // [8..16]
        buf.extend_from_slice(&(index_offset as u64).to_le_bytes()); // [16..24]
        buf.extend_from_slice(&self.root_cid.0); // [24..60]
        buf.extend_from_slice(&[0u8; 12]); // [60..72] reserved

        debug_assert_eq!(buf.len(), HEADER_LEN);

        // ── Blocks ──────────────────────────────────────────────────────────
        buf.extend_from_slice(&self.blocks_buf);

        // ── Index ───────────────────────────────────────────────────────────
        // Offsets in index are file-absolute (header + block section + data_offset).
        let header_and_blocks = HEADER_LEN as u64;
        let mut abs_offsets = Vec::with_capacity(self.offsets.len());
        for (cid, rel_off, len) in &self.offsets {
            let abs_off = header_and_blocks + rel_off;
            buf.extend_from_slice(&cid.0); // 36 bytes
            buf.extend_from_slice(&abs_off.to_le_bytes()); // 8 bytes
            buf.extend_from_slice(&len.to_le_bytes()); // 4 bytes
            abs_offsets.push((cid.clone(), abs_off, *len));
        }

        debug_assert_eq!(buf.len(), total_size);
        (buf, abs_offsets)
    }
}

// ─── CAR parsing ─────────────────────────────────────────────────────────────

/// Parse the index section from a complete CAR byte buffer.
/// Returns `(root_cid, Vec<(cid, abs_offset, data_len)>)`.
pub fn parse_index(car: &[u8]) -> Result<(KotobaCid, Vec<IndexEntry>)> {
    if car.len() < HEADER_LEN {
        bail!("car too short: {} bytes", car.len());
    }
    if car.len() > MAX_CAR_BYTES {
        bail!("car too large: {} bytes, limit {MAX_CAR_BYTES}", car.len());
    }
    if &car[0..4] != MAGIC {
        bail!("invalid car magic");
    }
    let version = u32::from_le_bytes(car[4..8].try_into().unwrap());
    if version != 1 {
        bail!("unsupported car version {version}");
    }
    let block_count_raw = u64::from_le_bytes(car[8..16].try_into().unwrap());
    let block_count = usize::try_from(block_count_raw)
        .map_err(|_| anyhow::anyhow!("car block_count does not fit usize: {block_count_raw}"))?;
    if block_count > MAX_CAR_BLOCKS {
        bail!("car block_count exceeds limit: {block_count} > {MAX_CAR_BLOCKS}");
    }
    let index_offset_raw = u64::from_le_bytes(car[16..24].try_into().unwrap());
    let index_offset = usize::try_from(index_offset_raw)
        .map_err(|_| anyhow::anyhow!("car index_offset does not fit usize: {index_offset_raw}"))?;
    if index_offset < HEADER_LEN {
        bail!("invalid car index_offset {index_offset}: before header end {HEADER_LEN}");
    }
    if index_offset > car.len() {
        bail!(
            "invalid car index_offset {index_offset}: beyond car length {}",
            car.len()
        );
    }

    let mut root = [0u8; 36];
    root.copy_from_slice(&car[24..60]);
    let root_cid = KotobaCid(root);
    if car[60..72].iter().any(|&b| b != 0) {
        bail!("invalid car reserved header bytes");
    }

    // The index section size (index_offset + block_count*INDEX_ENTRY) is derived
    // from untrusted header bytes; compute it with checked arithmetic so a hostile
    // block_count/index_offset cannot wrap the bound and then panic (or OOM the
    // Vec::with_capacity below) on a CAR fetched from an untrusted peer.
    let index_section_end = match block_count
        .checked_mul(INDEX_ENTRY)
        .and_then(|n| index_offset.checked_add(n))
    {
        Some(end) => end,
        None => bail!("car index section size overflows usize (block_count={block_count})"),
    };
    if car.len() < index_section_end {
        bail!("car truncated: index section incomplete");
    }

    let mut entries = Vec::with_capacity(block_count);
    let mut pos = index_offset;
    for _ in 0..block_count {
        let mut cid_bytes = [0u8; 36];
        cid_bytes.copy_from_slice(&car[pos..pos + 36]);
        let abs_off = u64::from_le_bytes(car[pos + 36..pos + 44].try_into().unwrap());
        let data_len = u32::from_le_bytes(car[pos + 44..pos + 48].try_into().unwrap());
        if data_len > MAX_CAR_BLOCK_BYTES {
            bail!("car block length exceeds limit: {data_len} > {MAX_CAR_BLOCK_BYTES}");
        }
        let start = usize::try_from(abs_off)
            .map_err(|_| anyhow::anyhow!("car block offset does not fit usize: {abs_off}"))?;
        let end = start
            .checked_add(data_len as usize)
            .ok_or_else(|| anyhow::anyhow!("car block offset+len overflows usize"))?;
        if start < HEADER_LEN || end > index_offset {
            bail!(
                "car block range outside blocks section: [{start}..{end}] not within [{HEADER_LEN}..{index_offset}]"
            );
        }
        entries.push((KotobaCid(cid_bytes), abs_off, data_len));
        pos += INDEX_ENTRY;
    }

    Ok((root_cid, entries))
}

/// Extract a single block from a CAR byte buffer using a pre-parsed index entry.
pub fn extract_block(car: &[u8], abs_offset: u64, data_len: u32) -> Result<Bytes> {
    let start = usize::try_from(abs_offset)
        .map_err(|_| anyhow::anyhow!("block offset does not fit usize: {abs_offset}"))?;
    // abs_offset/data_len come from the (untrusted) index; checked_add so a wrapped
    // `end` can't slip past the bound check and panic at `car[start..end]`.
    let end = match start.checked_add(data_len as usize) {
        Some(e) => e,
        None => bail!("block offset+len overflows usize: start={start}, len={data_len}"),
    };
    if end > car.len() {
        bail!(
            "block out of range: car {} bytes, want [{start}..{end}]",
            car.len()
        );
    }
    Ok(Bytes::copy_from_slice(&car[start..end]))
}

/// Extract a block and verify that its bytes hash back to the expected CID.
pub fn extract_verified_block(
    car: &[u8],
    expected_cid: &KotobaCid,
    abs_offset: u64,
    data_len: u32,
) -> Result<Bytes> {
    let block = extract_block(car, abs_offset, data_len)?;
    let actual_cid = KotobaCid::from_bytes(&block);
    if actual_cid != *expected_cid {
        bail!(
            "car block CID mismatch: expected {}, got {}",
            expected_cid.to_multibase(),
            actual_cid.to_multibase()
        );
    }
    Ok(block)
}

/// Parse the index and verify every indexed block against its CID.
pub fn parse_verified_index(car: &[u8]) -> Result<(KotobaCid, Vec<IndexEntry>)> {
    let (root, entries) = parse_index(car)?;
    for (cid, off, len) in &entries {
        extract_verified_block(car, cid, *off, *len)?;
    }
    Ok((root, entries))
}

// ─── CarBlockIndex ────────────────────────────────────────────────────────────

/// In-memory index: maps CID → (car_key, abs_offset, data_len).
/// `car_key` is the kotobase/IPFS CAR object key (= commit CID multibase).
#[derive(Default)]
pub struct CarBlockIndex {
    entries: HashMap<KotobaCid, (String, u64, u32)>,
}

impl CarBlockIndex {
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert all entries from a freshly written CAR file.
    pub fn insert_car(&mut self, car_key: &str, index: &[(KotobaCid, u64, u32)]) {
        for (cid, off, len) in index {
            self.entries
                .insert(cid.clone(), (car_key.to_string(), *off, *len));
        }
    }

    /// Look up a CID. Returns `(car_key, abs_offset, data_len)` if present.
    pub fn get(&self, cid: &KotobaCid) -> Option<(&str, u64, u32)> {
        self.entries.get(cid).map(|(k, o, l)| (k.as_str(), *o, *l))
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn fake_cid(n: u64) -> KotobaCid {
        KotobaCid::from_bytes(&n.to_le_bytes())
    }
    fn fake_data(n: u64, size: usize) -> Vec<u8> {
        (0..size).map(|i| ((n + i as u64) & 0xff) as u8).collect()
    }

    #[test]
    fn roundtrip_small() {
        let root = fake_cid(0);
        let mut w = CarBundleWriter::new(root.clone());
        for i in 1u64..=5 {
            w.append(&fake_cid(i), &fake_data(i, 128));
        }
        let (car, idx) = w.finish();

        let (parsed_root, parsed_idx) = parse_index(&car).unwrap();
        assert_eq!(parsed_root, root);
        assert_eq!(parsed_idx.len(), 5);

        for (i, (cid, off, len)) in parsed_idx.iter().enumerate() {
            assert_eq!(*cid, fake_cid(i as u64 + 1));
            assert_eq!(*len, 128);
            let block = extract_block(&car, *off, *len).unwrap();
            assert_eq!(block.as_ref(), fake_data(i as u64 + 1, 128).as_slice());
            // Also verify against pre-computed index
            assert_eq!(idx[i].1, *off);
        }
    }

    #[test]
    fn roundtrip_variable_sizes_including_empty_block() {
        // roundtrip_small uses uniform 128-byte blocks, which can mask a cumulative-
        // offset bug (a fixed-stride error would still extract correctly). Variable
        // sizes — including a zero-length block — force each block's offset to be the
        // running sum of all preceding *different* lengths, and exercise the len=0
        // boundary (an empty block shares its offset with its neighbour's edge).
        let root = fake_cid(0);
        let sizes = [1usize, 1000, 7, 0, 333, 64, 0, 2];
        let mut w = CarBundleWriter::new(root.clone());
        for (i, &sz) in sizes.iter().enumerate() {
            w.append(&fake_cid(i as u64 + 1), &fake_data(i as u64 + 1, sz));
        }
        let (car, idx) = w.finish();
        let (parsed_root, parsed_idx) = parse_index(&car).unwrap();
        assert_eq!(parsed_root, root);
        assert_eq!(parsed_idx.len(), sizes.len());

        // Offsets must be strictly the cumulative sum (a 0-length block does not
        // advance the offset, so it coincides with the following block's offset).
        let mut expected_off = HEADER_LEN as u64;
        for (i, (cid, off, len)) in parsed_idx.iter().enumerate() {
            assert_eq!(*cid, fake_cid(i as u64 + 1));
            assert_eq!(*len as usize, sizes[i], "length mismatch at block {i}");
            assert_eq!(*off, expected_off, "offset arithmetic wrong at block {i}");
            let block = extract_block(&car, *off, *len).unwrap();
            assert_eq!(
                block.as_ref(),
                fake_data(i as u64 + 1, sizes[i]).as_slice(),
                "byte mismatch at block {i}"
            );
            assert_eq!(idx[i].1, *off, "finish() index disagrees with parsed index");
            expected_off += sizes[i] as u64;
        }
    }

    #[test]
    fn block_index_insert_and_lookup() {
        let root = fake_cid(0);
        let mut w = CarBundleWriter::new(root);
        for i in 0u64..10 {
            w.append(&fake_cid(i), &fake_data(i, 64));
        }
        let (_, idx) = w.finish();

        let mut index = CarBlockIndex::new();
        index.insert_car("commit-abc123", &idx);
        assert_eq!(index.len(), 10);

        let (key, off, len) = index.get(&fake_cid(5)).unwrap();
        assert_eq!(key, "commit-abc123");
        assert!(off >= HEADER_LEN as u64);
        assert_eq!(len, 64);
    }

    #[test]
    fn header_is_exactly_72_bytes() {
        let mut w = CarBundleWriter::new(fake_cid(0));
        w.append(&fake_cid(1), b"x");
        let (car, _) = w.finish();
        // First block should be at HEADER_LEN offset
        assert_eq!(&car[HEADER_LEN..HEADER_LEN + 1], b"x");
    }

    // ── empty writer ───────────────────────────────────────────────────────────

    #[test]
    fn empty_writer_block_count_and_bytes() {
        let w = CarBundleWriter::new(fake_cid(0));
        assert_eq!(w.block_count(), 0);
        assert_eq!(w.blocks_bytes(), 0);
    }

    #[test]
    fn empty_writer_produces_valid_header_only_car() {
        let root = fake_cid(42);
        let w = CarBundleWriter::new(root.clone());
        let (car, idx) = w.finish();
        assert_eq!(car.len(), HEADER_LEN);
        assert!(idx.is_empty());
        let (parsed_root, parsed_idx) = parse_index(&car).unwrap();
        assert_eq!(parsed_root, root);
        assert_eq!(parsed_idx.len(), 0);
    }

    // ── block_count and blocks_bytes ──────────────────────────────────────────

    #[test]
    fn block_count_and_blocks_bytes_track_appends() {
        let mut w = CarBundleWriter::new(fake_cid(0));
        w.append(&fake_cid(1), &[0u8; 100]);
        w.append(&fake_cid(2), &[0u8; 200]);
        assert_eq!(w.block_count(), 2);
        assert_eq!(w.blocks_bytes(), 300);
    }

    // ── parse_index error paths ───────────────────────────────────────────────

    #[test]
    fn parse_index_rejects_too_short() {
        let result = parse_index(&[0u8; 10]);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("too short"));
    }

    #[test]
    fn parse_index_rejects_wrong_magic() {
        let mut car = vec![0u8; HEADER_LEN];
        car[0..4].copy_from_slice(b"XXXX");
        let result = parse_index(&car);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("magic"));
    }

    #[test]
    fn parse_index_rejects_wrong_version() {
        let mut car = vec![0u8; HEADER_LEN];
        car[0..4].copy_from_slice(b"KCAR");
        car[4..8].copy_from_slice(&2u32.to_le_bytes()); // version 2
        let result = parse_index(&car);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("version"));
    }

    #[test]
    fn parse_index_rejects_index_offset_before_header_end() {
        let mut car = vec![0u8; HEADER_LEN];
        car[0..4].copy_from_slice(MAGIC);
        car[4..8].copy_from_slice(&VERSION.to_le_bytes());
        car[8..16].copy_from_slice(&0u64.to_le_bytes());
        car[16..24].copy_from_slice(&(HEADER_LEN as u64 - 1).to_le_bytes());

        let err = parse_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("index_offset"),
            "index offsets inside the CAR header must be rejected: {err}"
        );
    }

    #[test]
    fn parse_index_rejects_overflowing_index_offset_without_panicking() {
        let mut car = vec![0u8; HEADER_LEN];
        car[0..4].copy_from_slice(MAGIC);
        car[4..8].copy_from_slice(&VERSION.to_le_bytes());
        car[8..16].copy_from_slice(&1u64.to_le_bytes());
        car[16..24].copy_from_slice(&u64::MAX.to_le_bytes());

        let result = parse_index(&car);

        assert!(
            result.is_err(),
            "overflowing index_offset must be rejected, not panic or wrap"
        );
    }

    #[test]
    fn parse_index_rejects_index_offset_beyond_car_length() {
        let mut car = vec![0u8; HEADER_LEN];
        car[0..4].copy_from_slice(MAGIC);
        car[4..8].copy_from_slice(&VERSION.to_le_bytes());
        car[8..16].copy_from_slice(&0u64.to_le_bytes());
        car[16..24].copy_from_slice(&((HEADER_LEN + 1) as u64).to_le_bytes());

        let err = parse_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("beyond car length"),
            "index offsets past EOF must be rejected early: {err}"
        );
    }

    #[test]
    fn parse_index_rejects_nonzero_reserved_header_bytes() {
        let mut car = vec![0u8; HEADER_LEN];
        car[0..4].copy_from_slice(MAGIC);
        car[4..8].copy_from_slice(&VERSION.to_le_bytes());
        car[8..16].copy_from_slice(&0u64.to_le_bytes());
        car[16..24].copy_from_slice(&(HEADER_LEN as u64).to_le_bytes());
        car[60] = 1;

        let err = parse_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("reserved"),
            "reserved header bytes must stay canonical zeroes: {err}"
        );
    }

    #[test]
    fn parse_index_rejects_block_count_above_limit_without_allocating_index() {
        let mut car = vec![0u8; HEADER_LEN];
        car[0..4].copy_from_slice(MAGIC);
        car[4..8].copy_from_slice(&VERSION.to_le_bytes());
        car[8..16].copy_from_slice(&((MAX_CAR_BLOCKS as u64) + 1).to_le_bytes());
        car[16..24].copy_from_slice(&(HEADER_LEN as u64).to_le_bytes());

        let err = parse_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("block_count exceeds limit"),
            "oversized block_count must be capped before index allocation: {err}"
        );
    }

    #[test]
    fn parse_index_rejects_truncated_index_section() {
        // Build a valid 1-block CAR, then truncate it
        let mut w = CarBundleWriter::new(fake_cid(0));
        w.append(&fake_cid(1), b"data");
        let (car, _) = w.finish();
        // Remove last byte (truncates the index section)
        let truncated = &car[..car.len() - 1];
        let result = parse_index(truncated);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("truncated"));
    }

    #[test]
    fn parse_index_rejects_block_length_above_limit() {
        let data = b"data";
        let mut w = CarBundleWriter::new(fake_cid(0));
        w.append(&fake_cid(1), data);
        let (mut car, _) = w.finish();
        let index_offset = HEADER_LEN + data.len();
        let data_len_pos = index_offset + 44;
        car[data_len_pos..data_len_pos + 4]
            .copy_from_slice(&(MAX_CAR_BLOCK_BYTES + 1).to_le_bytes());

        let err = parse_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("block length exceeds limit"),
            "oversized block lengths must be rejected before extraction: {err}"
        );
    }

    #[test]
    fn parse_index_rejects_block_range_inside_header() {
        let data = b"data";
        let mut w = CarBundleWriter::new(fake_cid(0));
        w.append(&fake_cid(1), data);
        let (mut car, _) = w.finish();
        let index_offset = HEADER_LEN + data.len();
        let data_offset_pos = index_offset + 36;
        let invalid_offset = (HEADER_LEN - 1) as u64;
        car[data_offset_pos..data_offset_pos + 8].copy_from_slice(&invalid_offset.to_le_bytes());

        let err = parse_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("outside blocks section"),
            "block ranges cannot point into the header: {err}"
        );
    }

    #[test]
    fn parse_index_rejects_block_range_inside_index_section() {
        let data = b"data";
        let mut w = CarBundleWriter::new(fake_cid(0));
        w.append(&fake_cid(1), data);
        let (mut car, _) = w.finish();
        let index_offset = HEADER_LEN + data.len();
        let data_offset_pos = index_offset + 36;
        let invalid_offset = index_offset as u64;
        car[data_offset_pos..data_offset_pos + 8].copy_from_slice(&invalid_offset.to_le_bytes());

        let err = parse_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("outside blocks section"),
            "block ranges cannot point into the index section: {err}"
        );
    }

    // ── extract_block out-of-range ────────────────────────────────────────────

    #[test]
    fn extract_block_rejects_out_of_range() {
        let car = vec![0u8; 100];
        let result = extract_block(&car, 90, 20); // 90+20=110 > 100
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("out of range"));
    }

    #[test]
    fn extract_block_rejects_overflowing_offset_len_without_panicking() {
        // abs_offset/data_len come from an untrusted index. start + data_len must use
        // checked arithmetic. With start = usize::MAX and a SMALL data_len, the sum
        // wraps to a small `end` (≤ buffer): in release it slips past `end > len` and
        // panics at `car[huge..small]`; in debug it overflows the add. Either way it
        // must now be Err, never a panic.
        let car = vec![0u8; 100];
        let result = extract_block(&car, u64::MAX, 50);
        assert!(
            result.is_err(),
            "overflowing offset/len must be rejected, not panic"
        );
    }

    #[test]
    fn extract_verified_block_accepts_matching_cid() {
        let root = fake_cid(0);
        let data = b"verified car block";
        let cid = KotobaCid::from_bytes(data);
        let mut w = CarBundleWriter::new(root);
        w.append(&cid, data);
        let (car, index) = w.finish();
        let (indexed_cid, off, len) = &index[0];

        let block = extract_verified_block(&car, indexed_cid, *off, *len).unwrap();

        assert_eq!(indexed_cid, &cid);
        assert_eq!(block.as_ref(), data);
    }

    #[test]
    fn extract_verified_block_rejects_cid_mismatch() {
        let root = fake_cid(0);
        let data = b"verified car block";
        let cid = KotobaCid::from_bytes(data);
        let wrong_cid = KotobaCid::from_bytes(b"different block bytes");
        let mut w = CarBundleWriter::new(root);
        w.append(&cid, data);
        let (car, index) = w.finish();
        let (_indexed_cid, off, len) = &index[0];

        let err = extract_verified_block(&car, &wrong_cid, *off, *len).unwrap_err();

        assert!(
            err.to_string().contains("CID mismatch"),
            "verified extraction should reject an index/data mismatch: {err}"
        );
    }

    #[test]
    fn parse_verified_index_accepts_matching_blocks() {
        let root = fake_cid(0);
        let mut w = CarBundleWriter::new(root.clone());
        for i in 1u64..=3 {
            let data = fake_data(i, 32);
            w.append(&KotobaCid::from_bytes(&data), &data);
        }
        let (car, _index) = w.finish();

        let (parsed_root, entries) = parse_verified_index(&car).unwrap();

        assert_eq!(parsed_root, root);
        assert_eq!(entries.len(), 3);
    }

    #[test]
    fn parse_verified_index_rejects_index_data_mismatch() {
        let root = fake_cid(0);
        let data = b"verified car block";
        let cid = KotobaCid::from_bytes(data);
        let mut w = CarBundleWriter::new(root);
        w.append(&cid, data);
        let (mut car, _index) = w.finish();
        car[HEADER_LEN] ^= 0xff;

        let err = parse_verified_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("CID mismatch"),
            "verified index parsing should reject CARs whose block bytes no longer match the index: {err}"
        );
    }

    #[test]
    fn parse_verified_index_rejects_block_range_outside_car() {
        let root = fake_cid(0);
        let data = b"verified car block";
        let cid = KotobaCid::from_bytes(data);
        let mut w = CarBundleWriter::new(root);
        w.append(&cid, data);
        let (mut car, _index) = w.finish();
        let index_offset = HEADER_LEN + data.len();
        let data_offset_pos = index_offset + 36;
        let invalid_offset = car.len() as u64;
        car[data_offset_pos..data_offset_pos + 8].copy_from_slice(&invalid_offset.to_le_bytes());

        let err = parse_verified_index(&car).unwrap_err();

        assert!(
            err.to_string().contains("outside blocks section"),
            "verified index parsing should reject entries that point outside the CAR: {err}"
        );
    }

    #[test]
    fn parse_index_rejects_overflowing_block_count_without_panicking() {
        // A CAR from an untrusted peer can claim an enormous block_count. The index-
        // section size computation must not overflow (and must not OOM via
        // Vec::with_capacity). Hand-craft a valid header with block_count = u64::MAX.
        let mut car = vec![0u8; HEADER_LEN];
        car[0..4].copy_from_slice(MAGIC);
        car[4..8].copy_from_slice(&1u32.to_le_bytes()); // version
        car[8..16].copy_from_slice(&u64::MAX.to_le_bytes()); // block_count
        car[16..24].copy_from_slice(&(HEADER_LEN as u64).to_le_bytes()); // index_offset
                                                                         // root cid bytes [24..60] left zero; reserved [60..72] zero.
        let result = parse_index(&car);
        assert!(
            result.is_err(),
            "overflowing block_count must be rejected, not panic/OOM"
        );
    }

    // ── CarBlockIndex ─────────────────────────────────────────────────────────

    #[test]
    fn car_block_index_is_empty_initially() {
        let idx = CarBlockIndex::new();
        assert!(idx.is_empty());
        assert_eq!(idx.len(), 0);
    }

    #[test]
    fn car_block_index_get_miss_returns_none() {
        let idx = CarBlockIndex::new();
        assert!(idx.get(&fake_cid(99)).is_none());
    }

    #[test]
    fn car_block_index_insert_multiple_cars() {
        let mut index = CarBlockIndex::new();

        // First CAR: 3 blocks
        let mut w1 = CarBundleWriter::new(fake_cid(0));
        for i in 0u64..3 {
            w1.append(&fake_cid(i), &fake_data(i, 32));
        }
        let (_, idx1) = w1.finish();
        index.insert_car("car-A", &idx1);

        // Second CAR: 2 blocks (different CIDs)
        let mut w2 = CarBundleWriter::new(fake_cid(10));
        for i in 10u64..12 {
            w2.append(&fake_cid(i), &fake_data(i, 16));
        }
        let (_, idx2) = w2.finish();
        index.insert_car("car-B", &idx2);

        assert_eq!(index.len(), 5);
        assert_eq!(index.get(&fake_cid(0)).unwrap().0, "car-A");
        assert_eq!(index.get(&fake_cid(10)).unwrap().0, "car-B");
        assert_eq!(index.get(&fake_cid(11)).unwrap().2, 16);
    }
}
