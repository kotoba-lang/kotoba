(ns haishin.target
  "Per-platform adaptation: canonical artifact -> a request *description*.

  All six targets live in one namespace deliberately. Each builder is a dozen
  lines whose entire content is 'how does this platform differ from the others',
  and that is far easier to audit side by side than spread across six files.

  ## What a request description is, and what it is not

  A request description says *what* to send: an endpoint id, a body map, which
  media to attach. It is data, it is pure, and it performs no I/O. This library
  contains no HTTP client and no credential handling anywhere — it physically
  cannot post on its own. Turning a description into an effect is the caller's
  job (see `haishin.execute`), which is what lets an existing, separately tested
  client such as `kotoba-lang/com-youtube` own the transport protocol while this
  namespace owns only the cross-platform mapping.

  That split is why the endpoint ids below are named after the vendor operation
  (`:youtube/videos-insert`) rather than a URL: the sender knows the URL, we
  only have to agree on which operation we mean."
  (:require [kotoba.lang.text :as str]
            [haishin.artifact :as artifact]
            [haishin.constraints :as constraints]))

;; ---------------------------------------------------------------------------
;; shared text composition

;; `\p{L}`/`\p{N}` are Unicode property escapes. On the JVM they work in a plain
;; pattern; in JavaScript they are inert without the `u` flag — a literal
;; `#"[^\p{L}\p{N}_]"` there silently matches almost everything and strips the
;; whole tag. Since tags in this workspace are routinely Japanese, that failure
;; would have been total rather than partial. Hence the explicit RegExp with
;; "gu" on the ClojureScript side.
(def ^:private non-tag-char
  #?(:clj #"[^\p{L}\p{N}_]"
     :cljs (js/RegExp. "[^\\p{L}\\p{N}_]" "gu")))

(def ^:private hashtag-re
  #?(:clj #"#[\p{L}\p{N}_]+"
     :cljs (js/RegExp. "#[\\p{L}\\p{N}_]+" "gu")))

(defn hashtag
  "Tag -> platform hashtag. Non-alphanumerics are dropped rather than replaced,
  because every platform treats punctuation as a tag terminator."
  [tag]
  (str "#" #?(:clj (str/replace (str tag) non-tag-char "")
              :cljs (.replace (str tag) non-tag-char ""))))

(defn compose-text
  "Fold an artifact into one text blob, for platforms with a single text field.

  Order is title, body, attribution link, hashtags — attribution before tags so
  the link survives if a human later trims the tail. Sections that are empty
  are omitted entirely rather than leaving blank lines."
  [artifact {:keys [tags? attribution?] :or {tags? true attribution? true}}]
  (let [{:artifact/keys [title body tags]} artifact
        link (when attribution? (artifact/attribution-url artifact))
        sections (cond-> []
                   (not (str/blank? title)) (conj (str/trim title))
                   (not (str/blank? body)) (conj (str/trim body))
                   (not (str/blank? link)) (conj link)
                   (and tags? (seq tags)) (conj (str/join " " (map hashtag tags))))]
    (str/join "\n\n" sections)))

(defn- count-hashtags
  [text]
  #?(:clj (count (re-seq hashtag-re text))
     :cljs (count (or (.match text hashtag-re) []))))

;; ---------------------------------------------------------------------------
;; target-side validation

