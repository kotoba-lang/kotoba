# kotoba-client-runtime.js: key handles, crypto, device-local commands, key approval, host OAuth (KOTOBA-974, 2026-11-22)

Author: Claude (claude-opus-5-5) in Claude Code, an Orca worker for the Dev coordinator. This document records a
design and its threat model, written by an AI model. It is not a human security audit, not a legal opinion and
not a product qualification. Tracking: KOTOBA-974 (child of KOTOBA-159).

Base: kotoba-lang/kotoba main `715b8e5f5`, runtime sha256 `3e2bc61e8ce544d4cc12fbf7f893be4f7f0367be00e2e3d4ebdee5c3bb410367`.
The new sha256 is in `local-changes.json`.

This is the second of two pull requests. PR 1 (KOTOBA-968) added host-local storage, declared binary/text bodies,
`device.save` and `device.openLink`. This one adds the crypto and host-assist channels PR 1 refused as
`not-declared`: key handles, `device.pick` / `device.open`, declared device-local host commands (karute
`awai_local_inference`), key approval (rodo `awai_key_approval`), and host-mediated OAuth with DPoP (nagare).

Inputs: PR 2 inputs (`pr2-inputs-20261122.md`), Yataverse's spec and acceptance tests (`runtime-gaps.md`,
`yataverse-acceptance.test.mjs`, 2026-11-22), Legal's memos (`kotoba-159-consent-dialog.md`,
`kotoba-159-consent-wording.md`, 2026-11-22), App QA's report (2026-11-22, `SUMMARY.md`).

## 1. What changes

| Scope | Change |
|---|---|
| A. Crypto and key handles | The host performs every operation. A guest holds only opaque handles (`kh.<32 hex>`), partitioned per app and per mount, in a host-memory table cleared on close. Four key classes: `secret` (`secret-32`, HKDF only), `sealing` (HKDF from a secret, wraps only), `content` (encrypt/decrypt, wraps content keys), `private` (`x25519-private` / `ml-kem-768-private`, agreement/decapsulation only), `signing` (`ed25519`). Three tiers: device secret → HKDF + AES-GCM identity/sealing key → hybrid content key (Yataverse). Every derive, unwrap and decapsulate returns a handle, never bytes. Content keys leave only wrapped. |
| B. `device.pick` / `device.open` | Separate calls, each behind the canonical trusted consent host (trusted press after the 600 ms arm, equal buttons). `pick` opens the OS file chooser inside that click and hands only the chosen file (bounded, declared type, sanitized name) to the guest. `open` hands a file to the device's default app for its type (only save-allowed types, never opaque). Neither sends anything anywhere. |
| C. Device-local host commands | The host registers a fixed allowlist (`createClientDeviceCommands`): each command has input/output schemas (enum/integer/boolean/string/bytes with byte caps), action byte caps, and an attestation (`network: 'none'`, `on-device`, `no-logging`, `no-retention`). The guest calls only commands its descriptor declares. A call that carries user data shows Legal's short confirmation (not the egress dialog), each time except where already granted; the command runs in the host and returns schema-checked output. `verifyDeviceCommandConformance` traps fetch/XHR/WebSocket/EventSource/RTCPeerConnection/beacon and console during probes. |
| D. Key approval | A declared, persistent `ed25519` key signs only through `keys.sign`, after the host shows a human-readable summary (operation, recipient, amount if any, payload SHA-256). What the user saw is exactly what is signed: the signed bytes are the canonical statement containing those fields. Continuous signing is per (operation, recipient), only when declared with a withdrawal place, and revocable (`revokeSigningApproval`). |
| E. Host-mediated OAuth (ATProto PDS) | The host runs the flow: PKCE S256, `state` (exact match, `iss` when present must be the declared issuer, RFC 9207), optional PAR (consent first), the system browser / Custom Tabs / ASWebAuthenticationSession via the host's `oauthAgent`. Tokens stay in the host and are returned as a session handle (sub/scope/expiresIn only). An operation may name a declared `oauth` entry (`oauth-session-not-declared` otherwise) and the host then adds `Authorization: DPoP …` and the `DPoP` proof (ES256, host-held non-extractable key). Every endpoint must sit on the declared issuer origin. |
| F. ICC vault migration | ICC's AES-GCM vault in `localStorage` migrates to non-extractable host keys. See the migration note below. |
| Allowlist | `keys.generate/open/delete/sign`, `crypto.hkdf`, `crypto.aesGcmEncrypt/Decrypt`, `crypto.wrapKey/unwrapKey`, `crypto.aesKwpWrap/Unwrap`, `crypto.x25519Derive`, `crypto.hybridEncapsulate/Decapsulate`, `crypto.generateKey`, `crypto.xchachaEncrypt/Decrypt`, `crypto.sha256`, `crypto.ed25519Sign/Verify`, `crypto.release`, `device.pick/open`, `device.command`, `oauth.authorize/refresh/release`. Anything else is refused as `not-declared`. Ed25519 receipt verification (public keys) stays guest-side via `crypto.ed25519Verify`. |

