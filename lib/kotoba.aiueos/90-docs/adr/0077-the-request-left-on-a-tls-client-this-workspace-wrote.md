# ADR-0077 — The request left on a TLS client this workspace wrote, and one pin check decided who it talked to

Date: 2026-08-22

## Status

Accepted and executable **for the hosted profile, on an opt-in transport**. On
2026-08-22 `kbb -M:cloud-live check --transport own` opened TLS 1.3
connections to `api.murakumo.cloud`, `infer.murakumo.cloud` and `kotobase.net`
using `kotoba-lang/org-ietf-tls`, framed HTTP/1.1 over them with
`kotoba.lang.http.wire`, resolved the `murakumo-main` alias, obtained a
completion from a `POST`, read a block whose bytes hash to its CID, and had a
404 refused for the right reason. **All five legs ADMITTED. Exit 0.** The same
gate on `--transport jdk` also exits 0, on the same run of the same policy.

`java.net.http` is not on that path. What is still the platform's, and is stated
here rather than at the end: the **primitives** are the JDK's —
`tls.provider.jvm` is its AES-GCM, SHA-256, HMAC, X25519 and ECDSA — and the
socket is `java.net.Socket`. What left is the HTTP client and the TLS
implementation, not the JDK.

Not executable, and also stated here:

- **`:jdk` is still the default and this change does not move it.** A transport
  that has run one operator's gate twice is not a default. Flipping it is a
  separate decision with its own evidence.
- **Chain validation to a trust anchor does not exist on either transport.** Not
  weakened here and not fixed here. On both paths the peer is accepted because
  its key is one the policy named for the host being reached, and for no other
  reason: no chain, no revocation, no certificate transparency, no name
  constraints, no issuer signature, no validity dates, and — measured, see
  below — no match between the certificate and the name it was reached by.
- **The bare-metal profile still cannot use any of this.** ADR-0041's ordered
  gap ledger steps **2 and 3** — a DNS stub resolver, and TCP as a usable stream
  — are exactly where they were. Step 1 closed on the same day, by different
  work in the same repository (ADR-0076: a real DHCPv4 exchange in QEMU), which
  makes the remaining gap smaller by one row and not by one inch on this path: a
  TLS client with no TCP stream under it is a state machine with nothing to
  read, and one with no resolver cannot find out where to point it. Steps 4 and
  5 are answered by this change *as libraries*, and their rows are corrected
  there. **Nothing in `os/aiueos/` changed here** — that directory's diff on
  this branch is entirely ADR-0076's.
- **The own transport speaks https and nothing else.** A plaintext URL is
  refused by name; the platform path, under the operator escape hatch that
  loopback suites use, would fetch it.
- **The credentialed inference surface is still unmeasured**, and the live write
  leg is still unauthorised. Neither is about transports.

## Context

ADR-0073 got the first request out of this machine. It went out on
`java.net.http` — correctly, because that was the only HTTP client that existed,
and because ADR-0044 had already taken the *decision* away from the platform:
the default trust store is not consulted, and an https peer is accepted only if
`grant.cloud/admit-peer` says its key is one the policy names for that host.

What remained platform-owned was the implementation. The TCB inventory said so
in as many words: `java.net.http`, `:source :platform`, `:assurance-gap
:platform-tls-implementation-not-content-addressed` — an entry that exists to
record that this repository cannot pin the JDK's TLS from inside itself.

On 2026-08-22 two libraries in this workspace became usable at once.
`kotoba-lang/org-ietf-tls` @ `b91d4a1` is an RFC 8446 client: handshake, record
layer, key schedule, `tls.cert`. `kotoba-lang/http` @ `1af5514` is
`kotoba.lang.http.wire`, an RFC 9112 client over an **injected** byte transport
— it knows nothing of TLS, sockets or DNS, which is the property that makes the
two composable without either depending on the other.

## Decision

Add a second transport to `aiueos.provider.cloud`, selected by an explicit
policy value, defaulting to the platform one.

