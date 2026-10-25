(ns atproto.core
  "EDN-first AT Protocol contract helpers shared by kotoba and app-aozora."
  (:require [kotoba.lang.text :as str]))

(def profile-collection "app.bsky.actor.profile")
(def post-collection "app.bsky.feed.post")
(def follow-collection "app.bsky.graph.follow")

(def known-collections
  #{profile-collection post-collection follow-collection
    "app.bsky.feed.like" "app.bsky.feed.repost"})

(defn did? [s]
  (boolean (and (string? s) (re-matches #"^did:[a-z0-9]+:.+" s))))

(defn collection? [s]
  (boolean (and (string? s)
                (re-matches #"^[a-zA-Z][a-zA-Z0-9-]*(\.[a-zA-Z0-9-]+)+$" s))))

(defn valid-rkey? [s]
  (boolean (and (string? s)
                (seq s)
                (<= (count s) 512)
                (not (str/includes? s "/"))
                (not (str/includes? s "#"))
                (not (str/includes? s "?")))))

(defn repo-uri
  "Build `at://<did>/<collection>/<rkey>`."
  [repo collection rkey]
  (when-not (did? repo)
    (throw (ex-info "repo must be a DID" {:repo repo})))
  (when-not (collection? collection)
    (throw (ex-info "collection must be an NSID" {:collection collection})))
  (when-not (valid-rkey? rkey)
    (throw (ex-info "invalid rkey" {:rkey rkey})))
  (str "at://" repo "/" collection "/" rkey))

(def uri-re #"^at://([^/]+)/([^/]+)/([^/?#]+)$")

(defn parse-uri
  "Parse an AT URI into EDN."
  [uri]
  (let [[_ repo collection rkey] (re-matches uri-re (or uri ""))]
    (when-not repo
      (throw (ex-info "invalid AT URI" {:uri uri})))
    {:repo repo :collection collection :rkey rkey}))

(defn handle-from-did [did]
  (if (str/starts-with? (or did "") "did:web:")
    (-> did (subs (count "did:web:")) (str/replace ":" "."))
    did))

(defn profile-record
  "Construct an app.bsky.actor.profile record. This is a profile claim by the
  actor/repo; it is not proof that the actor is an official authority."
  [{:keys [displayName display-name description avatar]}]
  (cond-> {:$type profile-collection}
    (or displayName display-name) (assoc :displayName (or displayName display-name))
    description (assoc :description description)
    avatar (assoc :avatar avatar)))

(defn profile-write
  "Return the canonical profile putRecord payload."
  [repo profile]
  {:repo repo
   :collection profile-collection
   :rkey "self"
   :record (profile-record profile)})

(defn xrpc-url [base nsid]
  (str (str/replace (or base "") #"/$" "") "/xrpc/" nsid))
