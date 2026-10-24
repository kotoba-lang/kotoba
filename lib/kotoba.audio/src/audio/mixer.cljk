(ns audio.mixer
  "KAMI Audio offline mixer bus graph (Wave 2, ADR-2607121400
  `com-junkawasaki/root`) — the L2 executor's answer to
  `kami-ongaku-project`'s L3 bus-graph data model: this namespace
  actually *renders* such a graph to a stereo sample buffer (offline,
  not realtime).

  Shape (kept intentionally close to kami-ongaku-project's bus/track
  shape, no hard dependency):
    tracks  {track-id {:buffer [mono doubles] :gain double :pan double}}
             :pan in [-1.0 (hard left) .. 1.0 (hard right)], equal-power.
    buses   {bus-id   {:inputs #{track-id-or-bus-id ...} :gain double}}
    master  bus-id — the bus whose rendered output is returned.

  A bus may receive from other buses (a real graph, not a flat list) —
  `find-cycle` walks bus-to-bus edges only (tracks are always leaves)
  and must be run before rendering; `render-bus-graph` does not
  itself guard against infinite recursion.")

(defn find-cycle
  "Returns a vector `[a b ...]` describing a cycle in `buses`' bus-to-bus
  input graph, or nil if acyclic. `buses` as in the namespace docstring."
  [buses]
  (let [bus-ids (set (keys buses))]
    (letfn [(dfs [node path visited]
              (if (some #{node} path)
                (conj (vec (drop-while #(not= % node) path)) node)
                (if (visited node)
                  nil
                  (let [inputs (filter bus-ids (get-in buses [node :inputs]))]
                    (some #(dfs % (conj path node) (conj visited node)) inputs)))))]
      (some #(dfs % [] #{}) bus-ids))))

(defn- pan-gains
  "Equal-power pan gains `[left right]` for `pan` in [-1.0, 1.0]."
  [pan]
  (let [theta (* (/ (+ pan 1.0) 2.0) (/ Math/PI 2.0))]
    [(Math/cos theta) (Math/sin theta)]))

(defn- mono->stereo [buffer gain pan]
  (let [[lg rg] (pan-gains pan)]
    (mapv (fn [s] [(* s gain lg) (* s gain rg)]) buffer)))

(defn- sum-stereo
  "Elementwise-sum stereo buffers (vectors of [l r]), zero-padding
  shorter buffers to the longest one's length."
  [buffers]
  (if (empty? buffers)
    []
    (let [n (apply max (map count buffers))]
      (mapv (fn [i]
              (reduce (fn [[al ar] buf]
                        (let [[l r] (get buf i [0.0 0.0])]
                          [(+ al l) (+ ar r)]))
                      [0.0 0.0]
                      buffers))
            (range n)))))

(defn render-bus-graph
  "Renders `master` bus of `{:tracks :buses :master}` to a stereo
  buffer (vector of `[l r]` pairs). Caller must have already checked
  `(find-cycle buses)` is nil."
  [{:keys [tracks buses master]}]
  (letfn [(render [node]
            (if-let [track (get tracks node)]
              (mono->stereo (:buffer track) (:gain track 1.0) (:pan track 0.0))
              (let [bus (get buses node)
                    inputs (mapv render (:inputs bus))
                    summed (sum-stereo inputs)
                    g (:gain bus 1.0)]
                (mapv (fn [[l r]] [(* l g) (* r g)]) summed))))]
    (render master)))
