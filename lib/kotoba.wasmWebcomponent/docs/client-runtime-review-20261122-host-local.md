# kotoba-client-runtime.js: host-local calls and declared bodies, with threat model (KOTOBA-968, 2026-11-22)

Author: Claude (claude-opus-5-5) in Claude Code, an Orca worker for the Dev coordinator. This document records a
design and its threat model, written by an AI model. It is not a human security audit, not a legal opinion and
not a product qualification. Tracking: KOTOBA-968 (child of KOTOBA-159).

Base: kotoba-lang/kotoba main `e58ae70b4`, runtime sha256 `37e82633…2d6d`. The new sha256 is in
`local-changes.json`.

This is the first of two pull requests. It lets restricted-wasm-v1 apps (Yataverse, Awai Drive and Itonami's
eight apps) move off trusted-page-v1 for storage, binary HTTP, files and links. The second pull request adds key
handles, crypto (AES-GCM, HKDF, X25519, ML-KEM-768 hybrid, XChaCha20-Poly1305, AES-256-KWP), `device.pick` and
`device.open`, and declared device-local host commands (karute `awai_local_inference`). Until then those
calls are accepted in a declaration and refused as `not-declared` when called.

Inputs: the Yataverse spec and acceptance tests (`runtime-gaps.md`, `yataverse-acceptance.test.mjs`, 2026-11-22),
Itonami's blockers and host-needs table (B1–B4), Legal's four host-local conditions and its one-time wording
decision (2026-11-22).

## 1. What changes

| Gap | Change |
|---|---|
| B1/G2 binary HTTP | An HTTP operation may declare `request-body` and `response-body` (`bytes` or `text`), each with `max-request-bytes` / `max-response-bytes` (at most 16 MiB). It may also declare `content-type` (the only request type accepted; a body without one is sent as it) and `timeout-ms` (body deadline, at most 120 s). |
| B2/G1 storage | A descriptor may declare `host-local` (schema `kotoba.host-local.v1`, `app-id`, `storage`, `stores`, `calls`). Guest protocol `kotoba.client.local.v1`: `storage.get/put/delete/list/clear/batch/usage/watch`. No consent; nothing leaves the device. |
| B3 files | `device.save` hands bytes, a name and a type to the host's save prompt. |
| B4 links | `device.openLink` opens a declared https origin in the system browser. |
| Route templates | A path parameter may be constrained (`path-params`: `enum`, or `charset` with `min-length` and `max-length` up to 128). A parameter-only path is accepted only when every parameter is constrained, and finding 7 refuses the rest as before. The dialog shows the resolved path. |
| Legal | For a `one-time` operation the dialog says 『この許可は今回の 1 回だけです。保存しません。』 instead of the withdrawal line. `withdrawal` is required only for `continuous`. |

### Declaration

```json
"host-local": {
  "schema": "kotoba.host-local.v1", "app-id": "network.awai.yataverse",
  "storage": { "class": "device-only", "backup": "excluded", "at-rest": "encrypted", "erasable": true,
               "quota-bytes": 2147483648, "max-entries": 100000, "max-value-bytes": 16777216 },
  "stores": ["files", "vault", "staging"],
  "calls": ["storage.get", "storage.put", "storage.batch", "storage.list", "storage.clear", "device.save", "device.openLink"],
  "save": { "max-bytes": 262144, "mime-types": ["application/json", "application/octet-stream"], "octet-stream-extensions": ["bs1", "bs2", "bs3"] },
  "links": { "origins": ["https://www.wikidata.org"], "max-url-length": 2048 }
}
```

- `host-local` is accepted only with `profile: restricted-wasm-v1`. Every key is exact: an `origin`, `endpoint`, `url` or
  `transport` makes the descriptor invalid. Calls are named one by one; `crypto.*` is not accepted.
- `storage` must be exactly `device-only`, `excluded`, `encrypted`, `erasable: true` (Legal L1, L3, L4).
- Global caps (proposed): 16 MiB for one body, value or file (`CLIENT_PORT_BYTES_MAX`; packs are up to 12 MiB);
  4 GiB quota per app (`CLIENT_STORAGE_QUOTA_MAX`); 1,000,000 entries; URL 2048 characters. A declaration over
  a cap is `limit-over-global-cap` / `bytes-limit-over-global-cap`.

### Host API

- `verifySignedClientDescriptor` now records its result as admitted. `createClientHostLocal({ admitted, appId,
  storage, consentHost, saveTarget, linkTarget, app })` requires such a result. `appId` is the host's own id for the
  app (its registry entry or Tauri identifier) and must equal `host-local.app-id`. It is the storage partition.
- `mountRestrictedClientApp({ …, hostLocal })` accepts only a handle from `createClientHostLocal` for the same
  descriptor as the broker.
