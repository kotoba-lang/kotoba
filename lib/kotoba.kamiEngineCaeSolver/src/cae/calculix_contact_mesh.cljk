(ns cae.calculix-contact-mesh
  "Generate paired structured C3D8 blocks for contact-pressure mesh studies."
  (:require [kotoba.lang.text :as str]))

(defn- nid [n offset layer i j]
  (+ offset 1 (* layer (inc n) (inc n)) (* i (inc n)) j))

(defn- csv [xs] (str/join ", " xs))
(defn- set-lines [xs] (map csv (partition-all 16 xs)))

(defn contact-blocks-input
  [{:keys [divisions gap compression tilt youngs-modulus poisson-ratio penalty]
    :or {gap 0.1 compression 0.1 tilt 0.05 youngs-modulus 210000.0
         poisson-ratio 0.3 penalty 2100000.0}}]
  (when-not (pos? divisions) (throw (ex-info "positive contact divisions required" {:divisions divisions})))
  (let [n divisions nodes-per-block (* 2 (inc n) (inc n)) elems-per-block (* n n)
        block-nodes (fn [offset z0]
                      (for [layer (range 2) i (range (inc n)) j (range (inc n))]
                        [(nid n offset layer i j) (/ (double i) n) (/ (double j) n) (+ z0 layer)]))
        lower-nodes (block-nodes 0 0.0) upper-nodes (block-nodes nodes-per-block (+ 1.0 gap))
        block-elements
        (fn [node-offset element-offset]
          (for [i (range n) j (range n)]
            [(+ element-offset 1 (* i n) j)
             (nid n node-offset 0 i j) (nid n node-offset 0 (inc i) j)
             (nid n node-offset 0 (inc i) (inc j)) (nid n node-offset 0 i (inc j))
             (nid n node-offset 1 i j) (nid n node-offset 1 (inc i) j)
             (nid n node-offset 1 (inc i) (inc j)) (nid n node-offset 1 i (inc j))]))
        lower-elements (block-elements 0 0) upper-elements (block-elements nodes-per-block elems-per-block)
        all-nodes (map first (concat lower-nodes upper-nodes))
        base (for [i (range (inc n)) j (range (inc n))] (nid n 0 0 i j))
        top (for [i (range (inc n)) j (range (inc n))] (nid n nodes-per-block 1 i j))
        displacement (fn [i] (- (- compression) (* tilt (- (/ (double i) n) 0.5))))
        lines (concat
               ["*HEADING" "Kotoba CAE tilted compression contact-pressure mesh study" "*NODE"]
               (map csv (concat lower-nodes upper-nodes))
               ["*ELEMENT, TYPE=C3D8, ELSET=BLOCKS"] (map csv (concat lower-elements upper-elements))
               ["*NSET, NSET=ALL"] (set-lines all-nodes)
               ["*NSET, NSET=BASE"] (set-lines base)
               ["*NSET, NSET=TOP"] (set-lines top)
               ["*SOLID SECTION, ELSET=BLOCKS, MATERIAL=STEEL" "*MATERIAL, NAME=STEEL"
                "*ELASTIC" (csv [youngs-modulus poisson-ratio])
                "*SURFACE, NAME=LOWER_TOP, TYPE=ELEMENT"]
               (map #(str (first %) ", S2") lower-elements)
               ["*SURFACE, NAME=UPPER_BOTTOM, TYPE=ELEMENT"]
               (map #(str (first %) ", S1") upper-elements)
               ["*SURFACE INTERACTION, NAME=CONTACT" "*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR"
                (csv [penalty 3.0])
                "*CONTACT PAIR, INTERACTION=CONTACT, TYPE=SURFACE TO SURFACE"
                "UPPER_BOTTOM, LOWER_TOP" "*BOUNDARY" "ALL, 1, 2, 0." "BASE, 3, 3, 0."]
               (for [i (range (inc n)) j (range (inc n))]
                 (csv [(nid n nodes-per-block 1 i j) 3 3 (displacement i)]))
               ["*STEP, NLGEOM=YES, INC=200" "*STATIC" "0.02, 1., 1.e-6, 0.05"
                "*NODE PRINT, NSET=TOP, TOTALS=YES" "U, RF"
                "*CONTACT PRINT, SLAVE=UPPER_BOTTOM, MASTER=LOWER_TOP" "CSTR, CFN"
                "*CONTACT FILE" "CSTR" "*END STEP"])]
    {:input (str (str/join "\n" lines) "\n") :divisions n
     :nodes (* 2 nodes-per-block) :elements (* 2 elems-per-block)
     :contact-faces elems-per-block :top-nodes (count top)}))
