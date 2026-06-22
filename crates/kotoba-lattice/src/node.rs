//! Stateful lattice controller — the continuous reconcile→auction→place loop
//! (ADR M2). This is the *brain that runs over time*; M1's `reconcile` module is
//! the pure decision functions it calls.
//!
//! Transport-agnostic by design: the controller consumes inbound messages
//! ([`LatticeController::on_message`]) and returns outbound messages to publish
//! ([`LatticeController::tick`] / [`LatticeController::close_due`]). The actual
//! gossipsub publish/subscribe is wired in `kotoba-net` via the [`Transport`]
//! trait, so the loop here stays pure and fully unit-testable.
//!
//! Time is **injected** (`now_ms` parameters): `Date::now()`/`Instant` are
//! avoided so the loop is deterministic and resumable (mirrors the workspace
//! Pregel `now`-injection convention).

use std::collections::BTreeMap;

use crate::error::LatticeError;
use crate::manifest::AppManifest;
use crate::protocol::{auction_id, Auction, Award, Bid, Constraints, Heartbeat, LatticeMessage};
use crate::reconcile::{award_winners, need_actions, observed_counts, score_bid};

/// Sink for outbound lattice messages. Implemented in `kotoba-net` against the
/// gossipsub swarm; [`RecordingTransport`] implements it for tests/examples.
pub trait Transport {
    /// Publish a control-plane message to its lattice topic.
    fn publish(&mut self, topic: &str, msg: &LatticeMessage) -> Result<(), LatticeError>;
}

/// A [`Transport`] that records every published `(topic, msg)` — for tests and
/// the `mesh_node` example.
#[derive(Debug, Default)]
pub struct RecordingTransport {
    pub sent: Vec<(String, LatticeMessage)>,
}

impl Transport for RecordingTransport {
    fn publish(&mut self, topic: &str, msg: &LatticeMessage) -> Result<(), LatticeError> {
        self.sent.push((topic.to_string(), msg.clone()));
        Ok(())
    }
}

/// An auction the controller has opened and is collecting bids for.
#[derive(Debug, Clone)]
struct OpenAuction {
    auction: Auction,
    bids: Vec<Bid>,
    opened_ms: u64,
}

/// The lattice controller. Any number of these (one per node, leader-less) that
/// see the same heartbeats + same desired state converge identically, because
/// every decision (auction id, award) is deterministic.
#[derive(Debug)]
pub struct LatticeController {
    /// Desired component instance counts (cid/placeholder → want).
    desired: BTreeMap<String, u32>,
    /// Per-component placement constraints (cid/placeholder → constraints).
    constraints: BTreeMap<String, Constraints>,
    /// Latest heartbeat per node + the time it was received.
    fleet: BTreeMap<String, (Heartbeat, u64)>,
    /// Open auctions, keyed by component cid (at most one open per component).
    open: BTreeMap<String, OpenAuction>,
    /// A node is considered gone if its last heartbeat is older than this.
    ttl_ms: u64,
    /// How long to collect bids before awarding.
    bid_window_ms: u64,
}

impl LatticeController {
    /// `ttl_ms`: heartbeat staleness cutoff. `bid_window_ms`: auction bid window.
    pub fn new(ttl_ms: u64, bid_window_ms: u64) -> Self {
        Self {
            desired: BTreeMap::new(),
            constraints: BTreeMap::new(),
            fleet: BTreeMap::new(),
            open: BTreeMap::new(),
            ttl_ms,
            bid_window_ms,
        }
    }

    /// Load desired state + per-component constraints from an app manifest.
    /// Constraints = the component's required caps + the app placement labels.
    pub fn set_app(&mut self, app: &AppManifest) {
        self.desired = app.desired_by_cid();
        self.constraints.clear();
        for c in &app.components {
            let key = c.cid.clone().unwrap_or_else(|| format!("clj:{}", c.name));
            self.constraints.insert(
                key,
                Constraints {
                    require_labels: app.placement.require.clone(),
                    requires_caps: c.requires.clone(),
                },
            );
        }
    }

    /// Record an inbound heartbeat.
    pub fn on_heartbeat(&mut self, hb: Heartbeat, now_ms: u64) {
        self.fleet.insert(hb.node_did.clone(), (hb, now_ms));
    }

