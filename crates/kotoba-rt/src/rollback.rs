//! Deterministic rollback netcode engine (GGPO-style), ADR-2606060001.
//!
//! Invariant the whole thing rests on: `SimHost::step` is pure over
//! (state, inputs). So if we ever simulate a tick with a *predicted* input that
//! later turns out wrong, we can rewind to a fast save of the state at that tick
//! and re-simulate forward with the corrected input — and arrive at exactly the
//! state we would have reached had the input never been mispredicted.
//!
//! Bookkeeping:
//!   - `snapshots[t]`   = fast save of the state at the START of tick `t`
//!     (i.e. after simulating `t-1`). `snapshots[0]` = init.
//!   - `used[t]`        = the inputs (real or predicted) actually fed to tick t.
//!   - `received`       = every real input we have, per player, per tick.
//!   - `current`        = next tick to simulate; we have simulated `[0, current)`.
//!
//! Prediction = repeat the player's most recent received input at-or-before the
//! target tick (or `Input::default()` if none yet).

use std::collections::BTreeMap;
use std::collections::HashMap;
use std::collections::VecDeque;

use crate::protocol::{Input, PlayerId, Tick};
use crate::sim::SimHost;

/// How many ticks of fast saves we retain. A correction older than this cannot
/// be rolled back to (it is past the confirmed horizon) and is dropped.
pub const DEFAULT_MAX_ROLLBACK: u64 = 120;

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct RollbackStats {
    /// Number of times a late/corrected input forced a rewind + re-sim.
    pub rollbacks: u64,
    /// Total ticks re-simulated across all rollbacks.
    pub resimulated_ticks: u64,
    /// Corrections that arrived too old to roll back to (past the horizon).
    pub dropped_stale: u64,
}

/// A tick that has fallen past the rollback horizon and is therefore FINAL — no
/// future input can revise it. This is the unit the authority confirms to
/// clients: `state_hash` is the desync detector, `inputs` the canonical merged
/// inputs for replay. (ADR-2606060001: "Confirm = final, not provisional".)
#[derive(Clone, Debug, PartialEq)]
pub struct FinalTick {
    pub tick: Tick,
    pub state_hash: [u8; 32],
    pub inputs: Vec<(PlayerId, Input)>,
}

pub struct RollbackEngine<S: SimHost> {
    sim: S,
    /// Tick-stamped membership: `roster_events[t][p] = joined?`. The ACTIVE
    /// roster at any tick is the fold of all events at-or-before it. Membership
    /// flows through the same ordered, rollback-aware path as inputs, so every
    /// peer derives the same roster at every tick and replay reconstructs it.
    roster_events: BTreeMap<u64, BTreeMap<PlayerId, bool>>,
    current: Tick,
    max_rollback: u64,

    snapshots: BTreeMap<u64, Vec<u8>>,
    used: BTreeMap<u64, HashMap<PlayerId, Input>>,
    /// Post-state hash of each simulated tick `t` (state AFTER stepping `t`).
    hashes: BTreeMap<u64, [u8; 32]>,
    received: HashMap<PlayerId, BTreeMap<u64, Input>>,
    /// Ticks finalized (copied out) but not yet drained by the consumer. A tick
    /// here is immutable: it is below the rollback horizon, so no `add_input`
    /// can ever revise it again.
    pending_final: VecDeque<FinalTick>,
    /// Next tick to finalize (everything `< finalized_cursor` is already final).
    finalized_cursor: u64,
    stats: RollbackStats,
}

impl<S: SimHost> RollbackEngine<S> {
    /// `initial_roster` are the players present from tick 0 (recorded as join
    /// events at tick 0). Players may also join/leave later via
    /// [`add_roster_event`](Self::add_roster_event).
    pub fn new(mut sim: S, initial_roster: Vec<PlayerId>, seed: u64, config: &[u8]) -> Self {
        sim.init(seed, config);
        let mut snapshots = BTreeMap::new();
        snapshots.insert(0u64, sim.save_fast());
        let mut roster_events: BTreeMap<u64, BTreeMap<PlayerId, bool>> = BTreeMap::new();
        if !initial_roster.is_empty() {
            let tick0 = roster_events.entry(0).or_default();
            for p in initial_roster {
                tick0.insert(p, true);
            }
        }
        Self {
            sim,
            roster_events,
            current: Tick(0),
            max_rollback: DEFAULT_MAX_ROLLBACK,
            snapshots,
            used: BTreeMap::new(),
            hashes: BTreeMap::new(),
            received: HashMap::new(),
            pending_final: VecDeque::new(),
            finalized_cursor: 0,
            stats: RollbackStats::default(),
        }
    }

