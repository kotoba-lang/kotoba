# Native `llm-v1` result component in an AIUEOS guest

`os/aiueos/native/llm_v1_result_shape.kotoba` adds a proposed, bounded
transport for the kit's completion and error arms. A shared native UTF-8
validator is used by both request and result validation. A 64-byte result header
declares the arm, separate text/keyword/message lengths, usage counts and
retryable flag. The validator checks the paired request header, capacity,
output-token budget, exact lengths, zero padding and UTF-8. The host must
still provide distinct owned regions, the model and a valid grant. This is a
kernel component; it does not lower the nested kit value into a user ELF.

The signed Mac Amu F2 selfhost compiler SHA-256
`5635e728fc49e8d0c7ca3685b5c22ac72bd2d85fae3799a0af45204b8e5f0755`
built a reproducible 20-module EFI/kernel image. A private-QMP observer SHA-256
`dc630e3d468ecb2d449fa5fcd056871ed8334e3e58dd51cffe3cc69de81c4896`
read 12/12 header, 9/9 request and 6/6 result checks from guest-owned memory.
The result checks covered a valid completion, unknown tag, output-token budget,
malformed UTF-8, a valid error and invalid retryable value. The final restored
`ok` text, `stop` reason and canonical result header were read back. The
positive kernel SHA-256 was
`1490d983ae719ef167523e59e8fb7619f611f14a1bf713f65d0fce84f04ab411`.

`os/aiueos/scripts/check-llm-v1-result-qemu-macos-native.py` builds and runs
that image and a separate valid 16-module non-LLM image headlessly. The latter
returned 42 but failed the LLM receipt assertion. The local gate returned
`PASS_MAC_NATIVE_LLM_RESULT_GUEST_AND_NEGATIVE`; its pinned receipt is
`workspaces/codex/jun444-llm-result-20261026/result-gate-2/llm-result-qemu.json`.
The same observer also refused an earlier valid 18-module header/request-only
image at the **result** receipt assertion: all six result words were absent.
That supplemental control used the pinned prior gate image at
`workspaces/codex/jun444-aiueos-llm-20261026/qmp-current-gate-1/positive-build`.

No VNC login, password, Linux guest, JVM, Node or C compiler is needed for
these runs. The result format is a proposed native transport, not proof of the
canonical nested ABI, wire 11/CPL3 dispatch, provider execution, a real model,
trusted human consent, an Itonami agent turn, release qualification or physical
hardware. The OS release score remains unchanged.

## Region alias guard (2026-10-26)

The request validator now checks all 15 pairs among the header, model,
system, prompt, selected-model and result regions before reading the model,
system or prompt bytes. It compares the roots by subtraction, avoiding `root + length`
overflow; an empty region still reserves its root byte against aliasing.
The host must supply checked positive low-half region roots. The validator
does not turn an arbitrary guest pointer into a safe host region.

The source-pinned probe exercises four representative refusals: model and
selected-model sharing a root despite equal bytes, empty system and prompt
sharing a root, prompt and result sharing a root, and prompt/result overlap
with a one-byte pointer offset. The earlier model mismatch, length mismatch,
UTF-8 and result checks remain in the same guest. The rerun's 12 header,
9 request and 6 result receipt words were all 1, and the valid non-LLM image
was rejected. The exact Mac-native build and QEMU readback are in
[alias-guard-receipt.json](alias-guard-receipt.json); the positive kernel
SHA-256 is `3a94e30ef085ab6704c398b7c13d482d7176b78d4a0ec9a7d1358a105cd43415`.
Full aliasing qualification stays open until the caller's host-owned roots,
all pairs, grant binding and user copy-back are tested together. This result
does not add a scorecard point.
