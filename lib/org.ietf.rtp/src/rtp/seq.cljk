(ns rtp.seq
  "The 16-bit sequence-number bookkeeping and jitter estimator from RFC 3550
  Appendix A — 'Algorithms for RTP header validation and jitter estimation',
  §A.1 (`update_seq`) and §A.8 (jitter). Rewritten here as pure functions of
  `(state, input) -> state` instead of the RFC's C struct-mutation, so a
  jitter buffer written in any host (JVM, browser, nbb) can drive the same
  arithmetic without a mutable `source` struct sitting behind it.

  The classic wrong way to compare two RTP sequence numbers is
  `(> seq-b seq-a)` — plain integer comparison. It is right 65535/65536 of
  the time and silently wrong exactly at the wraparound this whole module
  exists to handle, which is the worst possible failure mode: a bug that
  only shows up after ~18 minutes of an 8 kHz stream (65536 packets) or
  ~36 minutes at 30 fps video, long after the code that introduced it has
  shipped."
  )

(def ^:const seq-mod
  "RFC 3550 Appendix A.1's RTP_SEQ_MOD: sequence numbers are 16-bit and
  wrap modulo 2^16."
  0x10000)

(def ^:const max-dropout
  "Appendix A.1: an unsigned forward delta this large or more is treated as
  a probable source restart, not 3000+ packets of genuine loss."
  3000)

(def ^:const max-misorder
  "Appendix A.1: how far backward a sequence number may jump and still be
  accepted as reordering rather than flagged as a bad/duplicate packet."
  100)

(def ^:const min-sequential
  "Appendix A.1: number of consecutive in-order packets required before a
  new source (or one that just triggered probation) is trusted."
  2)

(defn- u16 [n] (bit-and n 0xFFFF))

(defn seq-delta
  "The unsigned 16-bit wraparound delta `seq - prev`, i.e. how far forward
  (with wrap) `seq` is from `prev`. This is `udelta` in Appendix A.1's
  `update_seq` — always in `[0, 65535]`, so `1` and `65535` both mean
  'one step', just in opposite directions; distinguishing them is what the
  rest of the module is for."
  [prev seq]
  (u16 (- seq prev)))

(defn seq-more-recent?
  "True when `seq-b` is later than `seq-a` in R-T-P's circular sequence
  space, using the RFC 1982-style rule: `b` is 'more recent' than `a` when
  the unsigned forward delta from `a` to `b` is less than half the space
  (`seq-mod`). Ties (`a == b`) and the exact half-way antipodal point are
  both `false` — there is no way to prefer one direction over the other at
  distance exactly 32768, so this codec does not pretend to."
  [seq-a seq-b]
  (let [d (seq-delta seq-a seq-b)]
    (and (pos? d) (< d (/ seq-mod 2)))))

(defn init-seq
  "Appendix A.1's `init_seq`: (re)synchronise tracking state on `seq`,
  discarding cycle count and loss-accounting history — sets `:probation`
  to 0, since `init_seq` is what `update_seq` calls once a source is
  already trusted (either freshly confirmed off probation, or resyncing
  after a confirmed restart); it is not itself the 'new source' entry
  point. Use `new-source` for that."
  [seq]
  {:base-seq seq :max-seq seq :bad-seq (inc seq-mod) :cycles 0
   :received 1 :received-prior 0 :expected-prior 0 :probation 0})

(defn new-source
  "Tracking state for an SSRC heard for the first time, per Appendix A.1's
  description of how a new source is added to a session's member list:
  `probation` set to `min-sequential`, and `max-seq` primed to `seq - 1`
  so that the very next `update-seq` call with this same `seq` reads as
  'in sequence' and starts the probation countdown, rather than being
  compared against a `max-seq` that hasn't seen a packet yet. A source
  entered this way is not validated — `loss-stats`/RTCP reports should not
  be trusted for it — until `min-sequential` consecutive in-order packets
  clear probation (which then calls `init-seq` internally, so
  `:base-seq`/`:cycles`/`:received` reflect the confirmed run, not the
  provisional ones)."
  [seq]
  {:base-seq seq :max-seq (u16 (dec seq)) :bad-seq (inc seq-mod) :cycles 0
   :received 0 :received-prior 0 :expected-prior 0 :probation min-sequential})

