# appkit — operator quickstart

From nothing to a page you can open. appkit is a **library**, so "operating"
it means: prove the floor holds, then render something with it and look at the
result.

Every command below was run on 2026-09-10 before it was written down, and the
page it produces was rendered in a browser and looked at. If a step here does
not work for you, that is a bug in appkit or in this file — not something to
route around.

## 0. What you need

| tool | why | check |
|---|---|---|
| `clojure` | resolves the dependency classpath — appkit's deps are pinned git shas in `deps.edn`, and both runtimes read the classpath it computes | `clojure --version` |
| `nbb` | the ClojureScript runtime appkit's consumers actually run on | `nbb --version` |

The first command that touches `deps.edn` clones the pinned dependencies into
`~/.gitlibs`. That needs network and takes a minute or so; every run after it
is offline and fast.

You do **not** need `bb`. This repo has no `nbb.edn` — every `nbb` invocation
here is either handed a `--classpath` or is a bare launcher that computes one,
so nbb never has to resolve coordinates itself.

## 1. Get the checkout

Inside the superproject, appkit is a west project:

```bash
west update --fetch smart appkit
cd orgs/kotoba-lang/appkit
```

Standalone:

```bash
git clone https://github.com/kotoba-lang/appkit.git && cd appkit
```

## 2. Prove the floor — both runtimes, not one

```bash
kbb -M:test                     # JVM
kbb --backend sci test/appkit/cljs_runner.cljk    # the same suite on cljs
```

Both must be run. appkit is `.cljc` and ships to browsers, so a regression
that only exists on the cljs side — a `#?(:clj …)` that swallowed a wrapper, a
reader conditional whose `:cljs` branch drifted — keeps `kbb -M:test`
completely green. The README's *Tests* section has the measurement that forced
this rule, and the `:local` variants for working against a sibling
`../kotoba-ui` checkout.

Expect two green summaries. The JVM count is larger on purpose (three tests
are `#?(:clj …)`-only). The counts move as tests are added; what matters is
that **neither run reports zero** — the cljs runner exits `2` rather than `0`
if it measured nothing, precisely so that "ran and found no problems" and
"never ran" cannot look alike.

## 3. Render a page and look at it

```bash
kbb --backend sci docs/quickstart_page.cljk
```

It prints the path it wrote and what it verified:

```
wrote /var/folders/…/appkit-quickstart.html (63397 bytes, 61391 of them inlined CSS)
checked: whole document / appkit defaults present / caller opt still overrides / stylesheet inlined
```

Then open it:

```bash
open /var/folders/…/appkit-quickstart.html      # the path it printed
```

Pass a path of your own as the first argument if you want it somewhere
specific. The default is the OS temp dir, deliberately — rendering the
quickstart should never leave anything in your working tree.

## 4. What you are looking at

One window, two panels, and the whole of appkit visible in the difference
between them:

- **the first panel** takes appkit's desktop defaults — a thick surface, flat
  elevation, sitting flush rather than floating — and holds a list-view that
  also picks up its thick default.
- **the second panel** is the *same function* with `{:elevation :floating}`
  passed in. It keeps the thick surface and takes the caller's elevation.

That is the entire contract: `(merge defaults opts)`, the caller always wins.
You can see it in the markup rather than take it on faith:

```bash
H=/var/folders/…/appkit-quickstart.html                 # the path it printed
sed -n 's/.*<body/<body/p' "$H" | grep -o 'liquid-glass__panel--[a-z]*' | sort -u
```

```
liquid-glass__panel--flat
liquid-glass__panel--floating
liquid-glass__panel--thick
```

Three modifiers on real elements: appkit's two defaults, and the caller's
override.

⚠ **Search the body, not the file.** The same `grep` without the `sed` returns
five — it also finds `--clear` and `--overlay`, which are on nothing. The
document inlines kotoba-ui's entire stylesheet, and that stylesheet defines a
rule for every modifier that exists, so a whole-file search finds `--floating`
whether or not any element got it. This is not hypothetical: while this page
was being built, a whole-file check called appkit correct after its merge was
reversed, after its panel defaults were deleted, and after its list-view
default was deleted. `docs/quickstart_page.cljk` looks only inside `<body>`
for exactly this reason, and the comment there records the measurement.

## When it does not work

`docs/quickstart_page.cljk` separates "appkit is wrong" from "I could not get
far enough to look", because those need different responses:

| exit | means | do |
|---|---|---|
| `0` | rendered, and carries all four properties | — |
| `1` | rendered, but a property is missing — the output names which one and why | that named property is the bug; the message says what it implies |
| `2` | **REFUSED** — the classpath or the render subprocess never ran, so nothing was measured | fix the environment; this is not a statement about appkit |

A `2` means one of exactly two things did not happen: `kbb -Spath` did not
resolve a classpath, or the render subprocess did not run. The refusal says
which, and repeats the underlying error. If it was the classpath, run it on
its own to see that error directly — on a first run it is usually the network,
while the pinned deps are still being cloned:

```bash
kbb -Spath
```

## Next

- `README.md` — what appkit wraps, and why only two components.
- `docs/design.md` — the wrapped-component table and the variance-point
  argument behind it.
- `docs/adr/0001-appkit.md` — the decision, in full, with the alternatives.
- [`kotoba-ui/docs/agent-guide.md`](../../kotoba-ui/docs/agent-guide.md) — the
  paved road for actually building an app on this stack. Read it before you
  write app CSS; apps call `kotoba-ui.core` plus this binding, never
  `liquid-glass.*` / `shitsuke.*` directly.
