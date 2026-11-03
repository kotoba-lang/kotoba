(ns kami.mangaka.reader.views
  "Manga reader UI as hiccup (ADR-2606282101). These fns return plain hiccup, so
  they serve double duty: reagent renders them live in the browser (cljs) and
  `kami.mangaka.hiccup` renders the identical data to HTML for the static build
  (clj). Only the text overlay depends on `locale`; the panel image does not."
  (:require [kami.mangaka.text :as t]))

(defn locale-switch
  "Language switcher. In SSR each link carries ?lang=; the re-frame app intercepts
  the click (data-lang) to re-render overlays without a reload."
  [locales current]
  (when (> (count locales) 1)
    [:nav.mk-langs
     (for [l locales]
       [:a {:href (str "?lang=" (name l))
            :data-lang (name l)
            :class (when (= l current) "on")}
        (name l)])]))

(defn page-figure
  "One rendered panel image + its localized text overlay. `figure` =
  {:src :alt :elements [:desc]}. When :src is nil (storyboard not yet rendered)
  a captioned placeholder stands in, so the same component serves rendered and
  unrendered chapters."
  [locale {:keys [src alt desc elements]}]
  [:figure.mk-fig
   (if src
     [:img {:loading "lazy" :src src :alt (or alt "")}]
     [:div.mk-noart (when desc [:p.mk-desc (t/localize desc locale)])])
   (t/overlay locale elements)])

(defn chapter-view
  "A whole chapter: header + vertical scroll of page figures + prev/next nav.
  `data` = {:title :crumb :beat :figures [...] :prev {:href :title} :next {…}
            :locale :locales}."
  [{:keys [title crumb beat figures prev next locale locales]}]
  [:article.mk-chapter
   [:header.chead
    (when crumb [:p.crumb crumb])
    [:h1 title]
    (when beat [:p.beat beat])
    (locale-switch locales locale)]
   [:div.mk-pages
    (for [f figures] (page-figure locale f))]
   [:nav.chnav
    (if prev [:a {:href (:href prev)} (str "◀ " (:title prev))] [:span])
    (if next [:a {:href (:href next)} (str (:title next) " ▶")] [:span])]])

(defn index-view
  "Table of contents. `data` = {:title :subtitle :synopsis :locale :locales
   :volumes [{:title :alt :chapters [{:href :n :title :titleSub :badge}]}]}."
  [{:keys [title subtitle synopsis locale locales volumes]}]
  [:div
   [:header.hero
    [:h1 title]
    (when subtitle [:p.sub subtitle])
    (locale-switch locales locale)
    (when synopsis [:p.syn synopsis])]
   [:main
    (for [{:keys [title alt chapters]} volumes]
      [:section.vol
       [:h2 title (when alt [:span.alt alt])]
       [:ol.chapters
        (for [{:keys [href n title titleSub badge]} chapters]
          [:li [:a {:href href}
                [:span.cn n]
                [:span.ct title (when titleSub [:span.cja titleSub])]
                [:span.cm [:span.badge badge]]]])]])]])
