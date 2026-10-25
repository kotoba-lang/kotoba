(ns loop-game-autoplay.server
  "Serves an unmodified game page with the agent driver injected.

  One server for both consumers, on purpose:

  - **Playwright** (training) loads it and calls `__autoplay.episode` over CDP.
  - **Safari on a booted iOS Simulator** (qualification) loads the *same* URL
    via `simctl openurl`, where there is no eval channel at all -- so the page
    has to start itself from the query string.

  If the two paths loaded different pages, the thing qualified on the phone
  would not be the thing that was trained."
  (:require ["http" :as http]
            ["fs" :as fs]
            ["path" :as path]
            [kotoba.lang.text :as str]))

(def ^:private driver-path
  (path/join (js/process.cwd) "resources" "autoplay-driver.js"))

(defn inject
  "Insert the driver script tag immediately before </body>.

  Appending rather than prepending matters: the game's classic <script>
  declares `G`, `keys` and `update` as top-level `let`/`const`/`function`, and
  those bindings only exist once that script has run."
  [html]
  (let [tag "<script src=\"/autoplay-driver.js\"></script>"]
    (if (str/includes? html "</body>")
      (str/replace html "</body>" (str tag "\n</body>"))
      (str html tag))))

(defn start!
  "Start the server. Returns a promise of `{:server :port :url :results}`.

  `:results` is an atom the page appends its own run outcomes to via
  `POST /result` -- the only channel back from Safari on a booted Simulator,
  where there is no remote eval.

  Port 0 asks the OS for a free port; a fixed port would collide with the
  other agent sessions running on this machine."
  [{:keys [game-file port] :or {port 0}}]
  (let [results (atom [])]
    (js/Promise.
     (fn [resolve reject]
       (let [html (inject (fs/readFileSync game-file "utf8"))
             driver (fs/readFileSync driver-path "utf8")
             srv (http/createServer
                  (fn [req res]
                    (let [url (or (.-url req) "/")]
                      (cond
                        (str/starts-with? url "/autoplay-driver.js")
                        (do (.writeHead res 200 #js {"Content-Type" "application/javascript"
                                                     "Cache-Control" "no-store"})
                            (.end res driver))

                        (str/starts-with? url "/result")
                        (let [chunks (atom "")]
                          (.on req "data" (fn [c] (swap! chunks str c)))
                          (.on req "end"
                               (fn []
                                 (swap! results conj
                                        (try (js->clj (js/JSON.parse @chunks) :keywordize-keys true)
                                             (catch :default e {:parse-error (str e) :raw @chunks})))
                                 (.writeHead res 204 #js {"Access-Control-Allow-Origin" "*"})
                                 (.end res))))

                        (str/starts-with? url "/health")
                        (do (.writeHead res 200 #js {"Content-Type" "text/plain"})
                            (.end res "ok"))

                        :else
                        (do (.writeHead res 200 #js {"Content-Type" "text/html; charset=utf-8"
                                                     "Cache-Control" "no-store"})
                            (.end res html))))))]
       (.on srv "error" reject)
       ;; 0.0.0.0, not 127.0.0.1: the Simulator reaches the host over the LAN
       ;; interface for anything other than plain localhost, and binding only
       ;; to loopback is the failure that looks like "the phone has no network".
       (.listen srv port "0.0.0.0"
                (fn []
                  (let [p (.-port (.address srv))]
                    (resolve {:server srv :port p
                              :url (str "http://127.0.0.1:" p "/")
                              :results results})))))))))

(defn stop! [{:keys [server]}]
  (js/Promise. (fn [resolve] (.close server (fn [] (resolve true))))))