### Declaration

```json
"host-local": {
  "schema": "kotoba.host-local.v1", "app-id": "network.awai.yataverse",
  "keys": [{ "id": "device", "type": "secret-32", "use": ["hkdf"] },
           { "id": "wallet", "type": "ed25519", "use": ["sign"], "approval": "continuous",
             "operations": ["transfer"], "withdrawal": "設定 › 署名の許可" }],
  "pick": { "max-bytes": 262144, "mime-types": ["application/json"] },
  "open": { "max-bytes": 262144, "mime-types": ["application/json"] },
  "device-commands": [{ "name": "awai_local_inference", "actions": ["generate"],
                        "purpose": "端末内の AI で文章を生成するため", "special-care": true }],
  "oauth": [{ "id": "atproto-pds", "issuer": "https://pds.example",
              "authorization-endpoint": "https://pds.example/oauth/authorize",
              "token-endpoint": "https://pds.example/oauth/token",
              "client-id": "https://app.example/oauth-client-metadata.json",
              "redirect-uri": "https://app.example/oauth/callback", "scope": "atproto", "disclosure": { … } }],
  "calls": ["keys.generate", "crypto.hybridEncapsulate", "device.pick", "device.command", "oauth.authorize", …]
}
```

- `keys` are declared one by one. `secret-32` is HKDF-only; `ed25519` is `keys.sign` only (ephemeral signing keys are made by `crypto.generateKey` and sign with `crypto.ed25519Sign`). Continuous approval requires a withdrawal place.
- `pick` / `open` declare their byte caps and MIME types. `open` accepts only save-allowed types and never `application/octet-stream`.
- `device-commands` declare command name, actions, purpose and whether the input carries special-care data. `special-care: true` adds the health-information line to the confirmation.
- `oauth` declares one authorization server; every endpoint must be on its origin, with a disclosure.
- Declarations are key-exact. A network destination (`origin`, `endpoint`, `url`, `transport`) makes the descriptor invalid, as in PR 1.

### Host API

- `createClientHostLocal` gains `keyStore` (a conformant host key store, `clientKeyStoreProblems`; `createClientKeyStore` / `createIndexedDbClientKeyStore` for a plain browser), `deviceCommands` (a registry from `createClientDeviceCommands`), `oauthAgent`, `pickTarget`, `openTarget`. A descriptor that declares `keys`, `pick`, `open`, `device-commands` or `oauth` without the corresponding host piece fails closed (a `TypeError` at mount, or `not-declared` / `unavailable` at call time).
- `verifyHostStorageConformance` is unchanged. A Tauri/Android host's key store keeps keys in the platform keystore; a plain browser may keep them in the host profile (`key-custody: 'host-profile'`) only with `no-cloud-backup: 'no-os-backup'`. The fictional-keystore hole (a host claiming the keystore while keeping extractable keys) is #975, not PR 2.
- `clearAppData()` also clears the app's persistent keys and continuous signing grants (crypto-shred). `clearClientAppData({ appId, keyStore })` deletes the keys when the app is removed.

### Crypto details

- AES-GCM, HKDF-SHA256, SHA-256, Ed25519 and ES256 run on the host's WebCrypto with non-extractable `CryptoKey`s.
- ML-KEM-768 (FIPS 203), XChaCha20-Poly1305 (24-byte IV), AES-256-KWP (RFC 5649) and X25519 run in the host realm from the vendored `@noble` libraries in `CLIENT_CRYPTO_LIBRARIES` (loaded on first use). They never run in the guest.
- Hybrid combine (Yataverse `kem.cljs`): `HKDF-SHA256(no salt, x25519 || ML-KEM shared, info || eph-pub || recipient-pub || pq-ct)`. Ephemeral `x25519` and the ML-KEM shared secret are wiped.
- Key agreement output is a content key handle; a low-order X25519 peer point is refused.
- Wraps under a sealing key bind the target type in the additional data (`kotoba.key-wrap.v1`), so a wrap of one type never unwraps as another. A private key wraps only under a sealing key; a sealing, secret or signing key is never wrapped. A content key wraps only content keys.
- Every crypto input is bounded (data ≤ 16 MiB, AAD ≤ 64 KiB, labels ≤ 1024 bytes, wrapped ≤ 4 KiB, sign payload ≤ 1 MiB, one handle table per mount ≤ 4096 handles).

