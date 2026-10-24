(ns daichou.canonical
  "受領証に入れる値の**正規形**。

   同じ意味の値が二通りに書けると、ハッシュが二通りになり、連鎖が壊れていないのに
   壊れて見える。逆に、違う意味の値が同じ形に潰れると、改ざんが検出できない。
   だから正規化は「見た目を揃える」ためではなく、**ハッシュを意味に対して一意に
   するため**にある。

   規則(RFC 8785 / JCS の考え方を EDN に合わせたもの):
   - map のキーは文字列化して昇順。キー衝突は例外(潰さない)。
   - keyword / symbol は名前空間つきの完全名で書く。
   - **浮動小数は受け付けない。**ClojureScript では 1 と 1.0 が同じ値なので、
     「整数と小数を区別する」規則は JVM でしか成り立たない。両 runtime で同じ
     連鎖にならない正規化は、台帳としては無いのと同じ(nbb で作った受領証が
     JVM で検証できないなら、検証器は信用できない)。金額や計測値は文字列か
     整数(最小単位)で入れる。これは JSON Canonicalization が同じ理由で数値の
     表現に苦しんでいる問題を、受け付けないことで避ける判断である。
   - nil は `null`、真偽値はそのまま。
   - 文字列は JSON と同じ最小エスケープ。"
  (:require [kotoba.lang.text :as str]))

(defn- esc [s]
  (str "\"" (-> (str s)
                (str/replace "\\" "\\\\")
                (str/replace "\"" "\\\"")
                (str/replace "\n" "\\n")
                (str/replace "\r" "\\r")
                (str/replace "\t" "\\t"))
       "\""))

(defn- key->str [k]
  (cond
    (keyword? k) (subs (str k) 1)
    (symbol? k)  (str k)
    (string? k)  k
    :else (throw (ex-info "受領証のキーは keyword / symbol / string のいずれかであること"
                          {:key k :type (type k)}))))

(declare write)

(defn- write-map [m]
  (let [pairs (map (fn [[k v]] [(key->str k) v]) m)
        ks    (map first pairs)]
    (when (not= (count ks) (count (distinct ks)))
      (throw (ex-info "正規化でキーが衝突した。潰すと改ざんが隠れるので拒否する"
                      {:keys (vec ks)})))
    (str "{" (str/join "," (map (fn [[k v]] (str (esc k) ":" (write v)))
                                (sort-by first pairs))) "}")))

(defn write
  "値を正規形の文字列にする。"
  [v]
  (cond
    (nil? v) "null"
    (boolean? v) (str v)
    (string? v) (esc v)
    (keyword? v) (esc (subs (str v) 1))
    (symbol? v) (esc (str v))
    (map? v) (write-map v)
    (or (vector? v) (seq? v) (list? v)) (str "[" (str/join "," (map write v)) "]")
    (set? v) (str "[" (str/join "," (map write (sort-by write v))) "]")
    (integer? v) (str v)
    (number? v)
    (throw (ex-info (str "浮動小数は受領証に入れない。ClojureScript では 1 と 1.0 が "
                         "同じ値なので、両 runtime で同じハッシュにならない。"
                         "金額や計測値は文字列か整数(最小単位)で入れること")
                    {:value v}))
    :else (throw (ex-info "正規形を持たない値は受領証に入れない"
                          {:value v :type (type v)}))))
