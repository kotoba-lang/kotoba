(ns woff.bytes
  "Portable read cursor over a sequence of unsigned byte values (0-255).
   Pure cljc. Self-contained copy of the primitive kasane.bytes provides —
   duplicated deliberately so this repo has zero kotoba-lang dependencies
   beyond org-ietf-deflate and org-iso-opentype.")

(defn cursor [data]
  (let [v (vec data)]
    {:data v :len (count v) :pos (atom 0)}))

(defn read-bytes! [c n]
  (let [p @(:pos c) end (+ p n)]
    (when (> end (:len c)) (throw (ex-info "woff.bytes EOF read-bytes" {:pos p :n n :len (:len c)})))
    (reset! (:pos c) end)
    (subvec (:data c) p end)))

(defn uint! [c n big?]
  (let [bs (read-bytes! c n)
        bs (if big? bs (reverse bs))]
    (reduce (fn [acc b] (+ (* acc 256) b)) 0 bs)))

(defn bytes->ascii [bs]
  (apply str (map char bs)))
