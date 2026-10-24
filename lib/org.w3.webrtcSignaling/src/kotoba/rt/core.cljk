;; kotoba.rt.core — transport-independent WebRTC signaling relay logic.
;;
;; Reimplements (as pure CLJC data + functions) the routing behavior of the
;; deleted Rust crate `kotoba-rt` (see kotoba-lang/kotoba PR #259 and
;; 90-docs/adr/2606271500-kotoba-stage-obs-live-aozora.md): a room of clients
;; exchange opaque `:signal` messages (SDP offer/answer, ICE candidates) that
;; are relayed verbatim — unicast to a named `:to` client, or broadcast to
;; every other member of the room when `:to` is omitted.
;;
;; This namespace holds NO network I/O. It is the semantic contract: given a
;; room-state value and an incoming message, `route-message` deterministically
;; returns the list of outbound deliveries (or an error value). A WebSocket
;; (or any other transport) adapter is expected to:
;;   1. maintain a room-state atom/ref, applying `apply-event` on connect/
;;      disconnect and `join`/`leave` directly for explicit room membership
;;      changes,
;;   2. call `route-message` for every inbound `:signal` frame, and
;;   3. fan the returned `{:to client-id :payload ...}` entries out to the
;;      corresponding live socket for `:to`, dropping/erroring per `:error`.
;;
;; See README.md "Integration points" for the transport-adapter sketch.
(ns kotoba.rt.core)

;; ---------------------------------------------------------------------------
;; Room state: {room-id -> #{client-id ...}}
;; ---------------------------------------------------------------------------

(def empty-rooms
  "The empty room-state value. Rooms are created implicitly by `join` and
   removed implicitly by `leave` once their last member departs."
  {})

(defn join
  "Add `client-id` to `room-id`'s member set, creating the room if needed.
   Pure: returns the updated rooms map."
  [rooms room-id client-id]
  (update rooms room-id (fnil conj #{}) client-id))

(defn leave
  "Remove `client-id` from `room-id`'s member set. If the room becomes empty
   it is dropped from `rooms` entirely (no dangling empty rooms). Leaving a
   room/client that isn't present is a no-op."
  [rooms room-id client-id]
  (if-let [members (get rooms room-id)]
    (let [members' (disj members client-id)]
      (if (empty? members')
        (dissoc rooms room-id)
        (assoc rooms room-id members')))
    rooms))

(defn room-members
  "The set of client-ids currently joined to `room-id`, or nil if the room
   does not exist (distinguishes 'no room' from 'empty room', though empty
   rooms are never retained by `join`/`leave`/`apply-event`)."
  [rooms room-id]
  (get rooms room-id))

(defn in-room?
  "True if `client-id` is currently a member of `room-id`."
  [rooms room-id client-id]
  (contains? (get rooms room-id #{}) client-id))

;; ---------------------------------------------------------------------------
;; Membership events — reducible over a stream of join/leave, e.g. from a
;; durable event log or a websocket connect/disconnect handler.
;; ---------------------------------------------------------------------------

(defn apply-event
  "Apply a single membership event to `rooms`. `event` is one of:
     {:type :join  :room-id rid :client-id cid}
     {:type :leave :room-id rid :client-id cid}
   Unknown `:type` is a no-op (rooms returned unchanged) so that `apply-event`
   can be used as a `reduce` fn over a heterogeneous event log without a
   pre-filter. Pure."
  [rooms {:keys [type room-id client-id]}]
  (case type
    :join  (join rooms room-id client-id)
    :leave (leave rooms room-id client-id)
    rooms))

(defn apply-events
  "Fold a seq of membership events over an initial `rooms` value (default
   `empty-rooms`). Convenience wrapper around `(reduce apply-event ...)`."
  ([events] (apply-events empty-rooms events))
  ([rooms events] (reduce apply-event rooms events)))

;; ---------------------------------------------------------------------------
;; Signal messages: {:type :signal :room-id rid :from cid :to cid? :payload m}
;; `:payload` is an opaque map (SDP offer/answer, ICE candidate, ...) that is
;; relayed byte-for-byte — kotoba-rt never interprets it.
;; ---------------------------------------------------------------------------

(defn- error [kind msg]
  {:error kind :message msg})

(defn route-message
  "Given the current `rooms` state and an inbound signal `msg`, return either:
     - a vector of deliveries `[{:to client-id :payload payload} ...]`
       (unicast: exactly one entry when `:to` is present; broadcast: one
       entry per other room member when `:to` is absent — possibly empty if
       the sender is alone in the room), or
     - an error map `{:error kind :message string}` when the message cannot
       be routed:
         :room-not-found      — `:room-id` has no active room
         :sender-not-in-room   — `:from` is not a member of that room
         :recipient-not-in-room — explicit `:to` is not a member of that room
         :malformed-message   — missing required keys
   Pure; performs no I/O and mutates nothing."
  [rooms {:keys [type room-id from to payload] :as msg}]
  (cond
    (not= type :signal)
    (error :malformed-message (str "expected :type :signal, got " (pr-str type)))

    (or (nil? room-id) (nil? from))
    (error :malformed-message "signal message requires :room-id and :from")

    :else
    (let [members (get rooms room-id)]
      (cond
        (nil? members)
        (error :room-not-found (str "no such room: " (pr-str room-id)))

        (not (contains? members from))
        (error :sender-not-in-room (str (pr-str from) " is not joined to " (pr-str room-id)))

        (some? to)
        (if (contains? members to)
          [{:to to :payload payload}]
          (error :recipient-not-in-room (str (pr-str to) " is not joined to " (pr-str room-id))))

        :else
        (mapv (fn [cid] {:to cid :payload payload})
              (remove #(= % from) members))))))
