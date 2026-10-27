# AIUEOS Mac native build from merged CCF Amu root (2026-10-26)

The ordinary `local-draft` desktop build used Amu draft [#1586](https://github.com/kotoba-lang/amu/pull/1586) head `75c000b0e0e60c9f26476ff48d006909f3c6cf3e`. Its signed Mac compiler SHA-256 is `c89f9fbedd680f06aa6ba6f06953d8c897ec78d2594f98326e5a23be1255d6d9`. No external compiler or packager override was set. This binds the diagnostic OS build to the merged CCF + Mac FS2 source candidate.

The [integrated receipt](integrated.json) records font, 31-module kernel, EFI and GPT/FAT16 media production. The [QEMU receipt](qemu.json) passed 11 actual commit, cold restart, uncommitted-edit loss and malformed-medium refusal observations. The [restored screenshot](restored-ab.png) shows the committed `Goal local: ab` after a new QEMU process.

The [unattended debugger](unattended-debug.json) launched another private-QMP VM and verified `Goal local: merged` in guest state and the [screenshot](debug-merged.png). `vncUsed=false` and `networkUsed=false`; no human login or guest keystrokes were required. The compiler and media identities match those in the receipts.

The same signed Mac Amu root compiled the zero-capability `x86_64-aiueos-user-v1` scalar fixture to an 8,280-byte ELF with SHA-256 `7f5a8c0a31b5bdf191410f007973413d16e497a20ae7fe86c734b9fea85808b1`. Its Git blob identity `737138fb00e3143f05a262a952aefc51150efba8` exactly matches the artifact in diagnostic [AIUEOS #505](https://github.com/kotoba-lang/aiueos/pull/505); the [parity receipt](user-elf-parity.json) records both identities. The current C-free desktop image still does not load that ELF; this is compiler/artifact parity, not in-guest user execution.

These are Mac host and QEMU diagnostic VM observations. Native Linux release gates, registered Itonami agent operations, signed D2 workspace restore and physical boot remain separate.