### Pin ledger (vendor)

`CLIENT_CRYPTO_LIBRARIES` is the ledger; names, versions, uses, integrity digests and files are there and are
asserted in the test (`crypto library ledger`). Provenance: `src/vendor/README.md` for `@noble/curves@1.9.7`
and `@noble/hashes@1.8.0`; the 2.0.1 packages (`@noble/post-quantum`, `@noble/ciphers`, `@noble/hashes`,
`@noble/curves` 2.0.1 NTT-only) are MIT-licensed (see each `LICENSE`), verbatim but for import paths, with the
package `integrity` digests recorded in `CLIENT_CRYPTO_LIBRARIES`. Re-vendor by copying the same file lists and
re-applying only the import-path edits.

## 2. Threat model

Assets: device secrets and signing keys, content and sealing keys, the user's stored data (possibly
要配慮個人情報), OAuth tokens and the DPoP proof key, the bytes passed to on-device AI, and the host tab's
availability. Adversaries: a compromised or malicious guest (any script in the sandboxed frame), another app on
the same host, a remote party reached by a declared operation or an OAuth provider, and someone with a copy of
the host's storage files. Trusted: the host shell, its registry and pins, its key store, its device commands,
its `oauthAgent`, and its browser/open targets.

| # | Threat | Control | Test |
|---|---|---|---|
| P1 | A guest extracts a key (device secret, private key, sealing key) | Keys live in a host-memory table as non-extractable `CryptoKey`s (WebCrypto) or byte arrays held only in the host realm (vendored noble). No call returns bytes for a key: every derive/unwrap/decapsulate returns a handle. The runtime exports no test-only function (`peekKeyForTest` lives in the harness, which knows the raw secret only because it minted it). An extractable key from a host store is refused as `unavailable`. | key handles stay in the host; extractable host key is refused; no test-only export; Yataverse K1 |
| P2 | A handle from another app (or another mount) names a key | Handles are random strings in a per-mount, per-app table. A foreign handle is `invalid-key`, never another app's key. The table is wiped on close. | cross-app handles and key agreement; Yataverse A2, K2 |
| P3 | A disallowed algorithm is used | The allowlist is per-call with exact argument shapes. `crypto.generateKey` rejects anything outside `aes-256-gcm` / `xchacha20-poly1305` / `x25519` / `ml-kem-768` / `ed25519`; `crypto.hkdf` accepts only 32-byte output as a sealing key or another secret. | primitives and bounds |
| P4 | An input exhausts memory or the table | Every input is bounded: data ≤ 16 MiB, AAD ≤ 64 KiB, labels ≤ 1024, wrapped ≤ 4 KiB, sign payload ≤ 1 MiB, 4096 handles per mount, 4 concurrent device commands. Oversize is `too-large` before anything runs. | primitives and bounds; device.command |
| P5 | Key material reaches logs, telemetry or crash reports (Legal L2) | The runtime has no console call. Errors are fixed codes that never carry a key, file name or content. Device-command inputs/outputs and OAuth tokens are never logged. `verifyDeviceCommandConformance` fails a command that logs. | key handles stay in the host; device.command; no test-only export |
| P6 | A pick/open runs without the user, or sends something | Each call runs only after the canonical trusted prompt (trusted press, 600 ms arm, equal buttons), with the effect inside that click. `pick` returns only the chosen file; `open` opens a declared save-type in the default app. Neither uses the network; the runtime records no request. | device.pick; device.open |
| P7 | A device-local command leaves the device or calls something undeclared | Only declared + registered commands run. Registration refuses a command whose attestation admits network I/O (`command-does-network-io`) or logging. `verifyDeviceCommandConformance` runs probes with network/console trapped and fails one that touches either. A call's input and output are schema-checked before and after, and neither is logged. | device.command refuses … |
| P8 | A device-local call passes user data to the AI without the user knowing | A call whose input carries user data shows Legal's short confirmation each time (fixed line, purpose, special-care line, stop line, one-time). Enum/integer/boolean-only actions carry no user data and run without it. | device.command dialog wording matches Legal |
| P9 | A signature is made of something the user never saw | The host builds and shows the statement (operation, recipient, amount, payload SHA-256); the signed bytes are that statement. Signing an undeclared operation is `not-declared`; a short or missing summary is `invalid-arguments`, before any dialog. | keys.sign shows the summary |
| P10 | Continuous signing is granted silently, or cannot be stopped | Continuous approval exists only when declared with a withdrawal place, covers only the same (operation, recipient) with no amount, and is revocable from the host (`revokeSigningApproval`, `signingApprovals`). | continuous signing is declared, scoped and revocable |
| P11 | An OAuth flow reaches an undeclared origin, or tokens leak to the guest | Every endpoint must be on the declared issuer origin (`oauth-endpoint-not-on-declared-origin`). Tokens stay host-side; the guest receives only a session handle with sub/scope/expiresIn. The DPoP proof key is a non-extractable host key; the `DPoP` and `Authorization` headers are added by the host only to declared `oauth` operations. | oauth.authorize …; oauth refuses … |
| P12 | CSRF or mix-up in the OAuth redirect | `state` must match exactly; `iss`, when present, must be the declared issuer (RFC 9207). A redirect off the declared URI is `invalid-arguments`. The flow never starts without the trusted consent (the system browser opens inside the Allow click; PAR runs after the same approval). | oauth refuses … |
| P13 | PKCE is missing, so a code can be intercepted | `code_challenge` (S256) and `state` are in the authorize URL; `code_verifier` is in the token request. The verifier never reaches the guest. | oauth.authorize … (authorize URL and token body) |
| P14 | Data survives in backups, or keys survive app removal (Legal L1, L3, L4) | The key store is declared per host (platform keystore for Tauri/Android; host profile only with no OS backup). `clearAppData` crypto-shreds persistent keys and grants; `clearClientAppData` deletes the keys with the app. | erase everything; sealing key wrap round trip (clearAppData) |
| P15 | A wrap is opened as a different key type | Sealing-key wraps bind the target type in the additional data. A content key (guest-chosen peer, so it may know the value) never wraps a private key. | sealing key wrap round trip |

