# ADR-0001: Native Human Approval Boundary

- Status: Accepted

## Context

Agents can navigate a page safely but must not silently accept terms or create
external accounts. A browser-only confirmation is easy to miss and couples the
approval policy to one UI implementation.

## Decision

`hil.core/IHumanApproval` is the host boundary for irreversible or legally
meaningful actions. The default macOS adapter uses a native `display dialog`
with `Approve` and `Reject`; `Reject` is the default button. The request shows
only a short summary, action, and optional impact.

Input is opt-in and exceptional. `:input-label` may request one short,
non-secret value; labels mentioning passwords, secrets, tokens, API keys, MFA,
OTP, or codes are rejected by the shared contract. Normal approval requests
therefore require no typing at all.

## Consequences

The same HIL contract can drive macOS alerts, web dialogs, chat cards, or
another host UI. Agents receive an explicit decision and may continue only
after `:approved`. Credentials, screenshots, and arbitrary page content never
belong in an approval request.
