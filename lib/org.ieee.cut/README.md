# kotoba-lang/org-ieee-cut — POSIX `cut`, as a Kotoba command binary

`cut` from IEEE Std 1003.1, the single-field form, written in `.kotoba` and
compiled to a standalone native executable.

```sh
./cut -f 2 FILE      # field 2, delimited by TAB
./cut -d: -f2 FILE   # field 2, delimited by :
```

## Two behaviours that carry most of the weight

**A line with no delimiter is printed whole.** `cut -d: -f2` over a line
reading `nofield` answers `nofield`, not the empty string. That is the
behaviour, not an edge case — `-s` suppresses such lines, and this does not
implement `-s`.

**The default delimiter is a TAB, not a space.** `cut -f2` over `a:b:c`
answers the whole line, because there is no tab in it; over
`one<TAB>two<TAB>three` it answers `two`.

A tab cannot be written in Kotoba source (no control characters, no
char-to-string builtin), so it is cut from a literal that contains one — the
same trick a newline needs.

## The case that caught the real bug

Asking for a field **past the last one**. `-f4` over a three-field line must
answer nothing; before it was fixed this answered `c`, and `-f1`, `-f2` and
`-f3` all agreed.

The mistake was conflating two different questions. Running out of
delimiters *at the top level* means the line has none, and the whole line is
the answer. Running out *mid-descent* means the line has fewer fields than
were asked for, and the answer is empty. `field-of` asks the first question
before the walk starts.

## The list is a set, not a sequence

`-f` takes a list — `-f2,4`, `-f2-4`, `-f2-`, `-f-3`, and mixtures. Measured
against `/usr/bin/cut` 2026-09-10, it behaves as a **set tested per field**
rather than a sequence to walk:

```
-f3,1  -> a:c    output is ASCENDING, not the order written
-f1,1  -> a      a repeat selects the field once
-f2,9  -> b      a field past the end is skipped, not an empty field
-f3-1  -> ""     a descending range selects nothing, and still prints a line
```

So this asks "is field n selected" for n = 1, 2, … in order. Ascending order,
de-duplication and out-of-range skipping all fall out of that — none of them
needs a sort, which is fortunate, because there is no ordering primitive to
sort with.

An absent low bound is 1 and an absent high bound is unbounded, but an absent
**item** is zero: `-f1,`, `-f,1`, `-f` and `-f-` all report *values may not
include zero*, while `-f1-` and `-f-1` are well formed. Both diagnostics are
compared byte for byte.

## Measured against the system utility

Thirty-six cases, all identical on stdout, stderr and exit status: fields 1,
2 and 3; past the last field, twice; no delimiter; an empty file; a leading
and a trailing delimiter (the empty field on each side **is** a field); a
multi-byte field; the tab default with and without a tab present; a missing
operand; the ten list and range cases above; and seven malformed lists across
both diagnostics.

Verified to fail as well as pass. The single-field controls each fail exactly
two cases: the field-overrun bug fails `-f4` and `-f9`, treating an
undelimited line as an empty field fails `nosep` and the tab-default case,
and making the default a space fails both `tabs` cases. The list controls are
just as narrow — writing the delimiter before every selected field instead of
between them fails 18 cases with a leading `:`, and bounding the walk by a
constant instead of the line's field count fails exactly 4, of which
`-f2,9 -> b:` is precisely the skipped-field claim.

## One pass per line, one write per KB (2026-09-16)

The list is parsed **once** into an i64 — a bit per field up to 40, the
last selected field (or the smallest open range) in the high twenty bits,
`-s` in bit 0 — and each line is walked once, field by field, stopping
after the last selected field. Until then every field of every line
re-parsed the list and every line was walked twice (once to count fields,
once to cut), which was **1.6 s** of a 33 MB cut where `/usr/bin/cut`
spends 0.04.

Selected fields are **appended** to an accumulator (amu's tail append:
`string-concat` onto the pool's last allocation costs the bytes and
nothing else) and the accumulator is written once per KB of input; a
write is a capability call measured at about 100 ns, and there were two
per line. Every batch is a region (`arena-scope`, context ABI v6), so its
views and its accumulator are released when it answers and the suite
packages the loader's **default 4,096 handles**. A line of thousands of
fields is cut in chunks of 256 fields, each its own region and write —
measured on 50 lines of 3,000 fields, every field selected.

Measured 2026-09-16, CPU seconds user, output identical to
`/usr/bin/cut` and to uutils `cut` (Rust) on a 33 MB C file, 769,400
lines, `-d' '`:

| list | this cut | this cut, before | uutils `cut` | `/usr/bin/cut` |
|---|---|---|---|---|
| `-f2` | **0.13** | 1.58 | 0.03 | 0.04 |
| `-f1,3` | 0.26 | — | 0.05 | — |
| `-f2-4` | 0.31 | — | 0.05 | — |
| `-f9` | 0.42 | — | 0.09 | — |
| `-f3-` | 0.76 | — | 0.14 | — |
| `-s -f2` | 0.19 | — | 0.03 | — |
| `-f1,1,5,60` | 0.65 | 9.75 | 0.14 | — |

