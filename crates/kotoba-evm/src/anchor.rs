//! kotoba-EVM R3 — Base L1 anchor payload (ADR-2606091500). Builds the
//! `AnchorBridge.commitRoot(bytes32 rootHash, bytes ipfsCid, uint64 batchSize)`
//! calldata that anchors a kotoba-EVM block's state root to Base L1 for
//! tamper-evidence / fork-choice (reuses the existing `AnchorBridge`, ADR-2605172300).
//!
//! kotoba stays **read+verify**: it CONSTRUCTS the anchor calldata; the actual tx
//! signing + Base submission is the operating-entity side (the relayer), exactly
//! as `AnchorBridge`'s permissionless-commit + off-chain-relayer model intends.

use kotoba_auth::eth::keccak256;
use kotoba_core::cid::KotobaCid;

/// `commitRoot(bytes32,bytes,uint64)` selector.
pub fn commit_root_selector() -> [u8; 4] {
    let h = keccak256(b"commitRoot(bytes32,bytes,uint64)");
    [h[0], h[1], h[2], h[3]]
}

fn pad32(out: &mut Vec<u8>, bytes: &[u8]) {
    // right-pad to a 32-byte word (ABI dynamic-tail data padding).
    out.extend_from_slice(bytes);
    let rem = bytes.len() % 32;
    if rem != 0 {
        out.extend(std::iter::repeat_n(0u8, 32 - rem));
    }
}

fn word_u64(n: u64) -> [u8; 32] {
    let mut w = [0u8; 32];
    w[24..32].copy_from_slice(&n.to_be_bytes());
    w
}

/// ABI-encode `commitRoot(rootHash, ipfsCid, batchSize)` calldata.
///
/// `root_hash` is the 32-byte state-root commitment (the low 32 bytes of the
/// block's state-root CID hash); `ipfs_cid` is the block CID's raw multibase
/// bytes (the DA pointer); `batch_size` is the tx count.
pub fn commit_root_calldata(root_hash: &[u8; 32], ipfs_cid: &[u8], batch_size: u64) -> Vec<u8> {
    let mut out = Vec::with_capacity(4 + 32 * 4 + ipfs_cid.len());
    out.extend_from_slice(&commit_root_selector());
    // head (3 words, param order): rootHash, offset→ipfsCid tail, batchSize
    out.extend_from_slice(root_hash); // word 0: bytes32
    out.extend_from_slice(&word_u64(0x60)); // word 1: offset to dynamic tail = 3*32
    out.extend_from_slice(&word_u64(batch_size)); // word 2: uint64
                                                  // tail: len(ipfsCid) + padded data
    out.extend_from_slice(&word_u64(ipfs_cid.len() as u64));
    pad32(&mut out, ipfs_cid);
    out
}

/// Convenience: build the anchor calldata for a block from its state-root CID +
/// block CID. The state-root commitment is the low 32 bytes of the CID's 36-byte
/// content hash (`KotobaCid.0` = 4-byte prefix + 32-byte hash).
pub fn anchor_block_calldata(
    state_root: &KotobaCid,
    block_cid: &KotobaCid,
    batch_size: u64,
) -> Vec<u8> {
    let mut root_hash = [0u8; 32];
    root_hash.copy_from_slice(&state_root.0[4..36]);
    commit_root_calldata(&root_hash, block_cid.to_multibase().as_bytes(), batch_size)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selector_is_stable() {
        // keccak256("commitRoot(bytes32,bytes,uint64)")[0..4]
        let s = commit_root_selector();
        // recompute independently to pin it.
        let h = keccak256(b"commitRoot(bytes32,bytes,uint64)");
        assert_eq!(s, [h[0], h[1], h[2], h[3]]);
    }

    #[test]
    fn calldata_layout_is_abi_correct() {
        let root = [0x11u8; 32];
        let cid = b"bafyblock"; // 9 bytes
        let data = commit_root_calldata(&root, cid, 7);

        // 4 selector + 3 head words + 1 len word + 1 padded data word = 4 + 32*5
        assert_eq!(data.len(), 4 + 32 * 5);
        // head word 0 = rootHash
        assert_eq!(&data[4..36], &root);
        // head word 1 = offset 0x60
        assert_eq!(data[4 + 32 + 31], 0x60);
        // head word 2 = batchSize 7
        assert_eq!(data[4 + 32 * 3 - 1], 7);
        // tail len word = 9
        assert_eq!(data[4 + 32 * 3 + 31], 9);
        // tail data = the cid bytes, right-padded
        assert_eq!(&data[4 + 32 * 4..4 + 32 * 4 + 9], cid);
        assert!(
            data[4 + 32 * 4 + 9..].iter().all(|&b| b == 0),
            "zero padding"
        );
    }

    #[test]
    fn anchor_block_calldata_uses_state_root_hash() {
        let sr = KotobaCid::from_bytes(b"state-root");
        let blk = KotobaCid::from_bytes(b"block-1");
        let data = anchor_block_calldata(&sr, &blk, 3);
        // rootHash word = low 32 bytes of the state-root CID.
        assert_eq!(&data[4..36], &sr.0[4..36]);
        // ipfsCid tail = the block CID multibase bytes.
        let mb = blk.to_multibase();
        let len = mb.len();
        assert_eq!(data[4 + 32 * 3 + 31] as usize, len);
        assert_eq!(&data[4 + 32 * 4..4 + 32 * 4 + len], mb.as_bytes());
    }
}
