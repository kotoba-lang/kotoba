# kotoba-lang/org-ieee-wc — POSIX `wc`, as a Kotoba command binary

`wc` from IEEE Std 1003.1 for one operand, written in `.kotoba` and compiled
to a standalone native executable.

```sh
./wc FILE        # lines, words, bytes
./wc -l FILE     # lines
./wc -w FILE     # words
./wc -c FILE     # bytes
```

## The format is `" %7d"`, and that took a fixture to prove

macOS `/usr/bin/wc` prints each count with an **unconditional leading space**
and the number right-aligned in **seven** columns. A fixed eight-wide field
looks identical until a count reaches eight digits — below that both produce
eight characters.

Measured 2026-09-10: padding to a fixed 8 passed **fourteen of fifteen**
cases. Only a 10,000,000-byte operand separates them:

```
correct      " 10000000 …"     (space + 8 digits)
fixed %8d    "10000000 …"      (no space)
```

That fixture is in the suite for exactly this reason, and `-c` is the case
that uses it: bytes need no walk, so the boundary costs one read.

## Measured against the system utility

`test/wc_test.cljk` compiles the guest, packages it, **runs the binary**, and
compares bytes against `/usr/bin/wc`. Sixteen cases, all byte-identical.

Each earns its place:

| fixture | what it separates |
|---|---|
| two lines | the three counts together |
| no trailing newline | lines are **newlines**: answers 0, not 1 |
| empty | three zeroes, not a blank line |
| UTF-8 | bytes are bytes (13) and words are words (2) |
| blank lines | empty lines count as lines and not as words |
| tabs | a tab separates words the way a space does |
| 10,000,000 bytes | the eight-digit format boundary |

Verified to fail as well as pass: counting word *characters* instead of word
*starts* fails three cases, dropping the tab from the whitespace set fails
two, and the fixed-width format fails exactly the boundary case and nothing
else.

## Cost is packaged, not supplied

Counting words is two host scans per word (`string-skip-blank` to the
word's start, `string-find-blank` to its end — amu context ABI v7,
2026-09-16; until then one guest call per **code point**), and counting
lines one host search per line inside a region (`arena-scope`) that
releases the search view, so the guest recursion is as long as the file
in words or lines and leaves nothing in the arena. Fuel and the string
arena are constants of the packaged binary (`--fuel`, `--string-pool`) —
like the grant and the filesystem scope, a caller cannot raise them. The
default 512 fuel counts almost nothing; package with a budget that matches
the files you mean to count.

Measured 2026-09-16 on a 33 MB C file (769,400 lines, 4,245,400 words),
CPU seconds user, counts identical to `/usr/bin/wc`:

| flag | this wc | this wc, 2026-09-15 | `/usr/bin/wc` |
|---|---|---|---|
| (none) | 0.21 | 0.68 | 0.11 |
| `-w` | 0.18 | 0.51 | 0.11 |
| `-l` | 0.06 | 0.20 | 0.01 |
| `-c` | 0.02 | — | 0.00 |

The host's blank set is space, `\t`, `\n`, `\v`, `\f`, `\r` — the six
`/usr/bin/wc` splits on in the C locale, measured on a file holding all
six (7 words both ways). The column padding of this wc is measured on the
suite's fixtures (below); on counts of seven digits and more the system
utility widens its columns and this does not, which is a known, unfixed
divergence of the format, not of the counts.

`-c` computes only bytes, `-l` only lines, `-w` only words. That is not a
micro-optimisation: computing words for `-c` would make the cheapest question
the most expensive one, and would put the eight-digit fixture out of reach of
a test that has to fit in fuel.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write` (37).

## Several files, and a `total` line

Each operand gets its own row, and **two or more** get a `total` row after
them. With one operand there is no total — the case an implementation that
always prints one fails, and it fails all 17 single-operand cases.

An unreadable operand is reported, **excluded from the totals**, and makes
the exit status 1 while the readable ones still print and still sum:
`wc h1 nope h2` totals 5, which is 3 + 2 and not 3 + 0 + 2. Measured against
`/usr/bin/wc` 2026-09-10.

That exclusion is deliberately *not* claimed as tested by the totals: a walk
that counted a missing operand as a zero row would produce identical sums.
What such a walk gets wrong is the per-file row, which is why every row is
compared too. The control that does bite the sums is stopping the
accumulation — every total becomes 0 and all 11 multi-operand cases fail.

### The totals cost a second walk

Three sums plus the index, the operand count and the flag is seven
parameters where the compiler admits five
(`kotoba.compiler.frontend/max-parameters`, an ABI arity limit rather than a
language decision), and a recursion can carry back only one `i64` in any
case. So the totals come from a second walk rather than from accumulators
threaded through the first.

The cost is real and worth naming rather than hiding: with no flag each
operand is read four times and its words counted twice. Since the ABI v7
scans the read is the larger share. If the arity limit moves, this
collapses into one walk.

## `-m` counts code points, `-c` counts bytes

Measured: a file holding `日本語`, a space, an `a` and a newline is **12
bytes** and **6 characters**.

Over an ASCII fixture the two agree, which is the whole reason the multi-byte
one carries the distinction: both controls — making per-file `-m` answer bytes,
and making the `total` row sum bytes — fail **only** the cases involving the
multi-byte fixture, and every ASCII case correctly survives them.

Each count is taken only when it will be printed. The character walk is one
guest call per code point, exactly like the word walk, so computing it for
`-c` would make the cheapest question the most expensive one.

### The flag is derived, not threaded

It used to be a `flagged?` parameter carried through four functions — a value
each of them could have disagreed about. There is one argument vector, so
there is one answer, and the functions ask for it.

## Standard input

With no file operand `wc` reads standard input (wire 41 `:io/read`,
2026-09-16) and prints the fields with no name column — 84% of how it is
invoked in agent tool use (5,092 of 6,096 over 1,268,018 measured Bash
calls; `wc -l | tr -d ' '` alone is 2,273). Whole-input form: input larger
than the binary's string pool is refused (exit 120), never counted short.

## What this is not

`-m` landed since the paragraph above was first written; what remains
unimplemented is nothing this README promises.