(defn problems
  "Can this target accept this artifact? Returns [] when it can.

  Separate from `haishin.artifact/problems`, which asks only whether the
  artifact is well formed at all. An artifact can be perfectly valid and still
  be rejected here — a 4-minute video is a fine artifact and not a valid X post."
  [target-id artifact {:keys [body-chars-override] :as opts}]
  (let [c (constraints/constraint target-id)]
    (if-not c
      [{:problem/kind :target/unknown
        :problem/target target-id
        :problem/message (str "no such target: " (pr-str target-id))}]
      (let [{:artifact/keys [kind media]} artifact
            limit-body (or body-chars-override (:limit/body-chars c))
            text (compose-text artifact opts)
            mimes (:media/mimes c)
            bad-mime (remove #(contains? mimes (:media/mime %)) media)]
        (cond-> []
          (not (contains? (:target/kinds c) kind))
          (conj {:problem/kind :target/kind-unsupported
                 :problem/target target-id
                 :problem/message (str (:target/label c) " does not accept " kind
                                       " (accepts " (pr-str (:target/kinds c)) ")")})

          (> (count text) limit-body)
          (conj {:problem/kind :target/text-too-long
                 :problem/target target-id
                 :problem/actual (count text)
                 :problem/limit limit-body
                 :problem/message (str (:target/label c) " text is " (count text)
                                       " chars, limit " limit-body)})

          (> (count media) (:limit/media-count c))
          (conj {:problem/kind :target/too-many-media
                 :problem/target target-id
                 :problem/actual (count media)
                 :problem/limit (:limit/media-count c)
                 :problem/message (str (:target/label c) " accepts at most "
                                       (:limit/media-count c) " media")})

          (seq bad-mime)
          (conj {:problem/kind :target/mime-unsupported
                 :problem/target target-id
                 :problem/actual (mapv :media/mime bad-mime)
                 :problem/message (str (:target/label c) " does not accept "
                                       (str/join ", " (map :media/mime bad-mime)))})

          (and (:limit/hashtags c) (> (count-hashtags text) (:limit/hashtags c)))
          (conj {:problem/kind :target/too-many-hashtags
                 :problem/target target-id
                 :problem/actual (count-hashtags text)
                 :problem/limit (:limit/hashtags c)
                 :problem/message (str (:target/label c) " allows at most "
                                       (:limit/hashtags c) " hashtags")}))))))

(defn warnings
  "Soft findings. These never block a send — they ride along on the plan entry
  so a human reviewing the plan can see them."
  [target-id artifact]
  (let [c (constraints/constraint target-id)
        m (artifact/primary-media artifact)]
    (cond-> []
      (and (:media/requires-public-url c) (some? m))
      (conj {:warning/kind :target/pulls-from-url
             :warning/target target-id
             :warning/message (str (:target/label c)
                                   " fetches the asset from :media/url — it must be"
                                   " publicly reachable before this post is created")})

      (and (:prefer/vertical? c) (:media/width m) (:media/height m)
           (>= (:media/width m) (:media/height m)))
      (conj {:warning/kind :target/not-vertical
             :warning/target target-id
             :warning/message (str (:target/label c) " favours vertical media; this is "
                                   (:media/width m) "x" (:media/height m))})

      (and (:prefer/max-duration-ms c) (:media/duration-ms m)
           (> (:media/duration-ms m) (:prefer/max-duration-ms c)))
      (conj {:warning/kind :target/over-preferred-duration
             :warning/target target-id
             :warning/message (str (:media/duration-ms m) "ms exceeds "
                                   (:prefer/max-duration-ms c)
                                   "ms; will publish but lose short-form placement")})

      (= :unverified (:constraint/provenance c))
      (conj {:warning/kind :target/limits-unverified
             :warning/target target-id
             :warning/message (str (:target/label c) " limits are :unverified (checked-at "
                                   (:constraint/checked-at c)
                                   ") — confirm against vendor docs before live use")}))))

;; ---------------------------------------------------------------------------
;; request builders

(defmulti request
  "artifact + opts -> {:request/endpoint .. :request/body .. :request/media ..}.
  Pure. Dispatches on target id."
  (fn [target-id _artifact _opts] target-id))

(defmethod request :default
  [target-id _ _]
  (throw (ex-info (str "haishin: no request builder for target " (pr-str target-id))
                  {:haishin/error :unknown-target :target target-id})))

(defn- privacy->youtube [v] (case v :public "public" :unlisted "unlisted" :private "private"))

(defmethod request :youtube
  [_ artifact opts]
  (let [{:artifact/keys [title body tags language visibility]} artifact]
    {:request/endpoint :youtube/videos-insert
     ;; Shape matches `youtube.videos/video-metadata` in kotoba-lang/com-youtube
     ;; so the sender can hand it straight over without remapping.
     :request/body {:snippet {:title title
                              :description (compose-text
                                            (assoc artifact :artifact/title "") opts)
                              :tags (vec tags)
                              :defaultLanguage language
                              :defaultAudioLanguage language}
                    :status {:privacyStatus (privacy->youtube visibility)
                             :selfDeclaredMadeForKids false
                             :embeddable true}}
     :request/media (artifact/primary-media artifact)}))

(defmethod request :instagram
  [_ artifact opts]
  (let [m (artifact/primary-media artifact)]
    {:request/endpoint :instagram/media-create
     :request/body (cond-> {:caption (compose-text artifact opts)}
                     (= :video (:artifact/kind artifact))
                     (assoc :media_type "REELS" :video_url (:media/url m))

                     (= :image (:artifact/kind artifact))
                     (assoc :image_url (:media/url m)))
     :request/media m
     ;; Instagram is two-phase: create the container, then publish it. Saying so
     ;; here keeps the sender from having to know it out of band.
     :request/follow-up :instagram/media-publish}))

(defmethod request :tiktok
  [_ artifact opts]
  (let [m (artifact/primary-media artifact)]
    {:request/endpoint :tiktok/video-init
     :request/body {:post_info {:title (compose-text artifact opts)
                                :privacy_level (case (:artifact/visibility artifact)
                                                 :public "PUBLIC_TO_EVERYONE"
                                                 :unlisted "MUTUAL_FOLLOW_FRIENDS"
                                                 :private "SELF_ONLY")}
                    :source_info {:source "PULL_FROM_URL"
                                  :video_url (:media/url m)}}
     :request/media m}))

(defmethod request :x
  [_ artifact opts]
  {:request/endpoint :x/posts-create
   :request/body {:text (compose-text artifact opts)}
   :request/media (vec (:artifact/media artifact))})

(defmethod request :vimeo
  [_ artifact opts]
  (let [m (artifact/primary-media artifact)]
    {:request/endpoint :vimeo/videos-create
     :request/body {:name (:artifact/title artifact)
                    :description (compose-text
                                  (assoc artifact :artifact/title "") opts)
                    :privacy {:view (case (:artifact/visibility artifact)
                                      :public "anybody"
                                      :unlisted "unlisted"
                                      :private "nobody")}
                    :upload {:approach "tus" :size (:media/bytes m)}}
     :request/media m}))

(defmethod request :linkedin
  [_ artifact opts]
  {:request/endpoint :linkedin/posts-create
   :request/body {:commentary (compose-text artifact opts)
                  :visibility (if (= :private (:artifact/visibility artifact))
                                "CONNECTIONS" "PUBLIC")
                  :distribution {:feedDistribution "MAIN_FEED"}
                  :lifecycleState "PUBLISHED"}
   :request/media (artifact/primary-media artifact)})
