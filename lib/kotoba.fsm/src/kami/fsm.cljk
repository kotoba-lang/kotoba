(ns kami.fsm
  "hiccup for state machines — an animation/behaviour FSM described as EDN data.
   Pure + cross-platform (.cljc): states carry params (visual or otherwise), transitions
   fire on named events. Store it as datoms, fork it, retune without code.

     {:initial :idle
      :states  {:idle {:emissive 0.4 :scale 1.0}
                :move {:emissive 0.95 :scale 1.08}}
      :transitions [{:from :idle :to :move :on :moving}
                    {:from :move :to :idle :on :still}
                    {:from :any  :to :jump :on :jumping}]}

   ## Where the player profile's rule lives

   `advance` over `default-player-fsm` does not compute anything here. It
   converts the state and events into the guest ABI, runs
   `src/kami/fsm.kotoba` — compiled, shipped as
   `resources/kami/fsm/oracle/player.kir.edn`, executed by `kami.fsm-oracle` —
   and converts the answer back. `fsm-parity-test` no longer binds two
   implementations of that machine, because for the calls the profile can
   express there is one.

   ## The generic/profile boundary, stated

   This namespace is a GENERIC engine: `advance` takes any machine map. The
   `.kotoba` is a bounded PROFILE of one specific machine — its own docstring
   says so: \"the generic EDN FSM remains in CLJC; this profile admits only its
   reviewed state/event contract\". `migration/player-fsm-v1.edn` records the
   same thing as `:generic-api-authorized false`. Delegating unconditionally
   would narrow this public API to that one machine, so it is conditional. The
   shipped core answers when all three of these hold, and every one of them is
   read off the artifact rather than asserted here:

     1. the machine IS `default-player-fsm` — the profile encodes that
        transition table, so any other table is a different rule, not the same
        rule with different data;
     2. the state is a case the shipped variant declares, carrying the `:i64`
        payload the profile models (see `params`, below, for why 0);
     3. the events are a set of the member type the shipped `[:set …]`
        parameter declares, no larger than the interpreter accepts.

   When any of them fails the generic engine answers, with exactly the
   behaviour it had before — a state the profile never heard of, an event
   collection that is not a set of keywords, and every machine that is not
   `default-player-fsm` are all unchanged. Which path ran is decided by the
   VALUES, never by whether the artifact loaded: a missing artifact throws.

   `params` and `initial` have no Kotoba counterpart and still answer here.
   Every variant case carries an `:i64` the profile always sets to 0, so the
   guest models transitions only, not the per-state visual params;
   `fsm-parity-test/params-is-unbound` is the tripwire that fires if that
   payload ever starts carrying something.

   ## ClojureScript hosts must register the KIR

   There is no classpath to read the artifact from, so a ClojureScript host has
   to `kami.fsm-oracle/register-kir!` before `advance` will answer for
   `default-player-fsm`; without it that call throws. Every other machine is
   unaffected, since it never reaches the guest. This is a real narrowing on
   that runtime, and it is the price of the rule having one home."
  (:require [kami.fsm-oracle :as oracle]))

(def default-player-fsm
  {:initial :idle
   :states  {:idle {:emissive 0.35 :scale 1.0}
             :move {:emissive 0.95 :scale 1.08}
             :jump {:emissive 1.4  :scale 1.16}}
   :transitions [{:from :any  :to :jump :on :jumping}
                 {:from :idle :to :move :on :moving}
                 {:from :jump :to :move :on :moving}
                 {:from :move :to :idle :on :still}
                 {:from :jump :to :idle :on :still}]})

;; ── the host ↔ guest ABI ─────────────────────────────────────────────
;;
;; Both descriptors are READ BACK from the shipped artifact rather than written
;; out here. The artifact is `fsm.kotoba` compiled, so the variant's name, its
;; declared cases and the events parameter's member type come from the source
;; of the rule. Delays, not defs: on a runtime with no classpath the artifact
;; arrives via `register-kir!`, which cannot have happened while this namespace
;; was being loaded.

(def ^:private state-type (delay (first (oracle/param-types :player 'advance-player-v1))))
(def ^:private events-type (delay (second (oracle/param-types :player 'advance-player-v1))))

(defn- ->guest-state
  "The guest value for `state`, or nil if the shipped profile cannot express it.

  The payload is 0 because the profile models transitions only and declares
  every case `:i64`; if a case ever declared something else, this returns nil
  and the generic engine answers rather than the host inventing a payload."
  [state]
  (when (= :i64 (oracle/case-payload-type @state-type state))
    (oracle/variant @state-type state 0)))

(defn- ->guest-events
  "The guest value for `events`, or nil if the shipped profile cannot express
  it. A Clojure set, because the interpreter refuses duplicates and a vector
  would let `contains?` mean something different on the way in."
  [events]
  (when (and (set? events)
             (= :keyword (oracle/set-member-type @events-type))
             (every? keyword? events)
             (<= (count events) oracle/max-typed-set-items))
    (oracle/typed-set @events-type events)))

(defn- advance-generic
  "The generic engine: the target of the first transition whose :from matches
   `state` (or :any) and whose :on event is present in `events`; else stay put.
   Answers every call the shipped profile cannot express, unchanged."
  [fsm state events]
  (or (some (fn [{:keys [from to on]}]
              (when (and (or (= from :any) (= from state)) (contains? events on)) to))
            (:transitions fsm))
      state))

(defn advance
  "Return the next state: the target of the first transition whose :from matches
   `state` (or :any) and whose :on event is present in `events` (a set); else stay put.

   For `default-player-fsm` with a state and an event set the shipped
   `player-v1` profile can express, this is `src/kami/fsm.kotoba` running.
   Everything else is the generic engine, unchanged — see the boundary note in
   the namespace docstring."
  [fsm state events]
  (let [guest-state (when (= fsm default-player-fsm) (->guest-state state))
        guest-events (when guest-state (->guest-events events))]
    (if guest-events
      (oracle/variant-tag
       (oracle/call :player 'advance-player-v1 [guest-state guest-events]))
      (advance-generic fsm state events))))

(defn params
  "The param map for a state (e.g. {:emissive :scale})."
  [fsm state]
  (get-in fsm [:states state] {}))

(defn initial [fsm] (:initial fsm))
