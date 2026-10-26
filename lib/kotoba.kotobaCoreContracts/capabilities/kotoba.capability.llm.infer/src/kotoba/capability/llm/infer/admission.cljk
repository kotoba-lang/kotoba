(ns kotoba.capability.llm.infer.admission
  "Whether one inference request may be sent, as a pure decision.

  `llm/infer` declares three effects where `http/fetch` declares one:

      http/fetch   #{:network-read}
      llm/infer    #{:data-egress :network-write :llm-inference}

  Each of the three is a separate thing the policy has to decide, and the
  reason this namespace is longer than `egress.cljc` is that it decides three
  questions rather than one:

  | effect | the question | the bound |
  |---|---|---|
  | `:network-write` | may this endpoint be reached at all | `:allow-endpoints` |
  | `:data-egress` | how much may leave this machine | `:max-prompt-bytes` |
  | `:llm-inference` | how much work may be bought | `:max-output-tokens` |

  Pure and `.cljc` on purpose. Every refusal below is reachable in a test with
  no socket, which is the only way a negative test can be trusted to have been
  exercised for the reason it claims (ADR-2608136000 §6).

  ## The alias trap: resolve first, then admit

  The workspace's model SSoT is an alias (`murakumo-main`) that resolves to an
  endpoint, and the endpoint moves. So a policy written about the ALIAS decides
  about a name while the request goes to whatever that name resolves to today —
  the decision made about one thing and executed against another. That is the
  same shape as following an HTTP redirect after the allowlist has already
  said yes, which `capability-http-fetch` refuses to do for the same reason.

  `admit` therefore takes `:endpoint`, not an alias, and refuses with
  `:infer/endpoint-unresolved` when it is absent. **Resolving the alias is a
  network READ and belongs to `http/fetch` — a different definition CID and
  therefore a different grant.** This capability does not resolve anything, and
  a provider here that quietly did would be exercising an authority it was
  never given.

  ## Deny by default here, and REPORT-when-absent in `bot-bounds`

  Two rows in this workspace look alike and default in opposite directions, so
  the difference is worth stating rather than discovering:

  - `cloud.itonami.app.bot-bounds` is **enforced when set, reported when
    absent**. It caps work that is already authorised and already paid for
    under the operator's own key; defaulting it to zero would stop live bots
    on nobody's decision.
  - this namespace is **deny by default**. It is not a cap on authorised work,
    it IS the authorisation — `:capability/default-policy :approval-required`.
    An absent ceiling here is not a permissive ceiling, it is a grant nobody
    bounded.

  Copying the wrong default between them is easy and silent, which is why both
  docstrings name the other.

  ## Eight refusals, eight facts

  | reason | what happened | what the operator changes |
  |---|---|---|
  | `:infer/no-policy` | an allowlist is empty | write the policy |
  | `:infer/unbounded` | allowlists exist, a ceiling does not | write the ceiling |
  | `:infer/endpoint-unresolved` | nobody said where this model is served | resolve it (via `http/fetch`) |
  | `:infer/unparsable-endpoint` | an endpoint was given and cannot be read | fix the endpoint |
  | `:infer/scheme-not-allowed` | not https | fix the endpoint |
  | `:infer/endpoint-not-allowed` | a policy exists and this host is not in it | widen the policy, deliberately |
  | `:infer/model-not-allowed` | a policy exists and this model is not in it | widen the policy, deliberately |
  | `:infer/prompt-too-large` | more would leave the machine than permitted | shrink the prompt, or the ceiling |

  Collapsing them into `denied` would leave the caller with one word for eight
  situations that are fixed by editing eight different things."
  (:require [kotoba.lang.text :as str]))

(def schema "kotoba.capability.llm.infer.admission.v1")

(def policy-keys
  "The policy's keys. Named so a surface can report which one is missing."
  #{:allow-endpoints :allow-models :schemes
    :max-prompt-bytes :max-output-tokens})

(def ^:private required-allowlists [:allow-endpoints :allow-models])
(def ^:private required-ceilings [:max-prompt-bytes :max-output-tokens])

