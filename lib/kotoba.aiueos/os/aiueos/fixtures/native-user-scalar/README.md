# Native scalar user-code fixture

`scalar.kotoba` and `scalar.elf` are the zero-capability
`x86_64-aiueos-user-v1` fixture emitted by the signed Mac Amu selfhost root
from [Amu #1586](https://github.com/kotoba-lang/amu/pull/1586) at
`75c000b0e0e60c9f26476ff48d006909f3c6cf3e`. The ELF is 8,280 bytes,
SHA-256 `7f5a8c0a31b5bdf191410f007973413d16e497a20ae7fe86c734b9fea85808b1`.
Its bytes also match the independent diagnostic fixture in
[AIUEOS #505](https://github.com/kotoba-lang/aiueos/pull/505).

The native diagnostic kernel stages only the ELF's code and data bytes through
Kotoba literals. The user code is position independent and runs at the
kernel's selected user code page, which can differ from the ELF's declared
virtual address. This is not a normal ELF loader, signature admission or
registered Itonami app.
