(ns kasane.gltf
  "Thin adapter over org-khronos-glb — this ns used to have its own minimal
   GLB chunk reader; org-khronos-glb already has an equivalent implementation
   (chunk framing via `glb/parse-glb` + generic JSON via `glb.json/parse`).
   org-khronos-glb's scope is deliberately narrow (binary container framing +
   raw JSON only, no glTF-JSON schema knowledge — no accessor/mesh/material
   decoding, per its own README), which is all kasane.normalize/gltf->doc
   needs (node/mesh/scene counts + transforms read straight off the raw JSON
   map). See ADR-2606272100 and the kotoba-lang reverse-domain media/graphics
   standards-substrate split (com-junkawasaki/root)."
  (:require [glb]
            [glb.json :as glb-json]
            [kasane.bytes :as b]))

(defn parse
  "Parse glTF `data` (auto-detects .glb binary vs .gltf JSON text) →
   {:json <parsed-map> :bin (nilable bytes) :binary? bool}."
  [data]
  (let [bv (vec data)]
    (if (and (>= (count bv) 4) (= (glb/le-bytes->u32 (subvec bv 0 4)) glb/glb-magic))
      (assoc (glb/parse-glb bv) :binary? true)
      {:json (glb-json/parse (b/bytes->ascii bv)) :bin nil :binary? false})))
