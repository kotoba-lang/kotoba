# ADR-0210 — a stick that asks

- Status: accepted
- Date: 2026-09-10
- Completes the tranche ADR-0208 named: the guided installer is now what a USB
  carrying no intent runs. Depends on ADR-0209, which made the bundle's scripts
  able to load at all.

## Two products, one builder

Until now an install USB was one thing: release image, installer bundle, and
`INTENT.JSN` — the owner's statement, authored on another machine, naming which
disk on which box may be erased. That stick installs unattended.

There is now a second: `--guided` builds a stick that carries **no intent**.
Booted as the live installer, `/init` hands over to `install-live.cljs`, which
finds no intent and runs `guided-install.cljs` with the console attached. The
operator answers five screens; the intent is written into the tmpfs; everything
below that line is unchanged.

The two differ by one payload file and by one property:

> A stick that asks cannot be left plugged in and forgotten. It installs
> nothing without a person.

That is the point of it, not an accident of packaging.

## What did NOT change

The guided path adds no authority, and this is worth stating precisely because
it is the thing that would be tempting to shortcut. The intent that
`guided-install.cljs` writes goes through:

- the same `install-intent.cljs` admission, against a **fresh probe** — the
  guided run's own probe is not carried forward as evidence;
- the same single-candidate target selection in `install-live.cljs`;
- the same device-level refusals in `install.mjs` (whole disk, internal, empty,
  not a system disk, identity unchanged between probe and open);
- the same repeat-safety check and the same target receipt.

**An intent authored ten seconds ago is not more trusted than one authored last
week.** Nothing in the chain reads `authoredBy`.

## Stated, never inferred

`--guided` and `--intent` are exclusive and one is required. Not "intent if
given": a forgotten `--intent` would then quietly produce the other product,
and the two differ in who may erase a disk without being asked. The check runs
before any I/O, so an argument error is not reported after a release image
failed to open — a different problem with a different fix.

The same rule applies to reading a stick back. `verify` decides which product
an image is **from the image alone**, and cross-checks the answer against
`SHA256S.TXT`:

- a payload carrying an intent that `SHA256S.TXT` does not list → refused;
- `SHA256S.TXT` listing an intent the payload does not carry → refused.

Without the first check the measurement is not subtle: the break test shows the
stick verifying as `INTENT` — the *other product* — while presenting itself as
one that asks.

The build receipt keeps the `intent` key in both cases
(`{"authoring": "guided-at-the-machine", "sha256": null}`), because a reader
that had to tell "guided stick" from "receipt written before guided existed" by
an absent key would be guessing.

## Exit codes are propagated, not flattened

`guided-install.cljs` exits `2` for a named refusal and `3` for
could-not-answer. `install-live.cljs` passes those through rather than
reporting "failed": an operator who typed something the installer would not
accept and an operator who walked away need to look in different places. An
unanswered run also writes no intent, which is asserted rather than assumed.

## Evidence

`os/aiueos/scripts/test-install-bundle.cljk`, now 34 cases, offline. The new
ones run the actual product path: `install-live.cljs`, from inside a real
guided bundle, with a piped operator script and a two-key-gated probe fixture.
It reaches the guided screens, writes an intent whose hostname and disk model
are the ones answered, and goes on to target selection — where, on this host,
there is no `lsblk` and it refuses on its own terms. That refusal is the
evidence the handover happened rather than the run ending at the guided step.

Two claims, and the break that turns each red, measured 2026-09-10:

| claim | break | what turned red |
|---|---|---|
| a stick with no intent runs the guided installer | the fallback in `install-live.cljs` deleted | exactly the four fallback cases |
| a payload between the two products is refused | the carried-vs-listed check deleted | exactly `undigested-intent-refuses`, and it reported `INTENT` — the stick verifying as the other product |

The control from ADR-0209 still holds: a stick that **does** carry an intent
must not ask, or the unattended product would stop at a prompt nobody is
standing at.

A defect found while writing this: the test's own `bin/nbb` shim execed `nbb`
by name while sitting first on `PATH`, so it called itself, appending one
`--classpath` per hop, forever. The real shim execs the bundled
`node-linux-x64` and cannot re-enter itself. The test shim now uses an absolute
path, and refuses rather than guessing if it cannot find one.

## What this does not claim

- **No hardware, and no QEMU.** Gate I3 remains evidence about 2026-08-25
  (ADR-0209); this adds a second product to the same unmeasured-since state.
  `smoke-qemu-install.cljs` covers the unattended stick only, and a guided
  variant of it needs an interactive console in QEMU.
- **No physical install.** I7 stays red.
- **The screens themselves are still measured against a piped answer script**,
  not a terminal in front of a person. It is the same fd-0 path with no
  test-only branch, which is the most that can be said offline.
