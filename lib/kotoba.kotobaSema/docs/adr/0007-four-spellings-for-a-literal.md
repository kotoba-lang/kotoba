# ADR-0007: Four spellings for a literal, and two wider firmware calls

- Status: accepted
- Date: 2026-09-02

## Context

ADR-0003 gave the frontend four UEFI firmware-boundary spellings and said, of
`GetMemoryMap`'s five arguments and `OpenProtocol`'s six, that they "need an
argument channel that does not fit in registers at all". That was wrong about
WHICH registers, and it is corrected here.

It also left `ConOut->OutputString(ConOut, L"AIUEOS")` unwritable, because that
takes a `CHAR16 *` and this language had no way to obtain the address of
anything.

## Decision

**`kernel-uefi-call4` (6 operands) and `kernel-uefi-call6` (8).** kotoba-mir
now draws privileged operands from the scratch tier FOLLOWED BY the preserved
tier, and the preserved tier is callee-saved under Microsoft x64 as well as
under the internal ABI -- so an operand parked there survives the call it is an
operand to. Two heads rather than one six-argument head, because a call site
with four arguments would have to invent two, and "the callee ignores the extra
words" is a fact about the CALLEE.

**A new family, `rodata-literal-operations`, with four heads at arity one:**

```clojure
(ucs2 "AIUEOS")                     ; CHAR16 *, UCS-2 LE, NUL terminated
(guid "5B1B31A1-9562-11D2-8E3F-00A0C969723B")  ; EFI_GUID *
(bytes-literal "48656c6c6f")        ; the address of those five bytes
(bytes-literal-length "48656c6c6f") ; 5
```

Its own family rather than four more entries in `kernel-privileged-operations`
because **the argument is a piece of the source text, not an expression**.
Every entry in that map takes i64 expressions and walks them; these take a
string literal and deliberately do not walk it. `(ucs2 s)` for a parameter `s`
has no answer -- there is no runtime under a firmware image that could place
bytes for a string which does not exist until the program runs -- so it is
refused at the source rather than lowered into something a backend has to
refuse with a shape error.

**The address and the length are two heads over one literal text.** This
language has no multi-value return and the value runtime's `pair` does not
exist on a firmware target. Deriving both from one string is what keeps them
together: there is no way to take the address of one literal and the length of
another without writing two different strings, which a reader sees.

**Content is validated here, not only downstream.** A malformed GUID has no
failure mode downstream: sixteen bytes get placed either way and the firmware
answers `EFI_UNSUPPORTED`, which is what a machine WITHOUT that protocol
answers. The check duplicates `kotoba.gmir/rodata-content?` on purpose and is
not allowed to disagree with it; it exists because the refusals differ in KIND
-- this one names a source form and a line.

## Consequences

- All four are admitted target-independently, exactly as `kernel-write-cr3` is.
  The target gate lives in amu, which is the only layer that sees a target
  keyword next to a module, and kotoba-verifier refuses independently.
- The four heads join `reserved-function-names`. A function named `guid` would
  shadow the head SILENTLY: `(guid "...")` would become a call with a string
  argument to a function whose parameter is declared i64.
- A privileged operation's operand count is not a function's parameter count.
  The suite's wide-call wrapper takes two parameters and a tail of constants
  because a six-parameter function is refused as "function parameters exceed
  ABI-supported arity" -- which would have made that test green for the wrong
  reason.