What remains per line is about six host calls — one search per field
(`string-index-of-from`, context ABI v8, from an offset with no view cut)
and the field's view, one search and a view for the line, the appends —
so a list naming a field above 40 (asked of the list itself, per field,
`-f60` above) and a list reaching every field (`-f3-`) pay in proportion.
Dropping the search views (ABI v7 → v8) did not move `-f2` at all: the
cost is the calls, about 30 ns each over a 33 MB text, not the handles.

Context ABI **v10** (2026-09-16) then removed the views themselves: when
the delimiter is one ASCII byte and no field number needs more than 13
bits, a line is cut over the text by offsets — the newline and each
delimiter found as a BYTE (`string-find-byte`, no needle handle, no
region), each selected field appended as a range (`string-append-range`,
no view), the delimiter between fields as the byte before the field and
the newline as the byte at the line's end. Per line: one search per field
read and one append per field written, nothing else. `-f2` 0.19 → **0.13
s**, `-f3-` 0.77 → 0.61, `-f9` 0.42 → 0.31 (uutils 0.03 / 0.14 / 0.09). A
multi-byte delimiter or a field past 8191 takes the general walk above.

## Five parameters

A function carries five parameters (`kotoba.compiler.frontend/max-parameters`
— an ABI arity limit, not a language decision), so the walk packs its
cursor, field number, handle budget, "written anything yet" flag and
"last line" flag into one i64 (`pk`), and the batch packs its cursor and
bytes consumed into another.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write` (37), `:io/write-error`
(39). A missing operand is reported byte-for-byte using wire 35's `EXISTS`
form.

## Several operands, each cut on its own

There are no headers; each operand is cut in turn and the outputs follow one
another. What makes two operands *look* like a single byte stream is a
per-line rule, not concatenation:

**A last line with no trailing newline gets one only if a field was
extracted.** Measured 2026-09-10 — `cut -d: -f1` over `nonl-x:nonl-y` answers
`nonl-x\n` (7 bytes), and over `g` answers `g` (**1 byte, no newline**),
because an undelimited line is echoed whole and its termination is preserved.

```
cut -d: -f1 bare colon   ->  ga / d            bare had no newline, so `a` follows it
cut -d: -f1 nonl colon   ->  nonl-x / a / d    a field was cut, so it did not
```

The first of those was misread as *"cut concatenates its operands"* while this
was being written. It does not — the previous operand's output was simply
unterminated. Those two cases together are what distinguish the models, and
both are in the suite.

### The single-operand suite could not see it

Every undelimited fixture ended in a newline, so this rule was never
exercised and the implementation terminated the last line unconditionally.
The control shows the reach: making it unconditional again fails three cases,
one of which is **single-operand** (`-f1 bare`) — a latent bug that only two
operands made visible.

An unreadable operand is reported and the readable ones are still cut and
printed, with exit 1 — where `sort` refuses to print anything at all.

## `-s` suppresses exactly the lines cut would echo whole

A line with no delimiter is printed whole — that is the behaviour this README
opens with — and `-s` is the flag that drops those lines instead. An **empty**
line has no delimiter either, so `-s` drops it too.

`-s` is about the **delimiter, not the field**: a delimited line that lacks
the requested field still prints an empty line under `-s`.

Removing the suppression fails **5** cases — exactly those containing an
undelimited line, while a fully-delimited fixture correctly survives, since
there is nothing there to suppress. Letting a suppressed line still emit its
newline fails **3**: otherwise `-s` replaces each dropped line with a blank
one.

## The flags are scanned, not indexed

`-d: -s -f1`, `-s -d: -f1` and `-d: -f2 -s` are one request. This used to ask
whether argument 0 began with `-d` and take the operand from a fixed offset —
a positional assumption that `-s` breaks in three places at once. The
arguments are now scanned, and a scan has no position to be wrong about.

Restoring fixed offsets fails **11** cases: every `-s` one. That is the
measure of how load-bearing the change is — it is not tidying.

## Standard input

With no file operand `cut` reads standard input (wire 41 `:io/read`,
2026-09-16) — 97% of how it is invoked in agent tool use (7,766 of 7,976
over 1,268,018 measured Bash calls; `head | cut` alone is 1,481). Whole-input
form: input larger than the binary's string pool is refused (exit 120), never
cut short.

## `-c`: character positions

`cut -c1-200` and its siblings are 5,598 of 1,268,018 measured agent Bash
calls (2026-09-17) — the most frequent cut flag; agents truncate lines
before they reach the context window. Positions count code points, as
`/usr/bin/cut` does in a UTF-8 locale (`-c1-3` of 日本語テスト is 日本語 —
the suite's multi-byte cases). The list grammar is `-f`'s. The list becomes
a 4,096-entry table plus one open lower bound; selected characters are
written as runs, one line per `arena-scope`, which is what let 1 MB through
a 4,096-pair budget (a view per character had not). Positions past 4,095
are refused with a message; two open ranges (`5-,9-`) are exact under 4,096
and take the last bound beyond it — a named divergence, not a measured
shape.

## What this is not

No `-b`, `-n`. `-d` must be joined to its argument (`-d:`), `-f` and `-c`
to their lists (`-f2`, `-c1-80`).

One malformed spec is classified differently from BSD `cut`: a list with
whitespace in it (`-f'1 ,2'`) is reported here as *illegal list value* where
`/usr/bin/cut` reports *values may not include zero*. That case is left out
of the comparison rather than papered over — the other seven malformed
shapes agree byte for byte.
