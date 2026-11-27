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
| nagare | Bodies by reference: `request-body: 'host-local'` sends stored values (an ordered key list) and `response-body: 'host-local'` writes the response into storage, up to 1 GiB (`CLIENT_REFERENCE_BODY_MAX`). The bytes stay in the host. |
| Migration | A trusted-page-v1 app may declare `host-local` too, and its host-document code calls `handle.call(call, args)`. Its last trusted-page release copies its IndexedDB data in before it moves to restricted-wasm-v1. |
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
  "links": { "max-url-length": 2048, "targets": [
    { "origin": "https://www.wikidata.org", "path": "/wiki/:item",
      "path-params": { "item": { "charset": "alnum", "min-length": 2, "max-length": 16 } },
      "query-params": { "uselang": { "enum": ["ja", "en"] } } } ] }
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
- Storage backends: `createIndexedDbClientStorageBackend({ conformance, keyProvider })` (IndexedDB) and
  `createEncryptedClientStorageBackend({ kv, conformance, keyProvider })` (any host key-value store). The host must
  supply `conformance`, its attested declaration; there is no default. Also `clientStorageBackendProblems` and
  `verifyHostStorageConformance`.
- `createClientOperationBroker({ …, hostLocal })` links a broker to the app's storage for bodies by reference.
- Caps for app sizing:
  - per value, and per call for a body over the bridge: 16 MiB (`CLIENT_PORT_BYTES_MAX`);
  - one storage call, including a batch: 64 MiB of byte arrays, counted before the call is queued;
  - a body by reference: 1 GiB.

### Storage semantics

- Keys are relative paths: 1–1024 characters, with no control, bidi or zero-width character, no backslash, no
  leading slash, and no empty, `.` or `..` segment. Stores are declared names.
- `get` returns `{ value, size, version }`, optionally `offset`/`length`. `put` returns `{ size, version }`, and
  `ifVersion` is a compare-and-swap (Bunsho; `0` means absent). `ifAbsent` gives `key-exists`.
- `batch` (≤1000 ops of `put`, `delete`, `move`, ≤64 MiB of values, moved values included) is all or nothing. Every
  op is checked and the quota is planned before anything is written. The backend then checks every expected version,
  assigns versions and writes, all in one transaction.
- Every mount of an app in one document shares one storage core (cache and queue). Compare-and-swap is decided inside
  the backend's transaction, so a stale cache in another tab cannot overwrite a newer value.
- `list` pages up to 1000 entries with a cursor. `watch` delivers `{ event: 'storage.changed', store, keys }` to
  this app's mounts and the host's other tabs (BroadcastChannel in the host origin), and never a value.
- Larger logical values (Kumade's models, 235.6 MiB in total; nagare's videos up to 512 MiB) are stored as chunks
  under one prefix and committed in one `batch`. The per-value cap stays 16 MiB. A range read is
  `storage.get({ offset, length })` on a chunk, so a guest never holds a whole video. The host reads at most one
  chunk (≤16 MiB) per call.
- A response written to storage is stored as chunks of `max-value-bytes` under `<key>/000000`, … and then a manifest
  at `<key>` (`kotoba.host-local.stored-body.v1`: bytes, chunks, sha256, content-type). The manifest is the commit
  marker. When the transfer fails, the chunks written so far are deleted.
- Errors are fixed codes: `not-declared`, `invalid-key`, `invalid-arguments`, `not-found`, `key-exists`,
  `version-conflict`, `too-large`, `quota-exceeded`, `busy`, `unavailable`, `not-approved`.

## 2. Threat model

Assets: the user's stored data (possibly 要配慮個人情報), the per-app storage key, the content of saved files and
URLs, and the host tab's availability. Adversaries: a compromised or malicious guest (any script in the sandboxed
frame), another app on the same host, a remote party reached by a declared operation, and someone with a copy of the
host's storage files. Trusted: the host shell, its registry and pins, and its backend and targets.