(defn update-seq
  "Appendix A.1's `update_seq`, as `(state, seq) -> state`. `state` is a
  map from `new-source` or a previous `update-seq` call — or `nil`, which
  is shorthand for `(update-seq (new-source seq) seq)`, i.e. 'first packet
  ever seen from this source': it still has to clear probation like any
  other new source, so `nil` does not mean 'accept unconditionally'.

  Returns the new state; `:accepted?` says whether the RFC's `update_seq`
  would have returned 1 (packet counted for loss/jitter accounting) or 0
  (provisionally rejected — held on probation, or a suspiciously large
  sequence-number jump not yet confirmed by seeing the very next number in
  that new range, RFC 3550's defence against treating a source restart as
  thousands of lost packets)."
  [state seq]
  (let [state (or state (new-source seq))
        {:keys [max-seq cycles bad-seq probation] :or {probation 0}} state
        udelta (seq-delta max-seq seq)]
    (cond
      (pos? probation)
      (if (= seq (u16 (inc max-seq)))
        (let [probation' (dec probation)]
          (if (zero? probation')
            (assoc (init-seq seq) :accepted? true)
            (assoc state :probation probation' :max-seq seq :accepted? false)))
        (assoc state :probation (dec min-sequential) :max-seq seq :accepted? false))

      (< udelta max-dropout)
      (assoc state
             :max-seq seq
             :cycles (if (< seq max-seq) (+ cycles seq-mod) cycles)
             :received (inc (:received state))
             :accepted? true)

      (<= udelta (- seq-mod max-misorder))
      (if (= seq bad-seq)
        ;; two sequential packets at the new number: the other side
        ;; probably restarted without telling us. Re-sync as if this
        ;; were a fresh source rather than reporting ~64K packets lost.
        (assoc (init-seq seq) :accepted? true)
        (assoc state :bad-seq (u16 (inc seq)) :accepted? false))

      :else
      ;; duplicate or (still) reordered packet — accepted for loss
      ;; accounting purposes, per the RFC's fallthrough to `s->received++`.
      (assoc state :received (inc (:received state)) :accepted? true))))

(defn loss-stats
  "Appendix A.3's fraction/cumulative-loss computation, as a pure read of
  `state` (does not mutate `:expected-prior`/`:received-prior` — call
  `advance-interval` to roll those forward once a report has actually been
  sent, matching the RFC's 'reset these at each reporting interval' note).

  Returns `{:expected N :lost N :fraction-lost F :extended-max N}` where
  `fraction-lost` is the 0..255 RTCP report-block byte: `lost-interval`
  shifted left 8 and divided by `expected-interval`, per the RFC — 0 when
  nothing was expected in this interval or when `lost-interval` comes out
  negative (duplicate packets can make it so; the RFC clamps rather than
  reports negative loss). `:lost` (the 24-bit signed cumulative-loss field)
  is likewise clamped at 0 on the low end — a source that duplicates more
  than it drops can otherwise make `expected - received` negative, and RFC
  3550 does not define a meaningful negative packet count.

  100% loss in the interval (`lost-interval == expected-interval`)
  computes to exactly `256`, one past the field's 8-bit range — the RFC's
  own pseudocode divides `lost_interval << 8` by `expected_interval` with
  no explicit clamp on the high end, unlike the low end's explicit `<= 0`
  check. Masking that with `bit-and 0xFF` (the naive translation of 'take
  the low byte') turns total loss into `0` on the wire — indistinguishable
  from zero loss, and a worse failure than not computing it at all — so
  this clamps to `255` instead."
  [{:keys [base-seq max-seq cycles received expected-prior received-prior]}]
  (let [extended-max (+ cycles max-seq)
        expected (inc (- extended-max base-seq))
        lost (- expected received)
        expected-interval (- expected expected-prior)
        received-interval (- received received-prior)
        lost-interval (- expected-interval received-interval)
        degenerate? (or (zero? expected-interval) (<= lost-interval 0))]
    {:expected expected
     :lost (max 0 lost)
     :fraction-lost (if degenerate?
                      0
                      (min 255 (quot (bit-shift-left lost-interval 8) expected-interval)))
     :extended-max extended-max}))

(defn advance-interval
  "Rolls `:expected-prior`/`:received-prior` forward to the values `loss-stats`
  just computed, per Appendix A.3's per-interval reset. Call this once,
  right after building the RTCP report that used `loss-stats`."
  [{:keys [base-seq max-seq cycles received] :as state}]
  (let [extended-max (+ cycles max-seq)
        expected (inc (- extended-max base-seq))]
    (assoc state :expected-prior expected :received-prior received)))

(defn transit
  "RTP transit time for one packet: `arrival - rtp-timestamp`, both in the
  same units (the media clock rate). Appendix A.8 computes this before the
  jitter update; kept separate so callers that only want transit (e.g. for
  one-way-delay estimates) don't have to thread jitter state through."
  [arrival-timestamp rtp-timestamp]
  (- arrival-timestamp rtp-timestamp))

(defn- abs-int [n] (if (neg? n) (- n) n))

(defn update-jitter
  "Appendix A.8's interarrival jitter estimator, run once per received
  packet — literally the RFC's own pseudocode:

      int transit = arrival - r->ts;
      int d = transit - s->transit;
      s->transit = transit;
      if (d < 0) d = -d;
      s->jitter += (1./16.) * ((double)d - s->jitter);

  `prev` is `{:transit t :jitter j}` from the previous call, or `nil` for
  the first packet of a source — there is no prior transit to diff
  against yet, so this returns `:jitter 0` rather than fabricating a `D`,
  matching the RFC's advice to initialise `J` to 0 on the first packet.
  `arrival-timestamp` and `rtp-timestamp` must already be in the same
  units (the stream's RTP clock rate); converting a wall-clock arrival
  time into that unit is the caller's job, not this function's.

  On the JVM, `:jitter` comes out as an exact Clojure ratio rather than
  the RFC's C `double` ((1./16.) recurs into `s->jitter` every packet, so
  this is the classic place floating point quietly drifts) — exact
  rational arithmetic, so this function's own `decode(encode(x)) == x`
  holds for jitter state the same way it does for everything else in this
  library. **In ClojureScript, `/` on two integers that don't divide
  evenly returns a `double`** (cljs has no ratio type), so this same code
  computes the RFC's own floating-point recursion there instead — still a
  faithful implementation of Appendix A.8, just without the JVM side's
  exactness bonus."
  [prev arrival-timestamp rtp-timestamp]
  (let [tr (transit arrival-timestamp rtp-timestamp)]
    (if (nil? prev)
      {:transit tr :jitter 0}
      (let [d (abs-int (- tr (:transit prev)))
            j (:jitter prev)]
        {:transit tr :jitter (+ j (/ (- d j) 16))}))))

(defn jitter-estimate
  "The RTCP-wire jitter value: RFC 3550's `J`, truncated to an unsigned
  32-bit integer number of timestamp units (`(u_int32)s->jitter` in the
  RFC's own pseudocode) for putting on the wire in a report block."
  [{:keys [jitter]}]
  (bit-and (long jitter) 0xFFFFFFFF))
