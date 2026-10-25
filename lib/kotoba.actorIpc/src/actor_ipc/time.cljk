(ns actor-ipc.time
  "Fixed-timestep game loop timing. Restored from the legacy kami-engine/kami-core
  Rust crate's `src/time.rs` (43 lines), deleted in kotoba-lang/kami-engine PR #82
  \"Remove Rust workspace from kami-engine\", as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  The original Rust `GameClock` was a mutable struct (`&mut self` methods that
  mutate `tick` / `accumulator_ns` in place). CLJC favors immutable data + pure
  functions, so `GameClock` is represented as a plain map and `advance` returns
  a new clock map (paired with the tick count produced) rather than mutating in
  place — callers thread the returned clock through their own loop state.")

(def ns-per-second
  "Nanoseconds per second, used to derive tick-duration-ns from tick-rate."
  1000000000)

(defn make-clock
  "Construct a new GameClock. `tick-rate` is ticks per second (e.g. 60).
  Mirrors Rust `GameClock::new(tick_rate: u32) -> Self`."
  [tick-rate]
  {:tick 0
   :tick-rate tick-rate
   :tick-duration-ns (quot ns-per-second tick-rate)
   :accumulator-ns 0})

(defn advance
  "Feed elapsed nanoseconds into the clock. Returns a map
  `{:clock <new-clock> :ticks <ticks-to-simulate>}`.
  Mirrors Rust `GameClock::advance(&mut self, elapsed_ns: u64) -> u32`, adapted to
  return the updated clock instead of mutating in place. Tick counter wraps at
  2^32 to match the original `u32` `wrapping_add`."
  [clock elapsed-ns]
  (let [acc (+ (:accumulator-ns clock) elapsed-ns)
        dur (:tick-duration-ns clock)
        ticks (quot acc dur)
        acc' (mod acc dur)
        tick' (mod (+ (:tick clock) ticks) 4294967296)]
    {:clock (assoc clock :accumulator-ns acc' :tick tick')
     :ticks ticks}))

(defn clock-tick
  "Current tick counter. Mirrors Rust `GameClock::tick(&self) -> Tick`."
  [clock]
  (:tick clock))

(defn clock-tick-rate
  "Configured tick rate (ticks per second). Mirrors Rust
  `GameClock::tick_rate(&self) -> u32`."
  [clock]
  (:tick-rate clock))

(defn alpha
  "Interpolation alpha for rendering between ticks (0.0 .. 1.0). Mirrors Rust
  `GameClock::alpha(&self) -> f32`."
  [clock]
  (double (/ (:accumulator-ns clock) (:tick-duration-ns clock))))
