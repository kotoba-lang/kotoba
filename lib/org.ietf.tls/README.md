# kotoba-lang/org-ietf-tls

**A TLS 1.3 client — [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html) —
in portable `.cljc`, with every cryptographic primitive injected.**

It completes a real handshake against a real server and moves application data.
It authenticates the peer **by public-key pin**, not by chain validation to a
trust anchor. Read *What you must not assume* before using it for anything.

```clojure
(require '[tls.client :as client]
         '[tls.transport.jvm :as tp]
         '[tls.result :as r])

(let [t (tp/socket-transport "kotobase.net" 443 {:timeout-ms 15000})
      conn (r/val (client/handshake provider t
                    {:server-name "kotobase.net"
                     :pin-spki-sha256 "50602ad366823fcf5274a7c917baa4fd24b9de4fd15635ff501177c83d05473e"}))]
  (client/write! conn (tls.codec/ascii "GET /llms.txt HTTP/1.1\r\nHost: kotobase.net\r\nConnection: close\r\n\r\n"))
  (r/val (client/read! conn))     ;=> {:tls/content [72 84 84 80 ...]}
  (client/close! conn))
```

## What actually ran

Four live handshakes, all reproduced by `scripts/` in this repo.

| against | suite | result |
|---|---|---|
| `openssl s_server` on loopback, Ed25519 certificate, OpenSSL 3.6.3 | `TLS_AES_128_GCM_SHA256` | handshake, `GET /`, **7 KiB HTTP response**, `close_notify` |
| **`kotobase.net:443`** (Cloudflare), over the public internet | `TLS_AES_128_GCM_SHA256` | handshake, 3-certificate chain, `GET /llms.txt`, **6,391-byte body**, `close_notify` |
| **`crypto.cloudflare.com:443`, with Encrypted ClientHello** | `TLS_AES_128_GCM_SHA256` | **the server accepted ECH** |
| **`defo.ie:443`, with Encrypted ClientHello** | `TLS_AES_128_GCM_SHA256` | **the server accepted ECH** — a different operator, and a three-config list |

The first two verified the server's `CertificateVerify` signature over the
section 4.4.3 context string and the transcript, verified the server's
`Finished`, sent their own `Finished`, and matched the leaf SPKI against a pin.

The ECH pair are worth their own sentence. A real server decrypted a
ClientHelloInner this client encrypted, used it, and said so by putting the
acceptance confirmation into `ServerHello.random` — which this client
recomputed from its own inner transcript and matched. **That is an independent
implementation agreeing, and for ECH it is the only external evidence that
exists**, because the draft is not an RFC and publishes no test vectors.

And the control, because "accepted" from a server that accepts anything would
look the same: flipping **one bit** of the config's public key, so the server
cannot decrypt, gets `:ech-rejected` from both hosts.

```sh
kbb -M scripts/live_ech.cljk crypto.cloudflare.com
kbb -M scripts/live_ech.cljk crypto.cloudflare.com corrupt   # must reject
```

Both verified the server's `CertificateVerify` signature over the section 4.4.3
context string and the transcript, verified the server's `Finished`, sent their
own `Finished`, and matched the leaf SPKI against a pin.

The same live path, run with a deliberately wrong pin against the same server,
**refuses**:

```clojure
#:tls{:alert :bad_certificate, :reason :spki-pin-mismatch,
      :expected "aaaa…aaaa",
      :actual   "50602ad366823fcf5274a7c917baa4fd24b9de4fd15635ff501177c83d05473e"}
```

## RFC 8448 is the oracle

