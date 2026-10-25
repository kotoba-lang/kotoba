# kotoba-lang/statement-fetch

**Declarative retrieval of bank / brokerage statements through a browser,
where the agent structurally cannot type your password.**

Written for the recurring case where a non-Japanese institution (US bank
onboarding, KYC, visa/immigration paperwork) asks for "a personal bank
statement from the last 90 days" and a Japanese online bank will only hand one
over through a logged-in web UI.

```
resources/institutions/*.edn   what to click, per institution — data, not code
src/kotoba/statement_fetch.cljk      pure: validate a flow, compile it to argv
src/kotoba/statement_fetch/
  agent_browser.cljs                 nbb driver: spawn agent-browser, poll, report
bin/statement_fetch.cljk             CLI
```

## The safety property

An agent driving a banking session is one prompt away from being asked to type
a password. This library makes that impossible rather than discouraged:

- **Authentication is a `:handoff` step, and `:handoff` compiles to no argv.**
  There is no code path from a flow definition to a keystroke carrying a
  credential.
- **`validate-flow` rejects any step that would carry one** — by explicit key
  (`:step/password`, `:step/otp`, `:step/token`, …) and by selector/value
  matching authentication vocabulary in English and Japanese
  (`password`, `otp`, `パスワード`, `暗証`, `ワンタイム`, …).
- **`plan` refuses to compile an invalid flow at all**, so an unsafe flow never
  reaches a browser — it throws during compilation.
- **A flow may carry exactly one handoff, and it must be the login.** A
  mid-flow handoff is a validation error.

The operator authenticates in a real browser through their own password
manager. The driver watches for a completion marker (`ログアウト` appearing on
the page) and resumes on its own. It never reads, stores, autofills, or
transmits the credential.

`test/kotoba/statement_fetch_test.cljk` asserts each of these, and
`test/kotoba/institutions_test.cljk` re-asserts them against every institution
file actually shipped here — including that none contains a digit run long
enough to be an account number, since this repository is public.

## Institutions

| Flow | Language | Notes |
|---|---|---|
| `jp-paypay-bank.transaction-statement-en` | English | 英文 取引明細書, immediate PDF. 880 JPY/issuance per PayPay's current published fee table. |
| `jp-rakuten-bank.transaction-detail-ja` | Japanese | 入出金明細, immediate PDF, 24-month window, ≤3,000 entries. |

Rakuten has no `*-en` flow on purpose: its English documents are phone-request
only and arrive by post in 1–10 days, so no browser flow can produce one.

## Personal, corporate, and crypto connections

`resources/providers/` contains public, secret-free connector definitions.
Local registration EDN separates the legal owner from the asset:

```clojure
{:connection/id :personal/main-bank
 :owner/kind :personal
 :owner/ref :owner/self
 :asset/kind :bank
 :provider/id :bank/browser}

{:connection/id :company/accounting
 :owner/kind :corporate
 :owner/ref :org/example
 :asset/kind :accounting
 :provider/id :moneyforward/cloud}

{:connection/id :personal/crypto
 :owner/kind :personal
 :owner/ref :owner/self
 :asset/kind :crypto
 :provider/id :bitflyer/readonly}
```

Keep registrations under a private local control directory. Account numbers,
wallet addresses, payees, tokens, API keys, and snapshots are runtime data and
must not enter this public repository.

```bash
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk connectors
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk auth-plan \
  moneyforward-cloud --connection private/company.edn \
  --state RANDOM_CALLBACK_STATE --redirect-uri http://127.0.0.1:8787/callback
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk normalize \
  --connection private/company.edn --snapshot state/provider.edn \
  --out state/normalized.snapshot.edn
```

After the operator consents and the local callback verifies the returned
`state`, exchange the code without placing credentials in argv or logs:

