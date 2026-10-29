# Native GUI effects candidate (JUN-502–505)

Implementation source `739c05832` (effects `5357ad091`, PIT correction
`172d74147`, main key-state/lock integration `739c05832`) extends PR #965. It requires the native Amu
candidate in [Amu #1642](https://github.com/kotoba-lang/amu/pull/1642), whose
Mac selfhost fixed point is source-bound in that PR. Neither PR promotes a
root/public/CDCI role, performs a release or changes a production route.

## Behavior and budgets

The native desktop uses two independently PIT-calibrated TSC samples for
its monotonic millisecond timeline. A latched actual PIT count corrects late
polling rather than dividing by a nominal20ms; ambiguous/overlong samples
refuse, with at most two fresh retries at boot. A refused calibration disables timed
motion; discontinuities settle transitions rather than replay missed frames.
Input is drained in bounded batches before presenting. A new modal request
flushes currently queued input before drawing its panel. This is a diagnostic
input-order proof, not trusted human approval or a replacement for the shared
browser broker.

The shared `lib/kotoba.browser/src/browser/effects.kotoba` owns integer motion
and original PCM rules. Builders stage that exact file and lock its bytes;
there is no product-local fork, legacy compiler or host UI renderer.

- Dock/home motion uses an absolute elapsed-time curve with a bounded small
  overshoot and exact200ms settlement. Repeated input starts from the current
  position; F10 settles immediately. A titlebar drag samples bounded velocity;
  release velocity decays with sample age and uses180ms analytic friction.
- Real separable5x5 backdrop blur precedes tint and foreground controls. It
  samples immutable rows, extends viewport edges and is limited to192x192px
  surfaces. Larger titlebars retain tint, with a counted fallback. This is a
  small CPU blur, not optical refraction or a standard CSS filter engine.
- A previous retained-list cache derives a conservative damage rectangle.
  Closure includes whole intersecting blur layers and their halo; a bounded
  dependency overflow redraws everything. Opaque fills use aligned64-bit
  spans within each already guarded framebuffer page. Glyphs and alpha
  compositing obey damage clips. The full-raster control must produce identical
  scanout pixels. Idle effects stop requesting frames after settlement.
- Selection, confirmed window actions and cancellation generate original
  short triangle/attack/release PCM, with separate mute and volume. A strictly
  identified Intel8086:2415 AC97 adapter emits one finite1024-frame stereo
  s16/48kHz buffer; overlapping requests are dropped/counted. The QEMU WAV
  sink resamples to44100Hz. No device means silence and a usable UI.

The surface remains8192bytes/259ops. Amu exposes the previously unused final
16KiB of the existing private mapping; allocation size is unchanged. Explicit
byte map: metadata0..1023, first list-cache part1024..4095, blur4096..8015,
BDL8192..8447, PCM8704..12799, second list-cache part12800..15943.
The complete previous list is6216bytes, blur scratch3920bytes, BDL reservation
256bytes and PCM4096bytes. IME, draft, retained key, signing buffers and crypto
workspace do not alias these ranges.

F2 minimizes; F6 retains main's key Lock action. F4 toggles blur; F10 switches to opaque/stationary effects; F11 mutes;
F12 cycles25/50/75/100/0percent without changing mute. These are session
preferences. The home shows the controls and a volume indicator. F3 is the
native diagnostic full-raster comparison control, not an authority switch.
Every pending consent kind consumes these keys before shell preferences or
window state can change. F7 signing and F8 key consent retain their meanings.

## Evidence

`source-pins.json` binds implementation and observers. Desktop/kernel/build,
GPT and ISO input receipts, shell-material observations and three GUI effects
receipts bind actual native artifacts and their observers. The GUI observer
checks native blur pixel goldens against alpha-only, motion settlement,
reduced motion independent of mute, actual window feedback, an eight-key
burst without loss/order changes, blur off/on, independent volume and device
readiness, exact damage/full-raster scanout equality, pre-display queued-Y
refusal, modal preference refusal and idle frame cessation.

The audio-present boot records nonzero PCM in both the actual DMA buffer and
the device's WAV output. The muted boot has zero output (a header-only WAV is
valid when the device never starts); absence is tested in a separate boot.
This is native virtual-device output, not a host beep or physical speaker.
The standalone titlebar-inertia observer records a real PS/2 drag and a
bounded release displacement of7px on each axis in this run.

Separate consent and local-draft profiles preserve their20 and12 observations,
with main's additional eight-observation key-lock/store gate kept separately,
including passphrase/signing/modal checks, full-range Lock wipe checks, actual local ATA save, cold restore,
uncommitted-crash recovery and named refusal cases. They use throwaway marked
scratch disks, no NIC and no physical disk. Private keys/passphrases/raw RAM are not
published as evidence.

`metrics.json` reports guest-calibrated diagnostic frame samples. The sample
set includes startup, mode changes and intentionally forced full redraws;
these quantiles are not a quiet-host benchmark. Input latency starts at guest
consumption and ends when framebuffer writes complete, not at physical HID
or photon delivery. No60fps qualification follows from these receipts.

## Remaining gates

Reference hardware, speaker/device coverage, consistent16.7ms frame budget,
idle CPU/power, event timestamps under all burst loads and suspend/multicore
clock behavior remain open. Settings are not persisted. Timed window launch,
minimize/restore and scrolling, a full shared Browser/DOM/CSSOM graph, dapps,
canonical D2/signed state and daily-use/release qualification remain separate.
The current screen is Kotoba→Amu native→draw ops→framebuffer; it does not become
an HTML/CSS GUI or acquire standard Web API compatibility from these effects.
JUN-143 and JUN-502–505 remain In Progress until their full criteria are met.

## Reproduce

Build the Amu candidate with its existing queued Mac selfhost gate, supplying
explicit pinned bootstrap compiler/packager arguments; inspect the resulting
fixed-point receipt. In the GUI build, set all four existing override variables
`AIUEOS_AMU_SELFHOST_BIN`, `AIUEOS_AMU_SELFHOST_SHA256`,
`AIUEOS_KOTOBA_PACKAGER_BIN`, `AIUEOS_KOTOBA_PACKAGER_SHA256` to those exact
verified images. Then run `os/aiueos/scripts/build-kotoba-native-desktop.sh`
from this library with the Amu source root and a fresh
`AIUEOS_NATIVE_DESKTOP_OUT` under the task workspace. Use profiles`desktop`,
`consent`, `local-draft` and `keystore` in separate fresh outputs. The desktop
entry requires both media gates, materials and all three effects/device boots.
The separately pinned `check-native-window-inertia-qemu.py` takes that exact
kernel/EFI/font/media plus pinned QEMU/firmware. Do not assume the current
unpromoted default Amu root already exposes these new intrinsics.

The bundle provenance record had duplicate `added`/`files` sections. They are
consolidated with every prior record retained, then current source/addition
hashes are refreshed. The historical31-module sentence in AGENTS.md is not
rewritten as a new qualification claim: this closure has37 modules (38 for
`cid`). Native build, shared graph, Linux controller, physical and release
remain separate gates.
