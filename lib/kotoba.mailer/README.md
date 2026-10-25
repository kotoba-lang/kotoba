# mailer

`mailer` maps approved `mail/send` effects to provider requests.

It is portable `.cljc`. It does not perform HTTP, SMTP, SES, Resend, DNS, secret,
clock, or retry effects directly. A host or aiueos provider executes the returned
request and feeds the provider result back into `mail.receipt`.

```text
mail/send effect -> provider request -> host capability -> mail receipt
```

## Providers

Initial provider request builders:

| provider | boundary |
|---|---|
| `:resend` | HTTP `POST https://api.resend.com/emails` |
| `:smtp` | host SMTP relay capability |
| `:ses` | host AWS SES capability |

## What it refuses

`request` builds nothing for a message it cannot express. `mail.message`
calls a message valid as soon as it has any part, so a message carrying only
parts this wire format has no field for reaches `mailer` looking well-formed;
building the request anyway would have instructed the host to send an email
with no body and report success.

Body parts are matched on the media type alone. `text/plain` and
`text/plain; charset=utf-8` are the same type -- RFC 2045 puts the charset in
the value, not in the type's identity.

## Tests

```sh
kbb -M:test
```
