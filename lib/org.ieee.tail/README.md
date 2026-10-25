# kotoba-lang/org-ieee-tail — POSIX `tail`, as a Kotoba command binary

`tail` from IEEE Std 1003.1 for one operand, written in `.kotoba` and
compiled to a standalone native executable.

```sh
./tail FILE          # the last 10 lines
./tail -n 2 FILE     # the last 2
```

## Two places `tail` and `head` differ, both measured

They look like twins and are not:

| | `head` | `tail` |
|---|---|---|
| `-n 0` | `head: illegal line count -- 0`, exit **1** | nothing, exit **0** |
| a last line without a newline | adds nothing | adds nothing |

`grep`, `sort` and `uniq` all **do** add one in the same situation. Six
commands in this family, two contracts, and running them is the only way to
know which is which — `x\ny` with `-n 1` is **one byte**, `y`.

## The model

```
lines = newlines, or newlines + 1 when the text does not end in one
skip  = lines - N, floored at 0
emit  = the bytes from just after the skip-th newline to the end
```

Emitting a **span of the original bytes** is what makes "adds nothing" fall
out rather than being a special case — and `-n 0` falls out too: skip reaches
the last newline and the span is empty.

## The boundary test this does *not* use

"Does the text end in a newline" is **not**
`(string-substring text (- n 1) n)`. A substring offset must be a code-point
boundary and `n-1` is not one when the last character is multi-byte — the
same trap [`org-ieee-ls`](https://github.com/kotoba-lang/org-ieee-ls) hit,
where it listed every ASCII entry and then trapped `SIGILL` on `é`.

Here the question is answered from the newline walk instead: the text ends in
a newline exactly when the offset just after the **last** newline is the
length.

## Measured against the system utility

Sixteen cases, all identical on stdout, stderr and exit status. Boundaries
are deliberate: `-n 20` is the file's exact line count and `-n 25` is past
it; `-n 0` on a file and on an empty file; blank lines, which are lines
(`-n 2` on `a\n\n\nb\n` answers `"\nb\n"`, not `"b\n"`).

Verified to fail as well as pass: counting a trailing newline as starting
another line fails three cases, adding the newline `grep` adds fails three,
and refusing `-n 0` the way `head` does fails two — **with identical stdout
on both sides**, the difference being the exit status alone.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write` (37), `:io/write-error`
(39). A missing operand is reported byte-for-byte
(`tail: PATH: No such file or directory`, exit 1) using wire 35's `EXISTS`
form — the read form traps, and a trap cannot be caught.

## Several files: the same rule head uses

With **two or more** operands each file is introduced by `==> FILE <==`; with
one there is no header. A blank line precedes every header **except the first
one printed** — a missing operand does not count. Measured against
`/usr/bin/tail` 2026-09-10, and identical to `head`'s rule, which is why the
same shape appears in both: the two utilities genuinely agree here rather
than one being assumed from the other.

```
tail -n 1 nope.txt h1.txt        h1's header has NO blank line before it
tail -n 1 h1.txt nope.txt h2.txt h2's header DOES
```

The control is exact: counting a missing operand as printed fails **one**
case, `missing three`, and no other. Emitting headers for a single file too
fails all 15 single-file cases.

`-n 0` with several files still writes every header and no body, which is the
case where tail differs from head — head rejects `-n 0` as an illegal line
count and tail accepts it.

## The count, in its three spellings

`tail -N`, `tail -n N`, `tail -nN`. Measured 2026-09-17 over 1,268,018 agent
Bash calls: `tail -1` is 16,939 of them and `tail -2` 7,336 — the numeric
shorthand is the most frequent form by far, and until that day it was a
usage error here. A non-numeric count answers `tail: illegal offset -- x:
Invalid argument`, byte for byte.

## Standard input

With no file operand `tail` reads standard input (wire 41 `:io/read`,
2026-09-16) — 94% of how it is invoked in agent tool use (38,255 of 40,584
over 1,268,018 measured Bash calls). `tail` needs the *end* of its input, so
this is the whole-input form: input larger than the binary's string pool is
refused (exit 120), never silently truncated to its last pool-full.

Landing that moved both newline walks to `string-find-byte`, which mints
nothing: they used to cut a substring per line, and three walks over 65,536
lines was 196,000 pairs — the 4 MB stdin case met the 200,000-pair budget at
exit 120, and the file path had the same ceiling.

## What this is not

No `-c`, `-f`, `-r`, no `+N` form.

The walk carries the exit status and the header flag in one word (bit 0
written, bit 1 failed), because five parameters is the compiler's limit
(`kotoba.compiler.frontend/max-parameters`, an ABI arity limit rather than a
language decision).
