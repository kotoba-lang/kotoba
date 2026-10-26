# ADR-0239 — the stick that asks installs, and links the account by QR

- Status: accepted (stage 1 landed and measured offline; no K16 run, I7 stays red)
- Date: 2026-09-25
- Owner request: 「USB installer として BIOS 起動時に選択して 7735HS に aiueos を
  install したい。また QR コードを読み込んで kotoba.cloud アカウントと同期
  できる様にしたい」. Owner decisions the same day: install to a **second disk**
  in the K16 (the existing SSD is kept), and the account link **in the installer
  first, native later** (both stages).
- Extends ADR-0208/0210 (the guided installer, the stick that asks) and
  ADR-0113 (`auth.kotoba.cloud` device authorization). Changes no gate state in
  root ADR adr-2608251418 except the one field named below.

## What was wrong

ADR-0210 says the guided stick "installs nothing without a person". The code
did less: `install-live.cljk` treated every `mode=interactive` intent as
`:dry-run-report-only`, and `guided-install.cljk` writes `interactive` unless
told otherwise. So a person who picked the USB in the K16's boot menu, answered
all five screens and retyped the hostname got `AIUEOS_INSTALL_ADMIT dry-run …
nothing was written` and a power-off. The stick that asks could not install.
Nothing was red because no test reaches past target selection (it needs
`lsblk`), and the contract field said `:dry-run-report-only` — true, and the
opposite of the product ADR-0210 describes.

## Decision

1. **An interactive intent authored at this console installs after the person
   types the destructive phrase.** `install-live.cljk` knows the intent was
   authored here (`asked-here?`: there was no intent when it started). It runs
   the dry run first — every admission the unattended path has — then prints the
   one target disk and asks for `ERASE <device> FOR AIUEOS`. What the person
   typed goes to `install.mjs --destructive-phrase` verbatim; `device-policy.mjs`
   remains the only place that decides whether it matches. An interactive intent
   **carried on the stick** still has nobody to confirm it and stays a dry run.
   The unattended path is unchanged.

2. **The account link runs at that console, before the erase, and is optional.**
   `account-sync.cljk` is ADR-0113's flow, unchanged on the wire:
   - the Ed25519 signing and X25519 encryption keys are generated on the
     machine being installed, at install time (the SSH host-seed rule);
   - `POST /v1/aiueos/device/start` carries a signed binding of device DID,
     model, method, both public keys and a request nonce;
   - the approval URL (public flow ID only) is drawn as a QR on the Linux
     console; a phone scans it and approves with its Passkey;
   - polls are signed; a 200 is admitted only when every echoed field binds this
     flow, device, challenge, model, method, authority, RP ID and both keys, with
     user presence, user verification and a Passkey-backed account;
   - the result goes through `aiueos.device-auth` (`authenticate-account`,
     then `prove-device` with a signature the device key just made and this
     program just verified) — the same state machine the hosted adapter uses.

   The record (`aiueos.account-sync.v1`, private keys included) is embedded by
   `make-provision-record.cljk` into the provision zone the SSH host seed already
   lives in, which the target receipt binds by digest; the tmpfs copy is deleted
   after the zone is written and read back. Declining, an unreachable authority
   or an expired flow leaves an install **without** an account and says so
   (`AIUEOS_LIVE_ACCOUNT not-linked …`); a malformed record is a refusal.

3. **The QR encoder is portable Kotoba source, `src/aiueos/qr.cljk`.** The hosted
   adapter's `io.nayuki/qrcodegen` is a JVM jar that neither the stick's nbb nor
   amu-native can load, and stage 2 needs the same encoder on KERNEL.ELF. It
   follows qrcodegen 1.8.0 step for step, including its mask choice, and the jar
   stays as the oracle, not as a dependency replaced.

4. **The bundle carries `orgs/kotoba-lang/security/src`.** `aiueos.device-auth`
   requires `kotoba.security.information-flow` (declared in
   `security-adoption.edn`); without the root, `account-sync.cljk` dies on
   the machine with `Could not find namespace` — the ADR-0209 shape, measured.

## Evidence (2026-09-25, offline and against the live authority)

- `aiueos.qr` vs qrcodegen 1.8.0, driven directly with `java` over the jar:
  80 cases, all four ECC levels, automatic mask and each forced mask 0–7,
  versions 1 to 40 and seven too-long inputs — **module-for-module identical**,
  including the NIL (does-not-fit) answers. Reproduce: encode the same bytes with
  `QrCode.encodeSegments([QrSegment.makeBytes(b)], ecl, 1, 40, mask, false)` and
  with `aiueos.qr/encode-bytes`, compare `getModule(x,y)` to `:modules`.
- `aiueos.qr-test` on nbb: 6 portable tests green; changing one capacity-table
  entry (M, version 4: 18 → 20) turns exactly `fixed-vector-matches-qrcodegen`
  red. The `#?(:clj)` oracle test in the same namespace was **not run**:
  `kbb -M:test` substitutes cljs.test on this engine and skips it.
- `account-sync.cljk` from a Mac against `https://auth.kotoba.cloud`: the
  signed start was accepted (201, shape valid, `did:aiueos:gmktec-k16:<hex>`).
  **Nobody approved it**; the poll, binding check and possession proof have not
  run against the real authority, only against their code.
- `test-guided-install` 56/56 (3 new: model slug), `test-provision-record` 9/9
  (3 new: account carried, malformed refused by name, absent when not given),
  `test-install-bundle` 36/36 (2 new: security root, `account-sync.cljk` loads
  from the bundle; the no-classpath control still loads nothing),
  `test-install-chain` 22/22.

## What this does not claim

- **No K16 run and no QEMU run of the new console path.** The interactive
  install and the account link after target selection need `lsblk` and a
  console; nothing offline reaches them. I6 is amber and I7 stays red.
- **The second disk is a property of the answers, not of this code.** The
  storage screen lists the disks it can see; the person picks the empty one,
  and `install-live` refuses unless exactly one disk matches. Two identical
  SSDs need the serial binding the storage screen offers.
- **The installed kernel does not read the account record** (stage 2 — native
  QR, HTTPS with full chain verification, Ed25519 signing on KERNEL.ELF; the
  last is also I4's blocker). The Wi-Fi envelope is carried, not applied.
- **What boots after the install is today's aiueos** (README "Where it actually
  is"): no scheduler, no ring 3; one job per boot.
