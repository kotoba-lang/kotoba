(ns importer.connector
  "The corpus, as a connector.

  A bot that wants mail has two ways to get it, and they are not the same
  thing:

    gmail_*  / microsoft_graph_*   live, at the provider, on the user's grant
    corpus_*                       imported, local, on no external grant at all

  Putting the second on the connector plane rather than inventing a plane for
  it is what makes N bots cheap. `cloud-itonami-app` already builds an
  `IHttp`, an `ITokens` and a registry, and `bots.clj` already calls
  `connector.invoke/call`; a corpus tool joins that path with no new code and
  inherits the two-tier rule -- and since every tool here is `:read`, nothing
  in it is ever held for a human.

  ## Why the auth profile is `bearer` and not `none`

  `:none` would be a lie that reads as a security property. The corpus is
  reached over HTTP and the request is authorised; saying so with a token the
  host supplies keeps the authority visible and per-bot, instead of ambient in
  whatever session happened to make the call.

  ## What the profile buys structurally

  `connector.validate` treats a scope declared on a provider with no scope
  mechanism as an ERROR. A `bearer` profile has none. So `corpus_*` tools
  **cannot** declare a Google or Microsoft scope -- not by convention, but
  because `connector.provider/provider` throws at load time if one tries. The
  property `a bot reading the corpus holds no provider scope` is checked by the
  kernel this namespace depends on, and `connector_test` asserts it directly."
  (:require [connector.model :as m]
            [connector.provider :as p]))

(def default-base-url "https://itonami.cloud")

(def auth
  (m/bearer "ITONAMI_CORPUS_TOKEN"))

(defn descriptor
  ([] (descriptor default-base-url))
  ([base-url]
   (-> (m/connector
        "cloud.itonami.corpus" "Imported Workspace Corpus"
        {:summary (str "Mail, calendar and files already imported from a tenant's "
                       "Google Workspace and Microsoft 365. Read-only, and every "
                       "answer states what it covers.")
         :origin-domain "itonami.cloud"
         :base-url base-url
         :auth auth})

       (m/add-tool
        "corpus_mail_search"
        {:description (str "Search imported mail across every connected provider. "
                           "Answers carry coverage: an empty result with an "
                           "uncovered mailbox is not the same as no such mail.")
         :effect :read
         :input-schema {:type "object"
                        :properties {"q" {:type "string" :description "free text over subject, body and addresses"}
                                     "mailbox" {:type "string" :description "restrict to one mailbox address"}
                                     "from" {:type "string"}
                                     "since" {:type "integer" :description "epoch ms, inclusive"}
                                     "limit" {:type "integer" :description "1-200, default 50"}}}})

       (m/add-tool
        "corpus_mail_thread"
        {:description "Every imported message in one thread, oldest first."
         :effect :read
         :input-schema {:type "object"
                        :properties {"thread_id" {:type "string"}}
                        :required ["thread_id"]}})

       (m/add-tool
        "corpus_mail_message"
        {:description (str "One imported message by its provider-independent id. "
                           "Headers by default; the raw blob is referenced, not inlined.")
         :effect :read
         :input-schema {:type "object"
                        :properties {"message_id" {:type "string"}
                                     "body" {:type "boolean" :description "include the body, default false"}}
                        :required ["message_id"]}})

       (m/add-tool
        "corpus_calendar_window"
        {:description "Imported events overlapping a time window."
         :effect :read
         :input-schema {:type "object"
                        :properties {"start" {:type "integer" :description "epoch ms"}
                                     "end" {:type "integer" :description "epoch ms"}
                                     "calendar" {:type "string"}}
                        :required ["start" "end"]}})

       (m/add-tool
        "corpus_file_search"
        {:description "Imported file metadata. Metadata only -- no tool here downloads content."
         :effect :read
         :input-schema {:type "object"
                        :properties {"q" {:type "string"}
                                     "limit" {:type "integer"}}}})

       (m/add-tool
        "corpus_import_status"
        {:description (str "What each stream is read through, and what it is not. "
                           "Three-valued: a stream that could not be measured is "
                           "reported as such rather than as current.")
         :effect :read
         :input-schema {:type "object" :properties {}}}))))

;; --- request / normalize ---------------------------------------------------

(def ^:private paths
  {"corpus_mail_search" "/api/corpus/mail/search"
   "corpus_mail_thread" "/api/corpus/mail/thread"
   "corpus_mail_message" "/api/corpus/mail/message"
   "corpus_calendar_window" "/api/corpus/calendar/window"
   "corpus_file_search" "/api/corpus/file/search"
   "corpus_import_status" "/api/corpus/status"})

(defn- query-of [args]
  (into {} (keep (fn [[k v]] (when (some? v) [(name k) (str v)]))) args))

(defn request
  "Tool call -> request map. No credential: `connector.invoke` attaches it."
  [base-url tool-name args]
  (if-let [path (get paths tool-name)]
    (cond-> {:connector.http/method :get
             :connector.http/url (str base-url path)}
      (seq args) (assoc :connector.http/query (query-of args)))
    (throw (ex-info "unknown corpus tool" {:type :importer/unknown-tool
                                           :tool tool-name}))))

(def no-coverage
  "The result a bot gets when the corpus answered without saying what it read.

  Returned rather than thrown so the bot's turn continues and the model can see
  why it must not conclude anything -- a thrown exception here reads to a
  caller as a transport failure, and transport failures get retried."
  {:importer/error :importer/no-coverage
   :importer/note (str "the corpus answered without stating its coverage; an "
                       "empty result cannot be told apart from a stream that "
                       "was never imported, so this answer supports no "
                       "conclusion either way")})

(defn normalize
  "Response -> result, refusing any answer that does not state its coverage.

  This is the enforcement point at the bot boundary. `importer.coverage/answer`
  is the only constructor of a corpus result in this library, but the corpus is
  reached over HTTP and an endpoint could be changed to return a bare list. If
  one ever is, every bot gets `:importer/no-coverage` instead of a plausible
  empty list, which is the failure it should be."
  [_tool-name response]
  (let [body (:connector.http/body response)]
    (cond
      (not (map? body)) no-coverage
      (contains? body :importer/coverage) body
      (contains? body "importer/coverage") body
      :else no-coverage)))

(defn provider
  ([] (provider default-base-url))
  ([base-url]
   (p/provider (descriptor base-url)
               {:request (fn [tool-name args] (request base-url tool-name args))
                :normalize normalize})))
