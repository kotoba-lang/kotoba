# ADR-0007: CapSolver production adapter

- Status: Accepted
- Date: 2026-07-18
- Extends: ADR 0004

## Decision

`browseruse.capsolver` is the first production implementation of the portable
`CaptchaProvider` boundary. It maps reCAPTCHA v2/v3, hCaptcha, and Cloudflare
Turnstile to CapSolver proxyless token tasks, submits with `createTask`, and
polls with `getTaskResult`.

HTTP remains an injected capability. The JVM host is
`browseruse.capsolver-http/request!`; other hosts provide an equivalent
request function. The client key is captured by the provider and excluded from
jobs, results, audit history, and exception data. Provider error payloads are
redacted before they cross the adapter boundary.

CapSolver has no documented cancel-task operation. `-cancel!` therefore marks
the job abandoned locally; the bounded timeout remains owned by
`browseruse.captcha/solve!`.

Only authorized automation is permitted. The adapter does not weaken domain,
action, budget, or operator policies.

## Evidence

- `test/browseruse/capsolver_test.cljk`: task mapping, request contracts,
  polling, local cancellation, and secret-redaction tests.
- `test/browseruse/captcha_test.cljk`: DOM `data-sitekey` extraction.
- `examples/capsolver_dry_run.cljk`: credential-free request-shape example.
- CapSolver official `createTask`, `getTaskResult`, and Turnstile task docs.
