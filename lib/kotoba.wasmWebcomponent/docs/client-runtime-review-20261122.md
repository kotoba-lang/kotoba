# kotoba-client-runtime.js: decided fixes and delta review (KOTOBA-159, 2026-11-22)

Author: Claude (claude-opus-5-5) in Claude Code, an Orca worker for the Dev coordinator. This is an
implementation of owner decisions plus a delta review by an AI model. It is not a human security audit,
not a legal opinion and not a product qualification.

## 1. Delta review: 48d95997..main

The last reviewed revision was sha256 `0926b63b…7fc6` (main `48d95997`, 1118 lines). Main then reached
`e7a264839` with sha256 `f8e5336db8b717c68be085b2bdd019929127cc2d2856a9648e9beca9af8fd5ed` (1259 lines;
the same file as at `4463ae792`). The 153-line diff is two changes:

- AWAI-3307: `delivery: 'host-stream'` artifacts (up to 64 GiB) streamed to a host sink captured at
  broker creation, with an incremental FIPS 180-4 SHA-256 (`createSha256`), the byte budget and a 60 s
  idle deadline; `close` only on an exact digest, `abort` otherwise. Consent lists revision, digest,
  budget and delivery.
- AWAI-3336: browser-action endpoints whose receiver has no origin: `recipient: 'user-selected-app'`
  (share sheet) and `recipient: 'browser-selected-push-provider'` for three push actions.

Method: read the diff; ran the runtime tests on `e7a264839` (all pass except the TLS probe, which needs a
local certificate and passed with one); ran `test/browser/verify-artifact-stream.mjs` in Chrome
(after fixing its file server, below).

No new High or Medium defect. The trust-critical paths are intact: both new endpoint kinds stay out of
connect-src, refuse HTTP options, keep the plain-data copy before consent and the each-operation
consent. The sink is host code captured at creation, so a guest cannot substitute it.

| # | Finding | Severity | Status |
|---|---|---|---|
| D5 | `streamArtifact` awaits `sink.write` with no deadline. The 60 s idle timer races only `reader.read`, so a host sink that never settles holds the download open. | Low | Open. The sink is trusted host code; recorded for hosts. |
| D6 | If the sink factory throws, the response body is not cancelled (same class as R2). | Low | Open. |
| D7 | A host-stream download has no overall deadline: a body that drips within the 60 s idle limit runs as long as its byte budget allows. | Info | Open, product decision. |
| D8 | `user-selected-app` and the push provider have no origin, so the internal-address rule (finding 8) does not apply to them; the receiver is the user's choice. With finding 9 the app must still describe the receiver in `disclosure.recipient`. | Info | Confirmed design. |
| — | `test/browser/verify-artifact-stream.mjs` wrote a 200 header before reading the file, so a missing file (favicon) crashed the server with `ERR_HTTP_HEADERS_SENT`. It failed the same way on main. | Test bug | Fixed here. |

## 2. Decided fixes in this change

Each item has a negative control in `test/verify-client-review-20261122.mjs`. The file runs its eight
sections against another copy of the runtime with
`KOTOBA_NEGATIVE_CONTROL=1 KOTOBA_CLIENT_RUNTIME=<file>`. Against main `e7a264839` all eight fail;
with this change all eight pass:

| Section | On main `e7a264839` | Here |
|---|---|---|
| Finding 7 | fail: `/:anything` route accepted | pass |
| Findings 8, P1, D1 | fail: `https://127.0.0.1` accepted | pass |
| Finding 9 | fail: operation without disclosure accepted | pass |
| Finding 1 | fail: trusted-page-v1 notice is "Denying sends no request…" | pass |
| R3 | fail: second call is snapshotted, then refused as "busy" | pass |
| R4 | fail: `{invoke}` object mounted | pass |
| R5, D4 | fail: Data categories rendered below Action | pass |
| D2 | fail: plain function adapter reaches consent for a scoped operation | pass |

- **7** Structural refusal: an endpoint with a wildcard or pattern origin, or a path made only of
  parameters (`/:a`, `/:a/:b`, in single endpoints or routes), is `generic-network-endpoint`, whatever
  the capability is called. The old name check for `net/http-post` stays.
- **8, P1, D1** `clientAddressScope(host)` classifies IPv4, IPv6 (with or without brackets, zone ids,
  IPv4-mapped/compatible, NAT64) and LAN names. Service, browser-action and redirect origins, peer
  addresses, relay hops and the receive listener may name an internal host only when the operation has
  `scope: 'lan'`; a `lan` operation may not name a public host. The dialog prints the LAN line on its
  first screen. 0.0.0.0 and ≥224 stay refused for peers as before.
- **9** Every operation carries `disclosure` (recipient's legal name, country, data in words,
  special-care flag with kinds, one-sentence purpose, one-time/continuous, where to withdraw; a foreign
  recipient adds the country name and a 施行規則 17 条 2 項 page). The first screen shows these; the
  technical scope and payload summary (content type, size, SHA-256, field names, header names, text)
  sit behind 詳細を見る. Categories are never inferred from the payload.
- **Wording** The dialog text is Legal's **draft** (`reports/kotoba-159-consent-wording.md`,
  2026-11-22), Japanese and English, kept in `CLIENT_CONSENT_TEXT` (`status: 'draft'`). Legal finalizes
  it before any public release. Lines with a missing value are left out. Both choices share one style
  and neither has focus or a default; focus goes to the heading. One deviation to confirm with Legal:
  the special-care sentence is also shown in trusted-page-v1, where the draft template omits it.
