//! Settlement proposal builder (ADR-2606011330 #2) — **PROPOSE-ONLY**.
//!
//! Turns audit `SettlementIntent`s into a Council-signable `SettlementBatch`
//! with USDC amounts resolved from a schedule. This is the artifact a Council
//! Lv6+ multisig reviews and signs to settle reward/slash on Base L2
//! (ADR-2605172100).
//!
//! **This module holds no key, moves no funds, and has no `transfer()`.**
//! On-chain execution is a separate, gated, Council-signed action (no-server-key
//! posture, ADR-2605231525). Building a proposal is pure data transformation.

use crate::audit::{SettlementIntent, SettlementKind};
use crate::node_id::NodeId;
use std::collections::BTreeMap;

/// Resolves audit `units` into USDC base units (micros; 1 USDC = 1_000_000).
#[derive(Debug, Clone, Copy)]
pub struct SettlementSchedule {
    pub usdc_micros_per_unit: u64,
}

impl SettlementSchedule {
    pub fn new(usdc_micros_per_unit: u64) -> Self {
        Self {
            usdc_micros_per_unit,
        }
    }

    /// Saturating units → USDC micros (no overflow panic on adversarial input).
    pub fn usdc_micros(&self, units: u64) -> u64 {
        units.saturating_mul(self.usdc_micros_per_unit)
    }
}

/// One resolved line of a settlement proposal: how much USDC to reward/slash a
/// single peer this batch.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SettlementLine {
    pub peer: NodeId,
    pub kind: SettlementKind,
    pub usdc_micros: u64,
}

/// A Council-ready settlement proposal — the propose-only hand-off to the
/// (gated) on-chain executor. Aggregates intents per `(peer, kind)` so a peer
/// rewarded across several epochs settles in one line. Lines are sorted for a
/// deterministic, signable artifact.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SettlementBatch {
    pub lines: Vec<SettlementLine>,
    pub total_reward_micros: u64,
    pub total_slash_micros: u64,
}

impl SettlementBatch {
    /// Build a proposal from pending intents under `schedule`. Pure: no funds
    /// move, no key is touched.
    pub fn from_intents(intents: &[SettlementIntent], schedule: SettlementSchedule) -> Self {
        // Aggregate per (peer, kind). Key by (node bytes, kind discriminant) for
        // a deterministic BTreeMap ordering.
        let mut agg: BTreeMap<([u8; 32], u8), (NodeId, SettlementKind, u64)> = BTreeMap::new();
        for i in intents {
            let kind_disc = match i.kind {
                SettlementKind::Reward => 0u8,
                SettlementKind::Slash => 1u8,
            };
            let micros = schedule.usdc_micros(i.units);
            let entry = agg
                .entry((i.peer.0, kind_disc))
                .or_insert((i.peer.clone(), i.kind, 0));
            entry.2 = entry.2.saturating_add(micros);
        }

        let mut lines = Vec::with_capacity(agg.len());
        let mut total_reward_micros = 0u64;
        let mut total_slash_micros = 0u64;
        for (_, (peer, kind, usdc_micros)) in agg {
            match kind {
                SettlementKind::Reward => {
                    total_reward_micros = total_reward_micros.saturating_add(usdc_micros)
                }
                SettlementKind::Slash => {
                    total_slash_micros = total_slash_micros.saturating_add(usdc_micros)
                }
            }
            lines.push(SettlementLine {
                peer,
                kind,
                usdc_micros,
            });
        }

        Self {
            lines,
            total_reward_micros,
            total_slash_micros,
        }
    }

    pub fn is_empty(&self) -> bool {
        self.lines.is_empty()
    }

    pub fn len(&self) -> usize {
        self.lines.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn intent(tag: &[u8], kind: SettlementKind, units: u64, epoch: u64) -> SettlementIntent {
        SettlementIntent {
            epoch,
            peer: NodeId::from_pubkey(tag),
            kind,
            units,
        }
    }

    #[test]
    fn schedule_converts_units_to_usdc_micros() {
        let s = SettlementSchedule::new(1_000); // 1000 micros (0.001 USDC) / unit
        assert_eq!(s.usdc_micros(0), 0);
        assert_eq!(s.usdc_micros(5), 5_000);
        // saturating, no panic on huge input
        assert_eq!(s.usdc_micros(u64::MAX), u64::MAX);
    }

    #[test]
    fn empty_intents_make_empty_batch() {
        let batch = SettlementBatch::from_intents(&[], SettlementSchedule::new(10));
        assert!(batch.is_empty());
        assert_eq!(batch.total_reward_micros, 0);
        assert_eq!(batch.total_slash_micros, 0);
    }

    #[test]
    fn aggregates_per_peer_and_kind() {
        let schedule = SettlementSchedule::new(100); // 100 micros / unit
        let intents = vec![
            intent(b"alice", SettlementKind::Reward, 3, 0), // 300
            intent(b"alice", SettlementKind::Reward, 2, 1), // +200 → 500 (same peer+kind)
            intent(b"bob", SettlementKind::Slash, 4, 0),    // 400
        ];
        let batch = SettlementBatch::from_intents(&intents, schedule);
        assert_eq!(batch.len(), 2, "alice's two rewards aggregate to one line");
        assert_eq!(batch.total_reward_micros, 500);
        assert_eq!(batch.total_slash_micros, 400);

        let alice = NodeId::from_pubkey(b"alice");
        let alice_line = batch.lines.iter().find(|l| l.peer == alice).unwrap();
        assert_eq!(alice_line.kind, SettlementKind::Reward);
        assert_eq!(alice_line.usdc_micros, 500);
    }

    #[test]
    fn same_peer_reward_and_slash_are_distinct_lines() {
        let schedule = SettlementSchedule::new(1);
        let intents = vec![
            intent(b"carol", SettlementKind::Reward, 10, 0),
            intent(b"carol", SettlementKind::Slash, 4, 1),
        ];
        let batch = SettlementBatch::from_intents(&intents, schedule);
        assert_eq!(batch.len(), 2, "reward and slash never net against each other");
        assert_eq!(batch.total_reward_micros, 10);
        assert_eq!(batch.total_slash_micros, 4);
    }

    #[test]
    fn batch_is_deterministic() {
        let schedule = SettlementSchedule::new(7);
        let intents = vec![
            intent(b"z", SettlementKind::Reward, 1, 0),
            intent(b"a", SettlementKind::Reward, 1, 0),
            intent(b"m", SettlementKind::Slash, 1, 0),
        ];
        let b1 = SettlementBatch::from_intents(&intents, schedule);
        let b2 = SettlementBatch::from_intents(&intents, schedule);
        assert_eq!(b1, b2, "same intents → byte-identical signable proposal");
    }
}
