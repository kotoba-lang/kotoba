;; kotoba.turn.allocation — RFC 8656 §5-§11 TURN allocation / permission /
;; channel-binding STATE MODEL. Pure/portable `.cljc`, same discipline as
;; `kotoba.turn.stun`: every function here is deterministic and
;; `now`-injected (callers pass a millisecond timestamp; nothing in this
;; namespace reads a clock, touches a socket, or does I/O of any kind) —
;; this is the CLJC port of the deleted Rust reference implementation's
;; `allocation.rs`, which the ADR describes as "deterministic, `now`-
;; injected" (docs/ADR-kotoba-turn-relay.md).
;;
;; What this models: a single TURN allocation as a plain EDN map — its
;; 5-tuple, its relayed-transport-address, its own expiry, the peer
;; permissions installed against it (§9, each with its OWN independent
;; expiry, default 300s), and the channel bindings installed against it
;; (§11, each with its own expiry, default 600s). Callers own storage (e.g.
;; an atom keyed by 5-tuple); this namespace never mutates or looks anything
;; up on its own — it only ever takes an allocation value in and returns a
;; new one (or `nil`) out. Garbage-collecting anything `expired?` reports
;; true, and anything a refresh/create-permission/channel-bind rejects
;; (returns `nil`), is also the caller's job.
;;
;; What this deliberately does NOT model (out of scope; a later listener
;; phase wires these against `kotoba.turn.stun`'s attribute codec plus the
;; functions here): actually relaying any data (zero socket I/O anywhere in
;; this repo); per-client allocation quotas/DoS limits; the
;; REQUESTED-TRANSPORT / DONT-FRAGMENT / EVEN-PORT / RESERVATION-TOKEN STUN
;; attributes that govern *request handling* around allocation creation
;; (this namespace models the allocation record a valid request produces,
;; not the request-validation logic that decides whether to produce one).
(ns kotoba.turn.allocation)

;; RFC 8656 §12 Table 2 formally allocates only 0x4000-0x4FFF as usable
;; channel numbers (0x5000-0x7FFF is reserved for RFC 7983 DTLS-SRTP
;; multiplexing collision avoidance). This repo instead validates the
;; coarser, RFC 5766-style 0x4000-0x7FFF range: the top 2 bits of a 16-bit
;; field taking any value in this range are always `01`, which is exactly
;; what makes the leading-bits STUN/ChannelData demux in
;; `kotoba.turn.demux/classify-datagram` (top bits `00` => STUN, per RFC
;; 8489 §5) a clean, non-overlapping 2-bit split. A future listener phase
;; that also needs to coexist with DTLS-SRTP/ZRTP/RTP on the same 5-tuple
;; (RFC 7983's finer first-byte table) would need to further narrow this to
;; 0x4000-0x4FFF; this pure state model does not assume that coexistence.
(def channel-min 0x4000)
(def channel-max 0x7FFF)

(defn channel-number-valid?
  "True iff `n` is in the [channel-min, channel-max] range this repo treats
   as valid TURN channel numbers (see the namespace-level comment above)."
  [n]
  (<= channel-min n channel-max))

;; RFC 8656 §5: default allocation lifetime, used when a request/refresh
;; carries no explicit lifetime.
(def default-lifetime-s 600)

;; RFC 8656 doesn't mandate a hard cap on allocation lifetime for the
;; allocation record itself, but a real server must enforce SOME bound
;; against a REFRESH chain that never ends — 1 hour is a conservative,
;; commonly-used default. Callers that want a different cap can pass
;; `:max-lifetime-s` to `allocate`/`refresh`.
(def default-max-lifetime-s 3600)

;; RFC 8656 §9: permissions have their own, shorter, independently-expiring
;; lifetime, distinct from the allocation's lifetime.
(def default-permission-lifetime-s 300)

;; RFC 8656 §11: channel bindings default to the same lifetime as a fresh
;; allocation (600s), refreshed by data flow in a real server; here they're
;; refreshed explicitly via `channel-bind`/`refresh-channel-binding`.
(def default-channel-lifetime-s 600)

(defn- clamp-lifetime-s
  "Effective lifetime in seconds: `lifetime-s` (or `default-lifetime-s` if
   omitted), clamped to `max-s` (or `default-max-lifetime-s` if omitted)."
  ([lifetime-s] (clamp-lifetime-s lifetime-s default-max-lifetime-s))
  ([lifetime-s max-s]
   (min (long (or lifetime-s default-lifetime-s)) (long (or max-s default-max-lifetime-s)))))

;; ---------------------------------------------------------------------------
;; Allocation (RFC 8656 §5-§7)

(defn allocate
  "New allocation for `five-tuple` (client addr/port, server addr/port,
   transport — an opaque value as far as this namespace is concerned, it's
   never inspected here) with relayed transport address `relayed-address`
   (also opaque — shape is the caller's choice, e.g. a
   `kotoba.turn.stun/decode-xor-mapped-v4`-shaped map). `now` is a
   caller-supplied millisecond timestamp. `:lifetime-s` overrides RFC 8656
   §5's 600s default; the effective value is clamped to `:max-lifetime-s`
   (default 3600s — see `default-max-lifetime-s`)."
  [now five-tuple relayed-address & {:keys [lifetime-s max-lifetime-s]}]
  {:turn/five-tuple five-tuple
   :turn/relayed-address relayed-address
   :turn/expiry (+ now (* 1000 (clamp-lifetime-s lifetime-s max-lifetime-s)))
   :turn/permissions {}
   :turn/channel-bindings {}})

