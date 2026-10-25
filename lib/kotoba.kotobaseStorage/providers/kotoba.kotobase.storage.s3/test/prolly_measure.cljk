(ns prolly-measure
  "**測るのは 1 つだけ: keyed read が何ブロック触るか。**

  現状（kotobase-peer engine + R2）は keyed な読みでもグラフ全体を hydrate する
  —— 1,626 datom の actor repo で 19.7 秒、`yoro-social-v2` では Worker の
  CPU 上限を超える。`describeRepo` は 1 回で 12 本前後の datoms を投げるので、
  この設計では読みが成立しない。

  prolly engine が prefix pruning で必要なブロックだけを触るなら、
  projection という別の store を持たずに keyed read が安くなる。

  **秒ではなくブロック GET の本数で測る。** 秒は miniflare の実装速度に依るが、
  本数は木の性質そのもので、R2 に載せても同じ比になる。"
  (:require ["miniflare" :refer [Miniflare]]
            [kotobase.engine.contract :as engine]
            [kotobase.engine.prolly.provider :as provider]
            [kotobase.storage.s3 :as s3]))

(def ^:private crypto
  {:blind-fn #(js/Promise.resolve (str "blind:" %))
   :encrypt-fn #(js/Promise.resolve %)
   :decrypt-fn #(js/Promise.resolve %)
   :digest-fn #(str "digest:" (hash %))})

;; 実データの形に寄せる: 1 actor repo ≒ 1,626 datom で、firehose の 1 件が
;; :atproto.firehose/{cid,seq,uri} の 3 属性を持つ。
(def ^:private entities 542)

(defn- seed-tx []
  {:database-id "m/db" :request-id "seed"
   :tx-data
   (vec (mapcat (fn [i]
                  (let [e (str "firehose/" (+ 1785735132335000 i))]
                    [[:db/add e :atproto.firehose/cid (str "bafy" i)]
                     [:db/add e :atproto.firehose/seq (str i)]
                     [:db/add e :atproto.firehose/uri (str "at://did:key:z" i "/c/r" i)]]))
                (range entities)))})

(defn- measure [r snap label pattern]
  (let [before (provider/request-count r)]
    (-> (engine/scan r snap pattern)
        (.then (fn [rows]
                 (println (str label "\trows " (count rows)
                               "\tblock GETs " (- (provider/request-count r) before)))
                 rows)))))

(defn- run [bucket]
  (let [storage (s3/open {:client (s3/r2-client bucket)
                          :prefix "measure"
                          :require-linearizable? true})
        w (provider/engine-from-backend storage crypto)]
    (-> (provider/transact-and-publish!
         w storage "main" (engine/empty-state w "m/db") (seed-tx))
        (.then (fn [_] (println (str "seeded datoms\t" (* 3 entities)))))
        ;; **冷えた reader で測る。** 書いた直後の温かい状態で測ると、
        ;; 木の性質ではなくキャッシュを測ることになる。
        (.then (fn [_]
                 (let [r (provider/engine-from-backend storage crypto)]
                   (-> (provider/restore-head r storage "main")
                       (.then (fn [restored]
                                [r (engine/open-snapshot r restored)]))))))
        (.then (fn [[r snap]]
                 (-> (measure r snap "KEYED-ENTITY"
                              [(str "firehose/" (+ 1785735132335000 271))
                               :atproto.firehose/cid nil])
                     (.then (fn [_] [r snap])))))
        (.then (fn [[r snap]]
                 (-> (measure r snap "FULL-SCAN  " [nil nil nil])
                     (.then (fn [_] [r snap])))))
        (.then (fn [_] nil)))))

(defn -main [& _]
  (let [mf (Miniflare. #js {:modules true
                            :script "export default {};"
                            :r2Buckets #js {:BUCKET "measure"}})]
    (-> (.getR2Bucket mf "BUCKET")
        (.then run)
        (.catch (fn [e] (js/console.error e)))
        (.then (fn [_] (.dispose mf))))))
