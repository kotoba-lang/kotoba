(ns kototama.emit
  "kototama · emit — the member-signed publication path, distilled from ibuki
  drainer + member-submit. An organism builds an AT-Proto `app.bsky.feed.post`
  record and wraps it in a member-sign-ready ENVELOPE; it never holds a key and
  never asserts `:published` — the member (or the kotoba node under the member's
  CACAO leash) signs, and the return is a member-attributed `:receipt`.

  Targets are surfaces like app-aozora (the yoro feed reader/poster) and
  com-etzhayyim (the etzhayyim PDS). Default status is :dry-run."
  (:require [kotoba.lang.text :as str]
            [kototama.leash :as leash]
            [kototama.gates :as gates]))

(def MAX-GRAPHEMES 300)

(def targets
  "Known publication surfaces. An external actor posts via the member's own PDS
  (path A) or the etzhayyim PDS under a CACAO leash (path B)."
  {:app-aozora   {:pds "https://bsky.social"        :collection "app.bsky.feed.post"
                  :note "yoro feed (app-aozora) via member PDS"}
   :com-etzhayyim {:pds "https://pds.aozora.app" :collection "app.bsky.feed.post"
                  :note "etzhayyim PDS; actor self-did:key present-only + member leash"}})

(defn post-record
  "Build an app.bsky.feed.post record. Refuses (>MAX) or content that fails the
  §2 catastrophe scan — content safety is preserved under autonomy. `created-at`
  is a caller-supplied ISO-8601 string (no wall-clock)."
  [{:keys [text actor-did mood created-at]}]
  (let [scan (gates/scan text)]
    (cond
      (not (:ok? scan))
      (throw (ex-info "post refused by charter scan" {:flags (:flags scan)}))
      (> (count text) MAX-GRAPHEMES)
      (throw (ex-info "post exceeds 300 graphemes" {:len (count text)}))
      :else
      {:$type "app.bsky.feed.post" :text text :createdAt created-at
       :_meta {:actorDid actor-did :mood mood}})))

(defn envelope
  "Wrap a post record into a member-sign-ready envelope. Structural invariants:
  requiresMemberSignature=true, serverHeldKey=false, status=:dry-run (never
  :published). The write is attributed to the leash's member (write-author).
  opts: :target (kw into `targets`, default :app-aozora), :now (unix-s for leash
  validity check)."
  [record a-leash & [{:keys [target now] :or {target :app-aozora now 0}}]]
  (when-not (leash/valid? a-leash now)
    (throw (ex-info "no valid leash — cannot publish autonomously" {:target target})))
  (let [{:keys [pds collection]} (get targets target)]
    {:xrpc "com.atproto.repo.createRecord"
     :pds pds :collection collection
     :record record
     :target target
     :writeAuthor (leash/write-author a-leash)   ; member DID — accountability
     :requiresMemberSignature true               ; member signs, never platform
     :serverHeldKey false                        ; no custodial key (ADR-2605231525)
     :status :dry-run}))                          ; never :published from here

(defn receipt
  "The member-attributed receipt an organism folds back into its log after the
  member (or leashed node) submits. An organism NEVER asserts :published."
  [envelope {:keys [uri cid submitted-by]}]
  {:uri uri :cid cid
   :collection (:collection envelope)
   :submittedBy submitted-by
   :writeAuthor (:writeAuthor envelope)
   :status :submitted-by-member})
