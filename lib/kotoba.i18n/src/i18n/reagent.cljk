(ns i18n.reagent
  "i18n-specific hiccup helpers, dual-render (SSR clj / live cljs) like every
  other shitsuke-based view in this org. Generic rendering itself (mount,
  as-element, SSR->string) is `shitsuke.reagent.core`'s job, not this
  namespace's — require that directly for the actual root mount call.

  `locale-links` + `wire-lang-switch!` generalize the delegated
  `a[data-lang]` click-listener pattern proven by
  kami-mangaka-reader/src/kami/mangaka/reader/app.cljs: SSR emits inert
  `<a data-lang=\"ja\">` markup (works with JS disabled — the reader is a
  real page, not an app shell), and one document-level click listener
  hydrates it into an `:i18n/set-locale` dispatch. No per-link `:on-click`,
  so the exact same hiccup renders identically on both hosts."
  (:require [i18n.registry :as registry]
            [i18n.re-frame :as i18n-rf]))

(defn root-attrs
  "`{:lang \"ja\" :dir \"ltr\"}`-shaped attrs for the document root element
  (`<html>` or an app-shell `<div>`), so RTL locales (ar/he/fa/ur/yi/ps/sd by
  default — see i18n.registry) get `dir=\"rtl\"` without any per-component
  awareness of direction."
  [locale]
  {:lang (name locale)
   :dir (name (registry/dir locale))})

(defn locale-links
  "Pure hiccup nav of locale-switch links. `locales` defaults to
  `(registry/all)`; pass a filtered subset to limit what a given app offers.
  `current-locale` gets `aria-current`."
  ([current-locale] (locale-links current-locale (registry/all)))
  ([current-locale locales]
   [:nav {:class "i18n__locale-switch" :aria-label "Language"}
    (for [{:i18n.lang/keys [code native-name]} locales]
      ^{:key code}
      [:a {:href "#"
           :data-lang (name code)
           :aria-current (when (= code current-locale) "true")}
       native-name])]))

#?(:cljs
   (defn wire-lang-switch!
     "Attach one delegated click listener that turns `a[data-lang]` clicks
     (as rendered by `locale-links`) into an `:i18n/set-locale` dispatch via
     `i18n.re-frame/set-locale!`. Call once at app mount time. Idempotent
     only in the sense that calling it twice attaches two listeners — call
     it exactly once, same as the pattern it generalizes."
     []
     (.addEventListener
      js/document "click"
      (fn [e]
        (when-let [a (.closest (.-target e) "a[data-lang]")]
          (.preventDefault e)
          (i18n-rf/set-locale! (keyword (.getAttribute a "data-lang"))))))))
