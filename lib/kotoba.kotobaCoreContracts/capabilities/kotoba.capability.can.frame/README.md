# capability-can-frame

Atomic authority package for `can/frame`.

CAN 2.0B frame send/receive with 29-bit extended identifiers, addressed by
CAN arbitration ID on a shared bus -- not by IP host/port and not by
EtherType. This is what SAE J1939 needs: J1939 Parameter Groups are carried
entirely inside the 29-bit extended CAN identifier (priority + PGN + source
address) and an up-to-8-byte classic-CAN data field; there is no IP or
Ethernet framing involved at all.

- imports: `#{:frame-send :frame-receive}`
- effects: `#{:data-egress :network-read :network-write :device-control :no-addressing-boundary :physical-actuation-risk}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreidavacouffmyyc6elrv3cp5abvxckjqm6jfejw6t23xkuenxvjpdm`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

## Why this effect set, and why it is stronger than `link/frame`'s

CAN is a broadcast bus, which gives it the same `:no-addressing-boundary`
and `:device-control` character as raw Ethernet (see
`kotoba-lang/capability-link-frame`'s README for that reasoning in full --
it applies here unchanged): every node on the bus receives every frame,
arbitration is priority-based rather than addressed, and opening a CAN
socket is a raw-device operation (`SocketCAN` on Linux, a vendor CAN driver
elsewhere), not an ordinary socket call.

`can/frame` carries one thing `link/frame` does not: `:physical-actuation-risk`.
J1939 is not a telemetry-only bus in the systems it targets (heavy trucks,
buses, agricultural and marine equipment, generator sets) -- Parameter
Groups on it include direct commands to engine, transmission, brake, and
steering controllers. A provider that can inject a J1939 frame is a
provider that can command a physical actuator on a real vehicle or machine,
which is a different and larger risk than reading or spoofing a substation
telemetry/trip signal. (IEC 61850 GOOSE also has real physical-safety
stakes, as `link/frame`'s README says -- the two capabilities are both
`:approval-required` for that reason. `:physical-actuation-risk` names the
*more direct* actuation path CAN/J1939 has: PGNs that are literally
`command` messages to a controller, not a protective-relay trip signal
riding alongside telemetry.)

## Limits are the CAN 2.0B frame itself, not a policy choice

Classic CAN (2.0A/2.0B, as opposed to CAN-FD) bounds the data field at
8 bytes per frame by the wire protocol, and a 29-bit extended identifier
tops out at `2^29 - 1 = 536,870,911`. The kit limits
(`kotoba-lang/amu`'s `resources/kotoba/lang/capability-kits/can-frame-v1.edn`)
state these as explicit bounds rather than leaving them implicit, but they
are not a narrower-than-necessary policy choice -- they are what a
correctly-formed CAN 2.0B frame *is*. CAN-FD (up to 64 data bytes) is out of
scope for this capability; J1939 does not require it.

## Upstream catalog status

`can/frame` is not yet a member of `kotoba-lang/kotoba-core-contracts`'
closed actor:host v0 catalog. Registering it there is a separate change to
that repository and is out of scope here. See
`test/kotoba/capability/can/frame_test.cljk`.

The functional binding for `.kotoba` guests lives in `kotoba-lang/amu`'s
`resources/kotoba/lang/capability-kits/can-frame-v1.edn` (capability id 29).
This repository is the authority/discovery descriptor; the kit is the
runtime surface.

```sh
kbb -M:test
```
