# ADR-0278 — The Itonami OS shell: first run, trust strip and key lifecycle

Date: 2026-10-28

## Status

Proposed (design only, nothing in this ADR is implemented). It extends ADR-0275 (the web3-first positioning and the W1-W8 scorecard) and
ADR-0277 (key custody). It creates no kernel, ABI, signer or trust root. Every row is `:spec` until its gate prints green.

## Why

ADR-0275 fixed the positioning (Itonami OS : AIUEOS = Brave : Chromium) and the rows, but not what the user sees and does. The native
desktop now has real pieces (merged, QEMU TCG with synthetic input only): the consent panel (Allow/Deny by key and pointer, modal), the
device key created under a passphrase and sealed (kotoba#959, #960), signing behind its own consent (#958), the sealed key stored on the
scratch disk and locked after a reboot (#962). They are reachable only through undocumented keys (F8 key, F7 sign, F9 fold), the
identity is a hex fingerprint, "Wallet" is a static "none", and there is no first-run, lock, forget or retry limit. Maturity here is
mostly a UX contract, so it is written down before more keys are added.

## Facts this design starts from (read from the code)

- The surface has no spare words (JUN-479). Word 2039 carries the shell's whole trust state: bit 0 consent open, bit 1 key kinds, bits 2..5
  Allow count, bit 6 key present, bits 7..30 fingerprint (or, with no key: bit 7 locked, bits 8..12 typed length, bit 13 unlock kind), bit 31
  sign/passphrase kind. New state must either reuse these bits or wait for the JUN-479 layout words.
- Consent text is static and states what this build asks; it is not read from a requester (W5 is open).
- The key record is one sector (4) of a separate 64 KiB scratch medium, not the boot media.

## Decisions

1. **The trust strip is the home.** The Itonami home shows five rows in fixed order, each a statement that is true of this build, each with
   an action only where one exists: *Identity* (`DID: none` / `locked` / `ed25519 <fingerprint>`), *Keys* (the actions below), *Approved: n
   this session*, *Network: off*, *Telemetry: none*. A row never claims what it cannot read (no "Wallet" row until a wallet exists; the
   current static "Wallet: none" is removed rather than kept as decoration).
2. **Actions are visible, not keys.** The Keys row shows buttons for the actions valid in the current state: no key -> `Create key`; locked
   -> `Unlock`; unlocked -> `Sign test` (until an app asks), `Lock`, `Forget`. F7/F8/F9 stay as accelerators; the hint line lists only
   those that exist. Pointer and keyboard reach every action (same hit geometry as the consent panel).
3. **First run.** With no key and no stored key the home offers `Create key` once; declining records nothing and the offer is a normal
   button afterwards. Nothing is created, stored or sent without the consent panel.
4. **Lock and forget.** `Lock` wipes the seed and the public key from RAM and returns to the locked state (a stored key) without touching
   the disk; with no stored key, Lock is not offered (it would destroy the only copy). `Forget` is a consent request of its own kind naming
   the effect ("erase the stored key"), requires the passphrase, overwrites sector 4 with zeros and reads it back; it is the only action
   that destroys a stored key.
5. **Wrong passphrase.** After a wrong passphrase the panel says so (not just returns to the home), and attempts are counted in the key
   record (a word of the record, written before the KDF runs, cleared on success). After 3 failures the next attempt is delayed by a doubling
   interval, capped at 15 minutes. The delay needs a guest time source the desktop does not use today (not checked: PIT or TSC); until one is chosen and gated, the counter is recorded and the delay is not claimed. This slows a guess at the keyboard; it does not
   protect a stolen disk, where only the passphrase and the KDF cost count (decision 6).
6. **Passphrase strength is told, not hidden.** The create panel shows the length and a plain strength hint (< 8: weak, offline guessable;
   8-11: fair; >= 12: good). The alphabet stays a-z and space until the keyboard path types more. The KDF stays iterated SHA-512 until a
   memory-hard function exists in the guest; the limit is documented in the panel's help line, not only here.
7. **Consent text comes from the operation (W5).** The consent panel's Service / Endpoint / Action / Data lines are filled from the
   operation descriptor of `kotoba.app.client-runtime.v1` for the requesting app, within the fixed panel geometry, and a line longer than the
   field is refused rather than truncated (a truncated line could hide what is approved). Until the descriptor reaches the guest, the
   static texts remain and are labeled `this build`.
8. **Everything a dapp can ask is shown before first launch (W5).** Launching an app first shows its declared operations (service, endpoint
   origin, data categories) with the effective set at zero approvals; each operation then needs its own fresh consent, and an approval
   never covers another operation or endpoint (shared contract). The shell keeps no persistent approvals in this ADR.
9. **`ipfs://` (W4) opens only after the bytes match the CID,** through the existing `aiueos.cid-v1-admit`; fetching is a declared network
   operation with its own consent, and a failed match shows the refusal, never the bytes. This needs a network path and a scheme
   handler, neither of which exists; it is sequenced last.

## What the user can rely on (acceptance of the whole design, per row of ADR-0275)

W2 identity row reflects locked/unlocked/none without a restart; W3 the key survives a reboot, a wrong passphrase is refused, lock/forget
behave as above; W5 declared operations precede launch and effective approvals start at zero; W7/W8 unchanged (idle desktop emits nothing).
Each item has its own QEMU gate with a negative control; synthetic input proves no human consent and no physical-hardware behaviour.

## Order of work (dependency first)

1. Visible actions on the Keys row, the Identity row, and removal of the static Wallet line (decisions 1, 2). Needs hit regions on the home
   (the consent panel's hit-test code is the model) and no new surface words if the layout fits in the existing home lines.
2. Lock, then Forget (decision 4); both small, both testable in the existing two-boot gate.
3. Wrong-passphrase message and attempt counter with delay (decision 5); needs one record word in sector 4.
4. First-run offer (decision 3), strength hint (decision 6).
5. Operation-derived consent text and pre-launch declaration (decisions 7, 8); depends on the JUN-479 surface words and on the descriptor
   reaching the guest.
6. `ipfs://` (decision 9); depends on a network path.

## Not decided here

The real minimize to the dock and a fuller home screen (JUN-479); more than one key or key rotation; passphrase alphabet beyond a-z and
space; a hardware-backed key (none in QEMU TCG); the "Itonami gateway" (no design exists; ask the owner what is meant before drawing one).
