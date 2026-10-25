(ns vllm.request
  "vllm-clj as EDN — a plain-data model of an LLM inference request against a
  vLLM (OpenAI-compatible) server. Portable .cljc (JVM, ClojureScript, SCI).

  A *request* IS data: a map keyed by namespaced `:vllm/*` keys. There are two
  endpoints — chat (`/v1/chat/completions`) and text completion
  (`/v1/completions`):

    {:vllm/endpoint :chat
     :vllm/model    \"meta-llama/Llama-3-8B-Instruct\"
     :vllm/messages [{:vllm/role :system :vllm/content \"You are concise.\"}
                     {:vllm/role :user   :vllm/content \"Hello.\"}]
     :vllm/sampling {:vllm/temperature 0.7 :vllm/max-tokens 512}
     :vllm/base-url \"http://localhost:8000\"}

  This namespace only builds the data. Sampling defaults live in
  `vllm.sampling`, wire rendering/parsing in `vllm.wire`, validation in
  `vllm.validate`, the host HTTP port in `vllm.ports`, and the top-level call in
  `vllm.core`. No network I/O happens here."
  (:require [vllm.sampling :as sampling]))

(def default-base-url "http://localhost:8000")

(defn message
  "A chat message `{:vllm/role … :vllm/content …}`. Extra keys (e.g.
  `:vllm/tool-call-id`, `:vllm/name`) are carried through to the wire."
  ([role content] (message role content {}))
  ([role content extra]
   (merge {:vllm/role role :vllm/content content} extra)))

(defn system    [content] (message :system content))
(defn user      [content] (message :user content))
(defn assistant [content] (message :assistant content))
(defn tool      [content tool-call-id]
  (message :tool content {:vllm/tool-call-id tool-call-id}))

(defn chat
  "A chat-completions request for `model` over `messages` (a seq of message
  maps). `opts` may carry `:vllm/base-url`, `:vllm/stream`, `:vllm/tools`,
  `:vllm/sampling`, etc."
  ([model messages] (chat model messages {}))
  ([model messages opts]
   (merge {:vllm/endpoint :chat
           :vllm/model    model
           :vllm/messages (vec messages)
           :vllm/base-url default-base-url
           :vllm/sampling sampling/defaults}
          opts)))

(defn completion
  "A text-completions request for `model` over a raw `prompt` string."
  ([model prompt] (completion model prompt {}))
  ([model prompt opts]
   (merge {:vllm/endpoint :completion
           :vllm/model    model
           :vllm/prompt   prompt
           :vllm/base-url default-base-url
           :vllm/sampling sampling/defaults}
          opts)))

;; ---------------------------------------------------------------------------
;; threadable modifiers
;; ---------------------------------------------------------------------------

(defn with-sampling
  "Merge sampling overrides (`{:vllm/temperature … :vllm/max-tokens …}`)."
  [req overrides]
  (update req :vllm/sampling merge overrides))

(defn with-base-url [req url]   (assoc req :vllm/base-url url))
(defn with-stream   [req on?]   (assoc req :vllm/stream (boolean on?)))
(defn with-tools    [req tools] (assoc req :vllm/tools (vec tools)))

(defn add-message
  "Append a message to a chat request."
  [req role content]
  (update req :vllm/messages (fnil conj []) (message role content)))

(defn endpoint-path
  "The OpenAI-compatible path for a request's endpoint."
  [req]
  (case (:vllm/endpoint req)
    :chat       "/v1/chat/completions"
    :completion "/v1/completions"
    (throw (ex-info (str "unknown endpoint: " (:vllm/endpoint req))
                    {:vllm/request req}))))

(defn target-url
  "Full POST URL for a request (`base-url` + endpoint path)."
  [req]
  (str (or (:vllm/base-url req) default-base-url) (endpoint-path req)))
