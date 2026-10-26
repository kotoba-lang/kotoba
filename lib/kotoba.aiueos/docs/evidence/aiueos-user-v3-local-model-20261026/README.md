# User-originated local model call, headless QEMU (2026-10-26)

The [native build](build.json) used the Amu selfhost compiler to generate a
Kotoba [user-v3 ELF](../../../os/aiueos/native/itonami-local-model-user-v3.kotoba)
and a native [AIUEOS kernel](../../../os/aiueos/native/user-elf-v3-local-model-entry.kotoba).
The builder reproduced the ELF and EFI byte for byte. The user ELF SHA-256 is
`331a3ed64c5859bc546a36ce9666e1a1e17e31195caca96407def6f63f5cc7b1`.
The v3 compiler target emits a bounded 104-byte request and invokes syscall 5
from CPL3. The kernel validates the domain, selected user page, request shape,
current Itonami choice and local-model input before consuming the choice.

The [QEMU receipt](debug-summary.json) records three boots through the
[headless wrapper](debug-run.json). Itonami saved Goal `awai a` to a marked
draft disk, then restored it in a new QEMU process. The [operation prompt](approval.png)
was exercised with synthetic `n` and `y` keys. Denial left the user pages zero
and stayed at CPL0. After `y`, the user code created the request and received
token `i` (105) through syscall 5, with no host-prefilled token input; the
approval was consumed. A one-byte changed ELF slot was refused before user
execution. The draft disk remained unchanged by inference and refusal.

Run the same gate on a pinned matching build:

```sh
python3 os/aiueos/scripts/debug-native-itonami.py "$BUILD"
```

The [variable-Goal run](variable-goal-summary.json) used the same pinned native
kernel, user ELF and GPT/FAT16 media with `--goal 'awai j'`. The observer read
the frozen 27-by-27 transition contract, expected token `o` (111), and checked
the full OS-filled Goal region plus the user-originated syscall envelope. A
fresh boot saved that Goal, a second boot restored its visible glyphs, `n`
left the user pages zero, and `y` returned 111 to CPL3 with no prefilled token.
The third boot refused a one-byte changed user slot before execution. The
[wrapper receipt](variable-goal-debug-run.json), [restored frame](variable-goal-restored.png)
and [choice frame](variable-goal-approval.png) are kept with the run. The
observer also refused uppercase input and a Goal ending in a transition row
without output before launching QEMU, with [input refusal readback](variable-goal-input-refusals.json).
A separate `awai s` run returned token
32, rather than the original fixed Goal's 105.

To repeat the variable-Goal gate:

```sh
python3 os/aiueos/scripts/debug-native-itonami.py "$BUILD" \
  --goal 'awai j' --boot-media "$MATCHING_NATIVE_MEDIA"
```

It writes a run receipt, guest traces and screenshots on success or failure.
QEMU uses private standard-I/O QMP, with no VNC listener, password, NIC or
manual guest input. These synthetic keys establish guest control-flow behavior;
they are not human consent for an external operation. This is a fixed one-token
local model, not general LLM inference or an agent loop. Signed app admission,
external operation consent, D2 workspace recovery and physical qualification
remain open.
