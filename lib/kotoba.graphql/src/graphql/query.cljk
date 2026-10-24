(ns graphql.query
  "GraphQL クエリ/ミューテーション文字列 → セレクション AST。third-party 依存なし、portable .cljc。

  手書きのトークナイザ + 再帰降下パーサで GraphQL クエリ操作の実行可能サブセットを処理する:

    { ... }                        — 匿名クエリ(ショートハンド)
    query Name? VariablesDef? { }  — 名前付きクエリ
    mutation Name? { }             — ミューテーション
    field(arg: value) { ... }      — フィールド選択(ネスト・引数付き)
    alias: field { }               — エイリアス(field-name として実名を使用)
    引数リテラル: 文字列・整数・浮動小数点・真偽値・enum 値

  対応していないもの: 変数($var)の型付け・フラグメント展開(スキップ)・
  ディレクティブ引数・入力オブジェクトリテラル。

  セレクションの形式:
    {:graphql/field \"user\" :graphql/args {\"id\" \"1\"} :graphql/selections [...]}"
  (:require [kotoba.lang.text :as str]))

;; --- tokenizer ---

(def ^:private tok-re
  "文字列リテラル・数値・識別子・クエリ区切り記号にマッチするトークン正規表現。"
  #"\"(?:[^\"\\]|\\.)*\"|[A-Za-z_][A-Za-z0-9_]*|-?[0-9]+(?:\.[0-9]+)?|[:{}\[\]()|!$@=]")

(defn- tokenize
  "# コメントを除去してトークン列(文字列 vector)を返す。"
  [s]
  (let [no-comments (str/replace s #"#[^\n]*" "")]
    (vec (re-seq tok-re no-comments))))

(defn- at [tokens i] (nth tokens i nil))

;; --- 値パーサ ---

(defn- parse-value
  "引数値リテラルをパースし [value next-i] を返す。
  対応: 文字列(クォート除去)・整数・浮動小数点・真偽値・列挙値(文字列として返す)。"
  [tokens i]
  (let [tok (at tokens i)]
    (cond
      (nil? tok) [nil i]
      (str/starts-with? tok "\"")
      [(subs tok 1 (dec (count tok))) (inc i)]
      (= "true" tok)  [true  (inc i)]
      (= "false" tok) [false (inc i)]
      (= "null" tok)  [nil   (inc i)]
      (re-matches #"-?[0-9]+\.[0-9]+" tok)
      [#?(:clj (Double/parseDouble tok) :cljs (js/parseFloat tok)) (inc i)]
      (re-matches #"-?[0-9]+" tok)
      [#?(:clj (Long/parseLong tok) :cljs (js/parseInt tok 10)) (inc i)]
      :else [tok (inc i)])))   ; enum value — returned as string

;; --- 引数リストパーサ '(' (name ':' value)* ')' ---

(defn- parse-args
  "引数リスト '(' (name ':' value)* ')' をパースし [args-map next-i] を返す。
  i は '(' の位置。"
  [tokens i]
  (loop [i (inc i) args {}]
    (let [tok (at tokens i)]
      (cond
        (or (= ")" tok) (nil? tok)) [args (if (= ")" tok) (inc i) i)]
        (= "@" tok) (recur (+ i 2) args)
        :else
        (let [name tok
              i2   (inc i)
              i3   (if (= ":" (at tokens i2)) (inc i2) i2)
              [value i4] (parse-value tokens i3)]
          (recur i4 (assoc args name value)))))))

;; --- セレクションセット '{' selection* '}' ---

(declare parse-selection-set)

(defn- parse-field
  "フィールドセレクションをパースし [selection-map next-i] を返す。"
  [tokens i]
  (let [first-name (at tokens i)
        i2         (inc i)
        ;; alias: もし次が ":" ならエイリアス→実フィールド名
        [field-name i3] (if (= ":" (at tokens i2))
                          [(at tokens (inc i2)) (+ i2 2)]
                          [first-name i2])
        ;; 引数リスト(省略可)
        [args i4] (if (= "(" (at tokens i3))
                    (parse-args tokens i3)
                    [{} i3])
        ;; ネストセレクションセット(省略可)
        [sels i5] (if (= "{" (at tokens i4))
                    (parse-selection-set tokens i4)
                    [[] i4])]
    [{:graphql/field field-name :graphql/args args :graphql/selections sels} i5]))

(defn- parse-selection-set
  "セレクションセット '{' selection* '}' をパースし [selections next-i] を返す。
  i は '{' の位置。"
  [tokens i]
  (loop [i (inc i) sels []]
    (let [tok (at tokens i)]
      (cond
        (or (= "}" tok) (nil? tok)) [sels (if (= "}" tok) (inc i) i)]
        ;; フラグメントスプレッド/インラインフラグメントをスキップ
        (= "..." tok)
        (let [i2 (inc i)]
          (if (= "on" (at tokens i2))
            ;; inline fragment: ... on TypeName { ... }
            (let [i3 (+ i2 2)
                  [_ i4] (parse-selection-set tokens i3)]
              (recur i4 sels))
            ;; fragment spread: ...FragmentName
            (recur (inc i2) sels)))
        :else
        (let [[field i2] (parse-field tokens i)]
          (recur i2 (conj sels field)))))))

(defn parse-query
  "GraphQL クエリ/ミューテーション文字列をセレクション AST(マップの vector)にパースする。

  ショートハンド形式 '{ ... }' と名前付き操作 'query Name? { ... }' の両方を処理する。"
  [query-str]
  (let [tokens (tokenize query-str)
        tok0   (at tokens 0)]
    (cond
      ;; shorthand: { ... }
      (= "{" tok0)
      (first (parse-selection-set tokens 0))

      ;; named operation: query/mutation/subscription Name? Variables? { ... }
      (contains? #{"query" "mutation" "subscription"} tok0)
      (let [i1  1
            ;; optional operation name
            i2  (if (and (at tokens i1) (not= "{" (at tokens i1))
                         (not= "(" (at tokens i1)))
                  (inc i1) i1)
            ;; optional variable definitions
            i3  (if (= "(" (at tokens i2))
                  (second (parse-args tokens i2))
                  i2)]
        (first (parse-selection-set tokens i3)))

      :else [])))
