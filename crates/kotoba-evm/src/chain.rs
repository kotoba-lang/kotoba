//! kotoba-EVM R2.5 — block persistence: IPFS CARv1 data-availability + chain-head
//! append (ADR-2606091500). A produced block's `evm/*` state-diff Datoms are
//! content-addressed into a `BlockStore`, bundled into a CARv1 (the DA wire format,
//! pinnable to IPFS), and the block is appended to the [`EvmChain`] head — so the
//! chain is replayable + verifiable from genesis by anyone holding the CARs.

use bytes::Bytes;
use serde::{Deserialize, Serialize};

use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use kotoba_query::datom::Datom;
use kotoba_store::car_bundle::CarBundleWriter;
use kotoba_store::put_verified;

use crate::block::ProducedBlock;

/// The persisted block header: links the parent + commits to the post-state root
/// and the content-addressed `evm/*` state-diff Datom blocks (the block payload).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EvmBlockHeader {
    pub number: u64,
    pub parent: Option<KotobaCid>,
    pub timestamp: u64,
    pub state_root: KotobaCid,
    pub tx_count: usize,
    /// content CIDs of the state-diff Datom blocks in this block.
    pub datom_cids: Vec<KotobaCid>,
}

/// Result of committing a block to the store: the block CID (chain head) + the
/// CARv1 bundle bytes (the DA artifact to pin to IPFS).
pub struct CommittedBlock {
    pub block_cid: KotobaCid,
    pub car: Vec<u8>,
}

/// An EVM chain over a content-addressed `BlockStore`: persists each block's
/// payload + advances the head. R2.5 keeps the head as an in-memory ref; wiring it
/// to the kotoba CommitDag head-ref is the final integration (R3+).
pub struct EvmChain<'a> {
    store: &'a dyn BlockStore,
    head: Option<KotobaCid>,
    height: u64,
}

impl<'a> EvmChain<'a> {
    pub fn new(store: &'a dyn BlockStore) -> Self {
        Self {
            store,
            head: None,
            height: 0,
        }
    }

    pub fn head(&self) -> Option<&KotobaCid> {
        self.head.as_ref()
    }
    pub fn height(&self) -> u64 {
        self.height
    }

    /// Persist a produced block: content-address its diff Datoms into the store +
    /// a CARv1 bundle (root = block CID), store the header under the block CID, and
    /// advance the head. Returns the block CID + the CAR bytes (the DA artifact).
    pub fn commit_block(&mut self, produced: &ProducedBlock) -> anyhow::Result<CommittedBlock> {
        let block_cid = produced.block.block_cid.clone();
        let mut car = CarBundleWriter::new(block_cid.clone());

        // 1. content-address each state-diff Datom → store + CAR.
        let mut datom_cids = Vec::with_capacity(produced.datoms.len());
        for d in &produced.datoms {
            let mut bytes = Vec::new();
            ciborium::ser::into_writer(d, &mut bytes)
                .map_err(|e| anyhow::anyhow!("datom enc: {e}"))?;
            let cid = KotobaCid::from_bytes(&bytes);
            put_verified(self.store, &cid, &bytes)?;
            car.append(&cid, &bytes);
            datom_cids.push(cid);
        }

        // 2. the block header (links parent + state root + the datom blocks).
        let header = EvmBlockHeader {
            number: produced.block.number,
            parent: produced.block.parent.clone(),
            timestamp: produced.block.timestamp,
            state_root: produced.block.state_root.clone(),
            tx_count: produced.block.tx_count,
            datom_cids,
        };
        let mut hbytes = Vec::new();
        ciborium::ser::into_writer(&header, &mut hbytes)
            .map_err(|e| anyhow::anyhow!("header enc: {e}"))?;
        // header is keyed by the block CID (the chain-id digest), not its own hash.
        self.store.put(&block_cid, &hbytes)?;
        car.append(&block_cid, &hbytes);

        // 3. the CARv1 DA artifact (pin to IPFS in production).
        let (car_bytes, _index) = car.finish();

        // 4. advance the head.
        self.head = Some(block_cid.clone());
        self.height = produced.block.number;

        Ok(CommittedBlock {
            block_cid,
            car: car_bytes,
        })
    }

