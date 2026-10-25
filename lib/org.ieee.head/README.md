# kotoba-lang/org-ieee-head — POSIX `head`, as a Kotoba command binary

`head` from IEEE Std 1003.1 for one operand, written in `.kotoba` and
compiled to a standalone native executable.

```sh
./head FILE          # the first 10 lines
./head -n 3 FILE     # the first 3
```

## "The first N lines" is bytes, not lines

It is **the bytes up to and including the Nth newline**, and nothing is
added. Measured 2026-09-10 against `/usr/bin/head` on a file holding `x\ny` —
two lines, no trailing newline — the answer is `x\ny`, **three** bytes. An
implementation that reasoned in "lines" and re-joined them with newlines
would answer four, and would pass every other case in this suite.

A file with fewer than N newlines is emitted **whole and unchanged**.

## Measured against the system utility

`test/head_test.cljk` compiles the guest, packages it, **runs the binary**,
and compares bytes *and exit status* against `/usr/bin/head`. Seventeen cases,
all identical.

The boundaries are deliberate: `-n 1` is the low edge, `-n 20` is the file's
exact line count, and `-n 25` is past it. A walk that stops one early or one
late fails `-n 20` and not `-n 25`.

Verified to fail as well as pass: a default of 5 instead of 10 fails exactly
one case, an off-by-one in the newline walk fails three, and emitting nothing
when the file is shorter than N fails four.

## One error path is matched now, and one still is not

`-n 0` is matched **byte for byte on stderr**, since `:io/write-error`
(wire 39) landed:

```
head: illegal line count -- 0
```

exit 1, nothing on stdout. `-n 00` and `-n x` are in the suite because head
echoes the count **as given** rather than re-rendering it.

That comparison discriminates, and it is worth saying how. Reverting to what
this did before wire 39 — exit 1 and say nothing — fails three cases **with
identical stdout and identical exit status on both sides**:

```
FAIL ["-n" "0" "three"] -> "" but /usr/bin/head says "" exits [1 1]
```

Changing the message's two dashes to one fails the same three. Neither would
have been visible to a suite that compared only stdout and status.

**A missing operand is matched too, since wire 35 gained an `EXISTS` form.**

Stderr alone did not fix it. The read form **traps** on a path it cannot
serve, and a trap cannot be caught, so the guest never got control back to
report anything — `SIGILL`, exit 120. The proper answer is a capability
returning `[:result T E]`, but the native gate admits
`[:result-i64 :result-i64]` and not a result over a string, so that is a
change to the *gate*. `"<path>EXISTS_SEP"` is a change to a request *form*,
on a wire that already told three apart by an ASCII token.

```
head: /some/missing/file: No such file or directory
```

exit 1, nothing on stdout, byte-identical.

A path **outside the granted scope** answers `0` — reported as absent rather
than trapped or admitted. `./head /etc/passwd`, packaged for a different
directory, says `No such file or directory` on a machine where that file
exists: the command learns whether the operand it was handed is one it may
read, and nothing else.

Removing the check leaves those two cases failing as `exits [120 1]`;
changing the message text leaves them failing as `exits [1 1]` with identical
stdout.

## Several files: the separator counts what was written, not what was asked

With **two or more** operands each file is introduced by `==> FILE <==`; with
one there is no header at all. A blank line precedes every header **except
the first one printed** — and *printed* is the exact word, because a missing
operand does not count. Measured against `/usr/bin/head` 2026-09-10:

```
head -n 2 nope.txt h1.txt        h1's header has NO blank line before it
head -n 2 h1.txt nope.txt h2.txt h2's header DOES
```

So the flag carried through the walk is "has a header been written", not "is
this the first operand". The control for that is exact: counting a missing
operand as printed fails **one** case, `missing three`, and no other — an
implementation keying off position passes every other multi-operand case.

An empty file still gets its header and contributes no body, so two
separators land back to back. And a file with no trailing newline followed by
another file is the seam worth pinning: the separator newline *completes* the
unterminated line rather than producing a visibly blank one.

Two further controls: emitting headers for a single file too fails 12 cases,
and emitting the separator before every header including the first fails all
9 multi-operand cases.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write` (37), `:io/write-error`
(39). Fuel, the string arena, the grant and the filesystem scope are all
constants of the packaged binary — a caller cannot raise any of them.

## Five parameters

The walk carries both the exit status and the header flag, and five
parameters is the compiler's limit
(`kotoba.compiler.frontend/max-parameters`, an ABI arity limit rather than a
language decision). So the two are packed into one word — bit 0 for "a header
has been written", bit 1 for "an operand was unreadable" — and only bit 1
survives as the exit status.

## Standard input, in 64 KiB pieces

With no file operand `head` reads standard input (wire 41 `:io/read`,
2026-09-16). Measured over 1,268,018 Bash calls in 558 agent transcripts,
that is 97% of how `head` is invoked (54,444 of 56,211), and `grep … | head`
is the most frequent pipeline shape of all — until the wire landed every one
of those exited 1 with nothing printed.

It reads in 64 KiB chunks and stops at the chunk holding the Nth newline, so
`yes | head -n 3` ends (28 ms, measured). Everything up to the Nth newline is
output, so a chunk with fewer newlines than are still wanted is emitted whole
and nothing accumulates; each chunk is read inside an `arena-scope` and
reclaimed once written, which is what lets `-n 200000` push 12.8 MB through a
4 MB string pool (in the suite). The first cut accumulated chunks instead and
the pool grew as the square of the input — a chunk read at the pool's tail
leaves the accumulator unable to tail-append — which `-n 20000` over 8 MB
caught at exit 120.

## The count, in its spellings

`head -N`, `head -n N`, `head -nN`, and `head -c N` / `-cN` for bytes.
Measured 2026-09-17 over 1,268,018 agent Bash calls: `head -3` 6,176,
`-20` 6,048, `-1` 5,967 — the numeric shorthand dominates and was a usage
error here until that day; `-c N` is 2,964.

## What this is not

`-c` with a count that lands inside a multi-byte sequence: `/usr/bin/head`
prints the raw partial bytes; this build cannot write a partial sequence
(on a file it traps, on standard input it stops at the boundary before the
cut). Counts on text are where `-c` is used; a split is the named
divergence.
