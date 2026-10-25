# kotoba-lang/org-ieee-ls — POSIX `ls`, as a Kotoba command binary

`ls` from IEEE Std 1003.1 in its default non-terminal form — one entry per
line, sorted, entries beginning with a period omitted — written in `.kotoba`
and compiled to a standalone native executable.

```sh
./ls /some/dir       # the visible entries
./ls -a /some/dir    # every entry, including . and ..
```

## The comparison is against `LC_ALL=C /bin/ls`, and that is not a convenience

Wire 34 answers its listing **sorted by bytes**. macOS's `/bin/ls` in a normal
locale sorts by collation, which is a different order entirely. Measured
2026-09-10 on a directory holding `-dash 1one Zebra _under "a b" apple
z-last é 日本`:

| | order |
|---|---|
| `/bin/ls` (default locale) | `日本 _under -dash 1one "a b" apple é z-last Zebra` |
| `LC_ALL=C /bin/ls` | `-dash 1one Zebra _under "a b" apple z-last é 日本` |
| wire 34 | `-dash 1one Zebra _under "a b" apple z-last é 日本` |

Comparing against the default would fail for a reason that has nothing to do
with this implementation, and the test says so where it sets `LC_ALL`.

## Measured against the system utility

`test/ls_test.cljk` compiles the guest, packages it into a standalone binary,
**runs that binary**, and compares bytes and exit status. Twelve cases over
six directories, all identical: a plain one, one with a dotfile, one whose
**only** entry is hidden (which prints nothing, not an empty line), an empty
one, one holding a subdirectory, and a mixed one with punctuation, digits,
case, a space and multi-byte names — each with and without `-a`.

## The bug the multi-byte case caught

Testing "begins with a period" as `(string-substring name 0 1)` looks
obviously right and is wrong: a substring offset must be a **code-point
boundary**, and 1 is not one when the first character is multi-byte. The
guest listed every ASCII entry and then trapped `SIGILL` on `é` — so the
wrong answer was a *truncated listing and a signal*, not a visibly wrong
name.

`(= (string-index-of name ".") 0)` is the form that works: it answers the
first byte offset of the needle, so 0 is exactly "begins with", and it never
constructs an offset it has not walked to.

## `-a`, and the claim this file used to make

This README recorded `-a` as blocked:

> Wire 34 excludes `.` and `..`, and adding them is **not** a prepend …
> The language has no string ordering comparison — only `string=` — so the
> merge means walking code points, which is its own slice.

The first half is right and measured. The last clause was wrong, and
[`org-ieee-sort`](https://github.com/kotoba-lang/org-ieee-sort) is where that
turned up: **UTF-8 preserves code point order lexicographically**, so walking
both strings with `string-code-point-at` and comparing code points *is* byte
order. No primitive and no language change — ordinary guest code, ported from
there.

So `-a` is a real merge with a two-element side, and the mixed directory is
what proves it is a merge:

```
ls -a    -dash  .  ..  .hidden  1one  Zebra …
prepend  .  ..  -dash  .hidden  1one  Zebra …
```

`-dash` is 0x2D and `.` is 0x2E. Replacing the merge with a prepend fails
**exactly that one case**; dropping the end-of-listing flush fails the empty
directory and nothing else.

## The exit status the bytes hid

The `-a` walk answers the merge index it reached, and returning that from
`main` made every `-a` case produce **byte-identical output and exit 2**. The
suite compares status as well as bytes, so it failed six cases; a suite
comparing only stdout would have called all six green.

## Capabilities

`:cli/args` (38), `:fs/browse` (34), `:io/write` (37). The browse scope is
baked into the packaged binary, so `./ls` lists exactly the tree it was
packaged for and the caller cannot widen it.

## Several operands are SORTED, and a file comes before a directory

Measured against `/bin/ls` 2026-09-10:

```
ls d2 d1      ->  d1: … then d2: …      the operands are sorted
ls f.txt d1   ->  f.txt, blank, d1: …   a non-directory is listed first,
                                        with no header, whatever the order
```

Directory operands get a `PATH:` header and a blank line between sections; a
single operand gets neither.

### No array, no sort primitive

The order is produced by repeatedly selecting the smallest operand strictly
**after** the one just emitted, with ties broken by **argument index**. Only
the index has to be carried, since the value is `(arg (decimal-of i))` away.

Both halves of that are held down by a control:

- walking argv in order instead of sorting fails **3** cases — and correctly
  leaves `hidden plain` passing, since there the two orders coincide
- comparing values without the index tie-break fails exactly **1**,
  `plain plain`, because a repeated operand is emitted once instead of twice

### A path's kind comes from its parent

There is no stat form, so whether an operand is a directory is read out of
its **parent's** listing, which answers `NAME<TAB>D`. Same technique
[`org-ieee-cp`](https://github.com/kotoba-lang/org-ieee-cp) uses and
[`org-ieee-find`](https://github.com/kotoba-lang/org-ieee-find) walks with.

That is why this grants `:fs/app-data` (35) as well as `:fs/browse` (34): the
EXISTS form tells a missing operand from a present one, and it answers under
the **fs** scope rather than the browse scope, so both are packaged.

## What this is not

No `-l`, `-1`, `-R`, `-t`, `-r`, `-d`, `-F`, and no column output: `/bin/ls`
prints one per line when stdout is not a terminal, which is the form this
matches. With no operand at all this exits 1 rather than listing something
else — POSIX lists the working directory and there is no cwd capability.
