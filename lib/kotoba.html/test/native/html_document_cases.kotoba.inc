;; Appended to the owner source by the native test harness.
(defn main [] :i64
  (let [l (leaf (record-new [:ref :hdoc/leaf] "p" "A&<\""))
        a (document-map :z (document-string "last") :a (document-string "x&y"))
        d (leaf-attrs (record-new [:ref :hdoc/leaf-attrs] "p" a "hello"))
        b (branch (record-new [:ref :hdoc/branch] "div"
                    (document-vector l (void-node "br"))))]
    (cond
      (not (string=? (render l) "<p>A&amp;&lt;&quot;</p>")) 1
      (not (string=? (render d) "<p a=\"x&amp;y\" z=\"last\">hello</p>")) 2
      (not (string=? (render b) "<div><p>A&amp;&lt;&quot;</p><br></div>")) 3
      (not (string=? (html5 b) "<!DOCTYPE html>\n<div><p>A&amp;&lt;&quot;</p><br></div>")) 4
      :else 0)))
