# Itonami home: two more honest lines (2026-10-28)

The Itonami home now shows five read-only lines: `DID: none`, `Wallet: none`,
`Approved: n` (live since the W2 slice), `Network: off` and `Telemetry: none`.
The last two state what is true of this build: the desktop has no network
driver, and nothing is sent (the W8 idle-silent gate measures that on a
virtual NIC). They are presentation text, not read from any state, and grant
nothing.

Evidence: `native-consent-qemu.json` (QEMU TCG, Apple Silicon, `--profile
consent`, signed kernel-v3 compiler 4350f3ba). Event `pointer-allow` records
`networkInk` and `telemetryInk` (ink pixels in the two line bands) and the
gate asserts the band under them stays blank. `home-after-allow.png` is the
frame. Desktop GPT+ISO, local-draft (12 events) and idle (4 events) gates
also pass with this change.

Limits: synthetic input; the lines are static, so "Network: off" is a claim
about this build, not live state; DID and Wallet are still `none`. Source
change and built candidate with QEMU results; not deployed.
