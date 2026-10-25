# 0084 — the check is emitted, not called

Status: accepted
Date: 2026-09-16
Base: `origin/main` `9cccd1b`

## Context

Every string and vector operation of a native binary is a call through the
context table into the loader's `checked_*` C function. Measured on
org-ieee-sort's index merge sort over 33 MB (superproject ADR-2609161700 and
its follow-up): the floor of one such call is 4 ns and the useful work of
`vector-at` is one load, so the ~15 million comparisons of the sort spent
most of their time in the calls around the comparison — two `vector-at`
and one `vector-assoc!` each — not in it.

The owner's decision (2026-09-16): inline emission is acceptable if it is
not a security regression — 「kotoba-native が inline emit で ok, security
的に問題なければ」.

## Decision

Five runtime operations are emitted in line on both ISAs
(`kotoba.native.machine-ir`, `inline-runtime-operations`): `pair-first`,
`pair-second` (`string-byte-length` shares its slot), `vector-count`,
`vector-at` and `vector-assoc!`. Each is a handle-range check, a table
read and one load or store. Everything else stays a call — a search, a
comparison, a concatenation is a loop, and the loader's loop is libc's.

The checks are the C twin's, emitted: `(uint64)(handle − 1) < *used` (a
handle of 0 wraps and fails like any other out of range), and for a vector
`(uint64)index < length`. Failure is `udf #0` / `ud2`: SIGILL, the signal
`raise(SIGILL)` sends in the C twin, so a supervisor cannot tell an inline
refusal from a host one.

What the inline path reads it reaches through six pointers the loader
writes into the context before the guest starts (context ABI v9, offsets
288–328: the pair-used counter, the pair table, the validated flags, the
vector-used counter, the vector table, the item arena). Nothing writes them
afterwards: guest code has no store but the kernel window family, which
the frontend admits separately and which addresses declared windows, so
the pointers and the tables are as trustworthy in line as behind a call.

The registers are the runtime-call profile's own — arguments in
x1..x3 / rsi..rcx, the answer in x0 / rax, all of which the call would have
clobbered — plus the encoder scratch pair x16/x17 and r10/r11 that no
allocated value ever occupies. The sequence touches neither the stack nor
the context register.

## Why this is not a regression

The security argument of a host slot has four parts: the handle is in
range, the bytes are inside the shared mapping, the offset is a boundary,
the string is validated. The five operations here need only the first
(and, for a vector, the index bound); both are one compare-and-branch,
emitted. What moves is WHERE the check lives — from one audited C function
to every call site — and the cost of that is a codegen bug becoming a
memory-safety hole rather than a wrong answer. The mitigation is that the
emitted bytes are pinned by test on both ISAs, that the sequence is the
same at every site (one function per ISA), and that amu's conformance
executes the inline path under the real loader in both directions: an
in-range read answers and an out-of-range one traps SIGILL.

## What this does not do

No loop is emitted. `string-index-of-from`, `string-compare-lines`,
`string-concat` and the rest stay host calls. UTF-8 validation is not
consulted in line: the five operations read table words, never string
bytes, so the validated flag is irrelevant to them.

## Measured

See amu's CHANGELOG entry for context ABI v9 and org-ieee-sort's README:
the same 33 MB sort with the same loader, before and after this lowering.