    /// The active roster at `tick`: fold every membership event at-or-before it
    /// (later events override earlier per player), sorted for determinism.
    pub fn active_roster(&self, tick: Tick) -> Vec<PlayerId> {
        use std::collections::BTreeSet;
        let mut set: BTreeSet<PlayerId> = BTreeSet::new();
        for (_t, evs) in self.roster_events.range(..=tick.0) {
            for (p, joined) in evs {
                if *joined {
                    set.insert(*p);
                } else {
                    set.remove(p);
                }
            }
        }
        set.into_iter().collect()
    }

    pub fn with_max_rollback(mut self, max_rollback: u64) -> Self {
        self.max_rollback = max_rollback.max(1);
        self
    }

    pub fn current_tick(&self) -> Tick {
        self.current
    }
    pub fn stats(&self) -> &RollbackStats {
        &self.stats
    }
    pub fn sim(&self) -> &S {
        &self.sim
    }
    pub fn state_hash(&mut self) -> [u8; 32] {
        self.sim.state_hash()
    }

    /// The inputs (real or predicted) actually fed to `tick`, sorted by player.
    /// Empty if `tick` was never simulated or has been trimmed past the horizon.
    pub fn used_inputs(&self, tick: Tick) -> Vec<(PlayerId, Input)> {
        let mut v: Vec<(PlayerId, Input)> = self
            .used
            .get(&tick.0)
            .map(|m| m.iter().map(|(p, i)| (*p, i.clone())).collect())
            .unwrap_or_default();
        v.sort_by_key(|(p, _)| *p);
        v
    }

    /// Durable, content-addressable snapshot of the *current* state for the
    /// cold lane (commit / replay / resync seed).
    pub fn durable_snapshot(&mut self) -> Vec<u8> {
        self.sim.snapshot_durable()
    }

    /// Predicted-or-real input for `(player, tick)`: the most recent received
    /// input at-or-before `tick`, else default.
    fn input_for(&self, player: PlayerId, tick: u64) -> Input {
        self.received
            .get(&player)
            .and_then(|m| m.range(..=tick).next_back())
            .map(|(_, v)| v.clone())
            .unwrap_or_default()
    }

    /// Build the sorted input set actually fed to `tick` — over the ACTIVE
    /// roster at that tick (deterministic across peers) — and remember it.
    fn assemble_inputs(&mut self, tick: u64) -> Vec<(PlayerId, Input)> {
        let ps = self.active_roster(Tick(tick)); // already sorted
        let mut map: HashMap<PlayerId, Input> = HashMap::with_capacity(ps.len());
        let mut sorted: Vec<(PlayerId, Input)> = Vec::with_capacity(ps.len());
        for p in ps {
            let inp = self.input_for(p, tick);
            map.insert(p, inp.clone());
            sorted.push((p, inp));
        }
        self.used.insert(tick, map);
        sorted
    }

    /// Simulate exactly one tick forward from `self.current`.
    fn step_one(&mut self) {
        let t = self.current.0;
        // State at the start of t must already be saved (post-step of t-1, or init).
        debug_assert!(self.snapshots.contains_key(&t));
        let inputs = self.assemble_inputs(t);
        self.sim.step(Tick(t), &inputs);
        self.current = Tick(t + 1);
        // Save state at the start of the next tick + record this tick's post-state
        // hash, then finalize anything that fell past the horizon, then trim.
        self.snapshots.insert(t + 1, self.sim.save_fast());
        self.hashes.insert(t, self.sim.state_hash());
        self.finalize_passed();
        self.trim_horizon();
    }

    /// Move ticks that have fallen strictly below the rollback horizon into the
    /// `pending_final` queue. Once below the horizon a tick can no longer be the
    /// target of `add_input` (its fast save is gone), so it is immutable —
    /// exactly the GGPO "confirmed frame". Done BEFORE `trim_horizon` so the
    /// finalized data is copied out before its maps are pruned.
    fn finalize_passed(&mut self) {
        let keep_from = self.current.0.saturating_sub(self.max_rollback);
        while self.finalized_cursor < keep_from {
            let t = self.finalized_cursor;
            if let Some(h) = self.hashes.get(&t).copied() {
                self.pending_final.push_back(FinalTick {
                    tick: Tick(t),
                    state_hash: h,
                    inputs: self.used_inputs(Tick(t)),
                });
            }
            self.finalized_cursor += 1;
        }
    }

    /// Drain ticks that are now FINAL (past the rollback horizon). The authority
    /// broadcasts these as the canonical Confirm/Bundle; clients use the hash as
    /// a desync detector and the inputs for replay.
    pub fn drain_finalized(&mut self) -> Vec<FinalTick> {
        self.pending_final.drain(..).collect()
    }

