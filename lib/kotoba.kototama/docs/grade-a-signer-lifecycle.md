# Grade A manifest signer lifecycle

`kototama.signer-lifecycle` maintains a live manifest-signer trust registry.
Every trust change is authorized by a caller-supplied root signature verifier
and must advance a strictly monotonic epoch.

At admission, a signer is rejected when it is unknown, not yet valid, expired,
revoked, or present in the emergency-distrust set. Rotation can add a new key
and revoke an old key in one signed update. Emergency distrust applies to the
same in-memory registry immediately, without process restart. Stale epochs and
forged root updates fail closed.

`kototama.tender/open-session` makes this check mandatory for
`:profile :production`, verifies that the signed manifest's SHA-256 is the
exact Wasm byte sequence being parsed, and performs the check before
compatibility parsing or instantiation. `fleet.exec/make-execute`
propagates the production signer inputs into the bounded runner. Missing
signing configuration is a denial, never a development fallback.

Verification:

```sh
kbb -M:test -n fleet.store-test \
  -n kototama.signer-lifecycle-test \
  -n kototama.tender-test
```
