# ADR-0001 — org-ietf-imap architecture: a real IMAP4rev1 client, not a curl shell-out

- Status: Accepted
- Date: 2026-07-06
- Context tags: imap, rfc3501, portable-cljc, vendor-client
- Builds on: `kotoba-lang/com-cloudflare` (injectable-transport pattern,
  adapted from one-shot HTTP to a stateful line protocol),
  `gftdcojp/local-manimani` `docs/adr/0022-email-sms-channels-mobile.md`
  (the curl-based IMAP ingress this library replaces)

## Decision

Give IMAP the same "one tested boundary, injectable transport" treatment
`com-cloudflare`/`com-gmail` give their protocols: `imap.transport` (a
4-fn `Transport` -- write!/read-line!/read-n!/close!, real `SSLSocket` by
default), `imap.protocol` (pure command construction + response parsing),
`imap.client` (the stateful session driver).

## Why a real client instead of continuing to shell out to curl

`local-manimani`'s `curl-imap-fetch` worked but had two real costs: (1) no
way to mark a message read after a decision was made on it (curl's `--url
imaps://...` is fetch-only; `STORE` needs an actual IMAP session), and (2)
every other project wanting IMAP access would re-derive the same curl
incantations from scratch. A real client closes both gaps once.

## Why a scripted fake Transport instead of a live IMAP server in CI

IMAP's literal syntax (`{n}` byte-counted payloads embedded mid-response)
means the response grammar genuinely depends on byte counts, not just line
splitting -- exactly the kind of protocol detail that's easy to get subtly
wrong and hard to notice without a networked round-trip. Scripting exact
wire sequences (`test/imap/fake_transport.cljk`) forces
`imap.client`'s read-loop to prove it handles a literal appearing mid-FETCH-
response correctly, without needing a real mailbox or network access in CI.

## Module boundaries

```
transport  Transport protocol (write!/read-line!/read-n!/close!) + real SSLSocket impl (JVM-only)
protocol   pure: command/quote-string, tagged-completion?/completion-status, literal-size,
           search-uids, parse-header-block (RFC 2822 header unfolding)
client     connect!/login!/select!/search-unseen!/fetch-header!/list-unseen-headers!/
           mark-seen!/logout! -- the read-until-tagged-completion loop over an injected Transport
```

## Non-goals

- IDLE, SASL beyond plaintext LOGIN, general MIME body parsing, arbitrary
  FETCH data items -- this is scoped to "ingest unseen mail headers, mark
  as seen once handled," not a general-purpose mail library.
- Gmail-specific IMAP extensions (`X-GM-LABELS` etc.) -- this client is
  intentionally protocol-generic. A Gmail integration wanting label
  operations should use `kotoba-lang/com-gmail`'s REST API instead, per
  `90-docs/adr/2607061503` in the `com-junkawasaki/root` superproject.

## Consequences

- `gftdcojp/local-manimani`'s IMAP channel (any account, including Gmail
  via an app password) can depend on this library instead of shelling out
  to curl, and gains `mark-seen!` -- a capability curl-imap-fetch never had.
- Any future project needing "ingest unseen IMAP mail" gets a tested
  starting point instead of re-deriving IMAP wire handling from scratch.
