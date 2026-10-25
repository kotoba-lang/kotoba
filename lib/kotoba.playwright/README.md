# kotoba-lang/playwright

**SSoT for `kami.playwright`** — headless WebGL2 Chromium eval from CLJ/bb.

Also ships `playwright-clj` core (Java Playwright bindings). `kotoba.playwright`
is a thin facade over `kami.playwright`. ADR-2607102200 addendum 8.

## Usage

```clojure
(require '[kami.playwright :as pw])
(pw/eval-page "return {ok: true};")
```

Bridge script: consumers typically run with cwd that has `scripts/pw_eval.cjs`
(webgpu keeps a copy for its bb tests; this package may grow a shared bridge).
