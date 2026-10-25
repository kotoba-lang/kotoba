# kotoba-lang/expr

Expression-as-data compiler core for kotoba DSLs.

`expr.core/compile` turns EDN expression trees into target-specific infix
source strings. Targets customize identifier, number, call, and special-form
rendering.

```clojure
(require '[expr.core :as expr])

(expr/compile [:+ :a [:* :b 2]])
;; => "(a + (b * 2))"
```

Compatibility namespace:

- `kotoba.expr`

Verify:

```sh
kbb -M:test
```
