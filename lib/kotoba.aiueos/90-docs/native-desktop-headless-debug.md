# Native desktop debugging without screen sharing

The native AIUEOS diagnostic desktop can be debugged through QEMU QMP.
VNC, a VNC password, and a person pressing guest keys are unnecessary.
The headless restart gate uses QMP over private standard-input/output pipes,
with no listener, and `-nic none`. It creates mode 0700 session directories
for guest memory dumps and screenshots. An already running interactive VM can
instead be inspected through its local QMP Unix socket; keep that socket in a
mode 0700 task directory because it controls the VM.

For routine agent debugging, use the headless QEMU gates and this QMP observer
first. They read the guest's completed frame, goal, focus, draft generation,
and framebuffer directly. Do not request a Screen Sharing login or a manual
key press to establish those facts. Keep the VNC password on any separately
shared interactive session; QMP does not require disabling it.

## One-shot Itonami UI debug (no listener or login)

For a completed Mac native user-v2 build, use one command. It reads the
`kernelEntry` in `build-state.json` and selects the matching live Goal, durable
Goal or local-model gate. It boots new isolated QEMU guests and saves the gate
receipt, standard output, standard error, screenshots when available, and a
top-level `debug-run.json` even when a guest check fails:

```sh
python3 os/aiueos/scripts/debug-native-itonami.py "$BUILD"
```

For a native local-model build with a matching Kotoba-built GPT/FAT16 image,
pass `--boot-media "$MEDIA"`. The positive save/restore/model boots read that
image through QEMU's snapshot drive; the separate altered-slot refusal boots
its modified EFI through an isolated FAT directory. The gate verifies the
disk's EFI bytes before boot and checks the media digest again afterwards.
The marked 64 KiB Goal draft disk remains an output-owned fixture.

Use `--goal 'a b'` for live or durable Goal builds. The local-model gate also
accepts a 1–51 character lowercase Goal ending in a letter with a nonempty
model row, for example `--goal 'awai s'`. It reads the frozen transition
contract to derive the expected token and checks the entire guest Goal region
and syscall request. The command prints the receipt path and
returns nonzero on failure. Read `stderr.log`, `guest/boot-2/last-state.json`
when present, and the QEMU logs under `guest/`. It uses private QMP standard
I/O, no VNC, no network and no password. QMP's synthetic Y/N keys only test
the guest's branch behavior; they are not human consent for a real external
operation. Use a fresh user choice at the trusted operation boundary in a
product run.

Use this command for each technical regression or restart check, including
after a fresh native build. The receipt identifies the exact build and gate;
keep that receipt with the issue or PR evidence. Screen Sharing and a person
typing test keys are optional interactive UX review, not a prerequisite for
debugging or for reproducing the automated result.

For a Mac native dual-payload user-v2 build, give its build directory to the
unattended user debugger. It validates the build receipt, extracts the pinned
ELF from the staged user slot, boots fresh isolated QEMU guests, types the
chosen Goal and a distinct control Goal into the real Itonami desktop, and
checks the CPL3 endpoint, empty Goal refusal and changed-slot refusal:

```sh
python3 os/aiueos/scripts/debug-native-user-v2-unattended.py "$DUAL_BUILD" \
  --goal 'debug run'
```

The command creates a mode 0700 observation directory beside the build and
prints `debug-summary.json`, the full QMP receipt, and the first guest
screenshot path. QMP uses private standard I/O. This path opens no VNC or
network listener and never asks for a password or manual key press. It does
not write to a live user VM; each boot uses a fresh test EFI under the
observation directory. `--output` selects a new private directory. This is
a diagnostic CPL3 length-result program, not a model/tool turn or a durable
user workspace. Native per-operation consent remains a separate acceptance
gate; this debugger does not grant it.

For the routine check, give one complete `local-draft` build directory to the
unattended entry. It creates a new private observation directory beside that
build, types a lowercase Goal through private QMP, asserts the guest state and
visible text, then prints the receipt and screenshot paths. No Screen Sharing
login, VNC password, or manual key press is involved:

```sh
python3 os/aiueos/scripts/debug-native-desktop-unattended.py "$BUILD" \
  --goal 'a b'
```

For the UI and persistence check together, run:

