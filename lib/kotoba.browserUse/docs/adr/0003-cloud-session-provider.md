# ADR-0003: Browser Use Cloud is an injected provider

- Status: Accepted (2026-07-18)
- Supersedes: the Cloud exclusion recorded in ADR-0002

## Context

Cloud sessions add hosted lifecycle, task follow-ups, live preview, recordings,
messages and remote files. They require credentials and billable network calls,
but portable agent code must remain deterministic and usable from ClojureScript.

## Decision

`browseruse.cloud` implements the official Browser Use Cloud API v3 contract
through an injected synchronous HTTP transport. The core never reads environment
variables, performs I/O, or logs API keys. A host supplies JSON encoding, HTTP,
timeouts and credentials. Request failures expose method, relative path, status
and response data, never request headers.

The provider covers agent session create/get/list/delete/stop, task dispatch and
follow-up, bounded polling, live/recording URLs and message pagination. It also
models the separate raw Browser-as-a-Service create/get/list/stop/download
surface (including CDP URLs), and Profile CRUD. Agent session IDs and raw browser
IDs remain distinct in API names. POST retries require an explicit idempotency key; safe GET
and DELETE operations retry bounded transient statuses. No real Cloud request is
made by the test suite.

Proxy country/custom proxy configuration is passed through only on raw browser
creation. CAPTCHA policy is not implemented in this namespace.
