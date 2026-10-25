# kotoba-lang/org-ieee-tr — POSIX `tr`, as a Kotoba command binary

`tr` from IEEE Std 1003.1, the forms agents use, written in `.kotoba` and
compiled to a standalone native executable. It reads standard input — `tr`
has no file operand — through wire 41 (`:io/read`).

```sh
... | tr SET1 SET2       # translate; SET2 shorter → its last byte repeats
... | tr -d SET1         # delete
... | tr -s SET1         # squeeze runs to one
... | tr -s SET1 SET2    # translate, then squeeze runs of a SET2 byte
... | tr -ds SET1 SET2   # delete SET1, then squeeze runs of a SET2 byte
```

Sets take the escapes `\n` `\t` `\r` `\\` `\a` `\b` `\f` `\v` and octal
`\NNN` (1..177), ranges (`a-z`), and the POSIX classes `[:space:]`
`[:blank:]` `[:upper:]` `[:lower:]` `[:digit:]` `[:alpha:]` `[:alnum:]`
`[:punct:]` `[:print:]` `[:cntrl:]`.

## Why these forms — measured, not assumed

Over 1,268,018 Bash calls in 558 agent transcripts (2026-09-16, superproject
ADR-2609161710), `tr` was invoked 7,020 times, 99% of them as a later
pipeline segment. The argument shapes, most frequent first:

| form | calls |
|---|---|
| `tr -d ' '` | 2,261 |
| `tr '\n' ' '` | 1,659 |
| `tr -d '\n'` | 228 |
| `tr ':' '\n'` | 178 |
| `tr ',' '\n'` | 140 |
| `tr '/' '_'` | 109 |
| `tr ' ' '\n'` | 95 |
| `tr -d '"'` | 76 |
| `tr -d '\r'` | 65 |
| `tr -s ' '` | 51 |
| `tr -d '[:space:]'` | 26 |
| `tr '\t' '\n'` | 23 |
| `tr -s ' \n' ' \n'` | 23 |

Every one of them is among the five forms above, and every one is a compared
case in the suite.

## Measured against the system utility

`test/tr_test.cljk` compiles the guest, packages it, **runs the binary** with
each case's bytes on standard input, and compares stdout, stderr and the exit
status against `/usr/bin/tr` fed the same bytes. 45 compared cases, all
byte-identical; four named divergences below. On the 5.4 MB corpus:

| form | this | `/usr/bin/tr` |
|---|---|---|
| `tr -d ' '` | 0.12 s user | 0.27 s |
| `tr '\n' ' '` | 0.07 s | 0.32 s |
| `tr a-z A-Z` | 0.58 s | 0.40 s |

The first two win because the walk keeps a *run* of unchanged bytes and
appends it in one `string-append-range` when something changes; the third
loses because every byte changes and each costs a host call.

## How it reads

64 KiB at a time (the decimal form of wire 41, which answers whole code
points), each chunk inside its own `arena-scope`, so the pool holds one chunk
and `yes | tr y z | head` streams (57 ms, measured). The squeeze state — the
last byte written — crosses the chunk boundary in the walk's return value,
which is why the `big` fixture puts a squeezable run exactly across byte
65,536.

## Sets are ASCII; input is bytes

A set holding a code point past 127 is refused (message, exit 1). The
**input** may hold anything: a multi-byte sequence is copied through whole,
which is also what `/usr/bin/tr` does with an ASCII set, so the two agree —
`utf8` fixtures are in the suite for exactly that.

Three things about the source, each measured the hard way:

- The guest has no byte→string operation, so an **alphabet literal** holds
  bytes 1..127 in order and byte *b* is `(string-substring alphabet (- b 1) b)`.
  CR must be spelled `\r` in it: a raw CR in source is read as a line ending,
  and the first cut's `tr -d '\r'` deleted newlines (the one red case of
  fifty).
- Expanded sets are **strings**, not vector slots: `vector-assoc!` wants a
  linear handle, and reading a length from a vector before writing to it is
  two uses on one path, which the compiler refuses. The table vector is
  written only while it is built and read only while it walks.
- The walk answers **one value**, so the squeeze state rides out as a
  two-byte trailer that `batch` strips with a substring (a view; nothing is
  copied).

## What this is not

- **No `-c` / `-C` / `-u`** — refused with `tr: only -d and -s are supported
  (no -c, -C, -u)`, exit 1, rather than half-done.
- **No NUL** in a set: `\0` / `\000` are refused (no literal can hold the
  byte). Sets past ASCII and unknown classes are refused with the same
  message.
- Usage errors (wrong operand count) print the BSD usage block, measured and
  compared byte for byte.
