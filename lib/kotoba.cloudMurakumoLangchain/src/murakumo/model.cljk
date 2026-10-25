(ns murakumo.model
  "Ollama (Murakumo fleet) ChatModel adapter for langchain-clj.

  langchain-clj と同じ WASM premise — このライブラリ自体は I/O をしない。
  ホスト能力は注入する:

    :http-fn    (fn [{:keys [url method headers body]}]
                  → {:status int :body string})
    :json-write (fn [clj-map] → json string)
    :json-read  (fn [json-string] → clj map, keyword keys)

  Ollama ネイティブ /api/chat を使う (OpenAI 互換側は options/num_ctx を
  黙って無視するため使わない)。gemma4 *-qat は reasoning モデルなので
  :think false が既定 — 思考トレースの ctx 浪費を止める。

  ADR-2605215000 (Murakumo-only inference): fleet Ollama 直叩きは認可経路。"
  (:require [langchain.model :as model]))

(def default-model "gemma4:e4b-it-qat")
(def default-options {:temperature 0.1 :num_ctx 16384})

;; ───────────────────────── wire format ─────────────────────────

(defn- msg->ollama [{:keys [role content tool-calls tool-call-id]}]
  (case role
    :system {:role "system" :content content}
    :user {:role "user" :content content}
    :tool (cond-> {:role "tool" :content (str content)}
            tool-call-id (assoc :tool_call_id tool-call-id))
    :assistant (cond-> {:role "assistant" :content (or content "")}
                 (seq tool-calls)
                 (assoc :tool_calls
                        (mapv (fn [{:keys [id name input]}]
                                (cond-> {:function {:name name :arguments input}}
                                  id (assoc :id id)))
                              tool-calls)))
    ;; 未知 role はクラッシュさせず素通し (string role / 想定外 keyword)
    {:role (if (keyword? role) (clojure.core/name role) (str role))
     :content (str content)}))

(defn tool->ollama
  "langchain tool map → Ollama native (OpenAI-shaped) tool wire format."
  [{:keys [name description schema]}]
  {:type "function"
   :function {:name name
              :description (or description "")
              :parameters (or schema {:type "object" :properties {}})}})

(defn request-body
  "langchain messages + opts → Ollama /api/chat request body. Exposed for testing."
  [messages {:keys [model think options tools] :as _opts}]
  (cond-> {:model (or model default-model)
           :messages (mapv msg->ollama messages)
           :stream false
           :think (boolean think)
           :options (merge default-options options)}
    (seq tools) (assoc :tools (mapv tool->ollama tools))))

(defn parse-response
  "Ollama /api/chat response map → assistant message. Exposed for testing."
  [{:keys [message done_reason eval_count prompt_eval_count] :as resp}]
  (when-let [err (:error resp)]
    (throw (ex-info "Ollama error" {:error err :response resp})))
  (let [calls (vec (map-indexed
                    (fn [i {:keys [id function]}]
                      ;; id 欠落時は内容由来 (name+input+i) のハッシュ — 異ターンの同 index で
                      ;; 衝突しない (WASM premise: 時計/乱数なし)。
                      {:id (or id (str "call-" (hash [(:name function) (:arguments function) i])))
                       :name (:name function)
                       :input (:arguments function)})
                    (:tool_calls message)))]
    (cond-> {:role :assistant
             :content (or (:content message) "")
             :stop-reason done_reason}
      (seq calls) (assoc :tool-calls calls)
      eval_count (assoc :usage {:output_tokens eval_count
                                :input_tokens prompt_eval_count}))))

;; ───────────────────────── ChatModel ─────────────────────────

(defn ollama-model
  "Single-node Ollama chat model.

    (ollama-model {:url \"http://100.101.27.85:11434\"
                   :model \"gemma4:e4b-it-qat\"
                   :http-fn host-fetch
                   :json-write … :json-read …})"
  [{:keys [url model think options http-fn json-write json-read]
    :or {model default-model think false}}]
  (when-not url
    (throw (ex-info ":url required (e.g. http://node:11434)" {})))
  (when-not http-fn
    (throw (ex-info ":http-fn must be injected (host capability)" {})))
  (when-not (and json-write json-read)
    (throw (ex-info ":json-write/:json-read must be injected on this host" {})))
  (reify model/ChatModel
    (-generate [_ messages opts]
      (let [body (request-body messages (merge {:model model :think think
                                                :options options}
                                               opts))
            {:keys [status] resp-body :body}
            (http-fn {:url (str url "/api/chat")
                      :method :post
                      :headers {"content-type" "application/json"}
                      :body (json-write body)})]
        (when-not (and status (<= 200 status 299))
          (throw (ex-info "Ollama API error" {:status status :body resp-body :url url})))
        (parse-response (json-read resp-body))))))
