(ns instagram.client
  "Instagram Content Publishing API (Graph API) — portable `.cljc`.

  I/O is injected (`:http-fn` / `:json-write` / `:json-read` / `:creds`), the
  same DI shape as `kotoba-lang/com-x` and `kotoba-lang/com-youtube`. Nothing
  here reads a token from the environment; a caller closes over its own.

  ## The one thing that surprises people

  There is no byte-upload path. `POST /{ig-user-id}/media` takes a `video_url`
  or `image_url` and Instagram *fetches the asset itself*, which means the
  media must already be publicly reachable before a post can be created at all.
  Publishing is therefore always at least two calls and a wait:

      create container -> poll until FINISHED -> publish

  The wait is real: Instagram transcodes video asynchronously, and publishing a
  container that is still `IN_PROGRESS` fails. `publish-video!` sequences this,
  but takes `:sleep-fn` rather than blocking on its own — a library that owns a
  timer cannot be tested without waiting for one."
  (:require [kotoba.lang.text :as str]))

(def default-base-url "https://graph.facebook.com/v21.0")

(def terminal-statuses
  "Container states that will never change again."
  #{"FINISHED" "ERROR" "EXPIRED"})

(defn- url [{:keys [base-url]} path]
  (str (or base-url default-base-url) path))

(defn- check!
  [{:keys [status body] :as resp} stage json-read]
  (when-not (<= 200 (or status 0) 299)
    (throw (ex-info (str "instagram " (name stage) " failed")
                    {:stage stage
                     :status status
                     ;; Graph API puts the useful part in {"error": {...}};
                     ;; surface it rather than a bare status code.
                     :error (try (get (json-read body) "error")
                                 (catch #?(:clj Exception :cljs :default) _ body))})))
  resp)

(defn- post!
  [{:keys [http-fn json-read creds] :as io} path params stage]
  (let [qs (str/join "&" (for [[k v] params :when (some? v)]
                           (str (name k) "=" v)))]
    (-> (http-fn {:url (str (url io path) "?" qs)
                  :method :post
                  :headers {"Authorization" (str "Bearer " (:access-token creds))}})
        (check! stage json-read)
        :body
        json-read)))

(defn create-container!
  "POST /{ig-user-id}/media. Returns the container id (`creation_id`).

  `media` is one of:
    {:kind :image :image-url \"https://...\"}
    {:kind :reels :video-url \"https://...\" :cover-url \"https://...\"}
  `caption` is the whole text; Instagram has no separate title field."
  [{:keys [creds] :as io} {:keys [kind image-url video-url cover-url caption
                                  share-to-feed?]}]
  (let [params (cond-> {:caption caption}
                 (= :image kind) (assoc :image_url image-url)
                 (= :reels kind) (assoc :media_type "REELS"
                                        :video_url video-url
                                        :share_to_feed (boolean share-to-feed?))
                 cover-url (assoc :cover_url cover-url))]
    (get (post! io (str "/" (:ig-user-id creds) "/media") params :create-container)
         "id")))

(defn container-status
  "GET /{container-id}?fields=status_code. One of QUEUED / IN_PROGRESS /
  FINISHED / ERROR / EXPIRED."
  [{:keys [http-fn json-read creds] :as io} container-id]
  (-> (http-fn {:url (str (url io (str "/" container-id))
                          "?fields=status_code,status")
                :method :get
                :headers {"Authorization" (str "Bearer " (:access-token creds))}})
      (check! :container-status json-read)
      :body
      json-read
      (get "status_code")))

(defn publish-container!
  "POST /{ig-user-id}/media_publish. Returns the published media id."
  [{:keys [creds] :as io} container-id]
  (get (post! io (str "/" (:ig-user-id creds) "/media_publish")
              {:creation_id container-id} :publish)
       "id"))

(defn await-container
  "Poll until the container reaches a terminal state, or `:max-polls` is spent.

  `sleep-fn` is called with milliseconds between polls; pass whatever your
  runtime's delay is. Returns the terminal status string. Throws when the
  container errored or the budget ran out — a silent give-up here would look
  exactly like a successful publish that never happened."
  [io container-id {:keys [sleep-fn poll-interval-ms max-polls]
                    :or {poll-interval-ms 5000 max-polls 24}}]
  (loop [n 0]
    (let [status (container-status io container-id)]
      (cond
        (= "FINISHED" status) status

        (terminal-statuses status)
        (throw (ex-info "instagram container did not finish"
                        {:stage :await-container
                         :container-id container-id
                         :status status}))

        (>= (inc n) max-polls)
        (throw (ex-info "instagram container still not ready"
                        {:stage :await-container
                         :container-id container-id
                         :status status
                         :polls (inc n)}))

        :else (do (when sleep-fn (sleep-fn poll-interval-ms))
                  (recur (inc n)))))))

(defn publish-video!
  "create container -> await FINISHED -> publish. Returns the media id.

  This is the whole flow, and it is a function rather than a documented
  three-step ritual because getting the order wrong fails in a way that reads
  like a permissions problem."
  [io media opts]
  (let [container (create-container! io media)]
    (await-container io container opts)
    (publish-container! io container)))
