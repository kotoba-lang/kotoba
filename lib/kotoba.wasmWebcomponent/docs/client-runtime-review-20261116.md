# kotoba-client-runtime.js: second independent review (KOTOBA-159, 2026-11-16)

Reviewed file: `lib/kotoba.wasmWebcomponent/src/kotoba-client-runtime.js` at `kotoba-lang/kotoba` main
`2a40111e21179eda1d82e1478cf65891444fff58` (49,211 bytes, 966 lines, sha256 `5a950051c484a992caba0ad9edff780938648f9cade0b18f2d016812742ee6fb`).

Reviewer: Claude (claude-sonnet-5-5) in Claude Code. The reviewer wrote none of the reviewed code. It read the
record of the first review (KOTOBA-159 comments) before it read the code, so this is a re-verification of that
review's conclusions plus a review of what changed since, not a blind second review. It is a review by an AI model,
not a human security audit and not a product qualification.

## What was reviewed and how

- Read all 966 lines: descriptor validation, endpoint and route matching, request snapshotting, the consent host,
  the broker, the restricted-guest mount, signed-descriptor verification, artifact verification, connect-src.
- Compared with the revision of the first review (`6f74fe21`, sha256 `4e6ef6ee...b693`): 65 lines added, 23 removed.
  The change is PR #1178 (abort signal, guest close, host-DOM observation, second-load invalidation, body-read
  cancellation) plus the `memory` local-state adapter. Everything else is byte-identical.
- Ran every existing client-runtime test on `2a40111e` (all pass): `verify-client-consent-host`,
  `verify-client-broker-review`, `verify-client-memory-state`, `verify-client-mount-navigation`, and
  `verify-client-fetch-cancel` (needs a local certificate directory, see the test header).
- Real browser: Chromium 156 (Claude desktop app) on `localhost`, the real runtime module, the real consent host and
  broker, trusted input from the browser pane, synthetic operations against `https://127.0.0.1:9` (nothing listens).
  An approved operation ends in `TypeError: Failed to fetch`; a denied one ends in `client operation was not approved`.

## Result

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | `trusted-page-v1` cannot enforce per-operation consent (same-document app code) | High | **Open, owner decision.** Unchanged since the first review. |
| 2, 4, 5, 6 | Undisplayed Fetch options and override headers; `..;` in prefix routes; browser-action origins in connect-src; descriptor re-read | Medium to Low | Fixed earlier. Re-verified: tests pass on this revision. |
| 3 | Allow clickable in the tick the dialog opens | Medium | Fixed earlier. Re-verified in a real browser (below). |
| 7, 8, 9 | Generic-network refusal by name only; private and loopback origins accepted; payload and body not shown in the dialog | Low | **Open, owner decisions.** Unchanged. |
| KOTOBA-158 | Late `close` event auto-denies the next operation | Medium | Fixed earlier. Re-verified in a real browser (below). |
| R1 | The approved request loses `referrerPolicy: 'no-referrer'` | Low | **Fixed here.** |
| R2 | A refused response is left open | Low | **Fixed here.** |
| R3 | A guest can make the host buffer many large bodies before the busy check | Low | Open, owner decision. |
| R4 | `mountRestrictedClientApp` accepts any object with `invoke` as its broker | Low | Open, owner decision. |
| R5 | A long query hides the data categories in the consent dialog | Low | Open, owner decision. |

### R1: `referrerPolicy` lost on every approved HTTP call (fixed)

PR #1178 changed `fetchRequest(approvedPayload.input)` to `fetchRequest(approvedPayload.input, { signal })`. A
non-empty `init` makes `fetch` build a new Request, and that step resets the referrer and the referrer policy
(Fetch, Request constructor, "If init is not empty"). The snapshot's explicit `referrerPolicy: 'no-referrer'` was
therefore dropped whenever the operation had a signal, which is every call made through `mountRestrictedClientApp`.

Observed in Chromium 156: with `no-referrer` a service receives no `Referer`; after `fetch(request, { signal })` it
receives `Referer: <host page URL>`; with the signal given to the `Request` constructor it receives none. The
`Origin` header is sent in all cases, so the host origin was already visible to the service. What the regression
adds is the full host URL when the host document sets a permissive policy such as `unsafe-url`.

