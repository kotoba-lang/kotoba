# org-ietf-imap

A genuine IMAP4rev1 (RFC 3501) client -- no `curl` shell-out, no
`jakarta.mail`. Zero-dep `.cljc`, an injectable transport for testing, real
`SSLSocket` I/O by default.

**Name provenance**: follows this org's `org-<standards-body>-<spec>` naming
convention (see `org-ietf-turn`, `org-ietf-ical`, `org-w3-aria`) -- IMAP is
an IETF specification (RFC 3501), hence `org-ietf-imap`.

## The session as a Kotoba application

`kotoba/imap/session.kotoba` is the mailbox-opening session — greeting,
CAPABILITY, the strongest authentication the server advertised, SELECT (or
EXAMINE), and the fold of everything the server said on the way in,
**including UIDVALIDITY** (RFC 3501 §2.3.1.1: lose it and a cached UID names
a different message, or none). It is written as a Kotoba guest (`init` /
`step` / `closed` / `outgoing`) and **no credential reaches it**: it is told
whether a password exists, never what it is, and names `:credential/login`
where the host writes one. The socket, TLS and base64 stay here in `.cljc`,
which remains the oracle `test/imap/session_kotoba_parity_test.cljk` compares
against. See that module's header for the guest/host line and the boundaries
it records.

## Why this exists

`gftdcojp/local-manimani`'s email channel (ADR-0022) fetched mail by
shelling out to `curl --url imaps://...`, deliberately avoiding a real IMAP
client to stay dependency-free. That worked for "search UNSEEN, fetch a
few headers" but had no way to mark a message read after a decision was
made on it (a gap ADR-0022 itself documented) and can't be reused by any
other project without re-deriving the same curl incantations. This library
is a real, portable, independently-tested IMAP client -- fill the same
"one tested boundary instead of ad hoc shell-outs" role `com-cloudflare`/
`com-gmail` play for their protocols, for IMAP specifically. It is
deliberately **not** Gmail-specific: any IMAP account works, and a
Gmail-via-REST-API integration should use `kotoba-lang/com-gmail` instead
(see that library's README) rather than this one -- they're separate
channels, not alternatives for the same job.

## Design

```text
imap.transport -- Transport protocol (write!/read-line!/read-n!/close!) + real SSLSocket impl (JVM-only)
imap.protocol  -- pure command construction + response parsing (tags, literals, SEARCH, header blocks)
imap.client    -- the session driver: connect!/login!/select!/search-unseen!/fetch-header!/mark-seen!/logout!
```

`imap.protocol` has zero I/O -- every command-building and response-parsing
function is pure and tested without a socket. `imap.client` drives the
read-until-tagged-completion loop over an injected `Transport`, so it's
tested the same way (`test/imap/fake_transport.cljk`, a scripted in-memory
`Transport`) -- never only against a live server.

## RFC 3501 coverage

| area | commands |
|---|---|
| session | CAPABILITY, STARTTLS (injected upgrade), LOGIN, AUTHENTICATE PLAIN / XOAUTH2, LOGOUT |
| mailboxes | SELECT, EXAMINE, LIST, STATUS, CREATE |
| reading | UID SEARCH (any criteria), UID FETCH — header fields, whole message, FLAGS / INTERNALDATE / RFC822.SIZE |
| writing | UID STORE (`+FLAGS`/`-FLAGS`/`FLAGS`, any flag), UID COPY, UID MOVE (RFC 6851, with COPY+`\Deleted` fallback), EXPUNGE, APPEND |
| waiting | IDLE (RFC 2177) |
| responses | untagged EXISTS / RECENT / EXPUNGE / FLAGS / CAPABILITY / LIST / STATUS / FETCH, `[response codes]`, flag lists |

**`SELECT` returns UIDVALIDITY** (RFC 3501 §2.3.1.1), which is the one a
client cannot afford to drop: a UID means nothing without the UIDVALIDITY it
was issued under, so a client that caches UIDs across sessions and never reads
it is correct right up until a server reissues one — after which every stored
UID names a different message, or none, silently.

**Not implemented**: CONDSTORE/QRESYNC, NAMESPACE, ACL, SORT/THREAD, BINARY,
COMPRESS, BODYSTRUCTURE/ENVELOPE parsing, sequence-number (non-UID) commands,
SASL mechanisms beyond PLAIN and XOAUTH2.

### Reads are binary strings

Everything this library reads off the wire is decoded **ISO-8859-1**, one
byte per character, which is exactly the input contract `org-ietf-mime`
states. A message is bytes and its parts routinely disagree about what those
bytes mean — a UTF-8 body beside an ISO-2022-JP subject beside a PDF — so
decoding a literal as UTF-8 destroys every part that was not UTF-8, quietly,
producing U+FFFD rather than an error. This transport did decode as UTF-8;
the symptom was a Japanese body arriving as mojibake that looked like a bug
in the MIME parser two libraries away.

Command writes stay UTF-8: a command is text this library composed, not
bytes it received. `append!`'s literal length is therefore a UTF-8 byte
count.

**Messages are not parsed here.** `fetch-message!` returns the bytes the
server sent, and [`kotoba-lang/org-ietf-mime`](https://github.com/kotoba-lang/org-ietf-mime)
turns those into headers, parts, attachments and decoded text:

```clojure
(-> (client/fetch-message! session 5) :raw mime/parse mime/message-parts)
```

For one commit this library carried its own `split-message` and
transfer-encoding decoder instead — a second, worse copy of a library that
already existed in this org, and one that got multipart wrong (it returned the
raw parts) where `mime.parse` gets it right: `multipart/alternative` orders its
parts worst-to-best, so the *last* match is the message somebody actually sent.

## Usage

```clojure
(require '[imap.client :as client])

(def session (client/connect! "imap.gmail.com"))
(client/login! session "you@gmail.com" "app-password")
(client/select! session "INBOX")

(client/list-unseen-headers! session {:limit 20})
;; => [{:from "..." :subject "..." :date "..." :message-id "..." :uid 5} ...]

;; Displaying a mailbox rather than triaging one: the newest N messages,
;; bodies included, oldest of those first.
(client/list-recent! session {:limit 40})
;; => [{:uid 5 :raw "From: ..." :flags #{:seen} :size 4242} ...]
;;    parse :raw with org-ietf-mime

(client/fetch-message! session 5)           ; one whole message, BODY.PEEK
(client/search! session "SINCE 1-Jan-2026") ; any RFC 3501 search key

(client/mark-seen! session 5)   ; after a decision has actually been made on message 5
(client/store-flags! session 5 :add [:flagged])  ; any flag, all three modes
(client/logout! session)
```

An OAuth-connected mailbox, with the folders and the Sent copy:

```clojure
(-> (client/connect! "imap.gmail.com")
    (client/capabilities!)
    (client/authenticate-xoauth2! "you@gmail.com" access-token)
    (client/examine! "INBOX"))          ; read-only: cannot set \Seen by accident
;; => session, with :mailbox {:uidvalidity 3857529045 :uidnext 4392 :exists 172 ...}

(client/list-mailboxes! session)         ; \Sent is found, not guessed at
(client/append! session "[Gmail]/Sent Mail" raw-message {:flags [:seen]})
```

## Tests

```sh
kbb -M:test
```

No live server or network access required -- every `imap.client` test
injects `imap.fake-transport`, a scripted in-memory `Transport`.
