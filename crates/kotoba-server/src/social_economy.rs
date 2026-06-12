//! `SocialEconomyDriver` — the **wiring** that ties the whole Mishmar social-capital
//! loop into one runnable unit (ADR-2606082100):
//!
//! ```text
//! observe (eth_getLogs pins + KaizenObserver Δ)
//!   → mint (validate+weigh)  → social/* Datoms
//!   → maintain SocialCapitalView  → SC_root
//!   → allocate retainer (§6)  → settle → per-pinner mKOTO credits
//! ```
//!
//! The orchestration is **fully testable end-to-end with fakes** ([`SocialEconomyDriver::tick`]
//! is generic over [`JsonRpcTransport`]); the only external dependencies are the
//! live EVM RPC socket ([`ReqwestRpc`]) and the KaizenObserver feed URL, both read
//! from env in [`live_evm_source`] / [`fetch_kaizen_feed`].
//!
//! The in-memory `SocialCapitalView` + indexes are the maintained MV; the minted
//! Datoms returned by `mint`/`tick` MUST be transacted to the canonical Datom log
//! by the caller (which is how they survive restart — the view rebuilds from the log).

use crate::econ::Econ;
use crate::mishmar_observe::{
    parse_kaizen_wellbecoming, EvmLogObservationSource, JsonRpcTransport, ReqwestRpc,
};
use crate::social::settle_retainer_to_econ;
use kotoba_core::cid::KotobaCid;
use kotoba_query::datom::Datom;
use kotoba_query::delta::Delta;
use kotoba_query::social::{
    allocate_retainer, build_pin_origins, settle_retainer, Falsification, MintParams,
    ObservedDisclosure, ObservedWellbecoming, OriginIndex, PinIndex, RetainerCredit, RetainerShare,
    SocialCapitalView, SocialMintJob,
};

/// The outcome of settling one epoch.
pub struct SettlementResult {
    pub shares: Vec<RetainerShare>,
    pub credits: Vec<RetainerCredit>,
    pub total_mkoto: i64,
    pub remainder_mkoto: i64,
}

/// Holds the maintained MV state (view + indexes) and drives the loop.
pub struct SocialEconomyDriver {
    job: SocialMintJob,
    pub view: SocialCapitalView,
    pub pins: PinIndex,
    pub origins: OriginIndex,
}

impl SocialEconomyDriver {
    pub fn new(params: MintParams, graph: KotobaCid) -> Self {
        Self {
            job: SocialMintJob::new(params, graph),
            view: SocialCapitalView::new(),
            pins: PinIndex::new(),
            origins: OriginIndex::new(),
        }
    }

    /// Ingest observed `mishmar/pin/*` Datoms (from `EvmLogObservationSource::pin_datoms`).
    pub fn ingest_pins(&mut self, pin_datoms: &[Datom]) {
        let deltas: Vec<Delta> = pin_datoms.iter().cloned().map(Delta::assert_datom).collect();
        self.pins.apply(&deltas);
    }

    /// Ingest observed `social/origin` Datoms.
    pub fn ingest_origins(&mut self, origin_datoms: &[Datom]) {
        let deltas: Vec<Delta> = origin_datoms.iter().cloned().map(Delta::assert_datom).collect();
        self.origins.apply(&deltas);
    }

    /// Validate + weigh an epoch's observations → social Datoms; apply them to the
    /// in-memory view; return the Datoms for the caller to transact to the log.
    pub fn mint(
        &mut self,
        disclosures: &[ObservedDisclosure],
        wellbecomings: &[ObservedWellbecoming],
        falsifications: &[Falsification],
    ) -> Vec<Datom> {
        let datoms = self.job.run_epoch(disclosures, wellbecomings, falsifications);
        let deltas: Vec<Delta> = datoms.iter().cloned().map(Delta::assert_datom).collect();
        self.view.apply(&deltas);
        datoms
    }

    /// Allocate the epoch's donation-funded retainer pool across known pins by
    /// SC_root, then settle to per-pinner mKOTO credits.
    pub fn settle(&self, epoch: u64, pool_mkoto: i64) -> SettlementResult {
        let pin_ids = self.pins.pin_ids();
        let pin_origins = build_pin_origins(&pin_ids, &self.pins, &self.origins);
        let (shares, remainder) = allocate_retainer(&pin_origins, &self.view, epoch, pool_mkoto);
        let (credits, total) = settle_retainer(&shares, |p| self.pins.pinner_of(p));
        SettlementResult { shares, credits, total_mkoto: total, remainder_mkoto: remainder }
    }

