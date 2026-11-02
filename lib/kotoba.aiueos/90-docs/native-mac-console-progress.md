# Mac remote console candidate (AWAI-119)

The development Mac can display the 6600H desktop in native macOS Screen
Sharing. The host adapter listens only on `127.0.0.1:22078`, authenticates
with a private VNC password, and uses the existing pinned-key SSH management
alias `itonami-6600h`. The actual OS ingress still verifies signed commands,
the current boot nonce and a rising request counter. This is a Mac host
administration adapter, separate from OS-native SSH, Kekkai and app runtime.

The progressive candidate obtains one verified row for geometry and sends
ServerInit before a full-screen read. A non-incremental update still covers
the entire requested area (RFC6143 section7.5.3), as a sequence of rectangles
with at most32 rows each. The first real rectangle can leave while later
bands are still being captured, and input runs between native band requests.
Small viewports do not trigger full-screen captures. Missing/malformed bands
close the session; they are never replaced with black or stale pixels.
Only pixels actually delivered to that viewer enter the incremental cache.
An incremental request cannot cancel a queued full refresh; disjoint pending
regions are retained, with a64-request backlog cap. The channel's native
nonce/signature and remote-approval restrictions remain unchanged.

`progressive-readback.json` binds the candidate source,17 RFB and8 channel
tests and four same-boot hardware runs. In that harness the first complete
rectangle arrived at0.733–0.740s rather than4.759–4.815s. A signed hover
followed by a requested64x32 region took0.349–0.407s rather than4.181–4.483s;
cursor pixel changes were read back independently. Whole-screen completion
still took4.35–4.37s. These are protocol-harness samples, not human-visible
first paint, physical input-to-panel latency or drag-smoothness acceptance.

The committed progressive adapter was then restarted on the Mac loopback
endpoint. Native macOS Screen Sharing displayed the full desktop, opened
Itonami with a pointer click, and sent `r`: Goal `aba` became `abar` in the
viewer. Backspace restored `aba`; Approved remained0 and Network remained
off. This verifies native-client compatibility and local input/readback,
not human timing or a trusted app approval. See `progressive-deployment.json`.

## Post-render damage priority candidate

The debug desktop now emits KDBG c015 (the complete64-bit accepted input
counter) and c016 (top/bottom rows, two16-bit edges) after the corresponding
native present-frame returns. The earlier c012/c013 admission replies remain
unchanged. The interval comes from the existing renderer's conservative
damage bounds, clipped to the viewport; refused or empty frames report0.
This is a scheduling hint, not authenticated pixel data or an app approval.

The private Mac management configuration must explicitly set
`frameDamageHints: true` only for a qualified image with this protocol.
Absent/false selects the existing legacy profile. With the new profile
selected, missing or mismatched post-render records fail; they never cause
an automatic downgrade or replay of the input. The viewer checks the boot,
full counter and actual framebuffer height, prioritizes the interval edges
and then its interior, and reads every displayed pixel through the existing
32-row transport. At most three priority reads precede a background read,
so unrelated physical input/animation still gets scanned. Hints coalesce
within256 row buckets and never make an unseen pixel valid. Disconnect and
new sessions clear the hints; a closed viewer cannot start a new capture
after waiting for an input's native result.

`damage-priority.json` records the35-module native component,44-module
product reproduction, normal12-event USB/NVMe regression, no-install PXE
USB/hub smoke and35 host tests. The existing2MiB internal code budget and
actual product/user ABI were retained. Initial E7104 attempts are recorded;
shared input presentation and exact public numeric/magic tables reduced
generated code. Native QEMU compares the actual packed command, log,
legacy screenshot and band-header bytes with independent literals. The
subsequent live readback is recorded in `damage-priority-live.json`.

