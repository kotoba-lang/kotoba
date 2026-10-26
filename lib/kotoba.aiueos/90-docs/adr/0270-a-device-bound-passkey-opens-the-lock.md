# ADR-0270 — A device-bound passkey opens the lock

Date: 2026-10-24

## Status

Accepted. Adds the `guest-browser-passkey` gate; no new floor. Row B1 ("Sign in with a device-bound passkey": the session opens; a passkey for
another device is refused) of the ChromeOS-grade scorecard.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-passkey` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_PASSKEY_OK`: the notification gate (and so the layout and clock gates) is green on the same serial; the
device key is registered (`PASSKEY_REG ready=1`); on the lock screen a passkey of another device signs but does not verify (the lock stays,
the red bar shows) and this device's passkey verifies and opens a session whose id is printed; and all 10 `AIUEOS_GUEST_BROWSER_PASSKEY`
frames equal the frame model's.

## Decision

- The device key is an ECDSA P-256 scalar drawn from the virtio-rng the first time a passkey is needed, with its public point, in sector
  1035 of this machine's volume (magic `AIUEPKY1`, an FNV checksum, written with readback). It is the device's: another volume has another
  key.
- The ceremony is WebAuthn-shaped, in C over the Kotoba ECDSA and SHA-256 objects: a fresh 32-byte challenge; authenticator data (the SHA-256
  of the relying party `aiueos-session` and the user-present flag, the key press); a signature over SHA-256(challenge || authenticator data)
  with a fresh nonce; and a verification of that signature against the REGISTERED public point. Only a verified signature opens the session;
  its id is the first eight bytes of SHA-256(challenge || signature).
- On the lock screen Kotoba maps F4 to "this device's passkey" and F3 to "a passkey made on another device" (a fresh scalar that is not the
  device's -- the test stand-in for a phone's passkey) and answers 300000001 / 300000002; C runs the ceremony and returns the verdict as the PIN
  attempt does (a value-2 key event), so the lock's own rules (the red bar, the unlock) are unchanged.

## Not

The private scalar sits in the clear on the volume (no data encryption at rest, G3) and there is no secure element or TPM seal; user presence
is the key press, with no biometric; no signature counter, no attestation, no rp/origin binding beyond the fixed id; the "other device" is a
test key, not a second machine; the PIN stays as the other way in.
