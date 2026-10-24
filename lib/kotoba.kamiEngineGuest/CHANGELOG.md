# Changelog

Not attempting to reconstruct full history here — this file starts tracking
from this point forward.

## Unreleased

- Added a docstring to `kotoba.engine-clj.ast/host-import`, the last
  genuinely undocumented public `defn` in this repo (a qa-governor
  documentation-coverage scan initially flagged 39 more, but those were all
  false positives: text inside docstrings/comments/error-message strings
  that happens to look like `(defn ...)`, not real code — e.g.
  `kotoba.engine_clj.cljc`'s `game-prelude` embeds guest-language *source
  text* as a string literal, which a naive regex scan can't distinguish
  from this namespace's own real functions).
- Added this CHANGELOG.md.
- Fixed 2 real clj-kondo warnings (`compile` shadowing `clojure.core/compile`
  without declaring it; an unused `if-let` binding) and found + fixed a real
  codegen bug (`expr-children` missing an `:atom-set` case, dropping a
  host-import call nested inside `set-atom!`'s value from import collection)
  — see this repo's own commit history for details.