(defn expired?
  "True iff `allocation`'s own expiry has passed as of `now`."
  [allocation now]
  (> now (:turn/expiry allocation)))

(defn refresh
  "RFC 8656 §7.3 Refresh: extends `:turn/expiry` from `now` by `:lifetime-s`
   (clamped to `:max-lifetime-s`, same defaults as `allocate`). Per §7.3, a
   Refresh whose requested lifetime is exactly 0 signals the client wants
   the allocation deleted. Since this is a pure function operating on a
   value (not a store), there is nothing here to delete — deletion is
   represented by returning `nil`; the caller is responsible for actually
   removing the allocation from wherever it lives."
  [allocation now & {:keys [lifetime-s max-lifetime-s]}]
  (when-not (and lifetime-s (zero? lifetime-s))
    (assoc allocation :turn/expiry (+ now (* 1000 (clamp-lifetime-s lifetime-s max-lifetime-s))))))

;; ---------------------------------------------------------------------------
;; Permissions (RFC 8656 §9) — each permission has its OWN expiry,
;; independent of the allocation's `:turn/expiry`.

(defn create-permission
  "Install or refresh a permission for `peer-address` on `allocation`
   (RFC 8656 §9). `peer-address` is an opaque key (typically just the peer's
   IP, per §9 — permissions are IP-only, not IP:port). Default lifetime
   300s (`default-permission-lifetime-s`); does not touch
   `:turn/expiry`."
  [allocation peer-address now & {:keys [lifetime-s]}]
  (assoc-in allocation [:turn/permissions peer-address]
            (+ now (* 1000 (or lifetime-s default-permission-lifetime-s)))))

(defn permission-active?
  "True iff `allocation` has a permission installed for `peer-address` AND
   that permission's own expiry has not passed as of `now`."
  [allocation peer-address now]
  (boolean
    (when-let [expiry (get-in allocation [:turn/permissions peer-address])]
      (<= now expiry))))

;; ---------------------------------------------------------------------------
;; Channel bindings (RFC 8656 §11)

(defn channel-bind
  "Bind `channel-num` to `peer-address` on `allocation` (RFC 8656 §11).
   `channel-num` must satisfy `channel-number-valid?` — an out-of-range
   channel number is a hard rejection: returns `nil` rather than silently
   installing an invalid binding (the caller is expected to reply with a
   400 Bad Request per §11, not to retry with a clamped value). On success,
   returns the updated allocation with `:turn/channel-bindings` holding
   `{channel-num {:peer-address peer-address :expiry ...}}`. Default
   lifetime 600s (`default-channel-lifetime-s`)."
  [allocation channel-num peer-address now & {:keys [lifetime-s]}]
  (when (channel-number-valid? channel-num)
    (assoc-in allocation [:turn/channel-bindings channel-num]
              {:peer-address peer-address
               :expiry (+ now (* 1000 (or lifetime-s default-channel-lifetime-s)))})))

(defn refresh-channel-binding
  "Refresh an existing channel binding's expiry. In a real server this
   happens implicitly on data flow through the channel (RFC 8656 §11); this
   pure namespace has no data-flow events to hang that off of, so it's
   exposed as an explicit call instead. Structurally identical to
   `channel-bind` (re-binding the same channel/peer with a fresh expiry IS
   a refresh) — kept as a separate name purely so callers can say what they
   mean. Same validation/rejection behavior as `channel-bind`."
  [allocation channel-num peer-address now & {:keys [lifetime-s]}]
  (channel-bind allocation channel-num peer-address now :lifetime-s lifetime-s))

(defn peer-for-channel
  "The peer address bound to `channel-num` on `allocation`, or `nil` if no
   binding exists OR the binding has expired as of `now`. Note this takes
   `now` (unlike the abbreviated signature sketched in the task that spawned
   this namespace) — an expiry check is meaningless without a timestamp to
   check it against, and every other expiry-checking function in this
   namespace (`expired?`, `permission-active?`) takes one too."
  [allocation channel-num now]
  (let [{:keys [peer-address expiry]} (get (:turn/channel-bindings allocation) channel-num)]
    (when (and expiry (<= now expiry))
      peer-address)))

(defn channel-for-peer
  "The channel number bound to `peer-address` on `allocation`, or `nil` if
   none is bound (or the one that was has expired as of `now`). Takes `now`
   for the same reason `peer-for-channel` does. RFC 8656 §11: a given peer
   address should be bound to at most one channel per allocation, so the
   first non-expired match is returned."
  [allocation peer-address now]
  (some (fn [[channel-num binding]]
          (when (and (= (:peer-address binding) peer-address)
                     (<= now (:expiry binding)))
            channel-num))
        (:turn/channel-bindings allocation)))
