(ns browseragent.browser.session
  "The agent's *owned* browser session, persisted as datoms.

  `managed-browser` decorates any `IBrowser` (the mock, Playwright,
  in-browser, an MCP) so that every navigation updates a `:browser/*`
  entity in the store and streams a frame to the live view. The agent
  thus *owns* a browser with a durable profile/tab state you can query
  and time-travel, instead of driving a throwaway page.

  Decoration, not reimplementation: browser-use-clj keeps `IBrowser`
  pure (mock stays mock); this layer adds ownership + observability on
  top, exactly the com-junkawasaki ↔ browser-use-clj boundary in
  ADR-2606250956."
  (:require [browseruse.browser :as b]
            [browseragent.browser.live :as live]
            [langchain.db :as db]))

(defn open!
  "Create (or reopen) an owned browser session entity for a task.
  Returns the browser-id."
  [conn db-api task-id browser-id start-url]
  ((:transact! db-api) conn
   [{:browser/id browser-id
     :browser/task [:task/id task-id]
     :browser/profile (str "profile/" browser-id)
     :browser/current (str start-url)
     :browser/tabs (pr-str [start-url])
     :browser/status :open}])
  browser-id)

(defn- persist-state! [{:keys [conn db-api browser-id]} {:keys [url]}]
  (when (and conn browser-id)
    ((:transact! db-api) conn
     [{:browser/id browser-id
       :browser/current (str url)
       :browser/tabs (pr-str [url])
       :browser/status :open}])))

(defn- observe! [ctx state]
  (persist-state! ctx state)
  (live/frame (:live ctx) state)
  state)

(defn managed-browser
  "Wrap an inner IBrowser with ownership (datoms) + live frames.

  ctx: {:inner IBrowser :conn conn :db-api api :browser-id \"…\"
        :live {:emit-fn … :screenshot-fn …}}"
  [{:keys [inner] :as ctx}]
  (let [ctx (update ctx :db-api #(or % db/api))]
    (reify b/IBrowser
      (-navigate! [_ url] (observe! ctx (b/-navigate! inner url)))
      (-click! [_ i]      (observe! ctx (b/-click! inner i)))
      (-input-text! [_ i text] (observe! ctx (b/-input-text! inner i text)))
      (-scroll! [_ dir]   (observe! ctx (b/-scroll! inner dir)))
      (-back! [_]         (observe! ctx (b/-back! inner)))
      (-state [_]         (b/-state inner)))))

(defn close!
  [conn db-api browser-id]
  ((:transact! db-api) conn [{:browser/id browser-id :browser/status :closed}]))

(defn session
  "Pull the current owned-browser session entity."
  [conn db-api browser-id]
  ((:pull db-api) ((:db db-api) conn)
   [:browser/id :browser/current :browser/tabs :browser/status :browser/profile]
   [:browser/id browser-id]))
