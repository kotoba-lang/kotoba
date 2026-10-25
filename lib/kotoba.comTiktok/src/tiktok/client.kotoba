(ns tiktok.client
  "TikTok Content Posting API — portable `.cljc`.

  I/O is injected (`:http-fn` / `:json-write` / `:json-read` / `:creds`), the
  same DI shape as `kotoba-lang/com-x` and `kotoba-lang/com-youtube`.

  ## Two source modes, and why both are here

  `PULL_FROM_URL` hands TikTok a URL and lets it fetch — one call, but the URL's
  domain must be verified with TikTok first, so it is not available to everyone.
  `FILE_UPLOAD` returns an upload URL and takes the bytes directly, which works
  without domain verification but is a three-step flow. Neither is a superset of
  the other, so a client that only implemented one would be unusable for half
  its callers.

  ## Init does not mean posted

  Both modes return a `publish_id` immediately and finish asynchronously. A
  caller that treats a successful init as a successful post will report
  publishes that never appeared. `publish-status` is how you find out, and
  `await-publish` sequences the polling with an injected `:sleep-fn`."
  (:require [kotoba.lang.text :as str]))

(def default-base-url "https://open.tiktokapis.com")

(def privacy-levels
  "TikTok rejects an unknown value rather than defaulting, so the accepted set
  is worth stating. `SELF_ONLY` is the safe choice for a first live test."
  #{"PUBLIC_TO_EVERYONE" "MUTUAL_FOLLOW_FRIENDS" "FOLLOWER_OF_CREATOR" "SELF_ONLY"})

(def terminal-statuses
  #{"PUBLISH_COMPLETE" "FAILED"})

(defn- url [{:keys [base-url]} path]
  (str (or base-url default-base-url) path))

(defn- check!
  [{:keys [status body]} stage json-read]
  (let [parsed (try (json-read body)
                    (catch #?(:clj Exception :cljs :default) _ nil))
        err (get parsed "error")
        ;; TikTok answers 200 with {"error":{"code":"..."}} for application-level
        ;; failures, so HTTP status alone is not a success test.
        failed? (or (not (<= 200 (or status 0) 299))
                    (and err (not= "ok" (get err "code"))))]
    (when failed?
      (throw (ex-info (str "tiktok " (name stage) " failed")
                      {:stage stage :status status :error (or err body)})))
    parsed))

(defn- byte-count
  "Length of a payload that may be a Clojure collection or a native byte
  container. `count` alone is wrong on the ClojureScript side: a Uint8Array
  implements no ICounted, so it throws rather than returning a length — and a
  byte length is exactly what these Content-Length / Content-Range headers need."
  [b]
  #?(:clj (if (bytes? b) (alength ^bytes b) (count b))
     :cljs (or (.-length b) (.-byteLength b) (count b))))

(defn- post!
  [{:keys [http-fn json-write json-read creds] :as io} path payload stage]
  (-> (http-fn {:url (url io path)
                :method :post
                :headers {"Authorization" (str "Bearer " (:access-token creds))
                          "Content-Type" "application/json; charset=UTF-8"}
                :body (json-write payload)})
      (check! stage json-read)))

(defn post-info
  "The `post_info` block shared by both source modes. `title` is the single
  caption field — TikTok has no separate title."
  [{:keys [title privacy-level disable-comment? disable-duet? disable-stitch?]
    :or {privacy-level "SELF_ONLY"}}]
  (when-not (privacy-levels privacy-level)
    (throw (ex-info "tiktok: unknown privacy level"
                    {:privacy-level privacy-level :accepted privacy-levels})))
  {:title title
   :privacy_level privacy-level
   :disable_comment (boolean disable-comment?)
   :disable_duet (boolean disable-duet?)
   :disable_stitch (boolean disable-stitch?)})

(defn init-pull-from-url!
  "POST /v2/post/publish/video/init/ with PULL_FROM_URL. Returns `publish_id`.

  The URL's domain must already be verified in the TikTok developer console;
  an unverified domain fails here rather than at fetch time."
  [io {:keys [video-url] :as opts}]
  (-> (post! io "/v2/post/publish/video/init/"
             {:post_info (post-info opts)
              :source_info {:source "PULL_FROM_URL" :video_url video-url}}
             :init-pull)
      (get-in ["data" "publish_id"])))

(defn init-file-upload!
  "POST /v2/post/publish/video/init/ with FILE_UPLOAD.

  Returns {:publish-id .. :upload-url ..}. `video-size` is the exact byte count
  and `chunk-size` must divide it the way TikTok expects — for a single-chunk
  upload, set both to the file size."
  [io {:keys [video-size chunk-size total-chunk-count] :as opts}]
  (let [data (-> (post! io "/v2/post/publish/video/init/"
                        {:post_info (post-info opts)
                         :source_info {:source "FILE_UPLOAD"
                                       :video_size video-size
                                       :chunk_size (or chunk-size video-size)
                                       :total_chunk_count (or total-chunk-count 1)}}
                        :init-upload)
                 (get "data"))]
    {:publish-id (get data "publish_id")
     :upload-url (get data "upload_url")}))

(defn upload-chunk!
  "PUT the bytes to the URL `init-file-upload!` returned.

  `Content-Range` is mandatory even for a single chunk; TikTok rejects the PUT
  without it."
  [{:keys [http-fn]} upload-url bytes {:keys [offset total mime]
                                       :or {offset 0 mime "video/mp4"}}]
  (let [len (byte-count bytes)
        end (+ offset len -1)
        resp (http-fn {:url upload-url
                       :method :put
                       :headers {"Content-Type" mime
                                 "Content-Length" (str len)
                                 "Content-Range" (str "bytes " offset "-" end
                                                      "/" (or total len))}
                       :body bytes})]
    (when-not (<= 200 (or (:status resp) 0) 299)
      (throw (ex-info "tiktok chunk upload failed"
                      {:stage :upload-chunk :status (:status resp)
                       :range [offset end]})))
    resp))

(defn publish-status
  "POST /v2/post/publish/status/fetch/. Returns the status string."
  [io publish-id]
  (-> (post! io "/v2/post/publish/status/fetch/" {:publish_id publish-id}
             :publish-status)
      (get-in ["data" "status"])))

(defn await-publish
  "Poll until the publish reaches a terminal state. Returns the status.

  Throws on FAILED and on running out of polls — an init that never completed
  is not a publish, and reporting it as one is the failure mode that matters."
  [io publish-id {:keys [sleep-fn poll-interval-ms max-polls]
                  :or {poll-interval-ms 5000 max-polls 24}}]
  (loop [n 0]
    (let [status (publish-status io publish-id)]
      (cond
        (= "PUBLISH_COMPLETE" status) status

        (terminal-statuses status)
        (throw (ex-info "tiktok publish failed"
                        {:stage :await-publish :publish-id publish-id
                         :status status}))

        (>= (inc n) max-polls)
        (throw (ex-info "tiktok publish still not complete"
                        {:stage :await-publish :publish-id publish-id
                         :status status :polls (inc n)}))

        :else (do (when sleep-fn (sleep-fn poll-interval-ms))
                  (recur (inc n)))))))
