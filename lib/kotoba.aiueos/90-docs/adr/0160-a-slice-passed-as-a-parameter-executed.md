# ADR-0160: A slice passed as a parameter, executed

- Status: accepted
- Date: 2026-09-02

## Context

amu ADR 0285 decided that the GiB-scale bulk carrier must be addressable
memory rather than a bigger vector. Its machine half landed as
`slice-{load,store}-u{8,16,32,64}`; its **value** half — `[:slice T]` as
something a `let` binds, a parameter carries and `slice-sub` narrows — landed
in kotoba-sema ADR 0022 as a source type erased into two i64 words before HIR.

The compiler side of that is checkable in bytes, and amu ADR 0314 checks it:
a carried traversal and the same traversal written with the machine
operations compile to **identical objects** on both ISAs, at every element
width.

Identical objects is the right thing to check and is not the same claim as
*the object addresses the memory it says it does*. That is a claim about a
machine, and 66 kernel objects thread `base` and `length` by hand precisely
because nobody had made it.

## Decision

`os/aiueos/native/slice-carrier-probe.kotoba` is a test variant of the
pure-Kotoba kernel that boots the way `kernel.kotoba` does — UEFI hands the
compiler's loader a boot-info prefix and a memory map, the loader
identity-maps the first GiB — and then does one thing. It builds a
`[:slice :u8]` over a real conventional-memory page and **passes it as a
function parameter**:

```clojure
(defn fill-slice [s [:slice :u8] index :i64 remaining :i64] ...)
(defn sum-slice  [s [:slice :u8] index :i64 total :i64]     ...)
(defn sum-tail   [s [:slice :u8]] (sum-slice (slice-sub s 16 32) 0 0))
```

`main` builds the slice once with `slice-of-u8` and hands the value on.
Nothing reconstructs it from two i64s at a call site, which is the thing the
carrier exists to stop.

`os/aiueos/scripts/smoke-qemu-slice-carrier.cljk` compiles it
(`--artifact image`), packages it (`package-aiueos-boot`), runs it under
q35 + OVMF with `isa-debugcon` at 0xe9, and reads the digits.

## The observation

```
exit=33 console="0000082000000410SLC"
  whole=00000820 tail=00000410
AIUEOS_SLICE_CARRIER_QEMU_OK whole=00000820 tail=00000410 exit=33 slice-passed-as-a-function-parameter=yes
```

- `0x00000820` = 2080 = 1 + 2 + … + 64 — the whole slice, filled through
  `slice-set!` and summed back through `slice-get`, both taking the slice as
  one parameter.
- `0x00000410` = 1040 = 17 + 18 + … + 48 — `(slice-sub s 16 32)`.
- exit 33 = `(16 << 1) | 1`, which is the probe's own six checks holding. One
  exit value per check, so a mismatch names itself.

## Why those two numbers and not one

A single sum would say "a traversal happened". Two say **which** traversal,
because the narrowing's answer separates four different wrong ones. Measured
by editing the probe and re-running, not by reasoning about it:

| probe | console | exit | what it means |
|---|---|---|---|
| `(slice-sub s 16 32)` | `0000082000000410SLC` | 33 | correct |
| `(slice-sub s 0 32)` | `0000082000000210SLC` | **27** | offset ignored: 1..32 = 528 |
| `(slice-sub s 48 32)` | **empty** | 0 | 48+32 > 64: the narrowing **traps** before anything prints |

A `slice-sub` that ignored its count would print `00000798` (17..64 = 1944);
one that did nothing would print `00000820` twice.

The third row is the one worth reading twice. `slice-sub` erases into
`kernel-subregion`, whose check is emitted rather than documented: a narrowing
that does not fit its parent reaches `ud2` before it addresses anything, and
the machine stops with an empty console. The smoke script refuses a blank
console explicitly rather than letting it fall into the digits regex — *no
digits* and *wrong digits* are different findings.

## Consequences

- The carrier is proven on a CPU, not only in a byte golden. `[:slice T]`
  passed as a parameter walks the memory it names, and the narrowing it
  supports is checked by emitted code.
- **No shipping object changes.** The 66 kernel objects still thread
  `base`/`length`; converting one is a separate change with its own byte diff
  to justify. This ADR does not claim K16 uses the carrier — it claims the
  carrier works.
- The probe is `--artifact image` on the JVM route, deliberately. kotoba-native
  ADR-0036 keeps the portable elf64 twin and the JVM one apart for the x86-64
  **kernel image** specifically (the twin carries no live-boot GDT/TSS shim),
  and `bin/amu --jvm-free` refuses that route rather than emitting a different
  file under the same name. The kernel **object** of the same source is
  byte-identical on both routes, and amu ADR 0314 compiles the carrier fixture
  that way.
- The no-foreign-object floor the shipping kernel's build keeps is kept here:
  the smoke script refuses if any `.c`/`.o`/`.a`/`.so` enters the probe output.