    /// One full cycle, generic over the EVM transport so it is testable end-to-end
    /// with a fake. Observes pins from chain + wellbecoming from a Kaizen feed,
    /// mints, and settles. Returns the Datoms to transact + the settlement.
    ///
    /// (ClaimStakeEscrow disclosure/falsification observation is a further decoder;
    /// here those inputs are empty until that source lands — wellbecoming + pin
    /// observation are wired.)
    pub fn tick<T: JsonRpcTransport>(
        &mut self,
        evm: &EvmLogObservationSource<T>,
        kaizen_feed: &serde_json::Value,
        from_block: &str,
        to_block: &str,
        epoch: u64,
        pool_mkoto: i64,
    ) -> Result<(Vec<Datom>, SettlementResult), String> {
        let pin_datoms = evm.pin_datoms(from_block, to_block)?;
        self.ingest_pins(&pin_datoms);

        let wellbecomings = parse_kaizen_wellbecoming(kaizen_feed);
        let minted = self.mint(&[], &wellbecomings, &[]);

        let result = self.settle(epoch, pool_mkoto);
        Ok((minted, result))
    }

    /// Apply a settlement's credits to the live, persisted mKOTO wallet.
    pub async fn settle_to_wallet(econ: &Econ, result: &SettlementResult) -> i64 {
        settle_retainer_to_econ(econ, &result.credits).await
    }
}

/// Construct the live EVM observation source from env (the external wiring):
/// `KOTOBA_EVM_RPC_URL` (geth-private / Base L2) + `KOTOBA_MISHMAR_ESCROW_ADDR`.
/// Returns `None` if either is unset.
pub fn live_evm_source(graph: KotobaCid) -> Option<EvmLogObservationSource<ReqwestRpc>> {
    let url = std::env::var("KOTOBA_EVM_RPC_URL").ok()?;
    let escrow = std::env::var("KOTOBA_MISHMAR_ESCROW_ADDR").ok()?;
    Some(EvmLogObservationSource::new(ReqwestRpc { url }, escrow, graph))
}

