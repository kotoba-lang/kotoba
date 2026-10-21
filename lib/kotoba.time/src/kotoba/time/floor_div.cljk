(ns kotoba.time.floor-div
  "floor-div -- addressed on its own.

  Split out of kotoba.lang.time on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn floor-div
  "Integer division that floors toward negative infinity (unlike `quot`,
  which truncates toward zero) -- consistent with `mod`, which Clojure
  already defines as floored (result always has the sign of `b`). Derived
  from that floored `mod` so the two never disagree: `a = b*floor-div +
  floor-mod` exactly, with no separate rounding rule to drift out of sync."
  [a b]
  (quot (- a (mod a b)) b))