- `clearAppData()` on the handle, and `clearClientAppData({ appId, storage })` when the app is removed.
- Storage backends: `createIndexedDbClientStorageBackend()` (browser), `createEncryptedClientStorageBackend({ kv,
  conformance })` (any host key-value store), `clientStorageBackendProblems`, `verifyHostStorageConformance`.

### Storage semantics

- Keys are relative paths: 1–1024 characters, with no control, bidi or zero-width character, no backslash, no
  leading slash, and no empty, `.` or `..` segment. Stores are declared names.
- `get` returns `{ value, size, version }`, optionally `offset`/`length`. `put` returns `{ size, version }`, and
  `ifVersion` is a compare-and-swap (Bunsho; `0` means absent). `ifAbsent` gives `key-exists`.
- `batch` (≤1000 ops of `put`, `delete`, `move`, ≤64 MiB of values) is all or nothing: every op is checked and the
  quota is planned before anything is written, and the backend writes in one transaction.
- `list` pages up to 1000 entries with a cursor. `watch` delivers `{ event: 'storage.changed', store, keys }` to
  this app's mounts and the host's other tabs (BroadcastChannel in the host origin), and never a value.
- Larger logical values (Kumade's models, 235.6 MiB in total; nagare's videos up to 512 MiB) are stored as chunks
  under one prefix and committed in one `batch`. The per-value cap stays 16 MiB. A range read is
  `storage.get({ offset, length })` on a chunk, so a guest never holds a whole video. The host reads at most one
  chunk (≤16 MiB) per call.
- Errors are fixed codes: `not-declared`, `invalid-key`, `invalid-arguments`, `not-found`, `key-exists`,
  `version-conflict`, `too-large`, `quota-exceeded`, `busy`, `unavailable`, `not-approved`.

## 2. Threat model

Assets: the user's stored data (possibly 要配慮個人情報), the per-app storage key, the content of saved files and
URLs, and the host tab's availability. Adversaries: a compromised or malicious guest (any script in the sandboxed
frame), another app on the same host, a remote party reached by a declared operation, and someone with a copy of the
host's storage files. Trusted: the host shell, its registry and pins, and its backend and targets.

| # | Threat | Control | Test |
|---|---|---|---|
| T1 | A guest reads another app's data or lists its keys | The partition is the host's `appId`, checked against the signed declaration. The guest never names it, so keys are relative and `../` is refused. Records are AES-GCM with the partition and key as additional data, so a record copied into another partition does not decrypt. | cross-app read; Yataverse A2 (storage part), A2b |
| T2 | Data leaves the device through the storage calls | The calls do not use fetch or any network API. The declaration cannot name a destination. Host-local stays out of `connect-src`. Anything that leaves the device is still an operation with each-operation consent. | no egress through storage; Yataverse A1, A3 |
| T3 | The per-app key is extracted | It is generated in the host realm with `extractable: false` and stored as a CryptoKey. The guest never receives it. | keys and logs (exportKey refused); Chromium probe |
| T4 | A disk copy of the host profile reveals data (Legal L3) | AES-GCM-256 at rest. Clearing deletes the key too (crypto-shred). Limit: in a browser the key lives in the same profile as the ciphertext, so this protects copies of the store files, not a reader with the whole profile and the browser. Tauri and Android hosts should wrap it with the Keystore or Keychain. | keys and logs (no plaintext at rest); Chromium probe |
| T5 | Stored data reaches logs, telemetry or crash reports (Legal L2) | The runtime has no console call. Errors are fixed codes. A backend error message (which may hold data) is replaced by `unavailable`. | keys and logs; Yataverse A6 |
| T6 | Data survives in OS cloud backup, or after app removal (Legal L1, L4) | Declared as MUSTs by each host backend (`clientStorageBackendProblems`), and a host that does not declare them gets no storage. `verifyHostStorageConformance` checks isolation, round trip, versions, batch and clear, and reports the platform MUSTs as `verified: false` for the host's own evidence. The browser host relies on browsers not backing site data up to an OS cloud. The host shell must call `clearClientAppData` when the user removes the app. | host conformance; clear app data |
| T7 | A guest exhausts memory or storage | Quota, entries and value caps per app, 16 pending calls, batch limits, a 16 MiB body cap. Each binary operation reserves its declared request + response bytes against a 32 MiB in-flight budget per broker before any body is read. The R3 slot still guards snapshot and consent. | size caps; binary bodies (R3) |
| T8 | An oversize response fills memory | A declared Content-Length over the limit is refused before reading. Otherwise the body is read up to the limit and the stream is cancelled. | size caps; Yataverse B4 |
| T9 | An oversize or unexpected request body is shown or sent | The body is read up to `max-request-bytes` before consent and refused above it, so nothing is fetched. A declared content type is enforced. The dialog shows size, type and SHA-256, never the bytes. | size caps; Yataverse B1, B2 |
| T10 | A guest saves a file that runs or escapes the folder | Only a fixed type allowlist (no HTML, SVG, XML, scripts or executables). `application/octet-stream` is allowed only with declared extensions outside an unsafe list. The name is reduced to its last segment, stripped of control and bidi characters, and its extension matched to the type. Windows device names are prefixed. | device.save |
| T11 | A save or link happens without the user | The host prompt is the canonical consent dialog: a trusted press after the 600 ms arm, with equal buttons. The effect runs inside that click. A synthetic, early or denied press does nothing. | device.save; device.openLink; Chromium probe |
| T12 | A link carries data off the device | Treated as egress. Only https, only declared public origins, no credentials, a length cap. The prompt names the origin and shows the whole URL in 詳細. The URL opens with `noopener,noreferrer`. | device.openLink |
| T13 | Change notices leak data across apps | Notices carry store and key names only, to the same app id: in the document, or over BroadcastChannel in the host origin. | batch, versions, watch |
| T14 | A test hook exposes keys in production | The runtime exports no test-only function. The harness lives in `test/` only. | keys and logs (no test/peek/debug export) |

