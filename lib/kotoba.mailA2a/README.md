# MailA2A

**A store-and-forward email binding for A2A v1.0, with x402 payment objects and
MLS-protected groups.**

MailA2A lets a bot use an ordinary Internet mailbox as an A2A endpoint. It does
not invent a second mail system or a new agent data model. It maps the A2A task
lifecycle onto RFC 5322 threads and MIME parts, carries the transport-neutral
x402 v2 objects in the protected JSON body, and uses existing end-to-end
security formats:

- S/MIME 4.0 or OpenPGP/MIME for authenticated confidential one-to-one mail;
- `message/mls` (RFC 9420) for asynchronous groups with forward secrecy and
  post-compromise security;
- SMTP/IMAP/JMAP or provider APIs only as delivery and mailbox access layers.

Status: **Experimental community specification, binding version 1.0.** It is
designed as an A2A custom protocol binding but is not an official A2A binding.
The upstream proposal is [a2aproject/A2A issue #2191](https://github.com/a2aproject/A2A/issues/2191).

Normative specification: [spec/v1.md](spec/v1.md)  
Machine schema: [schema/envelope-v1.schema.json](schema/envelope-v1.schema.json)  
Published binding URI: <https://kotoba-lang.github.io/mail-a2a/spec/v1/>

## Why this exists

There are strong pieces, but no current standard combines them:

- FIPA's abstract architecture explicitly allowed SMTP agent addresses, but
  did not define today's A2A task model, x402, or modern group cryptography.
- A2A v1.0 defines a transport-neutral operation and data model and permits
  custom bindings, but its standard bindings are HTTP/JSON, JSON-RPC, and gRPC.
- ECMA-430 NLIP standardizes agent interaction and has HTTP, WebSocket, and AMQP
  bindings, not an Internet Message Format/MIME binding.
- x402 v2 separates its objects from transport, but its canonical deployed
  mapping is HTTP 402 plus headers.
- MIME, S/MIME, OpenPGP/MIME, and MLS solve message packaging and cryptography;
  they do not define an agent task lifecycle or payment negotiation.

MailA2A fills only that binding gap.

## Boundaries with nearby repositories

| repository | responsibility |
|---|---|
| `kotoba-lang/mail` | portable address, message, draft, mailbox, and receipt model |
| `kotoba-lang/org-ietf-mime` | raw RFC 5322 and MIME parsing |
| `kotoba-lang/org-ietf-mls` | RFC 9420 cryptographic and group-state primitives |
| `kotoba-lang/mail-a2a` | A2A operation, thread, payment, security-profile, and ordering contract over mail |

No SMTP client, mailbox credential, wallet, settlement engine, or MLS cipher is
implemented here. Hosts inject those effects.

## Reference validator

The portable `.cljc` reference code validates the protected envelope and event
ordering. It intentionally does not parse MIME or perform cryptography.

```clojure
(require '[mail-a2a.core :as mail-a2a])

(mail-a2a/validate-envelope
 {:mail-a2a/version "1.0"
  :a2a/version "1.0"
  :kind :request
  :operation :message/send
  :message-id "urn:uuid:018f..."
  :sequence 0
  :final? false
  :payload {:message {:messageId "018f..." :role "ROLE_USER" :parts []}}})
;; => {:ok? true :errors []}
```

## Verification

```sh
kbb -M:test
kbb --backend sci --classpath "src:test" scripts/run-tests.cljk
```

Apache-2.0.
