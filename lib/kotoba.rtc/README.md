# kotoba-lang/rtc

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-rtc`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI RTC: WebRTC SDK for KAMI Engine — room-based real-time
communication with WebRTC peer connections (SDP offer/answer, ICE
candidates), media track management, spatial audio integration, and a
signaling protocol over a KNP ReliableOrdered channel.

| Namespace | Restored from | Purpose |
|---|---|---|
| `rtc.media` | `media` | Media track types + constraints presets |
| `rtc.peer` | `peer` | Per-peer connection state machine |
| `rtc.room` | `room` | Room management, signal processing, spatialize dispatch |
| `rtc.signal` | `signal` | Signaling protocol wire format (EDN round-trip instead of JSON) |
| `rtc.spatial` | `spatial` | Spatial audio pan/volume calculation |

`rtc.spatial` implements a self-contained stereo-pan calculation
(listener-relative angle -> equal-power pan; inverse-distance rolloff
-> volume) rather than depending on `kami-audio` (not yet restored to
CLJC at time of writing).

## Status

Restored — all 5 modules ported from the original 1027-line Rust
source (`lib.rs` + `media.rs` + `peer.rs` + `room.rs` + `signal.rs` +
`spatial.rs`), with all 15 original Rust unit tests mirrored 1:1 in
`test/rtc_test.cljk` (+1 smoke test) — 16 tests / 44 assertions, 0
failures. Pure data + pure functions throughout; no IO/GPU.

## Develop

```bash
kbb -M:test
```
