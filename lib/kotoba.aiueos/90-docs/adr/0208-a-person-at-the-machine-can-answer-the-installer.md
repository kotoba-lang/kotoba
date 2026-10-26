# ADR-0208 — a person at the machine can answer the installer

- Status: accepted
- Date: 2026-09-10
- Extends ADR-0097 (USB install and headless bootstrap) and ADR-0099 (live
  installer and QEMU install gate). Changes no gate state in
  `os/aiueos/contracts/install-v1.edn` and none in root ADR adr-2608251418.
- Modelled on the ubuntu-server installer (subiquity), deliberately and
  partially. What was borrowed and what was refused is the substance of this
  ADR.

## What was missing

The install chain was complete in one direction and absent in the other. An
owner could author an `aiueos.install-intent.v1` **on another machine, ahead
of time**, with nine flags:

```
kbb --backend sci os/aiueos/scripts/install-intent.cljk create \
  --receipt ... --hostname ... --target-model ... --target-transport ... \
  --target-min-gb ... --target-max-gb ... --ssh-public-key-file ... \
  --confirm-create ... --out ...
```

and the USB would then install unattended. A person **sitting at the machine**
had nothing. The contract said so in one field, and had said so since
2026-08-25:

```clojure
:interactive :dry-run-report-only
```

That is not a small gap. Every flag above except `--hostname` describes
hardware the operator is standing next to and the authoring host cannot see.
`--target-model` and `--target-transport` have to be typed from a spec sheet;
`--target-min-gb`/`--target-max-gb` have to be guessed wide enough to admit
the disk and narrow enough to exclude the others. Guess wrong in the wide
direction and the intent admits a disk nobody meant to erase; guess wrong in
the narrow direction and the install refuses on the target with
`target-capacity-out-of-bounds`, which reads like the wrong disk was fitted.

## What was borrowed from subiquity

- **The screen sequence is data.** Subiquity has one controller per screen and
  walks them in order. `aiueos.installer.guided/flow` is that list —
  network, storage, identity, ssh, confirm — and `pending-steps` is the walk.
- **An answer file may pre-answer any screen** (subiquity: `autoinstall.yaml`).
  `aiueos.install-answers.v1` is that file. A complete one asks nothing, which
  is what makes an unattended replay possible; a partial one asks only for the
  gap.
- **`interactive-sections`**, with the same semantics and the same `"*"`
  escape hatch: a section that IS answered is asked anyway when it is named.
- **The answer file is validated before anything is probed.** Subiquity
  schema-checks autoinstall before curtin is invoked; here the check runs
  before the first `lsblk`, so a malformed unattended answer file fails while
  the target disk is untouched.
- **A finished run emits the answer file that reproduces it.** Subiquity
  writes `autoinstall-user-data` at the end of an interactive install.

## What was refused, and why

**Subiquity's storage answers may name a device path.** `path: /dev/sda` is a
legal autoinstall answer. Here that is refused by contract — install-v1.edn
decision 2 exists because "largest disk", "first NVMe" and a bare device name
all eventually name the wrong machine's disk. So the guided storage screen
does **not** record the disk the operator picked. It records the MATCH the
pick implies — model, transport, capacity bounds, and optionally the serial
digest — and the installer re-derives the device from that on the target
machine, refusing unless exactly one disk matches.

This is the one place where the guided installer is strictly better than the
tool it copies, and it costs nothing: the operator still points at a line in a
list. `disk->match` does the derivation, and the emitted intent contains no
`/dev/` path at all — which is asserted, not assumed.

**No language, keyboard, mirror or snap screen.** The live environment has no
keymap layer and no package mirror. A screen that collects an answer nothing
reads is theatre.

**No new authority.** The guided installer opens no block device, writes no
partition table and erases nothing. It produces the same
`aiueos.install-intent.v1` that already existed, verified by the same
`install-intent.cljs verify`, consumed by the same `install-live.cljs` and
`install-to-disk.cljs`, sealed into the same USB receipt chain. A second
intent shape would have been a second admission surface.

## The defect this found in its own first draft

The first implementation keyed the walk off the intent's `:mode`: unattended
meant "ask nothing". That conflated two different things. `:mode` says how the
INSTALL runs on the target machine (decision 2 — an unattended intent is the
owner's confirmation); it says nothing about how the intent was authored. An
operator standing at the machine authoring an intent that will later install
unattended was asked nothing and got an empty intent.

The measurement said `pending=0` where five screens were due. The walk now
keys off what the answer file actually contains, and
`walk-mode-does-not-decide-who-is-asked` pins it: the two modes must produce
the same pending list.

## The confirmation rule

Confirm is asked whenever any other screen was asked. If a person answered
something in this run, that person confirms in this run — a confirmation
carried in from a file cannot confirm a hostname or a disk chosen a minute
ago. When nothing was asked, the file's own confirmation stands, exactly as
`install-intent.cljs` accepts `--confirm-create` from a script.

## Evidence

`os/aiueos/scripts/test-guided-install.cljk`, 53 cases, offline, fake probe
fixtures and temp files only — no block device is opened. Registered as
`:guided-install-test` in `scripts/tasks.edn`.

Three claims and the break that would make each of them red, measured
2026-09-10 rather than asserted:

| claim | break applied | what turned red |
|---|---|---|
| the capacity comparison is inclusive at both ends | `<=` → `<` in `install-intent.cljs` `verify-intent` | exactly `verify-admits-exactly-min-bytes` and `verify-admits-exactly-max-bytes`, nothing else |
| answers are validated before anything is probed | the early validation gate deleted | exactly `guided-validates-before-probing`, and with `status=1` (the run reached a probe file that does not exist) instead of `status=2` |
| the emitted intent is a working intent | — | the intent is handed to the real `install-intent.cljs verify` against a synthesised probe report; it admits, and admits again after a replay |

The date rendering is checked against the host as an oracle: 2000 random
instants must render exactly as `Date.toISOString` renders them. It is
computed rather than delegated because the two hosts disagree —
`Instant.toString` omits milliseconds when they are zero and `toISOString`
does not, and an intent is a digested artifact.

## What this does NOT claim

- **No hardware.** The interactive path is measured against a piped answer
  script, which takes the same code path as a terminal (fd 0, byte at a time,
  no test-only branch). It has not been run on the qualification target, and
  gate I7 stays red.
- **No fleet gate.** `:installer-test` and `:install-chain-test` are not fleet
  gates either; this follows their placement. Registering one is follow-up,
  and a gate is not landed until it has been green once on the fleet.
- **The live-installer UKI does not launch this yet.** `/init` hands over to
  `install-live.cljs`, which consumes an intent that already exists on the
  USB. Wiring the guided program in as the entry point when the USB carries no
  intent — the interactive install product — is the next tranche.