```sh
python3 os/aiueos/scripts/debug-native-desktop-unattended.py "$BUILD" \
  --goal 'a b' --verify-restore
```

This creates a separate scratch disk under the private observation directory,
checks F5 save and a cold boot in a new QEMU process, then runs the refusal
cases. The printed `restoreReceipt` points to that gate's result. The typed
Goal in the quick UI check and the save/restart gate's fixed `ab` fixture are
separate observations; the former is not claimed as a committed workspace.

Keep `BUILD` under `github/workspaces/` so the default observation directory
is scratch rather than a repository file. `--output` selects another new
private directory. The command starts a fresh isolated VM; it does not attach
to or modify an interactive user's VM. The underlying QMP observer remains
available for individual keys and expected-state checks below.

Use the same observer with `--build-dir` to launch one fresh VM. This route
uses private QMP standard-input/output pipes, opens no VNC or QMP listener,
and runs with `-nic none`. Set `BUILD` to the matching native `local-draft`
build directory and
`OBSERVATION` to a **new** scratch directory under `github/workspaces/`:

```sh
python3 os/aiueos/scripts/debug-native-desktop-qmp.py \
  --build-dir "$BUILD" \
  --local-draft --output "$OBSERVATION" \
  --keys 2 a b --expect-focus 2 --expect-draft-enabled 1 \
  --expect-generation 0 --expect-restore-code 0 \
  --expect-commit-code 0 --expect-goal $'Goal local:\nab' \
  --expect-visible-goal ab
```

The script resolves the media, EFI and kernel from that one build directory,
finds QEMU on `PATH` and its bundled OVMF firmware, and validates that the
kernel is inside the matching EFI/media before booting. Explicit
`--boot-media`, `--efi`, `--kernel`, `--qemu` and `--firmware` remain available
for unusual layouts. A fresh build-directory run is recorded in the
[headless debug receipts](evidence/headless-debug-20261026/README.md).
`--local-draft` creates a fresh, marked 64 KiB test disk *inside*
the private output directory; it never accepts an existing workspace or
physical disk as a writable draft target. The session ends after the last
frame. `debug.json` contains the assertions, source and image digests,
`desktop.png` shows the actual guest display, and `command.json` records
the QEMU launch. A wrong expectation exits nonzero and still saves the
framebuffer. F5 remains guarded by `--allow-draft-write`; use the isolated
restart gate below to test commit and recovery.
`--expect-visible-goal` checks dark pixels at the guest's native text draw
positions using the exact font inside the build's EFI. A passing
`--expect-goal` alone checks guest memory. The observer accepts lowercase
letters and `space` in `--keys`; visible assertions also handle spaces and
repeated letters.
`draftEnabled=1` means the opt-in profile is active; it does not prove a
medium was attached. Without `--local-draft`, the guest reports restore code
`-22` on this image, so assert the restore code when checking persistence.

## Reproducible save and restart check

