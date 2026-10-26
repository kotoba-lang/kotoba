# ADR-0113 — `auth.kotoba.cloud` authorizes the account; the node proves its own key

Accepted for the hosted Kotoba Browser adapter on 2026-08-29. This decision
implements the AIUEOS side of the device authorization contract. It does not
claim the production authority is deployed, a real Passkey ceremony has run,
or the physical K16 has completed the flow.

## Context

AIUEOS needs two user experiences — continue with a Passkey on the current
screen or scan with a phone — without creating two identity systems. The OS
must add a device to an account, but must never receive or copy the account's
Passkey private key. A browser response such as `verified=true` is not an
authentication result.

The formal authority, origin and WebAuthn RP ID are fixed:

- authority and origin: `https://auth.kotoba.cloud`
- RP ID: `auth.kotoba.cloud`
- device-flow start: `POST /v1/aiueos/device/start`
- device-flow poll: `POST /v1/aiueos/device/poll`

`auth.itonami.cloud` and generic OIDC are not alternate OS-auth routes.
The `/v1/aiueos/device/*` namespace is also deliberate: the authority already
serves a separate generic Device Code contract at `/v1/device/*`, which AIUEOS
must neither replace nor reinterpret.

## Decision

1. AIUEOS mints a 256-bit challenge and starts a five-minute authority flow
   bound to the exact device DID, model, method, challenge, raw Ed25519 signing
   public key and raw X25519 encryption public key. The request carries an
   Ed25519 proof over that complete binding and a fresh request nonce. The
   authority stores the proof digest for the flow lifetime and refuses replay.
2. The authority returns a public flow ID and approval URL plus a separate
   high-entropy poll token. AIUEOS keeps the poll token only in helper memory.
3. Passkey opens the approval URL. Phone scan locally renders the same URL as a
   QR. Neither path exposes the poll token, enrollment bearer token, account
   key, Passkey material or device private key.
4. The helper polls the authority directly. Every poll carries a fresh
   Ed25519 proof over the flow ID, device DID, challenge and private poll token;
   an invalid proof does not consume the result. Client-supplied verification
   flags are ignored. A grant is admissible only when the result binds the exact
   flow, device DID, challenge, model, method, authority, RP ID, verified
   device public keys, account principal/DID and an active Passkey-backed DID,
   with user presence and user verification.
5. A valid account result is not yet a node claim. AIUEOS signs the challenge
   with the device-owned Ed25519 key and verifies that proof locally. Only then
   does it persist a non-secret account/device receipt and project the node
   plan.
6. A successful authority result is consumed before local persistence. Replay,
   expiry, mismatched binding and missing local key possession fail closed.
7. The approval page may collect a Wi-Fi profile. WebCrypto encrypts it in the
   phone browser to the device's X25519 public key using HKDF-SHA256 and
   AES-256-GCM. The authority validates and stores only the opaque envelope.
   AIUEOS decrypts and validates it locally, then persists only the encrypted
   envelope. Applying that profile to the K16 radio is a separate native-driver
   gate and is not implied by synchronization.
8. The same device-owned Ed25519 seed mints short-lived self-signed CACAO for
   Murakumo node heartbeat and inference queue capabilities. The account
   authority never signs as, or receives the private key of, the node.

The hosted helper uses a fixed-origin Java HTTP client with redirects disabled,
bounded timeouts and a 64 KiB response limit. QR rendering uses the pinned
`io.nayuki/qrcodegen` 1.8.0 jar locally; no third-party QR service sees a live
approval flow. The adapter, state machine and QR dependency are all recorded in
the TCB inventory.

## Evidence and limits

The focused suites inject the authority port and prove signed start, replay
refusal, signed poll, pending, grant, one-time consumption, exact-origin/device
and public-key refusal, local device-key proof, encrypted Wi-Fi round-trip, and
absence of the poll secret or Wi-Fi plaintext from HTTP responses, QR output,
authority state and persisted state. They also prove that browser-supplied
`verified=true` cannot turn a pending authority result into a grant, and verify
the device-minted CACAO signature and issuer.

This is hosted JVM evidence. It does not change `KERNEL.ELF`, qualify the K16,
install the SSD, activate Kekkai, mark Murakumo workload readiness, or start
storage replication. Each of those requires its own runtime or physical proof.
The native K16 network client still routes its physical traffic through the Mac
relay. Its current TLS probe is not a reusable HTTP client with complete trust
chain and hostname verification, so neither K16-direct HTTPS nor physical Wi-Fi
association is claimed here. Production integration remains red until the
authority routes are deployed, the native path is completed, and the full
ceremony is completed by a person with a real Passkey.
