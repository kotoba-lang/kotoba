(ns kotobase.protocols.git
  "git.kotobase.net — git dumb-HTTP READ surface over kotobase
  (ADR-2607171700).

  DIRECTION GUARD: ADR-2607072300 (actor public data) stands — a git
  journal in the actor's own repo stays the primary source and
  kotobase a derived index. This namespace is the other, non-competing
  concern: kotobase acting as an object/ref STORE that can serve git's
  dumb HTTP protocol for repos whose objects were pushed into it (via
  the library fns below, gated upstream by kotoba-rad signing —
  identity/authorization only, per ADR-2607072200).

  Mapping:
    refs    → IStore collection [:kotobase.git/refs <repo>]   refname → sha
    objects → IStore collection [:kotobase.git/objects <repo>] sha → bytes
    HEAD    → refs doc under key \"HEAD\", value \"ref: refs/heads/<b>\"

  Dumb-HTTP endpoints (read-only; git clients can fetch over this):
    GET /{org}/{repo}/info/refs               \"<sha>\\t<refname>\\n\" lines
    GET /{org}/{repo}/HEAD                    symref line
    GET /{org}/{repo}/objects/{2-hex}/{38-hex} loose object bytes

  v0.1 stores loose-object bytes as opaque strings supplied by the
  writer and does NOT verify sha1(bytes) == key; verification and the
  smart protocol (upload-pack) are declared follow-ups in the ADR."
  (:require [kotoba.lang.text :as str]
            [kotobase.protocols.http :as http]
            [kotobase.store :as st]))

(defn refs-coll [repo] [:kotobase.git/refs repo])
(defn objects-coll [repo] [:kotobase.git/objects repo])

;; ------------------------------------------------------------ write (library)

