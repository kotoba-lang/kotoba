(ns vimeo-upload.client
  "Vimeo video upload (tus resumable) — portable `.cljc`.

  I/O is injected (`:http-fn` / `:json-write` / `:json-read` / `:creds`), the
  same DI shape as `kotoba-lang/com-x` and `kotoba-lang/com-youtube`.

  ## Why this is not in kotoba-lang/com-vimeo

  That repository is a *clean-room, API-compatible actor* — it answers Vimeo's
  shape, it does not call Vimeo. Putting a real outbound client inside it would
  mean one repository both serving and consuming the same API, and the honest
  name for the thing that uploads is a separate one. Hence the role suffix, per
  the workspace's naming rule for when the short name is taken.

  ## tus, in three moves

    POST /me/videos {upload:{approach:\"tus\", size:N}}  -> upload_link
    PATCH <upload_link>  (Upload-Offset, offset+octet-stream)  -> new offset
    HEAD  <upload_link>  -> current offset, to resume after a failure

  The resumability is the point: a 2 GB upload that dies at 80% resumes from
  `upload-offset` instead of starting over. `upload-file!` does the whole loop,
  but every step is exposed because resuming is a caller-side decision.

  Vimeo's API is versioned through Accept, not the URL — `application/vnd.vimeo.*+json;version=3.4`."
  (:require [kotoba.lang.text :as str]))

(def default-base-url "https://api.vimeo.com")
(def default-api-version "3.4")
(def tus-version "1.0.0")

(defn- url [{:keys [base-url]} path]
  (str (or base-url default-base-url) path))

(defn- api-headers
  [{:keys [access-token api-version]}]
  {"Authorization" (str "bearer " access-token)
   "Accept" (str "application/vnd.vimeo.*+json;version="
                 (or api-version default-api-version))
   "Content-Type" "application/json"})

(defn- check!
  [{:keys [status body] :as resp} stage]
  (when-not (<= 200 (or status 0) 299)
    (throw (ex-info (str "vimeo " (name stage) " failed")
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
  [resp name*]
  (let [hs (or (:response-headers resp) (:headers resp))
        target (str/lower name*)]
    (some (fn [[k v]] (when (= target (str/lower (name k))) v)) hs)))

(defn create-video!
  "POST /me/videos. Returns {:uri \"/videos/123\" :upload-link .. :link ..}.

  `size` is the exact byte count and is not negotiable — tus allocates against
  it, and a mismatch fails at the end of the upload rather than the start."
  [{:keys [http-fn json-write json-read creds] :as io}
   {:keys [name description size privacy-view]
    :or {privacy-view "anybody"}}]
  (let [body (-> (http-fn {:url (url io "/me/videos")
                           :method :post
                           :headers (api-headers creds)
                           :body (json-write
                                  {:upload {:approach "tus" :size size}
                                   :name name
                                   :description description
                                   :privacy {:view privacy-view}})})
                 (check! :create-video)
                 :body
                 json-read)]
    {:uri (get body "uri")
     :link (get body "link")
     :upload-link (get-in body ["upload" "upload_link"])}))

(defn upload-offset
  "HEAD the tus upload link. Returns how many bytes the server already has —
  the number to resume from."
  [{:keys [http-fn creds]} upload-link]
  (let [resp (-> (http-fn {:url upload-link
                           :method :head
                           :headers {"Tus-Resumable" tus-version
                                     "Accept" (str "application/vnd.vimeo.*+json;version="
                                                   (or (:api-version creds)
                                                       default-api-version))}})
                 (check! :upload-offset))]
    (some-> (header-value resp "upload-offset") str str/trim
            #?(:clj Long/parseLong :cljs js/parseInt))))

(defn upload-chunk!
  "PATCH bytes at `offset`. Returns the server's new offset.

  `Content-Type: application/offset+octet-stream` and `Upload-Offset` are both
  mandatory in tus; without them the server answers 415 or 409, neither of which
  mentions the missing header."
  [{:keys [http-fn]} upload-link bytes offset]
  (let [resp (-> (http-fn {:url upload-link
                           :method :patch
                           :headers {"Tus-Resumable" tus-version
                                     "Upload-Offset" (str offset)
                                     "Content-Type" "application/offset+octet-stream"
                                     "Content-Length" (str (byte-count bytes))}
                           :body bytes})
                 (check! :upload-chunk))]
    (some-> (header-value resp "upload-offset") str str/trim
            #?(:clj Long/parseLong :cljs js/parseInt))))

(defn update-video!
  "PATCH /videos/{id} — set metadata after (or before) the bytes land.

  Separate from `create-video!` because a title fix should not require
  re-uploading, and because tus lets metadata and bytes proceed independently."
  [{:keys [http-fn json-write json-read creds] :as io} video-uri params]
  (-> (http-fn {:url (url io video-uri)
                :method :patch
                :headers (api-headers creds)
                :body (json-write params)})
      (check! :update-video)
      :body
      json-read))

(defn upload-file!
  "Create, then push `bytes` in chunks until the server's offset reaches the end.

  Returns the create-video! result. Loops on the *server's* reported offset
  rather than a local counter, which is what makes a resumed upload correct
  instead of merely restarted."
  [io {:keys [size] :as video} bytes {:keys [chunk-size] :or {chunk-size 52428800}}]
  (let [{:keys [upload-link] :as created} (create-video! io video)]
    (loop [offset (or (upload-offset io upload-link) 0)]
      (if (>= offset size)
        created
        (let [end (min size (+ offset chunk-size))
              chunk #?(:clj (java.util.Arrays/copyOfRange ^bytes bytes
                                                          (int offset) (int end))
                       :cljs (.slice bytes offset end))
              next-offset (upload-chunk! io upload-link chunk offset)]
          (when (or (nil? next-offset) (<= next-offset offset))
            (throw (ex-info "vimeo upload made no progress"
                            {:stage :upload-file :offset offset
                             :server-offset next-offset})))
          (recur next-offset))))))
