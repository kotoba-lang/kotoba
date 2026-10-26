# Itonami Goal input to user-v2 CPL3 diagnostic (2026-10-26)

This gate links the native Itonami desktop and the Amu user-v2 Goal ELF in one
AIUEOS image. The [Mac native build](build-state.json) used a signed Amu image
to discover and compile a locked 32-module Kotoba graph, then reproduced the
kernel and EFI byte for byte. Its compiler process did not use Linux, JVM,
Node or a C compiler. Kernel SHA-256 was
`ce9022b23ee9c8f331af81e6cc4b239f0ce50c3d8c69d4abe88ad114ea6ada1a`;
EFI SHA-256 was
`dc3b0bdc13a0ee873558948e08cce4078341a04c2ade5841d6425ecb46af9bfc`.

The current EFI packager has one 512 KiB payload. The desktop needs it for
its font, so this diagnostic image pins the exact executable and context
segment bytes from [Amu user-v2 PR #1589](https://github.com/kotoba-lang/amu/pull/1589)
inside a generated Kotoba module rather than loading a second payload. The
[generator](../../../os/aiueos/scripts/generate-native-v2-inline.py) rejects
an ELF whose SHA-256 differs from
`d1cd47b63ec90df52f6763f63c9410d2a032266412be3dd49238db8ecdf61248`,
checks both segment layouts, and can compare the checked-in
[inline source](../../../os/aiueos/native/user_v2_inline.kotoba) byte for byte
with the pinned ELF. The kernel source graph pins that module. This is not
generic ELF or signed application admission.

In the [private QMP receipt](qmp.json), three fresh QEMU boots used no VNC,
password, network or human guest input. QMP selected Itonami, typed each Goal,
and checked the guest surface, completed frames and visible glyph ink before
pressing Enter. The [first screenshot](goal-a-b.png) shows `a b`; the
[second](goal-hello.png) shows `hello`. The compiled user code then ran at
CPL3 `0x220021`, returned lengths 3 and 5 respectively, and the guest request
page contained each exact typed string with a little-endian length and zero
padding. A third boot pressed Enter with an empty Goal; it stayed at CPL0 and
left the user request region untouched. The observer is
[`check-native-user-v2-live-goal-qemu.py`](../../../os/aiueos/scripts/check-native-user-v2-live-goal-qemu.py).

This qualifies a live keyboard/UI Goal handoff to one zero-capability Kotoba
program. It does not qualify an agent turn, trusted per-operation approval,
model/tool execution, receipt, committed workspace, restart continuation,
multiple apps, signature admission, release media or physical hardware. The
single-payload limit needs a real font-plus-app packaging/admission design.
