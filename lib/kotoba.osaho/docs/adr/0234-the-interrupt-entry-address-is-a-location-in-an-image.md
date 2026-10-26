# ADR 0234: The interrupt entry address is a location in an image, so the oracle refuses it

## Status

Accepted.

## Decision

`kernel-isr-entry-address` joins the privileged refusal family and the
`kernel-native?` set. It is admitted by the frontend and reaches machine code
on the x86-64 kernel target; here it traps with
`:kernel-privileged-unavailable`, naming itself.

`(kernel-isr-entry-address vector)` answers with the address of the
toolchain-generated interrupt entry for that vector -- the three offset fields
of an IDT gate descriptor. That address is chosen by the ELF image packager
AFTER every byte of the function has been emitted, so it does not exist in this
namespace at all: there is no image, no text segment and no entry table.

## Why the refusal is the `cpuid` refusal and not the `kernel-load-u8` one

Two refusals live in this file and they say different things.
`:kernel-memory-unavailable` means *you did not supply an image*, and supplying
one makes the operation answer. `:kernel-privileged-unavailable` means *there
is no value here to have*, and no argument to `execute` changes that.

This is the second kind, and the test asserts it by running with an image as
well as without: an image says what BYTES are, and this operation reads no
bytes.

It is the `cpuid` case at its sharpest. An invented `cpuid` answer is a wrong
branch. An invented answer here is **the address the CPU jumps to on an
interrupt** -- the caller's next act is to write it into a gate descriptor, and
a plausible-looking number is worse than a trap by exactly the distance between
a compile error and a triple fault.

## Why it must also suppress constant oracling

Its argument is a literal at every real call site: an IDT is built by naming
vectors, so `(kernel-isr-entry-address 3)` is the shape the source has. A
constant-folder therefore sees an operation over one constant with nothing
about it to suggest an effect, tries to evaluate it, and hits the trap above --
aborting the compile of a program that is perfectly valid. That is the same
structural reason the MSR pair, the `cpuid` four and `kernel-xgetbv` are in
that set, and it is why the two changes here are one change.

## Evidence

`kbb -M:test -n kotoba.kir-kernel-memory-test`: 49 tests, 207 assertions,
0 failures.

Two deliberate breaks, each producing the failure it names and no other:

| break | result |
|---|---|
| removed from the privileged refusal set | `:unknown-function` with no `:operation` -- what the operation got before this change |
| removed from the `kernel-native?` set | `lower` throws `kernel-privileged-unavailable` and the module does not compile |
