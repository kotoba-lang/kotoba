# ADR-0209 — the install USB carried no namespaces, and nothing was red

- Status: accepted
- Date: 2026-09-10
- Fixes a defect on `main`, measured rather than reasoned about.
- Follows ADR-0208 (the guided installer), which is what made the gap visible:
  its program lands in the bundle automatically, its namespace does not.

## The defect

`/init` extracts `INSTALL.TGZ` to a tmpfs, `cd`s into it, and hands over:

```sh
./node-linux-x64 nbb-bundle/node_modules/nbb/cli.js install-live.cljs
```

Reproduced 2026-09-10 by assembling that directory and running that line:

```
Message:  Could not find namespace: kotoba.lang.text
```

Not install-live alone. `install-to-disk.cljs`, `install-intent.cljs` and
`make-provision-record.cljs` are in the same state — every `.cljs` the bundle
carries. The stick boots, the initramfs finds its payload, the bundle extracts,
and the first decision the installer makes cannot load.

## Why

On 2026-09-09 this repository's tooling moved from `clojure.string` to
`kotoba.lang.text`. That commit's own follow-up is recorded in `nbb.edn`, which
says plainly that forty-nine scripts under `os/aiueos` now require the
namespace and that nothing invoking them had been told where it lives — and
which fixes it with a sibling path, `../text/src`.

**`nbb.edn` is not on the USB.** A sibling path resolves relative to the file
it is written in, and the stick has neither the file nor the sibling. The fix
reached every caller in the repository and no caller on the medium the
installer actually runs from.

The node USB beside this one was never affected: `make_node_bundle_tgz` has
carried a `cp/` root for its classpath all along, and its `/init` branch passes
`--classpath /run/aiueos-node/cp`. The two bundles sit in the same file, forty
lines apart. Only the install one lacked it.

## Why nothing was red

Every green in the area was about a different tree.

- `installer-test`, `install-chain-test`, `provision-record-test` run those
  scripts **from the repository**, where `nbb.edn` resolves. Measured with the
  bundle broken: 22/22, 6/6, and the ported `.mjs` suite green. Not one of them
  touches the medium.
- `install-usb-build` builds an image and verifies its receipt chain. The chain
  digests the bundle; it does not run anything in it. A tar of files that
  cannot load has a perfectly good SHA-256.
- Gate I3, `:green-qemu`, was measured **2026-08-25** — two weeks before the
  namespace move. Its evidence is real and its subject no longer exists.

This is question 8 of root ADR adr-2608136000 with the medium changed: *did the
check execute the artifact, or was it satisfied that the artifact built?* An
artifact that builds and cannot run is worse than one that fails to build,
because the build reports success.

## The fix

- `make_bundle_tgz` takes `classpath_dirs` and ships them under `cp/`, the same
  shape and the same name the node bundle beside it already used.
- `/init`'s install handover passes `--classpath /run/aiueos-installer/cp`.
- The bundled `bin/nbb` shim carries the same flag. `install-live.cljs` spawns
  `kbb --backend sci install-to-disk.cljk` **by name**, so the second hop resolves through
  `PATH` and would otherwise start with an empty classpath even when the first
  hop had one.
- `run-install-usb-build.cljs` passes `../text/src` and the aiueos `src` root
  (the latter for `aiueos.installer.guided`), and **refuses to build** when
  either is missing. A USB that dies on the machine is worse than one that was
  never written: the failure is then discovered standing next to the box, with
  the installer already booted.

Two refusals were added inside the builder, both from things that happened
while this was being written:

- **A classpath root that contributes no sources is refused.** A misquoted
  argument in the first draft of the test passed one path that did not exist;
  `rglob` returned empty, the bundle was produced clean with no `cp/` at all,
  and nothing said so. A root that contributed nothing must not be
  indistinguishable from a root nobody asked for.
- **Two roots merging into one `cp/` refuse on differing bytes at the same
  path.** Which file survived would otherwise depend on argument order.
  Identical bytes at the same path are not a conflict, and a case pins that the
  refusal is about content rather than tidiness.

## The detector

`os/aiueos/scripts/test-install-bundle.cljk`, registered as
`:install-bundle-test`. 17 cases, offline.

It assembles the bundle through the real `make_bundle_tgz`, extracts it, and
**runs each bundled entry point from inside it** with only what the stick
carries. A script may refuse for its own named reason — no device, no
arguments, exit 3. It may not fail to load.

The control is the other half and is the part that matters: the same assembly
**without** the classpath must produce the namespace error for all five entry
points. That case is green today, which is the evidence that this detector can
see the defect it was written for. A test whose control has never fired cannot
be told apart from a test that always passes.

## What this does not fix

- **Gate I3 is still evidence about 2026-08-25.** Nothing here re-runs the QEMU
  install gate, and this ADR does not move its state. The bundle now loads;
  whether the whole chain still installs under QEMU is unmeasured since the
  namespace move, and `install-smoke` needs a release image, a live UKI, a
  Linux node binary and an nbb tree.
- **No hardware.** I7 stays red.
- **The guided installer is still not `/init`'s entry point.** Its program and
  its namespace now both reach the stick and both load there, which is the
  prerequisite. Making a USB that carries no intent and authors one at the
  machine touches `--intent required`, `INTENT.JSN` and the receipt chain's
  `intent-sha256`, and is the next tranche.
