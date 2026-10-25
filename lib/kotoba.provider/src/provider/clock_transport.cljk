(ns provider.clock-transport
  "Production wall/monotonic clock sources for the typed clock capability kit
  (ADR 0029, `provider.clock`). See
  docs/adr/0073-production-clock-transport-real-wall-and-monotonic-sources.md
  for the full design rationale; this docstring is the summary.

  This namespace does NOT define a new provider or a new capability, and
  does NOT change any bound `clock.cljc` enforces -- non-negative-whole-
  number validation on both domains, monotonic-regression detection,
  provider-local observation sequencing, redacted typed errors for a
  throwing source -- all unchanged and un-weakened. This namespace only
  supplies the two zero-argument `(fn [] tick)` source functions
  `provider.clock/provider` has always accepted as its
  `{:wall-now ... :monotonic-now ...}` constructor map. It DOES, however,
  ship alongside one narrow, non-weakening portability fix TO `clock.cljc`
  itself (`valid-tick?`'s `:cljs` branch, and the provider-local
  observation-sequence counter) -- see docs/adr/0073 'The `:cljs` fix to
  `clock.cljc` itself' for why a transport alone could not have worked
  around a pre-existing defect in the reference provider's own `:cljs`
  i64 handling.

  ## Why this is much smaller than ADR 0064/0066/0071's LLM/HTTP/storage
  ## transports

  Every one of those three capabilities needs a HOST-chosen network
  destination (a fleet endpoint, a guest-named URL bounded by an
  allow-list, a configured KV backend) -- real ambient authority the
  compiler process does not have on its own, which is exactly why
  `llm.cljc`/`http.cljc`/`storage.cljc` all take a `:transport` seam in the
  first place. `clock-v1.edn` is different on both axes that matter here:
  `:source-authority :host` names the HOST's own process clock as the
  source (not a third party over the network), and `:ambient-clock false`
  says only what it has always said -- the COMPILER itself must never bake
  in a call to a time API; only a host-constructed provider may read one.
  Reading the process's own already-running wall/monotonic clock is not a
  new authority a host must be configured to grant; every host this repo
  targets already has one, synchronously, for free. So there is no
  endpoint, allow-list, credential, or wire protocol to design here -- just
  two zero-argument reads.

  ## `:cljs` gets a REAL implementation too, unlike its LLM/HTTP/storage
  ## siblings

  ADR 0064/0066/0071 each leave `:cljs` an explicit, documented gap for the
  same reason: every reference provider's `:transport` contract in this
  repo is a plain synchronous `(fn [request] -> reply)`
  (`kotoba.compiler.reference-runtime` has no promise/callback machinery a
  provider could return through), and nbb/Node's `fetch` is Promise-based --
  faking synchrony over a genuinely asynchronous network call is a
  separate, larger, independently-reviewable design decision none of those
  ADRs make unilaterally on cljs's behalf. Reading a clock has no such
  asynchrony to fake: `js/Date.now` and `js/performance.now` (available
  globally on every `:cljs` host this repo targets -- both Node/nbb, per
  Node's Performance Timing API being global since Node 16, and the
  browser, per the W3C High Resolution Time spec) are exactly as
  synchronous as `System/currentTimeMillis`/`System/nanoTime` are on the
  JVM. So both hosts get a genuine, non-stub implementation below."
  )

;; -----------------------------------------------------------------------
;; :clj -- java.lang.System wall/monotonic sources
;; -----------------------------------------------------------------------

#?(:clj
   (defn- clj-monotonic-source
     "Builds a monotonic nanosecond source anchored to a single
     `System/nanoTime` reading taken once, here, at construction time.

     `System/nanoTime`'s own Javadoc is explicit that its return value is
     'nanoseconds since some fixed but arbitrary origin time (perhaps in
     the future, so values may be negative)' -- i.e. the JVM gives no
     guarantee the raw value itself is non-negative, only that DIFFERENCES
     between two readings taken in the same JVM instance are meaningful.
     `clock.cljc`'s own `valid-tick?` requires a non-negative integer, so
     this namespace anchors every subsequent reading to the very first one:
     `(- (System/nanoTime) origin)`. This is a constant per-provider-
     instance offset, so it changes nothing about ORDERING or regression
     detection -- if the underlying raw source ever genuinely regresses,
     the anchored sequence regresses by exactly the same amount, and
     `clock.cljc`'s own `:clock/regressed` check (not this namespace) still
     catches it, exactly as it would for a raw un-anchored source. The only
     effect of anchoring is that the FIRST observation reads as (very close
     to) zero and every real-world observation after it is guaranteed
     non-negative by construction, instead of merely 'non-negative in
     practice on every JDK/platform combination this was tested on' -- see
     docs/adr/0073 'Remaining gaps' for the one rare edge case this
     trade-off accepts (a regression below the anchor's own first reading
     would surface as `:clock/invalid` rather than `:clock/regressed`)."
     []
     (let [origin (System/nanoTime)]
       (fn [] (- (System/nanoTime) origin)))))

