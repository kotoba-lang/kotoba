# ADR-0275 W1: the consent surface (native desktop)

Built with the signed Mac Amu compiler `4350f3ba…` (kernel-v3 capable, from the JUN-450 selfhost closure), the
`awai` distribution, `--kernel-target x86_64-aiueos-kernel-v3` (now the driver default). The macOS native desktop
QEMU gate prints `MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE` (QEMU TCG, synthetic keys, no NIC).

## What it is
With surface word 2039 = 1 the frame is the consent surface and nothing else: background, launcher, one panel that
names service, endpoint, action and data, and Allow / Deny. No window or dock is drawn, so no app can paint over or
imitate the panel; about 180 of the 259 ops are used. The text is static: it states what this build asks and grants nothing.
desktop.kotoba sets word 2039 when the existing local-model Y/N prompt opens and clears it on either answer. Allow/Deny
are the keys Y and N/Esc and the two button rectangles; while the request is pending every pointer press is consumed
by the panel, so nothing under it can be clicked.

## Checked (profile-4 throwaway build, QEMU HMP, not part of the gate)
- Enter in the Itonami window opens the panel (`consent-surface.png`).
- N and Esc return to the desktop with the Goal intact; a pointer click on Deny does the same (`after-deny.png`).
- A pointer click on Allow takes guest words 87/88/85 from (pending 1, approved 0, stop 0) to (0, 1, 1), the same as Y.

## Not checked / limits
- The standard gate does not open the panel (it appears only on the goal-model profile); the checks above are manual.
- QMP/HMP keys and clicks are synthetic and do not prove a human consent.
- Why kernel-v3: kernel-v1's packager admission (amu seed/84-aiueos-boot.kotoba `eb-admit?`) requires RX to end below RW at
  0x200000, i.e. at most 1,044,480 code bytes; this build is 1,048,064. kernel-v3 puts RW at 0x400000 (about 3 MiB for code).
- The repository bootstrap compiler is v1-only, so the driver now refuses it with that explanation instead of failing in the packager.
- check-native-desktop-qemu.py's expected CR3 depends on the layout (RW 0x200000 -> 0x30000, 0x400000 -> 0x130000); an unknown layout fails closed.

## Gate (added)
`build-native-desktop-macos.py --profile consent` builds `native/consent-entry.kotoba` (the goal-model profile) and boots it
under `scripts/check-native-consent-qemu.py`, which reads guest words with `xp` and pixels from `screendump`:
the panel opens (Allow pixel, border, dock not drawn), a launcher key and a launcher click do nothing while it is pending,
N, Esc and the Deny button deny (Goal intact, approved 0), and the Allow button approves exactly as Y does
(pending 0, approved 1, loop stop 1). Receipt: `native-consent-qemu.json` (status `PASS_NATIVE_CONSENT_QEMU`, 9 events).
Synthetic HMP input proves no human consent. The earlier manual checks above are superseded by this gate.
