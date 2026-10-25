(ns lgx.graphs.compose-tweet
  "x.etzhayyim.com `compose_tweet` graph — draft tweet/thread copy (no posting).
  clj port of `lg_x/graphs/compose_tweet.py` onto langgraph-clj (ADR-2606280030).

  Pure LLM compose path. Does NOT call X API (that is a future `post` graph that
  needs OAuth). Safest first ship: drafts are human-reviewable before any API call.

  Output shape:
    :format     single | thread | quote_tweet | reply
    :tweets     vector of strings, each ≤280 chars (X's hard limit)
    :rationale  1-line \"why this hook\"
    :hashtags   vector of strings, up to 4

  Topology: compose → emit_audit (same as Python). LLM via Murakumo loopback."
  (:require [langgraph.graph :as g]
            [lgx.audit :as audit]
            [lgx.llm :as llm]
            [cheshire.core :as json]
            [kotoba.lang.text :as str]))

(def hook-hints
  {"curiosity"  "Open with a surprising claim or counterintuitive observation that the reader needs to keep reading to resolve."
   "contrarian" "Open by stating the popular view, then immediately disagreeing with a specific reason."
   "story"      "Open mid-action with a tight scene (≤2 lines), then zoom out to the lesson."
   "data"       "Open with a single number that reframes the topic, then explain its meaning."
   "question"   "Open with a high-stakes question the reader genuinely doesn't know the answer to."})

(defn- as-int [v default]
  (cond (integer? v) v
        (string? v) (try (Integer/parseInt (str/trim v)) (catch Exception _ default))
        (number? v) (int v)
        :else default))

(defn build-system-prompt [state]
  (let [fmt (or (:format state) "single")
        angle (or (:angle state) "curiosity")
        hook (or (get hook-hints angle) (get hook-hints "curiosity"))
        handle (or (:handle state) "the user")
        max-t (max 1 (min 12 (as-int (:max-tweets state) (if (= fmt "thread") 8 1))))]
    (str "You are a tweet ghostwriter for @" handle ". Draft X content in their voice.\n"
         "Format: " fmt ". Max " max-t " tweet(s). Each ≤280 characters (HARD LIMIT).\n"
         "Angle: " angle " — " hook "\n"
         "Output ONLY a JSON object with exact keys: "
         "{ \"tweets\": [string, ...], \"rationale\": string, \"hashtags\": [string, ...] }. "
         "No prose, no code-fence, no commentary.")))

(defn enforce-280
  "X counts URLs as 23 chars + emoji as 2-4. Conservatively cap to 270 for safety."
  [^String text]
  (if (<= (count text) 270)
    text
    (let [head (subs text 0 267)
          sp (str/last-index-of head " ")
          cut (if (and sp (pos? sp)) (subs head 0 sp) head)]
      (str cut "…"))))

(defn parse-llm-json
  "Best-effort JSON extraction (mirrors the Python _parse_llm_json)."
  [raw]
  (let [raw (str/trim (or raw ""))
        raw (if (str/starts-with? raw "```")
              (-> raw
                  (str/replace #"(?s)^```[a-zA-Z]*\n" "")
                  (str/replace #"(?s)\n```$" ""))
              raw)]
    (or (try (json/parse-string raw true) (catch Exception _ nil))
        (when-let [m (re-find #"(?s)\{.*\}" raw)]
          (try (json/parse-string m true) (catch Exception _ nil)))
        {})))

(defn node-compose [state]
  (let [topic (str/trim (or (:topic state) ""))]
    (if (empty? topic)
      {:error "topic required"}
      (let [sys-prompt (build-system-prompt state)
            voice (str/trim (or (:voice-sample state) ""))
            parts (cond-> [(str "Topic: " topic)]
                    (seq voice)
                    (conj (str "Voice sample (match cadence + emoji density):\n"
                               (subs voice 0 (min 1500 (count voice)))))
                    (and (= (:format state) "quote_tweet") (:quote-url state))
                    (conj (str "Quote-tweeting: " (:quote-url state)))
                    (and (= (:format state) "reply") (:reply-to state))
                    (conj (str "Reply context: " (subs (:reply-to state) 0 (min 1500 (count (:reply-to state)))))))
            payload {:model (llm/model state)
                     :messages [{:role "system" :content sys-prompt}
                                {:role "user" :content (str/join "\n\n" parts)}]
                     :max_tokens 768
                     :temperature 0.85}
            {:keys [ok resp error latency-ms]} (llm/chat-completions state payload)]
        (if-not ok
          {:error error :latency-ms latency-ms}
          (let [raw (or (-> (or (:choices resp) [{}]) first :message :content) "")
                parsed (parse-llm-json raw)
                tweets (->> (or (:tweets parsed) [])
                            (filter string?)
                            (mapv enforce-280))
                tweets (if (empty? tweets) [(enforce-280 raw)] tweets)]
            {:tweets tweets
             :rationale (subs (or (:rationale parsed) "") 0 (min 300 (count (or (:rationale parsed) ""))))
             :hashtags (->> (or (:hashtags parsed) []) (filter string?) (take 4) vec)
             :model (or (:model resp) (llm/model state))
             :latency-ms latency-ms}))))))

(defn node-emit-audit [state]
  (audit/emit-audit-bg
   state
   {:actor (:app-did (audit/config state))
    :activity "x.tweet.composed"
    :object-id (str "compose:" (or (:handle state) "-") ":" (quot (System/currentTimeMillis) 1000))
    :object-type "x.tweet"
    :attributes {:handle (:handle state)
                 :topic (subs (or (:topic state) "") 0 (min 120 (count (or (:topic state) ""))))
                 :format (:format state)
                 :angle (:angle state)
                 :tweetCount (count (or (:tweets state) []))
                 :latencyMs (:latency-ms state 0)
                 :ok (not (boolean (:error state)))}})
  {})

(defn build
  "Compile the compose_tweet StateGraph: compose → emit_audit."
  []
  (-> (g/state-graph)
      (g/add-node :compose node-compose)
      (g/add-node :emit-audit node-emit-audit)
      (g/set-entry-point :compose)
      (g/add-edge :compose :emit-audit)
      (g/set-finish-point :emit-audit)
      (g/compile-graph)))

(def ^{:doc "Compiled compose_tweet graph (langgraph-clj). Name: compose_tweet."} GRAPH (delay (build)))
