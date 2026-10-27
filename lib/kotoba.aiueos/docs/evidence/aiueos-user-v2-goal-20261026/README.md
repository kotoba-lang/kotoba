# C-free user-v2 Goal request diagnostic (2026-10-26)

The [Amu user-v2 ELF](https://github.com/kotoba-lang/amu/pull/1589) at SHA-256
`d1cd47b63ec90df52f6763f63c9410d2a032266412be3dd49238db8ecdf61248`
was built by a signed Mac native F1=F2 Amu compiler. It targets the native
AIUEOS ValueRuntime pages: RX `0x220000`, RW `0x221000`, Goal request region
`0x221100`. The old v1 compiler ELF targets different pages and does not
qualify this guest result.

[`user-elf-v2-goal-entry.kotoba`](../../../os/aiueos/native/user-elf-v2-goal-entry.kotoba)
checks a fixed whole-ELF SHA-256 and a version-2 boot-slot header, copies the
330 code bytes and 88 context bytes into the sealed user pages, and writes a
test Goal region: little-endian length 3 followed by `a b` and zero padding.
This is a fixed diagnostic fixture. It does not read the live Itonami UI or
admit a signed general application.

The [Mac native build receipt](build-state.json) records a 27-module locked
Kotoba kernel source graph, exact owner pins, two byte-identical kernel/EFI
builds, and no Linux/JVM/Node/C compiler process in this build. Kernel SHA-256
was `3abc4f5e96495af77c6c7f2fd2e502ae0af113f82c0bb184f8d9c988aa9360d3`;
EFI SHA-256 was `816869fdb90df2ba6d4b8df66b8c1d8fe00c7583a74713bc6bcd82429ff15f32`.
The diagnostic slot SHA-256 was
`b88caa63c3b782a550f4aefdb84e8ad47be0c6f578cb58352a50573bc05e9b23`.
[`make-native-user-v2-fixture.py`](../../../os/aiueos/scripts/make-native-user-v2-fixture.py)
reproduces it from the pinned ELF and refuses the v1 ELF before writing a slot.

The [private QMP receipt](qmp.json) records three fresh QEMU boots. The
positive boot reached CPL3 at `0x220021`, returned 3, copied the exact Amu
code bytes, and had the expected 64-byte Goal region in guest memory. One
changed code byte and a slot version changed from 2 to 1 were both refused
at CPL0 with result 0. The gate used QMP stdio, no VNC listener, network,
password, or human guest input. The observer can be rerun with the matching
kernel, EFI, ELF, slot, source, QEMU and firmware using
[`check-native-user-v2-goal-qemu.py`](../../../os/aiueos/scripts/check-native-user-v2-goal-qemu.py).

This proves one fixed Goal input reaches one zero-capability Kotoba program
through native AIUEOS CPL3. It does not qualify live Itonami Goal ingress,
author/session binding, generic or signed app admission, fresh approval,
model/tool operations, receipt, durable workspace, reboot continuation,
release or physical hardware.
