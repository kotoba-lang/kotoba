(ns ipns.head
  "Signed IPNS head records for kotobase.net's own XRPC registry
  (`net.kotobase.store.*` / the kotoba lexicon `ipns/head.json`,
  `ipns/publish.json` shape: `{:name :value :sequence :valid_until ...}`).

  This resolves entirely within kotobase.net's own registry -- it does NOT
  join the real IPFS/libp2p DHT (ADR-2607061800). `ipns.core/pubkey->name`
  already derives the IPFS/Kubo-format-compatible `k51...` name; this
  namespace adds the other half, signing/verifying the mutable record that
  name points at.

  **This record shape is local to kotobase.net and no IPFS implementation can
  validate it.** It is not the IPNS Record of specs.ipfs.tech -- that one is a
  protobuf whose signature covers a DAG-CBOR `data` field, and it lives in
  `ipns.record`. Publishing these bytes to the DHT would put a record on the
  network that every peer rejects. Use `ipns.record` for anything that leaves
  kotobase.net; this namespace stays for the records already in that registry.

  `:clj`-only (JCA Ed25519 via `kotoba-lang/ed25519`'s did:key primitives,
  reused not reimplemented), matching `ed25519`/`cacao`'s own JVM-only
  convention -- `ipns.core` itself stays zero-dep and portable; only this
  namespace pulls in the crypto/CBOR deps, so a caller that only needs
  name derivation never resolves them. A portable `:cljs` signing path
  (e.g. over `@noble/curves`, as `kotobase-client`'s own `cacao.cljc`
  already uses) is a tracked follow-up, not fabricated here."
  (:require [ipns.core :as core]
            #?(:clj [ed25519.core :as ed])
            #?(:clj [cbor.core :as cbor])))

#?(:clj
   (defn sign
     "Sign an IPNS head record `{:name :value :sequence :valid_until ...}`
      with the actor's own raw 32-byte Ed25519 `seed` (ADR-2607032500's
      self-mint pattern -- the actor signs its own head, no delegation).
      Returns `record` with `:public_key_multibase`/`:signature_multibase`
      added, the signature covering a canonical dag-cbor payload of every
      OTHER field (the lexicon's own words: \"signature over a canonical
      CBOR payload\"). `:public_key_multibase` is a `did:key:z6Mk...`."
     [seed record]
     (let [payload (cbor/encode record)
           sig (ed/sign seed payload)]
       (assoc record
              :public_key_multibase (ed/did-key-from-seed seed)
              :signature_multibase (str "z" (ed/b58 sig)))))) ; 'z' = base58btc multibase prefix

#?(:clj
   (defn verify
     "Verify a signed IPNS head record (as `sign` produces). Returns
      `{:valid? bool :name (:name record)}` -- recomputes the canonical
      dag-cbor payload over every field except the two signature fields
      themselves, and checks `:signature_multibase` against the `did:key`
      in `:public_key_multibase` (via `ed25519.core/verify-did`).
      A syntactically malformed `:signature_multibase`/`:public_key_multibase`
      (bad base58, truncated did:key, etc. -- exactly what a bit-flip,
      truncation, or tampering attempt produces) fails closed as
      `:valid? false` rather than throwing, so callers can always trust
      `:valid?` without a surrounding try/catch of their own.
      Sequence-rollback (CAS) is NOT this function's job -- that is the
      storage layer's optimistic-concurrency write
      (`kotobase-cljc-worker`'s `r2-put-head-if-match`).

      **The signature alone is not authority over the name.** Until
      2026-08-04 this function checked only that `:public_key_multibase`
      signed the payload, and never that that key is the one `:name` names.
      Since a `k51...` name IS `pubkey->name` of its Ed25519 key, an
      attacker with any keypair of their own could sign a record carrying
      somebody else's `:name`, and every verifier in the stack -- including
      `kotobase.server.ipns/verify-and-decide-publish`, whose only other
      gate is sequence monotonicity -- accepted it. That is a takeover of
      an arbitrary name in kotobase.net's registry. `ipns.core/name-
      matches-pubkey?` is now checked FIRST, so the authoritative key is
      resolved from the name and `:public_key_multibase` is only ever a
      restatement of it. `ipns.record/validate` already worked this way;
      this is that discipline applied to the local registry shape."
     [record]
     (let [{:keys [public_key_multibase signature_multibase]} record
           payload (cbor/encode (dissoc record :public_key_multibase :signature_multibase))]
       {:valid? (boolean
                 (try
                   (and public_key_multibase signature_multibase
                        ;; the name IS the key -- resolve authority from the
                        ;; name, never from what the record claims alongside it
                        (core/name-matches-pubkey?
                         (:name record)
                         (ed/did-key->pubkey public_key_multibase))
                        (ed/verify-did public_key_multibase
                                       payload
                                       (ed/b58-decode (subs signature_multibase 1))))
                   (catch Exception _ false)))
        :name (:name record)})))
