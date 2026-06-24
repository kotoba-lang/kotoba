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

// ── Finality verification (read+verify side, GROWTH p8 / MISHMAR §1) ──────────
//
// The write side above CONSTRUCTS the anchor calldata. This side VERIFIES it: a
// graph head is *final* once its CommitDag root is observed anchored on Base.
// kotoba never submits the tx; it observes `AnchorBridge.committerOf[rootHash]`
// (read-only) and checks the three-way match (local head ↔ anchored root ↔ a
// non-zero committer). Pure — chain observation is the caller's; this is the verdict.

/// The 32-byte root commitment derived from a graph head CID — the value
/// `AnchorBridge.commitRoot` anchors and `committerOf` is keyed by (the low 32
/// bytes of the CIDv1 36-byte content hash).
pub fn root_hash_of(head: &KotobaCid) -> [u8; 32] {
    let mut h = [0u8; 32];
    h.copy_from_slice(&head.0[4..36]);
    h
}

/// True for the zero / unset Ethereum address (`committerOf` returns this when a
/// root hash has never been anchored).
pub fn is_zero_address(addr: &[u8; 20]) -> bool {
    addr.iter().all(|&b| b == 0)
}

/// Finality verdict for a graph head (read+verify; GROWTH p8 / MISHMAR §1).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FinalityStatus {
    /// The local head's root commitment that was checked on-chain.
    pub root_hash: [u8; 32],
    /// A non-zero committer was observed for this exact root hash.
    pub anchored: bool,
    /// `true` iff the head's root is anchored by a non-zero committer — the
    /// objective finality point. (Querying `committerOf` by the *local* root hash
    /// makes the three-way match hold by construction: a hit means the chain
    /// recorded exactly this root.)
    pub is_final: bool,
}

/// Verify a graph head's finality against an observed `AnchorBridge.committerOf`
/// lookup keyed by the head's own root hash. `committer_of_local_root` is the
/// observed committer address (`None` if the call reverted / no record). Final
/// iff that committer exists and is non-zero.
pub fn verify_finality(
    local_head: &KotobaCid,
    committer_of_local_root: Option<[u8; 20]>,
) -> FinalityStatus {
    let root_hash = root_hash_of(local_head);
    let anchored = committer_of_local_root
        .map(|a| !is_zero_address(&a))
        .unwrap_or(false);
    FinalityStatus {
        root_hash,
        anchored,
        is_final: anchored,
    }
}

/// Aggregate finality across a node's tracked graph heads — the checkpoint
/// observability surface (GROWTH p8). `finalized + pending == tracked`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct FinalitySummary {
    /// Heads observed.
    pub tracked: usize,
    /// Heads whose root is anchored by a non-zero committer (final).
    pub finalized: usize,
    /// Heads not yet anchored.
    pub pending: usize,
}

/// Summarize a batch of [`FinalityStatus`] (e.g. one per graph head this node
/// holds) into counts for `node.status`.
pub fn finality_summary(statuses: &[FinalityStatus]) -> FinalitySummary {
    let finalized = statuses.iter().filter(|s| s.is_final).count();
    FinalitySummary {
        tracked: statuses.len(),
        finalized,
        pending: statuses.len() - finalized,
    }
}

/// `committerOf(bytes32)` view selector.
pub fn committer_of_selector() -> [u8; 4] {
    let h = keccak256(b"committerOf(bytes32)");
    [h[0], h[1], h[2], h[3]]
}

/// ABI-encode the `AnchorBridge.committerOf(rootHash)` view calldata — the
/// read-only `eth_call` that returns who anchored `root_hash` (zero address if
/// none). selector ++ rootHash(32).
pub fn committer_of_calldata(root_hash: &[u8; 32]) -> Vec<u8> {
    let mut out = Vec::with_capacity(4 + 32);
    out.extend_from_slice(&committer_of_selector());
    out.extend_from_slice(root_hash);
    out
}

/// Decode an `address`-returning `eth_call` result (a 32-byte ABI word, address
/// in the low 20 bytes). `None` if the result is too short (reverted / empty).
pub fn decode_address_result(result: &[u8]) -> Option<[u8; 20]> {
    if result.len() < 32 {
        return None;
    }
    let mut addr = [0u8; 20];
    addr.copy_from_slice(&result[12..32]);
    Some(addr)
}