/// Fetch the KaizenObserver wellbecoming feed JSON from `KOTOBA_KAIZEN_FEED_URL`
/// (blocking; call off the async hot path). Returns `None` if unset/unreachable.
/// The feed schema is provisional — see [`parse_kaizen_wellbecoming`].
pub fn fetch_kaizen_feed() -> Option<serde_json::Value> {
    let url = std::env::var("KOTOBA_KAIZEN_FEED_URL").ok()?;
    reqwest::blocking::get(url).ok()?.json().ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mishmar_observe::JsonRpcTransport;
    use kotoba_query::social::{MintSource, ValidatedDisclosure, SCALE};
    use serde_json::json;

    fn did(s: &str) -> KotobaCid {
        KotobaCid::from_bytes(s.as_bytes())
    }

    fn cid_datom(e: &KotobaCid, attr: &str, v: &KotobaCid) -> Datom {
        Datom::assert(e.clone(), attr.to_string(), kotoba_query::datom::Value::Cid(v.clone()), did("g"))
    }

    /// fake EVM transport returning canned eth_getLogs results.
    struct FakeRpc {
        logs: serde_json::Value,
    }
    impl JsonRpcTransport for FakeRpc {
        fn call(&self, _m: &str, _p: serde_json::Value) -> Result<serde_json::Value, String> {
            Ok(self.logs.clone())
        }
    }

    #[test]
    fn driver_runs_full_loop_with_direct_inputs() {
        let graph = did("g:social");
        let a = did("did:key:a");
        let b = did("did:key:b");
        let peggy = did("did:key:peggy");
        let mut d = SocialEconomyDriver::new(MintParams::default(), graph);

        // observe pins: pinA(rootA,peggy), pinB(rootB,peggy)
        d.ingest_pins(&[
            cid_datom(&did("pinA"), "mishmar/pin/pinner", &peggy),
            cid_datom(&did("pinA"), "mishmar/pin/root", &did("rootA")),
            cid_datom(&did("pinB"), "mishmar/pin/pinner", &peggy),
            cid_datom(&did("pinB"), "mishmar/pin/root", &did("rootB")),
        ]);
        d.ingest_origins(&[
            cid_datom(&did("rootA"), "social/origin", &a),
            cid_datom(&did("rootB"), "social/origin", &b),
        ]);

        // mint: a = 30 pts disclosure, b = 70 pts disclosure (validated)
        let disc = vec![
            ObservedDisclosure { did: a.clone(), epoch: 0, n_validated: 30, citation_hits: 0, terminal_honest: true, witness_quorum_met: true },
            ObservedDisclosure { did: b.clone(), epoch: 0, n_validated: 70, citation_hits: 0, terminal_honest: true, witness_quorum_met: true },
        ];
        let minted = d.mint(&disc, &[], &[]);
        assert_eq!(minted.len(), 2);
        assert_eq!(d.view.capital(&a, 0), 30 * SCALE);
        assert_eq!(d.view.capital(&b, 0), 70 * SCALE);

        // settle pool 1_000_000: both pins → peggy → whole pool aggregated.
        let r = d.settle(0, 1_000_000);
        assert_eq!(r.credits.len(), 1);
        assert_eq!(r.credits[0].pinner_did, peggy);
        assert_eq!(r.credits[0].mkoto, 1_000_000); // 300k + 700k, both pins → peggy (clean split, no dust)
        assert_eq!(r.total_mkoto + r.remainder_mkoto, 1_000_000); // conserving
        assert_eq!(r.remainder_mkoto, 0);
    }

    #[test]
    fn tick_wires_chain_and_kaizen_end_to_end() {
        // a Pinned log for pinA→(rootA, pinner addr); a Kaizen Δ for alice.
        let pin = {
            let mut x = [0u8; 32];
            x[31] = 0x11;
            x
        };
        let root = {
            let mut x = [0u8; 32];
            x[31] = 0x22;
            x
        };
        let mut pinner_topic = [0u8; 32];
        pinner_topic[31] = 0x33;
        let topic0 = format!(
            "0x{}",
            hex::encode(kotoba_auth::eth::keccak256(
                b"Pinned(bytes32,bytes32,address,bytes32,uint256,uint64)"
            ))
        );
        let logs = json!([{
            "topics": [ topic0, format!("0x{}", hex::encode(pin)), format!("0x{}", hex::encode(root)), format!("0x{}", hex::encode(pinner_topic)) ],
            "data": "0x"
        }]);
        let graph = did("g:social");
        let evm = EvmLogObservationSource::new(FakeRpc { logs }, "0xescrow", graph.clone());

        // origin: rootA originated by alice (whose entity cid = did_to_cid).
        let alice_cid = crate::did_bridge::did_to_cid("did:web:alice");
        let mut d = SocialEconomyDriver::new(MintParams::default(), graph);
        d.ingest_origins(&[cid_datom(&KotobaCid::from_bytes(&root), "social/origin", &alice_cid)]);

        // Kaizen feed: alice Δ=+10 council-attested → 20 pts.
        let feed = json!([{ "did": "did:web:alice", "epoch": 0, "delta": 10, "council_attested": true }]);

        let (minted, result) = d.tick(&evm, &feed, "0x0", "latest", 0, 500_000).expect("tick ok");
        assert_eq!(minted.len(), 1); // alice's wellbecoming mint
        assert_eq!(d.view.capital(&alice_cid, 0), 20 * SCALE); // w_wellbecoming 2.0 * 10

        // the pin (pinner addr) keeps rootA (alice's data) → gets the whole pool.
        let pinner_cid = crate::did_bridge::did_to_cid(""); // placeholder; real pinner is from the addr
        let _ = pinner_cid;
        assert_eq!(result.total_mkoto, 500_000); // sole pin, all capital under its root
        assert_eq!(result.remainder_mkoto, 0);
    }

    #[tokio::test]
    async fn settle_to_wallet_credits_econ() {
        let graph = did("g:social");
        let mut d = SocialEconomyDriver::new(MintParams::default(), graph);
        let peggy = did("did:key:peggy");
        d.ingest_pins(&[
            cid_datom(&did("pinA"), "mishmar/pin/pinner", &peggy),
            cid_datom(&did("pinA"), "mishmar/pin/root", &did("rootA")),
        ]);
        d.ingest_origins(&[cid_datom(&did("rootA"), "social/origin", &did("did:key:a"))]);
        // give 'a' some capital so the pin's SC_root > 0
        let v = ValidatedDisclosure::new(did("did:key:a"), 0, 10, 0, true, true).unwrap();
        d.mint(
            &[ObservedDisclosure { did: did("did:key:a"), epoch: 0, n_validated: 10, citation_hits: 0, terminal_honest: true, witness_quorum_met: true }],
            &[],
            &[],
        );
        let _ = v;

        let result = d.settle(0, 1_000);
        let econ = Econ::from_env("did:key:operator".to_string());
        let credited = SocialEconomyDriver::settle_to_wallet(&econ, &result).await;
        assert_eq!(credited, 1_000);
        assert_eq!(econ.balance(&peggy.to_string()).await, 1_000);
    }
}