```bash
export FINANCE_OAUTH_CODE='code-from-local-callback'
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk oauth-exchange \
  moneyforward-cloud \
  --code-env FINANCE_OAUTH_CODE \
  --expected-state "$EXPECTED_STATE" --returned-state "$RETURNED_STATE" \
  --redirect-uri http://127.0.0.1:8787/callback \
  --token-out state/moneyforward.token.json --approve true
```

The provider definition names the client-id/client-secret environment
variables. The command never prints the code or token and stores the token
owner-readable only (mode `0600`). A separate local callback handler must
capture `code` and `state`; embedded WebViews are not assumed.

Fetch only an allowlisted read endpoint:

```bash
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk api-fetch \
  bitflyer-readonly --path /v1/me/getbalance \
  --out state/bitflyer-balance.snapshot.edn --approve true

kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk api-fetch \
  moneyforward-cloud --path /v2/tenant \
  --token-file state/moneyforward.token.json \
  --out state/moneyforward-tenant.snapshot.edn --approve true
```

`api-fetch` always constructs `GET`, rejects paths absent from the provider
allowlist, and writes an owner-readable snapshot. The bitFlyer adapter signs
the exact timestamp + method + path + body sequence with HMAC-SHA256 as
specified by its official API; it has no order, transfer, or withdrawal path.

OAuth plans require the provider's application portal registration and an
operator consent step. HMAC/API-key plans require a key created with read-only
permissions. The connector validator permits only explicitly allowlisted GET
paths; transfers, withdrawals, trades, and accounting writes are outside this
capability.

Money Forward Cloud requires an App Portal registration and supports OAuth 2.0
authorization-code flow or API-key-to-short-lived-JWT exchange depending on
the endpoint. freee requires application registration and OAuth consent.
bitFlyer uses API key plus HMAC-SHA256; create a dedicated read-only key and
verify its permissions before ingestion. These registrations are operator
procedures—Tamaki may remind and observe them, but cannot approve consent or
expand scopes.

## Verified vs unverified

A flow starts life with `:step/unverified true` on every selector nobody has
run yet, and **`fetch` refuses to execute an unverified flow**. A wrong
selector on a banking page is not a harmless miss.

Promoting a flow to verified:

```bash
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk verify <flow>
# authenticate in the browser yourself, then:
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk discover --profile Default
# replace the guessed selectors in resources/institutions/<flow>.edn, drop
# :step/unverified, and re-run verify
```

As of 2026-07-25 both shipped flows are **unverified past the login step**.
What *is* verified is PayPay's personal login entry point
(`https://login.paypay-bank.co.jp/wctx/LoginAction.do`), extracted from
`Janet_Login_URL` — the site's visible ログイン links are `javascript:void(0)`
and resolve through `jnb_tologin()`, so the URL is not scrapeable from markup.

## Usage

```bash
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk list
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk verify jp-paypay-bank.transaction-statement-en
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk plan  jp-paypay-bank.transaction-statement-en \
  --from 2026-04-26 --to 2026-07-25 --out ./statement.pdf
kbb --backend sci --classpath src:bin:resources bin/statement_fetch.cljk fetch jp-paypay-bank.transaction-statement-en \
  --from 2026-04-26 --to 2026-07-25 --out ./statement.pdf --profile Default
```

`--profile <name>` reuses an existing Chrome profile (`agent-browser profiles`
lists them), so the operator's own session and password manager are what the
flow runs against.

## Requirements

- [`nbb`](https://github.com/babashka/nbb)
- [`agent-browser`](https://www.npmjs.com/package/agent-browser) installed
  globally. The driver resolves the package entry point directly rather than
  the `agent-browser` shim on PATH — observed 2026-07-25, npm's
  `/opt/homebrew/bin/agent-browser` symlink pointed into a deleted worktree
  while the package itself was fine.

## Tests

```bash
kbb --backend sci --classpath src:test:resources test/run_tests.cljk
```

## Adding an institution

Add one EDN file to `resources/institutions/`. No code changes — the pure core
validates and compiles whatever you drop there, and `institutions_test.cljs`
picks it up automatically. Keep the login a `:handoff`; validation will not let
you do otherwise.
