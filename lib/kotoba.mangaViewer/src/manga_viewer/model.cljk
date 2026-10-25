(ns manga-viewer.model
  "Normalized manga work model + adapters (ADR-2607070500).

  A work is a plain EDN map:

    {:manga/id      \"zankyo-1\"
     :manga/title   \"残響のカルテット\"
     :manga/author  \"GFTD Mangaka AI\"
     :manga/episode \"第1話 遺品\"          ; optional
     :manga/tags    [\"音楽\" \"超常ドラマ\"] ; optional
     :manga/cover   \"https://…/p01\"        ; optional (index thumbnail)
     :manga/url     \"https://…/work/…\"     ; optional (canonical reader URL)
     :manga/pages   [{:page/number 1
                      :page/title  \"Opening\"   ; optional
                      :page/text   \"…\"          ; optional (caption/dialogue)
                      :page/images [\"https://…\"]}]}

  A page has one image (composed page renders, e.g. the manga.gftd.ai reader)
  or several (panel-per-image works, e.g. the aozora Ghost Hacker projection).
  Pagination/mode support derives from that distinction — see
  manga-viewer.pagination/supported-modes."
  (:require [kotoba.lang.text :as str]))

(defn page-count
  "Page count — :manga/page-count wins when set (index-only works that carry
  no :manga/pages, e.g. registry entries pointing at an external reader)."
  [work]
  (or (:manga/page-count work)
      (count (:manga/pages work))))

(defn image-count [work]
  (reduce + 0 (map #(count (:page/images %)) (:manga/pages work))))

(defn validate
  "Vector of human-readable problems; empty when the work is well-formed."
  [work]
  (let [pages (:manga/pages work)
        numbers (map :page/number pages)]
    (cond-> []
      (str/blank? (str (:manga/id work)))
      (conj "missing :manga/id")

      (str/blank? (str (:manga/title work)))
      (conj "missing :manga/title")

      (empty? pages)
      (conj "no pages")

      (some #(empty? (:page/images %)) pages)
      (conj "page without images")

      (not= (count numbers) (count (distinct numbers)))
      (conj "duplicate page numbers"))))

;; ── adapters ─────────────────────────────────────────────────────────────────

(defn from-mangaka-data
  "manga.gftd.ai reader `DATA` shape → work:
  {:title … :author … :pages [{:n 1 :src \"/img/…\"}]}. Extra work metadata
  (id/url/cover/episode/tags) comes from opts — the DATA blob doesn't carry it."
  ([data] (from-mangaka-data data nil))
  ([{:keys [title author pages]} {:keys [id url cover episode tags]}]
   (let [sorted (sort-by :n pages)]
     {:manga/id (or id title)
      :manga/title title
      :manga/author author
      :manga/episode episode
      :manga/tags (vec (or tags []))
      :manga/cover (or cover (:src (first sorted)))
      :manga/url url
      :manga/pages (mapv (fn [{:keys [n src]}]
                           {:page/number n :page/images [src]})
                         sorted)})))

(defn- page-text
  "Body of a page's :yoro.post/text — the aozora projection puts
  `<work title> / <page title>` on the first line, dialogue after."
  [text]
  (when text
    (let [body (->> (str/split-lines text) (remove str/blank?) (drop 1))]
      (when (seq body) (str/join "\n" body)))))

(defn from-gh-manga-tx
  "aozora `:gh.manga/*` projection tx (seq of entity maps, the shape
  aozora.appview.manga/work->tx emits) → work. Panels fold into their page's
  :page/images sorted by :gh.manga/panelNumber; the page's :yoro.post/* entity
  supplies :page/text. opts:
    :image-fn  url → url (e.g. .png → .webp display swap), default identity
    :author :url :cover :tags — work metadata the tx doesn't carry"
  ([tx] (from-gh-manga-tx tx nil))
  ([tx {:keys [image-fn author url cover tags]}]
   (let [image-fn (or image-fn identity)
         work (first (filter :gh.manga/title tx))
         work-eid (:db/id work)
         pages (->> tx
                    (filter #(= work-eid (:gh.manga/work %)))
                    (sort-by #(or (:gh.manga/pageNumber %) 0)))
         panels-by-page (group-by :gh.manga/page (filter :gh.manga/panel-id tx))
         text-by-uri (into {} (keep (fn [e]
                                      (when-let [uri (:yoro.post/uri e)]
                                        [uri (:yoro.post/text e)]))
                                    tx))
         page-panel-entities (fn [page]
                                (->> (get panels-by-page (:db/id page))
                                     (sort-by #(or (:gh.manga/panelNumber %) 0))))
         page-images (fn [page]
                       (->> (page-panel-entities page)
                            (keep :gh.manga/imageUrl)
                            (mapv image-fn)))
         ;; parallel to page-images: the variant map of each imaged panel, so
         ;; select-variant can swap images on geometry-free pages too.
         page-image-variants (fn [page]
                               (->> (page-panel-entities page)
                                    (filter :gh.manga/imageUrl)
                                    (mapv #(or (:gh.manga/imageVariants %) {}))))
         ;; ADR-2607141700: a panel-geometry-aware view of the same panels,
         ;; alongside (not replacing) :page/images -- populated only when at
         ;; least one panel on the page carries :gh.manga/rect (komawari
         ;; output, e.g. kami.mangaka.komawari/propose-page-layout via a
         ;; source's export step). Works with no geometry (the common case
         ;; today) get an empty :page/panels and render via :page/images as
         ;; before -- this is purely additive.
         ;; :panel/dialogue/:panel/sfx/:panel/tone carry through independent of
         ;; :gh.manga/rect -- a panel can have dialogue without geometry (an
         ;; ordinary panel-per-image page) or geometry without dialogue.
         ;; :gh.manga/imageVariants is {workflow -> url}: the same panel as
         ;; produced by another workflow/LLM run, not a revision of the
         ;; canonical one. Carried through image-fn like :panel/imageUrl so a
         ;; reader can offer "read this episode as <workflow>" without knowing
         ;; anything about how the images were made.
         variants-of (fn [p]
                       (when (seq (:gh.manga/imageVariants p))
                         (reduce-kv (fn [m wf url] (assoc m wf (image-fn url)))
                                    {} (:gh.manga/imageVariants p))))
         page-panels (fn [page]
                       (->> (page-panel-entities page)
                            (filter :gh.manga/rect)
                            (mapv (fn [p]
                                    (cond-> {:panel/rect (:gh.manga/rect p)
                                             :panel/imageUrl (some-> (:gh.manga/imageUrl p) image-fn)}
                                      (:gh.manga/tilt p) (assoc :panel/tilt (:gh.manga/tilt p))
                                      (seq (variants-of p)) (assoc :panel/imageVariants (variants-of p))
                                      (seq (:gh.manga/dialogue p)) (assoc :panel/dialogue (:gh.manga/dialogue p))
                                      (seq (:gh.manga/sfx p)) (assoc :panel/sfx (:gh.manga/sfx p))
                                      (:gh.manga/tone p) (assoc :panel/tone (:gh.manga/tone p)))))))
         all-variants (->> (filter :gh.manga/panel-id tx)
                           (mapcat (comp keys :gh.manga/imageVariants))
                           distinct sort vec)
         first-image (some seq (map page-images pages))]
     (when work
       {:manga/id (:gh.manga/id work)
        :manga/title (:gh.manga/title work)
        :manga/author author
        :manga/episode (or (:gh.manga/arc work) (:gh.manga/subtitle work))
        :manga/tags (vec (or tags []))
        :manga/cover (or cover (first first-image))
        :manga/url url
        ;; every workflow this work has ever been produced with, canonical
        ;; excluded — empty for a work made exactly once.
        :manga/variants all-variants
        :manga/pages (mapv (fn [page]
                             (cond-> {:page/number (or (:gh.manga/pageNumber page) 0)
                                      :page/images (page-images page)
                                      :page/image-variants (mapv #(reduce-kv (fn [m wf u] (assoc m wf (image-fn u))) {} %)
                                                                 (page-image-variants page))
                                      :page/panels (page-panels page)}
                               (:gh.manga/title page)
                               (assoc :page/title (:gh.manga/title page))

                               (page-text (get text-by-uri (:gh.manga/postUri page)))
                               (assoc :page/text (page-text (get text-by-uri (:gh.manga/postUri page))))))
                           pages)}))))

;; ── production variants ──────────────────────────────────────────────────────
;; A pipeline that re-produces the same episode with a different workflow/LLM
;; leaves several images per panel rather than one edited in place. The work
;; carries every alternative alongside the canonical image
;; (:panel/imageVariants / :page/image-variants, both {workflow -> url}), and
;; a reader picks one to read the episode through.

(defn select-variant
  "Work with every panel that HAS an image for `variant` swapped to it.

  Panels the chosen workflow never produced keep their canonical image, so a
  partially re-produced episode still reads end to end instead of showing
  holes — which is the normal case: a run usually covers some pages, not all.
  A nil/blank variant, or one this work has no images for, returns the work
  unchanged."
  [work variant]
  (let [v (when variant (str variant))]
    (if (or (nil? v) (= "" v))
      work
      (update work :manga/pages
              (fn [pages]
                (mapv (fn [page]
                        (let [panels (mapv (fn [p]
                                             (if-let [u (get (:panel/imageVariants p) v)]
                                               (assoc p :panel/imageUrl u)
                                               p))
                                           (:page/panels page))
                              images (mapv (fn [img vs] (get vs v img))
                                           (:page/images page)
                                           (concat (:page/image-variants page) (repeat {})))]
                          (assoc page :page/panels panels :page/images images)))
                      pages))))))
