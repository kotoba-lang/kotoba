(ns afdx.redundancy
  "Redundancy management: an AFDX End System transmits every frame twice,
  once on network A and once on network B, and a receiving End System's
  Integrity Checking function keeps only ONE copy per Sequence Number —
  whichever of the two arrives FIRST ('first valid wins') — and discards
  the later, redundant copy.

  This namespace is a pure state machine: `receive` takes the receiver's
  current per-VL state and one arriving frame descriptor, and returns
  the new state plus a classification of what to do with that frame. It
  does not read a clock, a socket, or a network interface — a caller
  supplies `:received-at-ms` from whatever real clock it has.

  Confidence: 'first valid wins' + per-network duplicate elimination
  keyed by Sequence Number is the redundancy-management behaviour
  consistently described across public AFDX overview material. The
  specific ordering of `:accept-with-gap` vs `:discard-stale` below for
  an SN that is neither the expected next value nor a repeat of the last
  delivered one is this library's own reasonable extension of that
  behaviour (a real End System does not retransmit lost AFDX frames, so
  a receiver that only ever accepted an exact `next-sn` would stall
  forever after a single lost frame pair) rather than a specific claim
  about the standard's wording — treat `:accept-with-gap` especially as
  this namespace's own design decision, not a spec citation."
  (:require [afdx.sequence :as afdx-sn]))

(def initial-state
  {:last-delivered-sn 0 :last-delivered-at-ms nil :last-delivered-network nil})

(defn- ahead-within
  "True if `sn` is reachable from `last` within `window` forward steps
  (and is not `last` itself) — i.e. it looks like a legitimate next
  frame, allowing for up to `window` - 1 consecutive lost frame-pairs,
  rather than a wildly out-of-range/corrupted or ancient replayed SN."
  [last sn window]
  (let [[status steps] (afdx-sn/steps-forward last sn)]
    (and (= :ok status) (<= 1 steps window))))

(defn receive
  "`state` (start with `initial-state`) + `frame` (`{:network :a/:b :sn
  1-255 :received-at-ms n}`) -> `[new-state action]`.

  `action` is one of:
  - `:deliver` — the expected next SN; state's `:last-delivered-*` moves
    forward to this frame.
  - `:accept-with-gap` — an SN further ahead than `next-sn` but within
    `gap-window` (default 8) forward steps: the redundant pair for one
    or more intervening frames was lost on BOTH networks, and this
    library's own policy (see docstring) is to accept rather than stall.
  - `:discard-duplicate` — exactly `state`'s last delivered SN: this is
    the redundant copy of an already-delivered frame arriving on the
    other network (or a genuine retransmission at the MAC layer) —
    'first valid wins' in action. State is unchanged.
  - `:discard-stale` — an SN that is not reachable forward from the last
    delivered one within `gap-window` steps: either a very old replay or
    a corrupted/out-of-policy SN. State is unchanged.

  `[:error :afdx/sn-out-of-range sn]` if `sn` itself is not 0..255."
  ([state frame] (receive state frame 8))
  ([{:keys [last-delivered-sn] :as state} {:keys [network sn received-at-ms]} gap-window]
   (cond
     (not (afdx-sn/valid-sn? sn)) [:error :afdx/sn-out-of-range sn]

     (afdx-sn/initial? last-delivered-sn)
     [{:last-delivered-sn sn :last-delivered-at-ms received-at-ms :last-delivered-network network}
      :deliver]

     (= sn last-delivered-sn)
     [state :discard-duplicate]

     (ahead-within last-delivered-sn sn gap-window)
     (let [[_ steps] (afdx-sn/steps-forward last-delivered-sn sn)]
       [{:last-delivered-sn sn :last-delivered-at-ms received-at-ms :last-delivered-network network}
        (if (= 1 steps) :deliver :accept-with-gap)])

     :else
     [state :discard-stale])))
