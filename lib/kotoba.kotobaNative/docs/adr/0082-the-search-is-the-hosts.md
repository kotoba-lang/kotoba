# 0082 — the search is the host's

Status: accepted
Date: 2026-09-15
Base: `origin/main` `77a48bd`

## Context

`string-index-of`, `string-contains?` and `string-replace-all` were one source
rewrite (`kotoba.native.string-search`, ADR 0002 / 0081): two helpers walked
the haystack a code point at a time and, at every position, took a
`string-substring` window and compared it with `string=?`. The reason was
stated in the namespace: a string is a `pair(offset,length)` handle whose
bytes only the host callbacks can read, and a search callback would be a
context-ABI bump whose loader (`amu/tools/kexe_loader.c`) is in another
repository.

Measured 2026-09-15 on a packaged `grep` (kotoba-lang/org-ieee-grep, amu
73ddd261, aarch64-macos), against a 3.3 MB C file:

- one pair handle per haystack byte — the window view, and the arena never
  reclaims — plus three or four host callbacks per byte;
- 0.15 s of user time for the 2 MB it managed, about 75 ns/byte, then
  `KEXE_TRAP {:kind :signal :signal :SIGILL}` with the 4 Mi-handle arena
  exhausted;
- `/usr/bin/grep -F` and `rg -F` read the whole file in 10 ms.

That is not a constant factor. A search that allocates per byte cannot finish
a file whose size exceeds the arena divided by one, and a search that calls
the host per byte cannot approach memmem.

## Decision

`string-index-of` is a host runtime operation: `:string-index-of`, arity 2,
in `kotoba.gmir/runtime-operation-arities` (kotoba-gmir 8e57296); context
offset 216 in `kotoba.mir/runtime-context-offsets` (kotoba-mir 1a6424c); the
same 216 in both legacy backends' `heap-call-offsets`; `kexe_context_v5` in
amu's loader with the `_Static_assert` at 216 and every `checked_*` refusing
any other version. It appends to the v4 table for the same one-directional
reason v4 appended to v3: a v4 host has nothing at 216.

The host answers the first UTF-8 byte offset of the needle in the haystack
or -1, and TRAPS on an empty needle exactly as the reference interpreter
does (`:empty-string-search-needle`) — an empty needle occurs at offset 0 in
every string, and an answer there would be indistinguishable from a real
match at the start.

`string-contains?` lowers to `(if (< (string-index-of h n) 0) 0 1)`.
`string-replace-all` keeps its driver, `kotoba$string-replace-from`, with the
scan replaced by one `string-index-of` per occurrence over the suffix it
hands on. The span and find helpers are gone; a program that only searches
gets no helper at all.

## Consequences

- `kotoba.native.string-search-test`: the rows that pinned the scan's answers
  now run through the reference interpreter only and are pinned as VALUES
  (`"日本語" / "語"` is 6, the first of two occurrences is 0); the emission
  test asserts one `:gmir/runtime-call` with `:string-index-of` and two
  arguments, no helper appended, and the slot-216 load bytes on both ISAs
  (`ldr x16, [x7, #216]` = f0 6c 40 f9; `call [r9+0xd8]` = 41 ff 91 d8 00
  00 00). Portable slice: 67 tests, 587 assertions, 0 failures on nbb.
- The host is where the bytes are measured now: amu's conformance runs the
  slot against these rows.
- kotoba-verifier's `expected-context` and amu's `:context-abi` move to
  version 5 with `:string-index-of-offset 216`; every artifact sealed before
  is refused by name, as v3 artifacts were by v4.
