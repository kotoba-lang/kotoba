# org-ietf-epp

[![CI](https://github.com/kotoba-lang/org-ietf-epp/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ietf-epp/actions/workflows/ci.yml)

**EPP** — the Extensible Provisioning Protocol (RFC 5730/5731/5734, plus the
RFC 3915 RGP extension) — as portable Clojure. Frames in, `srs` commands out;
`srs` results in, frames out. Named `org-<body>-<spec>` for the external spec it
implements, like this org's other IETF-RFC repos (`org-ietf-dns`,
`org-ietf-turn`, `org-ietf-ical`).

This is the door registrars push commands through. [`srs`](https://github.com/kotoba-lang/srs)
decides what happens to a domain; this library decides nothing — it parses,
authenticates, projects, and emits. A bug here can garble a response but cannot
change what the registry did.

```
registrar ──TCP──▶ epp.transport ──▶ epp.xmlns ──▶ epp.command ──▶ srs.core/execute
                    (RFC 5734          (resolve       (→ srs             │
                     framing)           prefixes)      command)          ▼
          ◀────────────────────── epp.response ◀──────────────── {:ok? … :events …}
```

## Modules

| ns | portability | role |
|---|---|---|
| `epp.xmlns` | `.cljc` | resolve XML namespace **URIs** to canonical keywords — see below |
| `epp.command` | `.cljc` | canonicalized frame → an `srs.core/execute` command map |
| `epp.response` | `.cljc` | `srs` result → response frame; the full RFC 5730 §3 result-code table |
| `epp.server` | `.cljc` | the session state machine: greeting, login, authorization, dispatch |
| `epp.transport` | `.cljc` | RFC 5734 length-prefixed framing, on plain byte vectors |

Every namespace is `.cljc` and there is **no socket layer here**. `epp.server/handle`
is `session + frame + registry + now → session + registry + response + events`, so
a JVM or Node listener is a loop around it, and a test is the same loop over a
vector of strings. That is why the session tests below are ordinary unit tests.

## The prefix is not the identity

The single thing this library gets right that hand-rolled EPP parsers usually do
not. All three of these are the same element:

```xml
<domain:create xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
<d:create      xmlns:d="urn:ietf:params:xml:ns:domain-1.0">
<create        xmlns="urn:ietf:params:xml:ns:domain-1.0">
```

XML namespaces are identified by URI; the prefix bound to a URI is the author's
free choice. A parser that matches on the literal string `domain:create` accepts
the first and silently fails on the other two — and registrars really do send
them. The failure is quiet: the frame parses as valid XML, matches nothing, and
comes back as "unknown command" to a registrar whose XML is correct.

`epp.xmlns/parse` resolves prefixes against the `xmlns` declarations actually in
scope (they are scoped and shadowable, so it is a walk with an environment, not a
lookup on the root) and rewrites every tag to a canonical keyword. An
unrecognized namespace keeps its own prefix rather than being dropped — an
extension this library does not implement should still be visible to a caller
that does.

## The session is the trust boundary

`srs.core/execute` takes a `:command/registrar` and checks that registrar
sponsors the object — but it has no way to know whether the caller *is* that
registrar. The session is the only thing that knows, because it is the only thing
that saw the password. So `epp.server` takes the registrar from the session and
**overwrites** anything the frame claimed:

```clojure
(assoc command :command/registrar (:session/registrar session))
```

A server that trusted the `clID` in the frame would let any authenticated
registrar act as any other.

`authenticate` is injected — `(fn [clID pw] -> boolean)`. Omitting it refuses
every login, which is the safe default: a server that authenticated everyone
because its operator forgot to pass a function is the failure mode worth
designing out.

## Decisions worth knowing about

**A host address with no `ip` attribute is v4, not a guess.** RFC 5732 §4.2
makes v4 the default. Inferring the family from the string would accept a v6
address sent without the attribute and file it under the wrong one — a
malformed frame silently stored as if it were fine. Recording what the frame
*said* is better than repairing it.

**A month period is refused, not rounded.** `<domain:period unit="m">18</…>` is
legal EPP. 18 months is not 1 year and is not 2, and a registry that rounds has
mispriced the registration in someone's disfavour. It comes back as 2306 with a
reason.

**The transfer `op` is on the core element, not the object mapping.** RFC 5730
§2.5 puts it on `<transfer op="…">`. Reading it from `<domain:transfer>` is why
some implementations treat every transfer as a request.

**RGP restore is an `<update>`, not a command.** RFC 3915 §4.1: requesting a
restore and filing the report are both `<update>` frames distinguished by an
attribute on an extension. `epp.command` reads the extension *before* the update
body, which is why `:domain/restore`, `:domain/restore-report` and
`:domain/update` can arrive as the same element.

**`clTRID` is echoed on the error path too.** EPP is pipelined; the client
transaction id is the only thing tying a response to its command (RFC 5730 §2.5).
Dropping it on errors — the usual omission, because the error path is written
second — makes exactly the failures you need to debug the ones you cannot
attribute.

**2304 carries the blocking statuses in an `<extValue>`.** A registrar can clear
its own `clientTransferProhibited` and cannot clear the registry's
`serverTransferProhibited`. Only the specific status says which, so it goes in
the machine-readable half of the response rather than only in the prose.

**A failed login answers 2501, not 2200.** RFC 5730 §2.9.1.1 has the server close
the connection; saying so in the code is what lets a client stop retrying on it.

**Commands before login are 2002, not 2200.** "Command use error" rather than
"authentication error" — the latter would tell an unauthenticated peer that the
command *would* have worked.

**The length prefix includes itself, and counts UTF-8 bytes.** RFC 5734 §4 says
so in one sentence, and off-by-four is the most common EPP interop bug; the two
directions are written next to each other in `epp.transport` so the `+ 4` and the
`- 4` cannot be maintained separately. Taking the length from the string rather
than its UTF-8 encoding truncates any frame containing a non-ASCII character —
an IDN registrant, a Japanese contact address — and only shows up once a
non-English registrar connects.

**An absurd declared length is refused before allocation.** The prefix is
attacker-controlled: a peer that sends `0xFFFFFFFF` and stops is asking a server
to allocate 4 GiB and wait. The read loop is the only place with the information
to refuse.

## Usage

```clojure
(require '[epp.server :as server] '[srs.core :as srs])

(def session (server/new-session {:server-id "srs.example"}))
(def registry (srs/empty-registry "com"))

;; the server speaks first (RFC 5730 §2.3)
(server/greeting session now)

(def r (server/handle session registry login-xml now
                      {:authenticate (fn [id pw] (check-credentials id pw))}))
;; => {:session … :registry … :response "<epp …>" :events []}

(server/handle (:session r) (:registry r) create-xml now {:authenticate …})
;; => :events [{:event/kind :domain/created :event/billable :create …}]
```

Over a socket, wrap it with `epp.transport`:

```clojure
(let [{:keys [frames rest]} (transport/decode-all buffer)]
  (doseq [f frames]
    (let [{:keys [response]} (server/handle session registry f now opts)]
      (write! (transport/encode response)))))
```

## Scope

- **In:** the domain object mapping (RFC 5731), session management (RFC 5730),
  TCP framing (RFC 5734), the RGP extension (RFC 3915), and `check`/`info`/
  `transfer query`.
- **Also in:** the host object mapping (RFC 5732), backed by `srs.host`. The
  greeting advertises `host-1.0` *because it can serve it* — a greeting is a
  contract, and advertising a mapping you cannot serve just means being sent
  commands you must then refuse.
- **Not yet:** the contact mapping (RFC 5733); a login asking for `contact-1.0`
  is refused with 2307 rather than accepted and failed later. Also absent:
  `<poll>` message queue semantics beyond parsing the command, and the
  secDNS-1.1 extension (see
  [`org-ietf-dnssec`](https://github.com/kotoba-lang/org-ietf-dnssec)).
- **Not here:** sockets and TLS. RFC 5734 requires TLS in production; that is the
  deployment's business and this library holds no credentials.

## Test

```
kbb -M:test
```

28 tests / 81 assertions. The command fixtures are the example frames from
RFC 5730/5731/3915 verbatim rather than frames this library generated — a parser
tested only against its own emitter agrees with itself and with nobody else.
