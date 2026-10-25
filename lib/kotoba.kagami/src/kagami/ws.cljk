(ns kagami.ws
  "Workspace manager (Phase 2 remainder, ADR-2607160005 Plane 3).
  Pure planning/policy — IO injected by the CLI (same style as kagami.sync).
  Cursor-2.0-style hygiene: automatic GC with age + machine-count caps,
  dirty workspaces never collected."
  (:require [kotoba.lang.text :as str]))

(defn gc-plan
  "workspaces: [{:path .. :age-h n :dirty? bool} ...]
  policy: {:max-age-h n :max-count n}
  -> {:remove [path ..] :keep [path ..] :skipped-dirty [path ..]}
  Removal order: expired first, then oldest beyond max-count. Dirty are
  never removed (west semantics: dirty is sacred)."
  [workspaces {:keys [max-age-h max-count]}]
  (let [{dirty true clean false} (group-by (comp boolean :dirty?) workspaces)
        expired (filter #(and max-age-h (> (:age-h %) max-age-h)) clean)
        alive   (remove (set expired) clean)
        over    (if (and max-count (> (count alive) max-count))
                  (take (- (count alive) max-count) (sort-by :age-h > alive))
                  [])
        remove-set (set (concat expired over))]
    {:remove (mapv :path (sort-by :age-h > remove-set))
     :keep (mapv :path (remove remove-set alive))
     :skipped-dirty (mapv :path dirty)}))
