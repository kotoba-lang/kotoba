# kotoba-lang/org-ieee-dirname — POSIX `dirname`, as a Kotoba command binary

`dirname` from IEEE Std 1003.1, written in `.kotoba` and compiled to a
standalone native executable.

```sh
./dirname /a/b/c.txt     # /a/b
./dirname c.txt          # .
./dirname /a//b//        # /a
./dirname /              # /
./dirname -- -x          # .
./dirname a /b/c         # . and /b, one per line
```

## Measured, 2026-09-16

399 invocations in 1,268,018 Bash calls across 558 agent transcripts
(superproject ADR-2609161710) — 140 as a bare word, most of the rest as
`$(dirname "$0")`. `/usr/bin/dirname` takes several operands and answers
one line each (`dirname a b` prints two dots, exit 0); so does this.

## Measured against the system utility

`test/dirname_test.cljk` compiles the guest, packages it, **runs the
binary**, and compares stdout, stderr and exit status against
`/usr/bin/dirname` on 26 argv cases: every POSIX edge (empty string, all
slashes, `//a`, `a/`, doubled separators, `.`/`..` prefixes), multi-byte
names, `--`, several operands, and the usage error. All byte-identical.

## Two forward walks, none backwards

The last non-empty component is found with a forward walk over slash
positions (`string-find-byte`), and the end of the component before it with
a second forward walk that stops at the first one's start. A slash is always
a code-point boundary, so no offset is ever inside a multi-byte sequence —
the first cut stripped trailing slashes by stepping back a byte at a time
and hit the continuation byte of 日 (SIGILL). Because a component ends at a
slash, the answer needs no trailing-slash strip of its own.

## What this is not

Capabilities: `:cli/args` (38), `:io/write` (37), `:io/write-error` (39) —
no filesystem, no stdin, and no path resolution (`dirname` is a string
function).