Fix: the signal is passed to the `Request` constructor in the snapshot, and the broker calls `fetch(request)` with no
init. Test: `test/verify-client-review-20261116.mjs` (fails on `2a40111e`); `verify-client-consent-host.mjs` case 6
now reads the signal from the Request.

### R2: refused responses were not cancelled (fixed)

After `fetch` the broker refuses a response for an undeclared final origin, an unverifiable redirect or a failed
artifact download. The body was never read or cancelled, so the connection and buffered data stayed open until
garbage collection. The refused branches now cancel the body. An accepted response is returned untouched. Test:
same file; the cancel assertions fail on `2a40111e`.

### R3: pre-consent buffering is not bounded by the busy check (open)

`invoke` materializes the request body (up to 16 MiB) before it asks the consent host, and the host rejects a second
request as busy only at that point. A guest that sends many operations at once makes the host hold one snapshot per
operation until each reaches the busy check. Measured in Node with a pending consent: 4 MiB bodies, resident set
48 MiB at start, 78 MiB with 1 concurrent call, 126 MiB with 4, 158 MiB with 8; 7 of 8 were rejected as busy only
after their snapshot. About 14 MiB per concurrent call for a 4 MiB body; at the 16 MiB limit the cost is about four
times larger per call (extrapolated, not measured). Impact is availability of the host tab, not consent.
Recommendation: take a per-broker slot before snapshotting and release it when consent resolves. This turns the
current race (a second call may succeed if the first is denied before the second reaches the host) into a
deterministic rejection, so it needs an owner decision.

### R4: any object with `invoke` is accepted as the broker (open)

`mountRestrictedClientApp` checks `typeof broker?.invoke === 'function'`. `createClientOperationBroker` refuses
caller-supplied confirmation, but a host can still mount a bespoke broker with no consent step. The existing mount
tests do exactly that. Recommendation: record canonical brokers in a `WeakSet` and require membership, with a
test-only escape that is not exported. This breaks the current tests and any host that mounts a custom broker.

### R5: a long query pushes the data categories out of view (open)

A route may declare `query-params` without fixed values, so the guest chooses the value. The dialog prints it on
the `Action` line inside a 45vh scroll area. Rendered in Chromium 156 with a 900-character value: `Data categories`
is cut off at the bottom and `Delivery redirects` is not visible without scrolling. Recommendation: print the fixed
fields (data categories, redirects) before `Action`, and show the length of the query.

### Known limits, unchanged

- The final-origin check after a redirect runs after the response arrived, so `connect-src` is the network barrier.
  Hosts must ship the static CSP derived by `clientRuntimeConnectSrc`.
- Guest navigation is contained by a parent `frame-src 'none'`, not by this file. A navigation that starts before the
  first `load` event is not detected. An already started browser action or sent request is not rolled back.
- Trailing `?` and `#` give an empty `search` and `hash`, so the matcher sees no query while the URL still carries
  the bare `?`. Harmless; not changed.

## Real-browser results (Chromium 156, synthetic operations)

| Case | Result |
|---|---|
| Allow clicked after the dialog had shown for over a second | Enabled 601 ms after open; click approved; fetch attempted (`Failed to fetch`). |
| Double click with a start button placed exactly over where Allow appears (finding 3) | The dialog stayed open and pending; Allow was enabled 602 ms after open; Deny then ended it with `not approved`. |
| Approve A, B starts 5 ms later (KOTOBA-158) | B's dialog stayed pending for more than 3 s; no stale `close` denied it. |
| `fetch(request, { signal })` and `Referer` (R1) | Referer sent. Not sent without a signal, with the signal in the Request, or with `referrerPolicy` repeated in the init. |
| 900-character query (R5) | Data categories cut off in the scroll area. |

## Not covered

No test of `trusted-page-v1` against hostile same-document code (finding 1 stays open on the first review's
evidence). No other browser, no touch input, no Firefox or Safari. No provider, credential or production host.
`verifySignedClientDescriptor` was read, not run with real keys. Subagents and Workers that use the runtime were not
reviewed. The CI of this repository does not run Node, so these tests run locally only.

## Reviewed revision

This change fixes R1 and R2 only. The reviewed revision for vendoring is the file as merged by this change; its
sha256 is recorded in `local-changes.json` and its commit in KOTOBA-159. Findings 1, 7, 8, 9, R3, R4 and R5 remain
open, so consent is guaranteed only for `restricted-wasm-v1` apps whose host ships the static CSP.
