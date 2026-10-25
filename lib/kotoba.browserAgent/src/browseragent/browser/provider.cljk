(ns browseragent.browser.provider
  "Default owned-browser providers.

  The principle from browser-use-clj holds — the browser is an
  injected `IBrowser` capability — but browser-agent-clj ships the
  *default*: if you inject nothing, the agent launches and owns its
  own browser. Pick a provider by `:kind`:

    :mock       pure-data site model (tests/offline) — bundled here
    :playwright agent-owned Chromium process with its own user-data-dir
                (profile/cookies persist) — JVM only, needs the
                :playwright alias; see comment below
    :in-browser the cljs page itself / an agent-owned `window.open` tab
    :cdp        a remote browser over CDP/MCP (e.g. kotoba-WASM host)

  Every provider is wrapped by `session/managed-browser`, so whatever
  the backend, the agent *owns* the session: profile + tabs + current
  URL are datoms, and frames stream to the live view."
  (:require [browseruse.browser :as b]
            [browseragent.browser.session :as session]))

(defmulti raw-browser
  "Construct the bare inner IBrowser for a provider spec.
  Extend with your own defmethod to add providers."
  :kind)

(defmethod raw-browser :mock [{:keys [site start-url]}]
  (b/mock-browser site start-url))

(defmethod raw-browser :default [spec]
  (throw (ex-info (str "No browser provider for " (:kind spec)
                       " — inject one or add a raw-browser defmethod."
                       " JVM Playwright lives behind the :playwright alias.")
                  {:spec spec})))

;; JVM Playwright provider (lives in examples/ behind the :playwright alias
;; to keep the core third-party-dep-free):
;;
;;   (defmethod raw-browser :playwright [{:keys [user-data-dir headless]}]
;;     (let [pw   (Playwright/create)
;;           ctx  (.launchPersistentContext (.chromium pw)
;;                  (Paths/get user-data-dir (into-array String []))
;;                  (doto (BrowserType$LaunchPersistentContextOptions.)
;;                    (.setHeadless (boolean headless))))
;;           page (first (.pages ctx))]
;;       (reify b/IBrowser …)))   ; .navigate/.click/.fill/.goBack + indexed snapshot
;;
;; The persistent context = the agent's *own* profile (cookies, logins,
;; history survive across tasks). Datomic `:browser/profile` points at it.

(defn open
  "Open an owned browser for a task: build the provider, wrap it with
  the managed (datom-persisting, live-streaming) decorator, and record
  the `:browser/*` session entity. Returns the managed IBrowser.

  opts: {:spec {…provider…} :conn :db-api :task-id :browser-id
         :start-url :live {…}}"
  [{:keys [spec conn db-api task-id browser-id start-url live]}]
  (when (and conn task-id browser-id)
    (session/open! conn db-api task-id browser-id start-url))
  (session/managed-browser
   {:inner (raw-browser spec)
    :conn conn :db-api db-api :browser-id browser-id :live live}))
