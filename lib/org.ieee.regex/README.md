# kotoba-lang/org-ieee-regex — POSIX regular expressions as a Kotoba library

`regex.core`: POSIX ERE and BRE (IEEE Std 1003.1) compiled to a program and
matched by Thompson's NFA simulation — a library module for `grep`, `sed`
and `awk`, linked with `--source-path`.

```clojure
(ns grep.core (:require [regex.core :as rx]))
(rx/compile-pattern "^(foo|bar)+" true)   ; ERE → program string, or "!" + message
(rx/matches? prog text lo hi)             ; is there a match in the line [lo, hi)?
(rx/find prog text lo from hi)            ; leftmost-longest: start*2^32 + end, or -1
(rx/prefilter pattern ere?)               ; newline-separated literal runs, one of which
                                          ; every matching line holds; "" when none
(rx/holds-run? line runs 0)               ; does the line hold one? (a host search)
(rx/captures prog text lo hi se)          ; the groups of the match se (find's answer):
                                          ; ten "start:end;" tokens, group 0 the match
(rx/group-count pattern ere?)             ; how many groups the pattern opens
```

Capture groups (2026-09-17): the simulation keeps no per-thread state, so
once `find` has the span the groups come from a second walk of the program
over exactly that span, depth first, greedy branch first — the first walk
that reaches the match at the span's end. That is what macOS libc regex
answers (`(a|ab)(c|bcd)` over `abcd` is `[a][bcd]`, `(ab)*` over `abab` is
the last iteration `[ab]`), measured on `/usr/bin/sed -E`, not the POSIX
subexpression rule; 20 cases in the suite pin those answers. The walk
remembers the epsilon instructions visited at each position, so `(a*)*`
cannot loop; it is exponential in the worst case, over a span already known
to match.

The prefilter is what makes the measured `-E` alternations of words run at
the system utility's speed: `SIGILL|static_assert` over 5.4 MB is 10.4 s
simulated on every line and 0.15 s simulated only on lines a host search
admits. It lived in `org-ieee-grep` first (2026-09-17) and moved here so
`sed` and `awk` share it. It is conservative: a pattern with an alternative
that has no literal prefix (`.*foo`, `[ab]c`) gets `""`, and the suite's
driver exits 3 by name on any matching line the runs would have skipped —
which is how `a\?b` over `b` (BRE `\?` makes the run's last character
optional) was caught before it shipped.

## Measured, 2026-09-17

Over 1,268,018 agent Bash calls: `grep -E` 9,582 patterns, shaped as
alternations of words (`W|W`, `^(W|W)`, `^W |W`), then `+` 1,294, `.` 1,225,
`*` 497, `?` 150, `{n,m}` 98, `[:space:]` 43; `sed -n '/re/p'` and `s/re/…/`
are the same grammar. That is the subset here: `|` `( )` `.` `*` `+` `?`
`{n}` `{n,}` `{n,m}`, bracket expressions with ranges, negation and the
POSIX classes, `^` `$`, `\` escapes (a literal metacharacter; `\w \W \d \D
\s \S` as classes; `\b \B` as boundaries), and the BRE spellings `\( \) \{
\} \| \+ \?`. No back-references — not regular, and none measured.

## Measured against the system utility

`test/regex_test.cljk` compiles a driver that links the module, packages
it, and compares its first match on each (pattern, line) against
`/usr/bin/grep -ob` — POSIX leftmost-longest with byte offsets — for 90
cases (plus 20 capture cases against `/usr/bin/sed`'s answers) (each construct and its edges, `a|ab` → `ab`, `(a|ab)(c|bcd)` →
`abcd`, multi-byte lines and classes, `(a*)*b`, the BRE context rules
below) plus 10 patterns both sides refuse. All byte-identical.

### BRE context, measured on `/usr/bin/grep` (macOS libc regex)

`^` is an anchor at the start of the pattern, after `\(` and after `\|`,
and a literal elsewhere (`a^b` matches `a^b`); `$` is an anchor at the end
and before `\)`, a literal elsewhere — even before `\|` (`b$\|x` over
`ab$` answers `b$`); `*` is a literal where an anchor `^` would be and
right after one (`^*b` over `*b` answers `*b`). ERE has none of this. `\t`
is a tab in both grammars, as `/usr/bin/grep` reads it. `\+` and `\?` are
one-or-more and optional in BRE as `/usr/bin/grep` reads them — where
`/usr/bin/sed` reads a literal `+` and `?`; `sed` names that divergence.

## How it runs, and what it cost to learn

- **A program is a string** of 9-byte records — an op byte and two four-digit
  base-93 fields (printable ASCII without `;`) — with *relative* jump
  targets computed from sub-program lengths, so it is built by concatenation
  alone. No vectors: the compiler's linearity rule refuses a vector that is
  read and written on one path, and a thread set is exactly that.
- **A thread set is a string** of `pc;` tokens, deduplicated by one
  `string-index-of`, rebuilt per character. Linear in input × program;
  `(a*)*b` cannot hang. Every visited pc is recorded, the ε ones too — the
  first cut recorded consumers only and followed the `(a*)*` cycle until the
  stack overflowed (exit 123).
- **`matches?` is one pass** (a fresh thread at pc 0 at every position);
  `find` is leftmost-longest the plain way, an anchored run from each start,
  each in its own `arena-scope` — unscoped, a 60-character line of misses
  minted 18,000 handles against a 4,096 budget.
- **Speed**: the per-character constant is host calls per live thread (~10),
  so a 5.4 MB file simulates in seconds where `/usr/bin/grep` takes 0.1 s.
  `grep` keeps a literal fast path for patterns without metacharacters and a
  *prefilter* from the top-level alternatives' literal prefixes, which makes
  the measured shapes run at BSD speed (`SIGILL|static_assert`: 0.15 s vs
  0.13 s user). Patterns that defeat the prefilter (`e+ in`, `^line [0-9]+`)
  run the simulation on every line: 2–4 s on 5.4 MB. The next lever is a
  lazily built DFA over the same program — read-only tables once built are
  what the linearity rule allows.

## What this is not

No back-references IN a pattern (`\1` matching what group 1 matched:
not regular), no collating symbols (`[[.a.]]`) or equivalence classes
(`[[=a=]]`), no lazy quantifiers (`*?`, a TRE extension `/usr/bin/grep`
accepts), no `\<` `\>`. Case folding is the caller's (ASCII, before
compiling). Lines are at most 2²¹ bytes and a program 8,649 records.
