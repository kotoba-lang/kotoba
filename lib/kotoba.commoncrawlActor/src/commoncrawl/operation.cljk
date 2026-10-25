(ns commoncrawl.operation
  "IngestActor — one Common Crawl ingestion attempt for ONE seed = one
  supervised langgraph.graph StateGraph run:

    intake -> fetch -> advise -> govern -> decide -> commit | hold

  The LLM extraction (`commoncrawl.llm`, the contained intelligence node)
  is sealed into `:advise`; its proposal is ALWAYS routed through
  `commoncrawl.policy` (`:govern`) and `:decide` before anything reaches
  `:commit` — the single invariant every actor in this workspace shares:
  the LLM never writes/discloses anything the Governor would reject.

  No approval/interrupt node (unlike `talent.operation`'s
  `:request-approval`) — this actor has no human-in-the-loop step, so a
  HARD or SOFT policy violation both resolve straight to `:hold`, just
  tagged differently in the ledger fact (see `commoncrawl.policy/
  hold-fact`'s `:soft?`). A fetch MISS (no capture, or a blank extracted
  body) short-circuits straight from `:fetch` to `:hold` too — there is
  nothing for `:advise`/`:govern` to do with an empty page.

  Everything the actor depends on is injected at `build` time (swap, not a
  rewrite):
    - `store`       — a `commoncrawl.store/Store` (MemStore | DatomicStore)
    - `:advise-fn`  — `(fn [page] -> extraction proposal)` (default: a
                      mock — see `commoncrawl.llm/advise` wired to a real
                      `complete-fn` for production)
    - `:embed-fn`   — `(fn [text] -> embedding-vector | nil)` (default:
                      always nil, i.e. ingest with no embedding)
    - `:fetch-fn` / `:warc-fetch-fn` — CDX/WARC capabilities
                      (`commoncrawl.cdx`), default: always-miss
    - `:ingest-fn`  — `(fn [page] -> {:ok ...})` (default: a mock that
                      records nothing — see `commoncrawl.kotobase/ingest!`
                      wired to a real session/http-fn for production)
    - `:collection-id` — the CC collection id `:fetch` queries

  One graph run = one seed. `commoncrawl.loop` drives repeated, budgeted
  runs across the seed list — this ns has no notion of ticks/budgets/
  scheduling, only 'given a seed and a governed decision path, what
  happens once'."
  (:require [langgraph.graph :as g]
            [langgraph.checkpoint :as cp]
            [commoncrawl.cdx :as cdx]
            [commoncrawl.policy :as policy]
            [commoncrawl.store :as store]))

(defn- fetch-miss-fact [seed]
  {:t :fetch-miss :domain (:domain seed) :url (:url seed)})

(defn- commit-fact [seed proposal ingest-result]
  {:t :committed
   :domain (:domain seed)
   :url (:url seed)
   :category (:category proposal)
   :summary (:summary proposal)
   :confidence (:confidence proposal)
   :ingest-ok? (boolean (:ok ingest-result))})

(defn- ingest-page
  "seed + fetched page + proposal + embedding -> the payload
  `commoncrawl.kotobase/ingest!` expects."
  [seed page proposal embedding]
  (cond-> {:url (:url seed)
           :title (or (:title page) "")
           :text (:text page)
           :extracted-category (:category proposal)
           :extracted-summary (:summary proposal)
           :extracted-entities (:entities proposal)}
    (seq embedding) (assoc :embedding embedding)))

