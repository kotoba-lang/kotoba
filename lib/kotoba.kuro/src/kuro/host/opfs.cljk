(ns kuro.host.opfs
  "Browser-side block store for `kuro.fs`: an OPFS-backed cache in front of
  the kotobase gateway (S2 of ADR-2609041240).

  ## Where this runs, and why

  OPFS sync access handles (`createSyncAccessHandle`) exist ONLY inside a
  Worker — the main thread gets async handles, which `kuro.fs`'s injected
  `get-block` cannot use (it is a synchronous seam by design; making it async
  would push async into the pure model). So the entire block store lives in a
  dedicated Worker and the main thread talks to it over postMessage with
  synchronous-looking request/reply correlation.

  ## The seam (what the host injects into kuro.fs)

    - `put-block`  : bytes -> cid    (computes sha-256 + CIDv1/raw via
                                      WebCrypto; same codec as
                                      `kuro.host.cid`, but the digest is
                                      async — the Worker masks this behind
                                      the sync-looking reply protocol)
    - `get-block`  : cid -> bytes|nil (OPFS first, gateway on miss)

  ## What this file is NOT

  - Not a `.cljc` model: OPFS and WebCrypto are browser effects. This is
    host code, in the same slot `kuro.host.node` occupies for Node.
  - Not durable custody: OPFS is origin-scoped cache. The durable plane is
    kotobase (`PUT/GET https://kotobase.net/ipld/:cid`, ADR-2608159100).
    publish! is an explicit op, never automatic.

  ## Verification

  A real-browser E2E (headless Chromium via Playwright, the
  `wasm-webcomponent/test/browser` harness pattern) instantiates the Worker
  from a served page, writes a file through `kuro.fs` with this store, reads
  it back, publishes to the gateway stub, and re-reads from a cold cache.
  `node_test.cljs` covers the pure parts that survive Node (the request/
  reply correlation and CID math via node:crypto parity fixture).")

(def format-version 1)

(def worker-source-file
  "The Worker script this host expects. Generated (not hand-written) from
  src/kuro/host/opfs_worker.js — see opfs/README.md. Keeping the name here
  means the E2E and the page glue cannot drift apart silently."
  "kuro-opfs-worker.js")

(defn request
  "Build a main->Worker request message. Pure (shared by page glue, Worker
  dispatcher, and tests so the wire shape cannot drift)."
  [id op payload]
  {:kuro.opfs/type :request
   :kuro.opfs/id id
   :kuro.opfs/op op
   :kuro.opfs/payload payload})

(defn reply
  "Build a Worker->main reply message. `result` is the op result on success;
  on failure `:kuro.opfs/error` carries a keyword reason (never a string from
  the browser — host errors are mapped to keywords by the Worker)."
  [id op result error]
  {:kuro.opfs/type :reply
   :kuro.opfs/id id
   :kuro.opfs/op op
   :kuro.opfs/result result
   :kuro.opfs/error error})

(def ops
  "The closed op vocabulary. Anything else is refused by the Worker (and
  reported as :unknown-op, not ignored — a silent no-op would corrupt the
  request/reply correlation)."
  #{:put :get :delete :publish :stats :drop-cache})

(defn valid-request?
  "Shape check for an incoming request. The Worker refuses malformed messages
  rather than guessing."
  [m]
  (and (map? m)
       (= :request (:kuro.opfs/type m))
       (int? (:kuro.opfs/id m))
       (contains? ops (:kuro.opfs/op m))
       (map? (:kuro.opfs/payload m))))
