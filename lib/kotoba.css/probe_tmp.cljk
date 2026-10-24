(require '[kotoba.compiler.core :as compiler]
         '[kotoba.kir :as ir])
(def src "(ns t)
(defn esc [s :string] :string
  (string-replace-all
    (string-replace-all
      (string-replace-all
        (string-replace-all s \"&\" \"&amp;\")
        \"<\" \"&lt;\")
      \">\" \"&gt;\")
    \"\\\"\" \"&quot;\"))
(defn check [] :string (esc \"a<b>&\\\"c\"))
(defn fold [] :string (string-fold-case \"</SCRIPT>\"))
(defn cont [] :bool (string-contains? (string-fold-case \"x</SCRIPT><img>\") \"</script\"))
(defn void-el [tag :string attrs :string] :string
  (string-concat \"<\" (string-concat tag (string-concat attrs \">\"))))
(defn el [tag :string attrs :string body :string] :string
  (string-concat \"<\" (string-concat tag (string-concat attrs (string-concat \">\" (string-concat body (string-concat \"</\" (string-concat tag \">\"))))))))
(defn demo [] :string
  (el \"div\" (string-concat \" class=\\\"page x\\\"\" \" id=\\\"app\\\"\")
      (string-concat (el \"h1\" \"\" \"Hello\") (void-el \"input\" \" disabled\"))))
(defn raw-ok [] [:result :string :string]
  (let [tag \"script\" content \"const x = \\\"<b>\\\";\"]
    (if (string-contains? (string-fold-case content) (string-concat \"</\" (string-fold-case tag)))
      (result-err-of [:result :string :string] \"breakout\")
      (result-ok-of [:result :string :string]
                    (string-concat \"<\" (string-concat tag (string-concat \">\" (string-concat content (string-concat \"</\" (string-concat tag \">\"))))))))))
(defn raw-bad [] :string
  (match-result
    (let [tag \"script\" content \"x</SCRIPT><img src=x>\"]
      (if (string-contains? (string-fold-case content) (string-concat \"</\" (string-fold-case tag)))
        (result-err-of [:result :string :string] \"breakout\")
        (result-ok-of [:result :string :string] content)))
    [:result :string :string]
    (ok text text)
    (err message \"REJECTED\")))
")
(try
  (let [kir (:kir (compiler/compile-source src :wasm32-kotoba-v1 {}))]
    (println "esc:" (pr-str (ir/execute kir 'check [])))
    (println "fold:" (pr-str (ir/execute kir 'fold [])))
    (println "cont:" (pr-str (ir/execute kir 'cont [])))
    (println "demo:" (pr-str (ir/execute kir 'demo [])))
    (println "raw-bad:" (pr-str (ir/execute kir 'raw-bad []))))
  (catch Exception e
    (println "ERROR:" (.getMessage e))
    (println (ex-data e))
    (.printStackTrace e)))
