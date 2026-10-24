(ns graphql.model
  "GraphQL スキーマを EDN/Clojure データとして表現する正準モデル。I/O なし、
  third-party 依存なし — portable .cljc (JVM, ClojureScript, SCI)。

  スキーマは namespaced :graphql/* キーで構成されたマップ。型定義は名前キーの
  マップ(O(1)参照)で保持し、順序には依存しない:

    {:graphql/types {\"Query\" {:graphql/name \"Query\" :graphql/kind :object
                                :graphql/fields [{:graphql/name \"user\"
                                                  :graphql/type \"User\"
                                                  :graphql/list? false
                                                  :graphql/non-null? false
                                                  :graphql/args [{:graphql/name \"id\"
                                                                  :graphql/type \"ID\"
                                                                  :graphql/non-null? true}]}]}
                     \"User\" {:graphql/name \"User\" :graphql/kind :object
                               :graphql/fields [{:graphql/name \"name\"
                                                 :graphql/type \"String\"
                                                 :graphql/list? false
                                                 :graphql/non-null? false}]}}
     :graphql/query-root \"Query\"}")

;; --- GraphQL 型種別 ---

(def builtin-scalars #{"String" "Int" "Float" "Boolean" "ID"})

(def type-kinds #{:object :input :enum :interface :union :scalar})

;; --- builder (threadable) ---

(defn schema
  "空のスキーマを返す。"
  []
  {:graphql/types {} :graphql/query-root nil})

(defn add-type
  "型定義をスキーマに追加する。:graphql/name がキーになる。"
  [schema type-def]
  (assoc-in schema [:graphql/types (:graphql/name type-def)] type-def))

(defn set-query-root
  "クエリルート型名をスキーマに設定する。"
  [schema name]
  (assoc schema :graphql/query-root name))

(defn type-def
  "型定義マップを構築する。kind は type-kinds の要素。"
  ([name kind] (type-def name kind []))
  ([name kind fields]
   {:graphql/name name :graphql/kind kind :graphql/fields fields}))

(defn field-def
  "フィールド定義マップを構築する。opts: {:list? :non-null? :args}。"
  ([name type-name] (field-def name type-name {}))
  ([name type-name opts]
   (cond-> {:graphql/name name
            :graphql/type type-name
            :graphql/list? (boolean (:list? opts))
            :graphql/non-null? (boolean (:non-null? opts))}
     (:args opts) (assoc :graphql/args (:args opts)))))

(defn arg-def
  "引数定義マップを構築する。opts: {:list? :non-null?}。"
  ([name type-name] (arg-def name type-name {}))
  ([name type-name opts]
   (cond-> {:graphql/name name
            :graphql/type type-name
            :graphql/non-null? (boolean (:non-null? opts))}
     (:list? opts) (assoc :graphql/list? true))))

;; --- queries ---

(defn get-type      [schema name] (get-in schema [:graphql/types name]))
(defn all-types     [schema]      (vals (:graphql/types schema)))
(defn query-root    [schema]      (:graphql/query-root schema))
(defn fields        [type-def]   (:graphql/fields type-def))

(defn field-by-name
  "型定義からフィールド名でフィールドを検索する。"
  [type-def fname]
  (first (filter #(= fname (:graphql/name %)) (:graphql/fields type-def))))
