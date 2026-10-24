(ns kotoba.pkg.bonding
  "Wire bond and flip chip bonding diagram generation — pure data, no IO.

  Ported from kami-pkg (Rust) src/bonding.rs.")

;; ---------------------------------------------------------------------------
;; Bond interconnect types
;; ---------------------------------------------------------------------------

(defn wire-bond
  "Gold or copper wire bond. Diameters/heights in um."
  [wire-diameter-um loop-height-um]
  {:bond-type/kind :wire-bond
   :wire-diameter-um wire-diameter-um
   :loop-height-um loop-height-um})

(defn flip-chip
  "Solder bump flip chip. Pitch/diameter in um."
  [bump-pitch-um bump-diameter-um]
  {:bond-type/kind :flip-chip
   :bump-pitch-um bump-pitch-um
   :bump-diameter-um bump-diameter-um})

(def thermo-compression
  "Thermo-compression bonding (Cu pillar)."
  {:bond-type/kind :thermo-compression})

;; ---------------------------------------------------------------------------
;; Pad locations and bonds
;; ---------------------------------------------------------------------------

(defn pad-location
  "A die or package pad location. Coordinates in mm."
  [name x y]
  {:name name :x x :y y})

(defn bond
  "A single bond connection between a die pad and a package pad."
  [pad-name die-x die-y pkg-x pkg-y bond-type]
  {:pad-name pad-name
   :die-x die-x
   :die-y die-y
   :pkg-x pkg-x
   :pkg-y pkg-y
   :bond-type bond-type})

(defn generate-bond-diagram
  "Generate a bond diagram connecting die pads to package pads in order.

  Each die pad is matched to the corresponding package pad by index. The
  bond type is applied uniformly to all connections. Extra pads on either
  side (die-pads / pkg-pads of different lengths) are ignored, matching the
  min(die-pads, pkg-pads) truncation of the original Rust implementation."
  [die-pads pkg-pads bond-type]
  (let [n (min (count die-pads) (count pkg-pads))
        bonds (mapv (fn [i]
                      (let [d (nth die-pads i)
                            p (nth pkg-pads i)]
                        (bond (:name d) (:x d) (:y d) (:x p) (:y p) bond-type)))
                    (range n))]
    {:bonds bonds}))