The no-install PXE image booted on6600H and returned actual post-render
counter/rows. On one boot with the same source, two explicit legacy-profile
samples took3.498/3.714s to show the new cursor and erase the old one in the
RFB harness; two enabled-profile samples took0.562/0.650s. The enabled samples
read back78 changed cursor pixels in two updates, with matching full counters.
These are host-observed samples, not panel or human-smoothness bounds.
The private management profile and local adapter are enabled. Native Mac
Screen Sharing opened Itonami, typed `r` to show `abar`, and restored `aba`
with Backspace, with Approved0/Network off. The next single PXE boot is
reserved for the same checked image; the existing fallback is preserved.
Production install/update, protocol negotiation across arbitrary fallback
images and whole-release acceptance remain separate open work.

## Continuous-input capture fairness

The previous adapter waited for the entire input queue to become idle before
querying changed rows or reading pixels. Continuous drag motion could keep
that wait alive until the gesture ended. Both queries now take an ordered
turn on the same worker as native input. Later motion follows the queued
read; earlier keys/button edges retain their order. Reads retain the existing
32-row limit and256-item work bound. Disconnect cancels unsent reads and
drains the final button release; an in-flight failure is returned once.

`fair-capture.json` records41 host tests, including six queue controls, and
four same-boot physical RFB/SSH/native-pointer samples in ABBA order. Each
sample injects240 small titlebar motion requests, then returns the window
and cursor to their original positions. The final complete screen was
byte-identical to its initial screen in every sample. The previous queue
returned no update during either gesture; its first update took5.389/5.357s.
The fair queue returned six updates during each gesture, five with changed
pixels. Its first update took0.707/0.706s; the first changed window strip
arrived at1.634/1.670s. Those strips contain more changed bytes than the
cursor's entire bounded path, corroborating actual window movement.

These are protocol-harness samples with an unchanged native boot, not
physical input-to-panel latency or native-client human smoothness acceptance.
Whole-screen refresh and drag smoothness remain open. No native image,
NVMe content, command admission, app consent or listener scope changed.

`os/aiueos/scripts/aiueos-console-macos.py --config PRIVATE_CONFIG` starts
the adapter. The owner-only JSON configuration names `sshHost` (only
`itonami-6600h`), `vncPassword` (an owner-only eight-byte file), optional
`vncPort` (default22078) and `frameInterval` (default0.03s). The existing
SSH management setup, host-key pin, forced-command policy and private
credential directory must already exist. The local LaunchAgent uses that
configuration; credentials, sockets and machine setup are not repository
artifacts. Connect Screen Sharing to `vnc://127.0.0.1:22078`. Its Keychain
lookup uses the exact `127.0.0.1:22078` endpoint name. No password is printed
or placed in process arguments. Use the endpoint address explicitly when an existing connection for the
same loopback host has a different name.

## Native input and bounded readback

Signed command18 carries a finite absolute x/y position and the left button;
command19 carries a keyboard make code1..127. They enter the existing native
mouse/window and keyboard reducers. While a native choice is pending, left
presses and keys other than Deny/Escape are refused. The viewer never uses
the older administrative key command to approve a request. This does not
implement trusted remote approval for app operations.

Command20 reads at most32 framebuffer rows. Each `AIUEBND2` packet names the
boot nonce, request counter, dimensions, row, chunk, format and valid pixel
count. The host rejects stale identities, changing geometry, incomplete
bands and conflicting duplicates. Final partial chunks zero their unused
pixels instead of reading beyond the framebuffer. The existing direct-cable
screenshot transport is retained; packet identity is not a claim of encrypted
or independently authenticated screenshot contents.

Keys and button edges keep their order. Adjacent motion can coalesce, but
the initial press coordinate is retained even when queued behind another
command. Captures yield between bands to queued input. Disconnect cancels
unsent input and drains a final nonce-bound left release before another
client can start. A boot change invalidates the session. Incremental RFB
requests scan unchanged bands until an input pulse or a one-second heartbeat
returns a valid strip, and an
authenticated idle session does not expire after30 seconds. Clipboard data
is discarded; there is no file transfer or arbitrary command interface.

## Evidence and limits

Source-bound receipts and screen readbacks are under
`docs/evidence/awai119-mac-console-20261102/`:

- 35-module native QEMU component: coordinate/key/modal/band admission,
 ten refusals, actual header encoding including unsigned nonce high bits,
 and the final partial framebuffer row. This is explicitly a NIC-less
 component with a deny-all user ABI; it does not replace product execution.
