# browser-use-clj

Cloud v3 の実接続確認は [`docs/cloud-live-probe.md`](docs/cloud-live-probe.md)
を参照してください。既定はdry-runで、課金されるsession作成には
`--execute`と`BROWSER_USE_API_KEY`の両方が必要です。

browser-use-style browser automation agent in **portable Clojure** —
every namespace is `.cljc`, designed for **Clojure-on-WASM hosts**
(SCI, ClojureScript, GraalVM, kotoba-clj) as well as the JVM. The
browser itself is an injected host capability; the action history is
persisted through a **Datomic API**.

Built on [langgraph-clj](https://github.com/kotoba-lang/langgraph)
/ [langchain-clj](https://github.com/kotoba-lang/langchain) —
the same layering as upstream browser-use over langchain.

```
src/browseruse/
  browser.cljc   IBrowser protocol (host capability) + mock-browser
  actions.cljc   action registry → tools (navigate / click / type / … / done)
  agent.cljc     agent loop (langgraph StateGraph) + action log as datoms
```

## Design

- **Indexed-element page representation** — the model sees the page
  the way browser-use renders it:

  ```
  Current page: Example Shop (https://shop.example)
  Interactive elements:
  [0]<a>Pricing</a>
  [1]<input name="q" value="">
  ```

- **Browser = injected host capability** — implement `IBrowser`
  (Playwright/CDP on the JVM, the page itself in-browser, an
  OS-automation MCP on desktop). `mock-browser` ships a pure-data site
  model for tests and offline runs.
- **Datomic API premise** — every executed action becomes a datom
  (`:action/name`, `:action/url`, …): "every URL the agent visited"
  is a Datalog query. Graph checkpoints (resume / human-in-the-loop)
  come from langgraph-clj.

## `agent-browser` compatibility

`agent-browser` is treated as a capability role, not as a required CLI
dependency. In the kotoba stack the equivalent implementation is:

```
browser-agent-clj -> browser-use-clj -> playwright-clj
```

- `browser-agent-clj`: owned browser session, supervisor, multi-agent control
- `browser-use-clj`: `IBrowser` protocol, indexed elements, action tools, logs
- `playwright-clj`: JVM host implementation for real Chromium

Applications should depend on an injected `IBrowser` capability. A CLI named
`agent-browser` can be added later as a thin wrapper over this stack without
changing the core agent/runtime model.

## Quickstart

```clojure
(require '[browseruse.browser :as b]
         '[browseruse.agent :as agent]
         '[langchain.model :as model]
         '[langchain.db :as db])

;; host capability: real IBrowser impl, or the mock:
(def browser
  (b/mock-browser
   {"https://shop.example"
    {:title "Example Shop"
     :elements [{:tag "a" :text "Pricing" :nav "https://shop.example/pricing"}]}
    "https://shop.example/pricing"
    {:title "Pricing — $29/mo" :elements []}}
   "https://shop.example"))

(def conn (db/create-conn agent/log-schema))

(agent/run
 {:model (model/anthropic-model {:api-key … :http-fn host-fetch …})
  :browser browser
  :task "Find the price of the product"
  :history-conn conn
  :session-id "s1"
  :max-steps 25})
;; => {:result "…" :done true :messages […] :steps n}

;; the audit trail is datoms:
(db/q '[:find ?name ?url
        :where [?a :action/name ?name] [?a :action/url ?url]]
      (db/db conn))
```

Custom actions are just more tool maps:

```clojure
(agent/run {:actions (conj (browseruse.actions/default-actions browser)
                           {:name "save_note" :description "…"
                            :schema {…} :fn (fn [args] …)})
            …})
```

## CAPTCHA orchestration

CAPTCHA handling is opt-in and provider-neutral. Human hand-off pauses and
resumes the agent session; an external adapter implements
`browseruse.captcha/CaptchaProvider`. Credentials must be captured inside that
adapter, never placed in settings:

```clojure
{:settings
 {:captcha {:mode :external
            :provider solver-adapter
            :timeout-ms 120000
            :max-polls 60
            :apply-solution apply-token!}}}
```

Recipes can use `{:do :captcha :captcha {:mode :human}}`. Solver tokens are
available only to `:apply-solution`; audit hooks and history receive a redacted
result. CAPTCHA automation must only be used where the caller is authorized.

### CapSolver adapter

The JVM production adapter uses CapSolver's asynchronous token API:

```clojure
(require '[browseruse.capsolver :as capsolver]
         '[browseruse.capsolver-http :as capsolver-http])

(def solver
  (capsolver/provider {:client-key (System/getenv "CAPSOLVER_API_KEY")
                       :request! capsolver-http/request!}))
```

Supported mappings are reCAPTCHA v2/v3, hCaptcha, and Turnstile. DOM detection
copies a public `data-sitekey` when present; otherwise provide `:site-key` in
the challenge. CapSolver does not expose task cancellation, so timeout performs
local abandonment. Run the credential-free example with
`kbb -M:capsolver -m capsolver-dry-run`; it uses no network or API key.

## Mapping from upstream

See [docs/adr/0001-architecture.md](docs/adr/0001-architecture.md) for
the browser-use → browser-use-clj correspondence (indexed elements,
Controller/Registry, agent loop, done action, history).

## Tests / example

```sh
kbb -M:test     # 4 tests, 15 assertions
kbb -Sdeps '{:paths ["src" "examples"]
                 :deps {io.github.com-junkawasaki/langgraph-clj
                        {:git/tag "v0.2.0" :git/sha "133740f"}}}' \
        -M -e "(require 'shop-agent) (shop-agent/-main)"
```

Workspace development against local checkouts: `kbb -M:dev:test`.

## Proxy, profiles, CDP, and fingerprint controls

The JVM Playwright host supports `:proxy` (`:server`, `:bypass`, `:username`,
`:password`), `:user-data-dir` persistent profiles, `:cdp-url` attachment,
`:channel`/`:executable-path`, context fingerprint controls, and document-start
`:init-scripts`. Inspect `(:capabilities session)` for the credential-redacted
effective mode.

These controls are configuration hardening, not a guarantee that automation is
undetectable. CAPTCHA and managed anti-detect services are separate providers.

Use the credential-safe [proxy/profile probe](docs/proxy-profile-probe.md) to
verify observed IP, locale/timezone, and persistent cookie/localStorage state
against either an authorized external endpoint or a deterministic local server.
