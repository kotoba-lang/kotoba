(ns murakumo.host
  "babashka ホスト能力 — langchain-clj/murakumo の注入ポイントを満たす。

  bb 組み込みの babashka.http-client + cheshire を使う (追加依存ゼロ)。
  JVM Clojure で使う場合はこの ns を別実装に差し替える。"
  (:require [babashka.http-client :as http]
            [cheshire.core :as json]
            [murakumo.fleet :as fleet]
            [murakumo.model :as mm]))

(defn http-fn [{:keys [url method headers body]}]
  (let [resp (http/request {:uri url
                            :method (or method :post)
                            :headers headers
                            :body body
                            :throw false
                            :timeout 600000})]
    {:status (:status resp) :body (:body resp)}))

(def json-write json/generate-string)

(defn json-read [s] (json/parse-string s true))

(def host-caps
  {:http-fn http-fn :json-write json-write :json-read json-read})

(defn gemma
  "fleet 全体のラウンドロビン gemma4 ChatModel (ホスト能力注入済)。

    (gemma)                              ; e4b-it-qat
    (gemma {:model \"gemma4:12b-it-qat\"})"
  ([] (gemma {}))
  ([opts] (fleet/fleet-model (merge host-caps opts))))

(defn gemma-node
  "単一ノードの gemma4 ChatModel (ホスト能力注入済)。

    (gemma-node \"http://100.101.27.85:11434\")"
  ([url] (gemma-node url {}))
  ([url opts] (mm/ollama-model (merge host-caps {:url url} opts))))
