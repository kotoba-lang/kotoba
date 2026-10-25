# kotoba-lang/org-ieee-mv — POSIX `mv`, as a Kotoba command binary

```sh
./mv SRC DST      rename SRC to DST
./mv SRC DIR      move SRC into DIR, keeping its name
./mv SRC... DIR   move several into DIR
```

Twelve cases agree with `/bin/mv` on stdout, stderr, exit status **and the
resulting directory tree** — `mv` writes nothing on success.

## The diagnostic names the resolved target

Measured against `/bin/mv` 2026-09-10:

```
mv nope x    ->  mv: rename nope to x: No such file or directory
mv nope dd   ->  mv: rename nope to dd/nope: No such file or directory
```

It names **both** operands and the verb — which no sibling command does — and
the destination it reports is the **resolved** target, `dd/nope`, not the `dd`
that was typed.

Reporting the operand instead passes every case whose destination is a plain
path and fails exactly the **two** whose destination is a directory. Not
resolving the directory at all fails **six**.

Both no operands and one operand print the same two usage lines and exit
**64**, not 1.

## This is a rename, not a copy

The wire form is `RENAME_SEP`, which is `rename(2)` under the grant. A move
**across filesystems** therefore fails, where `mv(1)` falls back to
copy-and-unlink. Inside one granted scope that cannot arise — but it is a real
difference, so it is stated here rather than left to be discovered.

Overwriting an existing destination is silent and allowed, exactly as
`rename(2)` is.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:fs/browse` (34), `:io/write-error`
(39). Nothing on stdout.

`RENAME_SEP` is a new **request form on wire 35**, not a new capability. Both
sides are admitted and both parents are proven inside the grant, so it cannot
be used to move a file out of the scope or to pull one in.

Whether the destination is a directory is read from its **parent's** listing,
since there is no stat form — the technique
[`org-ieee-cp`](https://github.com/kotoba-lang/org-ieee-cp) uses.

## What this is not

No `-f`, `-i`, `-n`, `-h`, `-v`. Operands must be absolute paths inside the
packaged scope.
