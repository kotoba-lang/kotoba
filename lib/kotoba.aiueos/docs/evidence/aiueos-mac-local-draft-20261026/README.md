# Mac native local-draft and unattended debug (2026-10-26)

The ordinary desktop build entry ran on Apple Silicon with
`AIUEOS_NATIVE_DESKTOP_PROFILE=local-draft`. One pinned, signed Mac Amu
compiler and one pinned Kotoba packager built the font, 31-module
`workspace-entry.kotoba` kernel, EFI and 8 MiB GPT/FAT16 media. That exact
media booted under QEMU TCG in the same build invocation. The
[integrated receipt](integrated.json), [font](font.json),
[kernel](kernel.json), [media](media.json), [QEMU](cold-restore.json), and
[native queue admission](build-admission.json) bind the stages. The 8 MiB
media SHA-256 is
`c7d4088475ac68944e5c28d94c206a74abf4063d08252545bfbfe89ffbc7671b`;
the kernel ELF, EFI and media match the exact-source Linux arm64 comparator
byte for byte. This Mac invocation did not run a Linux, JVM, Node or C
compiler process. The historical initial Mac Amu bootstrap has separate
provenance.

The isolated QEMU restart gate passed 11 observations with no NIC, VNC
listener, VNC password or manual keys. It used private QMP standard I/O to
open Itonami, type a Goal, commit with F5, start a new QEMU process, restore
the committed Goal, lose an uncommitted edit after process kill, and reject
malformed or missing scratch media. It checked actual scanout pixels at
the native draw positions in the [committed](committed-ab.png),
[cold-restored](restored-ab.png), and [orphan-refused](restored-abd.png)
screenshots. The `a` and `b` glyphs each had 23 and 25 dark pixels in the
first two screenshots. These are disposable 64 KiB plaintext test disks.

The separate [one-shot debug receipt](one-shot-debug.json) and
[screenshot](one-shot-debug.png) show the routine debug path on the Mac-built
media. It booted a fresh VM, sent `2`, `a`, `b`, asserted exact guest state,
and verified both visible glyphs. Its [queue admission](debug-admission.json)
records exit 0. QMP used private standard I/O, and both `vncUsed` and
`networkUsed` are false.
Additional one-shot [space](space-goal-debug.json) and
[repeated-letter](repeated-goal-debug.json) receipts passed `a b` and `aa`,
including the visible Goal assertion. The debugger maps its `space` choice
to QEMU's `spc` qcode.

The default RAM-only desktop profile was rebuilt through the same changed
entry afterward. Its [integrated receipt](normal-profile-integrated.json),
[12-event QEMU receipt](normal-profile-qemu.json), and
[queue admission](normal-profile-admission.json) passed. This checks that
selecting the new profile did not break the default diagnostic desktop.

For routine debugging, run the unattended wrapper. It creates a fresh
observation directory automatically and checks the Itonami Goal in guest
memory and on the captured screen:

```sh
python3 os/aiueos/scripts/debug-native-desktop-unattended.py "$BUILD" \
  --goal debug
```

No screen sharing, password, or manual guest key input is required. The
command prints the receipt and screenshot paths. Set `BUILD` to the matching
Mac native `local-draft` build; all outputs stay beside that build under
`github/workspaces/`.

For a custom key sequence or assertions, use the lower-level debugger with
a fresh output directory:

```sh
python3 os/aiueos/scripts/debug-native-desktop-qmp.py \
  --build-dir "$BUILD" --local-draft --output "$OBSERVATION" \
  --keys 2 a b --expect-focus 2 --expect-draft-enabled 1 \
  --expect-generation 0 --expect-restore-code 0 --expect-commit-code 0 \
  --expect-goal $'Goal local:\nab' --expect-visible-goal ab
```

Set `BUILD` to the matching Mac native `local-draft` build and
`OBSERVATION` to a new private directory under `github/workspaces/`.
`--build-dir` resolves the exact media, EFI, kernel and font. The guest
performs save and restore; Python only drives QMP and checks the result.

This is a local diagnostic VM candidate. The probe is not a D2 workspace
image, signed Cell head, registered Itonami dapp, distributed persistence,
release or physical hardware qualification.
