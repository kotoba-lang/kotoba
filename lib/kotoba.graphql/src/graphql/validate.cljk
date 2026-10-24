(ns graphql.validate
  "GraphQL スキーマ EDN モデルの構造検証。純粋関数: problem マップの vector を返す。
  {:graphql/severity :error|:warn :graphql/code ... :graphql/id ... :graphql/msg ...}

  `valid?` は :error-level の問題がない場合に真(warning は advisory)。"
  (:require [graphql.model :as m]))

(defn- problem [severity code id msg]
  {:graphql/severity severity :graphql/code code :graphql/id id :graphql/msg msg})

(defn problems
  "スキーマの構造的な問題を problem マップの vector として返す。

  Errors:
    :schema/missing-query-root  — query-root 型が定義されていない
    :field/unknown-type         — フィールドの型が未定義
    :field/duplicate-name       — 同一型内にフィールド名の重複
    :arg/unknown-type           — 引数の型が未定義

  Warnings: (現在なし、将来拡張のためプレースホルダ)"
  [schema]
  (let [ps            (transient [])
        defined-types (set (keys (:graphql/types schema)))
        all-types     (into defined-types m/builtin-scalars)]

    ;; クエリルート型の存在チェック
    (let [qr (:graphql/query-root schema)]
      (when (or (nil? qr) (not (contains? defined-types qr)))
        (conj! ps (problem :error :schema/missing-query-root nil
                           (str "query root type '" qr "' is not defined in the schema")))))

    ;; 各型の検証
    (doseq [t (m/all-types schema)]
      (let [type-name (:graphql/name t)
            fields    (:graphql/fields t)]

        ;; フィールド名の重複
        (let [names (map :graphql/name fields)
              dupes (for [[n cnt] (frequencies names) :when (> cnt 1)] n)]
          (doseq [dup dupes]
            (conj! ps (problem :error :field/duplicate-name type-name
                               (str "duplicate field name '" dup
                                    "' in type " type-name)))))

        ;; フィールド型の存在チェック
        (doseq [f fields]
          (when-not (contains? all-types (:graphql/type f))
            (conj! ps (problem :error :field/unknown-type type-name
                               (str "field '" (:graphql/name f) "' in " type-name
                                    " references unknown type '" (:graphql/type f) "'"))))
          ;; 引数の型チェック
          (doseq [a (:graphql/args f)]
            (when-not (contains? all-types (:graphql/type a))
              (conj! ps (problem :error :arg/unknown-type type-name
                                 (str "arg '" (:graphql/name a)
                                      "' in " type-name "." (:graphql/name f)
                                      " references unknown type '" (:graphql/type a) "'"))))))))

    (persistent! ps)))

(defn errors
  "スキーマの :error-level 問題のみを返す。"
  [schema]
  (filterv #(= :error (:graphql/severity %)) (problems schema)))

(defn valid?
  "スキーマに :error-level の構造的問題がない場合に真を返す。"
  [schema]
  (empty? (errors schema)))
