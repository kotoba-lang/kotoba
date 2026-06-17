//! # Hybrid Logical Clock (ADR-001 — causal ordering / GROWTH p11 firehose)
//!
//! A [`Hlc`] is a `u64` that packs a 48-bit physical millisecond timestamp with a
//! 16-bit logical counter (`phys_ms << 16 | counter`). It orders events causally
//! while staying close to wall-clock time, and it is monotonic even when the wall
//! clock jumps backwards — which is what makes it a safe cross-graph ordering key
//! and the deterministic merge tiebreak for the Merkle-CRDT (ADR-001).
//!
//! Two operations, the classic HLC algorithm, as **pure functions** (no global
//! state — the caller threads the previous clock value, so this is testable and
//! reusable across the single-node process clock and multi-node peer merges):
//! - [`Hlc::send`] — stamp a local event given the previous clock + wall time.
//! - [`Hlc::recv`] — merge an observed remote `Hlc` into the local clock (the
//!   receive event; the "merge observed peer HLCs" step ADR-001 deferred).

use serde::{Deserialize, Serialize};

/// Bits reserved for the logical counter; the rest hold physical milliseconds.
const COUNTER_BITS: u32 = 16;
const COUNTER_MASK: u64 = (1 << COUNTER_BITS) - 1;

/// A hybrid logical clock value: `phys_ms << 16 | counter`. Natural `u64` order
/// is causal order (and the merge tiebreak).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Hlc(pub u64);

impl Hlc {
    /// The zero clock (pre-HLC commits decode to this).
    pub const ZERO: Hlc = Hlc(0);

    /// Build from a physical-ms timestamp and a counter (counter saturates into
    /// its 16 bits — a caller that overflows the counter has bigger problems, and
    /// the next physical tick resets it).
    pub fn new(phys_ms: u64, counter: u64) -> Self {
        Hlc((phys_ms << COUNTER_BITS) | (counter & COUNTER_MASK))
    }

    /// The physical-millisecond component.
    pub fn phys_ms(self) -> u64 {
        self.0 >> COUNTER_BITS
    }

    /// The logical-counter component.
    pub fn counter(self) -> u64 {
        self.0 & COUNTER_MASK
    }

    /// Stamp a local event: advance past both the previous clock and `wall_ms`.
    /// If wall time moved the physical part forward the counter resets to 0; if it
    /// did not (clock stalled or jumped back) the counter increments — so the
    /// result is always strictly greater than `self`.
    pub fn send(self, wall_ms: u64) -> Hlc {
        let wall = Hlc::new(wall_ms, 0);
        if wall.phys_ms() > self.phys_ms() {
            wall
        } else {
            Hlc::new(self.phys_ms(), self.counter() + 1)
        }
    }

    /// Merge an observed remote clock on receipt (the classic HLC receive rule):
    /// take the max physical part across local, remote, and `wall_ms`, then pick
    /// the counter so the result strictly dominates whichever inputs share that
    /// physical part. Guarantees `recv > self` and `recv > remote`.
    pub fn recv(self, remote: Hlc, wall_ms: u64) -> Hlc {
        let l = self.phys_ms();
        let m = remote.phys_ms();
        let p = l.max(m).max(wall_ms);
        let counter = if p == l && p == m {
            self.counter().max(remote.counter()) + 1
        } else if p == l {
            self.counter() + 1
        } else if p == m {
            remote.counter() + 1
        } else {
            0
        };
        Hlc::new(p, counter)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pack_unpack_roundtrips() {
        let h = Hlc::new(1_700_000_000_000, 42);
        assert_eq!(h.phys_ms(), 1_700_000_000_000);
        assert_eq!(h.counter(), 42);
        // counter is masked to 16 bits.
        assert_eq!(Hlc::new(5, 0x1_0000).counter(), 0, "counter wraps at 16 bits");
    }

    #[test]
    fn order_is_causal_then_counter() {
        // higher physical wins regardless of counter; equal physical → counter.
        assert!(Hlc::new(10, 0) < Hlc::new(11, 0));
        assert!(Hlc::new(10, 5) < Hlc::new(11, 0));
        assert!(Hlc::new(10, 1) < Hlc::new(10, 2));
    }

    #[test]
    fn send_is_strictly_monotonic_even_when_wall_goes_back() {
        let h = Hlc::new(100, 3);
        // wall advanced → adopt wall, counter resets.
        let fwd = h.send(200);
        assert_eq!(fwd, Hlc::new(200, 0));
        assert!(fwd > h);
        // wall stalled at same ms → counter increments.
        let same = h.send(100);
        assert_eq!(same, Hlc::new(100, 4));
        assert!(same > h);
        // wall jumped BACK → still strictly greater (counter increments).
        let back = h.send(50);
        assert_eq!(back, Hlc::new(100, 4));
        assert!(back > h);
    }

    #[test]
    fn recv_dominates_both_local_and_remote() {
        let local = Hlc::new(100, 2);
        let remote = Hlc::new(100, 5);
        // equal physical on both, wall behind → counter = max(2,5)+1.
        let merged = local.recv(remote, 90);
        assert_eq!(merged, Hlc::new(100, 6));
        assert!(merged > local && merged > remote);

        // remote ahead in physical → adopt remote phys, counter = remote+1.
        let remote_ahead = Hlc::new(200, 1);
        let m2 = local.recv(remote_ahead, 100);
        assert_eq!(m2, Hlc::new(200, 2));
        assert!(m2 > local && m2 > remote_ahead);

        // wall ahead of both → adopt wall, counter resets to 0.
        let m3 = local.recv(remote, 300);
        assert_eq!(m3, Hlc::new(300, 0));
        assert!(m3 > local && m3 > remote);
    }

    #[test]
    fn recv_is_convergent_under_exchange() {
        // two nodes exchanging clocks both advance past each other's last value.
        let a0 = Hlc::new(100, 0);
        let b0 = Hlc::new(150, 0);
        let a1 = a0.recv(b0, 100); // a sees b
        let b1 = b0.recv(a0, 150); // b sees a
        assert!(a1 > b0, "a moved past b's observed clock");
        assert!(b1 >= a0, "b stayed ahead of a's observed clock");
    }

    #[test]
    fn zero_is_the_minimum() {
        assert_eq!(Hlc::ZERO, Hlc::new(0, 0));
        assert!(Hlc::ZERO < Hlc::new(1, 0));
        assert!(Hlc::ZERO.send(0) > Hlc::ZERO, "send always advances");
    }
}
