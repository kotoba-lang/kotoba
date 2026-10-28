# Native window minimize and dock restore (JUN-143)

The native desktop retains an app's window, geometry and Goal when minimized.
F6 or the new leftmost titlebar control hides it; its dock tile or launcher
restores it. F9 remains a separate roll-up operation. Hidden windows retain a
running marker but cannot receive text, pointer hits or Tab focus. If every
window is minimized the focus is zero. Restoring never creates a second window.

The bounded native surface uses height bit 16 as its minimized flag and the
low 16 bits as the original height. The renderer admits exactly that flag,
validates the retained rectangle and refuses a hidden focused window. No
surface word or allocation is added. This is an extension of the diagnostic
native mirror; it does not qualify the complete shared Browser/CSSOM ABI or
close JUN-479's layout and constant-data work.

Every pending request kind now consumes pointer presses before window hit
testing; an existing drag cannot move a window behind a consent surface.
The former predicate covered only the local-model request, leaving the key,
sign and passphrase request kinds exposed to background window operations.
The consent logic itself and the authority represented by an approval do not
change. Test-injected input never proves trusted human consent.

## Verification

`source-pins.json` binds the five implementation/observer sources to commit
`87702c6ef`. The signed Mac Amu bootstrap is `9d023d99...`; native Kotoba
emits the font, kernel, EFI and media. Python only stages, hashes and observes.
No JVM, NBB, Node, C compiler or Linux guest is used.

`desktop-build.json` is the successful integrated Mac entry receipt:
`MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE`. The exact GPT medium and EFI El Torito
ISO both boot under QEMU TCG with no NIC. `desktop-gpt-qemu.json` and
`desktop-iso-qemu.json` each report `PASS_NATIVE_DESKTOP_INPUT_QEMU` and 21
semantic observations, including:

- Keyboard minimize with the other visible app taking focus.
- Hidden Goal refusing typing; Tab skipping hidden windows.
- All windows minimized: no window body, focus zero, dock running marker visible.
- Pointer dock restore: the same window count, position, size and Goal.
- The restored Goal's `a` glyph present in both retained ops and scanout pixels.
- Pointer titlebar minimize, launcher-key restore and the original input/close checks.
- Normal desktop F5 still leaving persistence disabled; media bytes unchanged.

Pointer substeps wait for completed guest frames and do not enter the semantic
event count. The initial fast injection overran the guest redraw loop; those
failed attempts are not acceptance evidence. Controller expectations were
updated from 12 events/two glyph checks to 21 events/three glyph checks for
both media types; they still bind the exact observer and artifact digests.

`all-minimized.png` and `restored-goal.png` are QEMU scanout screenshots from
the successful integrated run. `desktop-kernel-build.json` retains the locked
source closure and emitted artifact identities.

`draft-build.json` is the successful integrated local-draft entry:
`MACOS_NATIVE_DRAFT_RESTORE_QEMU_CANDIDATE`. `draft-qemu.json` reports
`PASS_NATIVE_LOCAL_DRAFT_COLD_RESTORE` with 12 observations. Native ATA commit,
cold restore, recovery of the last commit after an uncommitted edit/crash,
alternate generation and named malformed/missing-medium refusals still pass.
This remains the existing plaintext, unsigned diagnostic draft transport,
not the D2 workspace codec, signed Cell state or distributed durability.

`consent-build.json` is the successful integrated consent entry:
`MACOS_NATIVE_CONSENT_QEMU_CANDIDATE`. `consent-qemu.json` records
`PASS_NATIVE_CONSENT_QEMU` and all 20 expected observations. In addition to
the existing fold, Allow/Deny, key/passphrase, signing, draft-after-key and
approval-count checks, F6 and a dock click cannot act behind local-model
consent, and a background dock click cannot act behind the key request.
`consent-kernel-build.json` binds its distinct entry and complete source
closure. The ordinary desktop and consent profiles have different artifact
digests and are qualified separately. All inputs were synthetic; no user
approved an external operation through this test.

From `lib/kotoba.aiueos`, reproduce on Apple Silicon with the pinned Amu
checkout and QEMU installed, choosing a fresh private output directory:

```sh
AIUEOS_NATIVE_DESKTOP_OUT=/new/private/output \
AIUEOS_DISTRIBUTION=awai \
AIUEOS_NATIVE_DESKTOP_PROFILE=desktop \
os/aiueos/scripts/build-kotoba-native-desktop.sh /path/to/amu
```

Select `consent` or `local-draft` and a different fresh output for their
separate gates. They use throwaway marked scratch media, never a physical disk.

## Limits

This is a native diagnostic GUI improvement, not a registered dapp launch,
canonical workspace image, real accounting workflow, complete agent turn,
full Browser/CSSOM parity, physical hardware, public release or deployment.
Legacy hosted frame contracts are not counted as native parity evidence.
JUN-143, JUN-93, JUN-145, AWAI-90 and the relevant physical/release gates remain
open. Existing owner WIP and other worktrees are preserved.

ADR-0275's status paragraph still says the gate does not open the consent
panel. The actual consent observer opens it and checks its modal behavior;
that source/document mismatch was reported to Linear without editing the ADR.
