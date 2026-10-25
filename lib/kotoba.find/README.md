# kotoba-lang/find — recursive search of a directory tree, in Kotoba

Walk a granted directory **tree** and count the `.clj` / `.cljc` / `.cljs`
files in it, as a `.kotoba` guest that runs on the kbb hosts — native (amu
KEXE + `kexe_loader.c`) and js — with `:fs/browse` (wire 34) and
`:env/read` (wire 33).

```
FIND_ROOT=<absolute path> ./guest        # answers the file count
```

## This no longer needs `:fs/browse-dir`

The repository was started on the premise that `:fs/browse` *"answers entry
NAMES only with no way to ask whether an entry is a directory"*, so a recursive
walk needed a second capability — `:fs/browse-dir`, compiler wire 36 / runtime
id 261 — and `STATUS.md` carried two blockers for it.

**That premise was true when it was written and is not true now.** Wire 34
answers `"NAME<TAB>D"`, where `D` is `1` for a directory, since amu `a681d3f2`;
`kbb.browse/subdirs` and `entry-dir?` read exactly that flag. The two wires
carry the *same bytes*.

What actually blocked this repository was neither recorded blocker:
`string-index-of` had no native lowering, so no listing could be split into
lines at all. That landed 2026-09-09 (kotoba-native ADR 0081, kotoba-verifier
ADR 0051, osaho ADR 0271).

## Measured, executed

aarch64-macos, through `tools/kexe_loader.c`, with only wires 33 and 34 granted:

| tree | `find … -type f` | this guest |
|---|---|---|
| 4 files over 3 levels | 4 | 4 |
| + one at depth 4 | 5 | 5 |
| + one at the root | 6 | 6 |
| − one at depth 2 | 5 | 5 |
| + an empty directory | 5 | 5 |
| a directory **named** `weird.clj` | 4 | 4 |

The last row is the one a naive suffix test gets wrong. `kbb.browse` exports
`entries` (every name) and `subdirs` (the directory names); both come from the
same listing and names in one directory are unique, so scoring the first and
subtracting the second leaves exactly the files — a directory called
`weird.clj` is counted once and subtracted once.

## The size it actually works at

A native guest's strings live in one 65,536-byte arena in the loader, and
`string_pool_used` only ever grows — there is no reclamation for the life of
the instance. So the walk is bounded by every byte it has ever concatenated,
not by what it holds.

Measured with fuel at 50,000,000 so that fuel is not the binding constraint,
one file per subdirectory:

| root path length | ran | trapped `SIGILL` |
|---|---|---|
| 17 bytes | 16 subdirectories | 24 |
| 123 bytes | 12 subdirectories | 16 |

The ceiling moves with path length, which is what says the limit is **bytes,
not a count**. A 57-directory repository checkout — 4,790 bytes of directory
paths, well under the arena — also traps, because the arena is spent on
intermediates.

**So this answers for a tree of a few dozen directories, not for `orgs/` with
its thousands.** It does not yet replace `scripts/repo-search.cljs`. The fix
is not a bigger arena but to stop accumulating: when `:io/write` lands, each
result is written as it is found and the walk holds nothing. That is why
stdout is a correctness capability here and not a convenience.

## Capabilities

`:fs/browse` (wire 34) for the tree, `:env/read` (wire 33) for `FIND_ROOT`.
Both are scoped by the policy and fail closed without a resource scope. The
native loader refuses a relative path outright, so `FIND_ROOT` must be
absolute.

Content grep (`:fs/app-data`, wire 35) is not in this slice: reading file
bodies into the same arena would lower the directory ceiling further, and the
honest order is to stream first and grep second.
