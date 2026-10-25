# kotoba-lang/org-ieee-grep — fixed-string `grep`, as a Kotoba command binary

Line search in the shape of POSIX `grep` (IEEE Std 1003.1) restricted to
`-F`, written in `.kotoba` and compiled to a standalone native executable.

```sh
./grep PATTERN FILE...              # the lines containing PATTERN
./grep -i PATTERN FILE...           # ASCII case folded, and only ASCII
./grep -v PATTERN FILE...           # the lines that do NOT contain it
./grep -c PATTERN FILE...           # a count per file, printed even when 0
./grep -n PATTERN FILE...           # each line behind its 1-based number
./grep -l PATTERN FILE...           # the name of each file with a match
```

Exit **0** when at least one line was selected, **1** when none was, **2**
when an operand could not be read. For grep that status *is* the answer, so
it is asserted alongside the bytes.

## Search the file, not the lines (2026-09-15)

`string-index-of` is a **host slot** since context ABI v5 (amu
`tools/kexe_loader.c` offset 216, memmem). Until then it was a per-byte
source rewrite in kotoba-native, and this command — which asked it twice per
line — measured **75 ns/byte and trapped after 2 MB of a 3.3 MB file**, the
pair arena spending one handle per byte. Compiling the previous guest with
the v5 compiler alone already finishes that file.

The guest now has ripgrep's shape: find the **next occurrence** of the
needle in the whole remaining text with one call, find the line around it
(the last newline before the hit, looked for in a window that doubles
backwards; the newline after it), report, continue after that line. Text
between matches is never walked by this program. `-n` counts newlines
between matches instead, one call per line crossed. `-v` walks every
line, one call each. `-i` (2026-09-16, context ABI v7) is the same
next-occurrence walk over a **folded copy of the text**: `string-fold-ascii`
lowers A–Z in one host pass, one byte to one byte, so an offset into the
fold is the same offset into the original — matches are found in the fold
and lines are reported from the original.