```clojure
:aiueos.cloud/transport :jdk   ; java.net.http           (the default)
:aiueos.cloud/transport :own   ; org-ietf-tls + http.wire
```

`kbb -M:cloud-live check --transport own` runs the same gate the other way,
and the receipt carries `:transport`, so two runs are distinguishable.

**The adapter lives here, beside the consumer, and not in a repository of its
own.** It is about twenty lines of coupling — `tls.client/write!` and `read!`
turned into the `{:write :read}` pair the wire layer asks for. What is not small
is the policy it carries: redirects are never followed, a body over the ceiling
is refused rather than truncated, a request that could not complete yields no
status and no digest, and the peer verdict is the decision plane's. Those are
statements about what this machine will act on. The trigger for extracting a
shared library is a **second** consumer, not this one.

### One pin check, and it is `grant.cloud/admit-peer`'s

`tls.client` can authenticate a peer against a pin itself, via
`:pin-spki-sha256`. It is not asked to. It is handed `:verify-chain`, which
takes the whole decision, and which does exactly two things: measure the leaf's
SubjectPublicKeyInfo with `tls.cert/spki-sha256-hex`, and ask
`grant.cloud/admit-peer` — the same function the platform path's trust manager
asks, with the same `{:spki-sha256 :host}` argument.

Two pin checks that could disagree is worse than one, and the failure mode of a
disagreement here is specific: a peer one layer refused, another layer has
already accepted. It also keeps the policy features that live in the decision
plane and not in the TLS library — host-bound anchors, `:previous` keys, and the
`:accept-previous-until-ms` rotation window — working identically on both paths.
`tls.client`'s own pin mode takes one hex string and has no vocabulary for any
of that.

### One `arrived` map

`grant.cloud/admit-block`, `admit-inference` and `admit-liveness` read one
shape. Both transports now build it through a single `arrived-of`, so two paths
cannot come to describe the same response differently — the day they did, the
difference would arrive as a decision rather than as a bug.

## Executable evidence

All measured 2026-08-22 on this workstation, against the real hosts and against
a loopback server this suite generates a certificate for.

### The live gate, both ways

```
$ kbb -M:cloud-live check                    → exit 0
LEG model-resolve       ADMITTED  :status 200  :host "api.murakumo.cloud"    :peer-spki "ec7f258f…1af1"  :byte-count 497
LEG inference-liveness  ADMITTED  :status 200  :live? true                                               :byte-count 582
LEG inference           ADMITTED  :status 200  :host "infer.murakumo.cloud"  :peer-spki "014bccd8…7038"  :completion-chars 4  :stop-reason "stop"
LEG storage-read        ADMITTED  :status 200  :host "kotobase.net"          :peer-spki "50602ad3…473e"  :digest "e3b0c442…b855"
LEG storage-absent      ADMITTED  :status 404  :refusal-reason :response-not-ok

$ kbb -M:cloud-live check --transport own    → exit 0
LEG model-resolve       ADMITTED  :status 200  :host "api.murakumo.cloud"    :peer-spki "ec7f258f…1af1"  :byte-count 497
LEG inference-liveness  ADMITTED  :status 200  :live? true                                               :byte-count 582
LEG inference           ADMITTED  :status 200  :host "infer.murakumo.cloud"  :peer-spki "014bccd8…7038"  :completion-chars 4  :stop-reason "stop"
LEG storage-read        ADMITTED  :status 200  :host "kotobase.net"          :peer-spki "50602ad3…473e"  :digest "e3b0c442…b855"
LEG storage-absent      ADMITTED  :status 404  :refusal-reason :response-not-ok
```

Three hosts, three pins, three separate TLS sessions per run, each presenting
the pin bound to the host it was reached at. The `inference` leg is a `POST`
carrying a JSON body; its response body was 1,275 octets on the own run and
1,499 on the platform run, because it is a language model's answer and not a
fixture. What is identical is what is supposed to be: every peer key, every
status, and the block digest.

### The two paths measure the same key

