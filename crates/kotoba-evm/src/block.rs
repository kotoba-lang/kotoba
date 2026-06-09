//! kotoba-EVM R2 — block production (ADR-2606091500). An EVM block is one
//! CommitDag commit carrying the ordered txs + the post-execution `stateRoot`.
//! [`produce_block`] executes a batch of raw signed txs in order over an evolving
//! Datom state, accumulates the `evm/*` state-diff Datoms (the block's state), and
//! content-addresses the block header (block hash = its CID).
//!
//! R2 scope: deterministic multi-tx execution + content-addressed block + state
//! root. IPFS CAR data-availability + the CommitDag head append are the mechanical
//! store-integration step (kotoba-store `CarBundleWriter` + `CommitDag::add`),
//! wired next.

use kotoba_core::cid::KotobaCid;
use kotoba_kqe::datom::Datom;
use kotoba_kqe::delta::Delta;
use kotoba_kqe::evm_state::EvmStateView;

use crate::logs::logs_bloom;
use crate::tx::apply_raw_tx;
use crate::EvmLog;

/// An EVM block header (content-addressed; `block_cid` is the block hash).
#[derive(Debug, Clone)]
pub struct EvmBlock {
    pub number: u64,
    pub parent: Option<KotobaCid>,
    pub timestamp: u64,
    pub tx_count: usize,
    /// post-execution world-state root (`EvmStateView::state_root`).
    pub state_root: KotobaCid,
    /// content-addressed block id (= block hash).
    pub block_cid: KotobaCid,
}

/// Result of producing a block: the header + the full `evm/*` state-diff Datoms to
/// commit (the block's payload), and the indices of txs that were rejected.
pub struct ProducedBlock {
    pub block: EvmBlock,
    pub datoms: Vec<Datom>,
    /// event logs emitted across the block's txs (for receipts / `eth_getLogs`).
    pub logs: Vec<EvmLog>,
    /// 2048-bit bloom over `logs` (block-level).
    pub logs_bloom: [u8; 256],
    /// (index, reason) for each tx that failed to decode/execute (excluded).
    pub rejected: Vec<(usize, String)>,
}