Measured 2026-09-16 on a 33 MB C file (10× amu's loader source), CPU
seconds user / sys, same output as `grep -F` in every row:

| pattern | matches | this grep | `/usr/bin/grep -F` | `rg -F` | this grep, 2026-09-15 |
|---|---|---|---|---|---|
| `zzzznotthere` | 0 | 0.02 / 0.01 | 0.14 / 0.00 | 0.00 / 0.01 | 0.13 / 0.01 |
| `SIGILL` | 26,400 | 0.04 / 0.01 | 0.15 / 0.01 | 0.00 / 0.01 | 0.17 / 0.03 |
| `e` | 598,400 | 0.25 / 0.02 | 0.15 / 0.03 | 0.05 / 0.03 | 0.47 / 0.07 |
| `-i static_ASSERT` | 6,000 | 0.06 / 0.02 | 1.02 / 0.02 | 0.01 / 0.00 | 0.67 / 0.09 on 3.3 MB |
| `-i sigill` | 26,400 | 0.07 / 0.03 | 1.01 / 0.01 | — | — |
| `-i E` | 614,000 | 0.25 / 0.03 | 0.36 / 0.04 | — | — |

Re-measured 2026-09-16 on context ABI v8, where every search runs from an
offset (`string-index-of-from`) and no view is cut per search or per
line: `e` 0.25 → **0.18** s (rg 0.06), `-n e` 0.34, `-v e` 0.11, `-c e`
0.12, `-i E` 0.25 → 0.19; the sparse rows unchanged. What remains in the
dense case is the three writes per reported line and the two searches
around each match. On context ABI v10 (2026-09-16) the line searches take
the newline as a BYTE (`string-find-byte`, no needle handle, no region):
`e` 0.17 → **0.15 s**, `-n e` 0.31.

Ahead of `grep -F` when matches are sparse or absent and under `-i`
everywhere; behind it, and `rg`, when every line matches, where the cost
is about six host calls and three writes per reported line. What moved
the absent case from 0.13 to 0.02 is amu's loader: its `memmem` behind
`string-index-of` had been calling `memcmp` at every haystack offset, and
is now `memchr` for the first byte and one `memcmp` per candidate
(2026-09-16). What moved `-i` is the fold: 26 `string-replace-all` passes
per line became one host pass per file.

## Every match is a region (2026-09-16)

`(arena-scope body)` — context ABI v6, ADR-2609160044 — releases every
handle and byte its body allocated when it returns. Each allocating step
of a match (the search view, the line walk's views, the reported line's
view and its write counts) is one,
so the recursion carries only scalars and the arena stays where it was
after the file was read. Measured on the 33 MB file with 598,400 matching
lines, packaged with the loader's **default 4,096 handles**: completes,
identical output, 0.43 s user — the unscoped scan spent four handles per
match and needed millions. The suite packages 4,096 handles.

## The comparison is `grep -F`, and that is not a convenience

POSIX grep reads its pattern as a basic regular expression; this reads it
literally. Measured 2026-09-10 on a file holding `a.c` and `abc`:

```
grep    'a.c'  ->  a.c   abc      (both: `.` is any character)
grep -F 'a.c'  ->  a.c              (one)
```

Comparing against plain `grep` would be comparing two different operations
and calling the difference a bug.

## The newline grep adds — the opposite of `head`

A matched last line **without** a trailing newline is printed **with** one.
Measured: a 20-byte file whose only line has no newline produces **21**
bytes.

`head` adds nothing in the same situation. Two commands, two contracts, and
the only way to know which is which is to run them. Both are in this family
and both are tested for it.

## Measured against the system utility

`test/grep_test.cljk` compiles the guest, packages it (`AMU_HOME` must be
amu of 2026-09-15 or later — the suite refuses a packager that does not echo
`--cpu-seconds`), **runs the binary**, and compares bytes and exit status.
Eighty-four cases plus one asserted divergence, all as measured — fourteen
of them over a generated 80,000-line, 3.4 MB fixture with sparse matches, a
match on every line, no match, and every flag.

Each earns its place: two matching lines where one is a substring match
(`alpha` also finds `alphabet`), a no-match file, an *empty* file (not the
same thing), the added newline, a line matching more than once printed
**once**, a metacharacter, and a multi-byte needle in a multi-byte haystack.

Verified to fail as well as pass — and one control is worth naming. Dropping
the exit status while keeping the output fails three cases **on the status
alone**, with identical bytes on both sides:

```
FAIL ["zzz" "words"] -> "" but grep says "" exits [0 1]
```

A suite that compared only stdout would have called that green.

Not adding the newline fails exactly one case; matching whole lines instead
of substrings fails three.

## What this refuses

An **empty pattern**. `grep -F ''` matches every line; `string-index-of`
refuses an empty needle, and that refusal is a language invariant rather
than a gap. This exits **2** rather than pretending, and says so here.

## Several files: a prefix, and an exit status that is a worst-of

With **two or more** file operands every line of output is prefixed `FILE:`;
with one it is not. The prefix is the operand exactly as written, not a
resolved path. It is decided by how many operands there **are**, not by how
many turned out to be readable — and under a flag it reaches more than
matching lines, which the flag section below measures one at a time.

The exit status is where this is easy to get wrong. It is a three-way
worst-of, and the order is: an unreadable operand (**2**) beats a match
(**0**), which beats no match (**1**). Measured 2026-09-10:

```
grep -F alpha a.txt missing.txt
  -> prints a.txt's match, complains about missing.txt, exits 2   (not 0)
```

Two controls hold this down, and they are the two that a single-file
implementation passes everything else without: prefixing always instead of
only for several files fails **11** cases, and letting a match outrank an
unreadable operand fails exactly **2** — the two where a match and an error
occur together. `zzz words missing` keeps passing under that second control,
correctly, because there is no match there to outrank.

### The suite could not have failed, for one run

The twelve multi-operand cases were added and passed immediately. They should
not have: the harness built its argv as `[(first names) (second names)]` and
**silently dropped every operand past the second**, so both implementations
were handed one file and agreed about it.

The giveaway was in the output rather than the status — cases naming three
files printed the first file's lines with no `FILE:` prefix anywhere. Fixed
to map every operand after the pattern, at which point the prefixes appeared
and the cases became real.

## One flag, and it is found by SHAPE

Five flags, one at a time: `-i`, `-v`, `-c`, `-n`, `-l`. Argument 0 is the
flag when it **starts with `-`** and the pattern otherwise.

That is deliberately not the argument **count**, and the two are easy to
confuse because they agree on most invocations. They do not agree here:

```
grep -c alpha words        # three arguments: a flag, a pattern, one file
grep alpha words one       # three arguments: a pattern and TWO files
```

Both are in the suite. Deciding by length passes one and ruins the other —
sibling commands in this family have carried exactly that bug — and the
control below measures how far the damage reaches.

Combining flags is **out of scope**, and it is worth being specific about
what that excludes rather than leaving it as a shrug. `grep -F -vc alpha
words` writes `2` and exits 0 — the count of *non*-matching lines — and
`grep -F -in alpha mixed` numbers the folded matches. Both are coherent, both
are answerable, and neither is here.

So is any other dashed argument 0: this exits **2** rather than searching for
the text `-in`. `/usr/bin/grep` accepts `-in` and prints a usage block for
`-Q`, so neither shape is compared here.

### How each flag meets what was already there

Measured against `/usr/bin/grep -F` on 2026-09-10, since every one of them
changes what the `FILE:` prefix means:

| | one file | two or more |
|---|---|---|
| `-c` | `2` | `words:2` **and** `one:0` |
| `-n` | `1:alpha` | `words:1:alpha` — prefix first, number second |
| `-l` | `words` | `words` — the operand, with no trailing colon |
| `-v` | the line | `words:beta` — `-v` gets the prefix too |
| `-i` | the line | `mixed:Alpha` |

The three that are easy to guess wrong:

- **`-c` prints `0`.** `grep -F -c zzz words` writes `0` and exits **1**. The
  count is not suppressed; only the status says nothing was found. With two
  operands *every* file gets a line, so a file with no match still prints
  `one:0`.
- **`-c` prints nothing for an unreadable operand.** Not `missing:0` —
  nothing. `grep -F -c alpha words missing` writes `words:2`, complains on
  stderr, and exits **2**.
- **`-l` prints one line per FILE, not per match.** `words` holds two matches
  for `alpha` and yields one line. Its exit status is the ordinary one — 0 if
  any file matched, 1 if none did — and the same operand named twice is not
  merged, so `grep -F -l alpha words words` writes `words` twice.

`-n` numbers lines from 1 and **restarts at each file**; blank lines are
counted rather than skipped. `-v` selects blank lines, and its exit status
follows what was *printed*, so `grep -F -v a words` — where every line
matches — writes nothing and exits 1.

## `-i` folds ASCII, and only ASCII

There is no case-folding builtin on this surface, so `-i` folds by hand:
twenty-six replacements, `A`–`Z` to `a`–`z`, over the needle once per file
and over each line.

**Non-ASCII case is not folded, and the system utility folds it.** Measured
2026-09-10 in `en_US.UTF-8` on a file holding `Éclair` and `éclair`:

```
/usr/bin/grep -F -i É  ->  Éclair   éclair      (U+00C9 folds to U+00E9)
./grep         -i É    ->  Éclair               (it does not)
```

This is a real divergence, not a rounding error, and it is asserted in the
suite as one — both sides by name, and the requirement that they *differ*.
A case in the ordinary list would simply fail; a line missing from the list
would say nothing at all. As written, the day someone implements Unicode
folding the check goes red and asks for this section to be corrected, which
is the only way a documented limit stays true.

Everything with no case at all is unaffected: `-i 日本` and `-i PLAIN` over a
multi-byte file agree with the system utility exactly.

## The controls for the flags

Each flag was broken deliberately, the suite re-run, and the failures read.
A control that passes would mean the suite is weaker than it looks.

| control | cases failed | which |
|---|---|---|
| the fold does nothing | 6 | only `-i` cases, and only those where case actually differs |
| `-v` stops inverting | 7 | every `-v` case except the empty file, which selects nothing either way |
| `-c` hides a zero count | 4 | exactly the four with a zero in the expected output |
| `-n` puts the number before the prefix | 3 | exactly the multi-file ones — with one file the prefix is empty and the order is invisible |
| `-n` does not restart per file | 7 | every `-n` case, since the walk then starts at 100 |
| `-l` prints one line per match | 5 | every `-l` case that has a match |
| `-l` names every operand | 4 | exactly the `-l` cases holding a file with no match |
| `-l` writes the `FILE:` prefix | 5 | every `-l` case that has a match — with one file the prefix is empty, so the line comes out bare |
| **the flag is found by COUNT** | 26 | 11 of them are the *pre-existing* multi-file cases — a length test does not merely miss flags, it re-reads the flagless invocations too |

The last row is the one that earns its keep. The other eight break a flag;
that one breaks the boundary between "a flag" and "another file", and it
takes eleven cases that have nothing to do with flags down with it.

Two of the nine are worth naming for what they did **not** fail. Removing the
fold leaves `["-i" "Beta" "mixed"]` green, because `Beta` matches `Beta`
without folding, and it leaves the `É` divergence green too, because U+00C9
is outside the fold either way — so neither of those is evidence that
folding works. `["-i" "ALPHA" "blank"]` is in the suite precisely to be the
one that does go red while `["-i" "alpha" "blank"]` beside it stays green.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write` (37), `:io/write-error`
(39). Fuel, the string arena, the grant and the filesystem scope are
constants of the packaged binary.

## Standard input

With no file operand `grep` reads standard input (wire 41 `:io/read`,
2026-09-16) — 67% of how it is invoked in agent tool use (27,408 of 41,041
over 1,268,018 measured Bash calls), and `grep … | head` is the most frequent
pipeline shape of all (8,593). No `FILE:` prefix; `-l` answers
`(standard input)`, `-c` a bare count, exactly as `/usr/bin/grep` does.
Whole-input form: input larger than the binary's string pool is refused
(exit 120), never searched short.

## Flags combine; `-o`, `-h`, `-q`

Since 2026-09-17 the mode is a bit set — `-in`, `-i -n`, `-vc`, `-oin`, any
spelling of a set of {i, v, c, n, l, o, h, q} — and `--` ends the flags.
Measured over 1,268,018 agent Bash calls: `-n` 17,633, `-c` 7,822, `-v`
6,234, `-o` 3,183, `-i` 2,929, and every combination was an unknown flag
here while each letter alone was accepted. `-o` prints the match, every
match on a line (`grep -o a` over `aa` prints two lines), the cursor
resuming after the match; under `-i` the original text of the match; with
`-c`/`-l`/`-q` it changes nothing, and with `-v` the lines print, as BSD
grep does. `-h` drops the `FILE:` prefix; `-q` prints nothing. 40 cases
added, 136 compared in all, byte-identical.

## Regular expressions

Since 2026-09-17 a pattern with a metacharacter is a POSIX BRE, and under
`-E` an ERE, matched by [`org-ieee-regex`](https://github.com/kotoba-lang/org-ieee-regex)
(linked with `--source-path`; the suite reads `REGEX_HOME`, default the
sibling checkout). `-F` keeps a metacharacter literal. Measured over
1,268,018 agent Bash calls: `grep -E` is 9,582 of them, shaped as
alternations of words (`W|W`, `^(W|W)`, `^W |W`). 40 regex cases compared
against `/usr/bin/grep` (without `-F`), every flag with a regex, BRE vs ERE.

Three paths, in order of cost: a pattern with no metacharacter (and every
`-F` pattern) takes the literal path — one host search per occurrence; a
regex whose top-level alternatives all begin with a literal is *prefiltered*
— a line is simulated only when a host search finds one of those prefixes
in it (`SIGILL|static_assert` on 5.4 MB: 0.15 s user, `/usr/bin/grep`
0.13 s); any other regex is simulated on every line (`e+ in`: 4 s). The
prefilter is bounded to the line — its first cut searched the rest of the
file from each line and was quadratic.

One rule of the linked-module route, learned here: a capability call is
admitted only as a function's *result* — `(string=? (typed-cap-call …) "1")`
is refused once the namespace has a `:require`.

## What this is not

One pattern. No `-r`, `-w`, `-x`, `-e`, `-f`, `-A/-B/-C`, no back-references
in a pattern. `grep -r` over a tree needs the recursive walk that
[`org-ieee-find`](https://github.com/kotoba-lang/org-ieee-find) has, and that
runs into the string arena rather than into anything here.
