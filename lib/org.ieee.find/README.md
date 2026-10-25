# kotoba-lang/org-ieee-find — POSIX `find`, as a Kotoba command binary

The `find` walk from IEEE Std 1003.1, with no expression and with `-type f`
/ `-type d`, written in `.kotoba` and compiled to a standalone native
executable.

```sh
./find DIR            # every path under DIR, DIR included
./find DIR -type f    # the regular files
./find DIR -type d    # the directories
./find FILE           # FILE itself, not descended into
./find A C            # several roots, walked in turn
./find nope           # find: nope: No such file or directory      exit 1
```

## The order is `find -s`, and it is compared as a sequence

`/usr/bin/find` emits entries in the order the directory hands them over —
**readdir order**, neither sorted nor stable across filesystems (measured
2026-09-10: `f1.txt` before `a`). Wire 34 answers a directory's listing
**sorted by bytes**, so plain find's order cannot be reproduced and against
it only the *set* is compared.

BSD find's `-s` walks each directory in lexicographical order, which under
`LC_ALL=C` is byte order — the order wire 34 answers in. This walk emits
every entry as it reaches it: **each directory before its contents, and
within a directory the entries in byte order, files and directories
interleaved.** Measured 2026-09-15 on the fixture, on a 34,803-entry tree
and on an 857,322-entry tree: byte-identical to `LC_ALL=C /usr/bin/find
-s`. The suite compares the sequence against it, so a walk that reordered
would fail there even with the same set.

## The walk is one pass, and every pair handle counts

Until 2026-09-15 the walk read each listing three times through
`string-index-of` — the files, then the subdirectory names, then a `"\n"`-
joined stack of directories still to visit, re-concatenated at every pop.
On native `string-index-of` costs about one pair handle per byte scanned and
the stack copy costs its whole length in pool bytes per pop, and neither
arena reclaims. Measured: SIGILL after 7,272 files of a 34,803-entry tree.

Now `walk-lines` moves a byte cursor over the listing once. At each line it
takes the name as a zero-copy view, joins it to the directory's `prefix`
(the path plus `/`), reports it, and — when the D flag is `1` — descends
into it right there (a non-tail self-call, depth = the tree's depth) before
the tail self-call that moves to the next line. Mutual recursion is not
available, so iteration and descent are one function.

Per entry that is **four handles**: the name view, the joined path, and the
two write counts wire 37 answers with — and since 2026-09-16 each entry
is a region, so they are released before the next entry (see below). A
directory adds its listing and its prefix. The newline is threaded through
as a parameter — building it with `(nl)` per line was a fifth handle, and
with five the unscoped 857,322-entry walk trapped at 607,572.

`scan-to` advances by **code point**, not by byte: `string-code-point-at`
refuses an offset inside a multi-byte sequence, and names are UTF-8. The
bytes searched for (TAB, `\n`, space) are ASCII and never occur inside one.

## Measured against `/usr/bin/find`, `fd` (2026-09-15)

Same machine, load average 95–145 so CPU seconds are the metric; the
output is identical in every row. Packaged with amu's loader of the same
date (buffered wire 37, `--cpu-seconds` / `--wall-seconds`, 64 Mi pair and
1 GiB pool ceilings).

| tree | entries | this find (user / sys) | `/usr/bin/find` | `fd -HI` (parallel) |
|---|---|---|---|---|
| amu | 8,719 | 0.02 / 0.09 s | 0.00 / 0.11 s | — |
| app-news | 34,803 | 0.07 / 0.49 s | 0.05 / 1.4 s | — |
| orgs/kotoba-lang | 857,322 | 1.64 / 18.5 s (wall 49 s) | 1.41 / 36.5 s (wall 76 s) | 1.90 / 22.7 s (wall 7.4 s) |

Less CPU than either, on every tree: the listing arrives with the
directory flag from the dirent, so nothing is stat'ed. Wall time on the
big tree is I/O serialisation, which is what `fd`'s parallel walk buys and
this runtime does not have.

What bounds the tree this can walk is the arenas: about four handles and
130 bytes per entry, nothing reclaimed. 857,322 entries is 3.9 Mi handles
and 110 MiB — the reason the ceilings moved.

## Each entry is a region (2026-09-16)

`(arena-scope body)` — context ABI v6, ADR-2609160044 — releases every
handle and byte its body allocated when it returns. Each entry of a listing
is one: the joined path, the write counts and, for a directory, the whole
subtree's listings and paths come back when the scope does. What stays
live across a directory is its listing and its prefix, so the arena holds
**depth × one listing, whatever the tree's size**.

Measured on orgs/kotoba-lang, 857,825 entries, packaged with the loader's
**default 4,096 handles** and a 4 MiB pool (the 12,727-entry listing on the
way is 700 KB): completes, user 1.16 s / sys 12.6 s, wall 26 s — where the
unscoped walk needed 3.9 Mi handles and 110 MiB of pool and was slower for
having touched them. The suite packages 4,096 handles and 1 MiB, and the
previous guest traps under that budget on its own wide case.

## `dir?` reads STAT, not the parent's listing

find's root is frequently the granted scope root itself, whose parent lies
**outside** the grant, so the parent-listing trick `org-ieee-cp` and
`org-ieee-ls` use traps here. `STAT`'s fourth field answers is-directory for
the path itself.

## The suite: 17 cases, sequence and set

`test/find_test.cljk` compiles the guest, packages it (`AMU_HOME` must be
amu of 2026-09-15 or later — the suite refuses a packager that does not
echo `--cpu-seconds`, since that one would silently bound the walk to one
CPU second), runs the binary, and compares stdout as a sorted set with
`/usr/bin/find`, as a byte sequence with `LC_ALL=C /usr/bin/find -s`, and
stderr and exit status byte for byte.

The last three cases are a **wide** directory — 4,000 files beside 40
nested directories, one with a multi-byte name — under the same
200,000-pair budget as everything else. Verified to fail as well as pass:
the previous `core.kotoba` under this suite fails 9 of 17 — SIGILL on the
wide cases and on the root walk that contains them, and `sequence=DIFFERS
from find -s` on the two-root cases whose set it gets right.

## What this is not

No expression language: no `-name`, `-path`, `-newer`, `-maxdepth`,
`-exec`, `-print0`, `-prune`. `-type` accepts `f` and `d` only — `-type l`
would need symlink detection, and wire 34 opens `O_NOFOLLOW`. The flag must
come last, and with no operand at all this exits 1 rather than walking a
working directory it cannot ask for. No parallel walk: the runtime has one
thread.

## Capabilities

`:cli/args` (38), `:fs/browse` (34), `:fs/app-data` (35, for EXISTS and
STAT), `:io/write` (37), `:io/write-error` (39).
