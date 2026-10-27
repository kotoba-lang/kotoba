(ns browser.devtools
  "L1 DevTools adapter: wires live browser session/page state into the
  pure-data `devtools.inspect` inspection model.

  This is the host side of the L1 DevTools surface. `devtools.inspect`
  defines the pure panel/render functions over plain-data shapes; this
  namespace produces those shapes from a real `browser.session`/page so a
  REPL, test, or (future) CDP/HTTP transport can inspect the engine without
  re-running anything.

  Reuses the engine's existing debug substrates rather than capturing fresh
  state: `browser.dom-bridge/document-snapshot` for the DOM tree,
  `:browser/draw-ops` for layout boxes, `browser.audit/events` for the
  event timeline and network log, and the QuickJS runtime state's
  `:console/messages` for the console panel. No IO; safe to call on any
  session, even one whose script engine was never started (console/network
  simply come back empty).

  Levels (L0->L1): L0 was 'absent' -- the devtools repo held only KAMI
  automation contracts and the browser scattered debug data across
  browser-use/debug-state with no unified inspector. L1 unifies that data
  behind a stable, tested inspection API. A CDP/HTTP transport is L2."
  (:require [browser.audit :as audit]
            [browser.dom-bridge :as dom-bridge]
            [devtools.inspect :as inspect]))

(defn- page-document
  [session]
  (get-in session [:browser.session/page :browser/document]))

(defn- page-draw-ops
  [session]
  (get-in session [:browser.session/page :browser/draw-ops]))

(defn- console-messages
  "Console messages accumulated by the page's QuickJS scripts. Persisted on
  the session under :browser.session/quickjs-runtime-state (see
  quickjs_runner's persistent-execution-keys) so they survive across script
  tags within a page generation and are inspectable here. Empty when no
  script has run yet."
  [session]
  (let [runtime (:browser.session/quickjs-runtime-state session)]
    (or (get-in runtime [:quickjs-runtime/state :console/messages]) [])))

(defn- navigation-summary
  "Navigation entries (url/status/error) built directly from the session, so
  this namespace need not depend on the optional :browser-use alias.
  Mirrors browser.browser-use/navigation-state's entry shape."
  [session]
  (let [navigation (:browser.session/navigation session)]
    {:entries  (mapv (fn [{:keys [url page]}]
                       {:url    url
                        :status (get-in page [:browser/response :status])
                        :error  (:browser/error page)})
                     (:entries navigation))
     :redirects (vec (:redirects navigation))
     :error     (:browser.session/error session)}))

(defn inspection-input
  "Build the plain-data input map `devtools.inspect` consumes from a session.
  Exposed so callers (tests, transports) can inspect or transform the raw
  projection before rendering. All keys degrade to nil/empty when the
  corresponding state is absent (no page, no scripts run, no audit)."
  [session]
  {:document      (some-> (page-document session) (dom-bridge/document-snapshot))
   :draw-ops      (page-draw-ops session)
   :console       (console-messages session)
   :audit-events  (-> session :browser.session/audit audit/events)
   :navigation    (navigation-summary session)})

(defn inspect-session
  "Aggregate DevTools data snapshot for `session`. Returns the
  `devtools.inspect/inspector-snapshot` shape:
  {:meta {:url :title :ready-state} :dom :styles :layout :console
   :network :timeline}."
  [session]
  (inspect/inspector-snapshot (inspection-input session)))

(defn inspect-page
  "Aggregate DevTools data snapshot for a bare page map
  ({:browser/document :browser/draw-ops ...}) with no session/audit/console
  -- e.g. the direct result of `browser.core/load-html`."
  [page]
  (inspect/inspector-snapshot
   {:document (some-> (:browser/document page) (dom-bridge/document-snapshot))
    :draw-ops (:browser/draw-ops page)}))

(defn render-session
  "Human-readable multi-section DevTools dump of `session` (REPL/debug)."
  [session]
  (inspect/render-inspector (inspection-input session)))

(defn render-page
  "Human-readable DevTools dump of a bare page map (REPL/debug)."
  [page]
  (inspect/render-inspector
   {:document (some-> (:browser/document page) (dom-bridge/document-snapshot))
    :draw-ops (:browser/draw-ops page)}))

(defn inspect-node
  "Inspect a single document node by id within `session`: attrs, computed
  styles, tree path, and layout box. See `devtools.inspect/inspect-node`."
  [session node-id]
  (inspect/inspect-node
   {:document (some-> (page-document session) (dom-bridge/document-snapshot))
    :draw-ops (page-draw-ops session)
    :node-id  node-id}))
