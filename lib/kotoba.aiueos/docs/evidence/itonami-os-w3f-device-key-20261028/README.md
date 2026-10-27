# Itonami OS W3f: a device key through the consent surface (2026-10-28)

ADR-0277 says the device key is created and used only through the W1 consent surface. This slice builds that path
in the native desktop (RAM only, one key per boot).

Flow: **F8** opens a consent request of its own kind (word 2039 bit 1; panel text "Service: device key / Endpoint:
none, stays here / Action: create one key / Data: no key leaves"). **N or Esc** denies: no entropy is consumed
and no key exists. **Y or the Allow button** draws a 32-byte seed with the Amu `kernel-rdrand` intrinsic (four
64-bit draws, only if CPUID reports RDRAND; a draw of 0 means no entropy and the request fails closed with nothing
stored), derives the Ed25519 public key (`aiueos.ed25519`, merged slices W3b-e) and signs a fixed proof message
`itonami-w3-key-proof` with it. The seed stays in guest RAM (browser-context bytes 512..543); it is never
displayed, never persisted and never leaves the device. The Itonami home DID line then reads
`DID: ed25519 <six hex digits>`, the first three bytes of the public key, and "Approved" counts the Allow.
A second F8 is refused while a key exists. Word 2039 layout: bit 0 consent open, bit 1 key request, bits 2..5
Allow count, bit 6 key exists, bits 7..30 fingerprint.

Evidence: `native-consent-qemu.json` (QEMU TCG, Apple Silicon, `--profile consent`, built from the Amu checkout's
pinned root alone), events `key-deny` and `key-allow`; screenshots `key-request.png` (the panel) and
`key-home-did.png` (the home after Allow). The gate checks, from the guest's RAM and with a reference Ed25519 in
Python: after N the seed bytes are still all zero and Approved is unchanged; after Y the seed is non-constant, the
guest public key equals the public key of that seed, the guest signature verifies under it, and three negative
controls fail to verify: a foreign key, a changed message and a changed signature; the fingerprint bits equal the first
three public-key bytes; a second request is refused. The model-consent checks of the earlier slices still pass
(Approved reaches 2 after the key and the model Allow).
Desktop GPT+ISO, local-draft, idle, cid, sha512, gf25519 and ed25519 profiles also pass with the crypto modules
now linked into the desktop (34 modules; the cid profile 35).

A bug the gate was blind to at first: the home line's dynamic digits did not stop at the end of the text, so the
renderer looped forever after the key was created (the memory assertions passed while the desktop hung; found because
the mouse stopped answering). The digits now cover exactly six positions.

Limits: the key lives in RAM for this boot only (no persistence slot yet, so it does not survive reboot); the seed
is readable by anything in the guest and by this gate (a QEMU observer); no human consent is proven (synthetic input);
no signing flow for requests from apps yet (the proof message is fixed); no constant-time qualification; no DID
document, wallet or key export. QEMU TCG only; diagnostic. Source change and built candidate with a QEMU result;
not deployed.