- **1** trusted-page-v1 shows 「この画面は送信の確認で、送信の制限を保証するものではありません。」 (and the
  provider sentence when the host supplies the provider) with 閉じる / 続ける. Only restricted-wasm-v1
  says that not allowing sends nothing. `client-runtime.md` documents the profile rule.
- **R3** One slot per broker, taken before any payload or body is read, released when consent is
  decided. A concurrent call is refused at once and its body is not read.
- **R4** Canonical brokers are recorded in a module-private WeakSet; `mountRestrictedClientApp` accepts
  nothing else. No escape is exported. The mount tests and browser fixtures now use canonical brokers
  (a stubbed fetch captured at creation, or a MutationObserver instead of a wrapped broker).
- **R5, D4** Fixed fields (data categories, redirects, network scope, transfer scope, artifact) come
  before Action; the query length is shown; values over 160 characters are cut with their length and a
  全文 toggle (up to 64 KiB of payload text is shown in full).
- **D2** A scoped peer operation needs `{handle, scopeEnforcement}` with the
  `kotoba.peer-scope-enforcement.v1` declaration; the broker checks `max-transfer-bytes` against
  `PEER_TRANSFER_MAX_BYTES` (256 MiB) and the declared bound. `verifyPeerAdapterScopeConformance` is
  the helper hosts must run and record. Bunsho and Awai Drive keep the 8 MiB limit until their adapter
  passes it (AWAI-3099).

Breaking for consumers: every descriptor needs `disclosure`; internal hosts need `scope: 'lan'`;
scoped peer adapters need the declaration; custom brokers no longer mount; button labels changed.

## 3. trusted-page-v1 inventory (for the sunset decision)

The itonami registry `index.json` (1364 entries, `cloud-itonami/app-itonami-itonami-registry` at
`8404e1ad1`) does not record the client-runtime profile, and it references no sheet. So the count comes
from descriptor declarations (`profile: 'trusted-page-v1'` outside the vendored runtime):

- Local checkouts of `network-awai` (169 dirs) and `cloud-itonami` (2008 dirs), excluding vendored
  runtime copies, `node_modules`, `.git`, `.agent-output` and `dist`.
- GitHub code search `"trusted-page-v1"` per owner (cloud-itonami, network-awai, kotoba-lang,
  com-junkawasaki): one extra hit (isco-5322). The index is incomplete (0 hits in kotoba-lang, where the
  string exists), and the REST quota was nearly used up, so the 999 `app-*` repos of cloud-itonami were
  not scanned one by one.
- The registry's `.agent-output/clones` held five more cloud-itonami apps.

First result: at least 60 apps. That count missed the JUN-1407 series, so it is corrected here.

**Correction (2026-11-22, Decision via App Build): the lower bound is about 860.**

- **JUN-1407 series.** The series Tauri apps (isic, isco, jsic, unspsc, cofog) all declare
  trusted-page-v1 because of the template's `build.mjs`. Listing the whole organization with
  `gh repo list cloud-itonami` (1859 repositories) gives 820 non-archived repositories named
  `app-itonami-cloud-itonami-(isic|isco|jsic|unspsc|cofog)-*`: isic 467, isco 340, jsic 3, unspsc 5 and
  cofog 5. Decision counts 813 series Tauri apps among them. The 7-repository difference was not
  checked repository by repository. The first count found only 8 of these.
- **Other apps.** 52 apps outside the series (51 in network-awai, plus `cloud-itonami/app-itonami-cloud-itonami-app`).
- **Total.** About 860: 813 series apps plus 52 others, or 872 by repository name.

Both groups are listed in
[evidence/trusted-page-v1-apps-20261122.txt](evidence/trusted-page-v1-apps-20261122.txt). Platform
surfaces that also declare it: `network-awai/awai-os` (desktop, Otehon shell), `network-awai-apex`
(node console, civic workspace, owner-store preflight), `cloud-murakumo-usb-installer` desktop and the
registry's Android assoc descriptor. Only `app-itonami-kaikei` was found declaring
`restricted-wasm-v1` (it also has a trusted-page-v1 declaration). The total is still a lower bound for
the apps outside the series.

**Decision's classification of the series (2026-11-22).** The 813 series apps are first-party, show
display settings only and make no outbound communication. They are category (3) and may stay on
trusted-page-v1 until **2027-03-31**. They move to `restricted-wasm-v1` all at once with the
itonami-lib migration. App Build changes the template to emit `restricted-wasm-v1` this week. A sunset
date for the other apps is still Decision's to set.

## 4. Verification

Node 26.0.0: all ten `test/verify-client-*.mjs` pass (the TLS probe with a throwaway localhost
certificate). Real browser: `verify-artifact-stream.mjs` in Google Chrome headless, 14 of 14 with
trusted input on the new dialog (続ける / 閉じる). Not covered: a person using the dialog on a
real device (App QA), Firefox and Safari, a real libp2p adapter run of the conformance helper,
screen readers. Node does not run in this repository's CI.

## Reviewed revision

The reviewed revision for vendoring is the file as merged by this change; its sha256 is recorded in
`local-changes.json` and KOTOBA-159. Consumers that must re-vendor: Bunsho (PR #13), Kumade
(JUN-430), kaikei, topology.
