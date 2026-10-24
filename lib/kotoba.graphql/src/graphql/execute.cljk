(ns graphql.execute
  "GraphQL クエリの純粋エグゼキュータ。スキーマ EDN + クエリ AST + IResolver ポートを受け取り、
  フィールドを再帰的に解決して結果マップを返す。I/O なし、third-party 依存なし — portable .cljc。

  実行モデル:
    - ルートセレクションは query-root 型のフィールドとして解決する
    - サブセレクションがあるフィールドは、解決値の型に対して再帰する
    - 解決値が sequence の場合、各要素にサブセレクションをマップして vector を返す
    - スカラー(サブセレクションなし)は解決値をそのまま返す
    - IResolver/resolve はフィールドごとに一度だけ呼ばれる(純粋関数前提)"
  (:refer-clojure :exclude [resolve])
  (:require [graphql.model :as m]
            [graphql.ports :as p]))

(declare execute-selections)

(defn- execute-field
  "一つのフィールドセレクションを `parent`(type-name 型)に対して解決する。"
  [ports schema type-name parent selection ctx]
  (let [field-name (:graphql/field selection)
        args       (:graphql/args selection)
        sels       (:graphql/selections selection)
        value      (p/resolve (:resolver ports) type-name field-name parent args ctx)]
    (if (seq sels)
      ;; サブセレクションあり: フィールドの戻り値型を参照して再帰
      (let [type-def   (m/get-type schema type-name)
            field-meta (m/field-by-name type-def field-name)
            ret-type   (:graphql/type field-meta)]
        (cond
          (sequential? value)
          (mapv #(execute-selections ports schema ret-type % sels ctx) value)
          (nil? value) nil
          :else (execute-selections ports schema ret-type value sels ctx)))
      ;; スカラー: 解決値をそのまま返す
      value)))

(defn execute-selections
  "セレクションリストを `parent`(type-name 型)に対して解決し、
  フィールド名 → 値 のマップを返す。"
  [ports schema type-name parent selections ctx]
  (reduce (fn [acc sel]
            (assoc acc (:graphql/field sel)
                   (execute-field ports schema type-name parent sel ctx)))
          {} selections))

(defn execute-query
  "パース済みクエリ AST をスキーマとポートに対して実行し、結果マップを返す。

  - ports:       {:resolver IResolver} を含むマップ
  - schema:      graphql.model スキーマ
  - query-ast:   graphql.query/parse-query が返すセレクション vector
  - root-value:  ルートフィールド解決時に parent として渡される値
  - ctx:         全リゾルバに透過的に渡されるコンテキスト値

  戻り値: {field-name → resolved-value} のマップ"
  [ports schema query-ast root-value ctx]
  (let [query-root-name (m/query-root schema)]
    (execute-selections ports schema query-root-name root-value query-ast ctx)))

;; --- host 不要のデフォルトポート ---

(defn default-ports
  "デフォルトリゾルバ: (get parent (keyword field-name)) で解決し、
  見つからない場合は文字列キー (get parent field-name) にフォールバックする。
  plain map のフィールドアクセスで任意のモデルをホスト実装なしで実行できる。"
  []
  {:resolver
   (reify p/IResolver
     (resolve [_ _type-name field-name parent _args _ctx]
       (or (get parent (keyword field-name))
           (get parent field-name))))})
