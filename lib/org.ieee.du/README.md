# kotoba-lang/org-ieee-du — POSIX `du`, as a Kotoba command binary

```sh
./du DIR...        every directory under each operand, then the operand
./du -s DIR...     only the total for each operand
./du -a DIR...     every file as well as every directory
```

Thirty-four cases agree with `/usr/bin/du` on stdout, stderr and exit status
over a tree this repository's test builds. Run them with:

```sh
AMU_HOME=<amu checkout> kbb --backend sci test/du_test.cljk
```

## What `du` reports is blocks, and blocks are not bytes

Measured against `/usr/bin/du` on macOS 26.4 (Darwin 25.4.0), 2026-09-10:

```
6-byte file      ->  8        18-byte file  ->  8
5000-byte file   -> 16        empty file    ->  0
```

Those are 512-byte units from `st_blocks`. `st_size` cannot produce them: 6
bytes and 18 bytes occupy the same disk, and a size-based sum answers 24 for
a directory where `du` answers 32. Reporting size instead of blocks fails
**26** of the 34 cases — the eight survivors are the ones whose every count
is zero anyway, plus the diagnostics.

So the command reads wire 35's `STAT` form,
`"<path>STAT_SEP"` → `"<mode> <size> <blocks> <isdir>"`, and prints field
three. The line is `"%lld\t%s\n"` — the count, one TAB, no padding.

The operand is echoed **verbatim**, which the trailing-slash case makes
visible: `du DIR/` prints `DIR//sub` and `DIR/`. This joins the same way, so
that case is in the suite.

## The order is readdir order and is not reproduced

`/usr/bin/du` walks with `fts` and no comparison function, so siblings arrive
in directory order. Measured on a directory holding `f1.txt`, `empty`, `zz`,
`aa` and `mm`, `du` emitted them in exactly that sequence — neither sorted
nor creation order. Wire 34 answers its listing sorted by bytes and has no
request form that asks for readdir order.

The test therefore compares stdout as **sorted lines**, the same concession
`org-ieee-find` makes for the same reason. Every number and every path still
has to match; stderr and the exit status are compared byte for byte with no
reordering; and for every single-line case (`-s`, a file operand, a
diagnostic) the sorted comparison *is* a byte comparison.

The order this implementation does promise — each operand one contiguous
block, every directory after everything beneath it — is asserted separately
as a property of our own stdout, so a pre-order walk fails even though the
sorted sets would agree.

## The walk is one worklist, not two functions

Mutual recursion is unavailable, so "sum this directory, which means summing
its subdirectories" cannot be two functions calling each other. `walk`
carries two `"\n"`-joined stacks:

- **stack** — paths still to account for. A leading `!` marks the *second*
  visit to a directory: the moment its subtotal is known. Popping directory
  `D` replaces it with its children followed by `!D`, and that is what makes
  the output post-order without a second traversal.
- **sums** — one partial total per directory currently open, innermost
  first. A file adds its blocks to the top; `!D` pops the top, prints it and
  adds it to the enclosing frame.

`-s` needs no depth counter as a result: the operand's own line is the one
whose *enclosing* sums stack is the single root frame. Removing that test
makes `-s` print every directory and fails exactly the six `-s` cases whose
operand contains a subdirectory.

A path containing a newline would corrupt both stacks. So would a path
beginning with `!`, which cannot happen — every path here is absolute.

## Capabilities

`:fs/browse` (34), `:fs/app-data` (35), `:io/write` (37), `:cli/args` (38),
`:io/write-error` (39). The packaged binary is granted `--fs-scope` and
`--browse-scope` over the tree it is asked about.

`STAT_SEP` is a request form on wire 35, not a new capability. A grant that
can read a file's contents can already tell its size; what it adds is the
block count, which is the number `du` exists to print.

## What this is not

**Hard links are counted every time.** `/usr/bin/du` counts them once — a
directory holding a file and a hard link to it reports 16, and `du -a` does
not even list the second name. It does that by remembering `(device, inode)`
pairs; the `STAT` form answers neither, so this cannot be fixed in the guest.
The fixtures contain no hard links.

**Symlinks are skipped entirely.** `du` lists them with their own block
count. Wire 35 opens `O_NOFOLLOW`, so a symlink answers the empty string
here and is neither counted nor printed. The fixtures contain none.

**A directory's own blocks are added but cannot be observed here.** APFS
reported `st_blocks` 0 for every directory measured, including one holding
3000 entries at 96 KB of directory size; an HFS+ disk image reported 0 as
well. The term is kept because 0 is a filesystem's answer and not a rule, but
deleting it fails **no** case on this machine, and the suite is honest about
not discriminating it.

**No default operand.** POSIX defaults to `.`; there is no working-directory
capability and wire 35 requires an absolute path, so this refuses with a
diagnostic rather than guessing. All operands must be absolute.

**Flags are leading only**, which is what BSD `getopt` does — measured,
`du DIR -s` reports `du: -s: No such file or directory` and still walks
`DIR`.

**`-A -c -l -n -x -H -L -P -g -h -k -m -d -B -I -t` are not implemented**,
and are refused with `du`'s own usage text and exit 64 rather than ignored.
Ignoring `-k` would print 512-byte units under a flag that asked for
1024-byte ones and look like a working answer. `du -q` answers
`du: invalid option -- q` and the usage line; `du -a -s` and `du -sa` answer
the usage line alone. All three are measured and all three are in the suite.

## Negative controls

Each was applied to `du/core.kotoba` alone, with the test unchanged, and the
patch was verified to have landed before the run (one control was first
written as a `sed` that silently matched nothing and reported a clean pass —
the guard exists because of it).

| control | cases failed |
|---|---|
| report `st_size` instead of `st_blocks` | 26 — every case with a nonzero count |
| drop the directory's own-blocks term | **0** — unobservable, see above |
| `-s` prints every directory | 6 — exactly the `-s` cases with a subdirectory |
| print files without `-a` | 16 — every non-`-a` walk over a tree holding a file |
| lower-case the `No such file or directory` text | 4 — exactly the missing-operand cases |
| push `!D` before its children instead of after | 21 — 17 on the order property, 4 on values |
| never set the failure exit status | 4 — on exit status alone; stdout and stderr still matched |
| drop the `-a`/`-s` conflict check | 2 — exactly `-a -s` and `-sa` |

The `!D`-before-children control is *not* an isolated order control: in this
design the moment a directory's line is printed is the moment its subtotal is
known, so moving the marker breaks both. It does show the order property is
live — it fired on 17 cases the value comparison would have caught anyway.
