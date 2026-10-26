# ADR-0036 — The double-fault IST is not yet a closure

- Status: accepted handoff; implementation not accepted
- Date: 2026-08-12
- Extends: ADR-0031 and the recoverable C-free page-fault work at `b1f00e8`
- Related: root ADR-2608110400

## Context

The owner asked to mature Amu and Kotoba native, make effects use the production
Kotoba path, and remove the C dependency because it is not an acceptable safety
boundary.  The authority check corrected the route: this work belongs in the
existing C-free aiueos boot path, not in a newly invented hosted Linux runtime.

The preceding slice made a real page fault recoverable using a compiler-emitted
IDT entry, a dedicated software stack, a sealed probe, and `iretq`.  The next
slice attempted to make vector 8 recoverable with a minimal TSS and IST1.

## What landed

The compiler substrate is on the default branches:

| repository | commit | evidence |
|---|---|---|
| kotoba-gmir | `fda4408` | 13 tests / 80 assertions |
| kotoba-sema | `b419c89` | 8 / 37 |
| kotoba-kir | `6d08e3c` | 134 / 575 |
| kotoba-verifier | `1ecea86` | 48 / 269 |
| kotoba-native | `5d58b2e` | 139 / 1,823 |
| amu closure | `2424db4` | focused closure: 4 / 45 |

The new sealed surface can emit a double-fault handler, configure the IST
receipt and stack, load and read back GDTR/TR, and emit a double-fault probe.
The native fixed-data boundary also moved from `0x10c000` to `0x110000` after
the emitted text was measured at 57,870 bytes.  The old boundary overlapped
code; the relocation is independently useful and is accepted.

The complete Amu suite was measured at the first closure as 970 tests / 7,658
assertions with only the three expected pinned-closure fixture failures; the
fixture and focused aggregate test were then advanced.  It was **not rerun at
the final `2424db4` closure**, so this ADR does not turn the focused result into
a full-suite claim.

## What did not land

The aiueos prototype is preserved, explicitly unmerged and unpinned, at
`agent/native-double-fault-ist` commit `9c74c73`.

It expands the admitted allocator extent from 8 to 11 pages, assigns pages for
the GDT, TSS, and IST1 stack, emits a TSS descriptor, gives vector 8 IST1, and
adds positive and rejection QEMU gates.  Its ordinary C-free boot passed after
the page-table readback was corrected for the new `0x110000` boundary:

```
AIUEOS_KOTOBA_NATIVE_QEMU_OK ... allocator-pages=11 ...
```

The double-fault mutation did not pass.  QEMU reached the pre-probe marker
`MPRCD`, emitted neither the handler marker nor receipt, and reset by triple
fault.  Therefore none of the following is claimed: a working TSS delivery
path, a recoverable vector 8, or a production #DF gate.

## The structural finding

The prototype executes `lgdt` and `ltr`, but does not reload the segment
registers.  Firmware left `CS=0x38`; the replacement GDT has limit 39
(`0x27`) and defines code at selector `0x08` plus the TSS at `0x18`.
After `lgdt`, aiueos reads the still-cached `CS=0x38` and writes that selector
into the page-fault and double-fault IDT gates.  Selector `0x38` lies outside
the new GDT.  An exception delivery can consequently fail, and its attempted
double-fault delivery uses the same invalid selector, explaining the observed
triple fault without treating absence of a receipt as proof of a working IST.

The frame-size assumption is also unproved.  The current handler expects the
same-CPL IST frame at `IST-top - 48`; that must be checked against the actual
architectural frame before accepting the receipt check.

## Decision

Do not merge or pin the aiueos prototype.  Keep the compiler operations because
their admission, independent verification, byte emission, and mutation tests
are closed, but do not describe those operations as an OS-level capability
until QEMU observes the handler and a negative mutation fails for the intended
reason.

The next implementation must choose and prove one coherent descriptor-table
transition:

1. preserve the active firmware code descriptor at selector `0x38` and enlarge
   the replacement GDT; or
2. add a sealed far control transfer that reloads CS to `0x08`, reload the data
   segments as required, and only then construct IDT gates using `0x08`.

The second option gives aiueos ownership of the post-UEFI selector state and is
the preferred direction, but it is not accepted until the transition itself
has a readback/exception-delivery gate.  No arbitrary far jump, descriptor
write, or raw privileged instruction is exposed to guest KIR.

## Resume gate

Resume from `9c74c73`, first fixing the CS/GDT invariant.  Then require all of:

1. ordinary C-free boot remains green;
2. the sealed probe reaches vector 8 on IST1 and returns with an exact receipt;
3. corrupting the IST index, TSS descriptor, gate selector, and expected frame
   independently fails closed;
4. QEMU diagnostic output contains no triple-fault reset;
5. the final Amu full suite and aiueos verifier/build/smoke suites are rerun at
   the exact pinned closure.

Until those gates pass, “the operation is written” is not “the capability
exists.”
