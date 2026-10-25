# kotoba-lang/org-ieee-cat — POSIX `cat`, as a Kotoba command binary

`cat` from IEEE Std 1003.1, written in `.kotoba` and compiled to a standalone
native executable. Named `org-ieee-cat` because IEEE publishes POSIX — the
same `org-<body>-<spec>` pattern as
[`org-ieee-tar`](https://github.com/kotoba-lang/org-ieee-tar) and
[`org-ieee-echo`](https://github.com/kotoba-lang/org-ieee-echo).

```sh
./cat a.txt b.txt        # contents of each operand, in order
```

## Measured against the system utility

`test/cat_test.cljk` compiles the guest, packages it into a standalone
binary, **runs that binary**, and compares bytes and exit status against
`/bin/cat` — `:ok true` from a compiler means the artifact was built, not
that it is right.

```
AMU_HOME=<amu checkout> kbb --backend sci test/cat_test.cljk
```

Nine cases, all byte-identical. Each separates a right implementation from a
wrong one that passes the others: two operands for concatenation **in order
with nothing added between**, the same operand twice because an operand is
not deduplicated, an **empty file** because it reads as the empty string and
must not end the loop the way "past the last operand" does, that case from
both sides, a file with **no trailing newline** because `cat` adds nothing of
its own, and a UTF-8 file including an astral code point.

## The size it works at, measured rather than described

A native guest's strings live in one arena in the loader that is a bump
allocator and **never reclaims**. So what bounds `cat` is not how big one
file may be — it is how many bytes the run ever allocates, and the operand
paths are part of that.

The test does not assert a number. It **bisects** the ceiling of a
default-budget binary and prints it, then asserts the relations that make
the bound the arena:

```
ceiling of the default-budget binary, bisected: 65441 bytes
  (operand path 89 bytes; 65530 together)
  ok   the default budget has a ceiling under 100 KiB
  ok   one byte past it traps
  ok   a 900,000-byte file is refused by the default binary
  ok   and written in full by the --string-pool 4000000 binary
```

A longer operand path lowers the ceiling by exactly the bytes it added —
that, and not the number, is what says the bound is the arena. The remaining
few bytes are the decimal count `:io/write` answers.

## Raising it is a per-run decision, not a bigger constant

The loader's arena is a **budget**: the default is what it has always been, so
a guest that ran before runs identically, and `--string-pool` at packaging
time (or `KEXE_STRING_POOL` for a loader invocation) moves one caller's
ceiling rather than everyone's. A binary packaged with the default cannot be
raised by its caller's environment — the budget is a constant of the binary,
like the grant and the filesystem scope.

So `cat` of a large file is a packaging choice:

```sh
nbb <amu>/scripts/package-command.cljs ... --string-pool 4000000 --output ./cat
```

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write` (37). The filesystem scope
is baked at packaging time, so `./cat` reads exactly the tree it was packaged
for and the caller cannot widen it.

## Flags: `-n`, `-b`, `-s`

```
-n   number every line          "     1\tone"   (six columns, then a TAB)
-b   number only NON-blank lines; a blank line gets no number and no tab
-s   squeeze runs of blank lines to one
```

One flag at a time; combining them is out of scope.

### The counter restarts per operand

Measured on `/bin/cat` (BSD): `cat -n pair pair` answers `1 2 1 2`, **not**
`1 2 3 4`. GNU `cat` numbers continuously, so this is a place the two
genuinely disagree and the comparison is against the one on this machine.

The control is exact: threading the count across files — the GNU behaviour —
fails **only** the four multi-operand numbering cases and nothing else.
Numbering blank lines under `-b` fails exactly the two `-b` cases that have
blank lines.

`-n` adds no trailing newline of its own: over a file holding `x` it answers
`     1\tx` with no terminator.

### The flags cost fuel, and the default budget cannot pay it

Plain `cat` is one host call per FILE. Numbering is per LINE, and at the
default 512 fuel `-n` over eight lines across two files exhausted it and
**trapped** — exit 120, output truncated mid-stream. That read as a missing
trailing newline until the exit status was looked at, which is why the suite
compares status and not just bytes.

The test now packages with raised fuel and the **default string pool**, so the
ceiling measurement below still measures the pool it names.

## What this is not

With **no operands** POSIX reads standard input. There is no stdin
capability, so this writes nothing and answers 0. That is stated rather than
worked around, and the test asserts what it actually does.

No `-b`, `-e`, `-n`, `-s`, `-t`, `-u`, `-v`. Concatenation is the whole of it
so far.