`aiueos.provider.cloud/spki-sha256-hex` hashes `PublicKey.getEncoded()`, the
JDK's re-encoding of the SubjectPublicKeyInfo. `tls.cert/spki-sha256-hex`
hashes `spki-der`, the exact octets that appeared in the certificate, never
re-encoded. Whether those agree is an assumption until somebody looks:
`both-transports-answer-the-same-question-the-same-way` runs one loopback
server through both transports and asserts the two digests are equal, and the
live receipts agree to the hex digit on all three real hosts.

### What an `[:ok …]` does not mean, measured rather than assumed

A certificate whose only `subjectAltName` is `IP:127.0.0.1`, reached as
`localhost`, was **accepted** by `aiueos.provider.cloud` on the `:jdk`
transport. So `java.net.http` with a custom `X509TrustManager` performs no
endpoint identification either, and the own path — which does not check a
server name in `:verify-chain` — is not weaker here. It was worth checking
before writing it down: had the platform path been checking, this change would
have removed a check while claiming parity.

### The suites

| | before | after |
|---|---|---|
| `kbb -M:test` | 341 tests / 8,645 assertions / 0 failures | **361 / 8,752 / 0** |
| `kbb -M:test-fleet` | 338 / 1,199 / 0 | **358 / 1,304 / 0** |
| `kbb -M:tcb-check` | `:valid? true :files 21 :external 6 :classpath 9` | **`:valid? true :files 22 :external 8 :classpath 9`** |
| `kbb -M:lint` | 0 errors / 56 warnings | **0 / 56** |

The **test** counts are exact and the **assertion** counts are not, which is
worth saying rather than rounding: `aiueos.provider.cloud-own-test` contributes
exactly 20 tests and 105 assertions, measured on its own, and the suite totals
above drift by two because `aiueos.tcp-seq-acceptable-parity-test` generates its
cases. A table that quoted one run's number as the number would go red on the
next run for a reason having nothing to do with this change.

Eleven of the twenty tests run **both** transports over the same server: a
behaviour proved on one and assumed on the other is the shape this ADR exists
to avoid.

The dependency suites, run from clean clones at the pinned commits:
`org-ietf-tls` `kbb -M:test:report` prints `RFC8448-VECTORS-COMPARED 43`,
`REFUSALS-EXERCISED 40` and `ASSERTIONS 550 passed, 0 failed, 0 errored`;
`kotoba-lang/http` `kbb -M:test` runs 69 tests / 268 assertions / 0
failures.

### The TCB grew, deliberately

`:files 21 → 22` and `:external 6 → 8`.

The file is `src/aiueos/provider/cloud_own.cljk`. It belongs there because it
holds the `:verify-chain` function, which **is** the peer decision on that path:
a change that returned `[:ok …]` without asking `grant.cloud/admit-peer` would
accept any peer, and nothing downstream would notice, because the handshake
would simply succeed.

The two coordinates are `org-ietf-tls` and `http`. They are what `java.net.http`
was, and unlike it they are content-addressed by a commit id rather than
carrying an `:assurance-gap`. **The platform entry stays.** `:jdk` is still the
default, so the JDK's TLS is still in the trusted computing base of this
machine, and removing the entry would make the inventory a record of an
intention. `:classpath` did not move, measured: git dependencies reach the
classpath as source directories, not jars.

## Both directions

Four deliberate faults, each injected on its own and reverted. In every case
the thing reported is the thing broken.

**One hex digit of a pin.** `infer.murakumo.cloud`'s key in the live policy
changed from `…4b997038` to `…4b997039`, nothing else touched. On
`--transport own` the **inference leg alone** went `REFUSED :peer-not-pinned`,
naming `:observed-spki "014bccd8…7038"` — the real key, next to the policy's
wrong one. The other four legs stayed ADMITTED. Gate exit **1**.

**`verify-chain` stops reading `admit-peer`'s answer** (`(if (cloud/allowed? v)`
→ `(if true`). Eight assertions failed, all of them the peer ones and all of
them on the `:own` row: `a-peer-outside-the-pin-set-is-refused-mid-handshake`,
`the-same-key-pinned-to-another-host-is-refused-mid-handshake`, and the direct
seam test. Nothing else moved.

