# kotoba-lang/org-w3-epub

Safety-bounded EPUB 3 package inspection in sovereign Kotoba.

`src/epub.kotoba` is the sole production source. An archive provider expands
the package, validates UTF-8, resolves admitted relative archive paths, and
passes `container.xml`, OPF, and individual XHTML documents across the typed
ABI. Kotoba exposes package path, title, manifest entries, spine order, and
chapter text through bounded counts and indexed option-string access.

The sealed XML parser admits only the fixed XHTML5 `<!DOCTYPE html>` form.
External identifiers and internal subsets fail closed. Clojure and the JVM are
compiler/test hosts only, never the production runtime.

## Test

```sh
kbb -M:test
kbb -M:lint
```