- 44-module product reproduction plus the normal12 USB/NVMe regression
 events, and a separately packaged no-install PXE USB/hub smoke.
- 6600H signed key/pointer operations, screenshots showing Goal `aba` to
 `abaa` and back, and a window moving from(2,36) to(12,66). Pending Y/left
 press, out-of-viewport input and a stale session were refused. Deny/Escape
 returned to the app with approval0. No physical mouse action was requested.
- Nine host protocol tests cover the system DES known-answer vector, failed
 authentication before backend access, RFB versions/pixels, bounded keys,
 clipboard discard, band failure controls and queued drag edge preservation.

The subsequent persistent-channel candidate reuses one authenticated SSH
session for status, nonce-bound pointer/key input and screenshot bands. The
framed protocol caps requests at1024 bytes and replies at1MiB, requires rising
request identities, and refuses administrative reboot/type/USB commands.
Every operation still takes the shared management lock and performs native
nonce/signature admission. Transport failure closes the channel without
replaying ambiguous input. Authentication/capture failure and disconnect
retire the session. The adapter remains a Mac administration bridge.

`persistent-channel.json` records a sequential ABBA hardware comparison with
no connected RFB client and one native boot. Pooled status medians were
0.250s versus0.144s;32-row bands were0.333s versus0.221s. Baseline full captures
took5.84–7.28s and persistent captures3.97–4.34s. The final lifecycle-cleanup
revision has a separate repeat in the same receipt. Eight channel tests
exercise framing, denied operations, malformed/repeated identities, generic
private failures, response bounds and no replay after an ambiguous input
timeout. At that stage the RFB suite had ten tests, including failed initial-capture
cleanup. Actual signed hover motion changed only the expected cursor pixels;
reboot, stale-nonce key input and an invalid pointer were refused. These
measurements do not qualify Sidecar responsiveness or native OS SSH.

The local loopback console was restarted on the committed candidate and
passed wrong-password refusal plus two authenticated800x600 RFB captures
across disconnect/reconnect. Authentication-to-first-frame took6.00–6.45s
in these live sessions; this is distinct from the isolated3.89s backend
capture and still leaves substantial interactive latency. See
`persistent-deployment.json`. The existing SSH listener and native PXE boot
were preserved, and the post-test signed status returned the same boot nonce.

The actual Mac Screen Sharing app displayed the desktop, entered `r`
(independent band readback `abar`), deleted it and opened Murakumo by pointer
click. A separate real loopback RFB wire session drove signed drag/typing
through the live host adapter and board: the Itonami window reached(16,46),
Goal became `abar`, then Backspace restored `aba`. CUA-driven Mac drag sent
initial hover/down but no motion/release packets in the private bounded trace;
manual native-client drag acceptance remains open. The wire/session and
physical reducer checks do not establish human drag smoothness.

The first band candidate stopped replying on hardware after unaligned u32
identity stores; byte stores replaced them. Two subsequent full candidates
were refused by the unchanged native code budget (E7104 details2098577 and
2098049). A shared byte encoder and one-use preparation inside the actual
band entry fit the existing target. No grant, code budget or feature was
removed or widened. The measured RX PT_LOAD size is recorded separately
from the compiler's internal generated-code admission budget.

The old full screenshot took about3.03s on this machine; the first32-row
band took about0.32s. A complete bounded initial capture took about5.76s.
These are host-observed command/capture times, not input-to-display latency
or Sidecar performance. Progressive scanning, native GOP cost and SSH
per-command overhead still limit smoothness. Hardware boot is a PXE
development candidate, not an installed/released OS update.

Remaining: low-latency dirty-region streaming/encoding, right/middle/wheel,
modifier chords, uppercase/general Unicode/IME, clipboard policy, dynamic
resolution, reconnect/held-button fault qualification, trusted remote app
consent, OS-native SSH and Kekkai transport. Physical Trackpad/HHKB acceptance
is owner-paused; JUN-502 drag/flicker and AWAI-121 ChromeOS parity stay open.
