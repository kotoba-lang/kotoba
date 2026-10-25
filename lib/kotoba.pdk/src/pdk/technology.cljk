(ns pdk.technology
  "Semiconductor technology node + design-rule tech file. Restored from
  kami-pdk's `technology` module (kami-engine/kami-pdk/src/lib.rs, deleted
  PR #82).")

(def nodes [:n180 :n130 :n90 :n65 :n45 :n28 :n22 :n16 :n14 :n10 :n7 :n5 :n3 :n2])

(defn feature-nm
  "Feature size in nanometres for technology node `node`."
  [node]
  (case node
    :n180 180 :n130 130 :n90 90 :n65 65 :n45 45 :n28 28
    :n22 22 :n16 16 :n14 14 :n10 10 :n7 7 :n5 5 :n3 3 :n2 2))

(def layer-types #{:diffusion :poly :metal :via :implant :well})

(defn layer-def [{:keys [name gds-number gds-datatype layer-type]}]
  {:name name :gds-number gds-number :gds-datatype gds-datatype :layer-type layer-type})

(defn get-min-width [tech-file layer] (get-in tech-file [:min-width layer]))
(defn get-min-spacing [tech-file layer] (get-in tech-file [:min-spacing layer]))

(defn metal-pitch
  "Metal pitch (min-width + min-spacing) for metal layer number `layer-num`,
  or nil if that layer isn't defined."
  [tech-file layer-num]
  (let [key (str "metal" layer-num)
        w (get-in tech-file [:min-width key])
        s (get-in tech-file [:min-spacing key])]
    (when (and w s) (+ w s))))

(defn for-node
  "A representative tech file for common nodes: metal-layer count scaled by
  node generation, min-width/spacing scaled from feature size, and a
  representative GDS layer map."
  [node]
  (let [feat (/ (feature-nm node) 1000.0) ; µm
        num-metals (case node
                     (:n180 :n130) 6
                     (:n90 :n65) 8
                     (:n45 :n28) 9
                     12)
        metal-entries (for [i (range 1 (inc num-metals))]
                        (let [key (str "metal" i)
                              w (* feat (+ 1.0 (* 0.1 i)))]
                          [key w (* w 0.8)]))
        min-width (into {"poly" feat "diffusion" (* feat 1.5)}
                         (map (fn [[k w _]] [k w]) metal-entries))
        min-spacing (into {"poly" (* feat 1.2) "diffusion" (* feat 1.5)}
                           (map (fn [[k _ s]] [k s]) metal-entries))
        layer-map [(layer-def {:name "nwell" :gds-number 1 :gds-datatype 0 :layer-type :well})
                   (layer-def {:name "diffusion" :gds-number 2 :gds-datatype 0 :layer-type :diffusion})
                   (layer-def {:name "poly" :gds-number 3 :gds-datatype 0 :layer-type :poly})
                   (layer-def {:name "metal1" :gds-number 10 :gds-datatype 0 :layer-type :metal})
                   (layer-def {:name "via1" :gds-number 11 :gds-datatype 0 :layer-type :via})
                   (layer-def {:name "metal2" :gds-number 12 :gds-datatype 0 :layer-type :metal})]]
    {:node node :num-metal-layers num-metals :min-width min-width
     :min-spacing min-spacing :grid-unit-nm (/ (feature-nm node) 4.0) :layer-map layer-map}))
