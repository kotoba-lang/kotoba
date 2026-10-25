(ns route.core
  "Fragment routing for kotoba-lang single-page apps. Pure `.cljc`, stdlib +
  jp-go-dds only, no I/O and no browser API in this namespace.

  WHY IT IS A LIBRARY. kotoba-lang UI is single-page apps (ADR-2608080100): one
  document, one bundle, one mount, and moving between screens changes state rather
  than location. Three apps arrived at the same ~76-line file to do it —
  `kami-app-daw`, `kami-app-nle`, `kami-app-suji` — and the first two differ from
  each other by six lines, five of which are the view table and one of which is a
  word in a docstring. The `kotoba-uiux` skill names the third app as the moment
  to extract, and this is it. Not into `jp-go-dds`, because routing is neither
  markup nor CSS.

  THE TWO INVARIANTS THIS EXISTS TO KEEP.

  **Views are data, and the nav is generated from them.** A view added to the
  dispatch and forgotten in the nav is dead code that looks live; generating the
  nav from the same table removes the possibility rather than asking anybody to
  remember. `check-views` refuses a table that cannot hold this up.

  **The fragment, not a path.** These apps are served by static hosts (GitHub
  Pages, the cloud-itonami sites plane), where `history.pushState` to `/editor`
  gives a URL that works until the reader reloads it and then 404s. A fragment is
  never sent to the host, so a hash route survives reload, bookmarking and
  sharing with no server rewrite rule. Use `pushState` only where a rewrite
  actually exists — and check, rather than assume."
  (:require [kotoba.lang.text :as str]
            [jp-go-dds.core :as dds]))

(defn check-views
  "Validate a view table, returning a vector of problems (empty when it is sound).

  Called by `fragment->view` in a way that cannot be skipped, because a table with
  two views on one fragment resolves arbitrarily and a table with no default
  resolves to nothing — both of which look like routing bugs in the app rather
  than like a malformed table."
  [views]
  (cond-> []
    (empty? views)
    (conj "a view table must have at least one view — the first is the default")

    (not-every? #(and (keyword? (:id %)) (string? (:fragment %)) (string? (:label %))) views)
    (conj "every view needs :id (keyword), :fragment (string) and :label (string)")

    (not= (count views) (count (distinct (map :id views))))
    (conj "two views share an :id")

    (not= (count views) (count (distinct (map :fragment views))))
    (conj "two views share a :fragment, so one of them is unreachable")

    (and (seq views) (not= "#/" (:fragment (first views))))
    (conj "the first view is the default and must be addressed by \"#/\"")))

(defn validate!
  "Throw on a malformed view table. An app calls this once at load; the failure a
  table like that produces at runtime looks like a router bug, and finding it in
  the app is much more expensive than being told here."
  [views]
  (let [problems (check-views views)]
    (when (seq problems)
      (throw (ex-info (str "invalid view table: " (str/join "; " problems))
                      {:type :invalid-views :problems problems :views views})))
    views))

(defn fragment->view
  "Resolve a location fragment to a view. Unknown, empty and nil all land on the
  first view — an address bar is user input, and a typo must not blank the app.

  A fragment carrying a query or a trailing segment (`#/compare?x=1`) still names
  its view; matching only on equality would drop the reader onto the default and
  look like the link was wrong."
  [views fragment]
  (let [f (or fragment "")
        default (first views)]
    (or (first (filter #(= (:fragment %) f) views))
        (first (filter #(and (not= "#/" (:fragment %))
                             (re-find (re-pattern (str "^#/?" (name (:id %)))) f))
                       views))
        default)))

(defn nav
  "The view switcher: `dds/button` with `:href`, so these are real anchors —
  middle-clickable, copyable, readable by anything that reads links — while
  remaining the design system's own controls. No app CSS for any of it.

  `opts` may carry `:aria-label` (default \"Views\") and `:size` (default \"sm\")."
  ([views active-id] (nav views active-id {}))
  ([views active-id {:keys [aria-label size] :or {aria-label "Views" size "sm"}}]
   (into [:nav {:class "dds-ext-row" :aria-label aria-label}]
         (for [{:keys [id fragment label]} views
               :let [active? (= id active-id)]]
           (dds/button label {:type (if active? :solid-fill :text)
                              :size size
                              :href fragment
                              :attrs (cond-> {} active? (assoc :aria-current "page"))})))))