#?(:clj
   (defn production-clock-source
     "Builds `{:wall-now (fn [] ...) :monotonic-now (fn [] ...)}`, ready to
     spread directly into `provider.clock/provider`:

       (clock/provider (clock-transport/production-clock-source))

     Wall time is `System/currentTimeMillis` verbatim -- already Unix
     milliseconds, matching `clock-v1.edn`'s `:wall {:unit
     :unix-milliseconds}` exactly, no conversion needed. Monotonic time is
     `clj-monotonic-source` (see its own docstring for the anchoring
     rationale). Neither reads anything beyond the JVM's own process clock;
     there is no host configuration to accept, unlike ADR 0064/0066/0071's
     LLM/HTTP/storage transports, which is why this constructor takes no
     options."
     []
     {:wall-now (fn [] (System/currentTimeMillis))
      :monotonic-now (clj-monotonic-source)}))

;; -----------------------------------------------------------------------
;; :cljs -- js/Date.now and js/performance.now sources
;; -----------------------------------------------------------------------

#?(:cljs
   (defn- cljs-monotonic-source
     "`js/performance.now()` returns fractional milliseconds relative to a
     fixed `timeOrigin` the host establishes once (process start under
     Node/nbb, navigation start in a browser) -- unlike
     `System/nanoTime`'s explicitly-arbitrary-and-possibly-negative origin,
     the W3C High Resolution Time spec guarantees this value is always
     non-negative AND monotonically non-decreasing by construction (it was
     designed specifically to replace `Date.now()` for interval
     measurement because wall time can jump backward on NTP adjustment).
     So, unlike the `:clj` source above, no anchoring is needed here for
     non-negativity -- the raw value already satisfies it, and (unlike the
     `:clj` anchor) its magnitude is NOT promised to start near zero -- it
     is relative to the host's own process/page start, which may already be
     well underway by the time a provider is constructed.

     Converted to nanoseconds (`* 1e6`), rounded to the nearest integer
     (`js/Math.round`) to match `clock-v1.edn`'s `:monotonic {:unit
     :nanoseconds}`, and finally coerced to `js/BigInt` -- REQUIRED, not
     cosmetic: `clock.cljc`'s own `valid-tick?` on `:cljs` checks
     `i64/bigint-value?`, because a plain cljs number is not the canonical
     i64 representation the ABI boundary requires for a `typed-cap-call`
     result crossing back into a compiled `.kotoba` guest (see
     docs/adr/0073 for the live repro that discovered this and the matching
     `clock.cljc` fix this ADR includes). Both a positive multiplication
     and `Math.round` are monotonically non-decreasing functions of their
     input, and `js/BigInt` of an already-whole number is an exact,
     lossless conversion, so composing them with an already-monotonic-
     non-decreasing source cannot itself introduce a spurious regression.
     See docs/adr/0073 'Remaining gaps' for the precision caveat this
     conversion accepts (the underlying clock's real resolution is coarser
     than one nanosecond; multiplying by 1e6 does not manufacture
     nanosecond-accurate measurement, only a nanosecond-UNIT integer) and
     the double-precision caveat in the multiplication step itself (the
     `js/Math.round (* ... 1e6)` arithmetic happens in IEEE-754 double
     precision BEFORE the `BigInt` conversion, so it is bounded by the same
     `Number.MAX_SAFE_INTEGER`-after-~104-days-of-uptime limit as an
     un-anchored plain-number nanosecond clock would be, even though the
     RESULT is a bigint)."
     []
     (fn [] (js/BigInt (js/Math.round (* (.now js/performance) 1e6))))))

#?(:cljs
   (defn production-clock-source
     "Builds `{:wall-now (fn [] ...) :monotonic-now (fn [] ...)}`, ready to
     spread directly into `provider.clock/provider` on a
     `:cljs` (nbb or browser) host -- see the `:clj` sibling above for the
     symmetric JVM version and the ns docstring for why `:cljs` gets a real
     implementation here, unlike ADR 0064/0066/0071's LLM/HTTP/storage
     transports.

     Wall time is `js/Date.now` coerced through `js/BigInt` (see
     `cljs-monotonic-source`'s docstring for why: `clock.cljc`'s `:cljs`
     `valid-tick?` requires the canonical i64 `bigint` representation, not
     a plain cljs number) -- `js/Date.now()` is already a whole number of
     Unix milliseconds, so the `BigInt` coercion is exact and lossless.
     Monotonic time is `cljs-monotonic-source` (see its own docstring).
     Takes no options, for the same reason as the `:clj` constructor: there
     is no host configuration for a local clock read."
     []
     {:wall-now (fn [] (js/BigInt (js/Date.now)))
      :monotonic-now (cljs-monotonic-source)}))
