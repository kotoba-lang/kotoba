(ns lgx.graphs.agent-chat
  "x.etzhayyim.com `agent_chat` graph — community / strategist / analyst persona
  chat. clj port of `lg_x/graphs/agent_chat.py` onto langgraph-clj (ADR-2606280030).

  Roles aligned with platform-X creator-economy ops:
    community_manager — replies, mentions triage
    strategist        — content calendar, hook design, A/B framing
    analyst           — engagement / impressions / CTR readings
    ghostwriter       — draft tweet copy in user's voice
    trend_scout       — surface trending topics & niche memes

  Topology: resolve_actor → llm_call → emit_audit (same as Python). LLM call goes
  to the Murakumo loopback (lgx.llm), not the RunPod proxy."
  (:require [langgraph.graph :as g]
            [lgx.audit :as audit]
            [lgx.llm :as llm]
            [kotoba.lang.text :as str]))

(def actor-prompts
  {"community_manager"
   (str "You are a community manager AI for the X (Twitter) platform. You triage "
        "mentions, replies, and DMs. Reply with: classification (positive / neutral / "
        "complaint / spam / urgent), suggested action (reply / ignore / escalate), "
        "and a draft response (≤280 chars) when reply is suggested. Be warm, concise.")
   "strategist"
   (str "You are a content strategist AI for X. You design weekly content calendars, "
        "hook frameworks (curiosity / contrarian / data / story / question), and "
        "thread architectures. Reply with structured plans: theme → 3-5 hook variants → "
        "thread outline. Reference current trends if given.")
   "analyst"
   (str "You are a growth analyst AI for X. Given engagement metrics (impressions, "
        "engagement rate, follower delta), surface 1-3 actionable insights. Quote the "
        "specific number that drove each insight. No vague advice — every claim must "
        "tie to a metric.")
   "ghostwriter"
   (str "You are a ghostwriter AI for X. Draft tweets / threads in the user's voice "
        "(reference their prior posts via context). Output formats: single tweet "
        "(≤280 chars), thread (numbered, ≤8 posts), or quote tweet. Match cadence "
        "and emoji density of the user's existing style.")
   "trend_scout"
   (str "You are a trend scout AI for X. Surface 3-5 niche-relevant trending topics "
        "from the past 24-48h. Reply: topic → why it matters → angle for the user's "
        "voice. Avoid generic top-10 trends — go niche.")})

(defn- system-prompt [role]
  (or (get actor-prompts role) (get actor-prompts "community_manager")))

(defn node-resolve-actor [state]
  (let [role (or (:actor-role state) "community_manager")
        app-did (:app-did (audit/config state))]
    {:actor-did (str app-did ":actor:" role)
     :actor-role role}))

(defn- trunc [^String s n] (subs s 0 (min n (count s))))

(defn node-llm-call [state]
  (let [user-text (str/trim (or (:message state) ""))]
    (if (empty? user-text)
      {:error "message required"}
      (let [role (or (:actor-role state) "community_manager")
            handle (or (:handle state) "")
            system (cond-> (system-prompt role)
                     (seq handle) (str "\n\nContext: handle=@" handle "."))
            history (->> (or (:history state) [])
                         (take-last 12)
                         (keep (fn [h]
                                 (when (map? h)
                                   (let [r (or (:role h) (get h "role"))
                                         c (or (:content h) (get h "content"))]
                                     (when (and (#{"user" "assistant"} r) (string? c) (seq c))
                                       {:role r :content (trunc c 2000)}))))))
            messages (concat [{:role "system" :content system}]
                             history
                             [{:role "user" :content (trunc user-text 4000)}])
            payload {:model (llm/model state)
                     :messages (vec messages)
                     :max_tokens (int (or (:max-tokens state) 384))
                     :temperature (double (or (:temperature state) 0.7))}
            {:keys [ok resp error latency-ms]} (llm/chat-completions state payload)]
        (if-not ok
          {:error error :latency-ms latency-ms}
          (let [choice (first (or (:choices resp) [{}]))
                msg (or (:message choice) {})
                usage (or (:usage resp) {})]
            {:reply (str/trim (or (:content msg) ""))
             :model (or (:model resp) (llm/model state))
             :prompt-tokens (int (or (:prompt_tokens usage) 0))
             :completion-tokens (int (or (:completion_tokens usage) 0))
             :total-tokens (int (or (:total_tokens usage) 0))
             :latency-ms latency-ms}))))))

(defn node-emit-audit [state]
  (audit/emit-audit-bg
   state
   {:actor (or (:actor-did state) (:app-did (audit/config state)))
    :activity "x.chat.reply"
    :object-id (str "chat:" (or (:actor-role state) "community_manager") ":"
                    (quot (System/currentTimeMillis) 1000))
    :object-type "x.chat"
    :attributes {:actorRole (:actor-role state)
                 :handle (:handle state)
                 :userDid (:user-did state)
                 :totalTokens (:total-tokens state 0)
                 :latencyMs (:latency-ms state 0)
                 :model (:model state)
                 :ok (not (boolean (:error state)))}})
  {})

(defn build
  "Compile the agent_chat StateGraph: resolve_actor → llm_call → emit_audit."
  []
  (-> (g/state-graph)
      (g/add-node :resolve-actor node-resolve-actor)
      (g/add-node :llm-call node-llm-call)
      (g/add-node :emit-audit node-emit-audit)
      (g/set-entry-point :resolve-actor)
      (g/add-edge :resolve-actor :llm-call)
      (g/add-edge :llm-call :emit-audit)
      (g/set-finish-point :emit-audit)
      (g/compile-graph)))

(def ^{:doc "Compiled agent_chat graph (langgraph-clj). Name: agent_chat."} GRAPH (delay (build)))
