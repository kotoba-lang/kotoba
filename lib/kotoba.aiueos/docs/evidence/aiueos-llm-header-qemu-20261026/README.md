# Native `llm-v1` request guest gate

`os/aiueos/native/llm_v1_header.kotoba` validates a bounded 64-byte request
header. `llm_v1_request_shape.kotoba` checks separate model, system, prompt
and result region lengths, validates their UTF-8, and compares model bytes
with a host-selected model region. `llm_v1_header_probe.kotoba` calls both in
a C-free AIUEOS kernel.
The Mac selfhost compiler produces a reproducible 18-module EFI/kernel image.
The Amu QMP observer reads 12 header and 9 request-shape guest checks plus
restored bytes from owned memory. A separate, valid 16-module kernel returns
the same result value but has no LLM receipt, so the observer must reject it.

`os/aiueos/scripts/check-llm-v1-header-qemu-macos-native.py` builds and runs
both images headlessly. It accepts a pinned signed Mac compiler, a pinned Amu
observer, QEMU and OVMF. Set the five `AIUEOS_*_SOURCE_PATH` variables used by
`build-native-kernel-macos.py` to the matching owner-source roots. A successful
run writes `llm-header-qemu.json` and the individual build/QMP receipts under
the output directory. No VNC login, keyboard input, password, Linux guest,
JVM, Node or C compiler is needed for this gate.

The updated local run on 2026-10-26 returned
`PASS_MAC_NATIVE_LLM_HEADER_GUEST_AND_NEGATIVE`. The positive guest had 12/12
header checks and 9/9 request-shape checks, including a valid four-byte UTF-8
sequence and refusal of an invalid lead, an overlong form and a scalar above
U+10FFFF. The valid-image negative was refused at the receipt assertion. The
model, selected-model fixture and restored prompt bytes were read back
separately from the guest.
Compiler SHA-256: `5635e728fc49e8d0c7ca3685b5c22ac72bd2d85fae3799a0af45204b8e5f0755`.
Observer SHA-256: `2b8e734fd9934d676b5e3999a0e2c999d4a441a2130a2e20ad754f3ef95f4788`.
Positive kernel SHA-256: `631ed3fb5353759eed957d0db2521e3817217d2c03c552ae10f4c8af75a1d8a2`.
Negative kernel SHA-256: `713ac2d4fab7947029cc280e3ab01713baa47329e25033a04865183cbef9c619`.
Local receipt: `workspaces/codex/jun444-aiueos-llm-20261026/utf8-gate-1/llm-header-qemu.json`.

This is a kernel-side component test. The selected-model bytes are a fixture,
not production host policy. Region alias refusal and the model keyword grammar
remain open. Wire 11 dispatch, CPL3 kit admission, model execution, trusted human
approval, Itonami agent/tool turns, and durable restore remain open. It does
not change the OS release score.
