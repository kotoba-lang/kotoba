(ns linkedin.client
  "LinkedIn Posts API — portable `.cljc`.

  I/O is injected (`:http-fn` / `:json-write` / `:json-read` / `:creds`), the
  same DI shape as `kotoba-lang/com-x` and `kotoba-lang/com-youtube`.

  ## Three headers that are not optional

  LinkedIn's REST surface is versioned per-request, not per-URL:

    LinkedIn-Version: YYYYMM        pins the API version
    X-Restli-Protocol-Version: 2.0.0
    Authorization: Bearer ...

  Omitting either of the first two gets a 426 or a 400 that reads like an auth
  problem, so `headers` always sends them and `:linkedin-version` is a required
  credential rather than a default this library silently picks — a client that
  chooses the version for you breaks on LinkedIn's schedule, not yours.

  ## The post id is in a header

  `POST /rest/posts` returns 201 with an empty body; the URN is in the
  `x-restli-id` response header. Reading the body gets you nothing and looks
  like a silent failure."
  (:require [kotoba.lang.text :as str]))

(def default-base-url "https://api.linkedin.com")

(defn- url [{:keys [base-url]} path]
  (str (or base-url default-base-url) path))

(defn headers
  [{:keys [access-token linkedin-version]}]
  (when (str/blank? (str linkedin-version))
    (throw (ex-info "linkedin: :linkedin-version is required (e.g. \"202506\")"
                    {:stage :headers})))
  {"Authorization" (str "Bearer " access-token)
   "LinkedIn-Version" (str linkedin-version)
   "X-Restli-Protocol-Version" "2.0.0"
   "Content-Type" "application/json"})

(defn- check!
  [{:keys [status body] :as resp} stage]
  (when-not (<= 200 (or status 0) 299)
    (throw (ex-info (str "linkedin " (name stage) " failed")
                    {:stage stage :status status :body body})))
  resp)

(defn- byte-count
  "Length of a payload that may be a Clojure collection or a native byte
  container. `count` alone is wrong on the ClojureScript side: a Uint8Array
  implements no ICounted, so it throws rather than returning a length — and a
  byte length is exactly what these Content-Length / Content-Range headers need."
  [b]
  #?(:clj (if (bytes? b) (alength ^bytes b) (count b))
     :cljs (or (.-length b) (.-byteLength b) (count b))))

(defn- header-value
  "Response headers arrive with inconsistent case across HTTP clients, so look
  the name up case-insensitively rather than trusting one spelling."
  [resp name*]
  (let [hs (or (:response-headers resp) (:headers resp))
        target (str/lower name*)]
    (some (fn [[k v]] (when (= target (str/lower (name k))) v)) hs)))

(defn create-post!
  "POST /rest/posts. Returns the post URN, read from the `x-restli-id` header.

  `author` is a URN — `urn:li:person:{id}` or `urn:li:organization:{id}`.
  `commentary` is the whole text; LinkedIn has no separate title field.
  `content` is optional and describes attached media, e.g.
  `{:media {:id \"urn:li:image:...\" :title \"...\"}}`."
  [{:keys [http-fn json-write creds] :as io}
   {:keys [author commentary visibility content]
    :or {visibility "PUBLIC"}}]
  (let [resp (-> (http-fn {:url (url io "/rest/posts")
                           :method :post
                           :headers (headers creds)
                           :body (json-write
                                  (cond-> {:author author
                                           :commentary commentary
                                           :visibility visibility
                                           :distribution
                                           {:feedDistribution "MAIN_FEED"
                                            :targetEntities []
                                            :thirdPartyDistributionChannels []}
                                           :lifecycleState "PUBLISHED"
                                           :isReshareDisabledByAuthor false}
                                    content (assoc :content content)))})
                 (check! :create-post))]
    (or (header-value resp "x-restli-id")
        (throw (ex-info "linkedin: post created but no x-restli-id header"
                        {:stage :create-post :status (:status resp)})))))

(defn initialize-image-upload!
  "POST /rest/images?action=initializeUpload.

  Returns {:upload-url .. :image-urn ..}. The URN is what a later
  `create-post!` references in `:content`; the URL takes the bytes."
  [{:keys [http-fn json-write json-read creds] :as io} owner-urn]
  (let [data (-> (http-fn {:url (url io "/rest/images?action=initializeUpload")
                           :method :post
                           :headers (headers creds)
                           :body (json-write {:initializeUploadRequest
                                              {:owner owner-urn}})})
                 (check! :init-image-upload)
                 :body
                 json-read
                 (get "value"))]
    {:upload-url (get data "uploadUrl")
     :image-urn (get data "image")}))

(defn initialize-video-upload!
  "POST /rest/videos?action=initializeUpload.

  Returns {:upload-instructions [..] :video-urn .. :upload-token ..}. Video is
  chunked: LinkedIn hands back one instruction per byte range, and each PUT's
  ETag must be collected and echoed back to `finalize-video-upload!`."
  [{:keys [http-fn json-write json-read creds] :as io} owner-urn file-size-bytes]
  (let [data (-> (http-fn {:url (url io "/rest/videos?action=initializeUpload")
                           :method :post
                           :headers (headers creds)
                           :body (json-write {:initializeUploadRequest
                                              {:owner owner-urn
                                               :fileSizeBytes file-size-bytes
                                               :uploadCaptions false
                                               :uploadThumbnail false}})})
                 (check! :init-video-upload)
                 :body
                 json-read
                 (get "value"))]
    {:video-urn (get data "video")
     :upload-token (get data "uploadToken")
     :upload-instructions (get data "uploadInstructions")}))

(defn upload-bytes!
  "PUT bytes to an upload URL. Returns the ETag, which video finalization needs.

  Note this call is deliberately *not* sent with `headers` — the upload URL is
  pre-signed and adding an Authorization header makes some CDNs reject it."
  [{:keys [http-fn]} upload-url bytes {:keys [mime] :or {mime "application/octet-stream"}}]
  (let [resp (-> (http-fn {:url upload-url
                           :method :put
                           :headers {"Content-Type" mime
                                     "Content-Length" (str (byte-count bytes))}
                           :body bytes})
                 (check! :upload-bytes))]
    (header-value resp "etag")))

(defn finalize-video-upload!
  "POST /rest/videos?action=finalizeUpload with the ETags from each chunk PUT,
  in the order the instructions were given. Out-of-order ETags fail."
  [{:keys [http-fn json-write creds] :as io} {:keys [video-urn upload-token etags]}]
  (-> (http-fn {:url (url io "/rest/videos?action=finalizeUpload")
                :method :post
                :headers (headers creds)
                :body (json-write {:finalizeUploadRequest
                                   {:video video-urn
                                    :uploadToken (or upload-token "")
                                    :uploadedPartIds (vec etags)}})})
      (check! :finalize-video-upload))
  video-urn)
