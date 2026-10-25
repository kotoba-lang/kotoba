# kotoba-lang/org-ieee-awk — POSIX `awk`, the print statement over regex patterns

A documented **subset** of `awk` from IEEE Std 1003.1 — the `print` statement,
over a regular-expression pattern (on the record, on a field, or a range),
with an optional explicit field separator and `exit` — written in `.kotoba`,
compiled to a standalone native executable, linked with
[`org-ieee-regex`](https://github.com/kotoba-lang/org-ieee-regex).

```sh
./awk '{print}'                 # the record, verbatim
./awk '{print $0}'              # the record, verbatim
./awk '{print $N}'              # field N, empty past the end
./awk '{print NF}'              # how many fields the record has
./awk '/RE/'                    # the records matching RE (an ERE)
./awk '/RE/ {print ...}'        # the action, on those records only
./awk '$N ~ /RE/ {print ...}'   # on records whose field N matches
./awk '/A/,/B/ {print ...}'     # from a record matching A through the next matching B
./awk '/A/,0'                   # from A to the end of the input
./awk '/RE/ {print $N; exit}'   # the first such record, then stop
./awk -FX '...'                 # an explicit field separator
```

133 cases agree with `/usr/bin/awk` (version 20200816) on stdout, stderr and
exit status. Twelve more are divergences this deliberately owns, asserted
against written-out bytes rather than compared — they are listed below.

**Anything outside those shapes is refused with a diagnostic**, not
half-interpreted. `{print $1, $2}` is not "print $1"; it is a program this
cannot represent, and answering it with a plausible-looking wrong line is worse
than refusing it.

## The program is read once (2026-09-15)

Every record used to re-derive the action, the field index, the pattern
and the separator from argv — `act-kind` alone is `print-form?` →
`action-text` → `body` → `trim (prog-text)` → wire 38 — and every wire
answer is interned in the string pool with a handle. Measured on a 33 MB
file: **362 handles and 275 pool bytes per record**, SIGILL at record
185,055 with the 64 Mi handle arena spent. `run` now reads the program once
into a packed `cfg` plus the pattern and separator strings and carries them
through `each` → `walk` → `show`.

Measured, CPU seconds user, output identical to `/usr/bin/awk`:

| program | 33 MB (769,400 records), 2026-09-16 | 33 MB, 2026-09-15 | `/usr/bin/awk`, 33 MB |
|---|---|---|---|
| `{print $2}` | **0.32 s** | 1.31 s (before 2026-09-15: SIGILL) | 1.11 s |
| `{print NF}` | **0.42 s** | 2.60 s | 1.20 s |
| `/SIGILL/` | **0.09 s** | 0.36 s | 1.41 s |
| `{print}` | **0.20 s** | 0.40 s | 1.14 s |

Re-measured on context ABI v8 (2026-09-16), the record walk searching
from an offset with no view (`string-index-of-from`): `{print $2}` 0.32 →
**0.26** s, `{print NF}` 0.42, `/SIGILL/` 0.10, `{print}` 0.20 → **0.15**. On context ABI v10 the record walk finds the newline as a byte
(`string-find-byte`, no needle handle, no region): `{print $2}` 0.26 →
**0.23 s**.

## The field walk is one host scan per blank run (2026-09-16)

`next-blank` is `string-find-blank` (amu context ABI v7): one scan that
stops at the first blank, where it had been a view and two whole-line
searches per blank run — the tab search walking to the line's end on
every line without one. The host's blank set is six characters and awk's
default separator is **space and tab only** (measured: `a\vb\fc\rd e` has
two fields, `\va b` keeps its `\v` in `$1`), so a `\v`, `\f` or `\r` the
scan stops on is read — it is ASCII, so a boundary — and stepped over.
`ltrim` reads one code point per leading blank instead of searching the
whole line for a space and again for a tab.

Records are walked by a scalar cursor and every record is a region
(`arena-scope`, ABI v6): its search view, its fields and its writes are
released as `show` answers, so the 33 MB file runs under the loader's
**default 4,096 handles** (the table above was packaged with them).

## Regular expressions (2026-09-17)

Measured over 5,025 single-quoted agent awk programs: 842 hold a regular
expression — `/A/,/B/` 175 (conflict-marker hunks), `/RE/{print $N}` 71,
`/RE/,0` 24, `$N ~ /RE/` 36, `/RE/{print $N; exit}` 10. The rest need
variables (`/RE/{f=1} f&&/RE/`), `NR`, `getline` or `printf`, and are refused.

A pattern is an ERE compiled by `org-ieee-regex` (leftmost-longest, with its
literal prefilter so a host search skips most records before the
simulation); a pattern without a metacharacter keeps the literal host search;
`//` matches every record; `\/` inside a pattern is a slash. Measured on
`/usr/bin/awk`:

```
/a/,/b/       a range ENDS ON THE SAME RECORD it starts on when the end
              matches there too (unlike sed, which tests from the next line);
              ranges restart after they end
/a/,0         never ends: from the first match to the end of the input
/a/,3         a non-zero constant is true: each start is a one-record range
$2 ~ /b/      the field, split as the record is (-F applies); $9 past the
              end is the empty string, so $9 ~ /^$/ selects every record
{print $1; exit}   prints, then stops every operand; exit 0
/a[/          refused, exit 2, in awk's four-line shape with the engine's
              words (a named divergence: awk says `nonterminated character
              class a[`, this says `brackets [ ] not balanced`)
```

The same caveat as before applies to a multi-character `-F`, which the system
awk reads as an ERE and this reads literally; the suite's multi-character
separators (`ab`, `aa`, `日`) contain no metacharacter, so both sides answer
the same question there.

A **single-character** `-F` is literal in the system awk too — measured: `-F.`
splits `a.b.c` into three fields and leaves a dotless record alone — so that
case is a real comparison, not a caveat.

## What was measured against `/usr/bin/awk`, 2026-09-10

```
{print} / {print $0}   the record VERBATIM: leading and trailing blanks kept,
                       and a missing final newline is ADDED
default splitting      on RUNS of space/tab, ignoring leading and trailing
                       ones: "  spaced   out  " is $1=spaced, $2=out, NF=2
blank-only record      NF=0
empty record           NF=0, and $1 prints an EMPTY LINE, not nothing
$9 past the end        an empty line — it still prints a line
-F:                    empty fields COUNT. a::b is NF=3 with $2="";
                       :lead is NF=2 with $2=lead; trail: is NF=2 with $2="";
                       an EMPTY record is still NF=0, not one empty field
-F: on a record with no colon in it    NF=1, and $1 is the whole record
-F. and -Fxy           taken literally
-Ft                    a TAB — awk's own special case for the letter t
-F' '                  a single space means DEFAULT splitting
''                     an empty program: exit 0, no output, and the operands
                       are never opened — a missing one is NOT reported
several operands       processed in order, as one stream
```

## The diagnostic for a file that will not open has three lines, not one

```
awk: can't open file nope.txt
 input record number 3, file nope.txt
 source line number 1
```

Exit 2, and processing **stops**: `awk '{print}' nope.txt plain` writes nothing
from `plain`. That is not what `cut` or `sed` do — both of those report and
carry on — so it was measured here rather than carried across.

The middle line appears only when some record has already been read (awk's own
condition is `NR > 0`), and the number it carries is **FNR** — the record count
of the file just before, not the running total:

```
plain colon nope   ->  3    plain has 2 records and colon 3; NR is 5
plain empty nope   ->  0    an empty file opens and resets FNR
empty nope         ->  the line is ABSENT: nothing had been read
```

Those last two are the pair that separates "a record has been read" from "a
file has been read". Both are cases.

### `argv[0]`, and the one thing the harness normalises

The first line names awk by its own `argv[0]`: invoked as `/usr/bin/awk` it
says `/usr/bin/awk:`, and through a symlink it says `./myawk:`. There is no
capability that answers "what am I called", so this command says `awk`, and the
suite spawns the system awk with `argv0` set to `"awk"` so the comparison is
about the *message* rather than about the path each was invoked by.

That is the only normalisation. Dropping it (a control) fails exactly the ten
missing-file cases and nothing else, which is the evidence that it is narrow.

## Divergences this owns

Asserted against written-out bytes in `test/awk_test.cljk`, and not compared —
the system awk answers a different question in each.

| input | here | `/usr/bin/awk` |
|---|---|---|
| `{print $1, $2}` | `awk: unsupported program: …`, exit 2 | prints two fields |
| `{print $x}` | refused at parse, exit 2 | `illegal field $(), name "x"` at the first record, exit 2 |
| `{print $}` | refused, exit 2 | a three-line syntax error, exit 2 |
| `BEGIN {print}` | refused, exit 2 | runs the BEGIN block |
| `/foo` (unclosed) | refused, exit 2 | a syntax error, exit 2 |
| `{}` | refused, exit 2 | accepted, prints nothing, exit 0 |
| `{print$1}` | refused, exit 2 | accepted |
| `-F : prog file` (detached) | `awk: -F needs its separator attached, as -Fx`, exit 2 | accepted |
| no arguments | a usage line, exit 2 | a usage line, exit 2, different text |

There is **no stdin capability**, so the no-operand case refuses rather than
pretending to have read an empty stream — and rather than hanging, which is the
other way that could have gone.

## Controls: which deliberate break fails which cases

Every behaviour above was broken on purpose, rebuilt, and re-run. Each control
was checked to have actually landed on disk before its result was believed —
one attempt reported `PATCH_NOT_APPLIED` and was redone, which is why that
check is there.

| control | cases failed |
|---|---|
| default splitting: stop stripping leading blanks | 5 — the `$1`/`$2` cases over `spaced` and `ws`, and `-F' ' $1` |
| a field past the end answers the record | 3 — `$3`/`$9` over `plain`, `$2` over `ws` |
| an empty record counts as one empty field under `-F` | 1 — `-F: NF` over `blank` |
| never print the record-number line | 6 — every case where a record had been read first |
| report the FIRST file's record count instead of the previous one's | 2 — `plain colon nope`, `plain empty nope` |
| the pattern matches everything | 12 — every pattern case with a non-matching record |
| `-Ft` is a literal `t` | 2 |
| `-F' '` splits on one space | 2 |
| the separator scan advances one byte | 2 (count) + 4 (fields) |
| drop an unterminated last record | 7 |
| carry on after a file that will not open | 10 |
| accept every program | 7 divergences — and `/foo` then **traps** rather than answering |
| an empty program is not special | 2 |
| `NF` off by one under `-F` | 12 |

### Two controls PASSED, which meant the suite was weaker than it looked

**The separator scan.** Advancing one byte instead of past the separator failed
exactly one case, and only because a multi-byte separator made it *trap*.
`-Fab` over `xabyabz` gives NF=3 either way — the miscounts cancel. The
fixtures that separate the two rules are `aaaa` under `-Faa` (three empty
fields, not four) and `xaayaaz` (`$3` is `z`, not `az`); with those present the
same control fails six cases, as it should have all along.

**The harness dropping operands.** Making the harness pass only the first file
operand left the whole suite **green**: both implementations were handed the
same truncated vector, so they still agreed, and every multi-operand case
quietly stopped being one. Agreement is not coverage. The harness now restates
what each argument vector must be — length, the flag verbatim at 0, the program
verbatim next, then one fixture path per named file — and refuses at setup
otherwise. With that check, both this control and the flag-joining one below
are caught before a single case runs.

### Harness controls

The suite compares two programs, so a harness bug can make both fail
identically and look like agreement. This project has shipped six suites that
could not fail; the most recent path-joined the **flag** onto the fixture
directory, and seventy-two flag cases were green without one flag executing.

| harness control | result |
|---|---|
| path-join the `-F` flag | refused at setup: *argv[0] is not the flag verbatim* |
| drop operands past the first | refused at setup: *argv has 2 elements, not 3* |
| name a fixture that does not exist | refused at setup: *neither a fixture nor declared absent* |
| compare against `/bin/cat` instead of awk | 92 cases fail |
| drop the `argv0` normalisation | exactly the 10 missing-file cases fail |

A case is a **map** — `:fs`, `:prog`, `:files` — rather than a positional
vector, because a vector cannot tell an argument that looks like a filename
from a filename.

## Byte offsets, and why this file never counts them

`string-substring` at an offset that is not a code-point boundary **traps** the
process — measured 2026-09-10, `(string-substring "日本" 1 2)` is SIGILL, exit
120. It does not answer wrongly; it dies. So every offset here is the index of
an ASCII byte found by `string-index-of` — a space, a tab, a brace, a slash —
or 0, or the string's length.

That is why trailing blanks are trimmed by scanning **forward**: reading the
last byte would mean slicing at `n-1`, which is inside the character when the
program ends in a multi-byte one. A refused program can end in anything.

## Build and test

```sh
AMU_HOME=/path/to/amu REGEX_HOME=/path/to/org-ieee-regex kbb --backend sci test/awk_test.cljk
```

The test compiles `awk/core.kotoba` itself (`compile --target aarch64-macos
--jvm-free --policy`, `extract-native --symbol main`, then the packager with
`--allow 35,37,38,39`), builds its own fixture directory, and compares every
case against `/usr/bin/awk`.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write` (37), `:io/write-error` (39).
Exactly the four wires used, and no more.

## What this is not

No `BEGIN`/`END`, no variables or assignment, no arithmetic or comparison
patterns (`NR>5`, `$1=="x"`), no `!/RE/`, no `&&`/`||`, no `printf`,
`getline`, `split`, `substr`, `gsub`, no field assignment, no `-v`, `-f` or
`--`, no output redirection, no comma in a print list, no bare `{exit}`.

## Standard input

With no file operand `awk` reads standard input (wire 41 `:io/read`,
2026-09-16) — 81% of how it is invoked in agent tool use (3,883 of 4,800 over
1,268,018 measured Bash calls; `grep | awk` alone is 826). Until the wire
landed this was a named divergence (`awk: no file operand: this awk cannot
read standard input`, exit 2); it is now a compared case. Whole-input form:
input larger than the binary's string pool is refused (exit 120), never
walked short.
