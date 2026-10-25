# STATUS — 2026-09-09

The guest compiles and **runs as native machine code**, and its answers match
`find … -type f` across six trees (see README). Both blockers this file
carried on 2026-09-07 are gone, and neither was the thing that was actually
blocking.

## What the previous status said, and what was true

| recorded blocker | state |
|---|---|
| compiler wire-id **36 vs runtime 261** for `:fs/browse-dir` | **moot.** `:fs/browse` (wire 34) answers the same `"NAME<TAB>D"` bytes since amu `a681d3f2`, so the second capability is not needed for a tree walk. Measured 2026-09-09: `kbb.browse/subdirs` answered 2 for a 3-entry directory, executed, with only wire 34 granted. |
| **murakumo KIR-drift** coupling any amu sema pin advance | **not on this path.** It was a cost of landing `:fs/browse-dir`; nothing here requires that advance. |
| `find/core.kotoba` unverified | **rewritten and verified.** The previous guest could not have worked: it called `browse/entries-dir`, which `kbb.browse` does not export; it called `walk-file`, declared after its caller; it compared an `i64` to `"1"` with `string=?`; it used a relative path, which the native loader refuses outright; and despite its own docstring it never recursed — a directory entry contributed 0 and was never descended into. |

**The real blocker was `string-index-of`**, which had no native lowering, so a
listing could not be split into lines at all. It failed as `aggregate ABI
rejected: call-abi-not-admitted`. Landed 2026-09-09 across the three gates in
front of it: kotoba-native `11691559` (ADR 0081), kotoba-verifier `1810a62c`
(ADR 0051), osaho `1a81e2d7` (ADR 0271), with amu's pins in kotoba-lang/amu#913.

## The real bound now

Not a capability and not a gate: the loader's 65,536-byte string arena is a
bump allocator that never reclaims, so the walk is bounded by bytes ever
concatenated. Measured ceiling is a few dozen directories, and it moves with
path length — the numbers are in the README.

This repository therefore does **not** yet replace `scripts/repo-search.cljs`,
`scripts/langchain-store-adoption-scan.cljs` or `scripts/jvm-dependency-scan.cljs`
over `orgs/`. Saying otherwise would be the claim this file exists to prevent.

## Next

1. `:io/write` (stdout) so results stream instead of accumulating. That is the
   capability this repository is waiting on, and it does not exist yet — the
   catalog has no stdout and no argv entry at all.
2. Then a printed listing rather than a count, and content grep on
   `:fs/app-data`.
3. Register this repository in `manifest/west.yml` — it is currently an orphan,
   which is why `kbb --backend sci scripts/repo-search.cljk` could not see it.
