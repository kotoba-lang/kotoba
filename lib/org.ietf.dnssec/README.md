# org-ietf-dnssec

[![CI](https://github.com/kotoba-lang/org-ietf-dnssec/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ietf-dnssec/actions/workflows/ci.yml)

**DNSSEC zone signing** — RFC 4034 / 4035, RFC 8080 (Ed25519), RFC 8624
(algorithm selection). Canonical forms, RRSIG, DNSKEY, DS and the NSEC chain,
as portable `.cljc` with **zero dependencies, including crypto**.

[`org-ietf-dns`](https://github.com/kotoba-lang/org-ietf-dns) explicitly scopes
DNSSEC out; this is that piece. It reads and produces the same `:zone/*` record
shape as [`zone`](https://github.com/kotoba-lang/zone), so signed records go
straight back into a zone with no translation.

## Crypto is injected, never imported

```clojure
(sign/rrsig records {:algorithm :ed25519
                     :key        key-handle          ; opaque to this library
                     :sign-fn    (fn [algo key octets] …)
                     :key-tag 12345 :signer "example.com."
                     :original-ttl 3600 :inception … :expiration …})
```

Not portability theatre. A library that imported a signing implementation would
also have to hold, or at least touch, the zone-signing key. Keeping the
primitive outside means the key can live in an HSM, in `kagi`, or in a JVM
`KeyStore` and this code never sees it — the same discipline
`cloud-itonami.dns-provider` uses to make "the actor reads a secret"
structurally impossible rather than merely discouraged.

It also makes the *serialization* testable on its own, which is the half that
actually breaks. A DNSSEC bug is almost never in the signature arithmetic; it is
in **which bytes got signed**. The test suite's "signer" returns the blob it was
handed, so every assertion is about exactly those bytes — with no crypto at all.

## The reference provider

`dnssec.provider` is one possible injection — Ed25519 via
[`kotoba-lang/ed25519`](https://github.com/kotoba-lang/ed25519) and SHA-2 via
the host — so the common case does not have to assemble it:

```clojure
(require '[dnssec.provider :as p])

(def pubkey (p/public-key seed))
(p/sign-rrset records {:algorithm :ed25519 :key seed :key-tag tag
                       :signer "example.com." :original-ttl 3600
                       :inception … :expiration …})
(p/delegation-signer dnskey {:algorithm :ed25519 :digest-type :sha256})
```

It does **not** weaken the boundary: `dnssec.canonical` and `dnssec.sign` still
import no crypto, requiring them does not load the provider, and a caller with
an HSM or a key store passes its own two functions and ignores this namespace
entirely.

`provider_test.cljc` is where the signer stops being a byte shuffler: it signs
with a real key, rebuilds the blob **the way a validator would** — from the
RRSIG's own rdata plus the RRset, not from what the signer happened to keep —
and checks the signature against that. It also asserts the two failures that
matter: one changed octet in the RRset breaks it, and so does signing with the
record's current TTL instead of the original (the failure that validates at the
origin and fails from every cache).

Not covered by the provider: ECDSA and RSA, which are legitimate DNSSEC
algorithms it refuses rather than signing with the wrong curve; and a Worker
path, because WebCrypto is asynchronous and zone signing is a job rather than a
request handler.

## Canonical form is the whole foundation

A signature is over bytes. If a validator serializes an RRset one byte
differently from the signer, every signature fails and the zone goes bogus —
which looks like a key problem, a clock problem, or a resolver problem, and is
none of them.

**Names are lowercased and uncompressed.** This library has its own encoder
rather than reusing `nameserver.wire`'s, because that one applies RFC 1035 name
compression — correct for a message, fatal here, since a compressed name's bytes
depend on what *else* is in the message. The same RRset would sign differently
depending on which query produced it.

**The original TTL is used, not the record's.** The RRSIG carries the TTL the
RRset had at the authoritative server; a cached copy has a decremented one.
Signing with the current TTL produces a signature that validates at the origin
and fails everywhere else — the hardest DNSSEC failure to reproduce, which is
why `encode-rr` takes `original-ttl` as a required argument instead of reading
it off the record.

**Names sort right-to-left, not as strings.** `z.a.example.com` precedes
`a.b.example.com`: the rightmost labels tie, then `a` beats `b`, and the
leftmost label never gets a say. Every place string order disagrees produces an
NSEC chain that proves the nonexistence of names that do exist. The RFC 4034
§6.1 worked example is in the test suite — with `\001` and `\200` as the real
octets 0x01 and 0x80, since spelling them as literal backslash text would
compare 0x5C and test nothing.

**RRsets sort by RDATA as unsigned octets.** So `192.0.2.2` precedes
`192.0.2.10`. Two servers that order an RRset differently produce different
signed blobs from the same records.

## What gets signed

RFC 4035 §5.3.2, and the order matters:

```
RRSIG_RDATA (signature field empty) || RR(1) || RR(2) || …
```

Signing only the records — omitting the RRSIG rdata prefix — is a real and
common mistake that produces signatures no validator accepts, because a
validator *rebuilds* the blob from the RRSIG it received. `sign/signing-blob`
is exposed for exactly this: when a signature will not validate, compare this
blob between signer and validator and the disagreement is always visible in it.

## Other things that fail quietly

**The key tag is a checksum, not a hash**, and two keys can collide — a
validator must try every DNSKEY with a matching tag rather than assuming the
first is right. Algorithm 1 (RSA/MD5) uses a *different* tag rule; it is
deprecated and unsupported, so passing it raises rather than returning a
silently wrong tag.

**The RRSIG `labels` field excludes the root and a leading wildcard.** An
off-by-one here breaks wildcard proofs specifically — everything else keeps
validating, which is why it survives testing.

**The NSEC type bitmap counts bits from the most significant end**, and only
non-empty windows are emitted. The endianness reads backwards and is the usual
source of a bitmap claiming the wrong types exist.

**The NSEC chain is circular** — the last name's `next` is the apex. A chain
that stops at the last name leaves every name sorting after it unprovable, so
those queries fail to validate instead of returning a proven NXDOMAIN.

**A DS never published in the parent means the zone is unsigned.** To every
validator, a correctly signed zone with no DS in its parent is just an unsigned
zone. The DS is the single link, and it is the one artifact this library
produces that has to leave the registry.

**Deprecated algorithms are absent, not discouraged.** RSA/SHA-1, the DSA
family and SHA-1 digests are not in `algorithms`/`digests` at all, so nobody
picks one by autocompleting (RFC 8624).

## EDNS0 is a prerequisite

A single signed response routinely exceeds 512 octets. A signed zone served
without EDNS0 pushes every query to TCP — so `nameserver.edns` in
`org-ietf-dns` is a dependency of deploying this, not an optimization.

## Scope

- **In:** canonical name/RR/RRset forms and ordering, DNSKEY, key tag, DS
  digest input and record, RRSIG signing blob and record, NSEC records and the
  full chain, the type bitmap.
- **Also in:** NSEC3 (RFC 5155) — `dnssec.nsec3`. NSEC proves nonexistence by
  handing you the two names that surround the queried one, which also lets
  anyone walk the chain and read out every name in the zone. For a registry
  whose name list is its business that is not theoretical. NSEC3 hashes the
  neighbours instead.
- **Not yet:** signature *validation* (this is a signer; `dnssec.provider`
  verifies, so a signer can check its own output before publishing), key
  rollover scheduling, and CDS/CDNSKEY (RFC 7344) for automated parent updates.
- **Never:** a key, a clock, or a crypto implementation.

## NSEC3, and the two places it is usually wrong

**Iterations are not a security dial.** Higher looks safer and is not: an
attacker pays the cost once per *candidate name*, and zone names are short and
dictionary-drawn, so the guessing cost is dominated by the candidate list. The
**validator** pays it on **every negative answer**. A high count is a
denial-of-service amplifier pointed at yourself, which is why RFC 9276
recommends `iterations = 0` and an empty salt — the default here, with anything
large refused.

**`base32hex`, not standard base32.** Standard base32 is `A-Z2-7`; base32hex is
`0-9A-V`. They differ in *every* symbol, so the wrong one yields owner names
that sort differently and match nothing — a chain that proves nothing while
looking correct. The RFC 4648 test vectors are in the suite.

Two more, each with a test: the hash is over the **canonical wire form** of the
name, not the text (hashing the text gives a chain no validator reproduces),
and the salt is applied at **every** iteration rather than only the first.

`covers?` handles the **wrap** at the end of the chain, where `next` is smaller
than `hash`. Written as a plain `lo < x < hi` range that interval is never
covered — and it is exactly the one an attacker would aim at.

**Opt-out is deliberately not produced.** It lets a zone skip NSEC3 records for
unsigned delegations, which is why large TLDs adopted it, and it also means the
zone can no longer prove those delegations do not exist. That is a different
security model, not a parameter.

## Test

```
kbb -M:test
```

25 tests / 88 assertions, including a real-key sign-then-verify round trip.
