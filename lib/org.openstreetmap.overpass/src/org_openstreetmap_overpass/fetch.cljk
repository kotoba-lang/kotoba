(ns org-openstreetmap-overpass.fetch
  "Overpass API への I/O（nbb / Node）。純粋部分は `core` にある。

  Overpass は無償の共有インフラで、利用規約が節度ある利用を求めている。
  したがってこのアダプタは:
  - 識別可能な User-Agent を必ず送る（匿名の連打をしない）
  - 呼び出し間に最小間隔を空ける（既定 1200ms）
  - 429 / 502 / 503 / 504 を受けたら**待ってから**1度だけ retry し、それ以上は
    諦めて呼び出し側にエラーを返す（無限 retry でサーバを叩き続けない）

  **この節度は主張ではなく検査対象である。** 送信そのもの（`:fetch-fn`）と
  retry の待ち（`:retry-delay-ms`）を差し替えられるようにしてあるのは、
  『1 度しか retry しない』『間隔を空ける』『User-Agent を必ず送る』を
  ネットワーク無しで確かめるため —— 実際に叩いて確かめる形にすると、
  検査そのものが規約違反の連打になる。"
  (:require [org-openstreetmap-overpass.core :as core]))

(def default-user-agent
  "kotoba-lang/org-openstreetmap-overpass (utility-pole survey; contact: root@junkawasaki.com)")

(def retryable-statuses
  "1 度だけ retry する status。**429 は rate limit、5xx は過負荷**で、どちらも
  『待てば直るかもしれない』側。404 や 400 を retry しても同じ答えが返るだけで、
  共有インフラを 2 度叩くぶん無作法になる。"
  #{429 502 503 504})

(def ^:private last-call (atom 0))

(defn- now-ms [] (.getTime (js/Date.)))

(defn- sleep [ms]
  (js/Promise. (fn [resolve] (js/setTimeout resolve ms))))

(defn- throttle!
  [min-interval-ms]
  (let [wait (max 0 (- (+ @last-call min-interval-ms) (now-ms)))]
    (.then (if (pos? wait) (sleep wait) (js/Promise.resolve nil))
           (fn [_] (reset! last-call (now-ms)) nil))))

(defn post-ql
  "QL 文字列 → parse 済み応答の Promise。`{:endpoint :user-agent
  :min-interval-ms :retry? :retry-delay-ms :parse-opts :fetch-fn}`。

  `:fetch-fn` は `(fn [url init] -> Promise<Response>)`。既定は `js/fetch`。"
  ([ql-string] (post-ql ql-string {}))
  ([ql-string {:keys [endpoint user-agent min-interval-ms retry? retry-delay-ms
                      parse-opts fetch-fn]
               :or {endpoint core/default-endpoint
                    user-agent default-user-agent
                    min-interval-ms 1200
                    retry? true
                    retry-delay-ms 5000
                    parse-opts {}}
               :as opts}]
   (let [f (or fetch-fn js/fetch)]
     (-> (throttle! min-interval-ms)
         (.then (fn [_]
                  (f endpoint
                     #js {:method "POST"
                          :headers #js {"Content-Type" "text/plain; charset=utf-8"
                                        "User-Agent" user-agent}
                          :body ql-string})))
         (.then (fn [res]
                  (cond
                    (.-ok res)
                    (.then (.json res) (fn [j] (core/parse-response (js->clj j) parse-opts)))

                    (and retry? (retryable-statuses (.-status res)))
                    ;; **元の opts をそのまま持ち越して `:retry?` だけ倒す。**
                    ;; 手で列挙し直すと、新しい option を足した人が retry 経路への
                    ;; 追加を忘れ、**1 回目と 2 回目で挙動の違う呼び出し**になる
                    ;; （既定へ黙って落ちるので、成功したように見える）。
                    (.then (sleep retry-delay-ms)
                           (fn [_] (post-ql ql-string (assoc opts :retry? false))))

                    :else
                    (throw (ex-info "overpass request failed"
                                    {:status (.-status res) :endpoint endpoint})))))))))

(defn fetch-poles
  "bbox → 電柱の観測。`core/ql` を通すので選択子の正しさはテスト済みの経路を通る。

  **QL に渡すのは `:kinds` と `:timeout` だけ** —— この入口は電柱のための
  短縮形なので、`:selectors` / `:ways?` / `:nwr?` / `:meta?` は届かない。
  それらが要るなら `fetch-features` を使う。"
  ([bbox] (fetch-poles bbox {}))
  ([bbox opts]
   (post-ql (core/ql bbox (select-keys opts [:kinds :timeout])) opts)))

(defn fetch-features
  "bbox + 任意の選択子 → 観測。屋外広告物の媒体を引くときはこちら
  （`okugai.medium/osm-selectors` と `osm-tags->medium` を渡す）。

     (fetch-features bbox {:selectors (medium/osm-selectors ids)
                           :ways? true   ; :nwr? true なら relation まで
                           :parse-opts {:classify medium/osm-tags->medium
                                        :attr :obs/medium}})"
  ([bbox] (fetch-features bbox {}))
  ([bbox opts]
   (post-ql (core/ql bbox (select-keys opts [:selectors :kinds :timeout :ways? :nwr? :meta?])) opts)))
