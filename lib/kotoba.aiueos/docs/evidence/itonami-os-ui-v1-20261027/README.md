# Native desktop UI v1 (ADR-0275 items 1 and 2, partial)

Built on the kotoba#905 tree with the signed Mac Amu compiler and packager (amu `844ad77ba`), distribution `awai`; the
macOS native desktop QEMU check printed `MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE` (QEMU TCG, synthetic keys, no NIC).

- Launcher row: right-aligned status area, a green dot and "local only" (ADR-0275 W2, first slice: static text, not yet a
  counter or wallet/DID state).
- Itonami goal line sits in an input box (blue edge while focused).
- App window bodies say plainly that nothing is connected.
- Dock: a short bar under an app tile that has a window, a longer bar under the focused one.

`itonami-goal-ab.png` is the screenshot from that run. Not done here: parity vectors for the new ops, minimized state, field
box, consent surface. Diagnostic candidate, not a release.
