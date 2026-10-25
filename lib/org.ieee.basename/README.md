# kotoba-lang/org-ieee-basename — POSIX `basename`, as a Kotoba command binary

`basename` from IEEE Std 1003.1, written in `.kotoba` and compiled to a
standalone native executable.

```sh
./basename /a/b/c.txt          # c.txt
./basename /a/b/c.txt .txt     # c
./basename -s .txt /a/b/c.txt  # c   (the BSD spelling)
./basename -- -x               # -x
./basename a b c               # a / b / c, one per line (BSD's -a form)
```

## Measured, 2026-09-16

760 invocations in 1,268,018 Bash calls across 558 agent transcripts
(superproject ADR-2609161710): `basename ARG` 619, `basename ARG SUFFIX`
146, `--` 3. No `-a` was seen; three-plus operands behave as `-a` because
`/usr/bin/basename` does (`basename a b c` prints three lines and exits 0
where POSIX would call it a usage error) — pinned by comparison, not typed.

## Measured against the system utility

`test/basename_test.cljk` compiles the guest, packages it, **runs the
binary**, and compares stdout, stderr and exit status against
`/usr/bin/basename` on 28 argv cases: every POSIX edge (empty string, all
slashes, trailing slashes, a suffix that is the whole name and is therefore
*not* removed), multi-byte names, `--`, `-s`, and the usage errors. All
byte-identical.

## The walk is forward

The last component is found with one forward walk over slash positions
(`string-find-byte`, context ABI v10). A slash is always a code-point
boundary, so no offset the walk constructs lands inside a multi-byte
sequence. The first cut walked *backwards* a byte at a time and
`string-code-point-at` refused the continuation byte of 本 (SIGILL) — the
suite's multi-byte cases are there for that.

## What this is not

No `-a` flag spelled out (the behaviour is there without it). Capabilities:
`:cli/args` (38), `:io/write` (37), `:io/write-error` (39) — no filesystem,
no stdin.
