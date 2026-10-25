(ns fleet.github
  "The one place the fleet talks to GitHub.

  Three callers needed it and each was about to grow its own: fetching the
  pinned source, landing a signed receipt into the published ledger, and
  pushing an accepted patch as a branch. They also share the same credential
  rule, which is the real reason this is one namespace: **nothing here reads an
  ambient login**. A token is passed in explicitly or the call is anonymous,
  and the caller records which it was, so a receipt can say what authority the
  run actually carried.

  Writes go through the Git Data API (blob → tree → commit → ref) rather than a
  local clone: a server-side commit on a known base has no working tree to get
  dirty, no merge to fight, and fails loudly (409/422) instead of silently
  producing a different history."
  (:require [kotoba.lang.text :as str]
            [fleet.cli :as cli]))

(def api-base "https://api.github.com")

(defn- headers [token]
  (cond-> {"accept" "application/vnd.github+json"
           "x-github-api-version" "2022-11-28"
           "user-agent" "kotoba-fleet"}
    token (assoc "authorization" (str "Bearer " token))))

(defn call
  "One API call. Returns {:status :json :body}; never throws on HTTP status."
  [{:keys [token method path body timeout-sec]}]
  (cli/json-http {:url (str api-base path)
                  :method (or method :get)
                  :headers (headers token)
                  :body (when body (js/JSON.stringify (clj->js body)))
                  :timeout-sec (or timeout-sec 60)}))

(defn- ok! [{:keys [status json body] :as resp} what]
  (if (#{200 201} status)
    json
    (throw (ex-info (str what " failed: HTTP " status " " (or (:message json) body))
                    {:resp resp}))))

;; ── read ────────────────────────────────────────────────────────────────────

(defn tarball-url
  "codeload URL for an exact commit — no API token needed for a public repo."
  [repo sha]
  (str "https://codeload.github.com/" repo "/tar.gz/" sha))

(defn fetch-tarball!
  "Download the pinned commit to `dest`. `token` may be nil for a public repo.
  Returns {:bytes :path :auth}."
  [{:keys [repo sha dest token]}]
  (let [args (cond-> ["-sS" "--fail" "--location" "--max-time" "300" "-o" dest
                      (tarball-url repo sha)]
               token (concat ["-H" (str "authorization: Bearer " token)]))
        {:keys [exit out]} (cli/sh-status "curl" (vec args))]
    (when-not (zero? exit)
      (throw (ex-info (str "could not fetch " repo "@" sha ": " out) {})))
    {:path dest :auth (if token :token :none)}))

(defn head-sha [{:keys [token repo branch]}]
  (:sha (ok! (call {:token token :path (str "/repos/" repo "/commits/" (or branch "HEAD"))})
             (str "read head of " repo))))

(defn file-at
  "{:text … :sha …} for a file at `ref`, or nil when absent (404 is an answer,
  not an error — an append-only ledger legitimately starts empty)."
  [{:keys [token repo path ref]}]
  (let [{:keys [status json]} (call {:token token
                                     :path (str "/repos/" repo "/contents/" path
                                                "?ref=" (or ref "main"))})]
    (when (= 200 status)
      {:sha (:sha json)
       :text (js/Buffer.from (:content json) "base64")})))

;; ── write ───────────────────────────────────────────────────────────────────

(defn put-file!
  "Create or update ONE file via the contents API, optimistic-locked on
  `base-sha` (nil to create). A stale base 409s instead of overwriting, which
  is what makes concurrent appenders safe without a lock."
  [{:keys [token repo path branch message content base-sha]}]
  (ok! (call {:token token :method :put
              :path (str "/repos/" repo "/contents/" path)
              :body (cond-> {:message message
                             :content (.toString (js/Buffer.from content "utf8") "base64")
                             :branch (or branch "main")}
                      base-sha (assoc :sha base-sha))})
       (str "put " path)))

(defn commit-tree!
  "Server-side commit of `files` ({path → content}) on top of `base-sha`, and
  point `branch` at it. Creates the branch when it does not exist.
  Returns the new commit sha."
  [{:keys [token repo base-sha branch files message]}]
  (let [base-commit (ok! (call {:token token :path (str "/repos/" repo "/git/commits/" base-sha)})
                         "read base commit")
        blobs (mapv (fn [[path content]]
                      {:path path :mode "100644" :type "blob"
                       :sha (:sha (ok! (call {:token token :method :post
                                              :path (str "/repos/" repo "/git/blobs")
                                              :body {:content content :encoding "utf-8"}})
                                       (str "create blob for " path)))})
                    files)
        tree (ok! (call {:token token :method :post
                         :path (str "/repos/" repo "/git/trees")
                         :body {:base_tree (get-in base-commit [:tree :sha]) :tree blobs}})
                  "create tree")
        commit (ok! (call {:token token :method :post
                           :path (str "/repos/" repo "/git/commits")
                           :body {:message message :tree (:sha tree) :parents [base-sha]}})
                    "create commit")
        ref (str "refs/heads/" branch)
        existing (call {:token token :path (str "/repos/" repo "/git/ref/heads/" branch)})]
    (if (= 200 (:status existing))
      (ok! (call {:token token :method :patch
                  :path (str "/repos/" repo "/git/refs/heads/" branch)
                  :body {:sha (:sha commit) :force false}})
           (str "update " ref))
      (ok! (call {:token token :method :post
                  :path (str "/repos/" repo "/git/refs")
                  :body {:ref ref :sha (:sha commit)}})
           (str "create " ref)))
    (:sha commit)))

(defn open-pr!
  [{:keys [token repo head base title body]}]
  (let [{:keys [status json]} (call {:token token :method :post
                                     :path (str "/repos/" repo "/pulls")
                                     :body {:head head :base (or base "main")
                                            :title title :body body}})]
    (cond
      (= 201 status) {:number (:number json) :url (:html_url json)}
      ;; a PR already open for this head is success, not failure
      (and (= 422 status) (str/includes? (str (:errors json)) "already exists"))
      {:existing true}
      :else (throw (ex-info (str "open PR failed: HTTP " status) {:json json})))))

(defn merge-branch!
  "Server-side merge — never a local merge, so there is no working tree to
  conflict and a race just 409s."
  [{:keys [token repo base head message]}]
  (let [{:keys [status json]} (call {:token token :method :post
                                     :path (str "/repos/" repo "/merges")
                                     :body {:base base :head head :commit_message message}})]
    (case status
      201 {:sha (:sha json) :merged true}
      204 {:merged :already-up-to-date}
      409 {:merged false :conflict true}
      (throw (ex-info (str "merge failed: HTTP " status) {:json json})))))
