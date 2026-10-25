# kotoba-lang/org-ieee-rm — POSIX `rm`, as a Kotoba command binary

```sh
./rm FILE...      remove each file
./rm -f FILE...   say nothing about what is not there, and exit 0
./rm -r DIR...    remove a tree
```

Sixteen cases agree with `/bin/rm` on stdout, stderr, exit status **and the
resulting directory tree** — `rm` writes nothing on success, so an
output-only comparison would pass an implementation that removed nothing.

## Measured against `/bin/rm` 2026-09-10

```
rm f1      (absent)  ->  rm: f1: No such file or directory     exit 1
rm -f f1   (absent)  ->  nothing                               exit 0
rm d1      (a dir)   ->  rm: d1: is a directory                exit 1
rm g1 nope g2        ->  g1 and g2 go, one line about nope,    exit 1
rm         (nothing) ->  two usage lines,                      exit 64
```

Note the lower-case `is a directory` — rm's own wording, not the capitalised
form its siblings use — and that an operand-less `rm` exits **64**, not 1,
while `rm -f` with no operand is silent and exits 0. Both measured on rm
itself rather than carried across.

## The tree walk is a stack, deepest-first

Mutual recursion is unavailable — a callee must be declared before its caller
— so "remove this directory, then recurse into each subdirectory" cannot be
two functions calling each other. One self-recursive sweep unlinks files and
pushes subdirectories onto the **front** of a `"\n"`-joined stack, while
**prepending** each directory it visits to a second list.

Prepending reverses discovery order, so that list comes back children before
parents, which is the order `rmdir` needs — it only removes an empty
directory. Same shape
[`org-ieee-find`](https://github.com/kotoba-lang/org-ieee-find) uses to walk a
tree.

The control is exact: making `-r` remove only the top directory fails the two
**nested** cases and correctly leaves `-r empty` passing, since an empty
directory needs no descent. Making `-f` stop silencing fails exactly its three
cases.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:fs/browse` (34), `:io/write-error`
(39). Nothing on stdout.

`UNLINK_SEP` and `RMDIR_SEP` are new **request forms on wire 35**, not new
capabilities, so nothing in the catalog or `kotoba-sema` moved. They are
separate forms deliberately: `UNLINK_SEP` never passes `AT_REMOVEDIR`, so a
guest that asked to remove a file cannot remove a directory instead.

Whether an operand is a directory is read from its **parent's** listing,
since there is no stat form — the technique
[`org-ieee-cp`](https://github.com/kotoba-lang/org-ieee-cp) and
[`org-ieee-ls`](https://github.com/kotoba-lang/org-ieee-ls) use.

## What this is not

No `-i`, `-v`, `-d`, `-P`, `-W`, `-x`. `-r` and `-f` cannot be combined
(`-rf` is not parsed; the flag must be the first argument and exactly one of
them). Operands must be absolute paths inside the packaged scope, and the
walk is bounded at 4096 directories.
