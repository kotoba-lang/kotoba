# Amu scalar code in the C-free AIUEOS CPL3 path (2026-10-26)

The signed Mac Amu root from [Amu #1586](https://github.com/kotoba-lang/amu/pull/1586)
compiled the diagnostic `user-elf-entry.kotoba` with its locked 27-module
kernel graph. The [build receipt](build-state.json) records two identical
KERNEL.ELF and EFI products. No Linux, JVM, Node or C compiler process ran in
the Mac build.

The source/artifact [parity receipt](source-parity.json) compares every staged
code and data word with the [pinned Amu user ELF](../../../os/aiueos/fixtures/native-user-scalar/scalar.elf).
Changing one source word or one ELF byte was refused. The independent
[QEMU receipt](qemu.json) observes the compiler-emitted code bytes in the
guest's code page, CPL3 at the scalar loop, and result `42` in the guest's
request page. QMP uses private standard I/O; no VNC, network or manual keys
are involved.

This is code-byte execution in the C-free AIUEOS user-entry mechanism. The
guest has not parsed or signature-admitted the ELF, and the code page address
differs from the ELF's declared virtual address. The diagnostic does not run
the Itonami Goal/approval/agent loop, restore a signed workspace, or qualify
a release or physical hardware.

To repeat from these source checkouts on Apple Silicon, use
`build-native-kernel-macos.py` with `user-elf-entry.kotoba`, the signed Mac Amu
root and the five owner source paths in `source-dependencies.json`, then run
`check-native-user-scalar-qemu.py` with the produced KERNEL.ELF/EFI, this
fixture, QEMU and firmware. Each output path must be a new private directory
under `github/workspaces/`.
