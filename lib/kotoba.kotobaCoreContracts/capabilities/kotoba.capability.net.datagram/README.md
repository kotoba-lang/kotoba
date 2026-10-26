# capability-net-datagram

Atomic authority package for `net/datagram`.

Connectionless UDP send/receive. No handshake, no ordering, no delivery
guarantee -- the guest sends one datagram to a destination, or waits for one
datagram to arrive on a bound local address. The transport (kernel socket,
allowlist enforcement, retry/timeout policy) is host-owned; this repository
only names the authority boundary a runtime must enforce before any transport
call happens.

- imports: `#{:datagram-send :datagram-receive}`
- effects: `#{:data-egress :network-read :network-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreidzbf6gmlgo4owxuejlaeb2whkwv4ws4vby2foeojitdl2ayhb3ya`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: the requesting actor must ask for it explicitly and the host must
admit the sealed envelope. `:capability/radicle-rid` is a locally-derived
(`base58(sha256(repository-name))`) discovery pointer, not a claim of a live
Radicle registration.

## Why UDP, not a generic `net/transport`

`kotoba-lang/capability-net-transport` (`net/transport`) already names a
generic connection-oriented read/write/close authority boundary. This
capability is narrower and connectionless on purpose: several wire-codec
protocol libraries in this workspace (CoAP, SNMP, RADIUS, RTP, PTP,
BACnet/IP) are UDP-only application protocols, and `net/transport`'s
open-then-write/read/close shape does not describe "send one datagram, get
one datagram back, there is no connection to close."

## Upstream catalog status

`net/datagram` is not yet a member of `kotoba-lang/kotoba-core-contracts`'
closed actor:host v0 catalog (neither the legacy `actor-host-capability-ids`
map nor the `capability_contract.edn` 201+ wire-id registry). Registering it
there is a separate change to that repository and is out of scope here. See
`test/kotoba/capability/net/datagram_test.cljk` for exactly what that means
for `validate-manifest` today.

The functional binding for `.kotoba` guests -- the typed request/result
schema, limits, and per-backend qualification -- lives in
`kotoba-lang/amu`'s `resources/kotoba/lang/capability-kits/datagram-v1.edn`
(capability id 27), not in this repository. This repository is the
authority/discovery descriptor; the kit is the runtime surface.

```sh
kbb -M:test
```
