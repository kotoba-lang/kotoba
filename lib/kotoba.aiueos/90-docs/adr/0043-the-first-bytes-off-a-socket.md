# ADR-0043 — The first bytes off a socket, and the digest that judged them

Date: 2026-08-18

## Status

Accepted and executable for the hosted profile. It is the mechanism behind
ADR-0042's decisions. It does not advance ADR-0041's gap ledger steps 1–5 for
the bare-metal profile.

**Superseded in two places by ADR-0073** (2026-08-21), which should be read
first for anything about writing or about the real hosts. The provider is no
longer `GET`-only — it performs the `:post` and `:put` its plans emit, through
an injected credential seam — and it has now contacted `kotobase.net`, so this
ADR's closing line about the trust store being a recorded gap was answered by
ADR-0044 and the pins were measured by ADR-0073.

## Context

ADR-0042 gave the two cloud authorities a decision layer that nothing could
execute. A decision no provider consumes is a decision nobody has to obey, so
the question this closes is narrow and worth stating plainly: **can this
repository take bytes off a real socket, and does the digest check actually
refuse the wrong ones?**

Writing the provider surfaced something the decision layer had left open. The
allowlist in `aiueos.policy/net-url-allowed?` matches on **host**: it strips the
scheme and the port before comparing. An entry admitting `kotobase.net`
therefore admits *plaintext* to `kotobase.net` exactly as readily as TLS. For a
machine whose storage and inference authorities are both remote, plaintext is
not a degraded mode — it is a different threat model, and nothing in the stack
was distinguishing the two.

## Decision

### `aiueos.cloud` requires https, and says where the exception is

Every plan goes through one function that now checks two things: the transport,
then the allowlist. The escape hatch is `:aiueos.cloud/allow-insecure-origins`,
an explicit set of origin prefixes in **policy** — so a deployment reading
plaintext is visible in its own configuration, not hidden in the code. The
loopback test server is the only thing that uses it, and it is spelled out in
the test's policy where a reader will see it. The resolved murakumo endpoint is
held to the same rule.

### `aiueos.provider.cloud` reports what arrived and judges nothing

The provider takes an allowed plan, performs it, and reports status, byte
count, and the SHA-256 of the bytes it received. The comparison against the
digest the CID commits to stays in `aiueos.cloud/admit-block`. "What did I get"
and "is that what was asked for" are different questions, and the same code
answering both is how a client ends up agreeing with itself.

Three properties are mechanism here that would be holes anywhere else:

- **Redirects are not followed.** The allowlist checked the URL *we* chose, not
  the one the server names next. A followed 302 leaves the allowlist behind
  while still looking like a successful fetch — the murakumo alias redirect one
  layer lower.
- **The body is read against a ceiling**, defaulting to kotobase's own 4 MiB
  block limit. A response above it cannot be a block that store would have
  accepted, and reading further only lets a hostile endpoint decide how much
  memory this machine spends. The ceiling **refuses** rather than truncates: a
  truncated block hashes to something, and that something would be reported as
  a measurement.
- **A request that could not complete is not a response.** Timeouts and I/O
  failures produce `:aiueos.provider.cloud/error` and never a `:digest-hex`.
  Faults and deny reasons are different keys, so a caller can tell "there was
  nothing to decide about" from "the decision was no".

## Executable evidence

A real `com.sun.net.httpserver` on loopback, a real request, real SHA-256 over
what arrived. **11 tests, 29 assertions** in `aiueos.provider.cloud-test`;
`aiueos.cloud-test` grows to 28 tests as the transport rule lands. Together:
**38 tests, 103 assertions, 0 failures.**

What the server proves, that a fixture could not:

- a block whose bytes hash to its CID is admitted end to end, with one request
  at the path the CID names;
- **a gateway serving the wrong bytes is caught** — `:digest-mismatch`, with
  the observed digest being of what arrived;
- an origin outside the allowlist, and plaintext without the exemption, are
  refused with the server recording **zero hits**: the refusal happened before
  the socket, not after the response;
- a 302 is returned as a status and the redirect target is never requested.

**Both directions, shown.** Two mutations, each producing exactly the failure it
should and no other: following redirects fails only `a-redirect-is-not-followed`
(and its hit list grows the `/elsewhere` request, visible in the diff), and
widening the ceiling fails only
`a-body-past-the-ceiling-is-a-fault-not-a-measurement`.

Full suite: **554 tests, 9138 assertions, 19 failures** — the *same 19 test
names* as the unmodified tree. `kbb -M:tcb-check` is `{:valid? true :files
37 :external 6 …}`. Lint: no new findings.

## The TCB grew a platform entry

`src/aiueos/provider/cloud.cljk` is pinned like every other decision file, and
`java.net.http` is now recorded as external with the gap named:
**the machine's trust in the cloud is the JDK's default trust store**, which
this repository neither owns nor pins. For an OS whose storage and inference
authorities are both remote, that store is what stands between it and whatever
answers on the other end. Recorded rather than left implied.

## Remaining boundary

- **Loopback, plaintext, and one process.** No certificate was validated,
  because the exemption that let the test run is exactly the one that skips it.
  What is proved is the seam and the digest, not TLS.
- ~~**No write path.**~~ Closed by ADR-0073: `write-block!` performs the `PUT`.
  The credential it needs turned out to be a **bearer token**, not a CACAO —
  and this machine holds none, so the live write answers 401.
- **The bare-metal profile is untouched.** It still has no DHCP, DNS, TLS or
  HTTP client. This provider is the hosted profile's, exactly as ADR-0019 split
  boot authority from workload authority.
- **The allowlist is still host-scoped.** The https requirement is enforced in
  `aiueos.cloud`, not by the allowlist, so an entry alone still does not
  distinguish `kotobase.net:443` from `kotobase.net:8443`.

Next is the first request that leaves this machine: the same provider against
the real `kotobase.net` over TLS, which is where the trust store stops being a
recorded gap and starts being a decision someone has to make.
