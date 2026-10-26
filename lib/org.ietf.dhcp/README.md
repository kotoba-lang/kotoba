# org-ietf-dhcp

**RFC 2131 / 2132 DHCPv4 — the wire codec and the client state machine, in
portable `.cljc`.**

Bytes in, map out; state plus event in, next state plus packets out. There are
no sockets here, no clock and no randomness: the caller supplies the
transaction id, the hardware address and `:now-ms`. That is what makes a lease
expiry testable without waiting out a lease, and the whole codec testable on a
machine with no DHCP server on it.

```clojure
(require '[dhcp.client :as dhcp] '[dhcp.wire :as wire])

(def c (dhcp/init {:chaddr [0x52 0x54 0x00 0x12 0x34 0x56] :xid 0xdeadbeef}))
(def started (dhcp/step c {:kind :start :now-ms 0}))   ; => :send [DISCOVER]
;; ... hand (:send started) to a transport, feed replies back in ...
(dhcp/bound-address (:state acked))                     ; => [192 168 1 50] or nil
```

## Why it exists

`kotoba-lang/aiueos` reaches IPv4 and one TCP connection with the address pair
10.0.2.15/10.0.2.2 **written into the driver** — QEMU SLIRP's fixed topology. A
machine with a hardcoded address does not join a customer's LAN, so "power it
on and plug it in" stops at the first switch.

Searched across all 4,178 west projects on 2026-08-15 before writing a line:
nothing in the org implemented DHCP. (`com-tcp-ip` is a CRUD actor over TCP
*records* — a schema, not a stack.)

## What the decoder refuses

A DHCP client takes its address from an unauthenticated broadcast, so the
decoder is the whole of its input validation.

- An option whose length runs past the buffer is `:option-overruns` — refused,
  never clamped. A clamped option decodes into something shorter but plausible
  from input that was never fully received.
- A reply with no DHCP message type is `:no-message-type`. A BOOTP reply is not
  a DHCP message, and guessing the type is how an OFFER gets treated as an ACK.
- `decode` returns a message map **or** `{:dhcp/error ...}` — never a
  half-filled map, because a caller cannot tell a missing field from a field
  that was never sent.

## What the state machine refuses

- A reply whose `xid` is not ours is `:foreign-xid`. Without that check, any
  broadcast on the segment can drive this client's state — which on a shared
  LAN is every DHCP conversation happening near it.
- A NAK drops the lease and returns to `:init` from every state that can
  receive one. Keeping an address after being told it is not ours is the case
  where two hosts hold the same address and neither knows.
- Past the lease end the address is **given up**, not renewed in place. An
  expired lease is an address someone else may now hold.
- `bound-address` is nil in every state but `:bound`. An address seen in
  `:requesting` is not yours until the ACK.

## Status

Codec and client state machine, with tests. **No transport** — sending and
receiving belong to whatever owns the interface (`aiueos` on bare metal, a
socket on a hosted profile). That boundary is deliberate: this layer has to run
where there is no socket API at all.
