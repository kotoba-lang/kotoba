(ns loop-game-autoplay.env
  "One episode of the real game, in a real browser, as a promise of a fitness.

  The episode runs *inside the page*: `__autoplay.episode` drives the game's
  own `update()` at a fixed step with no rendering and no clock. One CDP round
  trip per episode instead of one per frame -- a 90-second episode is 4,500
  steps, and paying a round trip for each would make the search 3 orders of
  magnitude slower than the physics it is searching over.

  What this buys, and what it costs: the game is completely unmodified, so
  what is being optimised is the shipped artefact rather than a reimplemented
  model of it. In exchange every episode carries a browser's worth of
  overhead, which is why episodes are capped in simulated time rather than
  run to the 15-minute win condition during search."
  (:require ["playwright" :as pw]
            ["fs" :as fs]
            [loop-game-autoplay.policy :as policy]))

(def ^:private system-chrome
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

(defn launch!
  "Launch a Chromium. Headless by default; `:headed? true` shows the window,
  which is occasionally the only way to see why an episode returns nothing.

  Falls back to the system Google Chrome when Playwright's own browser is not
  installed. This is not a nicety: on a machine running many agent sessions
  the shared `ms-playwright` cache is regularly mid-download behind a
  `__dirlock`, and a training run that dies because a *download* is in
  progress is a bad failure. Both are Chromium and both run the same driver;
  the receipt records which one was used."
  [{:keys [headed? executable] :or {headed? false}}]
  (let [opts #js {:headless (not headed?)}]
    (when executable (set! (.-executablePath opts) executable))
    (-> (.launch (.-chromium pw) opts)
        (.catch (fn [e]
                  (if (or executable (not (fs/existsSync system-chrome)))
                    (js/Promise.reject e)
                    (do (println "playwright browser unavailable; falling back to system Chrome")
                        (.launch (.-chromium pw)
                                 #js {:headless (not headed?)
                                      :executablePath system-chrome}))))))))

(defn open-page!
  "A page with the driver loaded and the game's globals present."
  [browser url]
  (-> (.newPage browser)
      (.then (fn [page]
               (-> (.goto page url #js {:waitUntil "load"})
                   (.then (fn [_] (.waitForFunction page "window.__autoplay && typeof update === 'function'"
                                                    nil #js {:timeout 15000})))
                   (.then (fn [_] page)))))))

(def ^:private js-episode
  "A real JS function, not a string.

  Playwright accepts a string page function, but a string like
  `\"([w,b]) => ...\"` is evaluated as an *expression* here: it produces the
  arrow function itself, which serializes to `undefined`, and every call
  quietly returns nil. Nothing errors -- the search just scores every genome
  as nothing. `js/Function` removes the ambiguity."
  (js/Function "a" "return window.__autoplay.episode({w: a[0], b: a[1]}, a[2], a[3]);"))

(defn episode!
  "Run one episode. Returns a promise of the driver's result map, with
  `:fitness` already computed in-page.

  `seed` fixes the game's randomness, so two genomes are compared on the
  *same* enemy waves -- without that, a generation's ranking is mostly a
  ranking of luck."
  [page genome seed max-sim-ms]
  (let [p (policy/genome->policy genome)]
    (-> (.evaluate page js-episode (clj->js [(:w p) (:b p) seed max-sim-ms]))
        (.then (fn [res] (js->clj res :keywordize-keys true))))))

(defn evaluate-genome!
  "Mean fitness over `seeds`. A single seed rewards a policy that happens to
  match one wave pattern; the mean is what makes the score a property of the
  policy."
  [page genome seeds max-sim-ms]
  (let [step (fn step [remaining acc]
               (if (empty? remaining)
                 (js/Promise.resolve (/ acc (count seeds)))
                 (-> (episode! page genome (first remaining) max-sim-ms)
                     (.then (fn [r] (step (rest remaining) (+ acc (:fitness r))))))))]
    (step seeds 0.0)))
