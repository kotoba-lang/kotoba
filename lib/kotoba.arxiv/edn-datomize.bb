#!/usr/bin/env kbb
;; manifest/edn-datomize.bb — EDN → Datomic/Datascript tx-data 変換ツール。
;;
;; 「datomic/datascript query 可能」の定義: ファイルのトップレベルが
;; (d/transact conn (edn/read-string (slurp file))) にそのまま渡せる
;; tx-data ベクタ（entity-map のベクタ、各 map は :db/id を持つ）であること。
;;
;; マップ1個のファイルは [{...:db/id -1}] に包み、既存キーはファイル種別ごとの
;; 名前空間を付けた属性名にリネームする。値が Datomic の scalar valueType
;; （string/long/double/boolean/keyword、またはそれらの集合）に収まらないもの
;; （入れ子 map、map を含む vector 等）は pr-str した文字列として保持する
;; （valueType=string の "blob" 属性にする — トップレベルの entity+attribute
;;  粒度でのクエリは常に有効、blob の中身は呼び出し側で edn/read-string すれば
;;  読める）。属性定義は manifest/schema.edn に自動登録する（Datomic/Datascript
;; 両対応、:db.install/_attribute 等の Datomic 固有キーは使わない）。
;;
;; 使い方:
;;   bb edn-datomize.bb wrap-map <path> <ns>          — map 1個のファイルを変換
;;                                                       (トップレベル全キーに ns を強制)
;;   bb edn-datomize.bb wrap-map-keep-ns <path> <ns>  — map 1個のファイルを変換
;;                                                       (既に名前空間付きのキーはそのまま保持し、
;;                                                        裸キーだけ ns を付与。kotoba-lang/security の
;;                                                        ような :register/type 等の慣用的に
;;                                                        名前空間付き map 向け。ADR generic transform と
;;                                                        同じ規則)
;;   bb edn-datomize.bb adr-dir  <dir>                 — ADR frontmatter/body を変換
;;   bb edn-datomize.bb adr-file <path>                — ADR 1ファイルを変換
;;
;; このコピーは kotoba-lang/security 用に schema-path のみ調整（manifest/ が無いので
;; リポジトリルート直下 schema.edn）。他のロジックは
;; com-junkawasaki/root の manifest/edn-datomize.bb と同一。

