(ns nostr.relay
  "Pure NIP-01 relay core: event acceptance (validate + store via the
  injected kotobase.store/IStore, ADR-2607171700's KRP §3.3 Content
  identity — event ids/Blossom hashes are domain-specific content hashes,
  see 90-docs/adr/2607172200 §16.3), and REQ/CLOSE query handling.

  \"Pure\" here matches this workspace's established convention from
  kotobase-protocols/src/kotobase/protocols/s3.cljc: no direct socket/
  network I/O — mutation goes only through the injected IStore, which is
  itself a pure in-memory value under kotobase.local/LocalStore. The actual
  WebSocket bytes-on-the-wire live in nostr.relay.transport (.cljs-only,
  per the kotoba-lang/dtn transport precedent) — this namespace has no
  knowledge of sockets, subscriptions-across-connections, or live fan-out;
  it hands the transport layer everything it needs (validated events,
  matched query results, response message data) to do that.

  STORAGE / NIP-01 KIND CLASSIFICATION (a real, not simplified, subset):
    regular      -> stored forever, keyed by id (:nostr.relay/events).
    replaceable  -> kind 0, 3, or 10000<=kind<20000: only the newest per
                    (pubkey, kind) is kept; storing an older-or-equal
                    timestamp than what's already stored is a no-op.
    addressable  -> kind 30000<=kind<40000 (aka \"parameterized replaceable\"):
                    same replace-by-newest rule, scoped to
                    (pubkey, kind, first \"d\" tag value).
    ephemeral    -> kind 20000<=kind<30000: never stored — accepted (OK
                    true) and handed to the transport for live fan-out
                    only, per NIP-01.
  Replaceable/addressable lookups do a full scan of the events collection
  (via IStore/-list + /-get) — correct, not optimized; documented as a v0.1
  scale limitation in the README, same spirit as s3.cljc's ListObjectsV2
  scanning every key in a bucket."
  (:require [kotoba.lang.text :as str]
            [kotobase.store :as st]
            [nostr.event :as event]))

(def events-coll :nostr.relay/events)

(defn- audit! [store op data]
  (st/-append store :nostr.relay/audit (merge {:surface :relay :op op} data)))

;; --------------------------------------------------------------- kinds

(defn ephemeral-kind? [kind] (and (>= kind 20000) (< kind 30000)))
(defn replaceable-kind? [kind] (or (= kind 0) (= kind 3) (and (>= kind 10000) (< kind 20000))))
(defn addressable-kind? [kind] (and (>= kind 30000) (< kind 40000)))

(defn- d-tag [event] (first (event/tag-values event "d")))

(defn- replace-key
  "The (pubkey, kind[, d-tag]) identity a replaceable/addressable event's
  storage slot is keyed by, or nil for a regular event."
  [{:strs [pubkey kind] :as ev}]
  (cond
    (replaceable-kind? kind) [pubkey kind]
    (addressable-kind? kind) [pubkey kind (d-tag ev)]
    :else nil))

(defn- all-events [store]
  (into [] (keep #(st/-get store events-coll %)) (st/-list store events-coll)))

(defn- newer-or-tied-lower-id?
  "NIP-01: for replaceable events with equal created_at, the event with the
  LOWEST id is retained. true iff `candidate` should win over `incumbent`."
  [candidate incumbent]
  (let [ct (get candidate "created_at") it (get incumbent "created_at")]
    (or (> ct it)
        (and (= ct it) (neg? (compare (get candidate "id") (get incumbent "id")))))))

(defn- find-replaceable-slot [store ev]
  (let [rk (replace-key ev)]
    (when rk
      (first (filter #(= rk (replace-key %)) (all-events store))))))

;; --------------------------------------------------------------- accept

(defn handle-event!
  "Validate + (maybe) store one client-submitted event. Returns:
    {:ok? bool :reason kw-or-nil :stored? bool :duplicate? bool :event event}
  `:event` is always the input event (for the caller to build an OK message
  and, when :ok? and :stored?/ephemeral, to fan out live to matching REQ
  subscriptions on OTHER connections — ephemeral events have :stored? false
  but still :ok? true, meaning \"broadcast it, just don't keep it\")."
  [{:keys [store]} event]
  (let [{:keys [valid? reason]} (event/validate event)]
    (if-not valid?
      {:ok? false :reason reason :stored? false :duplicate? false :event event}
      (let [kind (get event "kind")]
        (cond
          (ephemeral-kind? kind)
          (do (audit! store :accept-ephemeral {:id (get event "id") :kind kind})
              {:ok? true :reason nil :stored? false :duplicate? false :event event})

          (or (replaceable-kind? kind) (addressable-kind? kind))
          (let [incumbent (find-replaceable-slot store event)]
            (cond
              (and incumbent (= (get incumbent "id") (get event "id")))
              {:ok? true :reason nil :stored? false :duplicate? true :event event}

              (and incumbent (not (newer-or-tied-lower-id? event incumbent)))
              (do (audit! store :reject-stale-replaceable
                          {:id (get event "id") :kind kind :incumbent-id (get incumbent "id")})
                  {:ok? true :reason :superseded-by-newer :stored? false :duplicate? false :event event})

              :else
              (do (when incumbent (st/-put store events-coll (get incumbent "id") nil))
                  (st/-put store events-coll (get event "id") event)
                  (audit! store :store-replaceable
                          {:id (get event "id") :kind kind
                           :replaced-id (get incumbent "id")})
                  {:ok? true :reason nil :stored? true :duplicate? false :event event})))

          (st/-get store events-coll (get event "id"))
          {:ok? true :reason nil :stored? false :duplicate? true :event event}

          :else
          (do (st/-put store events-coll (get event "id") event)
              (audit! store :store {:id (get event "id") :kind kind})
              {:ok? true :reason nil :stored? true :duplicate? false :event event}))))))

;; ---------------------------------------------------------------- query

(defn query
  "REQ query: OR of `filters` over every currently-stored event (see
  nostr.event/run-filters). Pure read, no side effects."
  [{:keys [store]} filters]
  (event/run-filters (all-events store) filters))

;; ---------------------------------------------------- NIP-01 wire messages

(defn ok-message [event-id ok? message]
  ["OK" event-id (boolean ok?) (or message "")])

(defn event-message [sub-id event] ["EVENT" sub-id event])
(defn eose-message [sub-id] ["EOSE" sub-id])
(defn closed-message [sub-id message] ["CLOSED" sub-id (or message "")])
(defn notice-message [message] ["NOTICE" message])

(def reason->ok-message
  {:malformed "invalid: malformed event"
   :id-mismatch "invalid: id does not match canonical serialization"
   :invalid-signature "invalid: signature verification failed"
   :superseded-by-newer "replaced: a newer event for this replaceable slot already exists"})

;; ---------------------------------------------------- client message dispatch

(defn handle-client-message
  "Dispatch one already-JSON-parsed client message (a vector, string-keyed
  event maps preserved as-is per nostr.json's convention). Returns a map
  describing what happened — the transport layer turns this into actual
  wire sends and manages per-connection subscription registries (this
  namespace has no notion of a connection):

    EVENT -> {:type :event-result :ok-message [...]
              :accepted-event event-or-nil}   ; non-nil => transport should
                                               ; live-fan-out to every OTHER
                                               ; open subscription whose
                                               ; filters match it. nil for
                                               ; invalid, duplicate, AND
                                               ; superseded-by-newer events
                                               ; (a stale replaceable/
                                               ; addressable event the relay
                                               ; did NOT accept into its
                                               ; public state, even though
                                               ; its own OK is still true
                                               ; per NIP-01 convention) —
                                               ; non-nil for regular/
                                               ; replaceable/addressable
                                               ; events that were actually
                                               ; stored, AND for ephemeral
                                               ; events (never stored, but
                                               ; still meant to be
                                               ; broadcast live)
    REQ   -> {:type :req-result :sub-id sub-id :filters [...]
              :messages [[\"EVENT\" sub-id ev] ... [\"EOSE\" sub-id]]}
              ; transport also stores {sub-id filters} for this connection
              ; so FUTURE accepted events can be live-pushed to it too
    CLOSE -> {:type :close-result :sub-id sub-id
              :message [\"CLOSED\" sub-id \"\"]}
    other -> {:type :notice :message [\"NOTICE\" \"...\"]}"
  [ctx msg]
  (cond
    (not (and (vector? msg) (seq msg) (string? (first msg))))
    {:type :notice :message (notice-message "invalid message: expected a JSON array with a string type")}

    (= "EVENT" (first msg))
    (let [ev (second msg)
          {:keys [ok? reason stored? duplicate? event]} (handle-event! ctx ev)
          ok-msg (ok-message (get ev "id") ok?
                             (cond (not ok?) (get reason->ok-message reason (name (or reason :invalid)))
                                   (get reason->ok-message reason) (get reason->ok-message reason)
                                   duplicate? "duplicate: already have this event"
                                   :else ""))]
      {:type :event-result
       :ok-message ok-msg
       :accepted-event (when (and ok? (not duplicate?) (not= reason :superseded-by-newer)) event)})

    (= "REQ" (first msg))
    (let [sub-id (second msg)
          filters (vec (drop 2 msg))
          matched (query ctx filters)]
      {:type :req-result
       :sub-id sub-id
       :filters filters
       :messages (conj (mapv #(event-message sub-id %) matched) (eose-message sub-id))})

    (= "CLOSE" (first msg))
    (let [sub-id (second msg)]
      {:type :close-result :sub-id sub-id :message (closed-message sub-id "")})

    :else
    {:type :notice :message (notice-message (str "unknown message type: " (first msg)))}))
