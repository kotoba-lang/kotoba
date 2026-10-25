# i18n (kotoba-lang)

[![CI](https://github.com/kotoba-lang/i18n/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/i18n/actions/workflows/ci.yml)

Portable **.cljc i18n library**: message catalogs, compile-time-checked
message accessors (a paraglide-js equivalent for Clojure/ClojureScript),
CLDR-lite plural rules, a language registry (RTL/tier metadata), a bridge to
the [etzhayyim TM/LLM translation service](#etzhayyim-bridge-i18ntm-import),
and a re-frame + reagent seam so the same views SSR on the JVM and hydrate
live in the browser.

```text
i18n = core (registry+lookup) + plural + registry (lang metadata)
     + messages (defmessages macro) + tm-import (etzhayyim bridge)
     + re-frame seam + reagent seam
```

## Why (paraglide-js comparison)

paraglide compiles each message key into a tree-shakeable, type-checked JS
function (`m.appTitle()`). `defmessages` does the equivalent at the
Clojure/ClojureScript compiler level: it reads an EDN catalog **once, at
macroexpansion time** (which runs on the JVM for both `clj` and `cljs`
builds) and emits one plain `defn` per key. Unused ones are dropped by
ClojureScript's `:advanced` dead-code elimination exactly like unused
paraglide functions are dropped by esbuild/Rollup.

The difference: paraglide's generated functions are locale-specific (one
build per locale, or a runtime locale-swap layer bolted on separately). Here
the generated function is locale-*agnostic* — it always calls
`i18n.core/t`, which resolves against whatever locale is currently active.
What's fixed at compile time is only the **set of valid keys** (an unknown
key is a compile error — the same typo-safety paraglide gives); the
translated text itself stays a runtime lookup, so `i18n.core/set-locale!`
works without a rebuild. Plural/gender branching uses a Fluent-inspired
`{:select :count :one ... :other ...}` shape — the same idea paraglide v2's
own `match`/`when` syntax borrows from
[Project Fluent](https://projectfluent.org/).

## Boundaries

| namespace | role |
|---|---|
| `i18n.core` | runtime registry: `register!`, `set-locale!`, `t` (lookup + interpolation + select dispatch). Zero deps. |
| `i18n.plural` | CLDR-*lite* plural-category rules (curated language families, not full CLDR). Zero deps. |
| `i18n.registry` | language metadata: name/native-name/dir/tier. Curated default table + `load!` to extend from a live registry. Zero deps. |
| `i18n.messages` | `defmessages` macro — compile-time message accessors (see above). Zero deps. |
| `i18n.tm-import` | pure data-shape bridge to/from the etzhayyim TM service's flat JSON (see below). Zero deps. |
| `i18n.re-frame` | `:i18n/*` event/sub registration over `shitsuke.re-frame.core` (real re-frame in the browser, synchronous mini-runtime on the JVM). Depends on `shitsuke`. |
| `i18n.reagent` | `root-attrs` (RTL), `locale-links` + `wire-lang-switch!` (pure-hiccup locale switcher, generalizing kami-mangaka-reader's proven `data-lang` pattern). Depends on `shitsuke`. |

`i18n.core`/`plural`/`registry`/`messages`/`tm-import` are zero third-party
runtime deps (same split as `dot`/`jsonlogic`/`toml`). Only `i18n.re-frame`/
`i18n.reagent` pull in `shitsuke` (for its host-independent re-frame/reagent
seam); real `reagent`/`re-frame` themselves stay behind *shitsuke's own*
`:cljs` alias — a JVM-only consumer of `i18n.core` never pulls a UI
framework.

## Message catalogs

A catalog is a flat map, namespaced-keyword keys, string templates with
`{param}` placeholders or a select map for plural/gender branching:

```clojure
{:app/title "Densha TODO"
 :auth/welcome "Welcome, {name}!"
 :todos/count {:select :count
               :one "{count} task"
               :other "{count} tasks"}}
```

```clojure
(require '[i18n.core :as i18n])

(i18n/register! :en (edn/read-string (slurp (io/resource "i18n/messages/en.edn"))))
(i18n/register! :ja (edn/read-string (slurp (io/resource "i18n/messages/ja.edn"))))

(i18n/t :auth/welcome {:name "Jun"})      ;=> "Welcome, Jun!"
(i18n/set-locale! :ja)
(i18n/t :auth/welcome {:name "Jun"})      ;=> "Jun さん、ようこそ！" (if ja provides it; else falls back to :en)
(i18n/t :todos/count {:count 3})          ;=> plural-category dispatch via i18n.plural
```

Missing keys/locales degrade visibly (`"{missing:app/title}"`) instead of
throwing — a translation gap should be an obvious rendering artifact, not a
crash.

## Compile-time accessors (`i18n.messages/defmessages`)

```clojure
(ns myapp.messages
  ;; :include-macros true is REQUIRED in ClojureScript (harmless/ignored on
  ;; the JVM) — it pulls in i18n.messages as both a macro source (for
  ;; defmessages) and a compiled runtime cljs dependency. Without it, plain
  ;; `:refer [defmessages]` fails to resolve the macro at all under cljs,
  ;; and bare `:require-macros [i18n.messages :refer [defmessages]]` compiles
  ;; but leaves the macro-generated i18n.core/t calls as unresolved vars
  ;; under :advanced optimization (verified against a real shadow-cljs app).
  (:require [i18n.messages :refer [defmessages] :include-macros true]))

(defmessages "i18n/messages/en.edn")
;; => generates (defn app-title ([] ...) ([params] ...))
;;              (defn auth-welcome ([] ...) ([params] ...)) etc.
;;    one per key in en.edn, at compile time.

(myapp.messages/app-title)                 ;=> current-locale's :app/title
(myapp.messages/auth-welcome {:name "Jun"})
```

`resource-path` should point at the SOURCE locale's catalog — its keys
become the app's fixed, typo-checked message API; other locales are
registered at runtime via `i18n.core/register!` and don't need their own
`defmessages` call.

**On "compile-time checked"**: an unknown key (e.g. calling a renamed/typo'd
generated fn) is reported at compile time as an `:undeclared-var` diagnostic
naming the exact file/line — a real static check, not a silent runtime
"{missing:k}". By default ClojureScript reports this as a **warning**, not a
build-halting error, under both `compile` and `:advanced`-optimized
`release` builds (verified). CI setups that want a hard failure (matching
paraglide/TypeScript's usual behavior) should grep build output for
`WARNING` / `:undeclared-var` and fail the job, or configure Closure's
warning-to-error promotion.

### Getting catalog data into a cljs build (`i18n.messages/embed-catalog`)

On the JVM, registering a catalog is just reading the resource at runtime:
`(i18n/register! :en (edn/read-string (slurp (io/resource "..."))))`. The
browser has no classpath, so ClojureScript has no runtime equivalent —
`embed-catalog` is the compile-time counterpart: it reads the EDN file once,
at macroexpansion time, and inlines it as a literal map:

```clojure
(ns myapp.core
  (:require [i18n.core :as i18n]
            [i18n.messages :refer [embed-catalog]]))

(i18n/register! :ja (embed-catalog "i18n/messages/ja.edn"))
(i18n/register! :en (embed-catalog "i18n/messages/en.edn"))
```

Both catalogs end up bundled directly in the compiled JS (fine for a
handful of locales/keys; for many locales, fetch per-locale JSON at runtime
via `i18n.re-frame`'s `:i18n/catalog-loaded` event instead of embedding all
of them upfront).

## Language registry (`i18n.registry`)

```clojure
(require '[i18n.registry :as registry])

(registry/dir :ar)     ;=> :rtl
(registry/rtl? :ar)     ;=> true
(registry/tier :en)     ;=> 1
(registry/search "Japanese")   ;=> ({:i18n.lang/code :ja ...})
```

Ships a curated tier-1 (25 languages) + tier-2 sample table, RTL-flagged
(`ar`/`he`/`fa`/`ur`/`yi`/`ps`/`sd` by default). `load!` extends/overrides it
— e.g. from a live `GetLanguageRegistry`-style service (see below) for apps
that need the full 200+ list.

## etzhayyim bridge (`i18n.tm-import`)

[`i18n.etzhayyim.com`](https://i18n.etzhayyim.com) is an LLM-translation +
human-approved translation-memory *service* (`RegisterProject` /
`TranslateBatch` / `WidgetApprove` / `GetLanguageRegistry`, XRPC). It is the
runtime source of truth for translated strings and does the actual
translation work; this library only converts between its flat dotted-key
JSON shape and this library's namespaced-keyword catalogs — it has no HTTP
client of its own (bring your own; the caller already has a parsed body):

```clojure
(require '[i18n.tm-import :as tm])

;; ExportMessages response -> register! directly
(i18n/register! :ja (tm/export-messages->catalog export-messages-response))

;; catalog -> RegisterProject's `messages` payload
(tm/catalog->register-project {:app/title "Welcome"})  ;=> {"app.title" "Welcome"}

;; GetLanguageRegistry response -> i18n.registry/load!
(registry/load! (tm/language-registry->entries get-language-registry-response))
```

paraglide and this TM service solve different problems: paraglide-style
accessors are for **static UI chrome** compiled into the app; the TM
service is for **content that doesn't exist at build time** (translated
posts, chat messages, user content). The intended loop: the TM service's
`ExportMessages` becomes each app's `i18n/messages/<locale>.edn`, and
`i18n.core`/`defmessages` consume it — no hand-maintained duplicate
catalogs.

## re-frame + reagent

```clojure
(ns myapp.core
  (:require [i18n.re-frame :as i18n-rf]
            [i18n.reagent :as i18n-r]
            [shitsuke.reagent.core :as sr]))

(i18n-rf/init!)                 ; register :i18n/* events/subs once at start

(defn root []
  [:div (i18n-r/root-attrs @(i18n-rf/subscribe [:i18n/locale]))  ; {:lang :dir}
   (i18n-r/locale-links @(i18n-rf/subscribe [:i18n/locale]))
   [:h1 @(i18n-rf/subscribe [:i18n/t :app/title])]])

;; cljs only, once at mount (alongside the app's own mount code):
(i18n-r/wire-lang-switch!)
```

`i18n.re-frame` is built on `shitsuke.re-frame.core`'s host seam — the SAME
registration code runs against real re-frame 1.4.3 in the browser and
against shitsuke's synchronous mini-runtime on the JVM (SSR/tests), the dual
render contract proven by `kami-mangaka-reader-clj`. `i18n.core/*locale`
stays the single source of truth `i18n.core/t` reads (so
`defmessages`-generated top-level functions work correctly even outside a
reactive context); the re-frame layer mirrors it into app-db purely so
Reagent knows when to re-render.

`i18n.reagent/locale-links` + `wire-lang-switch!` generalize the delegated
`a[data-lang]` click-listener pattern already proven by
`kami-mangaka-reader/src/kami/mangaka/reader/app.cljs`'s `wire-lang-switch!`
— SSR emits inert markup (works with JS disabled), one document-level click
listener hydrates it.

## Test

```
kbb -M:test          # standalone (fetches shitsuke via git)
kbb -M:local:test    # monorepo dev, sibling ../shitsuke checkout
```
