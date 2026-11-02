# Mac remote console candidate (AWAI-119)

The development Mac can display the 6600H desktop in native macOS Screen
Sharing. The host adapter listens only on `127.0.0.1:22078`, authenticates
with a private VNC password, and uses the existing pinned-key SSH management
alias `itonami-6600h`. The actual OS ingress still verifies signed commands,
the current boot nonce and a rising request counter. This is a Mac host
administration adapter, separate from OS-native SSH, Kekkai and app runtime.

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