    /// Record an inbound bid against an open auction (ignored if unknown).
    pub fn on_bid(&mut self, bid: Bid) {
        for oa in self.open.values_mut() {
            if oa.auction.id == bid.auction_id {
                // de-dupe by node so a node bidding twice counts once (last wins)
                oa.bids.retain(|b| b.node_did != bid.node_did);
                oa.bids.push(bid);
                return;
            }
        }
    }

    /// Set desired state + constraints directly (e.g. from control-graph datoms
    /// via `crate::control::desired_from_quads`, or an inbound `PutApp`).
    pub fn set_desired(
        &mut self,
        desired: BTreeMap<String, u32>,
        constraints: BTreeMap<String, Constraints>,
    ) {
        self.desired = desired;
        self.constraints = constraints;
    }

    /// Convenience dispatch for any inbound [`LatticeMessage`].
    pub fn on_message(&mut self, msg: LatticeMessage, now_ms: u64) {
        match msg {
            LatticeMessage::Heartbeat(hb) | LatticeMessage::InventoryAck(hb) => {
                self.on_heartbeat(hb, now_ms)
            }
            LatticeMessage::Bid(b) => self.on_bid(b),
            LatticeMessage::PutApp { desired, constraints, .. } => {
                self.set_desired(desired, constraints)
            }
            _ => {}
        }
    }

    /// Live heartbeats (those seen within `ttl_ms` of `now_ms`).
    fn live(&self, now_ms: u64) -> Vec<&Heartbeat> {
        self.fleet
            .values()
            .filter(|(_, seen)| now_ms.saturating_sub(*seen) <= self.ttl_ms)
            .map(|(hb, _)| hb)
            .collect()
    }

    /// Observed instance counts across the *live* fleet.
    pub fn observed(&self, now_ms: u64) -> BTreeMap<String, u32> {
        let live: Vec<Heartbeat> = self.live(now_ms).into_iter().cloned().collect();
        observed_counts(&live)
    }

    /// Drop fleet entries whose heartbeat has gone stale. Returns the DIDs
    /// pruned (their hosted components will be re-auctioned on the next tick —
    /// self-healing).
    pub fn prune(&mut self, now_ms: u64) -> Vec<String> {
        let dead: Vec<String> = self
            .fleet
            .iter()
            .filter(|(_, (_, seen))| now_ms.saturating_sub(*seen) > self.ttl_ms)
            .map(|(did, _)| did.clone())
            .collect();
        for did in &dead {
            self.fleet.remove(did);
        }
        dead
    }

    /// One control-loop step: diff desired vs observed and open auctions for any
    /// shortfall (skipping components that already have an open auction), and
    /// emit scale-down for over-provisioned/undesired components. Returns the
    /// messages to publish on [`crate::protocol::topic`].
    pub fn tick(&mut self, now_ms: u64) -> Vec<(String, LatticeMessage)> {
        self.prune(now_ms);
        let observed = self.observed(now_ms);
        let actions = need_actions(&self.desired, &observed);
        let mut out = Vec::new();

        for a in actions {
            if a.delta > 0 {
                if self.open.contains_key(&a.cid) {
                    continue; // auction already in flight for this component
                }
                let want = self.desired.get(&a.cid).copied().unwrap_or(0);
                let have = observed.get(&a.cid).copied().unwrap_or(0);
                let constraints = self.constraints.get(&a.cid).cloned().unwrap_or_default();
                let auction = Auction {
                    id: auction_id(&a.cid, want, have),
                    cid: a.cid.clone(),
                    n: a.delta as u32,
                    constraints,
                };
                self.open.insert(
                    a.cid.clone(),
                    OpenAuction {
                        auction: auction.clone(),
                        bids: Vec::new(),
                        opened_ms: now_ms,
                    },
                );
                out.push((crate::protocol::topic::AUCTION.to_string(), LatticeMessage::Auction(auction)));
            } else {
                // over-provisioned or undesired → request scale to the target
                let n = self.desired.get(&a.cid).copied().unwrap_or(0);
                out.push((
                    crate::protocol::topic::CMD.to_string(),
                    LatticeMessage::ScaleTo { cid: a.cid.clone(), n },
                ));
            }
        }
        out
    }

    /// Compute this node's bid for an auction it just heard, if eligible. A node
    /// loop calls this with its own heartbeat and publishes the returned bid.
    pub fn bid_for(auction: &Auction, my: &Heartbeat) -> Option<Bid> {
        score_bid(my, &auction.constraints).map(|score| Bid {
            auction_id: auction.id.clone(),
            node_did: my.node_did.clone(),
            score,
        })
    }