Run [`check-native-draft-restart-qemu.py`](../os/aiueos/scripts/check-native-draft-restart-qemu.py)
with a newly built `local-draft` media, matching EFI and kernel, QEMU and
OVMF firmware, and a fresh output directory. The complete command and
artifact roles are in [AWAI-90 progress](native-workspace-restore-progress.md#reproduce-the-component-gates).
The observer provisions its own 64 KiB scratch draft disk, sends PS/2 keys
through its private QMP pipe, checks native guest state and framebuffer,
commits with F5, boots a new QEMU process, and verifies the restored bytes
and rejection cases. It never opens a VNC or QMP listener. This path ran in
the default local sandbox on 2026-10-26 without a socket-bind exception or
human input; see the [stdio gate receipt](evidence/headless-debug-20261026/qmp-stdio-gate.json).

## Inspect a running VM

For a VM started with `-qmp unix:qmp.sock,server=on,wait=off`, set these
paths to the running VM's socket, the exact kernel ELF in its EFI image, and
a **new** output directory:

```sh
python3 os/aiueos/scripts/debug-native-desktop-qmp.py \
  --qmp-socket "$SESSION/qmp.sock" \
  --kernel "$BUILD/kernel/KERNEL.ELF" \
  --output "$OBSERVATION" --keys 2 \
  --expect-focus 2 --expect-draft-enabled 1 \
  --expect-generation 0 --expect-goal $'Goal local:\n'
```

The script waits for a completed native frame, sends the requested keys,
reads the guest's actual desktop surface and context, and saves `debug.json`,
`desktop.ppm`, and `desktop.png`. With no `--keys`, it only observes. Supported
debug keys are `2`, lowercase `a` through `z`, `space`, `backspace`, `esc`, and `f5`.
State expectations produce a nonzero exit and a `FAIL` receipt with actual and
expected values when they differ. The screenshot is captured on either result.
Sending F5 to an attached VM requires `--allow-draft-write` because it can
commit to that VM's draft disk. Use the isolated check above for routine
write and cold-restore tests.

The exact matching kernel is required: the observer derives the context
address from it. A successful QMP read is a diagnostic observation of that
guest, not proof of a registered Itonami dapp, D2 workspace, hardware boot,
or Linux-free compiler closure.

On 2026-10-25, the debugger attached to the running `local-draft` VM on port
5902 through its QMP socket. It read `Goal local:\n`, `draftEnabled=1`,
`frames=1`, then sent `2` and observed `focus=2`, `keys=1`, `frames=2`; the
captured framebuffer displayed the Itonami card. No VNC authentication or
manual guest action was used for that observation.

On 2026-10-26, a fresh headless run of the save/restart gate passed all
positive and rejection cases without a VNC session. A separate QMP read of
the still-running diagnostic VM sent `2`, saw `focus=2`, `keys=2`,
`framesStarted=frames=3`, `draftEnabled=1`, and captured the Itonami card.
The [headless debug receipts](evidence/headless-debug-20261026/README.md)
include a failing expected-focus control. These are VM diagnostics, not
physical-device or full Itonami-agent acceptance.

An independent readback later that day attached to the same running :5902
VM without Screen Sharing. Sending `2` yielded `focus=2`, `keys=3`,
`framesStarted=frames=4`, `draftEnabled=1`, `generation=0`, and exact goal
`Goal local:\n`. The QMP screenshot visibly contains the Itonami card.
The [live receipt and screenshot](evidence/headless-debug-20261026/README.md)
record this run. The shell's restricted sandbox required local QMP socket
access for the observer; it did not require guest credentials or user input.

## Full normal desktop gate on Mac-built media

`build-native-media-macos.py` emits a fresh Kotoba-built GPT/FAT16 image
using a pinned Mac Amu compiler and packager. Run
`check-native-desktop-qemu.py` with its `awai-native.img`, matching EFI,
kernel, font, QEMU and OVMF firmware, and a new output directory. The gate
uses QMP over private standard-input/output pipes, `-nic none`, a temporary
disk overlay, and no VNC listener. It sends keys and mouse events, checks
guest memory and framebuffer changes, and writes
`native-desktop-qemu.json` plus screenshots.
The [Mac build and QEMU receipt](../docs/evidence/aiueos-mac-native-build-20261026/README.md)
records a passing run without Screen Sharing or password input. Use the
separate local-draft restart gate above for persistence; this normal profile
keeps Goal in RAM.

The [integrated Mac run](../docs/evidence/aiueos-mac-integrated-20261026/README.md)
uses the ordinary desktop build entry and checks the actual QEMU scanout
pixels for the Goal's `a` and `b` glyphs. Waiting only for the
guest text buffer allowed an earlier screenshot of an incomplete frame;
the current gate requires a completed frame and visible glyph ink.

The [Mac local-draft run](../docs/evidence/aiueos-mac-local-draft-20261026/README.md)
also runs F5 commit and cold restore without a person or password. It checks
visible text in committed and restored QEMU screenshots. The ordinary build
entry selects this diagnostic profile with
`AIUEOS_NATIVE_DESKTOP_PROFILE=local-draft`.

## User ELF boot-slot check

The [C-free user ELF diagnostic](../docs/evidence/aiueos-native-user-payload-20261026/README.md)
also runs through private QMP stdio. It checks actual CPL3 execution, a
modified-code refusal and an invalid-slot-header refusal in three isolated
QEMU boots. Its fixed scalar ELF is
separate from the Itonami desktop profile; a pass does not establish that
Itonami itself runs as a user ELF.
