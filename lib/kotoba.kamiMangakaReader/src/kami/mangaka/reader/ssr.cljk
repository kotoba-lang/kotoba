(ns kami.mangaka.reader.ssr
  "Server-side render the reader views to HTML strings for the static build
  (ADR-2606282101). Same hiccup the reagent app uses in the browser."
  (:require [kami.mangaka.hiccup :as h]
            [kami.mangaka.text :as t]
            [kami.mangaka.reader.views :as v]))

(def theme-css
  "Structural + default dark/gold theme for the reader (the work may append its
  own). Pairs with kami.mangaka.text/css (the overlay styles)."
  ":root{color-scheme:dark;--gold:#c9a24a;--bg:#15140f;--fg:#e6e6e0;--dim:#8a877c;--card:#1d1c16;--line:#33322a}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--fg);
  font-family:ui-serif,Georgia,serif;line-height:1.6}
a{color:var(--gold);text-decoration:none}a:hover{text-decoration:underline}
.hero{max-width:820px;margin:0 auto;padding:3rem 1.5rem 1rem;text-align:center}
.hero h1{font-size:2.4rem;margin:0;letter-spacing:.04em}.hero .sub{font-style:italic;color:var(--gold)}
main{max-width:820px;margin:0 auto;padding:1rem 1.5rem 4rem}
.vol h2{font-size:1.3rem;border-bottom:1px solid var(--line);padding-bottom:.4rem}
.vol h2 .alt{font-size:.8rem;color:var(--dim);font-style:italic;margin-left:.6rem}
ol.chapters{list-style:none;margin:0;padding:0}
ol.chapters li a{display:flex;align-items:center;gap:.8rem;padding:.55rem .4rem;border-bottom:1px solid #211f18;color:var(--fg)}
.cn{color:var(--gold);width:1.8rem;flex:none;font-variant-numeric:tabular-nums}.ct{flex:1}.ct .cja{display:block;font-size:.78rem;color:var(--dim)}
.badge{font-size:.7rem;text-transform:uppercase;color:var(--dim);border:1px solid var(--line);border-radius:3px;padding:.15rem .45rem}
.chead{max-width:900px;margin:0 auto;padding:2.5rem 1rem 1rem;text-align:center}.chead h1{font-size:1.8rem;margin:.2rem 0}
.crumb{color:var(--dim);font-size:.85rem}.beat{color:var(--gold);font-size:.9rem}
.mk-pages{max-width:900px;margin:0 auto;padding:0 .5rem}
.mk-fig{margin:0 0 1.1rem}.mk-fig img{width:100%;height:auto;display:block;border-radius:4px;box-shadow:0 4px 20px rgba(0,0,0,.5)}
.mk-langs{display:inline-flex;gap:.4rem;margin:.6rem 0}.mk-langs a{border:1px solid var(--line);border-radius:3px;padding:.1rem .5rem;font-size:.8rem;text-transform:uppercase}
.mk-langs a.on{background:var(--gold);color:var(--bg);border-color:var(--gold)}
.chnav{max-width:820px;margin:2rem auto 0;padding:1rem 1.5rem;display:flex;justify-content:space-between;gap:1rem;border-top:1px solid var(--line)}")

(defn styles
  "Concatenate overlay CSS + reader theme + optional work CSS."
  ([] (styles nil))
  ([extra] (str t/css "\n" theme-css (when extra (str "\n" extra)))))

(defn document
  "Wrap a body hiccup in a full HTML document string."
  [{:keys [title lang css body app-js]}]
  (str "<!DOCTYPE html>\n"
       (h/->html
        [:html {:lang (or lang "ja")}
         [:head
          [:meta {:charset "utf-8"}]
          [:meta {:name "viewport" :content "width=device-width, initial-scale=1"}]
          [:title title]
          [:style [:hiccup/raw (or css (styles))]]]
         [:body
          body
          (when app-js [:script {:src app-js}])]])))

(defn index-html
  [{:keys [title lang css app-js] :as data}]
  (document {:title (or title "Manga") :lang lang :css css :app-js app-js
             :body (v/index-view data)}))

(defn chapter-html
  [{:keys [title series-title lang css app-js] :as data}]
  (document {:title (str title (when series-title (str " — " series-title)))
             :lang lang :css css :app-js app-js
             :body (v/chapter-view data)}))
