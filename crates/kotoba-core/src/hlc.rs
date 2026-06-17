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
    /// did not (clock stalled or jumped back) the packed value increments — so the
    /// result is always strictly greater than `self`, and a counter that overflows
    /// its 16 bits carries cleanly into the physical part (monotonicity over
    /// pathological throughput beats a perfectly-shaped counter).
    pub fn send(self, wall_ms: u64) -> Hlc {
        let wall = wall_ms << COUNTER_BITS;
        if wall > self.0 {
            Hlc(wall)
        } else {
            Hlc(self.0 + 1)
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

/// Order HLC-stamped items into the cross-graph causal sequence (ADR-001 p1 /
/// GROWTH p11 firehose): ascending [`Hlc`], ties broken by `tiebreak` (e.g. the
/// event CID). The order is **total and deterministic** — every replica yields
/// the identical sequence regardless of the order events/streams arrived in.
pub fn causal_sort_by<T, K, FH, FK>(items: &mut [T], hlc_of: FH, tiebreak_of: FK)
where
    K: Ord,
    FH: Fn(&T) -> Hlc,
    FK: Fn(&T) -> K,
{
    items.sort_by(|a, b| {
        hlc_of(a)
            .cmp(&hlc_of(b))
            .then_with(|| tiebreak_of(a).cmp(&tiebreak_of(b)))
    });
}

/// Merge several per-graph event `streams` into one causally-ordered firehose,
/// deduping events that appear in more than one stream by their `tiebreak` key
/// (overlapping subscriptions must not emit an event twice). Result is the same
/// total causal order as [`causal_sort_by`]. Deterministic across stream order.
pub fn causal_merge_dedup<T, K, FH, FK>(
    streams: Vec<Vec<T>>,
    hlc_of: FH,
    tiebreak_of: FK,
) -> Vec<T>
where
    K: Ord + Clone,
    FH: Fn(&T) -> Hlc,
    FK: Fn(&T) -> K,
{
    let mut all: Vec<T> = streams.into_iter().flatten().collect();
    causal_sort_by(&mut all, &hlc_of, &tiebreak_of);
    // adjacent dedup by key (sort grouped equal keys together).
    let mut seen_prev: Option<K> = None;
    all.retain(|item| {
        let k = tiebreak_of(item);
        if seen_prev.as_ref() == Some(&k) {
            false
        } else {
            seen_prev = Some(k);
            true
        }
    });
    all
}

/// Resume a causal firehose from a `cursor`: keep only items strictly after it
/// (by [`Hlc`]) and return them in causal order (GROWTH p11 resumable
/// subscription). The cursor is the consumer's last-seen Hlc, so a reconnecting
/// subscriber gets exactly the unseen tail, deterministically — pass [`Hlc::ZERO`]
/// for a fresh subscription (the whole stream).
pub fn causal_after<T, K, FH, FK>(
    items: Vec<T>,
    cursor: Hlc,
    hlc_of: FH,
    tiebreak_of: FK,
) -> Vec<T>
where
    K: Ord,
    FH: Fn(&T) -> Hlc,
    FK: Fn(&T) -> K,
{
    let mut tail: Vec<T> = items.into_iter().filter(|i| hlc_of(i) > cursor).collect();
    causal_sort_by(&mut tail, &hlc_of, &tiebreak_of);
    tail
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

    // ── firehose causal ordering ──────────────────────────────────────────

    // (hlc, id) events; id doubles as the tiebreak / dedup key.
    fn ev(phys: u64, ctr: u64, id: &str) -> (Hlc, String) {
        (Hlc::new(phys, ctr), id.to_string())
    }

    fn order(items: &[(Hlc, String)]) -> Vec<String> {
        let mut v = items.to_vec();
        causal_sort_by(&mut v, |e| e.0, |e| e.1.clone());
        v.into_iter().map(|e| e.1).collect()
    }

    #[test]
    fn causal_sort_is_deterministic_across_input_order() {
        let a = vec![ev(10, 0, "a"), ev(20, 0, "b"), ev(10, 1, "c")];
        let mut b = a.clone();
        b.reverse();
        // both permutations → identical causal sequence (by hlc, then id).
        assert_eq!(order(&a), vec!["a", "c", "b"]);
        assert_eq!(order(&b), vec!["a", "c", "b"]);
    }

    #[test]
    fn causal_sort_breaks_ties_by_tiebreak() {
        // same hlc, different ids → ordered by id deterministically.
        let items = vec![ev(5, 0, "z"), ev(5, 0, "a"), ev(5, 0, "m")];
        assert_eq!(order(&items), vec!["a", "m", "z"]);
    }

    #[test]
    fn merge_dedup_interleaves_streams_and_drops_duplicates() {
        // two graph streams, each HLC-ordered, sharing one event ("b").
        let g1 = vec![ev(10, 0, "a"), ev(30, 0, "b")];
        let g2 = vec![ev(20, 0, "c"), ev(30, 0, "b")];
        let merged = causal_merge_dedup(vec![g1, g2], |e| e.0, |e| e.1.clone());
        let ids: Vec<String> = merged.into_iter().map(|e| e.1).collect();
        assert_eq!(ids, vec!["a", "c", "b"], "interleaved by hlc, 'b' deduped");
    }

    #[test]
    fn causal_after_returns_only_the_unseen_tail_in_order() {
        let events = vec![ev(10, 0, "a"), ev(20, 0, "b"), ev(10, 1, "c"), ev(30, 0, "d")];
        let ids = |v: Vec<(Hlc, String)>| v.into_iter().map(|e| e.1).collect::<Vec<_>>();
        // cursor at the "c" event (hlc 10/1): only strictly-later events, ordered.
        let cursor = Hlc::new(10, 1);
        assert_eq!(ids(causal_after(events.clone(), cursor, |e| e.0, |e| e.1.clone())), vec!["b", "d"]);
        // ZERO cursor → whole stream, causally ordered.
        assert_eq!(
            ids(causal_after(events.clone(), Hlc::ZERO, |e| e.0, |e| e.1.clone())),
            vec!["a", "c", "b", "d"]
        );
        // cursor past the end → empty (caller is fully caught up).
        assert!(causal_after(events, Hlc::new(99, 0), |e| e.0, |e| e.1.clone()).is_empty());
    }

    #[test]
    fn merge_dedup_is_order_independent() {
        let g1 = vec![ev(10, 0, "a"), ev(30, 0, "b")];
        let g2 = vec![ev(20, 0, "c")];
        let m1 = causal_merge_dedup(vec![g1.clone(), g2.clone()], |e| e.0, |e| e.1.clone());
        let m2 = causal_merge_dedup(vec![g2, g1], |e| e.0, |e| e.1.clone());
        let ids = |m: Vec<(Hlc, String)>| m.into_iter().map(|e| e.1).collect::<Vec<_>>();
        assert_eq!(ids(m1), ids(m2), "stream order does not change the firehose");
    }

    #[test]
    fn send_is_strictly_monotonic_over_any_wall_sequence() {
        // Thread one clock through an adversarial wall-time sequence (forward
        // jumps, stalls, and backward jumps) — every stamp must strictly exceed
        // the previous, the property the whole causal ordering rests on.
        let walls = [100u64, 100, 50, 100, 100, 200, 0, 200, 201, 1, 201, 5_000, 5_000];
        let mut clk = Hlc::ZERO;
        for w in walls {
            let next = clk.send(w);
            assert!(next > clk, "send not strictly monotonic at wall={w}: {clk:?} -> {next:?}");
            clk = next;
        }
    }

    #[test]
    fn recv_always_dominates_both_inputs() {
        // The HLC receive rule must produce a clock strictly greater than both the
        // local and the remote it merged, with physical >= max of the three
        // inputs. Sweep the combination space deterministically.
        for lp in [0u64, 5, 10] {
            for lc in [0u64, 1, 7] {
                for rp in [0u64, 5, 10] {
                    for rc in [0u64, 1, 7] {
                        for w in [0u64, 5, 10] {
                            let local = Hlc::new(lp, lc);
                            let remote = Hlc::new(rp, rc);
                            let m = local.recv(remote, w);
                            assert!(m > local, "recv !> local: {local:?} {remote:?} w={w} -> {m:?}");
                            assert!(m > remote, "recv !> remote: {local:?} {remote:?} w={w} -> {m:?}");
                            assert!(
                                m.phys_ms() >= lp.max(rp).max(w),
                                "recv physical below max input"
                            );
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn causal_sort_is_total_and_permutation_invariant() {
        // Any permutation of the same event set sorts to the identical sequence
        // (deterministic total order across replicas). Sweep several rotations.
        let base = vec![
            ev(10, 0, "a"), ev(10, 1, "b"), ev(20, 0, "c"),
            ev(5, 3, "d"), ev(20, 0, "c"), ev(7, 0, "e"),
        ];
        let canonical = order(&base);
        for rot in 0..base.len() {
            let mut perm = base.clone();
            perm.rotate_left(rot);
            assert_eq!(order(&perm), canonical, "rotation {rot} changed the order");
        }
        // canonical order is non-decreasing by (hlc, id).
        let keys: Vec<(Hlc, String)> = {
            let mut v = base.clone();
            causal_sort_by(&mut v, |e| e.0, |e| e.1.clone());
            v
        };
        for w in keys.windows(2) {
            assert!(
                (w[0].0, &w[0].1) <= (w[1].0, &w[1].1),
                "not sorted by (hlc, id)"
            );
        }
    }

    #[test]
    fn hlc_serializes_transparently_as_u64() {
        // Hlc is persisted in commits (the `hlc: u64` field). Its serde MUST be
        // wire-compatible with a bare u64 so the newtype never breaks the commit
        // format. Verify (format-agnostic, via dag-cbor) that an Hlc encodes to
        // the SAME bytes as its inner u64, a raw u64 decodes into an Hlc, and the
        // Hlc round-trips.
        let h = Hlc::new(1_700_000_000_000, 7);
        let hlc_bytes = serde_ipld_dagcbor::to_vec(&h).unwrap();
        let u64_bytes = serde_ipld_dagcbor::to_vec(&h.0).unwrap();
        assert_eq!(hlc_bytes, u64_bytes, "Hlc must encode identically to a bare u64");
        // a raw u64 decodes straight into an Hlc.
        let from_u64: Hlc = serde_ipld_dagcbor::from_slice(&u64_bytes).unwrap();
        assert_eq!(from_u64, h);
        // and the Hlc round-trips.
        let back: Hlc = serde_ipld_dagcbor::from_slice(&hlc_bytes).unwrap();
        assert_eq!(back, h);
    }

    #[test]
    fn zero_is_the_minimum() {
        assert_eq!(Hlc::ZERO, Hlc::new(0, 0));
        assert!(Hlc::ZERO < Hlc::new(1, 0));
        assert!(Hlc::ZERO.send(0) > Hlc::ZERO, "send always advances");
    }
}
