# ADR 0048: Kernel image fuel is artifact data

## Finding

Amu could seal a native artifact with a caller-selected fuel bound, but the
ELF kernel packager wrote the literal 512 into both x86-64 and AArch64 image
contexts. A CLI request and the sealed artifact could therefore say 4096 while
the machine actually received 512.

## Decision

`package-kernel` and `package-kernel-aarch64` copy the positive fuel value from
the sealed artifact. Packaging fails closed unless `:limits :fuel` and
`:fuel-abi :initial` are equal. The image test reads the emitted context word,
so artifact metadata alone cannot make this gate pass.

This repository owns the ELF context encoding. Amu owns threading a user's
finite budget into the sealed artifact, and aiueos owns selecting a budget that
covers its independently bounded boot workload. None of those layers may
silently replace another layer's value.
