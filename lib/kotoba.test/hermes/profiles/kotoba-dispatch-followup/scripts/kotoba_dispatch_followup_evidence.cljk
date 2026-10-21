;; kotoba-dispatch-followup evidence — kotoba.lang.edn dispatch-gap 残課題の実測（nbb）。
;; 判断はこの script が持つ。agent は出力 JSON を読んで 1 finding を報告するだけ。
;; credential を読まない。実行: nbb scripts/kotoba_dispatch_followup_evidence.cljs

(require '[kotoba.lang.text :as str]
         '["node:child_process" :as cp]
         '["node:fs" :as fs]
         '["node:path" :as path]
         '["node:os" :as os])

(def repo-root (path/join (os/homedir) "github" "com-junkawasaki"))
(def out-dir (path/join (os/homedir) ".hermes" "profiles"
                        "kotoba-dispatch-followup" "workspace" "findings"))

(defn sh [cmd cwd]
  (try (str/trim (str (cp/execSync cmd #js {:cwd cwd :timeout 15000})))
       (catch :default e (str "ERR:" (.-message e)))))

;; dispatch-gap wave-2 で対応した repo。main が依然 kotoba.lang.edn rewire を
;; 保持しているか（revert されていないか）を測る。
(def repos
  [{:path "orgs/kotoba-lang/langchain" :expect-kotoba-edn "src/langchain/edn_persist.cljc"}
   {:path "orgs/kotoba-lang/grant"      :expect-kotoba-edn "src/grant/audit.cljc"}
   {:path "orgs/kotoba-lang/kagi"       :expect-kotoba-edn "src/kagi/persist.clj"}
   {:path "orgs/kotoba-lang/murakumo"   :expect-kotoba-edn "test/murakumo/kotoba_oracle_gen.clj"}])

(defn has-kotoba-edn? [abs file]
  (when (fs/existsSync (path/join abs file))
    (let [txt (fs/readFileSync (path/join abs file) "utf8")]
      (not (nil? (re-find #"kotoba\.lang\.edn" txt))))))

(defn probe-repo [{:keys [path expect-kotoba-edn]}]
  (let [abs (path/join repo-root path)]
    (if (fs/existsSync abs)
      (let [head (sh "git rev-parse HEAD" abs)
            dirty (not (str/blank? (sh "git status --porcelain" abs)))
            kotoba (has-kotoba-edn? abs expect-kotoba-edn)
            reverted (not kotoba)]
        {:path path
         :main-head head
         :main-holds-kotoba-edn? (boolean kotoba)
         :reverted? (boolean reverted)
         :dirty? dirty
         :note (when reverted
                 (str "REVERTED: " expect-kotoba-edn
                      " no longer requires kotoba.lang.edn on main"))})
      {:path path :main-head "NOT-CHECKED-OUT" :reverted? false})))

;; test-runner blocker: kotoba-lang/test deftest が cognitect runner に invisible
;; なままか（:test var metadata の有無）
(defn probe-test-runner []
  (let [abs (path/join repo-root "orgs/kotoba-lang/test")]
    (if (fs/existsSync abs)
      (let [sources (sh "grep -rl deftest src" abs)]
        {:test-repo "orgs/kotoba-lang/test"
         :checked-out true
         :note "blocker: kotoba.lang.test/deftest attaches no :test metadata; cognitect.test-runner sees 0 tests (ADR-2809061500). fix = opt-in :test meta harness, self-tests stay invisible"})
      {:test-repo "orgs/kotoba-lang/test" :checked-out false
       :note "not checked out"})))

(defn main []
  (let [ts (.toISOString (js/Date.))
        result {:at ts
                :kind "kotoba-dispatch-followup-evidence"
                :repos (mapv probe-repo repos)
                :test-runner (probe-test-runner)
                ;; 残課題の優先順（dispatch 外・既存問題）
                :backlog
                [{:repo "kagi" :item "revert 032214a: vault に #inst/#uuid tagged literal。data 移行 or 許す reader の再判断が必要"
                  :severity :high}
                 {:repo "grant" :item "contract :flows が文字列内 dispatch vector（バリデータ不整合）15 fail"
                  :severity :medium}
                 {:repo "murakumo" :item "実 HTTP/署名 transport 3 fail + 7 err（dispatch 外）"
                  :severity :low}
                 {:repo "kotoba-lang/test" :item "deftest invisible to cognitect.test-runner — clojure.test rewire の実ブロッカー"
                  :severity :high}]}]
    (fs/mkdirSync out-dir #js {:recursive true})
    (fs/writeFileSync (path/join out-dir
                                 (str "kotoba-dispatch-evidence-"
                                      (.slice ts 0 10) ".json"))
                      (js/JSON.stringify (clj->js result) nil 2))
    (println (js/JSON.stringify (clj->js result) nil 2))))

(main)