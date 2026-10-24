(ns graphql.sdl
  "GraphQL SDL 文字列 → EDN スキーマ (graphql.model)。third-party 依存なし、portable .cljc。

  手書きのトークナイザ + 再帰降下パーサで SDL の実行可能サブセットを処理する:

    type / input / interface  — フィールド定義(引数・! 修飾・[] リスト修飾)
    enum                      — 値リスト
    union                     — メンバー型リスト
    scalar                    — スカラー宣言
    schema                    — query/mutation/subscription ルート型の指定
    #                         — 行コメント(除去)
    @directive                — 無視(スキップ)
    「implements」            — スキップ

  対応していないもの: 入れ子リスト型(実態は最外殻のみ保持)、デフォルト値の型検査、
  引数デフォルト値(スキップ)、フラグメント、型拡張 (extend type)。"
  (:require [kotoba.lang.text :as str]
            [graphql.model :as m]))

;; --- tokenizer ---

(def ^:private tok-re
  "文字列リテラル・識別子・SDL 区切り記号にマッチするトークン正規表現。"
  #"\"(?:[^\"\\]|\\.)*\"|[A-Za-z_][A-Za-z0-9_]*|[!:{}\[\]()|=@]")

(defn- tokenize
  "# コメントを除去してトークン列(文字列 vector)を返す。"
  [s]
  (let [no-comments (str/replace s #"#[^\n]*" "")]
    (vec (re-seq tok-re no-comments))))

(defn- at [tokens i] (nth tokens i nil))

(defn- expect
  "tokens[i] が expected であることを検証し i+1 を返す。"
  [tokens i expected]
  (if (= expected (at tokens i))
    (inc i)
    (throw (ex-info (str "SDL parse error: expected '" expected
                         "' but got '" (at tokens i)
                         "' at position " i)
                    {:pos i :got (at tokens i) :expected expected}))))

;; --- 型参照パーサ ---

(defn- parse-type-ref
  "型参照をパースし [{:graphql/type T :graphql/list? B :graphql/non-null? B} next-i] を返す。
  List 型は最外殻の nullability と要素型のみ保持する(ネスト list 非対応)。"
  [tokens i]
  (let [tok (at tokens i)]
    (cond
      (= "[" tok)
      (let [[inner i2] (parse-type-ref tokens (inc i))
            i3 (expect tokens i2 "]")
            non-null? (= "!" (at tokens i3))
            i4 (if non-null? (inc i3) i3)]
        [(assoc inner :graphql/list? true :graphql/non-null? non-null?) i4])

      (and tok (re-matches #"[A-Za-z_][A-Za-z0-9_]*" tok))
      (let [i2 (inc i)
            non-null? (= "!" (at tokens i2))
            i3 (if non-null? (inc i2) i2)]
        [{:graphql/type tok :graphql/list? false :graphql/non-null? non-null?} i3])

      :else
      (throw (ex-info (str "SDL parse error: expected type name or '[' at position " i)
                      {:pos i :tok tok})))))

;; --- 引数定義パーサ ---

(defn- parse-arg-def
  "引数定義 name: TypeRef (= default)? をパースし [arg-map next-i] を返す。"
  [tokens i]
  (let [name (at tokens i)
        i2   (expect tokens (inc i) ":")
        [type-info i3] (parse-type-ref tokens i2)
        ;; skip default value "= <value-token>" if present
        i4   (if (= "=" (at tokens i3)) (+ i3 2) i3)]
    [(merge {:graphql/name name} type-info) i4]))

(defn- parse-arg-defs
  "引数リスト '(' arg-def* ')' をパースし [args next-i] を返す。i は '(' の位置。"
  [tokens i]
  (loop [i (inc i) args []]
    (let [tok (at tokens i)]
      (cond
        (or (= ")" tok) (nil? tok)) [args (if (= ")" tok) (inc i) i)]
        (= "@" tok) (recur (+ i 2) args)   ; skip @directive on arg
        :else
        (let [[arg i2] (parse-arg-def tokens i)]
          (recur i2 (conj args arg)))))))

;; --- フィールド定義パーサ ---

(defn- parse-field-def
  "フィールド定義 name args? ':' TypeRef をパースし [field-map next-i] を返す。"
  [tokens i]
  (let [name (at tokens i)
        i2   (inc i)
        [args i3] (if (= "(" (at tokens i2))
                    (parse-arg-defs tokens i2)
                    [[] i2])
        i4   (expect tokens i3 ":")
        [type-info i5] (parse-type-ref tokens i4)]
    [(cond-> (merge {:graphql/name name} type-info)
       (seq args) (assoc :graphql/args args)) i5]))

;; --- フィールドブロック '{' field-def* '}' ---

(defn- parse-fields
  "型本体 '{' field-def* '}' をパースし [fields next-i] を返す。i は '{' の位置。"
  [tokens i]
  (let [i (expect tokens i "{")]
    (loop [i i fields []]
      (let [tok (at tokens i)]
        (cond
          (or (= "}" tok) (nil? tok)) [fields (if (= "}" tok) (inc i) i)]
          (= "@" tok) (recur (+ i 2) fields)   ; skip @directive_name
          :else
          (let [[field i2] (parse-field-def tokens i)]
            (recur i2 (conj fields field))))))))

;; --- enum 値ブロック '{' NAME* '}' ---

(defn- parse-enum-values
  "enum 本体 '{' NAME* '}' をパースし [values next-i] を返す。i は '{' の位置。"
  [tokens i]
  (let [i (expect tokens i "{")]
    (loop [i i vals []]
      (let [tok (at tokens i)]
        (cond
          (or (= "}" tok) (nil? tok)) [vals (if (= "}" tok) (inc i) i)]
          (= "@" tok) (recur (+ i 2) vals)
          :else (recur (inc i) (conj vals tok)))))))

;; --- union メンバー '=' NAME ('|' NAME)* ---

(defn- parse-union-members
  "union メンバー '=' Name ('|' Name)* をパースし [members next-i] を返す。i は '=' の位置。"
  [tokens i]
  (let [i  (expect tokens i "=")
        n0 (at tokens i)]
    (loop [i (inc i) members [n0]]
      (if (= "|" (at tokens i))
        (let [n (at tokens (inc i))]
          (recur (+ i 2) (conj members n)))
        [members i]))))

;; --- schema ブロック '{' (role ':' TypeName)* '}' ---

(defn- parse-schema-block
  "schema ブロック '{' ... '}' をパースし [roots-map next-i] を返す。i は '{' の位置。"
  [tokens i]
  (let [i (expect tokens i "{")]
    (loop [i i roots {}]
      (let [tok (at tokens i)]
        (cond
          (or (= "}" tok) (nil? tok)) [roots (if (= "}" tok) (inc i) i)]
          :else
          (let [role tok
                i2   (expect tokens (inc i) ":")
                tname (at tokens i2)]
            (recur (inc i2) (assoc roots role tname))))))))

;; --- トップレベル定義パーサ ---

(defn- skip-implements
  "implements キーワードに続くインタフェース名列を '{' まで読み飛ばす。"
  [tokens i]
  ;; i points at token after type name: either "{" or "implements"
  (if (= "implements" (at tokens i))
    (loop [j (inc i)]
      (let [t (at tokens j)]
        (if (or (= "{" t) (nil? t)) j (recur (inc j)))))
    i))

(defn- parse-definition
  "一つのトップレベル定義をパースし [next-i updated-schema] を返す。"
  [tokens i schema]
  (let [kw (at tokens i)]
    (cond
      (= "type" kw)
      (let [name (at tokens (inc i))
            i2   (skip-implements tokens (+ i 2))
            [fields i3] (parse-fields tokens i2)]
        [i3 (m/add-type schema (m/type-def name :object fields))])

      (= "input" kw)
      (let [name (at tokens (inc i))
            [fields i2] (parse-fields tokens (+ i 2))]
        [i2 (m/add-type schema (m/type-def name :input fields))])

      (= "interface" kw)
      (let [name (at tokens (inc i))
            i2   (skip-implements tokens (+ i 2))
            [fields i3] (parse-fields tokens i2)]
        [i3 (m/add-type schema (m/type-def name :interface fields))])

      (= "enum" kw)
      (let [name (at tokens (inc i))
            [vals i2] (parse-enum-values tokens (+ i 2))]
        [i2 (m/add-type schema {:graphql/name name :graphql/kind :enum
                                :graphql/values vals :graphql/fields []})])

      (= "union" kw)
      (let [name (at tokens (inc i))
            [members i2] (parse-union-members tokens (+ i 2))]
        [i2 (m/add-type schema {:graphql/name name :graphql/kind :union
                                :graphql/members members :graphql/fields []})])

      (= "scalar" kw)
      (let [name (at tokens (inc i))]
        [(+ i 2) (m/add-type schema {:graphql/name name :graphql/kind :scalar
                                     :graphql/fields []})])

      (= "schema" kw)
      (let [[roots i2] (parse-schema-block tokens (inc i))]
        [i2 (cond-> schema
              (get roots "query") (m/set-query-root (get roots "query")))])

      :else [(inc i) schema])))   ; skip unknown token

(defn parse-schema
  "GraphQL SDL 文字列を graphql.model スキーママップにパースする。

  schema ブロックが存在しない場合、GraphQL 仕様のデフォルトとして
  'Query' 型が存在すればそれをクエリルートに設定する。"
  [sdl]
  (let [tokens (tokenize sdl)]
    (loop [i 0 schema (m/schema)]
      (if (>= i (count tokens))
        ;; GraphQL default: root type named "Query" when no schema block
        (if (and (nil? (:graphql/query-root schema))
                 (contains? (:graphql/types schema) "Query"))
          (assoc schema :graphql/query-root "Query")
          schema)
        (let [[i2 schema2] (parse-definition tokens i schema)]
          (recur i2 schema2))))))
