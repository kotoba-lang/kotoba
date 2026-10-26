# ADR 0206: the compiler that builds the board is not reachable from amu's main

Status: accepted. Date: 2026-09-08. Related: ADR-0205 (step 1 landed on it).

## The finding

`os/aiueos/scripts/build-kotoba-native-kernel-46eeedae.tmp.sh` and its boot
counterpart both refuse to run unless the compiler checkout's `HEAD` is
exactly:

```
expected=94f8fe37eabac8bf401b75b709fb25fedbbf0878
```

That commit is the tip of `origin/k16-loader-port` in `kotoba-lang/amu`. It is
**not an ancestor of `origin/main`**, and there is no open PR proposing that it
become one.

This is not a stale pin that has fallen a little behind. Measured 2026-09-08,
`origin/main`'s `src/kotoba/compiler/packaging/pe32plus.cljc` is 216 lines
*shorter* and contains none of the K16 loader:

| symbol | `origin/main` | `94f8fe37` |
|---|---|---|
| `k16-preflight` | 0 | 15 |
| `:pe32+-embedded-kernel/v3` | 0 (still `/v2`) | 1 |
| `kernel-scratch-pages` | 0 | 5 |
| `uefi-output-string-tokens` | 0 | 4 |

The west pin for `amu` (`a169d7bf`) is correct and gated — it names
`origin/main`. So the workspace's own rule is satisfied and the gap is
invisible to it: **`west update` produces an amu checkout that cannot build
this board at all.** `package-aiueos-boot --k16-preflight` does not exist
there. A fresh clone reproduces everything in this repository except the one
artifact it is about.

## Why it was not noticed

The pin has no gate. `verify-west-pins.cljs` covers `manifest/west.yml`;
nothing covers a SHA baked into a shell script, which is the same class
AGENTS.md already names for `deps.edn` (`:git/sha` pins have no gate). The
build script *does* check the pin — it refuses to run against any other
commit — so the pin is loud about drift and silent about reachability. Those
are different questions and only the first one is asked.

It also fails in the direction that looks like success: on this workstation the
pinned checkout is present, so every build for weeks has passed.

## What follows

- **Do not advance this pin to `origin/main`.** Main does not have the loader;
  moving the pin forward would not update the board, it would stop building it.
- **The work owes a merge, not a rebase.** `k16-loader-port` already contains
  `origin/main` up to `715138d0` by merge, so the direction is
  `k16-loader-port -> main`, server-side, as one PR. Until that lands, every
  further K16 loader change (ADR-0205 steps 2-4) widens the same gap.
- **Landing this ADR does not land the merge.** Recorded as a blocker so that
  the next session inherits it as a fact rather than rediscovering it; the four
  packaging test failures on the branch (`v2` vs `v3`, boot-info v4 offsets)
  are stale assertions that the merge will have to settle first.

## Proposed, 2026-09-08 evening: kotoba-lang/amu#899

The precondition this ADR named is cleared. amu's suite is green on
`k16-loader-port` -- 1335 tests, 9603 assertions, 0 failures, 0 errors. The
four assertions that were red described the `/v2` embedded-kernel format and
the pre-v4 boot-info; they now assert the layout the running kernel validates
field by field (magic `AIUEBOOT`, version word 4, memory-map pointer, and
`kernel-scratch-pages` exactly 14), which is the layout a board that boots and
answers inference jobs is running.

The PR is `MERGEABLE`, **3 files, +345/-28**, from merge-base `715138d0`.

⚠ A two-dot `git diff origin/main origin/k16-loader-port` shows +785/-6078
across 37 files and looks like a mass revert of main. It is not one. That diff
compares the branch's whole tree against main's, so everything main has added
in its 47 newer commits appears as a deletion. The three-dot diff from the
merge-base -- which is what a merge actually applies, and what GitHub's PR
shows -- is the +345/-28. **Do not read a two-dot diff as a merge preview**;
the rule this workspace already has about long branches reverting current work
is real, and this is how you check whether it applies rather than assume it.

The PR state is `BLOCKED`: amu's `main` requires a pull request and status
checks. That is a review boundary, not a defect, and not one to route around.

## What this ADR does not claim

That the branch is *ready* to merge. Its test suite is red in four assertions
that predate the tender work, and whether main wants a `/v3` embedded-kernel
format is a decision for `amu`, not for this repository. The claim here is
narrower and is the part that was not written down anywhere: **the board's
compiler is on a branch, and nothing in the workspace says so.**
