(ns vllm.wire
  "Translation between the `:vllm/*` EDN model and the OpenAI/vLLM JSON shape.
  Following the sibling-library rule (*don't build JSON text*), this namespace
  produces and consumes **string-keyed Clojure maps** — the host transport does
  the actual JSON (de)serialization. Pure, no I/O.

  - `render`        : request EDN        → string-keyed request body
  - `parse-response`: parsed JSON map    → normalized `:vllm/*` result
  - `parse-chunk`   : one SSE data chunk → normalized `:vllm/*` delta"
  (:require [kotoba.lang.text :as str]
            [vllm.sampling :as sampling]))

;; ---------------------------------------------------------------------------
;; render :vllm/* request -> string-keyed OpenAI/vLLM body
;; ---------------------------------------------------------------------------

(defn- render-message [{:vllm/keys [role content tool-call-id name]}]
  (cond-> {"role" (clojure.core/name role) "content" content}
    tool-call-id (assoc "tool_call_id" tool-call-id)
    name         (assoc "name" name)))

(defn render
  "Render a request to the string-keyed map the server expects. Merges sampling
  fields, model, messages/prompt, stream, and tools. Pure."
  [req]
  (let [base (cond-> {"model" (:vllm/model req)}
               (:vllm/stream req) (assoc "stream" true)
               (:vllm/tools req)  (assoc "tools" (:vllm/tools req)))
        body (merge base (sampling/to-wire (:vllm/sampling req)))]
    (case (:vllm/endpoint req)
      :chat       (assoc body "messages"
                         (mapv render-message (:vllm/messages req)))
      :completion (assoc body "prompt" (:vllm/prompt req))
      body)))

;; ---------------------------------------------------------------------------
;; parse server response (string-keyed) -> normalized :vllm/* result
;; ---------------------------------------------------------------------------

(defn- choice-text
  "Extract generated text from a choice for either endpoint."
  [choice]
  (or (get-in choice ["message" "content"])    ; chat
      (get choice "text")                       ; completion
      (get-in choice ["delta" "content"])))     ; streaming delta

(defn- parse-choice [choice]
  (cond-> {:vllm/index  (get choice "index")
           :vllm/text   (choice-text choice)
           :vllm/finish-reason (some-> (get choice "finish_reason") keyword)}
    (get-in choice ["message" "tool_calls"])
    (assoc :vllm/tool-calls (get-in choice ["message" "tool_calls"]))))

(defn- parse-usage [usage]
  (when usage
    {:vllm/prompt-tokens     (get usage "prompt_tokens")
     :vllm/completion-tokens (get usage "completion_tokens")
     :vllm/total-tokens      (get usage "total_tokens")}))

(defn parse-response
  "Normalize a full (non-streaming) parsed JSON response into `:vllm/*` EDN:

    {:vllm/id … :vllm/model … :vllm/choices [{:vllm/text … :vllm/finish-reason …}]
     :vllm/text <first choice text> :vllm/usage {…}}

  Pure; tolerant of missing fields."
  [resp]
  (let [choices (mapv parse-choice (get resp "choices"))]
    (cond-> {:vllm/id      (get resp "id")
             :vllm/model   (get resp "model")
             :vllm/choices choices
             :vllm/text    (:vllm/text (first choices))}
      (get resp "usage") (assoc :vllm/usage (parse-usage (get resp "usage"))))))

;; ---------------------------------------------------------------------------
;; streaming: parse a single SSE `data:` line into a normalized delta
;; ---------------------------------------------------------------------------

(defn done-chunk?
  "True for the terminal `data: [DONE]` SSE sentinel."
  [line]
  (= "[DONE]" (str/trim (str/replace (or line "") #"^data:\s*" ""))))

(defn strip-sse
  "Strip a leading `data:` prefix from an SSE line, returning the JSON payload
  string (or nil for blanks / the [DONE] sentinel). The host JSON-parses it."
  [line]
  (let [s (str/replace (or line "") #"^data:\s*" "")]
    (when-not (or (str/blank? s) (= "[DONE]" (str/trim s))) s)))

(defn parse-chunk
  "Normalize one already-parsed streaming chunk (string-keyed map) into a delta:
  `{:vllm/delta <text> :vllm/finish-reason …}`. Pure."
  [chunk]
  (let [choice (first (get chunk "choices"))]
    {:vllm/delta         (get-in choice ["delta" "content"])
     :vllm/finish-reason (some-> (get choice "finish_reason") keyword)}))