A cryptographic implementation checked only against itself is worth nothing.
[RFC 8448](https://www.rfc-editor.org/rfc/rfc8448.html) publishes byte-exact
traces of a complete TLS 1.3 handshake — every intermediate secret, every
serialized `HkdfLabel`, every protected record. Section 3 is reproduced here
**byte for byte**:

- the X25519 shared secret, from the RFC's own private and public keys
- the whole ladder: early → derived → handshake → `c/s hs traffic` → derived →
  master → `c/s ap traffic` → `exp master` → `res master`
- the serialized `HkdfLabel` for `derived`, `c hs traffic`, `key`, `iv`,
  `finished` — checked *separately* from their outputs, because a wrong info
  block and a wrong PRK produce the same wrong answer and only this
  distinguishes them
- both directions' handshake and application traffic keys and IVs
- **all six protected records**, decrypted *and* re-encrypted to the identical
  ciphertext (AES-GCM is deterministic given key and nonce, so this is a real
  equality, not a round-trip through our own code)
- both `Finished` messages' `finished_key` and `verify_data`
- the resumption PSK

The vectors are **not transcribed by hand**. `scripts/extract_rfc8448.cljk`
parses them out of the RFC's own text; each block in the RFC declares its own
octet count and the extractor refuses to emit one that does not reach it
exactly. The fixture records the SHA-256 of the input it came from
(`6564d137…`), so a reader can re-fetch and re-derive.

## What you must not assume

`authenticate-peer` returns what it checked **and what it did not**, in the
value, so a caller that logs the decision logs the limit with it. From a live
run against `kotobase.net`:

```clojure
:checked     #{:leaf-usable :basic-constraints :server-name :spki-pin}
:not-checked #{:chain-to-trust-anchor :issuer-signature :revocation
               :name-constraints :certificate-transparency :validity}
```

- **There is no chain validation.** No root store, no path building, no
  issuer-signature check, no name constraints, no CRL, no OCSP, no certificate
  transparency. An `[:ok …]` does not mean the certificate chains to anything.
  Identity comes from the SPKI pin and nothing else.
- **`handshake` refuses to proceed** unless you pass `:pin-spki-sha256`, a
  `:verify-chain` function, or the explicit `:insecure-skip-peer-auth`. There is
  no default, because a client that authenticates nothing and returns success
  is worse than one that fails.
- **Expiry is checked only if you pass `:now`.** This library reads no clock —
  "was it valid when it signed" and "is it valid now" are different questions
  and only the caller knows which it is asking. Without `:now`, `:validity`
  appears in `:not-checked`; an expired certificate accepted knowingly and one
  accepted silently must not produce the same map.
- **Hostname matching happens only if you pass `:server-name`**, which the
  ClientHello needs anyway, so in practice it does. It is RFC 6125 §6.4 over
  `subjectAltName` `dNSName` entries: a wildcard is the entire leftmost label
  of a name with at least three labels and consumes exactly one. `commonName`
  is never a fallback. Pass `:check-server-name? false` to skip it.
- **No HelloRetryRequest.** One X25519 key share. If the server wants another
  group the handshake refuses and names it. Servers that require P-256 are
  unreachable.
- **No resumption, no 0-RTT, no PSK, no client certificates, no ALPN
  negotiation, no KeyUpdate.** A peer `KeyUpdate` is refused rather than
  ignored — ignoring one desynchronises the keys silently.
- **Only `TLS_AES_128_GCM_SHA256` and `TLS_CHACHA20_POLY1305_SHA256`.**
  `TLS_AES_256_GCM_SHA384` is not offered: it needs SHA-384, and offering a
  suite the provider may not carry is negotiating into a handshake that cannot
  finish. Which of the two is offered is *computed from the provider*
  (`tls.suite/negotiable`), not declared.
- **Timing.** The protocol layer is not written to be constant-time beyond the
  two comparisons that must be (`verify_data`, and AEAD tags, which are the
  provider's). Byte vectors of boxed integers are not a constant-time
  representation and nothing here claims otherwise.

## Layout

| namespace | RFC 8446 | what it owns |
|---|---|---|
| `tls.result` | — | `[:ok v]` / `[:error e]`. Nothing throws; every error carries the alert a peer would receive |
| `tls.codec` | §3 | the presentation language: cursor-based reads, `opaque x<lo..hi>` with its bounds, `u64` written with division so a 64-bit sequence number does not round |
| `tls.alert` | §6 | alert descriptions; `close_notify`/`user_canceled` may be warnings, everything else is forced fatal |
| `tls.transcript` | §4.4.1 | the message-level transcript (headers included), forkable at the four points TLS needs |
| `tls.schedule` | §7, RFC 5869 | HKDF, `HkdfLabel`, `Derive-Secret`, the ladder, traffic keys, `Finished`, KeyUpdate, resumption, exporter |
| `tls.record` | §5 | TLSPlaintext / TLSInnerPlaintext / TLSCiphertext, the §5.3 nonce, padding, size bounds |
| `tls.extension` | §4.2, RFC 6066 | extension framing; unknown extensions round-trip byte-exactly; duplicates refused |
| `tls.handshake` | §4 | message framing and bodies; HelloRetryRequest detection; the §4.1.3 client checks |
| `tls.suite` | App. B.4 | suite geometry bound to the provider's AEAD |
| `tls.cert` | §4.4 | the `Certificate` message, the `CertificateVerify` signed content, and the peer-identity decision |
| `tls.provider` | — | the crypto seam, as data: the contract, the validator, and the reason set |
| `tls.provider.jvm` | — | the JDK-backed provider. Byte arrays |
| `tls.provider.vectors` | — | adapts a byte-array provider to the byte-vector protocol layer, and refuses one that fails a published known answer |
| `tls.client` | — | the driver: handshake, `write!`, `read!`, `close!` |
| `tls.transport.jvm` | — | a TCP socket. Two functions, `:send` and `:recv` |

## Two byte representations, on purpose

The protocol layer works in `vector<int 0..255>` — the representation
`kotoba-lang/bytes`, `kotoba-lang/noise` and `kotoba-lang/org-ietf-asn1`
already share. That is not taste: byte vectors have **value equality**, so
`(= expected actual)` on a 679-octet record is a real assertion and a failure
prints the divergence. Byte arrays compare by identity, and a suite written
against them would be asserting `Arrays/equals` everywhere or asserting
nothing.

`tls.provider` speaks byte arrays, because that is what `MessageDigest`, `Mac`,
`Cipher` and `Signature` take.

`tls.provider.vectors/adapt` is the single conversion between them, using
`asn1.core`'s `->ints` / `ints->bytes` rather than a third pair. It **refuses**
a provider that fails `tls.provider/validate` or any of three published known
answers — SHA-256 of the empty string (FIPS 180-4), RFC 4231 test case 1, and
RFC 7748 §5.2's X25519 vector.

That check is not ceremony. The provider answers `[:error :hash/bad-input]`
when handed something that is not a byte array, and **`[:error :hash/bad-input]`
is itself a vector**: passed on as a digest it gives the key schedule a
two-element "hash", derives secrets nobody agrees with, and fails on the far
side with no local diagnostic. Checking once, against answers nobody in this
repository chose, turns that into a refusal at wiring time.

## The provider seam

Nothing in `src/` implements a cipher. The seam is copied deliberately from
`kotoba-lang/noise`, which states the argument: constant-time field arithmetic
and constant-time tag comparison are exactly what a hand-rolled portable port
loses, so those come from an audited implementation while everything that is
pure data-shuffling stays portable and identical on every runtime.

Say the consequence plainly: **on bare metal, where there is no JDK and no npm,
the provider is precisely the part that does not exist.** This library does not
close that gap. It reduces it from *a TLS stack* to *X25519, AES-GCM or
ChaCha20-Poly1305, SHA-256, HMAC, and one signature verify* — which is close to
what `kotoba-lang/aiueos` already has in `x25519.kotoba` and `sha256.kotoba`.

## What was reused rather than rewritten

Searched first (44,192 source files under `orgs/`, plus the west manifest's
4,229 project names and the concept index). There was **no TLS 1.3 protocol
implementation anywhere** — `capability-crypto-tls` is `provider-status:
contract-only`, and `io-storj-node` / `provider-transport` both call the *host's*
TLS 1.2. What did exist and is used or is directly adjacent:

| repo | what it gives |
|---|---|
| `kotoba-lang/noise` | the injected-primitive seam this copies, and its security argument |
| `kotoba-lang/org-nist-sha2` | pure `.cljc` SHA-256 + HMAC — the whole key schedule can run with **no host crypto at all** |
| `kotoba-lang/bytes` | the `vector<int 0..255>` byte contract |
| `kotoba-lang/org-ietf-x509`, `org-ietf-asn1` | RFC 5280 / X.690 — what `tls.cert` will build chain handling on |
| `kotoba-lang/org-ietf-tcp` | RFC 9293 TCP as a pure state machine — the layer below, for when there is no socket |
| `kotoba-lang/org-ietf-ed25519` | Ed25519, for a provider without a JDK |

## Encrypted ClientHello (`tls.ech`)

**draft-ietf-tls-esni-25.** The client sends two ClientHellos: a
`ClientHelloOuter` naming the client-facing server's `public_name`, and a
`ClientHelloInner` — the real one, with the real SNI — encrypted into the
outer's `encrypted_client_hello` extension with HPKE.

This is the ECH **data plane**: configurations, `EncodedClientHelloInner` and
its reconstruction, `ClientHelloOuterAAD`, the seal and open, and the
acceptance confirmation. Both halves are here, client and client-facing
server.

### Offering it

```clojure
(client/handshake provider transport
  {:server-name "crypto.cloudflare.com"
   :pin-spki-sha256 "…"
   :ech {:config-list <ECHConfigList bytes, from the host's HTTPS record>}})
```

The client builds both hellos, sends the outer, and decides from
`ServerHello.random` which one the server used — the transcript starts with
whichever it was, which is why both are kept until then. The inner is padded
by §6.1.3's scheme, without which the ciphertext length would track the inner
SNI length: the one thing ECH exists to hide.

### On rejection (§6.1.6)

The client does **not** stop at the ServerHello. It finishes the handshake
against the `ECHConfig.public_name` — a different identity from the one the
caller asked for, so `:ech {:public-name-pin "…"}` is what authenticates it —
collects `retry_configs` from EncryptedExtensions, sends an `ech_required`
alert, and returns an error.

An error, not a connection, and the draft is explicit about why:
authenticating for the public name **does not authenticate the origin**, so
such a connection may never be reported as successful or carry application
data. It exists to carry the retry configs out.

If the public name does not authenticate, the error is the authentication's
and the retry configs never surface — §6.1.6 says a client MUST NOT use them
in that case, and the way to guarantee that is not to hand them back.

Measured against a live server: offering ECH with a key Cloudflare does not
hold gets a rejection, the handshake completes against `cloudflare-ech.com`,
and the server hands back **one retry config** — a different `config_id` from
the one its DNS record publishes.

```
rejected, as it must with a key the server does not hold
  public name        cloudflare-ech.com
  retry_configs      1 config(s) from the server:
    id 75 kem 0x0020 name cloudflare-ech.com
```

A `public_name` that is not a host name is refused before any of that, when
the config is chosen (§6.1.7): dot-separated LDH labels, and a final label
that does not read as a number. A name whose last label is all digits or
`0x`-and-hex is one some resolvers and URL parsers take for an **IPv4
literal**, and a client that authenticated a certificate for it would be
authenticating something other than a host.

**ECH's HelloRetryRequest path is unreachable rather than omitted.** This
client does not implement HRR at all (`tls.handshake/check-server-hello`
refuses it by name), so §7.2.1 cannot arise from here.
`tls.ech/hrr-accept-confirmation` exists and is tested; nothing in
`tls.client` can reach it.

### ECH is not an RFC and has no test vectors

Measured, not assumed: the datatracker gives `draft-ietf-tls-esni` no RFC
number at revision 25, and the draft text contains no test-vector section. So
none of the ECH tests are known-answer tests, and none are labelled as though
they were. The evidence is of three kinds, kept apart:

**Live configurations.** `test/tls/ech_configs.cljk` holds `ECHConfigList`
values pulled from real HTTPS resource records — Cloudflare's, and defo.ie's,
which publishes three configs in one list. Parsing bytes that are actually
deployed is the only part of this that is not self-consistency.
`scripts/fetch_ech_configs.cljk` refreshes them, and it carries **no sha256
pin**, unlike every other generator in this workspace: servers rotate ECH keys
daily by design, so pinning that input would make the script refuse every time
it was right.

**Two-sided round-trip.** Every client operation has a server-side counterpart
in the same namespace, and the tests run both — including the compression
path, where the inner hello names extensions instead of repeating them and the
server puts the outer's copies back.

**The aborts.** §5.1 names four conditions under which a client-facing server
MUST abort while reconstructing the inner. Each has its own reason and its own
test. Three of them exist to stop a small ClientHelloOuter decompressing into
a huge ClientHelloInner (§10.12.4); they are not tidiness.

### What the offering is checked against

There is no TLS server in the test suite, so the client's ECH output is
checked against the property a real client-facing server checks: **the outer
this client sends can be opened with the config's private key and reconstructs
to exactly the inner hello the client composed.** That runs against
`build-ech-hellos`'s real output rather than a hand-built fixture.

The acceptance judgement is checked against an independently constructed
ServerHello — built the way §7.2 describes it from the server's side — and
against one computed over a *different* inner hello, which must not be
mistaken for acceptance.

And four inner names of four different lengths must produce **one** payload
length. A client that offered ECH without padding would be advertising the
length of the name it was hiding.

### What the ECH tests discriminate

| break | failures | which tests go red |
|---|---|---|
| the HPKE `info` drops the ECHConfig | **15** | the pinning test **only** |
| seal without `ClientHelloOuterAAD` | **5** | the round-trips and the binding test |
| keep the inner's `legacy_session_id` | **4** / **1** | two call sites, two tests |
| skip the outer-extensions order check | **1** | the aborts test |
| accept non-zero padding | **1** | the aborts test |
| drop §6.1.3's no-SNI padding rule | **1** | the padding test |
| the outer gets its own `legacy_session_id` | **4** | the shared-id test and the open |
| the transcript always starts with the outer | **2** | the selection test **only** |
| the ServerHello tail is not zeroed before hashing | **1** | the acceptance test |
| the inner hello is not padded | **1** | the payload-length test |
| the `public_name` split regex written `\\.` instead of `\.` | **14** | the host-name tests |
| drop §6.1.7's IPv4-literal rule | **8** | the host-name tests |
| an ECH extension after acceptance is allowed | **3** | the EncryptedExtensions test |
| `choose` ignores the `public_name` | **1** | the choose test |
| a malformed retry config becomes an empty list | **1** | the EncryptedExtensions test |
| *(restored)* | **0** | none |

Two rows are worth reading.

**The HPKE `info`.** Both halves of ECH live in one namespace, so a
*symmetric* change to it leaves every round-trip green — it is only wrong
against a peer. Dropping the ECHConfig from the info broke nothing at all
until `config-info` was pulled out and pinned to the draft's text. **A
two-sided test cannot check a value both sides agree on.**

**The transcript selection.** Getting it wrong gives a client that builds both
hellos correctly, encrypts correctly, judges acceptance correctly, and then
derives its keys from the wrong transcript. Forcing it to always pick the
outer left the whole unit suite green — **only the live handshake noticed.**
So the decision is a named function now, and it has a test.

**And the `public_name` check was wrong twice, the same way both times.** It
takes a byte vector, and both wrong versions reached for characters.

The first split labels on a regex with one escape too many, so the pattern
matched a backslash followed by anything instead of a dot: nothing split,
every name became one label containing dots, and **every valid public name was
rejected**. There was no test for it yet — the live handshake failed on the
first run after the check landed.

The second classified characters with `(map int …)`, which is code points on
the JVM and **zeros** under ClojureScript. The JVM suite was green; the
ClojureScript one was not. Then the *test's* own helper did the same thing and
had to be fixed too.

It compares bytes to byte constants now and never sees a character at all,
which has neither failure available to it. Fourteen assertions, both runtimes.

That trap — `hpke.kdf/ascii` documents it — was walked into **three times in
one afternoon** by code written to be careful about it. Documenting a trap is
not the same as removing the shape that makes it reachable.

### Two bugs this found, both in the shape the rules warn about

**A context map silently replaced the error reason.** `tls.result/error`
merges the caller's data *over* `{:tls/alert :tls/reason}`, so
`(error :decrypt_error :ech-open-failed {:tls/reason ...})` reported the inner
reason instead of the stable keyword. Nothing would have noticed if the tests
asserted "an error happened" rather than **which** error.

**A test's expected value hit the `(map int "…")` trap.** On the JVM that is
code points; under ClojureScript it is a vector of zeros — the trap
`hpke.kdf/ascii` documents, walked into by a test written to check exactly
that kind of thing. The seven bytes of `"tls ech"` are now written out, with
`(map char …)` back to the string as the cross-check.

### The ClojureScript path covers the ECH tests, and only those

The rest of this suite is `.clj` because the cryptographic provider is
injected and the one that exists is the JVM's. ECH's data plane is different —
its crypto is `org-ietf-hpke`, which is portable — so the parser, the
reconstruction and the confirmation derivation run on both runtimes, and the
codec underneath them is byte arithmetic, which is exactly where the two
runtimes differ.

```sh
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk
```

**922 assertions there; 1,472 for the whole suite on the JVM.** The runner
names its one namespace rather than globbing, and **exits 2 if it executed no
assertions at all** — a runner that quietly found nothing to run would
otherwise report success.

## Test

```sh
kbb -M:test                   # plain clojure.test
kbb -M:report                 # the same tests, with counts
```

Last run:

```
Ran 79 tests containing 550 assertions.
0 failures, 0 errors.

RFC8448-SOURCE-SHA256      6564d1376d1ec744fc7a9993da15ebc1b9be361908b166091f47ef605c537fba
RFC8448-BLOCKS-IN-FIXTURE  108
RFC8448-VECTORS-COMPARED   43
REFUSALS-EXERCISED         40
ASSERTIONS                 550 passed, 0 failed, 0 errored
OK
```

Verified in three directions, through the alias: unmodified → **exit 0**; one
vector byte corrupted → **exit 1** (`549 passed, 1 failed`); fixture removed →
**exit 3** and `COULD-NOT-RUN  refusing to report a pass`.

`tls.report` (see below for the invocation) exits **3**, not 1, when it could not run its vectors at all — a
suite that could not measure has not found a bug, and reporting one is its own
kind of lie. It refuses to report a pass on zero vectors compared or zero
refusals exercised.

Live runs are `scripts/live_loopback.cljk` and `scripts/live_kotobase.cljk`; they
are not part of the default suite because they need a network.

Apache-2.0.
