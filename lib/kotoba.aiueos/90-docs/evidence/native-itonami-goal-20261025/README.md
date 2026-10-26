# AIUEOS native Itonami goal draft — 2026-10-25

The local native Amu build reproduced a locked 30-module kernel, EFI, font
and 8 MiB GPT/FAT16 diagnostic medium. The builder used the pinned static
AArch64 compiler with SHA-256
`cd65664a146bb0eea13577d5d9687467a22700fe91820a12001f1ddb0dc9b4c9`.
The kernel SHA-256 was
`ec72e01bd5233877235a55b64df3087c0c807e328f552310464863b817c5c875`;
the medium SHA-256 was
`1e8a932f9b51523ce7d9dfffb7f2b21f732821f6e0b60ae8e9f10ff02e7f778b`.
The final source graph pins matched the source worktree before QEMU execution.

`check-native-desktop-qemu.py` booted that medium in QEMU TCG with a temporary
disk overlay and no NIC. It checked the sealed GOP/font and private kernel
state, verified that typing while Murakumo was focused left the Itonami draft
unchanged, opened the native Itonami window, typed `a` then `b`, and used
Backspace. The observed surface values were `Goal (RAM):\na`,
`Goal (RAM):\nab`, and `Goal (RAM):\na`, with a new completed frame after
each operation. The screenshots for `a` and `ab` have different pixels:

![Goal after a](itonami-goal-a.png)
![Goal after ab](itonami-goal-ab.png)

The QEMU verdict was `PASS_NATIVE_DESKTOP_INPUT_QEMU` with eleven named input and
render milestones. The target is a freestanding AIUEOS kernel; it booted no
Linux guest. The compiler ran in a Linux build container. This local proof
does not execute Itonami dapps or an agent loop, persist the goal, qualify the
shared Browser/CSSOM graph, or demonstrate physical hardware operation.
