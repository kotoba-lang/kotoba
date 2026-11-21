# Canonical client runtime host

Tracking: [JUN-14](https://linear.app/kotobalabs/issue/JUN-14).
Source: `src/kotoba-client-runtime.js`; styling: `src/kotoba-client-consent.css`.
Products import / copy these exact browser assets and pin revision / digest.
No build step or Node / JVM / NBB runtime is required. Product-local validators
and approval brokers are not substitutes for this implementation.
The architecture contract this host implements is
[app-environment-contract.md](app-environment-contract.md).

## Local-state declarations

`local-state` declares an adapter, a schema name and a positive integer version.
Use `adapter: 'memory'` for volatile application state when an app does not use
IndexedDB, OPFS or localStorage. Explicit user exports or URL snapshots do not
turn in-memory state into a persistent storage adapter. The validator does not
provide a store, migrate state, persist it or grant an operation; products own
their local-state implementation. The existing `indexeddb`, `opfs` and
`localstorage` declarations remain supported.

A local-only app can declare `operations: []`, with no requested capabilities,
host eligibility or supported selectors. Its canonical derived policy is
`connect-src 'none'`, and its broker refuses every invocation before consent.
This does not turn the same-document `trusted-page-v1` profile into a sandbox
for untrusted scripts or resolve KOTOBA-159's broader consent-enforcement review.

## Trusted shell and operation authority

The verified host shell owns its document, publisher pins, eligibility,
broker and supported browser handlers. Do not run arbitrary untrusted app
JavaScript in that realm. Apps receive only bounded invocation.

`createClientConsentHost({locale})` provides the canonical modal (`locale` is `'ja'`, the default,
or `'en'`). Its first screen shows the operation's declared disclosure (see below); the service,
operation, endpoint / action, method, path, query, data categories, redirects, scope and the payload
summary sit behind 詳細を見る (View details). A direct trusted MouseEvent on Allow approves one
invocation; synthetic clicks, forged handles and a true-returning callback do not. When the broker is
denied it sends no request. Eligibility starts empty and is not persisted user consent.

## Profiles: which apps may use trusted-page-v1 (KOTOBA-159 finding 1, owner decision 2026-11-22)

- An app that handles user data or communicates with an external service **must** use
  `restricted-wasm-v1`: the guest runs in an opaque-origin sandbox, so the broker's refusal is the
  only way out (with the host's static CSP; the WebRTC limit of review R6 still applies).
- `trusted-page-v1` is limited to **owner-signed first-party apps**. Its code shares the host
  document and can send without the dialog, so the dialog there is a notice, not an enforced consent.
  It says so: 「この画面は送信の確認で、送信の制限を保証するものではありません。」 Its buttons are
  閉じる / 続ける. It never says that refusing prevents sending; only `restricted-wasm-v1` says
  「許可しない場合、この情報は送られません。」
- A sunset date for `trusted-page-v1` is a separate owner decision (KOTOBA-159).

## Disclosure (KOTOBA-159 finding 9, Legal design 2026-11-22)

Every operation carries `disclosure`; descriptor validation rejects an operation without a complete
one (`invalid-disclosure`, with the missing or invalid fields in `details`). The values are shown as
written; nothing is inferred from the payload.

| key | value |
|---|---|
| `recipient` | the receiving business's official legal name (not an origin or abbreviation) |
| `country` | ISO 3166-1 alpha-2 code of the recipient, `JP` for Japan |
| `country-name`, `foreign-info-url` | required when `country` is not `JP`: the country in words, and an HTTPS page with the 施行規則 17 条 2 項 information (country, its data-protection regime, the recipient's measures; a link to the PPC country survey is enough for the regime) |
| `data` | data categories in words a user reads (氏名, メールアドレス, 相談内容 …), 1 to 32 |
| `special-care` | `true` when 要配慮個人情報 or a GDPR special category is sent; then `special-care-kinds` names them (病歴 …) |
| `purpose` | one specific sentence (not 「サービス向上のため」) |
| `frequency` | `one-time` or `continuous` |
| `withdrawal` | where in settings the permission is withdrawn (「設定 › 許可した送信」) |
| `note` | optional: a short plain-text note from the app, at most 200 characters, no control characters; shown as text, never parsed as HTML or Markdown |

The host may pass `app: {name, provider, 'privacy-policy'}` to `createClientOperationBroker` from its
own registry (never from the guest). The dialog title uses the name; trusted-page-v1 also names the
provider and its privacy policy. A line whose value is missing is left out, never shown blank.
Both profiles show the same declared facts: recipient, data, purpose, frequency, special care, the
note, where to withdraw and, for a foreign recipient, a line with a link to the information page
(AWAI-3819). Links are plain `<a>` elements to the validated HTTPS URL, opened in a new tab with
`rel="noopener noreferrer"`. Only the notice differs between the profiles.

The dialog text is a **draft** (Legal, `reports/kotoba-159-consent-wording.md`, 2026-11-22). It is
kept in one exported object, `CLIENT_CONSENT_TEXT` (`status: 'draft'`), and Legal finalizes it before
any public release. Two EU points (GDPR 49(1)(a) for continuous transfers, an Art. 27 representative)
wait for a lawyer. The two choices have the same style, neither is focused or selected by default,
and Allow stays disabled for the first 600 ms (finding 3).

Behind 詳細を見る: the technical scope, then the payload's content type, size, SHA-256, field names
(JSON or form bodies), header names and text. Fixed fields (data categories, redirects, scope) come
before the guest-chosen Action, the query length is shown, and a value over 160 characters is cut
with its length and a 全文 toggle (R5, D4).

## Addresses and `scope: "lan"` (KOTOBA-159 findings 8, P1, D1)

HTTP and browser-action origins, redirect origins, peer addresses, circuit-relay hops and the
receive-snapshot listener may not name loopback, RFC 1918, link-local (169.254.169.254 included),
CGNAT, 0.0.0.0/8, `localhost`, `.local`, `.home.arpa`, `.internal`, or the IPv6 equivalents (::1,
fc00::/7, fe80::/10, IPv4-mapped / compatible and NAT64 forms), unless the operation declares
`scope: 'lan'`. The dialog then says the recipient is on the local network or this device. A `lan`
operation may name only internal hosts. `clientAddressScope(host)` exposes the classification;
`clientEndpointAllowsRequest(endpoint, input, method, {scope: 'lan'})` and
`clientPeerEndpointProblems(endpoint, {scope: 'lan'})` take the same option.

## Generic network rails (finding 7)

An endpoint whose origin is a wildcard or pattern, or whose path is made only of parameters
(`/:a`, `/:a/:b`), is refused as `generic-network-endpoint`, whatever its capability is called.

## One request at a time; canonical brokers only (R3, R4)

A broker takes its single slot before it reads a payload or body and releases it when consent is
decided. A second invoke meanwhile is refused at once (`another client operation is awaiting
consent`). `mountRestrictedClientApp` accepts only a broker created by `createClientOperationBroker`;
no other object, copy or wrapper is mounted, and there is no exported way to register one.

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

A hand-off whose receiver the user picks in the operating system, such as a
share sheet, has no service origin. It uses `endpoint: {'browser-action':
'share/text', recipient: 'user-selected-app'}` (AWAI-3336). `recipient` has only
that one value, and no origin is fabricated. Everything else is the same as a
browser-native service effect: the operation names its service, operation and
data categories, needs `each-operation` consent and a host adapter, takes plain
bounded JSON copied before the modal, and never enters connect-src. The consent
dialog says that the receiving app is chosen by the user and handles the data
under its own rules. The host adapter only opens the system picker with the
approved payload: it must not pick, prefill or remember a receiver. Choosing an
app in that picker is the user's own step and is not a second approval by this
runtime.

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

An in-memory artifact is limited to 512 MiB, because its whole body is held as one
snapshot before the digest. A model file is larger, so an artifact may instead declare
`delivery: 'host-stream'` (AWAI-3307), with `max-bytes` up to 64 GiB.

- **Host sink:** the trusted host supplies `artifactSinks[service][operation]` when it creates
  the broker. The sink is captured at creation, like browser adapters. An operation without a
  sink is refused before consent and before any request.
- **Consent:** the dialog adds the artifact revision, SHA-256, byte budget and delivery.
  Denial sends nothing.
- **Streaming:** after the final response origin passes the declared redirect origins, the
  broker reads the body chunk by chunk:
  - it hashes it incrementally (`createSha256`, FIPS 180-4; WebCrypto has no streaming digest);
  - it enforces the byte budget and a 60-second idle deadline;
  - it gives the sink byte copies through `write`.
- **Outcome:** only an exact digest match calls `close({sha256, bytes, revision})`. Its plain-data
  result is returned with `verified: true`. A mismatch, overrun, idle timeout, cancellation or read
  error calls `abort(reason)` and never `close`.
- **The host's own duty:** the host must discard aborted bytes and admit the file only after `close`.
  `verifyClientArtifact` refuses a host-stream declaration.

`test/browser/verify-artifact-stream.mjs` qualifies this path in a real headless Chromium. The
artifact host and its CDN redirect are faked with the DevTools Fetch domain, and consent is answered
with trusted input.

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

## Proposals

- [Bounded batch consent](client-runtime-batch-consent-proposal.md) (AWAI-3276): one consent for a bounded set of
  requests of one operation. Proposal only; not implemented, with open owner decisions.
