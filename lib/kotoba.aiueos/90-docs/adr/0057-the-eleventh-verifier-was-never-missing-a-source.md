# ADR-0057 — The eleventh verifier was never missing a source

Date: 2026-08-18

## Status

Accepted as a measurement. It resolves a question ADR-0050 recorded as
unanswerable, adds the eleventh measurement, and changes the ratchet so that
measuring more cannot look like regressing.

## The question ADR-0050 could not answer, answered

ADR-0050 noticed `verify_value_runtime_kernel_image.clj` with no
`value-runtime-kernel-image.kotoba` beside it, and recorded: *"which of the two
is missing is not a thing this run can know."* It is, and git knows:

- `git log --all --diff-filter=AD -- os/aiueos/kotoba/value-runtime-kernel-image.kotoba`
  is **empty**. That source has never existed on any branch.
- The verifier arrived in `db4aeed`, *"cleanup: land untracked WIP (35 files)"*.
- Its `-main` takes **fourteen** arguments, not two.

It is not a per-object verifier missing its object. It is the **whole-image
verifier**: `compile-project` over the eleven value modules plus
`aiueos.native.kernel` and `aiueos.native.value-runtime-kernel`, checked against
`value-runtime-kernel-image-v1.edn`. The naming convention that made it look
broken — verifier *X* checks object *X* — simply does not apply to it.

The hedge was carried in the receipt for four iterations. **A recorded
"unknowable" is worth re-testing before it becomes furniture**; this one cost
one `git log`.

## What running it says

```
FAIL: project module requires an explicit :export vector   {:phase :project-link}
```

Two modules in the tree have no `:export`: `value-handle-plan.kotoba`, which is
not part of the image, and **`native/kernel.kotoba`, which is** — this
repository's production hard-flip input. So the composite verifier has never
been able to run, and making it run is a change to the production kernel source
rather than to a test.

**This bears on [amu#626](https://github.com/kotoba-lang/amu/issues/626).**
`compile-project` *requires* the `:export` vector that `compile-source`
ignores. The value objects are project modules being verified one at a time in
source mode, so the export-symbol mismatch that issue asks about may be a mode
mismatch on this side rather than a compiler defect. That does not explain why
`compile-source` picks `kotoba_aiueos_probe` instead of refusing, so the issue
stays open — with this added to it.

## The ratchet had to learn a distinction

Adding the eleventh measurement took the receipt from 10 failures to 11, and
the ceiling said *"this number may only be lowered."* Taken literally, the rule
punishes measuring: the cheapest way to keep it green is to stop looking.

So the ceiling now moves in a pair. `failing-ceiling` may be raised **only
together with `objects-at-ceiling`**, and only because a new object is being
measured; a scan that shrinks while the ceiling stays fails. Underneath both is
`passing-floor`, which genuinely may only increase and is **zero** — nothing in
the value runtime compiles against the pinned compiler.

## Executable evidence

`aiueos.value-runtime-baseline-test`: **11 tests, 81 assertions, 0 failures**.
Full suite **628 tests, 9388 assertions, 19 failures** — the baseline nineteen.

**Both directions**: shrinking the receipt to nine objects while leaving the
ceiling at eleven fails `the-failure-count-has-not-grown` on the
objects-at-ceiling assertion *and* the evidence floor — a shrunken scan cannot
buy itself headroom.

## A process note, repeated

ADR-0054 recorded editing the shared west checkout by accident after a failed
`worktree add`. **It happened again this iteration, the same way**: a `cd` into
the child repo persisted, the next command's `git -C orgs/...` and `cd` to the
worktree both failed, and the commands after them ran anyway. Caught by
`git status`, restored, redone with absolute paths.

Twice is not a slip, it is the shape of the tool: `&&`-chained setup does not
protect the lines after it, and a persistent working directory makes a relative
path mean something different than it did last call. The habit that actually
works is absolute paths everywhere, which this ADR's own commands now use.

## Remaining boundary

- **Eleven failing.** The eleventh needs `:export` on the production kernel
  source; the other ten are #625 and #626.
- **The composite verifier has still never produced a verdict about the image**,
  only about its own link step.
