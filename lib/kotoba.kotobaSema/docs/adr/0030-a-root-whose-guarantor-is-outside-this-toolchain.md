# ADR-0030: A root whose guarantor is outside this toolchain

- Status: accepted
- Date: 2026-09-03

## Context

ADR-0024 made `(kernel-scratch-region)` a provenance root, which gave a UEFI
image an out-pointer. `AllocatePages` became callable and its answer became
readable. It did not become usable.

The page is at an address the firmware chose, so it reaches the program
through a load, and `traceable-base?` refuses a base that came from one -- in
the caller as well as in the callee, because base taint propagates to call
sites by fixpoint. So a Kotoba UEFI application could allocate a page and
could not write it (amu ADR-0318 recorded exactly this, and marker `A` of its
fixture READS the allocated page for this reason). Everything a bootloader
does after it decides where the kernel goes was blocked on it.

## Decision

**`(kernel-uefi-alloc-region base slot allocate-type memory-type page-count
address-hint)` is a provenance root, beside `kernel-boot-info` and
`kernel-scratch-region`.**

### What was NOT done, and why the alternative is worse

The obvious repair is to admit a loaded word as a base -- either directly, or
behind an `(kernel-adopt-region address length)` head gated to the UEFI target
and reported in `kernel-region-report` so a build can see every adoption.

That is not an extension of the rule; it is its deletion with a log file.
`traceable-base?` earns every bounded access its meaning: the emitted check
compares an index against the length the SOURCE declared, and that check is
worth something only because the BASE is an address some layer of this
toolchain can account for. A head that says "trust me, this address has this
length" makes the length an assertion by the author about a number the author
also computed. Once it exists it is the cheapest way to get a writable base --
`GetMemoryMap`'s buffer, `HandleProtocol`'s interface, `LoadedImage`'s
`ImageBase` are all one adoption away -- and within one loader every window in
the program is rooted at an adoption. The report would then list them all and
mean nothing, because there would be nothing left that was not one.

### What roots actually are

The three roots are not "addresses the compiler knows". `kernel-boot-info` is
a word the firmware handed over; this pass has no idea what it is. What makes
it a root is that **something outside this expression is answerable for it**:

| root | guarantor |
|---|---|
| a compile-time literal | the author, at an address the compiler can print |
| `kernel-boot-info` | the ENTRY CONTRACT -- amu's shim parks RCX at context+0x50 |
| `kernel-scratch-region` | the PACKAGER -- `pe32plus` reserves 16384 bytes |
| `kernel-uefi-alloc-region` | the UEFI SPECIFICATION -- `AllocatePages` either fails or returns `page-count` 4 KiB pages the caller owns |

So the fourth root is the same kind of thing as the second and third, with a
guarantor outside this repository rather than inside it. What makes that
guarantee usable rather than merely quotable is that **the head is the
allocation**. A program cannot present an address to it: the out-word the
firmware writes through belongs to the emitted call's own frame (kotoba-gmir
ADR-0030). There is no shape of source in which this root names memory the
firmware did not just hand over -- which is precisely what an `adopt` head
could not have said.

### The page count is a literal, and that is the point

`page-count * 4096` is the length `AllocatePages` obtained under all three
allocate types. Requiring the count to be a literal
(`:kotoba.error/kernel-alloc-region-pages`) is what makes this a root this
pass can BOUND, exactly as it bounds the scratch reservation: a window
declared wider than the pages is a write past them, and no emitted check
catches it, because the emitted check compares an index against the length the
source declared and here the source is the thing that is wrong
(`:kotoba.error/kernel-alloc-region-window`). A non-literal window length is
refused for ADR-0024's reason -- an expression cannot be compared against a
ceiling.

**The ceiling bites for small allocations only, and that is enough.** Every
checked window is already bounded by its tier and the widest tier is 65536
bytes, so `page-count * 4096` is the tighter of the two exactly when
`page-count` is under 16. What this refuses concretely is a 64 KiB window
declared over a one-page allocation -- which is the mistake a loader makes,
because 65536 is the number the widest spelling of the operation carries.

`alloc-region-maximum-pages` is 2^40 and is NOT a policy about how much a boot
path may ask for. It keeps `page-count * 4096` under 2^52 so the product is an
exact i64 on both runtimes.

### The refusal is a separate keyword from the scratch one

"exceeds the 16384-byte reservation" sends a reader to the packager; "exceeds
the 4096 bytes this allocation obtained" sends them to their own page count.
Those are different mistakes and the message names the byte count rather than
a constant, because the region's size is a fact of the CALL SITE here.

## A defect this stream found in the neighbouring rule

`traceable-base?` follows BOTH arms of an `if`; `scratch-rooted?` followed
neither. So `(if c (kernel-scratch-region) p)` was a rooted base with **no
ceiling at all**, and `kernel-load-u64-64k` over it -- a 65536-byte window
over a 16384-byte reservation -- compiled. `scratch-rooted?` now answers true
when either arm is the region, which is the conservative direction; the new
`alloc-region-ceiling` takes the MINIMUM of its arms, which is the same
decision where the ceiling is a number rather than a constant.

## Consequences

- **A window over a base that reached a function as a PARAMETER is bounded by
  its tier and by nothing else.** That is not new -- `scratch-rooted?` has
  never followed parameters, because the ABI boundary is where this pass stops
  knowing -- but it is now true of two roots instead of one, and it is the
  honest limit of the ceiling. `kernel-region-report`'s `:abi-boundary` is
  where a build can see which parameters are in that position.
- The head joins `reserved-function-names` through
  `kernel-privileged-operations`, so a function of that name cannot shadow it.
- `lang/guest-grammar.edn` gains the head, and the digest pinned in
  kotoba-lang, kotoba-sema and kotoba moves with it. `:admitted-builtins` now
  names 115 kernel heads.
- amu owns the target gate, as it does for every firmware head: the answer is
  wrong outside the target whose packager and entry contract establish the
  boundary, and the failure mode is a machine that faults rather than a
  compile that refuses.
