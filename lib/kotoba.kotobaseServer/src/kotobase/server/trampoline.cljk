(ns kotobase.server.trampoline
  "Bridge an ASYNC block store (any `fetch1: cid -> Promise<bytes>`) to
  kotobase-peer's SYNCHRONOUS block reader contract (`(get-fn cid) -> bytes`).
  Storage-agnostic by construction -- works identically over Cloudflare R2,
  Backblaze B2, IndexedDB, or anything else that can answer \"give me the
  bytes at this CID\" asynchronously; the concrete `fetch1` is entirely the
  caller's concern.

  `cold-datoms`/`hydrate-db`/`commit!` walk a prolly-tree (or, for `commit!`,
  just the chain head) through that sync get-fn, but any real storage
  backend is async. `with-blocks` runs the sync computation against an
  in-memory block cache and, on a cache miss, fetches the block via `fetch1`
  and retries -- a block-miss trampoline. Correct for any tree shape;
  efficient once the read touches few blocks (prolly-tree prefix pruning
  bounds this for a filtered read, so this stays cheap even as a graph
  grows -- unlike a full-prefix warm)."
  (:require [kotoba.lang.text :as str]))

(defn missing-block
  "Signal thrown by the sync get-fn on a cache miss; caught by `with-blocks`.
  The `:block-miss` marker lets a caller's error handler re-throw it (rather
  than swallow it as a generic failure) so the trampoline actually sees the
  miss -- see `block-miss?`."
  [cid]
  (ex-info "block-miss" {:block-miss true :cid cid}))

(defn ex-data-chain
  "`ex-data` of `e` and of every cause beneath it, outermost first.

  Exists because a runtime may WRAP a thrown ex-info rather than rethrow it:
  nbb/SCI, when the throw crosses an async continuation, produces its own
  error whose `ex-data` is `{:type :sci/error ...}` and puts the original
  under `:cause`. Any classifier that reads a marker out of `(ex-data e)`
  ONCE therefore stops seeing that marker on that runtime -- and, because the
  marker is what selects the specific outcome, the failure is silent: the
  request degrades to a generic error, or a retryable miss stops being
  retried. Read the chain, not the outermost link.

  Bounded (9 links) so a self-referential cause cannot hang a request. On the
  JVM and under shadow-cljs the chain is one link long, so classifiers keep
  the behaviour they already had."
  [e]
  (->> (iterate ex-cause e) (take-while some?) (take 9) (mapv ex-data)))

(defn miss-data
  "The trampoline's miss payload (`{:block-miss true :cid ...}`) carried by `e`,
  or nil if `e` is not a miss.

  Searches the cause chain (see `ex-data-chain`). Every reader of the payload
  goes through here: `with-blocks` reading `(ex-data e)` inline is what made
  the trampoline itself blind to the signal, while `block-miss?` -- the
  documented predicate directly below it -- would have seen it."
  [e]
  (first (filter :block-miss (ex-data-chain e))))

(defn block-miss?
  "True if `e` is the trampoline's cache-miss signal. A caller wrapping a
  `with-blocks`-driven computation in its OWN try/catch (e.g. to turn engine
  errors into an API error response) must re-throw when this is true,
  instead of swallowing it -- otherwise the trampoline never sees the miss
  and the retry never happens."
  [e]
  (some? (miss-data e)))

(defn with-blocks
  "Run `(f sync-get)` where `sync-get` reads from an in-memory cache,
  fetching absent blocks via `(fetch1 cid) -> Promise<bytes>` and retrying.
  Returns a Promise of `f`'s result. `f` must be pure/idempotent (it is
  re-run per miss, from scratch).

  `f` may return a plain value OR a js/Promise (kotobase-peer's crypto seam,
  ADR-2607051000, makes engine calls Promise-returning on cljs) -- a
  block-miss can therefore surface either as a SYNC throw from `f` or as a
  REJECTION of `f`'s promise (sync-get called inside a `.then`
  continuation), and both trampoline the same way. Non-miss failures reject
  through unchanged.

  The 3-arity takes `seed`, a `{cid bytes}` map the cache STARTS from. It is
  the only way to stop paying for a miss the caller has already resolved.

  A caller that pre-fetches blocks into a cache of its OWN does not help this
  trampoline at all: the cache here is private and starts empty, so `sync-get`
  still throws on the first read of every block and `f` is still re-run once
  per block. The caller's warm makes each of those K re-runs FETCH faster; it
  does not make there be fewer of them, and the re-runs are the O(K^2) term.

  Measured on kotobase-cf-wasm-staging (version 8bedd21a, 2026-08-27): adding
  a per-graph prefetch wave in that Worker's own store layer moved reads from
  ~4,400 to ~3,787 ms of CPU each -- real, and far short of what the wave
  should be worth, because every warmed block was still discovered one at a
  time here.

  `seed` is trusted as already-verified bytes: the caller fetched them through
  its own path, and re-checking would need a hasher this namespace
  deliberately does not have (it is storage-agnostic by construction).
  nil or an empty map behaves exactly like the 2-arity."
  ([fetch1 f] (with-blocks fetch1 f nil))
  ([fetch1 f seed]
   (let [cache (atom (or seed {}))
         sync-get (fn [cid]
                    (if (contains? @cache cid)
                      (get @cache cid)
                      (throw (missing-block cid))))]
     (letfn [(fetch-and-retry [e]
               (if-let [d (miss-data e)]
                 (-> (fetch1 (:cid d))
                     (.then (fn [bytes]
                              (swap! cache assoc (:cid d) bytes)
                              (step))))
                 (js/Promise.reject e)))
             (step []
               (try
                 (-> (js/Promise.resolve (f sync-get))
                     ;; The wrapper is load-bearing, not noise: under nbb/SCI a
                     ;; `letfn` sibling passed BY NAME to a JS callback is never
                     ;; invoked (`(.catch fetch-and-retry)` silently does
                     ;; nothing and the miss escapes as a generic failure).
                     ;; Wrapping in an inline fn is correct on every runtime.
                     (.catch (fn [e] (fetch-and-retry e))))
                 (catch :default e (fetch-and-retry e))))]
       (step)))))
