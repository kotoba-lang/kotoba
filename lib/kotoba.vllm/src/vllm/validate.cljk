(ns vllm.validate
  "Structural validation of a vllm-clj request. Pure: returns a vector of problem
  maps `{:vllm/severity :error|:warn :vllm/code :vllm/field :vllm/msg}`.
  `valid?` is true iff there are no :error-level problems. Sampling range checks
  are delegated to `vllm.sampling/problems`."
  (:require [kotoba.lang.text :as str]
            [vllm.sampling :as sampling]))

(defn- problem [severity code field msg]
  {:vllm/severity severity :vllm/code code :vllm/field field :vllm/msg msg})

(def ^:private roles #{:system :user :assistant :tool})

(defn- check-messages [messages]
  (cond
    (empty? messages)
    [(problem :error :messages/empty :vllm/messages "chat request has no messages")]
    :else
    (vec
     (mapcat
      (fn [i {:vllm/keys [role content]}]
        (cond-> []
          (not (contains? roles role))
          (conj (problem :error :message/role (keyword (str "messages/" i))
                         (str "invalid role: " (pr-str role))))
          (not (string? content))
          (conj (problem :error :message/content (keyword (str "messages/" i))
                         "message :vllm/content must be a string"))))
      (range) messages))))

(defn problems
  "All structural + sampling problems in `req`, as a vector of problem maps."
  [req]
  (vec
   (concat
    (when (str/blank? (str (:vllm/model req)))
      [(problem :error :request/model :vllm/model "missing :vllm/model")])
    (case (:vllm/endpoint req)
      :chat       (check-messages (:vllm/messages req))
      :completion (when-not (string? (:vllm/prompt req))
                    [(problem :error :request/prompt :vllm/prompt
                              ":completion request needs a string :vllm/prompt")])
      [(problem :error :request/endpoint :vllm/endpoint
                (str "unknown endpoint: " (pr-str (:vllm/endpoint req))))])
    (sampling/problems (:vllm/sampling req)))))

(defn valid?
  "True iff `req` has no :error-level problems."
  [req]
  (empty? (filterv #(= :error (:vllm/severity %)) (problems req))))
