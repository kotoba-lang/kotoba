(ns kotoba-client.prolly-hydrate
  "Compatibility facade: prolly-tree nodes now carry REAL tag-42 IPLD links
  for their child references, so the prolly-specific `children` walk this
  namespace used to implement is subsumed by the generic link walk in
  `kotoba-client.ipld-hydrate`. Kept as a delegating var so existing
  callers keep working; prefer `kotoba-client.ipld-hydrate/missing-cids`
  in new code."
  (:require [kotoba-client.ipld-hydrate :as ih]))

(def missing-cids
  "See `kotoba-client.ipld-hydrate/missing-cids` (generic tag-42 walk)."
  ih/missing-cids)
