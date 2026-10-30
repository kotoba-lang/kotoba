# ADR-0282 — Installed itonami dapps run offline; a dapp never resolves a name

Date: 2026-10-30

## Status

Accepted (owner request 2026-10-30, AWAI-120: "Apps on the OS assume installation. Make them run even without DNS access,
set up as itonami dapps running on the OS"). First slice implemented: desktop profile 5 (`native/dapps-entry.kotoba`,
`native/dapps.kotoba`), checked on QEMU by `scripts/check-native-dapps-qemu.py` (`--profile dapps`). Physical
hardware is not qualified by that check. Extends ADR-0275 (W5 "dapp grant") and ADR-0280 (local inference by default).

## Context

The dock's four apps (Murakumo, Itonami, Yataverse, Aozora) were static cards (`aiueos/session/app_catalog.kotoba`):
"No dapp installed / No network". Their web counterparts run from public origins, and on 2026-10-30 one of them had no
DNS record at all (`ipfs.yataverse.com`). An app that needs a name lookup to start is not usable on a machine with no
cable, and it hands the lookup's operator a view of what the user opens.

## Decision

1. **A dapp is installed, not fetched.** Its code and UI are bytes in the OS image. Starting it reads only local bytes.
   Each dapp's install record is `distributions/awai/dapps/<id>.json` (`itonami.dapp.v1`): the dock id, the local core,
   the local state and where it lives, and the declared remote operations.
2. **A dapp never resolves a name.** No DNS client is part of a dapp. A remote operation names its peer by DID or CID plus an
   address the user chose, and it is declared in the install record. The record says `"dns": "never"`.
3. **Offline is the normal state, not an error.** With no network, each dapp runs its local core:

   | Dock | Local core | State |
   |---|---|---|
   | 1 Murakumo | local inference: the bounded micro bigram model, asked in place after Itonami's local-model consent; counts runs and shows the last token | RAM |
   | 2 Itonami | the Goal, its local-model request (ADR-0280 panel), the device key | Goal: draft store when a medium exists, else RAM |
   | 3 Yataverse | content-addressed store: Enter names the 64-byte Goal record as a raw CIDv1 (`01 55 12 20` + SHA-256) and re-admits it with `aiueos.cid-v1-admit` | RAM |
   | 4 Aozora | outbox: Enter asks to sign the Goal record as a post with the device key (its own panel text: "sign one Aozora post / Goal text, stays here"); Allow signs and verifies it; nothing is published | RAM |

4. **Every remote operation keeps its own consent** (shared contract, ADR-0275 W1). None is implemented in this slice; the
   install records list them with `"state": "not-implemented"`. Denial sends nothing; there is no fallback.
5. **The unit is a fixed 64-byte record.** The kernel compiler admits only a literal window length for SHA-256 and Ed25519
   input (ADR 0373 of amu), so Yataverse's block and Aozora's post are the Goal text padded with zeros to 64 bytes.

## Consequences

- Profile 5 runs the micro model inside the kernel loop. Profile 4 runs the same model in the v5 user domain (CPL3). The
  model is a pure table over a 64-code-point Goal, but moving profile 5's call into a user domain is open work.
- The app bodies stay no longer than the static cards they replace. The renderer refuses a whole frame past 259 ops, and
  four open windows with longer bodies were measured to overflow it (refusal -5).
- Surface word 30 (unassigned until now) marks the open signing request as an Aozora post.
- Nothing persists except the Goal (draft store, QEMU scratch medium only). The NVMe of a real machine has no draft store;
  there, all four cores are RAM only.
- The dapps profile is not the default entry. Making it the installed default (ADR-0274 release authority) is a separate
  owner decision, as is physical qualification.