    /// Advance simulation up to (but not including) `target`.
    pub fn advance_to(&mut self, target: Tick) {
        while self.current.0 < target.0 {
            self.step_one();
        }
    }

    /// Advance by `n` ticks.
    pub fn advance(&mut self, n: u64) {
        let target = Tick(self.current.0 + n);
        self.advance_to(target);
    }

    /// Ingest a real input. If it corrects a tick we already simulated with a
    /// different (predicted) value, rewind to that tick and re-simulate forward.
    /// Returns true if a rollback occurred.
    pub fn add_input(&mut self, player: PlayerId, tick: Tick, input: Input) -> bool {
        let t = tick.0;
        // Record it (idempotent; last write wins for the same tick).
        self.received.entry(player).or_default().insert(t, input.clone());

        // Future or current tick: nothing simulated yet, no rollback needed.
        if t >= self.current.0 {
            return false;
        }

        // Did we feed a different value to tick t already?
        let mispredicted = self
            .used
            .get(&t)
            .and_then(|m| m.get(&player))
            .map(|prev| prev != &input)
            .unwrap_or(false);
        if !mispredicted {
            return false;
        }

        // Can we still roll back to t?
        if !self.snapshots.contains_key(&t) {
            // Correction is older than the retained horizon — unrecoverable here;
            // the caller should resync from a durable snapshot CID.
            self.stats.dropped_stale += 1;
            return false;
        }

        self.rewind_to(t);
        true
    }

    /// Ingest a tick-stamped membership change (join/leave). Like `add_input`, a
    /// change to an already-simulated tick rewinds + re-sims so the roster — and
    /// therefore which inputs are processed — is reconstructed deterministically.
    /// Returns true if a rollback occurred. Typically `tick` is in the future
    /// (a scheduled join), in which case no rollback is needed.
    pub fn add_roster_event(&mut self, player: PlayerId, tick: Tick, joined: bool) -> bool {
        let t = tick.0;
        // Dedup: ignore a no-op event (same membership already recorded at t).
        if self
            .roster_events
            .get(&t)
            .and_then(|m| m.get(&player))
            .map(|prev| *prev == joined)
            .unwrap_or(false)
        {
            return false;
        }
        self.roster_events.entry(t).or_default().insert(player, joined);

        // Future/current tick: affects only ticks not yet simulated.
        if t >= self.current.0 {
            return false;
        }
        // Past tick already simulated with a different roster → rollback if we can.
        if !self.snapshots.contains_key(&t) {
            self.stats.dropped_stale += 1;
            return false;
        }
        self.rewind_to(t);
        true
    }

    /// Restore the fast save at the start of tick `t`, then re-simulate forward
    /// to where we were. Re-simulation re-reads `received` + `roster_events`
    /// (now corrected). Shared by input and roster-event corrections.
    fn rewind_to(&mut self, t: u64) {
        let saved_current = self.current.0;
        let snap = self.snapshots.get(&t).cloned().expect("snapshot present");
        self.sim.restore_fast(&snap);
        self.current = Tick(t);
        // Drop stale used/snapshot/hash entries from t on; they get recomputed.
        // (Finalized ticks live below the horizon, hence below `t` here — the
        // `snapshots.contains_key(&t)` gate ensures it — so finality is never
        // revised by a rollback.)
        self.used.retain(|k, _| *k < t);
        self.snapshots.retain(|k, _| *k <= t);
        self.hashes.retain(|k, _| *k < t);

        self.advance_to(Tick(saved_current));

        self.stats.rollbacks += 1;
        self.stats.resimulated_ticks += saved_current - t;
    }

    /// Drop saves/used-inputs older than the rollback horizon to bound memory.
    fn trim_horizon(&mut self) {
        let keep_from = self.current.0.saturating_sub(self.max_rollback);
        if keep_from == 0 {
            return;
        }
        self.snapshots.retain(|k, _| *k >= keep_from);
        self.used.retain(|k, _| *k >= keep_from);
        // `finalize_passed` has already copied out everything below keep_from, so
        // pruning hashes to the same floor cannot drop an un-finalized tick.
        self.hashes.retain(|k, _| *k >= keep_from);
        // Received inputs older than the horizon can never trigger a rollback;
        // keep one straggler per player (for prediction continuity) by trimming
        // strictly below keep_from but leaving the floor entry.
        for m in self.received.values_mut() {
            let stale: Vec<u64> = m.range(..keep_from).map(|(k, _)| *k).collect();
            // keep the newest stale entry as the prediction floor.
            if stale.len() > 1 {
                for k in &stale[..stale.len() - 1] {
                    m.remove(k);
                }
            }
        }
    }
}
