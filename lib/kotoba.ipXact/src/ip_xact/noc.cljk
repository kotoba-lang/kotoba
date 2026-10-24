(ns ip-xact.noc
  "Network-on-Chip topology synthesis and router generation. Restored
  from kami-ip's `noc` module (deleted PR #82). Has its own
  `port-directions` set (north/south/east/west/local), distinct from
  `ip-xact.component/port-directions` (in/out/in-out) — matches the
  original's two separately-scoped `PortDirection` enums in different
  Rust modules.")

;; NocTopology variants
(defn mesh-topology [rows cols] {:kind :mesh :rows rows :cols cols})
(defn ring-topology [nodes] {:kind :ring :nodes nodes})
(defn crossbar-topology [ports] {:kind :crossbar :ports ports})
(defn tree-topology [levels] {:kind :tree :levels levels})

(def port-directions #{:north :south :east :west :local})
(def routing-algorithms #{:xy :west-first :odd-even})

(defn noc-port [direction bandwidth-gbps latency-cycles]
  {:direction direction :bandwidth-gbps bandwidth-gbps :latency-cycles latency-cycles})

(defn noc-config [topology data-width flit-size routing]
  {:topology topology :data-width data-width :flit-size flit-size :routing routing})

(defn noc-router [id x y ports] {:id id :x x :y y :ports (vec ports)})
(defn noc-link [src-id dst-id bandwidth-gbps] {:src-id src-id :dst-id dst-id :bandwidth-gbps bandwidth-gbps})

(defn noc-design [routers links total-area-um2 estimated-latency-cycles]
  {:routers (vec routers) :links (vec links) :total-area-um2 total-area-um2
   :estimated-latency-cycles estimated-latency-cycles})

(defn- generate-mesh [config]
  (let [rows (:rows (:topology config))
        cols (:cols (:topology config))
        data-width (:data-width config)
        link-bw (double data-width)
        link-latency 1]
    (let [[routers links]
          (reduce
           (fn [[routers links] [r c]]
             (let [id (+ (* r cols) c)
                   ports0 [(noc-port :local link-bw 0)]
                   [ports links] (if (> r 0)
                                   [(conj ports0 (noc-port :north link-bw link-latency))
                                    (conj links (noc-link id (+ (* (dec r) cols) c) link-bw))]
                                   [ports0 links])
                   ports (if (< r (dec rows)) (conj ports (noc-port :south link-bw link-latency)) ports)
                   [ports links] (if (> c 0)
                                   [(conj ports (noc-port :west link-bw link-latency))
                                    (conj links (noc-link id (+ (* r cols) (dec c)) link-bw))]
                                   [ports links])
                   ports (if (< c (dec cols)) (conj ports (noc-port :east link-bw link-latency)) ports)]
               [(conj routers (noc-router id c r ports)) links]))
           [[] []]
           (for [r (range rows) c (range cols)] [r c]))
          total-ports (reduce + 0 (map (comp count :ports) routers))
          area (* total-ports 5000.0 (/ (double data-width) 32.0))
          diameter (+ (dec rows) (dec cols))]
      (noc-design routers links area (+ (* diameter link-latency) 1)))))

(defn- generate-ring [config]
  (let [nodes (:nodes (:topology config))
        data-width (:data-width config)
        link-bw (double data-width)
        link-latency 1
        [routers links]
        (reduce
         (fn [[routers links] i]
           (let [ports [(noc-port :local link-bw 0)
                        (noc-port :east link-bw link-latency)
                        (noc-port :west link-bw link-latency)]]
             [(conj routers (noc-router i i 0 ports))
              (conj links (noc-link i (mod (inc i) nodes) link-bw))]))
         [[] []]
         (range nodes))
        area (* nodes 3.0 5000.0 (/ (double data-width) 32.0))
        diameter (quot nodes 2)]
    (noc-design routers links area (+ (* diameter link-latency) 1))))

(defn- generate-crossbar [config]
  (let [ports-n (:ports (:topology config))
        data-width (:data-width config)
        link-bw (double data-width)
        [routers links]
        (reduce
         (fn [[routers links] i]
           (let [r-ports [(noc-port :local link-bw 0)]
                 links (reduce (fn [links j] (if (not= i j) (conj links (noc-link i j link-bw)) links))
                                links (range ports-n))]
             [(conj routers (noc-router i i 0 r-ports)) links]))
         [[] []]
         (range ports-n))
        area (* (Math/pow ports-n 2) 3000.0 (/ (double data-width) 32.0))]
    (noc-design routers links area 2)))

(defn- ilog2 [x]
  (loop [x x n 0] (if (<= x 1) n (recur (quot x 2) (inc n)))))

(defn- generate-tree [config]
  (let [levels (:levels (:topology config))
        data-width (:data-width config)
        link-bw (double data-width)
        link-latency 1
        total-nodes (dec (bit-shift-left 1 levels))
        [routers links]
        (reduce
         (fn [[routers links] i]
           (let [level (ilog2 (inc i))
                 ports [(noc-port :local link-bw 0) (noc-port :north link-bw link-latency)]
                 links (if (> i 0) (conj links (noc-link i (quot (dec i) 2) link-bw)) links)]
             [(conj routers (noc-router i i level ports)) links]))
         [[] []]
         (range total-nodes))
        area (* total-nodes 2.0 5000.0 (/ (double data-width) 32.0))]
    (noc-design routers links area (* 2 levels))))

(defn generate-noc
  "Generate a NoC design from `config`: creates routers and links
  according to the topology, then estimates area and latency from data
  width, flit size, and topology diameter."
  [config]
  (case (:kind (:topology config))
    :mesh (generate-mesh config)
    :ring (generate-ring config)
    :crossbar (generate-crossbar config)
    :tree (generate-tree config)))
