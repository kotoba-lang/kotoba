# kotoba-build

**The build, as a value.** `kotoba/build_core.kotoba` turns a config into an
ordered vector of inert steps; `bin/kotoba_build.cljk` performs them. Nothing
about what a build *is* — the step order, the shell, the manifest, whether a
title may go in a page — is decided in JavaScript.

This is the shadow-cljs-shaped piece of the Kotoba browser stack: config in,
a deployable directory out. It compiles with an **empty
`requiredCapabilities`**, because deciding a build touches nothing.

```bash
kbb --backend sci bin/kotoba_build.cljk example/build.edn                 # release
kbb --backend sci bin/kotoba_build.cljk example/build.edn --mode dev      # ends by serving it
```

```
kotoba-build counter -> …/dist (release)
  module-lock app.lock.edn
  compile     app.mjs 92062 bytes
  runtime     dom-driver.mjs 10446 bytes
  runtime     browser-host.mjs 154988 bytes
  write       index.html
  manifest    build-manifest.edn 8 outputs
```

## The plan

| step | performed by the host as |
|---|---|
| `[:module-lock {…}]` | `kotoba -M module-lock` — pins the module graph |
| `[:compile {…}]` | `kotoba -M compile --module-lock` — emits the restricted ESM |
| `[:runtime {:assets […]}]` | copies amu's `dom-driver.mjs` + `browser-host.mjs` |
| `[:write {:path :content}]` | writes the single-page shell |
| `[:manifest {…}]` | measures every output's bytes and sha256, then asks the guest what the record means |
| `[:serve {…}]` | dev only: a static server over the output directory |
| `[:refuse {:why :what}]` | the guest refused the config; the host stops |

A release build ends by recording what it produced; a dev build ends by
serving it. Nothing about the emitted module differs between them — a dev
build is the same artifact with a server in front of it.

## What the shell is

One document, one bundle, one mount (ADR-2608080100). The driver is **amu's
`runtime/dom-driver.mjs`, required rather than rewritten** — the browser-stack
charter's rule — and it wants a *factory*, because an instance's fuel is spent
and never replenished. The emitted ESM's `instantiateKotoba` is exactly that.

```html
<div id="app"></div>
<script type="module">
import { instantiateKotoba } from "./app.mjs";
import { mountKotobaApp } from "./dom-driver.mjs";
mountKotobaApp({ instantiate: instantiateKotoba, container: document.getElementById("app") });
</script>
```

**The title is admitted, not escaped.** A title carrying `<`, `>`, `&`, `"` or
`'` is refused and the build stops. `kotoba-lang/html` already owns HTML
escaping, and a second copy of an escaping rule is how one copy gets fixed and
the other stays broken. When the shell needs real text it should require that
module, not grow an escaper here.

## A multi-repo build

`--source-path` may be repeated (measured 2026-09-09), so a Kotoba module graph
links across repositories. `example/counter_app.kotoba` is written against
shitsuke's Kotoba re-frame pair and resolves it that way:

```clojure
:source-paths ["." "…/orgs/kotoba-lang/shitsuke/kotoba"]
```

## Measured, and the bound it makes visible

`browser-host.mjs` is **155 KB of Wasm host shipped for one function**,
`reconcileUiDocument`, which `dom-driver.mjs` imports. The manifest shows it as
bytes rather than hiding it. The fix is upstream — amu splitting the reconciler
into its own module — not a second reconciler here.

There is **no watch and no hot reload**: `--mode dev` serves, it does not
rebuild. A dev server that silently served yesterday's bundle would be exactly
the failure this repo is about, so it says so instead.

## Tests

```bash
# the plan, the shell and the manifest, on :jvm-kir :js and :wasm.
# ABSOLUTE paths: a relative one is "input must be a regular file".
kotoba -M test "$PWD/kotoba/build_core.kotoba"

# build the example app, serve it, and CLICK IT in a real headless browser
kbb --backend sci test/build_acceptance.cljk
```

The acceptance ends in a browser on purpose. A test that asserted the plan's
shape would pass on a day when the page loaded blank, and a page that renders
but never answers a click is the same failure one step later. So the last
checks are the DOM the guest drew, the click the driver carried back, and the
state it changed.
