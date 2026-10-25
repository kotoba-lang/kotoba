# kami-mangaka-text-clj

Work-agnostic, **multilingual manga text layer** (ADR-2606282101): the
lettering layer — dialogue / narration / SFX / thought — kept as DATA and
separate from the panel image, so one language-neutral render serves every
locale. The `MangaText` shape follows ghosthacker's proto (`type`/`x`/`y`/
`style`) but the text itself is a **locale map** (`{:ja … :en …}`); the genko
editor's fukidashi types and `writing-mode: vertical-rl` are first-class.

Two renderers consume the same schema: an HTML/CSS overlay (web reader,
mobile) and a Java2D bake (`kami-mangaka-page-clj`, EPUB/KDP). Pure
`cljc` — babashka-safe, no GPU, no AWT in this namespace.

This was split out of `kotoba-lang/kami-engine`'s `kami-mangaka-text-clj/`
subtree into its own standalone repo, following the same pattern used for
the sibling `kami-mangaka-genko-clj` -> `kotoba-lang/kami-genko` split. It is
a **dependency of** [`kotoba-lang/kami-mangaka-page-clj`](https://github.com/kotoba-lang/kami-mangaka-page-clj)
and [`kotoba-lang/kami-mangaka-reader-clj`](https://github.com/kotoba-lang/kami-mangaka-reader-clj),
which both declare it via:

```clojure
gftd/kami-mangaka-text-clj {:local/root "../kami-mangaka-text-clj"}
```

## Namespaces

- `kami.mangaka.text` — the `MangaText` data model, locale coercion/fallback
  (`coerce-text`, `localize`, `locales`), kinds (`:dialogue` / `:narration` /
  `:sfx` / `:thought` / `:chatter` / `:nameplate`), fukidashi bubble shapes,
  and weights. Returns hiccup so reagent can render it directly in the
  browser.
- `kami.mangaka.hiccup` — renders the same `MangaText` data to static HTML
  (for the non-reagent / server-rendered build path), sharing the schema
  with `kami.mangaka.text`.

## Usage

```clojure
;; deps.edn
gftd/kami-mangaka-text-clj {:local/root "../kami-mangaka-text-clj"}
```

```clojure
(require '[kami.mangaka.text :as text])
(text/localize {:ja "こんにちは" :en "Hello"} :en) ;=> "Hello"
```

## Tests

```bash
kbb -M:test
```
