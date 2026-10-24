(ns haishin.artifact
  "Canonical, platform-neutral creator artifact.

  Every producer in this workspace (dougaka / mangaka / animeka / ongakuka
  actors, app-aozora entries, cloud-itonami observation posts) normalizes into
  this one shape. Targets never see producer-specific keys, and producers never
  see platform-specific keys — that is the whole point of the boundary.

  Pure: nothing here performs I/O or reads ambient state."
  (:require [kotoba.lang.text :as str]))

(def kinds
  "What an artifact fundamentally *is*. A target declares which kinds it
  accepts; a kind mismatch is a rejection, not a warning."
  #{:video :image :text :audio})

(def visibilities
  "Requested reach. Targets map this onto their own vocabulary (YouTube
  `privacyStatus`, LinkedIn visibility, ...). `:private` means uploaded but not
  discoverable — it is NOT a substitute for not posting at all."
  #{:public :unlisted :private})

(def default-artifact
  {:artifact/kind :text
   :artifact/title ""
   :artifact/body ""
   :artifact/tags []
   :artifact/language "ja"
   :artifact/media []
   :artifact/visibility :public})

(defn- blank? [v] (str/blank? (str v)))

(defn- normalize-media
  [m]
  (let [mime (some-> (:media/mime m) str str/lower str/trim)]
    (cond-> m
      mime (assoc :media/mime mime))))

(defn normalize
  "Fill defaults and coerce loose input into the canonical shape. Never throws —
  `problems` is what reports badness, so a caller can normalize first and
  report every problem at once instead of one exception at a time."
  [m]
  (let [a (merge default-artifact m)]
    (-> a
        (assoc :artifact/tags (vec (remove blank? (:artifact/tags a))))
        (assoc :artifact/media (mapv normalize-media (:artifact/media a))))))

(defn- media-problems
  [idx {:media/keys [url mime bytes duration-ms width height]}]
  (cond-> []
    (blank? url)
    (conj {:problem/kind :media/missing-url
           :problem/media-index idx
           :problem/message "media entry needs :media/url"})

    (blank? mime)
    (conj {:problem/kind :media/missing-mime
           :problem/media-index idx
           :problem/message "media entry needs :media/mime"})

    (and (some? bytes) (not (pos? bytes)))
    (conj {:problem/kind :media/bad-bytes
           :problem/media-index idx
           :problem/message ":media/bytes must be positive when present"})

    (and (some? duration-ms) (not (pos? duration-ms)))
    (conj {:problem/kind :media/bad-duration
           :problem/media-index idx
           :problem/message ":media/duration-ms must be positive when present"})

    (and (some? width) (some? height) (not (and (pos? width) (pos? height))))
    (conj {:problem/kind :media/bad-dimensions
           :problem/media-index idx
           :problem/message ":media/width and :media/height must be positive"})))

(defn problems
  "Producer-side validation only: is this a well-formed artifact at all?
  Whether any *target* will accept it is a separate question answered by
  `haishin.target/problems`. Returns [] when clean."
  [artifact]
  (let [{:artifact/keys [id kind title media visibility]} artifact]
    (cond-> []
      (blank? id)
      (conj {:problem/kind :artifact/missing-id
             :problem/message "artifact needs a stable :artifact/id for receipt correlation"})

      (not (contains? kinds kind))
      (conj {:problem/kind :artifact/bad-kind
             :problem/message (str ":artifact/kind must be one of " (pr-str kinds))})

      (not (contains? visibilities visibility))
      (conj {:problem/kind :artifact/bad-visibility
             :problem/message (str ":artifact/visibility must be one of " (pr-str visibilities))})

      (and (not= :text kind) (empty? media))
      (conj {:problem/kind :artifact/missing-media
             :problem/message (str "kind " kind " requires at least one :artifact/media entry")})

      (and (= :text kind) (blank? title) (blank? (:artifact/body artifact)))
      (conj {:problem/kind :artifact/empty-text
             :problem/message "a :text artifact needs a title or a body"})

      :always
      (into (mapcat media-problems (range) media)))))

(defn valid? [artifact] (empty? (problems artifact)))

(defn primary-media
  "The one media entry a single-media target should use."
  [artifact]
  (first (:artifact/media artifact)))

(defn attribution-url
  "Where this artifact canonically lives. Cross-posts link back here rather than
  pretending the syndicated copy is the original."
  [artifact]
  (get-in artifact [:artifact/source :source/url]))
