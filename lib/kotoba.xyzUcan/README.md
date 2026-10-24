# kotoba-lang/xyz-ucan

Clean-room, EDN-first implementation of the current
[UCAN](https://ucan.xyz/specification/) Delegation v1 envelope and validation
rules. This is the external-origin plane for `ucan.xyz`; it is not the Kotoba
language authority and is not affiliated with the UCAN Working Group.

The implemented interoperable core is deliberately narrow and explicit:

- canonical DAG-CBOR envelope `[signature, sig-payload]`;
- exact `ucan/dlg@1.0.0` type tag;
- Varsig v1 header for Ed25519 over DAG-CBOR (`34 01 ed 01 ed 01 71`);
- real Ed25519 signing and `did:key` verification;
- CIDv1 + dag-cbor + sha2-256 + base58btc token identifiers;
- bounded schema, time, principal-alignment, subject, command-hierarchy,
  revocation, and attenuation checks;
- a closed equality-policy profile for resource-bearing integrations.

It does **not** claim the complete UCAN policy language, Invocation, Promise,
container compression, P-256, or secp256k1. Unsupported surfaces fail closed.
The equality profile accepts exactly:

```clojure
[["==" ".resource" "kotoba://cap/host/ledger-append/dataspace:rooms/a"]]
```

## Example

```clojure
(require '[ucan.core :as ucan]
         '[ed25519.core :as ed])

(def seed (byte-array (range 32)))
(def issuer (ed/did-key-from-seed seed))
(def payload
  {"iss" issuer
   "aud" "did:key:z6Mk..."
   "sub" issuer
   "cmd" "/kotoba/host/ledger-append"
   "pol" [["==" ".resource" "kotoba://cap/host/ledger-append/dataspace:rooms/a"]]
   "nonce" (byte-array (range 12))
   "exp" 2000000000})

(def token (ucan/sign-delegation seed payload))
(ucan/verify-chain
 [token]
 {:now 1900000000
  :revoked? (constantly false)
  :resource! ucan/exact-resource})
```

Authority is never reconstructed from EDN. The result is verified inert data;
a caller still has to intersect it with local policy before minting an opaque
runtime capability.
