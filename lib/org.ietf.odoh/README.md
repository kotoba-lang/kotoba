# kotoba-lang/org-ietf-odoh

**Oblivious DNS over HTTPS — [RFC 9230](https://www.rfc-editor.org/rfc/rfc9230)
— in portable `.cljc`.**

A client encrypts a DNS query to a **target**'s public key and sends it through
a **proxy**. The proxy sees who is asking but not what; the target sees what is
asked but not who. Neither alone can link a client to a query — and that holds
exactly as long as the two do not collude.

```clojure
(require '[odoh.core :as odoh] '[odoh.wire :as wire])

;; client
(def cfg  (first (:value (wire/decode-configs config-bytes))))
(def sent (odoh/encrypt-query cfg dns-query padding-length eph))
;; send (:bytes sent) through the proxy; KEEP (:context sent) and
;; (:query-plaintext sent) — the response cannot be opened without them

;; target
(def got (odoh/decrypt-query cfg target-key-pair (:bytes sent)))
(odoh/encrypt-response cfg (:context got) (:query-plaintext got)
                       dns-response padding-length resp-nonce)

;; client again
(odoh/decrypt-response cfg (:context sent) (:query-plaintext sent) response-bytes)
```

This is HPKE's first consumer in this workspace.

## The response is not a second encapsulation

The query is HPKE base mode, `SetupBaseS(pkR, "odoh query")`. The response is
**not** HPKE at all. The target exports an AEAD key from the *same* HPKE
context, salted with the query plaintext and a fresh `resp_nonce`, and
encrypts with that key directly.

Two consequences a caller can act on:

- **The client must keep the query plaintext.** It is an input to the key
  derivation, so a client that discarded it after sending has thrown away the
  ability to read the answer. That is why `encrypt-query` returns it.
- **The response is bound to its query** — not to the session, to those exact
  bytes. A target cannot take a response it prepared for one query and attach
  it to another. Measured: salting the derivation with only the nonce turns 49
  assertions red, and the two tests named for the binding are among them.

## The `resp_nonce` travels in the `key_id` field

RFC 9230 §6.1 gives both message types the same structure, and a response has
no key to identify — so the field carries the nonce instead. It is
`max(Nn, Nk)` bytes, and it is **also** in the AAD, so a proxy that rewrites
it breaks the tag rather than silently changing the key derivation.

## `key_id` is plain HKDF, not HPKE's labeled forms

`Expand(Extract("", config), "odoh key id", Nh)`, over the encoded
`ObliviousDoHConfigContents`. Everything around it uses HPKE's
`LabeledExtract`/`LabeledExpand`, and reaching for those here produces an
identifier no other implementation computes — after which a peer silently
fails to find its key. It is one line and it is worth a test of its own.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

**229 assertions on both runtimes.**

### The vectors are Cloudflare's, not the RFC's

**RFC 9230 publishes no test vectors.** `test/odoh/vectors.cljk` is
**generated** by `scripts/extract_odoh_vectors.cljk` from `cloudflare/odoh-go`'s
`test-vectors.json`, pinned by sha256 (`737badc1…857c`). That distinction is
kept visible in the test names rather than allowed to read as RFC anchoring.

What the corpus is good for is the strongest form of differential evidence
there is: it carries **16 queries and 16 responses that another implementation
sealed**, and this one opens every one of them. That beats two implementations
agreeing on bytes they both computed the same wrong way.

It cannot be run in the other direction. The ephemeral key is not published, so
the ciphertexts are not reproducible byte-for-byte — sealing is covered by
round-trip instead, across three query paddings and three response paddings,
and that substitution is stated rather than glossed.

### What the suite discriminates

| break | failures | which tests go red |
|---|---|---|
| the query info label is `"odoh-query"` | **115** | the corpus and the binding tests |
| drop `resp_nonce` from the response AAD | **76** | the corpus, the binding, the round-trip |
| salt `derive_secrets` with the nonce only, not the query | **49** | the corpus and the binding tests |
| `key_id` via HPKE's labeled Extract | **1** | the key-id test **only** |
| accept non-zero padding | **1** | the padding test **only** |
| *(restored)* | **0** | none |

The two 1s are the point. Each is a single line that no amount of successful
encryption and decryption would notice: a wrong `key_id` makes a peer fail to
find its key, and unchecked padding turns a MUST-be-zero field into a covert
channel a target could vary per client. Both needed a test written for them
specifically.

### Decoding refuses rather than repairs

A short buffer, a length that runs past the end, trailing bytes after a
complete structure, an empty DNS message, a message type that is neither
0x01 nor 0x02 — each has its own reason, and each is asserted **by** that
reason. Taking what is there and carrying on turns a truncated message into a
successfully parsed different message, and the caller cannot tell.

An `ObliviousDoHConfig` with an unknown **version** is the one exception, and
it is not a repair: RFC 9230 §5 says a client MUST ignore it. Refusing the
whole list would make offering a future version a breaking change, so unknown
versions are counted into `:skipped` — a client that finds nothing usable can
then say whether the server offered none or offered only ones it cannot read.

## Not here

**The HTTP hop.** RFC 9230 §4 defines the exchange over HTTPS with
`application/oblivious-dns-message`, and §3 the deployment requirement that
the proxy and target be operated independently. Both are a caller's, and this
is a leaf: it has no HTTP capability and having one would make it a service.

**Randomness.** `eph` and `resp_nonce` are parameters. A fresh ephemeral per
query is mandatory — reusing one reuses the HPKE context, and the response key
is exported from it — and taking them rather than making them means a caller
who reuses one is doing so visibly.

**DNS.** Nothing here parses a DNS message. RFC 9230 treats it as an opaque
string and so does this.
