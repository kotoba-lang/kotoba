# ADR-0001 — org-ietf-smtp architecture: a real SMTP client, not a curl shell-out

- Status: Accepted
- Date: 2026-07-06
- Context tags: smtp, rfc5321, portable-cljc, vendor-client
- Builds on: `kotoba-lang/org-ietf-imap` (sibling library, same transport-
  injection shape), `gftdcojp/local-manimani`
  `docs/adr/0022-email-sms-channels-mobile.md` (the curl-based SMTP egress
  this library replaces)

## Decision

Give SMTP the same "one tested boundary, injectable transport" treatment
as `org-ietf-imap`: `smtp.transport` (write!/read-line!/close!, real
`SSLSocket` by default), `smtp.protocol` (pure command/response/MIME/
dot-stuffing logic), `smtp.client` (the session driver).

## Why not share code with org-ietf-imap

Both libraries inject a small `Transport` protocol over a TCP+TLS socket
and both read line-oriented responses, so the shapes look similar. But the
response *grammars* are different in a way that matters: IMAP's tagged
completion detection and literal (`{n}`) handling has no SMTP analogue,
and SMTP's multi-line `250-`/`250 ` continuation marker has no IMAP
analogue. `read-n!` (IMAP literals) doesn't exist in `smtp.transport` at
all -- SMTP has no binary literals. Sharing a "transport" abstraction
across the two would mean carrying dead capability in one direction or the
other. Per this org's `2606272330` grab-bag-library precedent, kept
independent.

## Module boundaries

```
transport  Transport protocol (write!/read-line!/close!) + real SSLSocket impl (JVM-only, port 465)
protocol   pure: response-line (multi-line-aware), command, dot-stuff, mime-message, base64
client     connect!/ehlo!/auth-login!/send-mail!/quit! -- the read-until-final-line loop
```

## Non-goals

- STARTTLS (this client only does implicit TLS on port 465, matching this
  org's existing `MANIMANI_SMTP_URL=smtps://...:465` convention) -- add it
  if a target server needs port 587 instead.
- AUTH PLAIN / XOAUTH2, multi-recipient sends in one call, attachments/
  multipart MIME -- add these when a real caller needs them.

## Consequences

- `gftdcojp/local-manimani`'s email egress (any SMTP account, including
  Gmail via an app password) can depend on this library instead of
  shelling out to curl.
- Any future project needing "send one plain-text email" gets a tested
  starting point instead of re-deriving SMTP wire handling from scratch.