/// Execute `raw_txs` in order over the state seeded by `prior_state_datoms`,
/// accumulating each tx's diff so later txs see earlier effects, and produce the
/// block. `parent`/`number`/`timestamp` form the header; the block CID commits to
/// all of them + the state root (deterministic).
pub fn produce_block(
    prior_state_datoms: &[Datom],
    raw_txs: &[Vec<u8>],
    parent: Option<KotobaCid>,
    number: u64,
    timestamp: u64,
    graph: &KotobaCid,
) -> ProducedBlock {
    // seed the evolving view with the prior state.
    let mut view = EvmStateView::new();
    view.apply(
        &prior_state_datoms.iter().cloned().map(Delta::assert_datom).collect::<Vec<_>>(),
    );

    let mut diff: Vec<Datom> = Vec::new();
    let mut logs: Vec<EvmLog> = Vec::new();
    let mut rejected: Vec<(usize, String)> = Vec::new();
    let mut applied = 0usize;

    for (i, raw) in raw_txs.iter().enumerate() {
        match apply_raw_tx(&view, raw, graph) {
            Ok((_tx, out)) if out.success => {
                // fold this tx's diff into the evolving view so the next tx sees it.
                view.apply(&out.datoms.iter().cloned().map(Delta::assert_datom).collect::<Vec<_>>());
                diff.extend(out.datoms);
                logs.extend(out.logs);
                applied += 1;
            }
            Ok((_tx, out)) => rejected.push((i, format!("reverted (gas {})", out.gas_used))),
            Err(e) => rejected.push((i, e)),
        }
    }
    let bloom = logs_bloom(&logs);

    let state_root = view.state_root();
    let parent_tag = parent.as_ref().map(|c| c.to_multibase()).unwrap_or_default();
    let header = format!(
        "kotoba-evm/block/v1\n{number}\n{parent_tag}\n{timestamp}\n{applied}\n{}",
        state_root.to_multibase()
    );
    let block_cid = KotobaCid::from_bytes(header.as_bytes());

    ProducedBlock {
        block: EvmBlock { number, parent, timestamp, tx_count: applied, state_root, block_cid },
        datoms: diff,
        logs,
        logs_bloom: bloom,
        rejected,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_kqe::evm_state::account_datoms;
    use revm::primitives::U256;

    fn graph() -> KotobaCid {
        KotobaCid::from_bytes(b"g:evm")
    }
    fn u256(n: u128) -> [u8; 32] {
        U256::from(n).to_be_bytes()
    }
    // EIP-155 canonical tx (sender 0x9d8a..a4f, to 0x3535..3535, value 1e18, nonce 9).
    const EIP155_RAW: &str = "f86c098504a817c800825208943535353535353535353535353535353535353535880de0b6b3a76400008025a028ef61340bd939bc2195fe537567866003e1a15d3c71ff63e1590620aa636276a067cbe9d8997f761aecb703304b3800ccf555c9f3dc64214b297fb1966a3b6d83";

    fn sender20() -> [u8; 20] {
        let mut a = [0u8; 20];
        a.copy_from_slice(&hex::decode("9d8a62f656a8d1615c1294fd71e9cfb3e4855a4f").unwrap());
        a
    }

    #[test]
    fn produces_block_with_executed_tx_and_state_root() {
        let from = sender20();
        let genesis = account_datoms(&from, 9, &u256(2_000_000_000_000_000_000), None, &graph());
        let raw = hex::decode(EIP155_RAW).unwrap();

        let produced = produce_block(&genesis, &[raw], None, 1, 1_700_000_000, &graph());
        assert_eq!(produced.block.tx_count, 1, "one tx applied");
        assert!(produced.rejected.is_empty());
        assert_eq!(produced.block.number, 1);
        assert!(produced.block.parent.is_none());

        // the diff advances state: recipient credited, sender nonce bumped.
        let mut pv = EvmStateView::new();
        pv.apply(&produced.datoms.iter().cloned().map(Delta::assert_datom).collect::<Vec<_>>());
        let mut to = [0u8; 20];
        to.copy_from_slice(&hex::decode("3535353535353535353535353535353535353535").unwrap());
        assert_eq!(pv.balance_of(&to), u256(1_000_000_000_000_000_000));
        assert_eq!(pv.nonce_of(&from), 10);
    }

    #[test]
    fn block_is_deterministic_and_links_parent() {
        let from = sender20();
        let genesis = account_datoms(&from, 9, &u256(2_000_000_000_000_000_000), None, &graph());
        let raw = hex::decode(EIP155_RAW).unwrap();

        let b1 = produce_block(&genesis, &[raw.clone()], None, 1, 100, &graph());
        let b1again = produce_block(&genesis, &[raw.clone()], None, 1, 100, &graph());
        assert_eq!(b1.block.block_cid, b1again.block.block_cid, "deterministic block hash");
        assert_eq!(b1.block.state_root, b1again.block.state_root, "deterministic state root");

        // block 2 links block 1 as parent → distinct CID.
        let b2 = produce_block(&genesis, &[], Some(b1.block.block_cid.clone()), 2, 200, &graph());
        assert_eq!(b2.block.parent, Some(b1.block.block_cid.clone()));
        assert_ne!(b2.block.block_cid, b1.block.block_cid);
    }

    #[test]
    fn rejects_undecodable_tx_without_aborting_block() {
        let from = sender20();
        let genesis = account_datoms(&from, 9, &u256(2_000_000_000_000_000_000), None, &graph());
        let good = hex::decode(EIP155_RAW).unwrap();
        let bad = vec![0xde, 0xad, 0xbe, 0xef];

        let produced = produce_block(&genesis, &[bad, good], None, 1, 1, &graph());
        assert_eq!(produced.block.tx_count, 1, "good tx applied, bad rejected");
        assert_eq!(produced.rejected.len(), 1);
        assert_eq!(produced.rejected[0].0, 0, "the bad tx (index 0) was rejected");
    }
}
