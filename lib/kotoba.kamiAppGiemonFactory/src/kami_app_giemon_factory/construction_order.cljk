(ns kami-app-giemon-factory.construction-order
  "The 4D construction order (`ConstructionOrder`/`OrderStep` in `scene.rs`),
  generated in the original crate from `construction.edn` into
  `construction.order.json` and deserialized via serde. That JSON is not
  present anywhere in this monorepo checkout (confirmed absent alongside the
  rest of the `giemon-factory-r0` scene data), so `ConstructionOrder::load`
  is not ported — callers supply the parsed order map.

  An order map: `{:order/of \"giemon-factory-r0\" :order/steps [...]}`. Each
  step: `{:step/seq n :step/id .. :step/name .. :step/trade .. :step/robot ..
  :step/zone .. :step/duration-d .. :step/reveals [id ...]}` — 1:1 with the
  Rust `OrderStep` fields (kebab-case).

  `seq-contiguous?` and `reveals-resolve?` are inlined from the Rust crate's
  own `#[cfg(test)]` suite (`order_is_contiguous_and_reveals_resolve`) —
  genuine order-validity checks, not just test scaffolding, so they're ported
  as reusable predicates rather than left behind as test-only code.
  `steps-resolve-robots?` is inlined from `robots_load_and_steps_assigned`
  for the same reason.")

(defn programme-days
  "Total nominal programme length (sum of step durations), in days."
  [order]
  (reduce + (map :step/duration-d (:order/steps order))))

(defn seq-contiguous?
  "True if `:step/seq` across the order's steps is exactly `1..=N`, in order
  (ported from `order_is_contiguous_and_reveals_resolve`)."
  [order]
  (let [seqs (map :step/seq (:order/steps order))
        n (count seqs)]
    (= seqs (vec (range 1 (inc n))))))

(defn reveals-resolve?
  "True if every id revealed by every step is a member of `known-ids`
  (ported from `order_is_contiguous_and_reveals_resolve`, which builds this
  set from `factory/element-ids`)."
  [order known-ids]
  (every? #(every? known-ids (:step/reveals %)) (:order/steps order)))

(defn steps-resolve-robots?
  "True if every step names a non-empty `:step/robot` that resolves in
  `known-robot-ids` (ported from `robots_load_and_steps_assigned`, which
  asserted `!s.robot.is_empty()` and `robots.get(&s.robot).is_some()` for
  every step)."
  [order known-robot-ids]
  (every? (fn [{:keys [step/robot]}]
            (and (some? robot) (not= robot "") (contains? known-robot-ids robot)))
          (:order/steps order)))
