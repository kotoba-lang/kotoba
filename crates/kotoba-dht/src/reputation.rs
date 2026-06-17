//! # Reputation weighting (ADR-002 — stake-to-replicate, phase 5)
//!
//! The third ledger of the membrane: **reputation ranks, it never admits.**
//! Admission is decided upstream by bond alone ([`crate::membrane::bonded_candidates`]
//! over [`kotoba_query::social::eligible_replica`]); reputation only reorders the
//! already-eligible set and scales the retainer *flow*. This keeps the
//! SOCIAL-CAPITAL-LEDGER invariants intact — reputation is non-transferable,
//! decaying, and here it can change *who is preferred* and *how fast they earn*,
//! but never *who is allowed in* and never a stored balance.
//!
//! Two surfaces, both Council-bounded:
//! - [`EarnRateBand`] — the retainer earn-rate multiplier band (a flow knob).
//! - [`prefer_by_reputation`] — placement preference for an oversubscribed pool.

use crate::node_id::NodeId;

/// Council-bounded multiplier band for the retainer earn-rate (ADR-002 §3).
/// Reputation scales the reward *flow* within `[min_bps, max_bps]` (basis points;
/// `10_000` = ×1.0). The floor guarantees a bonded replica still earns at zero
/// reputation — this is a flow adjustment, never a gate and never a transfer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EarnRateBand {
    pub min_bps: u32,
    pub max_bps: u32,
}

impl EarnRateBand {
    /// A band; a reversed `(min > max)` pair is normalised, not rejected, so the
    /// invariant `min_bps <= max_bps` always holds.
    pub fn new(min_bps: u32, max_bps: u32) -> Self {
        if min_bps <= max_bps {
            Self { min_bps, max_bps }
        } else {
            Self { min_bps: max_bps, max_bps: min_bps }
        }
    }

    /// The identity band (always ×1.0) — reputation weighting off.
    pub fn identity() -> Self {
        Self { min_bps: 10_000, max_bps: 10_000 }
    }

    /// Multiplier in bps for a reputation fraction `r ∈ [0,1]` (clamped): linear
    /// interpolation across the band. `r = 0 → min_bps`, `r = 1 → max_bps`.
    pub fn multiplier_bps(&self, rep_fraction: f64) -> u32 {
        let r = if rep_fraction.is_nan() { 0.0 } else { rep_fraction.clamp(0.0, 1.0) };
        let span = (self.max_bps - self.min_bps) as f64;
        self.min_bps + (span * r).round() as u32
    }

    /// Scale reward `units` by the reputation multiplier, saturating. With the
    /// default band floor > 0, a bonded replica always earns something — low
    /// reputation slows the flow, it does not stop it.
    pub fn scale_units(&self, units: u64, rep_fraction: f64) -> u64 {
        let bps = self.multiplier_bps(rep_fraction) as u128;
        let scaled = (units as u128).saturating_mul(bps) / 10_000;
        scaled.min(u64::MAX as u128) as u64
    }
}

/// Placement preference for an oversubscribed pool (ADR-002 §3): order an
/// **already-eligible** candidate set by reputation (highest first) and take at
/// most `k`. Higher-reputation cells are preferred for better expected liveness.
///
/// This reorders/selects *within* the eligible set and can never admit a node
/// that was not already eligible — admission is bond-only, decided upstream. The
/// sort is **stable**, so equal-reputation candidates keep their input order: feed
/// an XOR-sorted eligible set and proximity remains the tie-breaker.
pub fn prefer_by_reputation(eligible: &[(NodeId, u64)], k: usize) -> Vec<NodeId> {
    let mut ranked: Vec<&(NodeId, u64)> = eligible.iter().collect();
    ranked.sort_by(|a, b| b.1.cmp(&a.1)); // stable; reputation descending
    ranked.into_iter().take(k).map(|(n, _)| n.clone()).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn nid(tag: &[u8]) -> NodeId {
        NodeId::from_pubkey(tag)
    }

    #[test]
    fn band_normalises_reversed_bounds() {
        assert_eq!(EarnRateBand::new(20_000, 5_000), EarnRateBand::new(5_000, 20_000));
    }

    #[test]
    fn multiplier_interpolates_and_clamps() {
        let band = EarnRateBand::new(5_000, 20_000); // 0.5x .. 2.0x
        assert_eq!(band.multiplier_bps(0.0), 5_000);
        assert_eq!(band.multiplier_bps(1.0), 20_000);
        assert_eq!(band.multiplier_bps(0.5), 12_500);
        // out-of-range and NaN clamp into the band, never outside it.
        assert_eq!(band.multiplier_bps(-1.0), 5_000);
        assert_eq!(band.multiplier_bps(2.0), 20_000);
        assert_eq!(band.multiplier_bps(f64::NAN), 5_000);
    }

    #[test]
    fn scale_units_floor_still_earns_and_saturates() {
        let band = EarnRateBand::new(5_000, 20_000);
        // zero reputation still earns the floor (0.5x), never zero.
        assert_eq!(band.scale_units(100, 0.0), 50);
        assert_eq!(band.scale_units(100, 1.0), 200);
        assert_eq!(band.scale_units(100, 0.5), 125);
        // saturating, no overflow panic on adversarial units.
        assert_eq!(band.scale_units(u64::MAX, 1.0), u64::MAX);
    }

    #[test]
    fn identity_band_is_always_unit() {
        let band = EarnRateBand::identity();
        assert_eq!(band.scale_units(777, 0.0), 777);
        assert_eq!(band.scale_units(777, 1.0), 777);
    }

    #[test]
    fn prefer_orders_by_reputation_desc_and_caps_k() {
        let pool = vec![
            (nid(b"low"), 10u64),
            (nid(b"high"), 100),
            (nid(b"mid"), 50),
        ];
        let got = prefer_by_reputation(&pool, 2);
        assert_eq!(got, vec![nid(b"high"), nid(b"mid")]);
    }

    #[test]
    fn prefer_is_stable_on_ties_keeping_proximity_order() {
        // Equal reputation ⇒ input order preserved (input is XOR-sorted upstream,
        // so proximity stays the tie-breaker).
        let pool = vec![(nid(b"near"), 7u64), (nid(b"far"), 7)];
        assert_eq!(prefer_by_reputation(&pool, 2), vec![nid(b"near"), nid(b"far")]);
    }

    #[test]
    fn reputation_never_admits_a_non_eligible_node() {
        // Property: whatever reputations we assign, the preferred set is always a
        // subset of the eligible input — reputation reorders, never invents. And
        // with k ≥ len it returns exactly the same membership.
        let eligible: Vec<NodeId> = (0..8u8).map(|i| nid(&[i; 3])).collect();
        let eset: std::collections::HashSet<&NodeId> = eligible.iter().collect();
        for seed in 0..16u64 {
            // deterministic pseudo-reputations from the seed (no RNG in scripts).
            let pool: Vec<(NodeId, u64)> = eligible
                .iter()
                .enumerate()
                .map(|(i, n)| (n.clone(), (seed.wrapping_mul(31).wrapping_add(i as u64)) % 97))
                .collect();
            let preferred = prefer_by_reputation(&pool, 8);
            // never invents a node...
            for n in &preferred {
                assert!(eset.contains(n), "reputation admitted a non-eligible node");
            }
            // ...and at k ≥ len the membership is exactly the eligible set.
            let pset: std::collections::HashSet<&NodeId> = preferred.iter().collect();
            assert_eq!(pset, eset, "reputation changed admission membership");
        }
    }
}