    /// Close auctions whose bid window has elapsed: award deterministically and
    /// emit `Award` + `StartComponent` (one per winner). Returns messages to
    /// publish. Closed auctions are removed, so a still-unmet need re-opens on a
    /// later tick (retry / self-heal).
    pub fn close_due(&mut self, now_ms: u64) -> Vec<(String, LatticeMessage)> {
        let due: Vec<String> = self
            .open
            .iter()
            .filter(|(_, oa)| now_ms.saturating_sub(oa.opened_ms) >= self.bid_window_ms)
            .map(|(cid, _)| cid.clone())
            .collect();

        let mut out = Vec::new();
        for cid in due {
            let oa = self.open.remove(&cid).expect("present");
            let winners = award_winners(&oa.auction, &oa.bids);
            for w in winners {
                out.push((
                    crate::protocol::topic::AUCTION.to_string(),
                    LatticeMessage::Award(Award {
                        auction_id: oa.auction.id.clone(),
                        node_did: w.clone(),
                    }),
                ));
                out.push((
                    crate::protocol::topic::CMD.to_string(),
                    LatticeMessage::StartComponent {
                        node_did: w,
                        cid: oa.auction.cid.clone(),
                        count: 1,
                        links: Vec::new(),
                    },
                ));
            }
        }
        out
    }

    /// Drive both phases through a [`Transport`] in one call (tick then close).
    /// Returns the number of messages published.
    pub fn step<T: Transport>(&mut self, now_ms: u64, tx: &mut T) -> Result<usize, LatticeError> {
        let mut n = 0;
        for (topic, msg) in self.tick(now_ms) {
            tx.publish(&topic, &msg)?;
            n += 1;
        }
        for (topic, msg) in self.close_due(now_ms) {
            tx.publish(&topic, &msg)?;
            n += 1;
        }
        Ok(n)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::manifest::AppManifest;
    use crate::protocol::NodeRole;

    fn hb(did: &str, caps: &[&str], free_gas: u64, hosted: &[&str]) -> Heartbeat {
        Heartbeat {
            node_did: did.into(),
            roles: vec![NodeRole::Compute],
            labels: BTreeMap::new(),
            caps: caps.iter().map(|s| s.to_string()).collect(),
            free_gas,
            hosted: hosted.iter().map(|s| s.to_string()).collect(),
            lat_ms: 0,
        }
    }

    const APP: &str = r#"{:kotoba.app/name "t"
        :kotoba.app/components
        [{:name "reply" :cid "bafyReply" :scale 2 :requires [:cap/kqe]}]}"#;

    fn controller() -> LatticeController {
        let app = AppManifest::from_edn(APP).unwrap();
        let mut c = LatticeController::new(1000, 100);
        c.set_app(&app);
        c
    }

    #[test]
    fn tick_opens_one_auction_for_shortfall() {
        let mut c = controller();
        c.on_heartbeat(hb("nA", &["cap/kqe"], 100, &[]), 0);
        let msgs = c.tick(0);
        assert_eq!(msgs.len(), 1);
        assert!(matches!(msgs[0].1, LatticeMessage::Auction(_)));
        // second tick before close → no duplicate auction
        assert!(c.tick(10).is_empty());
    }

    #[test]
    fn bid_award_start_full_cycle() {
        let mut c = controller();
        c.on_heartbeat(hb("nA", &["cap/kqe"], 100, &[]), 0);
        c.on_heartbeat(hb("nB", &["cap/kqe"], 200, &[]), 0);
        c.on_heartbeat(hb("nC", &["cap/other"], 999, &[]), 0); // ineligible (no cap/kqe)

        let opened = c.tick(0);
        let auction = match &opened[0].1 {
            LatticeMessage::Auction(a) => a.clone(),
            _ => panic!(),
        };
        // each eligible node bids
        for did in ["nA", "nB", "nC"] {
            let my = hb(did, if did == "nC" { &["cap/other"] } else { &["cap/kqe"] }, if did=="nB"{200}else{100}, &[]);
            if let Some(b) = LatticeController::bid_for(&auction, &my) {
                c.on_bid(b);
            }
        }
        // close after window → award 2 winners (nC excluded), 2 starts
        let closed = c.close_due(120);
        let starts: Vec<_> = closed
            .iter()
            .filter_map(|(_, m)| match m {
                LatticeMessage::StartComponent { node_did, cid, .. } => Some((node_did.clone(), cid.clone())),
                _ => None,
            })
            .collect();
        assert_eq!(starts.len(), 2);
        assert!(starts.iter().all(|(_, cid)| cid == "bafyReply"));
        // nB (higher gas) must be a winner; nC must not
        let winners: Vec<&String> = starts.iter().map(|(n, _)| n).collect();
        assert!(winners.contains(&&"nB".to_string()));
        assert!(!winners.contains(&&"nC".to_string()));
    }

