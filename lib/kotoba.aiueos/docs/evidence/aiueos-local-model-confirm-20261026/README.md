# Native local-model confirmation after Goal restore (2026-10-26)

The [Mac native build receipt](build.json) records one signed Amu selfhost
compiler generating the [Kotoba user program](../../../os/aiueos/native/itonami-local-model-user-v2.kotoba),
its AIUP v2 slot, the AIUEOS kernel and the dual-payload EFI. The user ELF
and slot were each generated twice with identical bytes, as were the kernel
and EFI. The user ELF SHA-256 is
`6d5ec74da6197788a5e778b8903cc40f001602c4c19cb4701d2620a948208e6d`;
kernel and EFI SHA-256 are respectively
`40b2d5baf8729ae3612bd2ae5cc1ca315545e9b7ad3ff41bc0348aea9bbf2469`
and `6cc21dea18ca1141341e46ddb1f4370c056fc31a9af2a85ec47f6959f7a5135f`.
An independently staged user slot produced byte-identical kernel and EFI
images. The builder's existing `--user-slot` path also rebuilt and passed
its [prior Goal save/restart QMP gate](existing-slot-debug.json). A wrong
user-source SHA-256 was refused before an output directory was created.

The [private-QMP receipt](debug-summary.json) records three fresh QEMU boots
with an output-owned marked 64 KiB draft disk. Boot 1 saved `awai a` from
Itonami. Boot 2 cold-restored the Goal and showed [the operation prompt](approval.png):
`AIUEOS local model Goal? y/n`. QMP pressed `n`; the user request stayed zero
and the guest stayed at CPL0. QMP requested the operation again and pressed
`y`; the native `aiueos-char-bigram-v1` transition row for final character
`a` produced token `i` (code 105). The pinned user-v2 program read that token
in CPL3 and returned 105. Boot 3 changed one byte of the slot's executable
code. The guest refused it at CPL0 before copying user pages or running the
model. The draft disk was unchanged by the inference and refusal boots.

Run the headless gate on a matching Mac native build:

```sh
python3 os/aiueos/scripts/debug-native-itonami.py "$BUILD"
```

This entry selects the source-bound gate from the build receipt and writes a
top-level run receipt plus logs, including on failure. The direct
`debug-native-local-model-confirm-qemu.py` gate remains available for detailed
guest work.

The unified entry passed against the local-model build (three QEMU boots,
including restored Goal and changed-slot refusal) and the older durable-Goal
build (two boots). A negative control using `/usr/bin/false` as the QEMU
executable returned `FAIL` and exit 1, while preserving `debug-run.json` and
the QMP traceback in `stderr.log`. The successful local-model run printed both
guest screenshot paths. These runs required no Screen Sharing login, password
or manual guest input.

The builder now accepts a pinned local `--user-source`,
`--user-source-sha256` and `--user-elf-sha256` in place of an existing
`--user-slot`; its other compiler, font, kernel source and owner source pins
remain required. QEMU uses private standard I/O QMP, no VNC listener,
password, NIC or manual guest key press. Synthetic test keys verify the
native decision path; they do not establish that a human approved an
external operation.

This is a one-token local model operated by the native host. The user-v2
program consumes the result from a bounded diagnostic input word at offset
60. It is not a user-space `:llm/generate` call, a tool effect, an agent
loop, or a general signed app admission. The local draft is plaintext Goal
text; D2 workspace reconstruction, trusted external-operation approval,
release and physical qualification remain open.
