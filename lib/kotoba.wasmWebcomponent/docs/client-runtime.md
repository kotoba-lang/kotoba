# Canonical client runtime host

Tracking: [JUN-14](https://linear.app/kotobalabs/issue/JUN-14).
Source: `src/kotoba-client-runtime.js`; styling: `src/kotoba-client-consent.css`.
Products import / copy these exact browser assets and pin revision / digest.
No build step or Node / JVM / NBB runtime is required. Product-local validators
and approval brokers are not substitutes for this implementation.

## Trusted shell and operation authority

The verified host shell owns its document, publisher pins, eligibility,
broker and supported browser handlers. Do not run arbitrary untrusted app
JavaScript in that realm. Apps receive only bounded invocation.

`createClientConsentHost()` provides a canonical modal displaying the service,
operation, endpoint / action, method, path, query, data categories and redirects.
A direct trusted MouseEvent on Allow approves one invocation; synthetic
clicks, forged handles and a true-returning callback do not. Denial / dismissal
sends no request. Eligibility starts empty and is not persisted user consent.

`createClientOperationBroker` takes `runtime`, `requestedCapabilities`,
`approvedOperations` (host eligibility ceiling, not consent),
`hostSupportedOperations` (triples of capability / service / operation), and
the canonical `consentHost`. `invoke({capability,service,operation}, payload)`
obtains fresh consent even after a previous successful invocation.
Legacy `confirmOperation` / `serviceAdapters` options throw: products must
migrate rather than fall back to a product-local callback or HTTP transport.

## HTTP scope and browser APIs

An operation declares `capability`, `service`, `operation`,
`consent: 'each-operation'`, `data-categories` and `endpoint`.
HTTP endpoints declare an HTTPS origin and fixed method / path, or a bounded
route set with allowed query names / fixed values and resource templates or
prefixes. Unknown / duplicate queries, encoded path tricks, credentials,
non-HTTPS services and app-origin endpoints are refused.

HTTP payload is `{input, init}` with a URL / Request and Fetch options.
The broker captures the exact request before consent, uses browser fetch,
omits ambient credentials, and sets no-referrer. Mutable bodies are copied
with a 16 MiB / five-second bound. Oversized or unfinished streams fail closed.
`prepareClientOperationRequest` exposes that preflight without authority or
transport. It never sends a request or grants consent.

Redirects default to error. Declared bounded HTTPS redirect origins require
GET / HEAD and fixed query values. The final Fetch response origin is checked;
unverifiable / opaque redirects are refused. Live redirect delivery is not
qualified by the current fixture run.

Browser-native service effects use `endpoint: {origin: 'https://service.example',
'browser-action': 'push/subscribe'}` with the same service / data declaration.
The trusted host supplies `browserAdapters[service][operation]`, enforcing the
concrete API and bounded parameters. A missing handler fails before consent.
Parameters must be plain bounded JSON, copied before the modal. Browser
permission does not approve a subsequent service request. The fixture's local
counter handler is not a PushManager implementation or permission test.
Do not represent local node control using a fake HTTPS origin.

## Artifact admission and guest boundary

`artifact: {revision: '<40 lowercase hex Git SHA>', sha256: '<64 lowercase hex>',
'max-bytes': 123456}` declares a bounded read-only artifact operation.
Download requires its own operation approval, followed by digest verification
before an immutable verified Blob is returned. Nothing executes automatically.
`verifyClientArtifact(bytes, declaration)` performs the same check on existing
bytes. `verifySignedClientDescriptor` verifies exact descriptor bytes using
WebCrypto Ed25519 and a host-pinned publisher key, revision and digest, then
validates the descriptor. The installer establishes pins independently of
guest assertions. Ephemeral fixture keys are not production trust roots.
Model download consent never grants remote inference.

`mountRestrictedClientApp` accepts only branded verified self-contained HTML,
uses an opaque-origin `sandbox="allow-scripts"` iframe, restricting child CSP
and a MessageChannel. Eligibility / handlers stay in the trusted host.
Guest text responses are bounded to 1 MiB / 30 seconds. The parent must retain
restrictive CSP / frame navigation policy and explicitly admit pinned guest
scripts; the child cannot widen its parent CSP. The fixture proves parent-DOM
and direct-fetch refusal, not exhaustive isolation of every navigation,
Worker or native browser API. General multi-file packaging remains open.

## Static policy and evidence

`clientRuntimeConnectSrc` derives only declared service / redirect origins,
without implicit app-origin access. No operations gives `connect-src 'none'`.
It is one CSP directive, not a full server policy or deployment.
`applyOfflineClientPolicy` adds a restricting offline document policy.
The app origin remains static-only; direct services are separate endpoints.

The [2026-10-23 receipt](evidence/client-runtime-browser-20261023.json) records
42 automatic checks and three interactive checks: denial with no fetch, an
exact anonymous public GitHub GET / verified response origin, and one trusted
browser action with synthetic-click refusal / immutable payload. Test-only
Ed25519 keys were generated in browser memory. No production keys were used.
The harness in `test/browser/` imports the canonical module staged byte-exact
as `console.js`, delivered by an Amu-built native diagnostic static server.
Diagnostic staging is not native CDCI / compiler closure qualification.

Real provider APIs, live redirect delivery, product builders, publisher pin
distribution, complete static headers, production browser consent, node / Cell
execution and deployment remain separate acceptance gates. No production route
cutover or stopping of an existing service is authorized by these fixtures.