    #[test]
    fn converges_then_self_heals_on_node_loss() {
        let mut c = controller();
        c.on_heartbeat(hb("nA", &["cap/kqe"], 100, &[]), 0);
        c.on_heartbeat(hb("nB", &["cap/kqe"], 100, &[]), 0);
        let auction = match &c.tick(0)[0].1 {
            LatticeMessage::Auction(a) => a.clone(),
            _ => panic!(),
        };
        c.on_bid(LatticeController::bid_for(&auction, &hb("nA", &["cap/kqe"], 100, &[])).unwrap());
        c.on_bid(LatticeController::bid_for(&auction, &hb("nB", &["cap/kqe"], 100, &[])).unwrap());
        c.close_due(120);

        // winners now report the component hosted → observed == desired (2)
        c.on_heartbeat(hb("nA", &["cap/kqe"], 90, &["bafyReply"]), 130);
        c.on_heartbeat(hb("nB", &["cap/kqe"], 90, &["bafyReply"]), 130);
        assert_eq!(c.observed(130).get("bafyReply"), Some(&2));
        assert!(c.tick(140).is_empty(), "converged → no actions");

        // nB goes silent → pruned after ttl → observed drops to 1 → re-auction
        c.on_heartbeat(hb("nA", &["cap/kqe"], 90, &["bafyReply"]), 2000); // keep nA alive
        let pruned = c.prune(2000);
        assert!(pruned.contains(&"nB".to_string()));
        assert_eq!(c.observed(2000).get("bafyReply"), Some(&1));
        let healing = c.tick(2000);
        assert!(
            healing.iter().any(|(_, m)| matches!(m, LatticeMessage::Auction(_))),
            "lost instance must trigger a new auction (self-heal)"
        );
    }

    #[test]
    fn step_through_recording_transport() {
        let mut c = controller();
        c.on_heartbeat(hb("nA", &["cap/kqe"], 100, &[]), 0);
        let mut tx = RecordingTransport::default();
        let n = c.step(0, &mut tx).unwrap();
        assert_eq!(n, tx.sent.len());
        assert!(tx.sent.iter().any(|(t, _)| t == crate::protocol::topic::AUCTION));
    }

    #[test]
    fn put_app_sets_desired_and_drives_auctions() {
        // a node that starts with NO desired state receives a PutApp and then
        // begins emitting auctions for the announced components (wadm, M4).
        let mut c = LatticeController::new(1000, 100);
        c.on_heartbeat(hb("nA", &["cap/kqe"], 100, &[]), 0);
        assert!(c.tick(0).is_empty(), "no desired yet → no auctions");

        let put = LatticeMessage::PutApp {
            app: "bot".into(),
            desired: BTreeMap::from([("bafyX".to_string(), 1u32)]),
            constraints: BTreeMap::from([(
                "bafyX".to_string(),
                Constraints { require_labels: BTreeMap::new(), requires_caps: vec!["cap/kqe".into()] },
            )]),
        };
        c.on_message(put, 10);
        let msgs = c.tick(20);
        assert!(msgs.iter().any(|(_, m)| matches!(m, LatticeMessage::Auction(_))));
    }

    #[test]
    fn scale_down_emitted_when_over_provisioned() {
        let mut c = controller();
        // 3 nodes already hosting → observed 3 > desired 2
        for did in ["nA", "nB", "nD"] {
            c.on_heartbeat(hb(did, &["cap/kqe"], 100, &["bafyReply"]), 0);
        }
        let msgs = c.tick(0);
        let scale = msgs.iter().find_map(|(_, m)| match m {
            LatticeMessage::ScaleTo { cid, n } => Some((cid.clone(), *n)),
            _ => None,
        });
        assert_eq!(scale, Some(("bafyReply".to_string(), 2)));
    }
}