**The ceiling stops reaching the wire layer** (`{:limits {:max-body-bytes
max-bytes}}` → `{:limits {}}`). A 65-octet body under a 64-byte ceiling came
back `:status 200` with a digest instead of `:response-too-large` with neither.
Two assertions, both in `the-body-ceiling-refuses-rather-than-truncates`.

**`fetch!` follows a `Location` header.** The 302 became a 200 and the server's
hit log became `["/ipfs/bafkrei…" "/elsewhere"]`. Two assertions, both in
`a-redirect-is-a-status-and-never-a-second-request`.

**The request headers travel onto the verdict** (one `assoc` in `judged`). The
credential test failed on **both** transports, which is the right blast radius:
that leak would not have been specific to the new path.

**An unreachable peer reports as an empty response** (`:request-failed` →
`{:status 0 :body-octets []}`). `a-request-that-could-not-complete-yields-no-status-and-no-digest`
failed with `(not (nil? 0))` — exactly the confusion the rule exists to prevent.

## Consequences

### Open, and worth naming plainly

- **Chain validation to a trust anchor does not exist on either transport.**
  `tls.cert/authenticate-peer` returns its own `:tls/not-checked` set and this
  code passes it through; the platform path's trust manager never had one to
  begin with. Pin-only trust is a real posture for a machine that talks to three
  authorities known before it boots, and it is not the same thing as validating
  a certificate.
- **The bare-metal profile still cannot use any of this.** ADR-0041 steps 2 and
  3 are untouched: no DNS stub resolver, no TCP stream. Step 1 closed the same
  day under ADR-0076, and the lease it obtains is recorded and consumed by
  nothing. Steps 4 and 5 are now answered as libraries — corrected in that
  ledger — and standing on the two rows that did not move.
- **`:jdk` is the default.** Changing it needs more than one operator's two runs.

### What the own transport cannot do

Measured or read off the implementation, not guessed:

1. **https only.** A plaintext URL is `:transport-scheme-unsupported`. Reaching
   one at all needs `grant.cloud`'s `:allow-insecure-origins` escape hatch, and
   with it the platform path fetches where this one refuses.
2. **No connection reuse.** One request, one TLS session, one TCP connection.
   Five legs is five full handshakes.
3. **No ALPN and no HTTP/2.** The wire layer refuses an `HTTP/2` version token
   rather than downgrading, so a server that requires it is unreachable.
4. **No session resumption, no 0-RTT, no `KeyUpdate`.** `tls.client` refuses a
   `key_update` rather than desynchronising its keys silently — right, and it
   means a server that rekeys mid-connection ends the exchange. Unreachable
   today only because connections are not reused.
5. **No proxy support.** `tls.transport.jvm/socket-transport` connects to a host
   and a port.
6. **No IPv6 literal hosts.** `kotoba.lang.http/parse-url` throws on
   `https://[::1]:443/x` — its host pattern excludes `:` — while
   `java.net.URI` parses it. Measured. Not reached today because all three
   authorities are named by DNS.
7. **No overall response deadline.** The read timeout bounds each read, not the
   exchange. A peer dripping one octet inside that timeout is bounded only by
   the wire layer's `:max-read-calls`, which defaults to 100,000.
8. **The primitives are the JDK's.** `tls.provider.jvm` and `java.net.Socket`.
   The claim is that the protocol left the platform, not that the platform did.
9. **`--transport` is a live-gate flag, not a per-call option.** Which stack
   this machine's bytes go through is a property of the machine; a caller able
   to override it per request would make a receipt's answer depend on who asked.

### What it buys

The one entry in the TCB inventory that could not be content-addressed on the
path a request actually takes is now, on that path, two commit ids. That is the
whole of it, and it is enough: an inventory whose largest entry is
`:assurance-gap :platform-tls-implementation-not-content-addressed` is an
inventory that has written down what it cannot check. This is one fewer of
those — on a transport nothing uses by default yet, which is the honest size of
the claim.