/// Turn a raw `committerOf` `eth_call` result into a [`FinalityStatus`] for
/// `local_head`: decode the address word, then [`verify_finality`]. An empty /
/// short / zero-address result is not final.
pub fn finality_from_call_result(local_head: &KotobaCid, result: &[u8]) -> FinalityStatus {
    verify_finality(local_head, decode_address_result(result))
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

    // ── finality verification ────────────────────────────────────────────

    #[test]
    fn root_hash_is_the_low_32_bytes_and_matches_anchor_calldata() {
        let head = KotobaCid::from_bytes(b"graph-head");
        assert_eq!(root_hash_of(&head), {
            let mut h = [0u8; 32];
            h.copy_from_slice(&head.0[4..36]);
            h
        });
        // the same root hash the write side anchors.
        let data = anchor_block_calldata(&head, &head, 1);
        assert_eq!(&data[4..36], &root_hash_of(&head));
    }

    #[test]
    fn unanchored_head_is_not_final() {
        let head = KotobaCid::from_bytes(b"unanchored");
        // no committerOf record at all.
        let st = verify_finality(&head, None);
        assert!(!st.anchored);
        assert!(!st.is_final);
        assert_eq!(st.root_hash, root_hash_of(&head));
        // a zero-address committer (root never anchored) is also not final.
        let zero = verify_finality(&head, Some([0u8; 20]));
        assert!(!zero.is_final);
    }

    #[test]
    fn head_anchored_by_nonzero_committer_is_final() {
        let head = KotobaCid::from_bytes(b"anchored");
        let mut committer = [0u8; 20];
        committer[19] = 0xAB; // a real relayer address
        let st = verify_finality(&head, Some(committer));
        assert!(st.anchored);
        assert!(
            st.is_final,
            "a non-zero committer at the local root = finality"
        );
    }

    #[test]
    fn is_zero_address_detects_unset() {
        assert!(is_zero_address(&[0u8; 20]));
        let mut a = [0u8; 20];
        a[0] = 1;
        assert!(!is_zero_address(&a));
    }

    #[test]
    fn committer_of_calldata_is_selector_plus_root_word() {
        let root = [0x22u8; 32];
        let data = committer_of_calldata(&root);
        assert_eq!(data.len(), 4 + 32);
        assert_eq!(&data[0..4], &committer_of_selector());
        assert_eq!(&data[4..36], &root);
    }

    #[test]
    fn decode_address_result_takes_low_20_bytes() {
        // ABI address word: 12 zero bytes ++ 20 address bytes.
        let mut word = [0u8; 32];
        word[12..32].copy_from_slice(&[0xCD; 20]);
        assert_eq!(decode_address_result(&word), Some([0xCD; 20]));
        // short/empty result → None.
        assert_eq!(decode_address_result(&[]), None);
        assert_eq!(decode_address_result(&[0u8; 31]), None);
    }

    #[test]
    fn finality_summary_counts_finalized_and_pending() {
        let head = KotobaCid::from_bytes(b"h");
        let final_st = verify_finality(
            &head,
            Some({
                let mut a = [0u8; 20];
                a[19] = 1;
                a
            }),
        );
        let pending_st = verify_finality(&head, None);
        assert_eq!(finality_summary(&[]), FinalitySummary::default());
        let s = finality_summary(&[final_st, pending_st, final_st]);
        assert_eq!(s.tracked, 3);
        assert_eq!(s.finalized, 2);
        assert_eq!(s.pending, 1);
        assert_eq!(s.finalized + s.pending, s.tracked);
    }

    #[test]
    fn finality_invariants_hold_adversarially() {
        // verify_finality: final iff a non-zero committer is observed for the
        // head's own root hash; root_hash always = the head's low-32. And the
        // summary partition finalized+pending==tracked always holds. Sweep
        // committer shapes × batch compositions.
        let head = KotobaCid::from_bytes(b"head");
        let committers = [
            None,            // no record → pending
            Some([0u8; 20]), // zero address → pending
            Some({
                let mut a = [0u8; 20];
                a[0] = 1;
                a
            }), // non-zero → final
            Some({
                let mut a = [0u8; 20];
                a[19] = 1;
                a
            }), // non-zero → final
            Some([0xFF; 20]), // non-zero → final
        ];
        let mut statuses = Vec::new();
        for c in committers {
            let st = verify_finality(&head, c);
            assert_eq!(st.root_hash, root_hash_of(&head));
            assert_eq!(st.is_final, st.anchored, "is_final tracks anchored");
            let expect_final = matches!(c, Some(a) if !is_zero_address(&a));
            assert_eq!(st.is_final, expect_final, "final iff non-zero committer");
            statuses.push(st);
        }
        // every prefix of the batch keeps the partition invariant.
        for n in 0..=statuses.len() {
            let s = finality_summary(&statuses[..n]);
            assert_eq!(s.tracked, n);
            assert_eq!(s.finalized + s.pending, s.tracked, "partition must hold");
            assert_eq!(
                s.finalized,
                statuses[..n].iter().filter(|x| x.is_final).count()
            );
        }
    }

    #[test]
    fn finality_from_call_result_end_to_end() {
        let head = KotobaCid::from_bytes(b"head-7");
        // zero-address word → not final.
        assert!(!finality_from_call_result(&head, &[0u8; 32]).is_final);
        // empty (reverted) → not final.
        assert!(!finality_from_call_result(&head, &[]).is_final);
        // non-zero committer word → final, and root hash matches the head.
        let mut word = [0u8; 32];
        word[31] = 0x09;
        let st = finality_from_call_result(&head, &word);
        assert!(st.is_final);
        assert_eq!(st.root_hash, root_hash_of(&head));
    }
}