(defn build
  "Compiles an IngestActor graph bound to `store`. opts (all optional):
    :advise-fn      (fn [page] -> proposal)   — default: always empty/zero-confidence
    :embed-fn       (fn [text] -> vector|nil) — default: always nil
    :fetch-fn       CDX capability            — default: always no result
    :warc-fetch-fn  WARC capability           — default: always nil
    :ingest-fn      (fn [page] -> {:ok ...})  — default: records nothing, {:ok false}
    :collection-id  CC collection id string   — default: \"CC-MAIN-latest\" placeholder
    :checkpointer   langgraph checkpointer    — default: in-mem

  No `:interrupt-before` is configured — every run is a single bounded
  supervised step with no human-in-the-loop pause, so the default in-mem
  checkpointer is sufficient (the state that must survive ACROSS runs
  lives in `store`'s own `:agent.*` datoms, not in a langgraph checkpoint)."
  [store & [{:keys [advise-fn embed-fn fetch-fn warc-fetch-fn ingest-fn collection-id checkpointer]
             :or {advise-fn (constantly {:category "" :summary "" :entities [] :confidence 0.0})
                  embed-fn (constantly nil)
                  fetch-fn (constantly nil)
                  warc-fetch-fn (constantly nil)
                  ingest-fn (constantly {:ok false :error "no ingest-fn configured"})
                  collection-id "CC-MAIN-latest"
                  checkpointer (cp/mem-checkpointer)}}]]
  (-> (g/state-graph
       {:channels
        {:seed        {:default nil}   ; {:domain :url} — the seed for this run
         :context     {:default nil}   ; {:seeds :exclude :budget} — governor inputs
         :page        {:default nil}   ; {:url :capture :text} | nil on a fetch miss
         :proposal    {:default nil}   ; commoncrawl.llm/advise result
         :embedding   {:default nil}
         :verdict     {:default nil}   ; commoncrawl.policy/check result
         :disposition {:default nil}   ; :commit | :hold
         :audit       {:reducer into :default []}}})

      (g/add-node :intake (fn [s] s))

      (g/add-node :fetch
        (fn [{:keys [seed]}]
          (let [page (cdx/fetch-page-text fetch-fn warc-fetch-fn collection-id (:url seed))]
            (if page
              {:page page :audit [{:t :fetch-ok :domain (:domain seed) :url (:url seed)}]}
              {:page nil :audit [(fetch-miss-fact seed)]}))))

      ;; The contained intelligence node — proposal only, never a commit.
      (g/add-node :advise
        (fn [{:keys [page]}]
          (let [proposal (advise-fn page)
                embedding (embed-fn (:text page))]
            {:proposal proposal :embedding embedding :audit []})))

      ;; PolicyGovernor — independent of the LLM (commoncrawl.policy).
      (g/add-node :govern
        (fn [{:keys [seed context proposal]}]
          {:verdict (policy/check seed context proposal)}))

      (g/add-node :decide
        (fn [{:keys [verdict]}]
          (if (:ok? verdict)
            {:disposition :commit}
            {:disposition :hold})))

      ;; Commit — the ONLY node that writes to net-kotobase + this store's ledger.
      (g/add-node :commit
        (fn [{:keys [seed page proposal embedding]}]
          (let [payload (ingest-page seed page proposal embedding)
                result (ingest-fn payload)
                fact (commit-fact seed proposal result)]
            (store/mark-ingested! store (:url seed)
                                  {:category (:category proposal) :ingest-ok? (:ok result)})
            (store/append-ledger! store fact)
            {:audit [fact]})))

      ;; Hold — write the rejection to the ledger; nothing sent to net-kotobase.
      ;; `:disposition` is set HERE (not only by `:decide`) because a fetch
      ;; MISS routes straight from `:fetch` to `:hold`, bypassing `:decide`
      ;; entirely — without this, that path would leave `:disposition` at
      ;; its channel default (nil), not `:hold`.
      (g/add-node :hold
        (fn [{:keys [seed verdict audit]}]
          (let [fact (if verdict
                       (policy/hold-fact seed verdict)
                       (last audit))]
            (store/append-ledger! store fact)
            {:disposition :hold :audit [fact]})))

      (g/set-entry-point :intake)
      (g/add-edge :intake :fetch)

      (g/add-conditional-edges :fetch
        (fn [{:keys [page]}] (if page :advise :hold)))

      (g/add-edge :advise :govern)
      (g/add-edge :govern :decide)

      (g/add-conditional-edges :decide
        (fn [{:keys [disposition]}] disposition))

      (g/set-finish-point :commit)
      (g/set-finish-point :hold)

      (g/compile-graph {:checkpointer checkpointer})))

(defn run-seed!
  "Runs the compiled actor once for `seed` ({:domain :url}) with the given
  `context` ({:seeds :exclude :budget}). Returns the full run* result
  ({:state :events :status ...}); `thread-id` defaults to the seed's URL
  so repeated runs for the same URL share a (harmless, since no interrupt
  is ever pending) checkpoint thread."
  [actor seed context]
  (g/run* actor {:seed seed :context context} {:thread-id (:url seed)}))