    /// Read a persisted block back from the store: its header + reconstructed
    /// state-diff Datoms. `None` if the block CID is absent.
    pub fn read_block(
        &self,
        block_cid: &KotobaCid,
    ) -> anyhow::Result<Option<(EvmBlockHeader, Vec<Datom>)>> {
        let Some(hbytes) = self.store.get(block_cid)? else {
            return Ok(None);
        };
        let header: EvmBlockHeader = ciborium::de::from_reader(&hbytes[..])
            .map_err(|e| anyhow::anyhow!("header dec: {e}"))?;
        let mut datoms = Vec::with_capacity(header.datom_cids.len());
        for cid in &header.datom_cids {
            let b: Bytes = self
                .store
                .get(cid)?
                .ok_or_else(|| anyhow::anyhow!("missing datom block"))?;
            let d: Datom =
                ciborium::de::from_reader(&b[..]).map_err(|e| anyhow::anyhow!("datom dec: {e}"))?;
            datoms.push(d);
        }
        Ok(Some((header, datoms)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::block::produce_block;
    use kotoba_query::delta::Delta;
    use kotoba_query::evm_state::{account_datoms, EvmStateView};
    use kotoba_store::memory_store::MemoryBlockStore;
    use revm::primitives::U256;

    fn graph() -> KotobaCid {
        KotobaCid::from_bytes(b"g:evm")
    }
    fn u256(n: u128) -> [u8; 32] {
        U256::from(n).to_be_bytes()
    }
    const EIP155_RAW: &str = "f86c098504a817c800825208943535353535353535353535353535353535353535880de0b6b3a76400008025a028ef61340bd939bc2195fe537567866003e1a15d3c71ff63e1590620aa636276a067cbe9d8997f761aecb703304b3800ccf555c9f3dc64214b297fb1966a3b6d83";
    fn sender20() -> [u8; 20] {
        let mut a = [0u8; 20];
        a.copy_from_slice(&hex::decode("9d8a62f656a8d1615c1294fd71e9cfb3e4855a4f").unwrap());
        a
    }

    #[test]
    fn commit_persists_block_with_car_and_advances_head() {
        let from = sender20();
        let genesis = account_datoms(&from, 9, &u256(2_000_000_000_000_000_000), None, &graph());
        let raw = hex::decode(EIP155_RAW).unwrap();
        let produced = produce_block(&genesis, &[raw], None, 1, 100, &graph());

        let store = MemoryBlockStore::new();
        let mut chain = EvmChain::new(&store);
        assert!(chain.head().is_none());

        let committed = chain.commit_block(&produced).expect("commit");
        // head advanced to the block CID; CAR is a valid CARv1 (MAGIC prefix).
        assert_eq!(chain.head(), Some(&committed.block_cid));
        assert_eq!(chain.height(), 1);
        assert!(!committed.car.is_empty());
        assert_eq!(&committed.car[0..4], b"KCAR", "CARv1 magic"); // kotoba CAR magic

        // the block is replayable from the store: read header + diff Datoms back,
        // apply them, and confirm the post-state (recipient credited).
        let (header, datoms) = chain
            .read_block(&committed.block_cid)
            .expect("read")
            .expect("present");
        assert_eq!(header.number, 1);
        assert_eq!(header.tx_count, 1);
        assert_eq!(header.state_root, produced.block.state_root);

        let mut v = EvmStateView::new();
        v.apply(
            &datoms
                .into_iter()
                .map(Delta::assert_datom)
                .collect::<Vec<_>>(),
        );
        let mut to = [0u8; 20];
        to.copy_from_slice(&hex::decode("3535353535353535353535353535353535353535").unwrap());
        assert_eq!(v.balance_of(&to), u256(1_000_000_000_000_000_000));
    }

    #[test]
    fn chain_links_blocks_via_parent() {
        let from = sender20();
        let genesis = account_datoms(&from, 9, &u256(2_000_000_000_000_000_000), None, &graph());
        let raw = hex::decode(EIP155_RAW).unwrap();
        let store = MemoryBlockStore::new();
        let mut chain = EvmChain::new(&store);

        let b1 = produce_block(&genesis, &[raw], None, 1, 100, &graph());
        let c1 = chain.commit_block(&b1).unwrap();

        // block 2 links block 1 as parent.
        let b2 = produce_block(&genesis, &[], Some(c1.block_cid.clone()), 2, 200, &graph());
        let c2 = chain.commit_block(&b2).unwrap();

        assert_eq!(chain.head(), Some(&c2.block_cid));
        assert_eq!(chain.height(), 2);
        let (h2, _) = chain.read_block(&c2.block_cid).unwrap().unwrap();
        assert_eq!(h2.parent, Some(c1.block_cid), "block 2 links block 1");
    }

    #[test]
    fn read_unknown_block_is_none() {
        let store = MemoryBlockStore::new();
        let chain = EvmChain::new(&store);
        assert!(chain
            .read_block(&KotobaCid::from_bytes(b"nope"))
            .unwrap()
            .is_none());
    }
}