Migration notes:

- Secrets kept in guest storage today (cloud-itonami-app's pairing token in localStorage; ICC's AES-GCM vault) move
  into host-local storage, which is encrypted at rest under a non-extractable host key. Once PR 2 lands, a
  signing or wrapping secret should become a host key handle instead, so the guest never holds it.
- App Build's survey (2026-11-22) says rodo's `GET /:topic/json` is refused as `generic-network-endpoint`. The code
  disagrees: main `e58ae70b4` accepts `/:topic/json`, in both the single and the routes form, because `json` is a
  fixed segment. Only a parameter-only path such as `/:topic` is refused. Constraining `topic` with `path-params`
  is still recommended.

Residual risks and limits:

- In the browser, two tabs of one app keep separate quota counts. A change notice from the other tab drops the cached
  counts so they are read again, but a race between the two tabs can briefly exceed the quota by one write.
- Key names and value sizes are not encrypted. The record stores its length, version and time in the clear.
- The guest can use storage without consent, so the app's own descriptor and review decide what it keeps. The runtime
  limits where data goes, not what an app chooses to store.
- `device.openLink` cannot see what the destination does with the URL. Its disclosure is the origin and URL only, not
  a finding-9 disclosure. Legal to confirm whether that is enough.
- The new dialog strings (byte limits, save and link prompts, one-time line) are Dev drafts in `CLIENT_CONSENT_TEXT`,
  marked draft like the rest. Legal finalizes them.

## 3. Verification (2026-11-22, Node 26.0.0, Google Chrome 158.0.8127.37)

- `test/verify-client-host-local-20261122.mjs`: 12 sections. With
  `KOTOBA_NEGATIVE_CONTROL=1 KOTOBA_CLIENT_RUNTIME=<main e58ae70b4 file>` all 12 fail. With this change all 12 pass.
  The sections are cross-app read, no egress through storage, size caps, binary bodies, host conformance, keys and
  logs, clear app data, batch/versions/watch, device.save, device.openLink, route templates and undeclared calls.
- `test/verify-client-review-20261122.mjs`: the finding 9 and finding 1 sections now assert the one-time wording, the
  continuous withdrawal line in both profiles, and that `withdrawal` is optional for one-time only.
- All other `test/verify-client-*.mjs` pass unchanged. `verify-client-fetch-cancel.mjs` passes with a synthetic
  certificate (PROBE_TLS_DIR).
- `test/browser/verify-host-local-browser.mjs` (Chromium) passed:
  - the sandboxed guest has no IndexedDB or localStorage (SecurityError);
  - values persist across a reload through the host;
  - IndexedDB holds no plaintext, and its only key is a non-extractable AES-GCM key;
  - the conformance helper passes;
  - `device.save` downloads nothing before the click, and after a trusted click downloads `probe.json` from `../../probe.json`.
- `test/browser/verify-artifact-stream.mjs`: 14 of 14 checks pass.
- Yataverse's `yataverse-acceptance.test.mjs` with `KOTOBA_HARNESS=test/client-runtime-host-local-harness.mjs`
  (its fixture disclosure replaced by the runtime's schema) passed A1, A2b, A3–A6, A8, A9, B1–B5 and C1. It failed
  A2 and A7 at `keys.generate`, and K1–K3 (crypto); those are PR 2. The app layer (P1–P4, C2) was not run here.
