# kotoba-lang/org-ieee-diff — POSIX `diff`, as a Kotoba command binary

`diff` from IEEE Std 1003.1 — the normal output format and `-q` — written
in `.kotoba` and compiled to a standalone native executable.

```sh
./diff FILE1 FILE2      # 3c3 / < old / --- / > new …   exit 1 when they differ
./diff -q FILE1 FILE2   # Files FILE1 and FILE2 differ   (or nothing, exit 0)
```

## Measured, 2026-09-16

888 invocations in 1,268,018 Bash calls across 558 agent transcripts
(superproject ADR-2609161710): plain `diff A B` about 450, `-q` 127,
`-U`/`-u` 68, and 316 with process substitution (`diff <(a) <(b)`).

## Measured against the system utility

`test/diff_test.cljk` compiles the guest, packages it, **runs the binary**,
and compares stdout, stderr and exit status against `/usr/bin/diff` on 37
argv cases: changes / insertions / deletions at the start, middle and end;
empty files on either side; a missing final newline on either side and on
both (`\ No newline at end of file`, and `a` ≠ `a\n`); repeated lines where
a greedy alignment picks the wrong match; blank lines; multi-byte lines; a
3,000-line file against a copy with 40 scattered edits (both directions,
and against itself); `-q` both ways; missing operands; the usage block. All
byte-identical. One named divergence: `-u` is refused (exit 2, message)
because the unified header carries each file's mtime in the local time
zone, which this build has no capability to read.

On the 3,000-line pair: 0.01 s user, the same as `/usr/bin/diff`.

## The algorithm, and three things the compiler taught it

Myers' O(ND) shortest edit script over lines. Both files are read whole and
joined into one text (a newline inserted between them when FILE1 lacks a
final one), so every line is an offset into a single string and the host's
`string-compare-lines` compares two lines by offset without minting a view.
Line starts sit in one vector `S`; the furthest-reaching rows alternate
between two vectors `P` (read) and `C` (written), each row is copied into a
write-only trace `T` at offset `1 + d²`, the back-trace reads `T` and marks
deleted / inserted lines in `M`, and the output walk prints each run of
marks between two common lines as one hunk.

- **A vector is read-only or write-only on any one path.** `vector-assoc!`
  wants a linear handle, and the analysis counts reads too, so the step's
  `d`, its "done" flag and the trace's capacity all travel in the rows
  (written into `C`, read from `P` next step) or in packed scalar
  parameters — never read back from the vector about to be written.
- **Row index `k + n + m + 4`, not `+ 1`.** The first three slots of a row
  are metadata; with the smaller offset a one-line file's `k = -1` landed on
  its own capacity slot (SIGILL, measured).
- **The trace is capped at 2²² words** (`D ≤ 2,047`). The first cut sized it
  by `(n+m+1)²` up to the whole item budget, and an identical pair of
  3,000-line files trapped on the allocation alone. Past the cap this
  refuses with `diff: too many differences for this build`, exit 2, rather
  than answering wrong.

## What this is not

- **No `-u` / `-U` / `-c`** (time zone, above), no `-r`, `-i`, `-w`, `-b`,
  `-B`, no directories, no `Binary files … differ`.
- **Process substitution works when the binary is packaged with `/dev/fd`
  in its scope** — `<(…)` operands are `/dev/fd/N` paths, and since amu
  #1019 a scope entry that *is* `/dev/fd` means "the descriptors the caller
  connected" (the trust standard input already has). The suite runs four
  pairs through `bash -c 'diff <(cat a) <(cat b)'` on both binaries.
- Capabilities: `:cli/args` (38), `:fs/app-data` (35), `:io/write` (37),
  `:io/write-error` (39).
