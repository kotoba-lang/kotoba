# ADR-0275 — Itonami OS is the web3-first browser OS

Date: 2026-10-27

## Status

Accepted direction (owner request 2026-10-27). **Nothing below is implemented by this ADR**: it fixes the positioning, the
scorecard and the order of work. Every row is `:spec` until its gate prints green; no row is claimed. Extends ADR-0274 (Itonami OS is
the `awai` distribution of AIUEOS); it creates no kernel, ABI, signer or trust root.

## Positioning

AIUEOS is the common foundation. **Itonami OS is to AIUEOS what Brave is to Chromium**: the same core, a distribution whose defaults
put the user's keys, data and consent first, and whose "browser" is the shell of the machine. Where ChromeOS makes the OS a thin client
of one vendor's cloud, Itonami OS makes it a thin client of nobody: identity, storage and inference are the user's, and every external
operation is the user's explicit act.

This is not new machinery. The workspace's shared architecture contract (apps run in the user's environment; the origin is static;
`kotoba.app.client-runtime.v1`; fresh `each-operation` consent) already is the Brave-shields model. The work is to make it visible and
usable in the native desktop.

| Brave | Itonami OS | Existing owner |
|---|---|---|
| Shields (block by default) | No external operation without fresh, operation-bound consent; denial sends nothing; no silent remote fallback | client-runtime broker, ADR-0274 |
| Brave Wallet | Device-bound passkey today (ADR-0270); a user-held DID / key wallet (`org-w3-did`, `org-ietf-ed25519`, CACAO) for sign-in and signing, never leaving the device | ADR-0270, kotoba libs |
| IPFS / ENS resolution | Content-addressed fetch (CID verified before use), `ipfs://` and DID-document resolution, no gateway trust | `io-ipfs`, `io-ipld`, `kura` |
| Brave Sync (E2EE) | Backup/restore of the user's records (ADR-0271) extended to user-selected storage, encrypted on device | ADR-0271 |
| Brave Rewards / BAT | Out of scope. No token, no ads, no telemetry. Payments, if any, are an app operation with its own consent | — |
| Leo (local-first AI) | Local inference by default; downloading a model never authorizes sending a prompt (shared contract) | itonami-agent `:inference` |
| Private by default | No telemetry, no account, nothing leaves the machine until the user approves the displayed operation | shared contract |

## Scorecard (the web3-first rows; all `:spec`)

Same form as the ChromeOS-grade scorecard of ADR-0270..0273: a row is green only when its named gate prints its marker on the same
serial as the chain before it.

| Row | Statement | Proposed gate |
|---|---|---|
| W1 | A consent prompt is a first-class shell surface: it names service, endpoint, operation and data categories, and Allow/Deny are reachable by pointer and keyboard (ADR-0262). Deny sends no frame. | `guest-browser-consent` |
| W2 | The shell shows an always-visible trust strip: wallet/DID state, and a count of operations approved this session. | `guest-browser-trust-strip` |
| W3 | A user-held key signs a challenge on device; the same key re-verifies after reboot; a key from another device is refused. | `guest-browser-wallet-sign` |
| W4 | An `ipfs://` address opens a window only if the fetched bytes hash to the CID; a mismatch is refused and shown. | `guest-browser-cid-open` |
| W5 | A dapp's declared operation set is shown before first launch and the effective set starts with no approvals. | `guest-browser-dapp-grant` |
| W6 | Records are backed up to a user-selected store, encrypted; a restore on a fresh volume returns them. | extends `guest-browser-backup` |
| W7 | Inference runs locally by default; a remote rail needs its own consent and is never a fallback. | `guest-browser-infer-consent` |
| W8 | No outbound network frame occurs on an idle desktop (telemetry-free is measured, not asserted). | `guest-browser-idle-silent` |

## Shell UX direction

Observed on the native diagnostic desktop (QEMU, 2026-10-27): the launcher row, a letter-tile dock (`M I Y A`), a centered window with a
title and a close control, and plain text bodies. Findings that this ADR turns into work:

1. **No system chrome.** There is no clock, no status area and no place for trust state. Add a right-aligned status area in the
   launcher row (clock, wallet/DID, consent counter). Trust state must be visible without opening anything (W2).
2. **The dock is anonymous.** Single-letter tiles say nothing about the app or its running state. Show the title, a running marker and
   the focused marker; keep the number-key and Tab/Escape contract of the current desktop.
3. **Windows have one control.** Add minimize/restore through the dock and tray (ADR-0254/0255 already specify this on the hosted
   line; the native line has not taken it) and a visible focus ring, so focus is never inferred from stacking alone.
4. **Input fields look like text.** The Itonami goal is a bare line (`Goal local:`). Give it a field box, a caret that is always drawn
   in the focused window, a placeholder, and a visible `local only` badge: the goal is RAM-only and is not submitted.
5. **Itonami is the front door.** Its first screen should be the web3-first home: identity (DID / passkey), the dapps with their
   declared operations, and the consent log, not a diagnostic card.
6. **Consent is a window kind, not a dialog afterthought** (W1), drawn above every window and not dismissible by a click elsewhere.

## Constraints that decide the order

- The native renderer is a bounded behavior mirror: 8192-byte surface, 259 ops, 64-code-point bodies, parity-gated against the hosted
  engine (ADR-0234). Items 1-4 add ops and surface words, so they need their own parity vectors, not an ad-hoc edit of `desktop.kotoba`.
- `desktop.kotoba` and the native build are under concurrent change (JUN-450; kotoba PR 905 carries the macOS native build driver and
  a desktop layout port). Renderer work starts after that lands, from it, so the change can be built and QEMU-checked locally.
- No JVM/nbb CI (owner instruction 2026-10-22): gates run natively or are recorded as blocked, never swapped for a fallback.

## Migration

1. This ADR and the `awai` descriptor intent (`distributions/awai/distribution.json`): composition intent only; nothing installed.
2. Renderer: status area + labelled dock + field box (items 1, 2, 4), with parity vectors and a QEMU screenshot gate.
3. Consent surface (W1) and trust strip (W2) wired to the client-runtime broker.
4. Wallet/DID (W3), CID open (W4), dapp grant (W5), then backup target (W6), local-inference consent (W7), idle-silent (W8).
5. Qualification and release stay with the existing OS release authority (ADR-0274); this ADR grants no capability.
