;; Appended to the owner source by the native test harness.
(defn main [] :i64
  (let [m (typed-map-new [:map :keyword :string] :z "last" :a "x&\"<>")
        empty (typed-map-new [:map :keyword :string])
        u (typed-map-new [:map :keyword :string] : "bmp" :𐀀 "astral")
        many (typed-map-new [:map :keyword :string] :k30 "v" :k29 "v" :k28 "v" :k27 "v" :k26 "v" :k25 "v" :k24 "v" :k23 "v" :k22 "v" :k21 "v" :k20 "v" :k19 "v" :k18 "v" :k17 "v" :k16 "v" :k15 "v" :k14 "v" :k13 "v" :k12 "v" :k11 "v" :k10 "v" :k09 "v" :k08 "v" :k07 "v" :k06 "v" :k05 "v" :k04 "v" :k03 "v" :k02 "v" :k01 "v" :k00 "v")]
    (cond
      (not (string=? (esc "&<>\"") "&amp;&lt;&gt;&quot;")) 1
      (not (string=? (attrs m) " a=\"x&amp;&quot;&lt;&gt;\" z=\"last\"")) 2
      (not (string=? (style-css m) "a:x&\"<>;z:last;")) 3
      (not (string=? (attrs empty) "")) 4
      (not (string=? (attrs-from (record-new [:ref :html/attrs-from] m -1 "prefix")) "prefix")) 5
      (not (string=? (attrs-from (record-new [:ref :html/attrs-from] m 2 "end")) "end")) 6
      (not (string=? (attrs u) " 𐀀=\"astral\" =\"bmp\"")) 7
      (not (string=? (tag-attrs "p.hello#id") " class=\"hello\" id=\"id\"")) 8
      (not (string=? (el (record-new [:ref :html/el] "p" "" "&amp;")) "<p>&amp;</p>")) 9
      (not (raw-text-safe? (record-new [:ref :html/raw-pair] "script" "safe"))) 10
      (raw-text-safe? (record-new [:ref :html/raw-pair] "script" "</script>")) 11
      (not (string=? (attrs many) " k00=\"v\" k01=\"v\" k02=\"v\" k03=\"v\" k04=\"v\" k05=\"v\" k06=\"v\" k07=\"v\" k08=\"v\" k09=\"v\" k10=\"v\" k11=\"v\" k12=\"v\" k13=\"v\" k14=\"v\" k15=\"v\" k16=\"v\" k17=\"v\" k18=\"v\" k19=\"v\" k20=\"v\" k21=\"v\" k22=\"v\" k23=\"v\" k24=\"v\" k25=\"v\" k26=\"v\" k27=\"v\" k28=\"v\" k29=\"v\" k30=\"v\"")) 12
      (not (string=? (attrs-from (record-new [:ref :html/attrs-from] m 1 "prefix")) "prefix z=\"last\"")) 13
      (not (string=? (style-from (record-new [:ref :html/style-from] m 1 "prefix")) "prefixz:last;")) 14
      :else 0)))
