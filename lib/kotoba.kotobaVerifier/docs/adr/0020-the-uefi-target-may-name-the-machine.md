# ADR-0020: The UEFI firmware target may name the machine

- Status: accepted
- Date: 2026-09-02

## Context

`verify-runtime!` admitted the kernel-facing operations -- port I/O, control
registers, the interrupt-flag instructions, the bounded memory family -- for
`:x86_64-aiueos-kernel-v1` and `:aarch64-aiueos-kernel-v1` and refused every
other target with "bounded kernel memory operation requires the aiueos kernel
target".

`:x86_64-aiueos-uefi-v1` was one of the refused. That is the target whose own
profile says `:execution :firmware`, `:runtime :none`,
`:ambient-syscalls false` -- a UEFI application runs at CPL0 on an
identity-mapped machine with boot services live, which is the same execution
surface the kernel targets name, reached earlier. Refusing it a port write
refused the target its own profile describes, and it is a large part of why
aiueos's BOOTX64.EFI is still C: a bootloader cannot say anything at all
without one.

## Decision

`:x86_64-aiueos-uefi-v1` joins the admitted set. The four UEFI firmware
operations (`kernel-system-table`, `kernel-load-ptr`, `kernel-uefi-call2`,
`kernel-jump-to`, kotoba-gmir ADR-0008) join the operation list, so an
ordinary native target is refused here as well as by amu's own target gate --
two refusals, because a gate on one route is not a gate.

## Consequences

- This repository pins kotoba-native itself, deliberately, and that pin
  predates the four operations' encodings. The new tests therefore assert
  admission with `kernel-out-u8`/`kernel-in-u8`, which this pin can emit.
  They deliberately do NOT assert the four operations' refusal on an ordinary
  target: measured at this pin, `(kernel-load-ptr 4096 64)` on
  `:x86_64-kotoba-v1` throws "aggregate ABI rejected: call-abi-not-admitted",
  because a backend that predates the operation reads it as a call to an
  unknown function -- a refusal that would still happen with the target rule
  deleted. Four green assertions that discriminate nothing are worse than
  none. Their gate is tested in amu, where the toolchain is new enough.
- The rule now separates FIRMWARE from ordinary native, not KERNEL from
  everything. A future ring-3 aiueos target would still be refused, which is
  correct: `:x86_64-aiueos-user-v1` is `:execution :process`.
- Break-checked: removing `:x86_64-aiueos-uefi-v1` from the set turns the two
  admission cases red with exactly this ADR's message.

## Addendum, same day: two lists that must agree, in two repositories

Admitting the target was not enough. `verify-runtime!` also re-executes the
ENTRY through the oracle and compares the result to the sealed value, unless
the module is kernel-native -- and the list that decides that is a SECOND
list, derived independently here and in `kotoba.kir/lower`.

The four firmware operations were in kir's and not in this one. The failure
that produced surfaces in neither list's terms: the compiler correctly seals
no value, this side re-executes `(defn main [] (kernel-system-table))`, gets
`:kernel-privileged-unavailable`, and refuses the artifact as "native artifact
oracle evaluation rejected" -- an oracle mismatch it never had. Measured
2026-09-02 while wiring amu's target-gate test.

The set is now the private var `kernel-native-operations` rather than a `let`
binding inside `verify-runtime!`, so `kotoba.verifier-test` can assert its
membership directly instead of inferring it from a behaviour this repository's
own kotoba-native pin cannot produce. Break-checked: removing
`kernel-system-table` turns that test red naming the missing symbol.

