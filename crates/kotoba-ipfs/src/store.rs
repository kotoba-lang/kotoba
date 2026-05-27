use anyhow::Result;
use cid::Cid;
use co_libp2p_bitswap::{BitswapStore, Block, Token};
use libp2p::PeerId;
use multihash::Multihash;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

/// SHA2-256 multihash code.
const SHA2_256: u64 = 0x12;
/// CIDv1 raw codec.
const RAW: u64 = 0x55;

/// Compute a CIDv1 SHA2-256 raw content identifier.
pub fn cid_for(data: &[u8]) -> Cid {
    let digest = Sha256::digest(data);
    let mh = Multihash::<64>::wrap(SHA2_256, &digest).expect("multihash wrap");
    Cid::new_v1(RAW, mh)
}

/// In-memory block store keyed by CIDv1 SHA2-256.
#[derive(Clone, Default)]
pub struct MemBlockStore {
    inner: Arc<RwLock<HashMap<Cid, Vec<u8>>>>,
}

impl MemBlockStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn put(&self, data: Vec<u8>) -> Cid {
        let cid = cid_for(&data);
        self.inner.write().unwrap().insert(cid, data);
        cid
    }

    pub fn get_local(&self, cid: &Cid) -> Option<Vec<u8>> {
        self.inner.read().unwrap().get(cid).cloned()
    }

    pub fn contains_local(&self, cid: &Cid) -> bool {
        self.inner.read().unwrap().contains_key(cid)
    }

    fn missing_refs(&self, cid: &Cid) -> Vec<Cid> {
        // For raw blocks there are no links; return the CID itself if absent.
        if self.contains_local(cid) {
            vec![]
        } else {
            vec![*cid]
        }
    }
}

#[async_trait::async_trait]
impl BitswapStore for MemBlockStore {
    async fn contains(&mut self, cid: &Cid, _peer: &PeerId, _tokens: &[Token]) -> Result<bool> {
        Ok(self.contains_local(cid))
    }

    async fn get(
        &mut self,
        cid: &Cid,
        _peer: &PeerId,
        _tokens: &[Token],
    ) -> Result<Option<Vec<u8>>> {
        Ok(self.get_local(cid))
    }

    async fn insert(&mut self, block: &Block, _peer: &PeerId, _tokens: &[Token]) -> Result<()> {
        self.inner
            .write()
            .unwrap()
            .insert(*block.cid(), block.data().to_vec());
        Ok(())
    }

    async fn missing_blocks(&mut self, cid: &Cid, _tokens: &[Token]) -> Result<Vec<Cid>> {
        Ok(self.missing_refs(cid))
    }
}
