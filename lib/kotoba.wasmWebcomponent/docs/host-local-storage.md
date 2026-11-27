# Host-local storage: what the runtime checks, what the host attests

Tracking: KOTOBA-972 (Tauri Android), KOTOBA-973 (Tauri macOS/iOS),
KOTOBA-975 (web hosts). Design and threat model:
`client-runtime-review-20261122-host-local.md` (T1–T16). Legal's four
conditions (memo `kotoba-159-consent-dialog.md`): L1 excluded from OS cloud
backup, L2 never in logs/telemetry/crash, L3 encrypted at rest with keys in
the platform keystore, L4 user-deletable and removed with the app.

## 1. What verifyHostStorageConformance proves (verified: true)

For every backend it checks partition isolation, round trip, versions and
compare-and-swap inside the backend, all-or-nothing batch, and clear.

For a backend from `createEncryptedClientStorageBackend` /
`createIndexedDbClientStorageBackend` it also runs `keyCustodyProbe`:
a throwaway partition is created exactly as storage creates it, and both
keys (AES-GCM encryption, HMAC index) must reject `exportKey` — the
`key-custody` case, `verified: true`. An extractable-key provider fails
the report (`conformant: false`). The probe runs in the host realm, is
never handed to the guest, and only returns a boolean; no key material or
ciphertext leaves it. Results: `evidence/host-storage-conformance-20261125.json`.

## 2. What the runtime cannot prove (host's attested duty)

The probe proves **non-extractability**, not **platform custody**: a
`keyProvider` that returns locally generated non-extractable keys passes
the probe without ever touching a keystore. A passing report is therefore
not proof of L1/L3. Each host attaches its own platform evidence:

| Host | Declaration | Platform evidence the host must show |
|---|---|---|
| Plain browser (incl. GitHub/Cloudflare Pages) | `no-cloud-backup: 'no-os-backup'`, keys kept in the profile (`host-profile`) — browsers do not back site data up to an OS cloud | IndexedDB readback: keys stored with `extractable: false`; values and names are ciphertext on disk; clear-site-data path removes them |
| Tauri Android / Android WebView | `no-cloud-backup: true` **only with** a platform-keystore `keyProvider` | Merged manifest / `dumpsys` showing `allowBackup="false"` plus `dataExtractionRules` (or store outside backup roots, e.g. `noBackupFilesDir`); keys from Android Keystore, non-exportable, StrongBox where available; no `Log`/logcat of store values; app-sandbox storage removed with the app |
| Tauri macOS/iOS | `no-cloud-backup: true` **only with** a platform-keystore `keyProvider` | Keychain attribute readback: `kSecAttrSynchronizable=false` and ThisDeviceOnly accessibility; files with `isExcludedFromBackup`; no `os_log` of values; data in the app container, removed with the app |

Also required on every host: L2 — no secret, stored value, stored file
name or device-local command input/output in log, telemetry, crash report
or console (the runtime itself writes no console output; host code must
not either). L4 — the host shell calls `clearAppData()` /
`clearClientAppData()` from its settings and when the app is removed.

Negative controls (all covered by `test/verify-client-host-local-20261122.mjs`):
no declaration → `missing-conformance-declaration`; `no-cloud-backup: true`
on the web without a keyProvider → `key-custody-requires-platform-keystore`;
an extractable-key `keyProvider` → `conformant: false`; an Android manifest
with `allowBackup="true"` fails the host's own Android check (that check
lives in the app host, e.g. itonami-lib's manifest script, not here).

## 3. device.save / device.openLink need no storage conformance

`createClientHostLocal` gates storage calls on a conformant backend only
when the descriptor declares `host-local.storage`. `device.save` and
`device.openLink` store nothing at rest: they require only the admitted
(signed) descriptor, the canonical trusted consent host for the prompt,
and the host's save/open targets. A descriptor that declares `save` /
`links` but no `storage` mounts fine (`save and link without storage
conformance` section in the host-local test).

A custom (non-Tauri) Java WebView host must implement, in the host realm:

1. Verify the descriptor (`verifySignedClientDescriptor`) with the
   host-pinned publisher key; admit it to `createClientHostLocal` with
   the host's own app id (its registry entry or app identifier), which
   must equal the declared `host-local.app-id`.
2. Show the canonical consent prompt on a real user gesture: a trusted
   press after the 600 ms arm; synthetic, early or denied presses save or
   open nothing. The effect runs inside that click.
3. Provide the save target: write the approved bytes (name already
   reduced to a safe last segment, type allowlisted) to the platform save
   dialog / file sink. The target must not log the bytes or the file name.
4. Provide the link target: open the approved URL in the system browser
   with `noopener,noreferrer`. Only declared, constrained https targets
   reach it; the guest cannot widen the set.

Keys are never handed to the guest: the guest holds only per-app handles;
derive/unwrap/decapsulate results come back as handles, never as bytes.