(require '[clojure.edn :as edn]
         '[clojure.java.io :as io]
         '[clojure.java.shell :as shell]
         '[clojure.string :as str])

(def root (str/trim (:out (shell/sh "git" "rev-parse" "--show-toplevel"))))

(defn schema-path [] (io/file root "schema.edn"))

(defn slurp-edn [path] (edn/read-string (slurp path)))

(defn already-tx-data?
  "既に [{...:db/id ...} ...] 形式に変換済みか判定（再実行の冪等性用）。"
  [content]
  (and (vector? content) (seq content) (map? (first content)) (contains? (first content) :db/id)))

(defn classify
  "値から Datomic :db/valueType + :db/cardinality を推定する。scalar に収まらない
   値（入れ子 map / map を含む vector 等）は :blob true を返す(pr-str して string 化)。"
  [v]
  (cond
    (string? v)  {:type :db.type/string  :card :db.cardinality/one}
    (boolean? v) {:type :db.type/boolean :card :db.cardinality/one}
    (integer? v) {:type :db.type/long    :card :db.cardinality/one}
    (double? v)  {:type :db.type/double  :card :db.cardinality/one}
    (keyword? v) {:type :db.type/keyword :card :db.cardinality/one}
    (nil? v)     {:type :db.type/string  :card :db.cardinality/one}
    (and (coll? v) (empty? v))
    {:type :db.type/string :card :db.cardinality/many}
    (and (coll? v) (every? string? v))  {:type :db.type/string  :card :db.cardinality/many}
    (and (coll? v) (every? keyword? v)) {:type :db.type/keyword :card :db.cardinality/many}
    (and (coll? v) (every? integer? v)) {:type :db.type/long    :card :db.cardinality/many}
    :else {:type :db.type/string :card :db.cardinality/one :blob true}))

(defn attr-value [v]
  (let [{:keys [blob]} (classify v)]
    (if blob (pr-str v) v)))

(defn namespaced-key [ns-name k]
  (keyword ns-name (name k)))

(defn entity-from-map
  "トップレベル map の各キーに ns-name の名前空間を付け、:db/id を足した 1 entity にする。"
  [content ns-name]
  (into {:db/id -1}
        (map (fn [[k v]] [(namespaced-key ns-name k) (attr-value v)]))
        content))

(defn schema-attrs
  [content ns-name]
  (for [[k v] content]
    (let [{:keys [type card]} (classify v)]
      {:db/ident (namespaced-key ns-name k)
       :db/valueType type
       :db/cardinality card})))

(defn load-schema []
  (let [f (schema-path)]
    (if (.exists f) (slurp-edn f) [])))

(defn merge-schema! [new-attrs]
  (let [existing (load-schema)
        by-ident (into {} (map (juxt :db/ident identity)) existing)
        merged-by-ident (reduce (fn [acc {:keys [db/ident] :as attr}]
                                   (if (contains? acc ident) acc (assoc acc ident attr)))
                                 by-ident
                                 new-attrs)
        merged (vec (sort-by (comp str :db/ident) (vals merged-by-ident)))]
    (spit (schema-path) (str ";; schema.edn — Datomic/Datascript 互換スキーマ定義（自動生成 by edn-datomize.bb）\n"
                              ";; :db/ident 属性定義のリスト。Datomic 固有キー(:db.install/_attribute 等)は使わない。\n"
                              ";; 手編集禁止 — 再生成すると上書きされる。\n"
                              ";;\n"
                              ";; wrap-map-keep-ns で変換したファイルは、元々 Clojure 慣用の名前空間付き\n"
                              ";; キーワード(:register/type, :case/id 等)をそのまま保持し、裸キーだけ\n"
                              ";; ファイル(ディレクトリ)単位の namespace を付与している。同じ属性名でも\n"
                              ";; 由来ファイルによって非scalar値の実データ形が異なる場合があるが、値は\n"
                              ";; すべて pr-str の \"blob\" (valueType=string) として保持しているため型は\n"
                              ";; 常に一意 — ADR 系(90-docs/adr/*.edn)のような型不一致の問題はここでは生じない。\n\n"
                              (pr-str merged)
                              "\n"))
    merged))

(defn wrap-map! [rel-path ns-name]
  (let [f (io/file root rel-path)
        content (slurp-edn f)]
    (if (already-tx-data? content)
      (println "skip (already tx-data):" rel-path)
      (let [entity (entity-from-map content ns-name)
            attrs (schema-attrs content ns-name)]
        (spit f (pr-str [entity]))
        (merge-schema! attrs)
        (println "wrapped" rel-path "->" (count entity) "attrs, ns=" ns-name)))))

;; ---------- keep-ns variant (files whose top-level keys are already
;;            idiomatically namespaced, e.g. :register/type, :case/id) ----------
;;
;; kotoba-lang/security の conformance/policy/registers 系ファイルは
;; Clojure 慣用の名前空間付きキーワード（:register/type, :evidence/id,
;; :case/id 等）を最初からトップレベルに使っている。wrap-map! のように
;; 全キーへ機械的にファイル単位の ns を上書きすると、既存の意味のある
;; namespace（:register, :evidence, :case ...）が失われ、消費側コードの
;; reconstitute（namespace 復元）が複雑になる。ADR generic transform と同じ
;; 規則（namespace が既にあれば保持し、裸キーだけ ns-name を付与）を使うことで、
;; 消費側の復元は「attr の namespace が ns-name と一致する裸キーだけ剥がす」
;; という単純な規則で済む。

(defn keep-ns-key [ns-name k]
  (if (namespace k) k (keyword ns-name (name k))))

(defn transform-keep-ns [content ns-name]
  (into {:db/id -1}
        (map (fn [[k v]] [(keep-ns-key ns-name k) (attr-value v)]))
        content))

(defn schema-attrs-keep-ns [content ns-name]
  (for [[k v] content]
    (let [{:keys [type card]} (classify v)]
      {:db/ident (keep-ns-key ns-name k)
       :db/valueType type
       :db/cardinality card})))

(defn wrap-map-keep-ns! [rel-path ns-name]
  (let [f (io/file root rel-path)
        content (slurp-edn f)]
    (if (already-tx-data? content)
      (println "skip (already tx-data):" rel-path)
      (let [entity (transform-keep-ns content ns-name)
            attrs (schema-attrs-keep-ns content ns-name)]
        (spit f (pr-str [entity]))
        (merge-schema! attrs)
        (println "wrapped(keep-ns)" rel-path "->" (count entity) "attrs, ns=" ns-name)))))

;; ---------- ADR (90-docs/adr/*.edn) ----------
;;
;; 実測(2026-07-10): 458 ファイル中、トップレベル shape は :frontmatter+:body の
;; 単純形（約130件）から :frontmatter+(:problem/:decision/:consequences/...の
;; 多様な追加キー)、さらに :frontmatter を持たず :adr/id :adr/status 等を
;; 最初から名前空間付きで直接トップレベルに持つ別系統（fleet/governor 由来、
;; 90件超）まで極めて多様。個別 shape を全列挙するのではなく、
;; 汎用ルールで統一的に扱う: :frontmatter があればその中身をトップレベルへ
;; マージし、名前空間の無いキーには :adr/ を付与、既に名前空間付き(:adr/xxx等)の
;; キーはそのまま使う。値は classify/attr-value で scalar はそのまま、
;; 非scalar(入れ子 map/vector-of-map)は pr-str blob にする。
;; :related/:supersedes/:superseded_by は ADR-id と生ドキュメントパスが混在する
;; 実データ（例: 2607011345 の :related は ["AGENTS.md" "....md" ...]）ため、
;; Datomic lookup-ref 化はせず素の文字列 vector のまま保持する。

(defn adr-key [k]
  (if (namespace k) k (keyword "adr" (name k))))

(defn transform-adr-generic [content]
  (let [fm (:frontmatter content)
        base (dissoc content :frontmatter)
        fm-entries (when (map? fm) (seq fm))
        entries (concat fm-entries (seq base))
        m (into {:db/id -1}
                (map (fn [[k v]] [(adr-key k) (attr-value v)]))
                entries)]
    [m]))

(defn adr-schema-for [entity]
  (for [[k v] (dissoc entity :db/id)]
    (let [{:keys [type card]} (classify v)]
      {:db/ident k :db/valueType type :db/cardinality card})))

(defn adr-file! [f report]
  (try
    (let [content (slurp-edn f)]
      (cond
        (already-tx-data? content)
        (do (println "skip (already tx-data):" (str f)) (swap! report update :skipped conj (str f)))

        (not (map? content))
        (do (println "skip (not a frontmatter map, likely already data payload):" (str f))
            (swap! report update :skipped conj (str f)))

        :else
        (let [tx (transform-adr-generic content)]
          (spit f (pr-str tx))
          (swap! report update :attrs into (mapcat adr-schema-for tx))
          (swap! report update :ok conj (str f)))))
    (catch Exception e
      (println "SKIP (parse/transform error):" (str f) "->" (.getMessage e))
      (swap! report update :errors conj [(str f) (.getMessage e)]))))

(defn adr-dir! [dir]
  (let [files (->> (io/file root dir) file-seq (filter #(str/ends-with? (str %) ".edn")) sort)
        report (atom {:ok [] :skipped [] :errors [] :attrs []})]
    (doseq [f files] (adr-file! f report))
    (merge-schema! (:attrs @report))
    (println "done." (count files) "files:" (count (:ok @report)) "transformed,"
             (count (:skipped @report)) "skipped," (count (:errors @report)) "errors.")
    (when (seq (:errors @report))
      (println "=== ERRORS (left untouched, pre-existing data issues) ===")
      (doseq [[f m] (:errors @report)] (println " " f "->" m)))
    (when (seq (:skipped @report))
      (println "=== SKIPPED ===")
      (doseq [f (:skipped @report)] (println " " f)))
    @report))

(defn -main [& args]
  (let [[mode a b] args]
    (case mode
      "wrap-map"         (wrap-map! a b)
      "wrap-map-keep-ns" (wrap-map-keep-ns! a b)
      "adr-dir"  (adr-dir! a)
      "adr-file" (let [report (atom {:ok [] :skipped [] :errors [] :attrs []})]
                   (adr-file! (io/file root a) report)
                   (merge-schema! (:attrs @report))
                   (println @report))
      (do (println "usage: bb edn-datomize.bb [wrap-map <path> <ns> | wrap-map-keep-ns <path> <ns> | adr-dir <dir> | adr-file <path>]")
          (System/exit 1)))))

(apply -main *command-line-args*)
