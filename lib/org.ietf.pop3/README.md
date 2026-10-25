# org-ietf-pop3

A genuine POP3 (RFC 1939) client — no `curl` shell-out, no
`jakarta.mail`. Zero-dep `.cljc`, an injectable transport for testing, real
`SSLSocket` I/O (implicit TLS, port 995) by default.

**Name provenance**: follows this org's `org-<standards-body>-<spec>` naming
convention (see `org-ietf-imap`, `org-ietf-smtp`, `org-ietf-mime`) — POP3 is
an IETF specification (RFC 1939), hence `org-ietf-pop3`.

## The session as a Kotoba application

`kotoba/pop3/session.kotoba` is the maildrop-listing session — greeting,
CAPA, the strongest authentication the server advertised, STAT, LIST, UIDL,
QUIT — written as a Kotoba guest (`init` / `step` / `closed` / `outgoing`).
**No credential reaches it**: it is told whether a password exists, never
what it is, and it names `:credential/pass` where the host writes one. The
socket, TLS, base64 and MD5 stay here in `.cljc`, which remains the oracle
`test/pop3/session_kotoba_parity_test.cljk` compares against. See that
module's header for the guest/host line and the two design decisions it
records.

## Why this exists

The third of the three protocols a mailbox is actually reached over, and the
one that was missing. `org-ietf-imap` covers IMAP and `org-ietf-smtp` covers
submission; an account that offers neither — and plenty still offer only
POP3, particularly ISP and legacy hosting mailboxes — could not be connected
by anything in this workspace at all.

It is deliberately **not** a lesser IMAP. POP3 answers a different question
(*"what is in the maildrop right now"*), and the design notes below are about
the ways that difference bites.

## Design

```text
pop3.transport -- Transport protocol (write!/read-line!/close!) + real SSLSocket impl (JVM-only),
                  implicit TLS on 995 and cleartext on 110 for STLS
pop3.protocol  -- pure: +OK/-ERR parsing, command building, byte-unstuffing, LIST/UIDL/CAPA
                  listings, APOP digest, SASL payloads
pop3.client    -- the session driver: connect!/capabilities!/stls!/authenticate!/stat!/
                  list-messages!/retrieve!/top!/delete!/quit!
```

`pop3.protocol` has zero I/O — every command-building and response-parsing
function is pure and tested without a socket. `pop3.client` drives the
read-until-terminator loop over an injected `Transport`
(`test/pop3/fake_transport.cljk`, a scripted in-memory `Transport`), so it is
tested the same way — never only against a live server.

## RFC coverage

| area | commands |
|---|---|
| session | connect (implicit TLS 995, or cleartext 110), CAPA (RFC 2449), STLS (RFC 2595), NOOP, QUIT |
| auth | USER/PASS, APOP (RFC 1939 §7), AUTH PLAIN and XOAUTH2 (RFC 5034), and `authenticate!` which picks the strongest offered |
| maildrop | STAT, LIST, UIDL, RETR, TOP, DELE, RSET |

**Not implemented**: SASL beyond PLAIN/XOAUTH2, and message parsing — `retrieve!`
returns the bytes the server sent, and
[`kotoba-lang/org-ietf-mime`](https://github.com/kotoba-lang/org-ietf-mime)
turns those into headers, parts, attachments and decoded text.

## Three things POP3 gets wrong that a client has to get right

**Message numbers do not survive the session.** They are assigned per session
and renumber whenever anything is deleted. The UIDL (§7) is the only
identifier that persists, so `list-messages!` joins LIST and UIDL and returns
both — a client deciding what it has already downloaded keys on `:uid`, and
`:number` is good only for naming a message to *this* session's RETR. A client
that caches numbers will, after one deletion, attribute every later message to
the wrong one.

**Reading is not deleting.** POP3's historical default was to remove the
server's only copy as a side effect of reading it, which destroys the mailbox
for every other client the account is opened in. `retrieve!` does not delete
and nothing here deletes implicitly; `delete!` exists and marks, and the
maildrop is not actually changed until `quit!` enters UPDATE state — `RSET`
before then is POP3's only undo.

**QUIT is not a courtesy.** It is what releases the maildrop lock. A client
that drops the socket instead leaves the mailbox locked until the server times
the session out, and every other client is refused in the meantime.

## Usage

```clojure
(require '[pop3.client :as client])

(-> (client/connect! "pop.example.com")
    (client/capabilities!)
    (client/authenticate! {:user "you@example.com" :password "app-password"})
    (doto (-> client/stat! prn))          ; {:count 2 :size 520}
    (doto (-> client/list-messages! prn)) ; [{:number 1 :size 120 :uid "whqtswO00"} ...]
    (doto (-> (client/retrieve! 1) prn))  ; the raw message, for org-ietf-mime
    client/quit!)                         ; releases the lock

;; An OAuth grant, and a cleartext session upgraded in place:
(-> (client/connect! "outlook.office365.com" {:tls? false :port 110})
    (client/stls! upgrade-fn)             ; re-reads CAPA, per RFC 2595 §4
    (client/authenticate! {:user "you@example.com" :access-token token}))
```

## Tests

```bash
kbb -M:test    # 26 tests, 53 assertions
kbb -M:lint
```

Including RFC 1939 §7's own worked APOP example, which is the only way to
pin that the digest is over timestamp-then-secret in that order.

## License

Apache-2.0.
