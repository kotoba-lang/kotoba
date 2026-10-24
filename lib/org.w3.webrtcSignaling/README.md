# kotoba-rt

**Transport-independent WebRTC signaling relay logic, in pure CLJC.**
`kotoba-rt` lets a set of clients that share a room-id exchange opaque
`:signal` messages (SDP offer/answer, ICE candidates) — unicast to a named
peer, or broadcast to every other room member. It never interprets the
payload; it only decides *who receives what*.

This reimplements the routing behavior of the Rust crate `kotoba-rt`
(deleted in `kotoba-lang/kotoba` PR #259, see
[`rust-crate-migration.md`](https://github.com/kotoba-lang/kotoba/blob/main/docs/rust-crate-migration.md))
as CLJC: the CLJC contract is the semantic authority now, and a native
(Rust/whatever) adapter may be reintroduced later only to *host* this
contract over a real transport — it does not get to redefine the routing
semantics.

```clojure
(require '[kotoba.rt.core :as rt])

(def rooms (-> rt/empty-rooms
               (rt/join "room-42" "alice")
               (rt/join "room-42" "bob")
               (rt/join "room-42" "carol")))

;; unicast — alice sends carol an SDP answer
(rt/route-message rooms {:type :signal :room-id "room-42" :from "alice" :to "carol"
                          :payload {:sdp-type "answer" :sdp "..."}})
;;=> [{:to "carol" :payload {:sdp-type "answer" :sdp "..."}}]

;; broadcast — alice sends an ICE candidate to everyone else in the room
(rt/route-message rooms {:type :signal :room-id "room-42" :from "alice"
                          :payload {:candidate "..."}})
;;=> [{:to "bob" :payload {...}} {:to "carol" :payload {...}}]

;; membership changes fold over a durable event log
(rt/apply-events [{:type :join :room-id "room-42" :client-id "dave"}
                   {:type :leave :room-id "room-42" :client-id "alice"}])
```

## Contract

- **Room state** — `{room-id -> #{client-id ...}}`. `join`/`leave` are pure
  functions of this map; a room with zero members is dropped, never
  retained as an empty set.
- **`route-message`** is the routing core: `rooms + signal-msg -> deliveries
  | error`. It never mutates state and performs no I/O, so it is fully unit
  tested (`test/kotoba/rt/core_test.cljk`) without any network harness.
  Errors are returned as data (`{:error kind :message ...}`), not thrown,
  for the same reason — kinds: `:room-not-found`, `:sender-not-in-room`,
  `:recipient-not-in-room`, `:malformed-message`.
- **`apply-event`/`apply-events`** fold `:join`/`:leave` events over room
  state — usable both for an in-memory atom and for replaying a persisted
  event log (e.g. reconnect/crash-recovery of a signaling adapter).

## Integration points (not implemented here, deliberately)

`kotoba-rt` ships **no transport**. A production adapter (WebSocket, or
anything else) is expected to:

1. Hold a `rooms` value in an atom (or a durable store), applying
   `apply-event` on connect (`:join`) and disconnect (`:leave`).
2. On every inbound `:signal` frame from a socket, call `route-message`
   against the current `rooms` value.
3. For each `{:to client-id :payload ...}` in the result, look up the live
   socket for `client-id` and forward `payload` verbatim; on an `:error`
   result, either drop the frame or send an error frame back to the
   sender — the adapter's choice, `kotoba-rt` does not prescribe wire
   framing.
4. TURN/ICE credentialing and DTLS-SRTP transport (formerly `kotoba-turn`)
   remain a separate concern; `kotoba-rt` only relays the SDP/ICE blobs
   clients exchange to *set up* that transport, not the media itself.

The expected caller on the client side is
`kami-engine-sdk/src/lib/call/call.ts` (perfect-negotiation WebRTC client),
which speaks a `ClientMsg::Signal`-shaped message to whatever relay hosts
this contract.

## Correctness

`kbb -M:test`: join/leave/room-members, membership-event
folding, unicast routing, broadcast routing (including "alone in room" =>
empty delivery list), and all four error kinds — green (6 tests / 22
assertions, verified 2026-08-13).

The `kbb -M:test` alternative that used to be noted here is **unavailable**:
babashka was retired as this workspace's script host (ADR-2607173000) and the
conversion left `scripts/tasks.edn` empty, so it has had no runnable path since
2026-07-17 (ADR-2608131600).

## Scope notes / deliberate omissions

- No WebSocket server, no network I/O, no serialization format for the
  wire — see "Integration points" above. This is intentional: the contract
  should be testable and portable (JVM Clojure and ClojureScript, via
  `.cljc`) independent of any one transport or runtime.
- No TURN/ICE credential minting (that was `kotoba-turn`, a separate former
  crate) and no media-plane concerns.
- Room state here is an in-memory pure value; persistence/replication
  across relay instances is left to the adapter (e.g. backing `rooms` with
  a shared store, or sharding rooms by relay instance).

See `docs/ADR-kotoba-rt-signaling-relay.md` for the design rationale.

## License

Apache-2.0.
