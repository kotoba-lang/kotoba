(ns browser.accessibility
  "Accessibility tree projection for kotoba browser documents and OS surfaces."
  (:require [aria.core :as aria]))

;; The pure, host-independent WAI-ARIA accessibility-tree projection (implicit
;; role table, hidden?/role/name-for/form-value/etc., and the accessible-node/
;; tree entry points) now lives in kotoba-lang/org-w3-aria's aria.core
;; (ADR-2607051500). This file re-exports those two entry points and keeps
;; only browser's own OS-shell "surface" (window manager) projection below,
;; built on top of them.

(def tree aria/tree)

(def accessible-node aria/accessible-node)

(defn- surface-app-node
  [app]
  {:a11y/id (str "app/" (:app/id app))
   :a11y/role "button"
   :a11y/name (str (or (:app/title app) (:app/id app)))
   :surface/app-id (:app/id app)})

(defn- rect-state
  [[x y w h]]
  {:a11y/x x
   :a11y/y y
   :a11y/width w
   :a11y/height h})

(defn- surface-window-node
  [surface window]
  (let [text-state (:window/text window)
        [selection-start selection-end] (or (:text/selection text-state) [nil nil])
        composition-text (get-in text-state [:text/composition :composition/text])]
    (cond-> (merge {:a11y/id (:window/id window)
                    :a11y/role "window"
                    :a11y/name (str (:window/title window))
                    :surface/window-id (:window/id window)
                    :surface/app-id (:window/app-id window)
                    :surface/window-state (:window/state window)}
                   (rect-state (:window/rect window)))
      (= (:window/id window) (:surface/focus surface))
      (assoc :a11y/focused true)

      (contains? window :window/text-buffer)
      (assoc :a11y/value (:window/text-buffer window))

      (some? (:text/caret text-state))
      (assoc :a11y/caret (:text/caret text-state))

      (some? selection-start)
      (assoc :a11y/selection-start selection-start)

      (some? selection-end)
      (assoc :a11y/selection-end selection-end)

      (seq (str composition-text))
      (assoc :a11y/composition composition-text)

      (contains? window :window/scroll)
      (assoc :a11y/scroll-left (first (:window/scroll window))
             :a11y/scroll-top (second (:window/scroll window))))))

(defn surface-tree
  "Project the kotoba OS/browser surface model into an accessibility tree."
  [surface]
  (when surface
    (cond-> {:a11y/id (:surface/id surface)
             :a11y/role "application"
             :a11y/name (str (:surface/title surface))
             :surface/focus (:surface/focus surface)
             :a11y/children
             (vec
              (concat
               [{:a11y/id (str (:surface/id surface) "/launcher")
                 :a11y/role "navigation"
                 :a11y/name "Launcher"
                 :a11y/children (mapv surface-app-node (:surface/apps surface))}
                {:a11y/id (str (:surface/id surface) "/workspace")
                 :a11y/role "group"
                 :a11y/name "Workspace"
                 :a11y/children (mapv #(surface-window-node surface %)
                                       (:surface/windows surface))}]))}
      (:surface/viewport surface)
      (assoc :a11y/viewport (:surface/viewport surface)))))

(defn session-tree
  "Project the active browser session page and OS surface as one host tree."
  [session]
  (let [page-node (when-let [document (get-in session [:browser.session/page :browser/document])]
                    (when-let [node (aria/tree document)]
                      (assoc node
                             :a11y/id "browser.session/page"
                             :browser/url (get-in session [:browser.session/page :browser/url]))))
        surface-node (surface-tree (:browser.session/surface session))
        children (cond-> []
                   surface-node (conj (assoc surface-node :a11y/id "browser.session/surface"))
                   page-node (conj page-node))]
    (when (seq children)
      (cond-> {:a11y/id "browser.session"
               :a11y/role "application"
               :a11y/name "Browser Session"
               :a11y/children (vec children)}
        (get-in session [:browser.session/profile :profile/id])
        (assoc :profile/id (get-in session [:browser.session/profile :profile/id]))

        (get-in session [:browser.session/page :browser/url])
        (assoc :browser/url (get-in session [:browser.session/page :browser/url]))

        (get-in session [:browser.session/surface :surface/focus])
        (assoc :surface/focus (get-in session [:browser.session/surface :surface/focus]))))))
