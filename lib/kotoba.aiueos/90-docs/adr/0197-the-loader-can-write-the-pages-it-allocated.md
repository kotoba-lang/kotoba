# ADR-0197: The loader can write the pages it allocated

- Status: accepted
- Date: 2026-09-03

## Context

ADR-0180 landed the first two loader modules -- `aiueos.uefi.console` and
`aiueos.uefi.elf` -- and closed naming five more as BLOCKED rather than
deferred: `memory`, `fs`, `integrity`, `exit`, and the load-and-jump smoke.
All five needed the same thing, and it was not a module. It was an address the
image is allowed to WRITE.

kotoba-gmir ADR-0013 got half of that: 16 KiB of scratch in the image's own
`.data`, which is enough for an out-pointer, so `AllocatePages` became callable
and its answer became readable. It did not make the answer usable. The page is
at an address the firmware chose, so it arrives through a load, and
kotoba-sema's region-provenance rule refuses a base that came from one -- in
the caller as well as the callee, because the taint propagates by fixpoint. A
Kotoba UEFI application could allocate a page and could not put a byte in it.

## Decision

**`os/aiueos/kotoba/aiueos/uefi/memory.kotoba` is the third loader module, and
it is the DECISION half of `main.c`'s `load_verified_model` placement rule
(:684-712) plus the four boot services the loader needs to get memory at
all.**

It is the boundary ADR-0015 draws, applied one module further along. What is
in Kotoba: where pages are allowed to land (`window-reason`, seven named
clauses), how big a request has to be to survive 2 MiB alignment
(`slack-pages`, the C's `raw_pages = pages + 511`), and the slot numbers and
argument shapes of `AllocatePages` / `FreePages` / `AllocatePool` /
`FreePool` / `CopyMem`. What is not: the allocation itself, which is one
instruction.

**There is no `(defn allocate-region [bs pages] ...)` in it, and there cannot
be one.** Two independent reasons, either alone sufficient, and both are
recorded in the module because a reader will otherwise assume an oversight:

- the page count must be a compile-time literal, because the region's length
  is `page-count * 4096` and that is what kotoba-sema compares a declared
  window against -- a parameter has no value at compile time, so a wrapper
  could not carry the bound that makes the root worth having;
- a function RESULT is not a provenance root. A wrapper would hand its caller
  a number that could not be written to, which is the state this stream
  started in.

A region DOES cross a function boundary as a PARAMETER, so a helper that takes
the pages and writes them is expressible and a helper that produces them is
not. The head is therefore spelled at the site that declares the window over
it.

**`AllocatePool` and `CopyMem` take three arguments and are called with
`kernel-uefi-call4` and an explicit fourth zero.** kotoba-gmir ADR-0011 is
right that the argument count is the caller's business, but a third arity
would be worse here rather than better, and the reason is measured:
`x86-uefi-call-wide` loads RCX, RDX, R8 and R9 from its staging slots
unconditionally, so an action that wrote only three of them would pass R9's
stale contents as the fourth word. An explicit zero is what owning the frame
is for.

## Evidence

`os/aiueos/uefi/loader-probe.kotoba` gains two markers and one console line,
and was booted under QEMU with OVMF (`edk2-x86_64-code.fd`, `q35`,
`accel=tcg`, the image on a `fat:rw:` ESP). BOOTX64.EFI is 29,184 bytes.

```
exit=33 debugcon="KHSCNAbcdefPWZ"
entry="0000000000101000" verdicts="0 2 5 24 23 41" window="0 4 3 6 7"
AIUEOS_UEFI_LOADER_OK markers=KHSCNAbcdefPWZ verdicts=0,2,5,24,23,41 window=0,4,3,6,7 entry=0000000000101000
```

| byte | what it proves |
|---|---|
| `P` | a page the firmware allocated was WRITTEN and read back. `(kernel-uefi-alloc-region bs 40 0 2 1 0)` answers with the page's base; `kernel-store-u64-4k` then `kernel-load-u64-4k` carry `0x0123456789ABCDEF` through the CHECKED family, so the declared window and its emitted bounds check are in the path |
| `W` | the placement rule answered all five of its clauses -- 0 admitted, 4 below 4 GiB, 3 not allocated, 6 ends above 64 GiB, 7 ends past the pages the firmware gave -- and the firmware's own console driver rendered them |

### The two markers discriminate

| variant | change | console | window |
|---|---|---|---|
| baseline | -- | `KHSCNAbcdefPWZ` | `0 4 3 6 7` |
| P | the read-back compares `…EF` against `…F0` | `KHSCNAbcdef_WZ` | `0 4 3 6 7` |
| W | clause 7's allocation grown from 4096 pages to 8192 | `KHSCNAbcdefP_Z` | `0 4 3 6 0` |

The W variant is the useful one. Growing the allocation is exactly what the
511 pages of slack are for, so clause 7 stops firing and the printed verdict
changes with the marker -- the console and the marker fail together and say
the same thing, which is what makes the clause an assertion about alignment
slack rather than about a number.

## Consequences

- **`fs`, `integrity` and `exit` are still not written, and are no longer
  blocked.** ADR-0180 listed them behind one missing capability and that
  capability now exists: `integrity` needs a 512-byte SHA state region and a
  digest destination, and both are `(kernel-uefi-alloc-region … 1 0)` away.
  They are LOADER's to write, not this stream's.
- **`main.c` is byte-unchanged.** This merge adds files and does not delete a
  line of C; the K16 pure-native gate's verdict is unchanged by construction
  (`REFUSED foreign-code: uefi/main.c`) and was NOT re-run -- that needs a
  full 33-object zig link, and the claim here is only that `main.c` and
  `build-uefi.sh` are untouched.
- **The probe is still not in the K16 link list**, so the gate never sees it.
  That was true of ADR-0180 and stays true.
- There is still no host-side oracle for `memory.kotoba`. `window-reason` is
  pure arithmetic over seven clauses and would take a `verify-admissions`
  contract well; the evidence today is CPU-only.