| # | Threat | Control | Test |
|---|---|---|---|
| T1 | A guest reads another app's data or lists its keys | The partition is the host's `appId`, checked against the signed declaration. The guest never names it, so keys are relative and `../` is refused. A stored body by reference reads and writes the app's own partition only. Records are AES-GCM, with the partition and index as additional data, so a record copied into another partition does not decrypt. | cross-app read; Yataverse A2 (storage part), A2b |
| T2 | Data leaves the device through the storage calls | The calls do not use fetch or any network API. The declaration cannot name a destination. Host-local stays out of `connect-src`. Anything that leaves the device is still an operation with each-operation consent. | no egress through storage; Yataverse A1, A3 |
| T3 | The per-app keys are extracted | An AES-GCM key and an HMAC key per app, both `extractable: false`, created in the host realm or supplied by the host's `keyProvider` (the platform keystore). An extractable key from a provider is refused. The guest never receives either. | keys and logs; host conformance; Chromium probe |
| T3a (KOTOBA-975, 2026-11-25) | A web host passes a `keyProvider` and declares `no-cloud-backup: true`, posing as a platform-keystore host | `verifyHostStorageConformance` runs the factory backend's `keyCustodyProbe`: both keys must reject `exportKey` (non-extractable), reported as `key-custody` `verified: true`. The probe proves non-extractability only; that the provider really sources keys from the platform keystore stays the host's attested duty (see `host-local-storage.md` §2). | host conformance |
| T4 | A disk copy or a cloud backup reveals data or file names (Legal L1, L3) | Values are AES-GCM-256, padded to 4 KiB buckets. Names, sizes and times are in an encrypted meta record filed under an HMAC of the name. Clearing deletes the keys too (crypto-shred). A key kept in the host profile next to the data is accepted only from a host that declares `no-cloud-backup: 'no-os-backup'` (a plain browser). A Tauri or Android host, whose data directory an OS can back up, must pass a platform-keystore `keyProvider` (`key-custody-requires-platform-keystore`), so a backup never holds ciphertext and key together. In a plain browser the key still lives in the same profile; that protects copies of the store files, not a reader with the whole profile and the browser. | keys and logs; host conformance; Chromium probe |
| T5 | Stored data reaches logs, telemetry or crash reports (Legal L2) | The runtime has no console call. Errors are fixed codes. A backend error message (which may hold data) is replaced by `unavailable`. | keys and logs; Yataverse A6 |
| T6 | Data survives in OS cloud backup, or after app removal (Legal L1, L4) | Each host attests the MUSTs in its backend's declaration, which has no default. A host that does not declare them gets no storage. `verifyHostStorageConformance` checks isolation, round trip, versions and compare-and-swap, atomic batch and clear. It reports the platform MUSTs (`no-cloud-backup`, `key-custody`, `removed-with-app`, `no-logging`) as `verified: false`, for the host's own evidence. A plain browser declares `no-os-backup`. The host shell must call `clearClientAppData` when the user removes the app. | host conformance; clear app data |
| T7 | A guest exhausts memory or storage | Quota, entries and value caps per app. 16 pending calls, a call's byte arrays counted (≤64 MiB) before it is queued, and at most 128 MiB held by the queued calls of one app together. Batch limits count moved values too. A 16 MiB cap per body over the bridge. Each binary operation reserves its declared request + response bytes against a 32 MiB in-flight budget per broker, and a body by reference against a 1 GiB budget, before any body is read. The R3 slot still guards snapshot and consent. | size caps; binary bodies (R3); review 1372; stored bodies |
| T15 | Lost updates between two mounts or tabs of one app | One storage core per (backend, app) in a document. Expected versions are checked and versions assigned inside the backend transaction. A conflict drops the stale cache. | review 1372; host conformance (compare-and-swap, atomic) |
| T16 | A body by reference sends or stores more than approved, exhausts memory before consent, or fails after consent | Before consent only stored sizes and versions are read. Nothing is decrypted, and the total is checked against `max-request-bytes`. The upload path is chosen then too. It streams (`duplex: 'half'`) only when the host attests `uploadStreams` and the engine passes feature detection. Otherwise it buffers in the host, up to `CLIENT_UPLOAD_BUFFER_MAX` (256 MiB). A declared body that neither path can send is refused before the dialog. The dialog shows store, count, size and path. After consent each value is read and compared with its approved version. A value changed after approval stops the request. A response written to storage is capped while it streams, cancelled past the limit, and its partial chunks deleted. | stored bodies |
| T8 | An oversize response fills memory | A declared Content-Length over the limit is refused before reading. Otherwise the body is read up to the limit and the stream is cancelled. | size caps; Yataverse B4 |
| T9 | An oversize or unexpected request body is shown or sent | The body is read up to `max-request-bytes` before consent and refused above it, so nothing is fetched. A declared content type is enforced. The dialog shows size, type and SHA-256, never the bytes. | size caps; Yataverse B1, B2 |
| T10 | A guest saves a file that runs or escapes the folder | Only a fixed type allowlist (no HTML, SVG, XML, scripts or executables). `application/octet-stream` is allowed only with declared extensions outside an unsafe list. The name is reduced to its last segment, stripped of control and bidi characters, and its extension matched to the type. Windows device names are prefixed. | device.save |
| T11 | A save or link happens without the user | The host prompt is the canonical consent dialog: a trusted press after the 600 ms arm, with equal buttons. The effect runs inside that click. A synthetic, early or denied press does nothing. | device.save; device.openLink; Chromium probe |
| T12 | A link carries data off the device | Treated as egress. Only https, no credentials and a length cap. The URL must match a declared target: a fixed URL, or a template whose every path and query parameter is an enum or a constrained charset. An undeclared query parameter, free text or a fragment is refused. This is Legal's condition (2026-11-22) for opening a link without a full disclosure: a real click, and only public or fixed data. An app that puts user data in a URL declares a normal egress operation with a disclosure. The prompt names the origin and says that the IP address and the URL reach the site; the whole URL is in 詳細. The URL opens with `noopener,noreferrer`. | device.openLink |
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
  counts so they are read again, but a race between the two tabs can briefly exceed the quota by one write. Versions
  are exact, because they are checked in the backend.
