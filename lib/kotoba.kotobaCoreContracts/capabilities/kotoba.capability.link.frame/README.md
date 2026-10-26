# capability-link-frame

Atomic authority package for `link/frame`.

Raw OSI layer-2 Ethernet frame send/receive, addressed by EtherType, not by
IP host/port. This is what IEC 61850 GOOSE and Sampled Values need: those
protocols run directly over Ethernet (EtherType `0x88B8` / `0x88BA`), with
no IP layer at all, and are typically multicast to the whole substation LAN
segment.

- imports: `#{:frame-send :frame-receive}`
- effects: `#{:data-egress :network-read :network-write :device-control :no-addressing-boundary}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreigozrpzqrltjlmc4kfzhxrrc7e5noquzcjmzkzoy4tiusa7d43hii`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

## Why this is a different, stronger effect set than `net/datagram`

`net/datagram` (UDP) still has an addressing boundary: the OS kernel's IP
stack, a destination-allowlist provider can check the destination address
against, and a socket that only sees traffic addressed to it. A raw L2
socket has none of that:

- **No addressing boundary.** A raw Ethernet socket bound to an interface
  observes (and, depending on host configuration, can be made to accept)
  every frame of the admitted EtherType(s) on that physical/virtual segment,
  not just frames "for" the caller. There is no port, no listening backlog,
  no per-destination filter below the guest -- the provider's own
  allowlist is the *only* boundary, and it runs after the frame is already
  on the wire in the send direction, or already delivered to the host in the
  receive direction. `:no-addressing-boundary` names this precisely because
  `:network-read`/`:network-write` alone (as declared on `net/transport`
  and `net/datagram`) would silently imply the IP-layer boundary those two
  capabilities actually have and this one does not.
- **Direct device/bus access.** Opening a raw socket normally requires
  elevated host privilege (`CAP_NET_RAW` on Linux, or an OS-specific raw
  packet API) and talks to the network interface below the routing/
  filtering stack the rest of the host's networking goes through.
  `:device-control` is carried for the same reason `pci/config`/`dma/map`/
  `mmio/map` carry it in `kotoba-core-contracts`: this is not an ordinary
  socket call.
- **Physical-safety adjacency.** IEC 61850 GOOSE is not a telemetry
  protocol at rest -- it is routinely used to carry protective-relay trip
  commands between substation devices, with sub-4ms delivery expectations.
  A provider that can inject or spoof a GOOSE frame is a provider that can
  assert a trip (or block one). This capability's default policy is
  `:approval-required` for that reason, same as `can/frame`, and stronger
  than an ordinary network-write default would be.

## Upstream catalog status

`link/frame` is not yet a member of `kotoba-lang/kotoba-core-contracts`'
closed actor:host v0 catalog. Registering it there is a separate change to
that repository and is out of scope here. See
`test/kotoba/capability/link/frame_test.cljk`.

The functional binding for `.kotoba` guests lives in `kotoba-lang/amu`'s
`resources/kotoba/lang/capability-kits/link-frame-v1.edn` (capability id 28).
This repository is the authority/discovery descriptor; the kit is the
runtime surface.

Provider implementations may also import the pure Kotoba helpers under
`kotoba/capability/link/frame.kotoba`. They define the standard untagged
Ethernet pre-FCS bounds and make short-frame padding explicit. The helpers do
not grant raw-frame authority; the `link/frame` capability remains the gate.

```sh
kbb -M:test
```
