(ns kotoba.capability.http.fetch.egress
  "Whether one URL may be fetched, as a pure decision.

  `http/fetch` is the first capability in this family whose effect leaves the
  machine. The other eight are `:pure-compute`, `:codec`, `:crypto`,
  `:randomness` and `:clock` — none of them can reach anything, so none of them
  needed a policy and none of them has one. This does, and the policy is the
  capability: an unconstrained `http/fetch` is not a narrower authority than
  `process/spawn`, it is a wider one with a friendlier name.

  Pure and `.cljc` on purpose. Every refusal below is reachable in a test with
  no socket, which is the only way a negative test can be trusted to have been
  exercised for the reason it claims.

  ## Deny by default, and `no-policy` is its own answer

  A provider built without an allowlist refuses everything with
  `:egress/no-policy`, NOT `:egress/host-not-allowed`. `manifest/bot-allowances.edn`
  states the same floor for spending — \"no policy is not permission\" — and the
  distinction matters here for the same reason it matters there: an operator
  who forgot to write a policy and an operator whose policy excludes this host
  have different next actions.

  ## The four refusals are four facts

  | reason | what happened |
  |---|---|
  | `:egress/no-policy` | nothing was configured; nothing was attempted |
  | `:egress/host-not-allowed` | a policy exists and this host is not in it |
  | `:egress/scheme-not-allowed` | not https |
  | `:egress/method-not-allowed` | not a read |

  Collapsing them into `denied` would leave the caller with one word for four
  situations, three of which are fixed by editing different things."
  (:require [kotoba.lang.text :as str]))

(def schema "kotoba.capability.http.fetch.egress.v1")

(def read-methods
  "The methods this capability admits.

  `http/fetch` declares `:capability/effects #{:network-read}`. A POST is a
  write and belongs to `capability-http-post`, which is a different definition
  CID and therefore a different grant. Admitting one here would make the
  effect declaration false, and the effect declaration is what a policy engine
  upstream reads to decide whether this capability may be held at all."
  #{"GET" "HEAD"})

(defn- host-of [url]
  (try
    (let [m (re-find #"^([a-zA-Z][a-zA-Z0-9+.-]*)://([^/?#]+)" (str url))]
      (when m
        (let [scheme (str/lower (nth m 1))
              authority (nth m 2)
              ;; strip userinfo before the host: `https://evil@allowed.example`
              ;; has authority `evil@allowed.example` and host `allowed.example`,
              ;; and a naive split would let the userinfo carry the allowed name
              ;; while the host is something else entirely.
              hostport (if-let [i (str/last-index-of authority "@")]
                         (subs authority (inc i))
                         authority)
              host (if (str/starts-with? hostport "[")
                     ;; IPv6 literal
                     (subs hostport 0 (inc (or (str/index-of hostport "]") 0)))
                     (first (str/split hostport #":")))]
          {:scheme scheme :host (str/lower (str host))})))
    (catch #?(:clj Exception :cljs :default) _ nil)))

(defn admit
  "`{:allowed? true :host h}` or a refusal naming its reason.

  `policy` is `{:allow #{host …} :schemes #{\"https\"}}`. An absent or empty
  `:allow` is not an open door."
  ([policy url] (admit policy url "GET"))
  ([policy url method]
   (let [allow (:allow policy)
         schemes (or (:schemes policy) #{"https"})
         m (str/upper (str (or method "GET")))
         parsed (host-of url)]
     (cond
       (empty? allow)
       {:allowed? false :reason :egress/no-policy
        :message "この provider には egress policy がありません。policy が無いことは許可ではありません。"}

       (nil? parsed)
       {:allowed? false :reason :egress/unparsable-url
        :message (str "URL を読めません: " (pr-str url))}

       (not (contains? read-methods m))
       {:allowed? false :reason :egress/method-not-allowed
        :message (str m " は read ではありません。書き込みは http/post（別の capability）です。")
        :method m}

       (not (contains? schemes (:scheme parsed)))
       {:allowed? false :reason :egress/scheme-not-allowed
        :message (str (:scheme parsed) " は許可された scheme ではありません: "
                      (str/join " " (sort schemes)))
        :scheme (:scheme parsed)}

       (not (contains? allow (:host parsed)))
       {:allowed? false :reason :egress/host-not-allowed
        :message (str (:host parsed) " は policy の allow にありません: "
                      (str/join " " (sort allow)))
        :host (:host parsed)}

       :else {:allowed? true :host (:host parsed) :scheme (:scheme parsed) :method m}))))
