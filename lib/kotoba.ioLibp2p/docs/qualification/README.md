# Qualification receipts

`gossipsub-recovery-2026-08-16.edn` records one three-physical-machine
failure/recovery run. Its detached Ed25519 signature covers the receipt bytes
exactly. Verify it with:

```sh
openssl pkeyutl -verify -pubin \
  -inkey docs/qualification/fleet-ci-signer-tip.pub.pem -rawin \
  -in docs/qualification/gossipsub-recovery-2026-08-16.edn \
  -sigfile docs/qualification/gossipsub-recovery-2026-08-16.ed25519
```

The four raw process logs are not committed; their SHA-256 digests are part of
the signed receipt. The receipt deliberately distinguishes the two incarnations
of the restarted physical machine by authenticated libp2p peer id.
