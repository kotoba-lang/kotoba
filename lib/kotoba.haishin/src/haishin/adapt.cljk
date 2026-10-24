(ns haishin.adapt
  "Adapters from this workspace's existing producers into the canonical artifact.

  ## The tamaki content contract

  The `*ka` creator actors — dougaka (動画家), mangaka (漫画家), animeka
  (アニメ家), ongakuka (音楽家) — already emit a *secret-free publication
  handoff*: `dougaka.manifest/artifact-manifest` plus
  `dougaka.manifest/publication-plan`, whose contract is that it never uploads
  and never carries credentials. That contract lines up exactly with this
  library's, so the adapter is a rename rather than a redesign.

  ## `:executable?` is the grant

  A tamaki publication plan carries `:decision` and `:executable?`, where
  `:executable? true` means *stage is publish-ready AND a human approved it*.
  That is precisely the condition under which targets may be granted, so
  `plan->grant` maps it straight onto `haishin.execute/execute!`'s `:grant`.
  When a plan is `:approval-required`, the grant is empty and every target
  yields a `:skipped` receipt — the human approval boundary is preserved by
  construction rather than by remembering to check a flag."
  (:require [kotoba.lang.text :as str]
            [haishin.artifact :as artifact]))

(def ^:private tamaki-kind->artifact-kind
  {:vertical-video :video
   :video :video
   :image :image
   :manga-page :image
   :audio :audio
   :track :audio
   :text :text})

(defn tamaki-content->artifact
  "A tamaki artifact-manifest -> a canonical haishin artifact.

  `opts`:
    :public-url  where the asset is publicly readable. A tamaki manifest holds
                 `:artifact/path`, a *local* path, which several platforms
                 cannot use — Instagram's API fetches the asset from a URL it
                 can reach. Pass the aozora URL once the asset is published
                 there; without it, targets that pull from a URL will warn.
    :source-url  the canonical page for the work (defaults to :public-url)
    :body        description/caption text; tamaki manifests carry no body field
    :tags        vector of tags
    :visibility  defaults to :public"
  [manifest {:keys [public-url source-url body tags visibility]
             :or {visibility :public}}]
  (let [{:artifact/keys [title mime verification episode-id content-project]} manifest
        id (:artifact/id manifest)
        {:keys [width height duration-s]} (or verification {})]
    (artifact/normalize
     {:artifact/id (cond-> id (keyword? id) name)
      :artifact/kind (get tamaki-kind->artifact-kind
                          (:artifact/kind manifest) :video)
      :artifact/title (or title (some-> episode-id str))
      :artifact/body (or body "")
      :artifact/tags (vec tags)
      :artifact/visibility visibility
      :artifact/media [(cond-> {:media/mime (or mime "video/mp4")}
                         public-url (assoc :media/url public-url)
                         width (assoc :media/width (long width))
                         height (assoc :media/height (long height))
                         duration-s (assoc :media/duration-ms
                                           (long (* 1000 (double duration-s)))))]
      :artifact/source {:source/platform :aozora
                        :source/url (or source-url public-url)
                        :source/project content-project}})))

(defn plan->grant
  "A tamaki publication plan -> the set of targets that may actually be sent to.

  Empty unless the plan is `:executable?`. `:aozora` is dropped: it is the
  producer's own appview, published by the producer, not something this library
  syndicates to."
  [publication-plan]
  (if (:executable? publication-plan)
    (into #{} (remove #{:aozora}) (:channels publication-plan))
    #{}))

(defn grant-explanation
  "Why the grant is what it is — for the actor's audit ledger, so a run that
  sent nothing records the reason rather than looking like a no-op."
  [publication-plan]
  (let [grant (plan->grant publication-plan)]
    (cond
      (seq grant)
      (str "granted " (str/join ", " (sort (map name grant)))
           " (plan :executable? true, decision " (:decision publication-plan) ")")

      (not (:executable? publication-plan))
      (str "no grant — plan decision is " (:decision publication-plan)
           "; human approval boundary not crossed")

      :else
      "no grant — plan is executable but declares no channel beyond :aozora")))
