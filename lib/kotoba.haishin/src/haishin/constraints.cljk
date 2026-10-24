(ns haishin.constraints
  "Per-platform publishing limits, as data.

  These live in code rather than a resource file on purpose: the runtime
  priority in this workspace puts ClojureScript/nbb ahead of the JVM, and
  `slurp`-ing a resource is the one thing that does not port cleanly across
  those. A plain map ports everywhere.

  ## Provenance is part of the data

  Every limit carries `:constraint/checked-at`, `:constraint/source` and
  `:constraint/provenance`. Platform limits drift — a number with no date on it
  is a number nobody can audit. `:constraint/provenance` is honest about how the
  value got here:

    :in-repo-corroborated — an independently written client in this workspace
                            encodes the same number (strongest signal we have
                            offline)
    :vendor-doc           — read off the vendor's published API reference
    :unverified           — recorded from general knowledge and NOT yet checked
                            against the vendor doc

  **Anything still `:unverified` must be checked before that target is used for
  live posting.** `unverified-targets` exists so a caller can assert on it in
  its own test suite rather than discovering the drift in production. The
  library deliberately does not refuse to plan on unverified limits: planning is
  free and offline, and a wrong limit surfaces as a rejection you can read,
  which is more useful than a library that will not run."
  (:require [kotoba.lang.text :as str]))

(def ^:private mp4 #{"video/mp4" "video/quicktime"})
(def ^:private jpeg-png #{"image/jpeg" "image/png"})

(def targets
  "target-id -> constraint map.

  `:limit/*` keys are hard bounds — exceeding one is a rejection.
  `:prefer/*` keys are soft — missing one is a warning on the plan entry.
  `:media/requires-public-url` marks platforms whose API *pulls* the asset from
  a URL we host rather than accepting uploaded bytes. That is a real
  architectural constraint, not a detail: it means the artifact must already be
  publicly reachable before the post can be created at all."
  {:youtube
   {:target/id :youtube
    :target/label "YouTube"
    :target/kinds #{:video}
    :limit/title-chars 100
    :limit/body-chars 5000
    :limit/tags-total-chars 500
    :limit/media-count 1
    :media/mimes mp4
    :media/requires-public-url false
    :prefer/vertical? true
    :prefer/max-duration-ms 180000 ; Shorts eligibility, not an upload limit
    :constraint/source "https://developers.google.com/youtube/v3/docs/videos"
    :constraint/checked-at "2026-08-04"
    ;; kotoba-lang/com-youtube's `youtube.videos/video-metadata` independently
    ;; clamps title/description to exactly 100/5000, ported 1:1 from a working
    ;; Python client. Two independent encodings agreeing is real corroboration.
    :constraint/provenance :in-repo-corroborated}

   :instagram
   {:target/id :instagram
    :target/label "Instagram"
    :target/kinds #{:video :image}
    :limit/title-chars 0 ; Instagram has no title field; title folds into caption
    :limit/body-chars 2200
    :limit/hashtags 30
    :limit/media-count 10
    :media/mimes (into mp4 jpeg-png)
    ;; The Content Publishing API creates a container from `video_url` /
    ;; `image_url`. There is no byte-upload path, so nothing can be posted here
    ;; until the asset is already served publicly.
    :media/requires-public-url true
    :prefer/vertical? true
    :constraint/source "https://developers.facebook.com/docs/instagram-platform/content-publishing"
    :constraint/checked-at "2026-08-04"
    :constraint/provenance :unverified}

   :tiktok
   {:target/id :tiktok
    :target/label "TikTok"
    :target/kinds #{:video}
    :limit/title-chars 0 ; single caption field
    :limit/body-chars 2200
    :limit/media-count 1
    :media/mimes mp4
    :media/requires-public-url false ; FILE_UPLOAD or PULL_FROM_URL both exist
    :prefer/vertical? true
    :constraint/source "https://developers.tiktok.com/doc/content-posting-api-get-started"
    :constraint/checked-at "2026-08-04"
    :constraint/provenance :unverified}

   :x
   {:target/id :x
    :target/label "X"
    :target/kinds #{:text :image :video}
    :limit/title-chars 0 ; single text field
    :limit/body-chars 280
    :limit/media-count 4
    :media/mimes (into mp4 jpeg-png)
    :media/requires-public-url false
    :constraint/source "https://docs.x.com/x-api/posts/creation-of-a-post"
    :constraint/checked-at "2026-08-04"
    ;; 280 is the default-tier limit. Accounts on a higher tier get more; a
    ;; caller on such an account can override via `haishin.plan/plan` opts.
    :constraint/provenance :unverified}

   :vimeo
   {:target/id :vimeo
    :target/label "Vimeo"
    :target/kinds #{:video}
    :limit/title-chars 128
    :limit/body-chars 5000
    :limit/media-count 1
    :media/mimes mp4
    :media/requires-public-url false
    :constraint/source "https://developer.vimeo.com/api/upload/videos"
    :constraint/checked-at "2026-08-04"
    :constraint/provenance :unverified}

   :linkedin
   {:target/id :linkedin
    :target/label "LinkedIn"
    :target/kinds #{:text :image :video}
    :limit/title-chars 0 ; commentary is the single text field
    :limit/body-chars 3000
    :limit/media-count 1
    :media/mimes (into mp4 jpeg-png)
    :media/requires-public-url false
    :constraint/source "https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api"
    :constraint/checked-at "2026-08-04"
    :constraint/provenance :unverified}})

(def target-ids (into (sorted-set) (keys targets)))

(defn constraint
  "Constraints for `target-id`, or nil if this library has no such target."
  [target-id]
  (get targets target-id))

(defn unverified-targets
  "Targets whose limits have not been checked against the vendor documentation.
  Assert on this in your own suite before enabling a target for live posting."
  []
  (into (sorted-set)
        (keep (fn [[id c]]
                (when (= :unverified (:constraint/provenance c)) id))
              targets)))

(defn single-text-field?
  "True when the platform has no separate title — the artifact's title has to be
  folded into the body rather than sent alongside it."
  [target-id]
  (zero? (:limit/title-chars (constraint target-id) 0)))

(defn describe
  "Human-readable one-liner, for CLI output and receipts."
  [target-id]
  (if-let [c (constraint target-id)]
    (str (:target/label c)
         " — kinds " (str/join "/" (sort (map name (:target/kinds c))))
         ", body ≤" (:limit/body-chars c) " chars"
         ", limits checked " (:constraint/checked-at c)
         " (" (name (:constraint/provenance c)) ")")
    (str "unknown target " (pr-str target-id))))
