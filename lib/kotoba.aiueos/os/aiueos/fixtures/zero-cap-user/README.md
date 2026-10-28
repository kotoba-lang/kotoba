# Amu selfhost zero-capability CPL3 fixture

`scalar.kotoba` was compiled by the re-pinned Amu F2 selfhost image from
`kotoba-lang/amu` commit `d3f49e21c853683d43eb1d555bc682d0a7cba804` using
target `x86_64-aiueos-user-v1`. The 8,280-byte `scalar.elf` has SHA-256
`7f5a8c0a31b5bdf191410f007973413d16e497a20ae7fe86c734b9fea85808b1`.
An emulated x86 Amu image produced identical bytes from the same source.

Run `AIUEOS_ZERO_CAP_USER_SMOKE=1 os/aiueos/scripts/smoke-qemu-uefi.sh` to
build a fresh UEFI image, sign the pinned ELF with an ephemeral test key,
verify the digest and P-256 signature in the guest, and execute it at CPL3.
The test checks a tampered signature is refused, that the user context has no
capabilities or runtime handle, and that the result is 42. The temporary
private key is deleted by the smoke script.

This fixture proves the test-only signed guest path. It does not qualify
normal app-catalog admission, Itonami operations, physical hardware, or a
Linux-free AIUEOS build toolchain.