(defn- host-of
  "The host of `url`, or nil. Shares `capability-http-fetch`'s two traps.

  userinfo is stripped before the host is read, because
  `https://api.murakumo.cloud@evil.example/` has authority
  `api.murakumo.cloud@evil.example` and host `evil.example` — a naive split
  would let the userinfo carry the allowed name while the request goes
  somewhere else."
  [url]
  (try
    (let [m (re-find #"^([a-zA-Z][a-zA-Z0-9+.-]*)://([^/?#]+)" (str url))]
      (when m
        (let [scheme (str/lower (nth m 1))
              authority (nth m 2)
              hostport (if-let [i (str/last-index-of authority "@")]
                         (subs authority (inc i))
                         authority)
              host (if (str/starts-with? hostport "[")
                     (subs hostport 0 (inc (or (str/index-of hostport "]") 0)))
                     (first (str/split hostport #":")))]
          {:scheme scheme :host (str/lower (str host))})))
    (catch #?(:clj Exception :cljs :default) _ nil)))

(defn- missing-allowlists [policy]
  (into #{} (remove #(seq (get policy %)) required-allowlists)))

(defn- missing-ceilings [policy]
  (into #{} (remove #(let [v (get policy %)] (and (number? v) (pos? v)))
                    required-ceilings)))

(defn unbounded?
  "Whether `policy` names allowlists but no ceiling. For counting, not deciding."
  [policy]
  (and (empty? (missing-allowlists policy))
       (seq (missing-ceilings policy))))

(defn refuse-model
  "A refusal if `policy` does not admit `model`, else nil.

  Separate from `admit` and public because the ORDER matters to the caller, not
  only to the answer. A provider that resolves an endpoint before checking the
  model lets a guest drive the host's resolver with names the policy already
  rejects — and resolving is itself a network read the guest was never granted.
  So the provider asks this first, and never resolves what it will refuse."
  [policy model]
  (let [no-lists (missing-allowlists policy)
        no-ceils (missing-ceilings policy)]
    (cond
      (seq no-lists)
      {:allowed? false :reason :infer/no-policy :missing no-lists
       :message (str "この provider には policy がありません（"
                     (str/join " " (sort (map name no-lists)))
                     "）。policy が無いことは許可ではありません。")}

      (seq no-ceils)
      {:allowed? false :reason :infer/unbounded :missing no-ceils
       :message (str "policy に上限がありません（"
                     (str/join " " (sort (map name no-ceils)))
                     "）。上限の不在は無制限ではなく、誰も上限を決めていないという事実です。")}

      (not (contains? (:allow-models policy) (str model)))
      {:allowed? false :reason :infer/model-not-allowed :model model
       :message (str (pr-str model) " は policy の allow-models にありません: "
                     (str/join " " (sort (:allow-models policy))))})))

(defn admit
  "`{:allowed? true …}` or a refusal naming its reason.

  `request` is `{:model \"…\" :endpoint \"https://…\" :prompt-bytes n
  :max-output-tokens n}`. `:endpoint` is the RESOLVED endpoint — see the alias
  trap above; an alias passed here is refused as unparsable rather than
  resolved.

  A caller asking for more output than the policy permits is **narrowed, not
  refused**: the result carries the capped `:max-output-tokens` and
  `:narrowed? true`. That mirrors `bot-bounds/cap` — every ceiling narrows and
  none raises — and it keeps the fact visible instead of silently granting the
  smaller number as if it had been asked for.

  A prompt over `:max-prompt-bytes` is refused rather than truncated. Truncating
  it would send a DIFFERENT prompt than the caller wrote while reporting
  success, and `:data-egress` is precisely the effect where quietly changing
  what left the machine is the wrong answer."
  [policy request]
  (let [{:keys [model endpoint prompt-bytes]} request]
    (cond
      ;; The policy, the ceiling and the model first -- see `refuse-model`.
      ;; A request for a model this policy does not admit is refused before
      ;; anything is asked about where that model lives.
      (some? (refuse-model policy model))
      (refuse-model policy model)

      (str/blank? (str endpoint))
      {:allowed? false :reason :infer/endpoint-unresolved
       :message (str "この model が serve されている場所を誰も言っていません: "
                     (pr-str model)
                     "。alias の解決は network read であり http/fetch の grant です。")
       :model model}

      (nil? (host-of endpoint))
      {:allowed? false :reason :infer/unparsable-endpoint
       :message (str "endpoint を読めません: " (pr-str endpoint)
                     "。alias は endpoint ではありません。")
       :endpoint endpoint}

      :else
      (let [{:keys [scheme host]} (host-of endpoint)
            schemes (or (:schemes policy) #{"https"})]
        (cond
          (not (contains? schemes scheme))
          {:allowed? false :reason :infer/scheme-not-allowed :scheme scheme
           :message (str scheme " は許可された scheme ではありません: "
                         (str/join " " (sort schemes)))}

          (not (contains? (:allow-endpoints policy) host))
          {:allowed? false :reason :infer/endpoint-not-allowed :host host
           :message (str host " は policy の allow-endpoints にありません: "
                         (str/join " " (sort (:allow-endpoints policy))))}

          (> (long (or prompt-bytes 0)) (long (:max-prompt-bytes policy)))
          {:allowed? false :reason :infer/prompt-too-large
           :prompt-bytes prompt-bytes :max-prompt-bytes (:max-prompt-bytes policy)
           :message (str "prompt が data-egress の上限を超えます: "
                         prompt-bytes " > " (:max-prompt-bytes policy)
                         "。切り詰めれば、書かれたものと違う prompt を送って成功と報告することになります。")}

          :else
          (let [ceiling (long (:max-output-tokens policy))
                asked (:max-output-tokens request)
                capped (if (number? asked) (min (long asked) ceiling) ceiling)]
            {:allowed? true
             :host host
             :scheme scheme
             :model (str model)
             :endpoint (str endpoint)
             :prompt-bytes (long (or prompt-bytes 0))
             :max-output-tokens capped
             :narrowed? (boolean (and (number? asked) (> (long asked) ceiling)))}))))))
