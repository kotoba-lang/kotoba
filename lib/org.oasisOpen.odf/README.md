# kotoba-lang/org-oasis-odf

Safety-bounded OpenDocument Format content inspection in sovereign Kotoba.

`src/odf.kotoba` is the sole production source. An archive capability/provider
expands the package, validates UTF-8, and passes the decoded `mimetype`,
`content.xml`, and entry count across the typed ABI. The pure Kotoba module
detects the document kind and exposes paragraph count plus indexed paragraph
text. This represents every paragraph without admitting an unbounded host
sequence.

The compiler targets restricted JavaScript and typed WebAssembly. Clojure and
the JVM are compiler/test hosts only, never the production runtime.

## Test

```sh
kbb -M:test
kbb -M:lint
```
