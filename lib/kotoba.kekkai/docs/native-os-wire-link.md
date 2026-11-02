# Native Kekkai wire over an emulated OS NIC — JUN-757

The native `kekkai.wire-region` port now composes with the existing region IK
and datagram implementation over the RTL8139C+ MMIO/DMA driver. The isolated
QEMU guest authenticates a public test peer, decrypts its transport frames,
dispatches framed data/ping/keepalive and emits independently checked encrypted
responses. This is a kernel diagnostic, not an installed Kekkai app, a native
Mac backend or a production/physical6600H peer connection.

The wire matches `kekkai-node/src/kekkai/node/peer.cljk` at
`60a62c3aca79dc5eb5f87b4bd8dfc5ee71d00f49` (source SHA in the receipt):
outer `6b 01 type` with init48/response49/transport50; encrypted inner types
data1/ping2/pong3/call-me-maybe4/keepalive5. The codec recognizes all of them;
the diagnostic only replies to data/ping and accepts an empty keepalive.
Pong/path-discovery/roaming semantics are still product work. No legacy
CLJK/JVM/Node implementation is executed.

`outer-type(input,capacity,used)` and `inner-type` return a type scalar, or0.
`wrap-outer(type,input,capacity,output,out-cap,used)` and `wrap-inner` return
total bytes, or-1. Capacities describe actual caller allocations, separately
from logical used lengths. Invalid lengths/types and overlapping allocations
refuse before output writes. No decoded type grants authority. Calls must be
serialized and input immutable, as for the underlying region crypto.

The codec preserves65535 payload bytes: outer total65538, inner total65536.
Physical capacities are bounded to131072. Byte accesses use checked subregions
so a full outer frame does not masquerade as a65536-byte intrinsic region.
The native fixture compares every byte of both maximum encodings, checks a
boundary sentinel, actual0/1/2-byte views, exact empty outer framing, all five
inner kinds, output capacity, payload overflow, unknown kinds and alias
refusals. Earlier v7-v9 probes successfully exercised the network but their
narrower encoding limit is superseded by final v10. Neither logical bound
claims single-packet transport: the exercised IP MTU remains1500. Fragment
reassembly/segmentation and larger logical-frame delivery remain open.

`aiueos.native.kekkai-link-gate` uses only public Cacophony IK keys, prologue
and fixed synthetic100/101-second times. Its designated positive received
packet uses `prepare-read`, and its response uses `prepare-write` with the
emitted token checked. Malformed probes exercise automatic transactional
read. This is actual packet consumption, not dummy calls or a solution to the
compiler's unused-public-function closure limitation. No export, grant,
ValueRuntime source, user ABI or compiler cap is removed or relaxed.

The40 exact injected frames yield11 byte-for-byte matching Ethernet/IP/UDP
responses,27 dispatch refusals,18 authenticated transport packets and two
accepted keepalives. Refusals include wrong magic/version/type/state,
authenticated IK with the wrong static or prologue, truncated/tampered
messages, the reverse-direction key, counter tampering, replay, wrong endpoint
and empty/unknown/unhandled inner plaintext. Six refused inner plaintexts
were authenticated; refusal must not be equated with failed authentication.
Reordered counters8 then7 are accepted. Data bodies0/1/31/64/257/1024/1444,
a ping/pong transaction and recovery after a rejected body/endpoint are
checked. The largest UDP body is1472 bytes, Ethernet1514. Native code creates
fresh IPv4/UDP checksums for changed response lengths; Python compares every
frame byte, not merely packet counts or an absence timeout.

All40 RX descriptors are reposted before acknowledgement. Native errors0,
request/DMA/state canaries intact, and the final8192-byte handshake and
17408-byte datagram states are zero both in native checks and independent
memory readback. The guest then parks; the terminal phase counter records
what occurred, not an active session after erasure. Application plaintext and
public fixture bytes are not claimed to be secret/persistently protected.

Three final faults independently bypass magic, version or replay checks.
Each completes all40 probes and final wipes with errors0/canaries intact,
while the observer detects actual bad-packet responses. Compile failures,
timeouts and halted guests are not counted as fault detection.

The23-module source-locked native graph retains the11 actual ValueRuntime
sources, two PT_LOAD segments (RX695424B/RW2359296B), existing256KiB request
grant, owned DMA window and2MiB compiler code cap. Native kernel/EFI/user
ELF/slot reproduce; the diagnostic user ELF is packaged but not executed.
Datagram39 and the earlier raw UDP31-frame regression retain their previous
source graphs and executable artifacts byte for byte. Their observer differs
from the final one only in the two Kekkai mutation search strings, explicitly
recorded in the receipt. Mac host sockets are127.0.0.1 UDP only; no TAP, router,
physical image, PXE candidate or management listener is changed.

Reproduce with `scripts/check-kekkai-region-os.py --component kekkai-link` and
the pinned compiler/packager/baseline/payload/QEMU/firmware arguments recorded
in [the evidence receipt](evidence/native-os-link-20261102/receipt.json).
Controls are `--mutation kw-magic`, `kw-version` and `kw-duplicate`. Python
stages/hashes/observes and constructs independent public expected wire bytes;
Amu alone discovers, compiles and packages the native OS/media.

Six initial failures remain recorded: duplicated source root (E6024), missing
recursive boolean annotations (E2104), unused `prepare-read` region contract
(E7106), an unprovable computed capacity (E7106), and two halted final-check
probes. The last two were an observer-fixture error: a broad edit gave its
wipe-check helper a1536-byte view while scanning a larger allocation. The
compiler's runtime bounds trap correctly stopped it. Final v10 uses the true
allocation extent. No failed run is retroactively qualified.

Remaining gates are verified signed roster/version/revocation, fresh entropy
and protected keys, trusted monotonic clock, retry/rekey/reconnect/path
lifecycle, admitted app sockets, full product/desktop import closure, Mac/OS
app install with fresh operation-specific consent, actual device round trips
and native SSH. The IK compatibility path is not the separate PQ broker
qualification. Whole L1/distributed OS production release remains open.

Status-note drift: the prior AIUEOS UDP progress note:17 lists Kekkai framing
as remaining; this new codec/integration partially resolves that list. The
old note and receipt retain their original scope. `AGENTS.md:20` says no module
here has a native gate; this is now an OS-target component proof, while its
specifically described Linux static CI gate and whole control-plane tests
still do not exist. The canonical instruction document is preserved.
