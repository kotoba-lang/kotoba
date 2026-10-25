# kotoba-lang/org-ieee-sort — POSIX `sort`, as a Kotoba command binary

`sort` from IEEE Std 1003.1, in byte order, written in `.kotoba` and compiled
to a standalone native executable.

```sh
./sort FILE...
./sort -r FILE...     # descending
./sort -u FILE...     # adjacent duplicates dropped after sorting
./sort -n FILE...     # by a leading numeric key
```

**One flag, and it is argument 0.** Combining them (`-rn`, `-r -u`, `-nu`) is
out of scope and is not implemented — see *What this is not*.

## The ordering is one host call (context ABI v7, 2026-09-16)

Until 2026-09-16 the language had no string comparison but `string=`
(which is why [`org-ieee-ls`](https://github.com/kotoba-lang/org-ieee-ls)
records `-a` as needing "a merge into byte order" it could not do), and
`less?` walked both lines with `string-code-point-at` — one host call per
code point per line per merge level. **UTF-8 preserves code point order
lexicographically**, so that walk *was* byte order, and so is what
replaced it: `string-compare` (amu context ABI v7, slot 240) is the
loader's `memcmp` over the common prefix, the shorter first. `less?` is
one call.

## Byte order, so the comparison is `LC_ALL=C sort`

Measured 2026-09-10:

| input | default locale | `LC_ALL=C` |
|---|---|---|
| `b a B A` | `a A b B` | `A B a b` |
| `日 é z` | `日 é z` | `z é 日` |

This produces the second in both cases. Comparing against the first would be
comparing two orderings.

`sort` also **adds** the newline a last line lacks — 13 bytes in, 14 out.
Same as `grep`, opposite of `head`.

## The flag is argument 0's SHAPE, never the argument COUNT

`org-ieee-cut` asked `(= 3 count)` until 2026-09-10. That is right for
exactly one operand and silently wrong for two: `cut -f1 a b` counts 3 and
reads as carrying a `-d`. The bug is invisible until a second operand exists.

So this asks whether argument 0 begins with `-`, which keeps its answer when
a second operand shows up. Operand paths are absolute here, so they begin
with `/` and cannot collide.

The control is `flag-by-count`: replacing the shape test with
`(string=? (arg "") "2")` fails **19** cases, and it fails them in *both*
directions — the eleven two-operand cases with no flag now refuse as if they
carried one, and the eight three-argument flag cases now try to open `-r` as
a file. That is the sibling's bug, reproduced.

## `-n`, measured one shape at a time

Every one of these was a guess with an answer. The model that fits **all** of
them, and the only thing this implements:

> `key(line)` is the leading numeric prefix, after `[ \t]*` and an optional
> `-`. Ties on the key are broken by comparing the **whole line** in byte
> order.

Six things the measurement contradicted:

| assumption | measured `LC_ALL=C /usr/bin/sort -n` | so |
|---|---|---|
| `-n` is stable for equal keys | `1 01 " 1" 1x` → ` 1`, `01`, `1`, `1x` | it is **not** input order, it is byte order — the tie-break the merge applies |
| a leading `+` is a sign | `+5 3 +1 10` → `+1 +5 3 10` | `+` is **not** accepted; both plus lines are key 0 |
| blanks are whitespace | `\v7 \f6 5` → `\v7 \f6 5` | only **space and tab** are skipped; `\v` and `\f` leave the line non-numeric |
| the tiebreak is the part after the number | `1a 01b` → `01b 1a` | it is the **whole line** |
| `-0` is negative | `-0` vs `  0` → `  0` first | `-0` **equals** 0; the sign loses and the byte tiebreak decides |
| the key is a number | 30 ones vs 29 ones and a `2`, ordered right | it is **decimal digits**. No `i64` and no float can tell those apart |

And the rest, all reproduced:

- **not a number at all** → key 0, then the whole-line tiebreak.
  `banana 10 apple 9 2` → `apple banana 2 9 10`.
- **an empty line** → key 0, and first, because `""` is bytewise least.
  A blank-only line (`" "`) is also key 0 and sits after `""`.
- **leading whitespace** → space and tab skipped, then the number.
- **a leading `-`** → negative, but only if digits follow immediately:
  `- 5` is key 0, and a lone `-` is 0.
- **a leading numeric PREFIX**, not the whole line: `10abc 9xyz 2zzz` sorts
  `2zzz 9xyz 10abc`, `3abc9` is 3, and `1e3` is **1** — there is no exponent.
- **fractions**: `1.10 < 1.25 < 1.5`. `.5` is 0.5, `5.` is 5, `1.2.3` is 1.2,
  and `1.5 = 1.50 = 1.500` so the byte tiebreak orders them.
- **leading zeros** do not change the value: `007` and `7` tie, and `007`
  wins the tiebreak.

### What `-n` does NOT implement, and refuses rather than approximates

- **No exponent** (`1e3` is 1). This is not an exclusion — it is what the
  system utility does, measured.
- **No `+` sign, no `\v`/`\f` blanks.** Same: measured, not omitted.
- **No thousands separator and no locale decimal comma.** The suite runs
  `LC_ALL=C`, where neither exists. Under another locale this would be wrong
  and the README would be lying, which is why the locale is pinned.
- **No `-b`, `-k`, `-t`, `-g`, `-h`, `-V`.** The key is always the whole
  line's leading number.

The comparison is exact decimal, so it does not overflow and there is no
`text->i64` in this program: integer parts compare by significant-digit
count and then left to right, fractions compare digit by digit with a
missing digit reading as `0`.

That last rule looks untestable and is not. On the positive side, extra
fraction digits make a number both larger *and* bytewise later, so
"missing reads as 0" and "stop at the shorter fraction" agree on every
positive input. **Negated they disagree**: measured, `-1.5` and `-1.50001`
answer `-1.50001` first, where the byte tiebreak would have answered `-1.5`
first. The `nfracn` fixture is that shape, and it is the only reason the
rule is checked rather than assumed.

## Measured against the system utility

**98 cases**, all byte-identical on stdout, stderr and exit status.

### Every control, and exactly what it broke

Each is a deliberate single-line break, re-run, then restored.

| control | what it does | fails |
|---|---|---|
| `HARNESS-flag-as-path` | joins the flag onto the fixture directory in the *test* | **0 — see below** |
| `flag-by-count` | asks the argument count instead of argument 0's shape | 19: every two-operand case with no flag, and every three-argument case with one |
| `r-noop` | `-r` compares ascending | 12: every `-r` case whose answer is order-dependent |
| `u-nodedupe` | `-u` keeps duplicates | 7: exactly the `-u` cases that have a duplicate |
| `append-join` | restores the joined accumulator | 3: `-r` on `blank`, `trailblank`, `twoblank` |
| `n-lexical` | `-n` compares bytes | 20, all `-n` |
| `n-no-tiebreak` | `-n` gives up on an equal key | 17, all `-n`: every fixture with a tie |
| `n-minus-zero-negative` | `-0` sorts as negative | **1**: `nzero` |
| `n-vf-are-blanks` | `\v` and `\f` skipped as blanks | **1**: `nws` |
| `n-accept-plus` | a leading `+` reads as a sign | **2**: `nplus`, `nplus2` |
| `n-i64-parse` | integer parts through a `text->i64` digit walk | **1**: `nbig` (21 digits, and the walk overflows) |
| `n-frac-shortstop` | fractions stop at the shorter span | 3: `nfracn`, `nfracn2`, `ndot` |

The `-r` cases that survive `r-noop` are `one`, `empty`, `missing` and
`fruit missing` — one line, no lines, and two error paths. The `-u` cases
that survive `u-nodedupe` are the ones with nothing duplicated. Neither
survival is a gap; there is no order to get wrong.

### The control that passed, and what it found

`HARNESS-flag-as-path` is a control on the **test**, not on the program, and
it is the one that mattered. Path-joining `-r` onto the fixture directory
produces `/tmp/.../-r`, which does not exist — so *both* implementations fail
with the same `sort: No such file or directory` and the same exit 2, and the
suite reports **`{:ok true, :cases 98, :failed 0}`** with all 72 flag cases
green and none of them executing a flag.

That is one argument to the left of the bug this repo already carried: the
harness built argv as `[(first names)]` until 2026-09-10 and dropped every
operand past the first, so twelve multi-operand cases passed while printing
one file's lines. Same shape, same silence. The fix is that a name beginning
with `-` is passed through verbatim, and the evidence that it is load-bearing
is that removing it turns 72 real cases into 72 vacuous ones.

### One fixture that discriminates nothing, said plainly

`nbig2` is 31 ones against 30 ones and a `2`. **It survived all twelve
controls** — zero failures, against `nbig`'s two. A `text->i64` overflows there in a way that happens to preserve
the order, and a binary float collapses both to the same value and then falls
to the byte tiebreak, which also preserves the order. No wrong implementation
that could be built here fails it.

It is kept as a *witness* — it pins the 31-digit answer if someone later
swaps the digit compare for arithmetic — but it is not evidence, and calling
it evidence would be the thing this repo keeps warning about. **`nbig` is the
fixture that carries the discrimination**: 21 digits, and `n-i64-parse` fails
exactly it.

## The bug `-r` found in code that was already green

`append-line` used to **join**: an empty accumulator meant "nothing appended
yet", so it emitted the line alone rather than a separator and the line.

An accumulator holding **one empty line** is also the empty string. The two
were the same value, and the line was lost.

Ascending never showed it. An empty line is the smallest line there is, so it
is emitted first and never sits alone in the remainder — all 25 cases passed.
`-r` puts it **last**: on `a\n\n` this answered `a` where `/usr/bin/sort`
answers `a` and then an empty line.

It now **terminates** rather than joins, so "no lines" and "one empty line"
are the distinct values `""` and `"\n"`. It costs the same two
concatenations. `append-join` restores the old form and fails exactly the
three `-r` cases with an empty line.

## The lines are never moved until they are written (index sort, 2026-09-16)

A vector holds the byte offset where each line starts; a bottom-up merge
sort orders the **offsets** between two vectors written in place
(`vector-assoc!`, one store per element per level); the sorted text is
appended from the offsets at the end, a thousand lines per region. A
comparison is one host call over the two lines in place
(`string-compare-lines`, context ABI v8, newline excluded — with it a
line holding a tab would sort after a line it is a prefix of); only `-n`
cuts views, for its numeric keys, inside a region. The loader's default
**4,096 handles** suffice; what the command is packaged with is
`--vector-items`, two words per line, and the line count is what bounds
the file it can sort.

What made this possible is `kotoba.kir.value/vector-item-limit` moving
from 16,384 to 2^24 (osaho #93, owner decision 2026-09-16) and amu's
vector arenas becoming per-run budgets. Before it, a merge sort over the
**text** rebuilt the whole file at every level with the tail append and
searched every line end again (2026-09-15 → 09-16: selection sort that
trapped at 4,600 lines → text merge 12.5 s → ABI v7 3.0 s → ABI v8 2.69 s).

Measured 2026-09-16, CPU seconds user, output identical to `LC_ALL=C
/usr/bin/sort` and to uutils `sort` (Rust):

| input | this sort | `-r` | `-u` | `-n` | `/usr/bin/sort` | uutils `sort` |
|---|---|---|---|---|---|---|
| 3.3 MB / 76,940 lines | 0.06 | — | 0.06 | 2.25 | 0.03 | 0.01 |
| 33 MB / 769,400 lines | **0.62** | 0.63 | 0.64 | **0.86** | 0.38 | 0.17 |

Text merge, same file, same day: 2.69 s; the index sort on the ABI v8
loader 0.83 s; with context ABI v9 — kotoba-native ADR 0084 emits
`vector-at` / `vector-assoc!` / `vector-count` in line, and the loader
resolves a string once when both compared lines are in it — 0.66 s; with
context ABI v10 (the line ends found as a byte, `string-find-byte`, and
the output appended as ranges, `string-append-range`, no needle handle and
no view per line) — **0.62 s**.
Sampled, what remains is the comparison itself (one pass, eight bytes at
a time, in the loader) and the call around it, then the output phase's
view and append per line.

`-n` computes its key **once per line** (2026-09-16): the numeric prefix
as `sign × (integer × 1000 + fraction)` when the integer part has at most
six significant digits and the fraction at most three, packed into the
line's vector word beside its offset; anything wider carries a sentinel
and is compared by the exact digit-by-digit path over views, so the order
is the same total order as before. 33 MB: fuel-exhausted → **0.87 s**
(`/usr/bin/sort -n` 0.79, uutils 0.43). A 200,000-line corpus mixing
negatives, 5-digit fractions, 12-digit integers, `-0`, `+5`, `1e3`, `.5`
and `\t7`: 2.37 s → 0.77 s, identical to `/usr/bin/sort -n` on both.
(The first cut packed "unrepresentable" as a −1 low half, which read
back as 2³²−1 after the shift; the corpus caught it.)

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write` (37), `:io/write-error`
(39).

## Several files are MERGED, not sectioned

`sort` has no headers and no per-file structure: the operands are read
together and sorted as one, so the operand order does not change the output.
Duplicates survive — the same file twice yields every line twice, and under
`-u` it yields one copy.

### A last line with no newline stays whole

This is the case that separates reading operands as **lines** from
concatenating their **bytes**. Measured against `/usr/bin/sort` 2026-09-10,
where `nn.txt` holds `x` with no trailing newline:

```
sort nn.txt s2.txt         ->  a  c  x        `x` is its own line
cat nn.txt s2.txt | sort   ->  c  xa          `x` and `a` ran together
```

So each operand is terminated before the next is appended. The control is
precise: dropping that termination fails exactly the two cases where the
unterminated file is *followed* by another operand, and leaves
`["fruit" "nonl"]` passing — nothing follows it there to run into.

### An unreadable operand writes nothing at all

Not the readable operands, not a partial answer: `sort s1 nope s2` exits 2
with empty stdout, where `cat` and `wc` print what they could. So every
operand is checked **before** any is read. Removing that check fails all four
missing-operand cases.

Measured again with each flag: `sort -r nope`, `sort -u nope` and
`sort -n nope` all answer identically — exit 2, empty stdout, and
`sort: No such file or directory` — so the flag does not change this path.

## What this is not

- **No combined flags.** `-rn`, `-nu`, `-r -u` and `-un` are out of scope.
  Argument 0 is one of `-r`, `-u`, `-n` or it is an operand.
- **Flags combine** (2026-09-17): `-rn`, `-nr`, `-r -n`, `-rnu` — any
  spelling of the set {r, n, u}. `sort -rn` is 1,031 of the measured agent
  calls and was refused while `-r` and `-n` alone were accepted. Under `-nu`
  numerically equal lines are one line (`1`, `1.0`, `01`; any two
  non-numbers) and the one kept is the *first in input order* — `-u` makes
  the numeric comparison stable, where plain `-n` tiebreaks equal keys by
  bytes. Both measured on `/usr/bin/sort` and pinned.
- **No `-k`, `-t`, `-f`, `-b`, `-c`, `-m`, `-o`, `-s`, `-g`, `-h`, `-V`.**
- **Standard input is read when there is no operand** (wire 41 `:io/read`,
  2026-09-16) — with or without a flag. 97% of `sort`'s invocations in agent
  tool use are a later pipeline segment (6,046 of 6,208 over 1,268,018
  measured Bash calls; `sort | uniq` alone is 1,889). Whole-input form: input
  larger than the binary's string pool is refused (exit 120), never sorted
  short. The suite feeds fixtures — including the 3.6 MB one — to both
  binaries as stdin.
- **`-` is not standard input**; it is rejected as an unknown flag.
- **An unknown flag is not reproduced byte for byte.** `/usr/bin/sort -x`
  exits 2 with `sort: invalid option -- x` followed by the whole BSD `Usage:`
  block, and `--bogus` words it differently again. That block is a
  BSD-`sort`-version-specific string; copying it would pin this suite to one
  build of one utility. This exits 2 and writes `sort: invalid option`, which
  is **not** byte-identical, and there is therefore **no test case for it** —
  named here rather than left for someone to discover.
