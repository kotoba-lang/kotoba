# org-ietf-mime

**Raw RFC 5322 message → the map `kotoba-lang/mail` already takes.**

The layer that did not exist. `kotoba-lang/mail` models a received message and
says so explicitly in its own README: *"Sending and receiving are intentionally
outside this repo… use a host capability to parse the wire format into the
plain map `mail.inbound/from-parts` expects."* Every host capability that could
produce one — a Cloudflare Email Worker, an SMTP server, an IMAP poller — hands
over raw bytes. This library is the missing middle (ADR-2607263000 D8 in
`com-junkawasaki/root`).

Named for this org's `org-<standards-body>-<spec>` convention, alongside
`org-ietf-smtp` (RFC 5321) and `org-ietf-imap` (RFC 3501). Those two are
transport *clients*; this is the message format they carry — RFC 5322 (message
syntax), RFC 2045–2047 (MIME, transfer encodings, encoded-words), RFC 2231
(parameter continuations and charset-tagged values), RFC 8601
(Authentication-Results).

```clojure
(require '[mime.parse :as mime])

(-> raw-message-binary-string
    mime/parse
    mime/message-parts)
;; => {:from "jun@example.com"
;;     :to ["alice@example.com"]
;;     :subject "日本語"          ; =?UTF-8?B?…?= decoded
;;     :text "hello" :html nil
;;     :spf :pass :dkim :fail :dmarc :none
;;     :attachments [{:filename "report.pdf" :content-type "application/pdf"
;;                    :size 13 :bytes "…"}]
;;     :headers {…} :message-id "<abc@example.com>" :date "…"}
```

That map is exactly `mail.inbound/from-parts`' argument, minus `:provider` and
`:provider-message-id`, which are the host's to supply. This library does not
depend on `kotoba-lang/mail` — it parses, that one models, and a parser
depending on a model it never calls is a dependency for nothing. The shape is
the contract.

Pure `.cljc`, zero dependencies. **The suite runs green on both the JVM and
ClojureScript** — 20 tests / 71 assertions, same file, both hosts.

## The input contract

Every function takes a **binary string**: the raw bytes decoded
one-byte-per-character (latin-1), so character *n* is byte *n*. **Not** a UTF-8
decode of the message.

```clojure
;; JS   (new TextDecoder "latin1")  ; NOT "utf-8"
;; JVM  (String. bytes StandardCharsets/ISO_8859_1)
```

A message is bytes, and its parts routinely disagree about what those bytes
mean — a UTF-8 body next to an ISO-2022-JP subject next to a PDF. Decoding the
whole message as UTF-8 up front destroys every part that was not UTF-8, and
does it quietly: you get U+FFFD, not an error. So the wire form stays
byte-per-char until the headers say what each part is.

## What it gets right that a naive parser does not

- **`multipart/alternative` takes the LAST alternative**, not the first. RFC
  2046 §5.1.4 orders parts worst-to-best; taking the first is the classic bug
  that shows a plain-text fallback instead of what the sender actually wrote.
- **Commas inside quoted display names are not list separators.**
  `"Doe, John" <j@e.com>, a@e.com` is two recipients, not three. Splitting on
  commas breaks exactly the addresses whose display name is surname-first.
- **Adjacent encoded-words lose the whitespace between them** (RFC 2047 §6.2).
  That is how a long Japanese subject split across several words rejoins
  without spurious spaces. Whitespace next to ordinary text is kept.
- **Semicolons inside quoted parameters are not separators**, so a
  `boundary="=_a;b_="` survives.
- **Folded headers rejoin**, bare-LF messages parse (the spec says CRLF; every
  unix pipe says LF), preamble and epilogue around a multipart are ignored, and
  a `multipart/*` with no boundary keeps its body as one text part instead of
  losing the message.
- **Malformed input degrades rather than throws.** A bad `=` escape stays as
  written, a truncated UTF-8 sequence becomes U+FFFD, an unparseable address is
  carried through with the raw text as `:address`. A dropped recipient is worse
  than a malformed one a validator can reject.

## Charsets it cannot do alone

UTF-8, US-ASCII and ISO-8859-1 decode here. **Everything else needs a decoder
injected** — pass `{:decoder (fn [charset binary-string] …)}`:

```clojure
(mime/parse raw {:decoder (fn [cs s] (.decode (js/TextDecoder. cs) (bytes-of s)))})
```

The rest of the world's charsets are lookup tables and, for ISO-2022-JP, a
stateful escape machine. Reimplementing those inside a pure library would be
both large and worse than the host's own `TextDecoder`/`Charset`, which are
already correct and already present. `mime.codec/decodable?` tells a caller
which case it is in, so "this subject needs a decoder I was not given" is
detectable rather than something you discover from mojibake.

## Test

```sh
kbb --backend sci --classpath "src:test" scripts/run-tests.cljk   # ClojureScript
kbb -M:test                                     # JVM
```
