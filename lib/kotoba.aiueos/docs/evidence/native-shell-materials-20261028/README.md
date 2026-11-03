# Native glass materials and interactive home (JUN-143)

Owner direction, 2026-10-28: make the AIUEOS / Itonami OS shell interactive
and enjoyable, inspired by Apple Liquid Glass and Nintendo Switch 2.
This supersedes the earlier DADS-only colour direction for this work.
Existing readability, keyboard access and operation-consent boundaries remain.

Design references: Apple's [materials guidance](https://developer.apple.com/design/human-interface-guidelines/materials)
and [Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)
inform the use of translucent navigation/control layers above opaque readable
content and a reduced-effects alternative. Nintendo's [system menu overview](https://www.nintendo.com/en-gb/Support/Nintendo-Switch-2/Nintendo-Switch-2-System-Menu-Overview-2914762.html)
is a reference for a clear home/application relationship. Our card layout,
colours, geometric symbols and keyboard/pointer feedback are original choices,
not a port of either platform's UI or a claim of matching their interaction quality.

## Implemented

- Native RGB565 gradient wallpaper and app tiles; rounded solid and alpha-tinted
  glass primitives, including real compositing against the framebuffer below.
- A four-card home with original cloud, conversation, workspace-grid and page
  symbols. Clicking a card or using Left/Right and Enter opens its existing
  diagnostic window. Selection wraps; Escape cancels without launching.
- The dock shows a label and visible selection outline. Hover lifts/enlarges
  a tile; pressing compresses it; release restores it. Card hover/press states,
  rounded launcher/control feedback, window edges and tinted shadows use the
  same retained list and native presenter.
- F10 switches to opaque materials and stationary tiles/cards. Selection,
  text, input and focus remain available. This is a session-only local setting.
- Existing F6 minimize/dock restore, F9 fold, Goal input and consent remain.
  A pending consent request consumes navigation/effect keys before they can
  operate the shell. These visual flags never contain approvals or capabilities.

The surface stays 8192 bytes / 259 ops. Material ops retain the six-word
format: 3 rounded solid, 4 rounded `0xAARRGGBB` glass, 5 rounded gradient,
6 rectangular gradient. Radius is capped at 12 and half the smaller dimension;
gradient endpoints are RGB565 halfwords. Pointer-y's low 16 bits remain the
coordinate; high bits hold press/reduced-effects/dock-selection display state.
The native context retains the local selection and preference. A refused
renderer result, stored as u32, cannot be walked as an enormous op count.

## Native evidence

`source-pins.json` binds the six sources/observers to final implementation
commit `cca7ff337` (material/home `1fb328b59`, exact blend cache and synchronized
input `f226e60ab`, terminal handoff observation `e5cb8a289`, distribution-neutral
shared heading `cca7ff337`). The home says "Your space"; distribution branding
remains a composition/configuration concern.
The signed Mac Amu selfhost root is `9d023d99...`. Kotoba emits
font/kernel/EFI/media; Python stages, hashes and observes native execution.
No JVM, NBB, Node, C compiler, host UI compositor or Linux guest supplies the UI.

`desktop-build.json` reports `MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE` with
`nativeShellMaterialsQualified=true`. The exact GPT and EFI El Torito ISO
images each pass the existing 21-operation window/input/restore gate.
The separate shell-material gate uses the exact same native artifacts and
reports `PASS_NATIVE_SHELL_MATERIAL_QEMU` with nine observations:

1. Gradient and rounded corner pixels, plus the expected alpha-composited dock pixel.
2. Keyboard focus, wrapping in both directions and Escape cancellation.
3. Keyboard app launch followed by actual Goal text input.
4. Hover's exact retained 40x40 tile rectangle and scanout.
5. Press's exact retained 34x34 tile rectangle and changed scanout.
6. Release preserving the window and Goal without a pending external operation.
7. F10: opaque glass pixel and stationary 36x36 tile.
8. Effects restored with the Goal intact.
9. Pointer launch from the large home card, retaining the same Goal.

All observed lists stay within the 259-op bound (164-199 in these material
cases); the observer also checks every op's viewport bounds and the native
renderer error/overflow fields. `home.png`, `keyboard-focus.png`,
`dock-hover.png`, `dock-pressed.png` and `reduced-effects.png` are actual QEMU
scanout screenshots. They are not browser mockups or generated images.

`draft-build.json` and `draft-qemu.json` retain the integrated local-draft
regression: native ATA commit, cold restore, uncommitted-crash recovery and
all named malformed/missing-medium refusals, 12 observations.

`consent-build.json` reports `MACOS_NATIVE_CONSENT_QEMU_CANDIDATE` and
`consent-qemu.json` records all 20 expected consent/key/passphrase/signing
observations, including background-operation refusal and Goal persistence
after key creation. The final input/frame-synchronous observer and both of
its helper sources are digest-bound to this build. The consent panel remains
opaque and modal; the new material/navigation state grants nothing.

The alpha presenter caches only the immediately previous underlying pixel's
exact blended result, resetting the cache for every row. It still reads each
underlying pixel and recomputes when that pixel changes; text under glass is
never approximated as a uniform band. The source-fixed pre/post-cache scanouts
in `cache-scanout-comparison.json` were byte-identical. That comparison predates
the final neutral heading: its hashes describe the earlier build pair, not
the final screenshots above. No speedup or frame-rate claim is derived.

An earlier fixed-delay consent run failed its passphrase-length assertion.
The final observer uses private QMP bulk memory snapshots and waits for both
input consumption and a completed guest frame before sending the next event.
After the final model Allow, the desktop intentionally hands control out of
its input loop: the observer releases its host-injected button only when the
guest reports stop=1, pending=0, approved=1, and performs no further guest
action. Failed attempts remain outside the accepted receipts. This serial
input check does not qualify burst-input throughput or physical-machine latency.

## Reproduce and scope

From `lib/kotoba.aiueos`, run the existing native entry on Apple Silicon:

```sh
AIUEOS_NATIVE_DESKTOP_OUT=/new/private/output \
AIUEOS_DISTRIBUTION=awai \
AIUEOS_NATIVE_DESKTOP_PROFILE=desktop \
os/aiueos/scripts/build-kotoba-native-desktop.sh /path/to/pinned/amu
```

The integrated desktop entry now requires GPT, ISO and shell-material gates.
Use fresh outputs with `consent` and `local-draft` for their separate gates.
All test input is synthetic, with no NIC or physical disk and no trusted human
approval of an external operation.

This is an event-driven native diagnostic UI slice. It implements tint/alpha,
rounding, gradients and discrete interaction feedback. Backdrop blur, optical
refraction, timed/spring animation, a qualified frame rate, audio/haptics,
persisted accessibility preferences and physical-machine usability remain open.
The cards still open diagnostic windows: full Browser/CSSOM parity, registered
dapps/Kaikei, a canonical D2 workspace, signed Cell state and a public release
are separate gates. No production route is changed.
