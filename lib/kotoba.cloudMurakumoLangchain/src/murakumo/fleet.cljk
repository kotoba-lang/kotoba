(ns murakumo.fleet
  "Murakumo Mac mini fleet roster + round-robin ChatModel.

  10 ノード (tailscale IP, 2026-06-11 全ノード gemma4 e4b/12b QAT 配布済,
  Ollama 0.30.7)。jacob は control plane なので含めない。
  SSoT: 50-infra/murakumo/fleet.edn"
  (:require [langchain.model :as model]
            [murakumo.model :as mm]))

(def nodes
  [{:name "naphtali" :url "http://100.101.27.85:11434"}
   {:name "simeon"   :url "http://100.81.66.86:11434"}
   {:name "judah"    :url "http://100.113.200.45:11434"}
   {:name "zebulun"  :url "http://100.66.28.79:11434"}
   {:name "levi"     :url "http://100.102.78.81:11434"}
   {:name "joseph"   :url "http://100.82.123.35:11434"}
   {:name "issachar" :url "http://100.89.204.30:11434"}
   {:name "dan"      :url "http://100.98.142.59:11434"}
   {:name "benjamin" :url "http://100.75.169.8:11434"}
   {:name "asher"    :url "http://100.96.122.69:11434"}])

(defn fleet-model
  "Round-robin ChatModel over the fleet. 1 つの ChatModel として振る舞い、
  -generate ごとに次のノードへ回す (状態は atom — WASM ホストでも可)。

    (fleet-model {:model \"gemma4:12b-it-qat\"
                  :http-fn … :json-write … :json-read …})

  opts は murakumo.model/ollama-model と同じ (:url を除く)。
  :nodes で roster を差し替え可能。"
  [{:keys [nodes] :as opts}]
  (let [roster (vec (or nodes murakumo.fleet/nodes))
        i (atom -1)
        models (mapv #(mm/ollama-model (-> opts
                                           (dissoc :nodes)
                                           (assoc :url (:url %))))
                     roster)]
    (reify model/ChatModel
      (-generate [_ messages gen-opts]
        (let [n (mod (swap! i inc) (count models))]
          (model/-generate (nth models n) messages gen-opts))))))
