# kotoba-lang/org-ieee-sed — POSIX `sed`: `s`, `p`, `d`, addresses, regular expressions

IEEE Std 1003.1 `sed`, written in `.kotoba`, compiled to a standalone native
executable, linked with [`org-ieee-regex`](https://github.com/kotoba-lang/org-ieee-regex)
for the regular expressions.

```sh
./sed 's/RE/REPLACEMENT/[g][p]' [FILE...]
./sed -n '/RE/,/RE/p'           [FILE...]
./sed -n '12,40p'               [FILE...]
./sed '/RE/d'                   [FILE...]
./sed -E 's/(a|b)+/X/g'         [FILE...]
./sed -i '' 's/RE/REPLACEMENT/' FILE...      in place (-i.bak keeps a backup)
... | ./sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
```

188 cases agree with `/usr/bin/sed` on stdout, stderr, exit status and —
under `-i` — every file's bytes and mode; six named divergences are
written out in the suite rather than compared. Operands may be relative
(`src/a.txt`, `./x`): the loader resolves them against the directory the
command started in, then holds them to its scope (amu #1023, 2026-09-17 —
99,826 of the measured file operands are relative, 17,104 absolute).

## Which scripts, measured 2026-09-17

Of 1,268,018 agent Bash calls, 15,968 are `sed` with a single-quoted script.
By shape:

| shape | count | here |
|---|---|---|
| `-n 'N,Mp'` (and several joined by `;`) | 8,762 + 205 | yes |
| `s` with a metacharacter (`s/^+//`, `s/[[:space:]]*$//`, …) | 3,217 | yes |
| … with `g`, with `-E`, joined by `;` | 139, 102, ~380 | yes |
| `-i ''` (in place; `-i.bak` once) | 1,042 | yes |
| `-n '/re/,/re/p'`, `/re/p`, `,+N` | 817 + 59 | yes |
| `\1` in the replacement | 193 + 105 + 89 | yes (2026-09-17) |
| `s` literal | 345 + 57 | yes |
| `/re/d` | 109 | yes |
| `-n 's/…/…/p'` | 113 | yes |

## Semantics, each measured on `/usr/bin/sed`

```
s/X/-/       the FIRST match on each line; g every match, scanning on
             AFTER each replacement (so s/a/aa/g terminates)
s/x*/-/g     -a-b-c- over abc: an empty match at every position
s/b*/-/g     -a-c-: an empty match right after a match is skipped
s/^a/X/g     Xaa over aaa: ^ is the line start, not the scan start
&  \&  \n \t the match, a literal &, a newline, a tab, in the replacement
\1 .. \9    group N of the match (rx/captures): the groups are macOS libc
             regex's greedy-first answers -- (a|ab)(c|bcd) over abcd is
             [a][bcd], (a*)(a*) over aaa is [aaa][], (ab)* over abab is
             [ab], the last iteration; a group that did not take part is
             empty; \N past the pattern's groups is refused with
             /usr/bin/sed's words (`\1 not defined in the RE`)
s/a\/b/X/    \ before the delimiter is the delimiter itself
\x1b         a byte by hex (the ANSI-escape stripper agents write)
\t           a tab, in the pattern too
s//-/        an EMPTY pattern is refused: "first RE may not be empty"
s/X/-/p      prints the line when it substituted (twice without -n)
/A/,/B/p     from a line matching A through the next matching B, the end
             tested from the NEXT line (/A/,/A/ spans two lines); ranges
             restart after they end
/A/,3p       through line 3; an end at or before the start is ONE line
/A/,+2p      the start and two more lines
2,/B/p       from line 2 through the next B
0,2p         nothing (lines begin at 1); $ is the last line
1,2p;2,3p    a line prints once PER command selecting it
/A/d         deletes: no later command sees the line, no autoprint
without -n   every line once, plus once per p
no newline   a last line without one keeps none, on EVERY print of it
             (printf a | sed p is aa)
several files ONE stream: line numbers continue, and a file lacking a
             final newline gets one only when another LINE follows
a^b  a$b  *b BRE: ^ $ * are literal where they cannot anchor or repeat
```

### Named divergences (in the suite as `divergences`, not compared)

- A bad pattern: exit 1 and the shape `sed: 1: "SCRIPT\n": RE error: …`
  are `/usr/bin/sed`'s; the message after `RE error:` is the engine's.
- BRE `\+` and `\|`: one-or-more and alternation here, as `/usr/bin/grep`
  reads them (the engine is shared); `/usr/bin/sed` reads a literal `+`
  and `|`. 17 + 31 measured scripts use them, every one written for the
  GNU meaning and silently a no-op on macOS.
- Two `+N` addresses in one script: refused (one countdown is kept).
- A line holding the literal text `WRITE_SEP` or `APPEND_SEP` cannot be
  written in place: the loader's wire-35 request tokens, refused fail-closed
  (exit 120). Reading and printing such a line is fine.
- A bad substitute flag or command letter: `sed: unsupported script`,
  exit 1, where `/usr/bin/sed` names the flag or letter.

## In place: `-i ''`, measured on `/usr/bin/sed`

The argument after `-i` is the backup suffix — `''` for none, so
`sed -i 's/a/b/' f` takes the script as the suffix and refuses `f` as the
script, exactly as `/usr/bin/sed` does on macOS. Each operand is its own
stream (`$` and line numbers restart); the output is appended line by line
to `<file>.sed-tmp` (the loader's wire-35 APPEND form, one buffered
descriptor per file), the mode is copied, the original is renamed to the
backup if a suffix was given, and the temporary is renamed over the
operand. Nothing reaches standard output. A missing operand or a directory
stops the run with `/usr/bin/sed`'s words, exit 1, after the operands
before it were edited and before the ones after it were touched; `-i` with
no operand is `sed: -I or -i may not be used with stdin`. 20 cases, each
in a fresh copy of the fixtures with relative operands, compare stdout,
stderr, exit and every file's bytes and mode.

## What this is not

No `y`, `a`, `i`, `c`, `q`, `{}`, `w`, `N`, hold space, `I` flag,
`//` (the last RE), numeric substitute flag (`s/a/b/2`), more than 40
commands in one script (one bit per command carries range state). Each of
these is refused, exit 1, never half-done.

## How

The script is parsed ONCE into length-prefixed fields (`LEN:bytes`, eight
per command: addr1 type, value, addr2 type, value, command, pattern,
replacement template, flags) — no separator byte, so any bytes fit. A
pattern with a metacharacter is a regex.core program plus its literal
prefilter (the runs one of which every matching line must hold; a host
search skips the rest before the simulation); a pattern without one keeps
the literal walk (one host search per occurrence). Each line runs its
cycle inside an `arena-scope`, so a file's walk never accumulates; what
crosses lines is one i64: bit k = "command k's range is active", bits 40+
the `+N` countdown. `d` carries the untouched bits of the commands after it.

Measured 2026-09-17 on a 5.6 MB, 769,400-line file (user time, this /
`/usr/bin/sed`): `-n '/^\.\.\./,/^:/p'` 0.84 s / 0.21 s (3.69 s before the
prefilter); `s/foo/bar/g` 1.25 s / 0.26 s; `-n 100,200p` 0.61 s / 0.13 s.
The per-line cycle (field decoding, the region) is the floor; the measured
inputs are pipeline tails of a few hundred lines, where the process start
is what counts.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35: read, and under `-i` the WRITE,
APPEND, STAT, CHMOD and RENAME forms), `:io/write` (37), `:io/write-error`
(39), `:io/read` (41). A missing operand is reported byte-for-byte and the
readable ones are still written, exit 1. With a script and no file operand
`sed` reads standard input, whole; input larger than the binary's string
pool is refused (exit 120), never edited short.

## Test

```sh
AMU_HOME=../amu REGEX_HOME=../org-ieee-regex kbb --backend sci test/sed_test.cljk
```

Needs amu at or after #1023 (relative operands, the APPEND form).