(defn put-object!
  "Store loose-object `bytes` for `sha` (40 hex chars) in `repo`."
  [store repo sha bytes]
  {:pre [(re-matches #"[0-9a-f]{40}" sha)]}
  (st/-put store (objects-coll repo) sha bytes)
  (st/-append store :kotobase.protocols/audit
              {:surface :git :op :put-object :repo repo :sha sha})
  sha)

(defn set-ref!
  "Point `refname` (e.g. \"refs/heads/main\") at `sha` in `repo`."
  [store repo refname sha]
  (st/-put store (refs-coll repo) refname sha)
  (st/-append store :kotobase.protocols/audit
              {:surface :git :op :set-ref :repo repo :ref refname :sha sha})
  sha)

(defn set-head!
  "Make HEAD a symref to `branch-ref` (e.g. \"refs/heads/main\")."
  [store repo branch-ref]
  (st/-put store (refs-coll repo) "HEAD" (str "ref: " branch-ref)))

;; -------------------------------------------------------------- read (HTTP)

(defn- info-refs [store repo]
  (let [refnames (->> (st/-list store (refs-coll repo))
                      (remove #(= "HEAD" %))
                      sort)]
    (if (empty? refnames)
      (http/not-found (str "repository not found: " repo))
      (http/text 200
                 (apply str
                        (for [r refnames]
                          (str (st/-get store (refs-coll repo) r) "\t" r "\n")))))))

(defn- head-line [store repo]
  (if-let [h (st/-get store (refs-coll repo) "HEAD")]
    (http/text 200 (str h "\n"))
    (http/not-found (str "repository not found: " repo))))

(defn- loose-object [store repo d2 d38]
  (let [sha (str d2 d38)
        stored (st/-get store (objects-coll repo) sha)]
    (cond
      (nil? stored) (http/not-found (str "object not found: " sha))
      ;; base64-marked objects (real zlib loose objects seeded over HTTP)
      ;; carry :body-encoding so the deploy shell decodes them back to
      ;; raw bytes for git clients.
      (map? stored) (assoc (http/response 200
                                          {"content-type" "application/x-git-loose-object"}
                                          (:b64 stored))
                           :body-encoding :base64)
      :else (http/response 200 {"content-type" "application/x-git-loose-object"} stored))))

(defn- base64-body? [req] (= "base64" (http/header req "x-kotobase-body")))

(defn- object-path?
  "[… \"objects\" \"aa\" \"38hex\"] tail?"
  [segs n]
  (and (>= n 4) (= "objects" (segs (- n 3)))
       (re-matches #"[0-9a-f]{2}" (segs (- n 2)))
       (re-matches #"[0-9a-f]{38}" (segs (- n 1)))))

(defn- handle-get [store segs n]
  (cond
    (and (>= n 3) (= ["info" "refs"] (subvec segs (- n 2))))
    (info-refs store (str/join "/" (subvec segs 0 (- n 2))))

    (and (>= n 2) (= "HEAD" (peek segs)))
    (head-line store (str/join "/" (subvec segs 0 (dec n))))

    ;; dumb-transport clients probe these; empty 200 keeps them on the
    ;; loose-object path (this surface serves no packs).
    (and (>= n 4) (= ["objects" "info" "packs"] (subvec segs (- n 3))))
    (http/text 200 "")
    (and (>= n 4) (= ["objects" "info" "alternates"] (subvec segs (- n 3))))
    (http/text 200 "")

    (object-path? segs n)
    (loose-object store
                  (str/join "/" (subvec segs 0 (- n 3)))
                  (segs (- n 2)) (segs (- n 1)))

    :else (http/not-found)))

(defn- handle-put
  "HTTP write surface (the deploy shell's write auth gates every PUT).
  Bodies with header `x-kotobase-body: base64` are stored as
  {:b64 …} and served back with :body-encoding :base64."
  [store req segs n]
  (let [body (:body req)]
    (cond
      ;; The repo's OWN top-level HEAD symref — NOT any ref whose NAME
      ;; happens to end in \"HEAD\" (e.g. refs/remotes/origin/HEAD, a
      ;; real 40-hex-sha-valued ref some git checkouts carry). Guarding
      ;; on \"no 'refs' segment anywhere in the path\" tells the two
      ;; apart; without it this branch swallowed refs/…/HEAD writes and
      ;; rejected their sha body as an invalid symref line (found live
      ;; seeding a real repo's for-each-ref output, ADR-2607177500).
      (and (>= n 2) (= "HEAD" (peek segs)) (not-any? #(= "refs" %) segs))
      (let [repo (str/join "/" (subvec segs 0 (dec n)))]
        (if (and body (str/starts-with? body "ref: refs/"))
          (do (st/-put store (refs-coll repo) "HEAD" (str/trim body))
              (http/text 200 "ok"))
          (http/text 400 "HEAD body must be a 'ref: refs/…' symref line")))

      (object-path? segs n)
      (let [repo (str/join "/" (subvec segs 0 (- n 3)))
            sha (str (segs (- n 2)) (segs (- n 1)))]
        (if (seq body)
          (do (st/-put store (objects-coll repo) sha
                       (if (base64-body? req) {:b64 body} body))
              (st/-append store :kotobase.protocols/audit
                          {:surface :git :op :put-object :repo repo :sha sha})
              (http/text 200 sha))
          (http/text 400 "empty object body")))

      ;; PUT /{repo}/refs/… — refname = the path tail from its "refs"
      ;; segment on, body = 40-hex sha it should point at.
      :else
      (if-let [i (first (keep-indexed
                         (fn [i s] (when (and (pos? i) (= "refs" s)) i)) segs))]
        (let [repo (str/join "/" (subvec segs 0 i))
              refname (str/join "/" (subvec segs i))
              sha (some-> body str/trim)]
          (if (and sha (re-matches #"[0-9a-f]{40}" sha))
            (do (set-ref! store repo refname sha)
                (http/text 200 sha))
            (http/text 400 "ref body must be a 40-hex sha")))
        (http/not-found)))))

(defn handle
  "git dumb-HTTP handler: GET serves clone/fetch, PUT seeds
  refs/objects/HEAD. Repo path = every segment before the protocol
  suffix, joined with '/', so org/repo nesting works."
  [{:keys [store]} req]
  (let [segs (http/segments (:path req))
        n (count segs)]
    (case (:method req)
      :get (handle-get store segs n)
      :put (handle-put store req segs n)
      (http/method-not-allowed))))
