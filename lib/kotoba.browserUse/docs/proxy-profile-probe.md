# Proxy and persistent-profile probe

This Phase 6 probe checks the effective public IP, browser locale/timezone, and
cookie/localStorage persistence after closing and reopening a Playwright
persistent profile. It does not claim that a local browser is undetectable.

Create a private config file outside the repository:

```clojure
{:probe-url "https://your-authorized-ip-echo.example/json"
 :user-data-dir "/private/tmp/browseruse-profile"
 :executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
 :proxy {:server "http://proxy.example:8080"
         :username "..."
         :password "..."}
 :locale "ja-JP"
 :timezone-id "Asia/Tokyo"
 :expected {:ip "203.0.113.10" :locale "ja-JP" :timezone "Asia/Tokyo"}
 :dry-run? true}
```

Validate configuration without opening a browser or contacting the proxy:

```sh
kbb -M:playwright-probe /absolute/path/to/probe.edn
```

Inspect the credential-redacted plan, then change `:dry-run?` to `false` for an
authorized live probe. The command exits with status 2 when an expectation or
persistence check fails. Proxy credentials are never included in probe output.
URL-embedded credentials are rejected; supply proxy authentication only through
the dedicated `:username` and `:password` fields.

For deterministic host verification, `start-deterministic-server!` binds only
to loopback and provides a local JSON endpoint. The Playwright test suite uses
it without external traffic:

```sh
kbb -M:playwright:test -n browseruse.playwright-probe-test
```