- At rest, the record count, each record's version, its 4 KiB size bucket and the partition (the app id) are visible.
  Names, exact sizes and times are not.
- Streaming a stored request body needs an engine that streams uploads (Chromium, over HTTP/2 or later; not
  WebKit) and a host that attests it with `uploadStreams`. Other hosts buffer up to 256 MiB, which holds the whole
  body in host memory after consent. A larger declared body needs a streaming host or a native request path
  (KOTOBA-971).
- Follow-ups (Yataverse review, Low): the quota counts value bytes and names, not the 4 KiB padding or the meta
  records actually stored; `handle.call` is meant only for the app's own last trusted-page release.
- The guest can use storage without consent, so the app's own descriptor and review decide what it keeps. The runtime
  limits where data goes, not what an app chooses to store.
- `device.openLink` cannot see what the destination does with the URL. Legal (2026-11-22) accepts the origin plus the
  full URL as its disclosure, given a real click and a URL made only of declared, constrained parts.
- The new dialog strings (byte limits, save and link prompts, one-time line) were confirmed by Legal on 2026-11-22, with
  the save and link notices reworded. `CLIENT_CONSENT_TEXT` as a whole keeps its draft status for the earlier wording.

## 3. Verification (2026-11-22, Node 26.0.0, Google Chrome 158.0.8127.37)

- `test/verify-client-host-local-20261122.mjs`: 14 sections. With
  `KOTOBA_NEGATIVE_CONTROL=1 KOTOBA_CLIENT_RUNTIME=<main e58ae70b4 file>` all 14 fail. With this change all 14 pass.
  The sections are cross-app read, no egress through storage, size caps, binary bodies, host conformance, keys and
  logs, clear app data, batch/versions/watch, device.save, device.openLink, review 1372 (shared core, compare-and-swap in the backend, moved bytes, pre-queue size), stored bodies, route templates and undeclared calls.
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