Migration notes:

- ICC's vault (AES-GCM in `localStorage`) becomes a host-local `vault` store encrypted at rest under a
  non-extractable host key (PR 1). With PR 2 the vault's wrapping secret becomes a `secret-32` handle: the app
  calls `keys.generate` (or migrates an existing value with the host-only `crypto.importKey`), derives the
  sealing key with `crypto.hkdf`, and `crypto.wrapKey` / `crypto.unwrapKey` the private keys. The guest never
  holds the secret, so no backup or log carries it. `crypto.importKey` is host-document-only (`handle.call`);
  the guest cannot import a key it chose.
- karute's `awai_local_inference` (actions `info` / `open` / `generate`; prompt ≤ 8192 bytes; `maxTokens`
  1..256; output text ≤ 65536 bytes; text-only modality) registers as a device command with those schemas and
  the Legal short confirmation. Model downloads are a separate egress operation, never a device command
  (a command with `network: 'none'`).

Residual risks and limits:

- The combiner matches Yataverse's `kem.cljs` by design (see Crypto details). They are independent
  implementations of the same combine; there is no cross-implementation test here (the Yataverse acceptance
  suite only checks the round trip inside one runtime). A mismatch would fail only between implementations.
- A host that lies about its native device command (a Tauri `invoke` that does network I/O) is invisible to the
  conformance probe traps; its attestation is the host's own evidence (`native: 'not-observed'`).
- The `oauthAgent` (system browser) is host code; the runtime checks the redirect URI, `state` and `iss`, but
  it cannot see what the browser shows.
- `CLIENT_CONSENT_TEXT` was confirmed by Legal (reports/kotoba-974-pr2-consent-wording.md, 2026-11-22) for
  device-local, pick, open and sign in both locales; the link payload line is outside that confirmation and
  remains with Legal.

## 3. Verification (2026-11-22, Node 26.0.0)

- `test/verify-client-keys-20261122.mjs`: 17 sections. With
  `KOTOBA_NEGATIVE_CONTROL=1 KOTOBA_CLIENT_RUNTIME=<main 715b8e5f5 file>` 16 of 17 fail (all but the
  no-test-only-export guard, which is a hygiene invariant: it passes on both copies, like PR 1 T14). With this
  change all 17 pass. The sections are key handles stay in the host, extractable host key is refused, cross-app
  handles and key agreement, primitives and bounds, sealing key wrap round trip, erase everything, device.pick,
  device.open, device.command runs …, device.command refuses …, device.command dialog wording matches Legal,
  keys.sign shows the summary, continuous signing is declared scoped and revocable, oauth.authorize …, oauth
  refuses …, no test-only export, crypto library ledger.
- Yataverse's `yataverse-acceptance.test.mjs` with `KOTOBA_HARNESS=test/client-runtime-host-local-harness.mjs`
  passes A1–A9, B1–B5, C1 and K1–K3 (19 runtime tests; the app layer P1–P4, C2 is not run here).
- All other `test/verify-client-*.mjs` pass unchanged.
