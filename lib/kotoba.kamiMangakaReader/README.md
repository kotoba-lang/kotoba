# kami-mangaka-reader-clj

Work-agnostic manga **reader** (ADR-2606282101): one set of hiccup components
(`.cljc`) renders two ways —

- **static build**: SSR via `kami.mangaka.hiccup` (Clojure/babashka) → plain
  HTML pages, readable with no JS.
- **interactive**: reagent + re-frame (ClojureScript, shadow-cljs) → live
  locale switch in-browser, progressively enhancing the same server-rendered
  markup (only the text overlay re-renders per locale; panel images never
  reload).

## Origin

Split out of [`kotoba-lang/kami-engine`](https://github.com/kotoba-lang/kami-engine)'s
[`kami-mangaka-reader-clj/`](https://github.com/kotoba-lang/kami-engine/tree/main/kami-mangaka-reader-clj)
subtree into its own standalone repository, following the same pattern
already used for the sibling `kami-mangaka-genko-clj` -> `kotoba-lang/kami-genko`
split. `kami-engine`'s Rust workspace was deleted in PR #82, but this
Clojure(Script) project was (and remains) live and current — it was copied
out verbatim, not restored from history.

Sibling of `kami-mangaka-text-clj` (the lettering/text-overlay layer this
project composes) and `kami-mangaka-render-clj` / `-page-clj` / `-scene`.

## Layout

```
deps.edn                                  ; clj/cljs deps, :cljs and :test aliases
shadow-cljs.edn                           ; browser build (reader.js)
package.json / package-lock.json          ; npm deps for shadow-cljs (react, react-dom)
src/kami/mangaka/reader/views.cljk        ; shared hiccup views (index + chapter)
src/kami/mangaka/reader/ssr.clj           ; server-side render to HTML strings
src/kami/mangaka/reader/app.cljk          ; reagent/re-frame browser hydration
test/kami/mangaka/reader/ssr_test.cljk     ; SSR test
```

## Known issue: broken monorepo-relative dependency

`deps.edn` declares:

```clojure
gftd/kami-mangaka-text-clj {:local/root "../kami-mangaka-text-clj"}
```

This pointed at a sibling directory inside the `kami-engine` monorepo. In
this standalone repo that sibling does not exist, so `kbb -M:test` (and
any other classpath resolution) currently fails with:

```
Error building classpath. Local lib gftd/kami-mangaka-text-clj not found: <parent-dir>/kami-mangaka-text-clj
```

`kami.mangaka.reader.ssr` and `kami.mangaka.reader.views` both require
`kami.mangaka.text` (overlay CSS/rendering) and `kami.mangaka.hiccup`
(hiccup->HTML), both of which live in
[`kami-mangaka-text-clj`](https://github.com/kotoba-lang/kami-engine/tree/main/kami-mangaka-text-clj)
(not yet split out as of this writing).

**To fix once `kami-mangaka-text-clj` has its own standalone repo** (e.g.
`kotoba-lang/kami-mangaka-text-clj` or similar, following this same split
pattern), update the `:local/root` to a `:git/url` + `:sha` (or a sibling
checkout path) coordinate pointing at that repo instead of the now-absent
monorepo-relative path. Until then, clone `kami-mangaka-text-clj` alongside
this repo at `../kami-mangaka-text-clj` to restore the relative path locally.

## Build / run

This project was **not** built end-to-end as part of the migration (npm
install / amu compile --target wasm32-browser were intentionally skipped — slow and not the
point of a copy-out verification). Once the `kami-mangaka-text-clj`
dependency above is resolved:

```bash
npm install
amu compile --target wasm32-browser reader   # -> dist/reader.js (single-module browser build)
kbb -M:test                  # SSR test suite (needs the classpath fix above)
```

The `:reader` shadow-cljs build target's `:init-fn` is
`kami.mangaka.reader.app/init`; a static manga page includes the emitted
`reader.js` alongside `window.__manga` / `window.__locale` globals injected
by the SSR step (see `kami.mangaka.reader.ssr/document`).
