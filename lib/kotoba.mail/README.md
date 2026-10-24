# mail

`mail` is the portable Kotoba mail model.

It is all `.cljc` and performs no network, SMTP, IMAP, filesystem, clock, or
secret access. Hosts provide effects through aiueos capabilities; this library
defines the deterministic data model for addresses, messages, drafts, send
effects, and receipts.

```text
mail = address + message + draft + send-effect + receipt + inbound + mailbox/thread
```

## Boundaries

| namespace | role |
|---|---|
| `mail.message` | addresses, message envelope, body parts, validation |
| `mail.draft` | draft lifecycle and send-effect creation |
| `mail.receipt` | provider-independent delivery receipts |
| `mail.inbound` | provider-independent representation of a received message |
| `mail.mailbox` | provider-independent mailbox, threads, labels, read/trash state and used-byte accounting. An entry may carry `:mailbox.message/sealed` — an opaque description of content the mailbox holds but cannot read — so that a sealed message can *be* a message here instead of being stored as a fabricated empty one. `search` cannot see inside a seal, and says so |

Sending and receiving are intentionally outside this repo. Use
`kotoba-lang/mailer` to map approved mail effects to a provider request; use a
host capability (Cloudflare Email Worker, SMTP server, IMAP poller, ...) to
parse the wire format into the plain map `mail.inbound/from-parts` expects.

## Example

```clojure
(require '[mail.message :as msg]
         '[mail.draft :as draft])

(def m
  (msg/message
   {:from "ops@example.com"
    :to ["alice@example.com"]
    :subject "Hello"
    :text "Hello Alice"}))

(draft/send-effect
 (draft/approve (draft/draft "d1" m) {:by "did:web:example.com"}))
```

## Tests

```sh
kbb -M:test
```
