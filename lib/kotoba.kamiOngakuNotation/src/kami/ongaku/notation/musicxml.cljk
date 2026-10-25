(ns kami.ongaku.notation.musicxml
  "MusicXML-subset import/export for kami.ongaku.notation's score IR.

  This round-trips the subset the library itself emits (partwise scores
  with attributes/note/pitch/duration/type/dot/voice/tie/notations/
  dynamics/tempo-direction) — it is not a general MusicXML 4.0 conformance
  layer, and does not attempt to parse arbitrary third-party MusicXML
  files beyond that subset.

  Portable .cljc, no platform XML library — built on
  kami.ongaku.notation.xml."
  (:require [kami.ongaku.notation :as notation]
            [kami.ongaku.notation.pitch :as pitch]
            [kami.ongaku.notation.rational :as r]
            [kami.ongaku.notation.xml :as xml]))

;; 512 ticks/quarter (2048 ticks/whole) exactly represents every
;; base-type x dot-count combination this library allows (worst case:
;; 64th note with 3 dots = 15/512 of a whole note -> 60 ticks).
(def ^:private divisions-per-quarter 512)

(defn- duration->ticks [n]
  (r/->int (r/scale (notation/duration-value n) (* 4 divisions-per-quarter))))

(def ^:private articulation->tag
  {:staccato "staccato" :legato "legato" :accent "accent"
   :tenuto "tenuto" :marcato "marcato"})
(def ^:private tag->articulation (into {} (map (fn [[k v]] [v k])) articulation->tag))

(defn- xml-int [s]
  #?(:clj (Long/parseLong s)
     :cljs (js/parseInt s 10)))

;; ---------------------------------------------------------------------
;; export
;; ---------------------------------------------------------------------

(defn- single-note-xml
  [{:keys [pitch chord? ticks type dots voice tie articulations rest?]}]
  (str "      <note>\n"
       (when chord? "        <chord/>\n")
       (if rest?
         "        <rest/>\n"
         (str "        <pitch>"
              "<step>" (name (:pitch/step pitch)) "</step>"
              (when (not= 0 (:pitch/alter pitch)) (str "<alter>" (:pitch/alter pitch) "</alter>"))
              "<octave>" (:pitch/octave pitch) "</octave>"
              "</pitch>\n"))
       "        <duration>" ticks "</duration>\n"
       (when tie (str "        <tie type=\"" (name tie) "\"/>\n"))
       "        <voice>" voice "</voice>\n"
       "        <type>" (name type) "</type>\n"
       (apply str (repeat dots "        <dot/>\n"))
       (when (seq articulations)
         (str "        <notations>\n"
              "          <articulations>\n"
              (apply str (map (fn [a] (str "            <" (articulation->tag a) "/>\n")) articulations))
              "          </articulations>\n"
              "        </notations>\n"))
       "      </note>\n"))

(defn- dynamic-direction-xml [dyn]
  (str "      <direction placement=\"above\"><direction-type><dynamics><"
       (name dyn) "/></dynamics></direction-type></direction>\n"))

(defn- note-event->xml [n]
  (let [ticks (duration->ticks n)
        base {:ticks ticks :type (:note/type n) :dots (:note/dots n)
              :voice (:note/voice n) :tie (:note/tie n)
              :articulations (:note/articulations n) :rest? (:note/rest? n)}]
    (str
     (when (:note/dynamic n) (dynamic-direction-xml (:note/dynamic n)))
     (if (:note/rest? n)
       (single-note-xml base)
       (apply str (map-indexed (fn [idx p] (single-note-xml (assoc base :pitch p :chord? (pos? idx))))
                                (:note/pitches n)))))))

(defn- key-sig->xml [{:key-sig/keys [fifths mode]}]
  (str "        <key><fifths>" fifths "</fifths><mode>" (name mode) "</mode></key>\n"))

(defn- time-sig->xml [{:time-sig/keys [beats beat-type]}]
  (str "        <time><beats>" beats "</beats><beat-type>" beat-type "</beat-type></time>\n"))

(defn- tempo->xml [{:tempo/keys [bpm]}]
  (str "      <direction placement=\"above\"><direction-type><metronome>"
       "<beat-unit>quarter</beat-unit><per-minute>" bpm "</per-minute>"
       "</metronome></direction-type><sound tempo=\"" bpm "\"/></direction>\n"))

(defn- measure->xml [m]
  (str "    <measure number=\"" (:measure/number m) "\">\n"
       (when (or (:measure/key-signature m) (:measure/time-signature m))
         (str "      <attributes>\n"
              "        <divisions>" divisions-per-quarter "</divisions>\n"
              (when-let [ks (:measure/key-signature m)] (key-sig->xml ks))
              (when-let [ts (:measure/time-signature m)] (time-sig->xml ts))
              "      </attributes>\n"))
       (when-let [t (:measure/tempo m)] (tempo->xml t))
       (apply str (map note-event->xml (:measure/notes m)))
       "    </measure>\n"))

(defn- part->score-part-xml [p]
  (str "    <score-part id=\"" (xml/escape-attr (:part/id p)) "\">"
       "<part-name>" (xml/escape-text (:part/name p)) "</part-name>"
       "</score-part>\n"))

(defn- part->xml [p]
  (str "  <part id=\"" (xml/escape-attr (:part/id p)) "\">\n"
       (apply str (map measure->xml (:part/measures p)))
       "  </part>\n"))

(defn score->musicxml
  "Score IR -> MusicXML 4.0 partwise document string."
  [sc]
  (str "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
       "<!DOCTYPE score-partwise PUBLIC \"-//Recordare//DTD MusicXML 4.0 Partwise//EN\" "
       "\"http://www.musicxml.org/dtds/partwise.dtd\">\n"
       "<score-partwise version=\"4.0\">\n"
       "  <part-list>\n"
       (apply str (map part->score-part-xml (:score/parts sc)))
       "  </part-list>\n"
       (apply str (map part->xml (:score/parts sc)))
       "</score-partwise>\n"))

;; ---------------------------------------------------------------------
;; import
;; ---------------------------------------------------------------------

(defn- parse-pitch [pitch-el]
  (let [step (keyword (xml/text-content (xml/find-child pitch-el "step")))
        alter (if-let [a (xml/find-child pitch-el "alter")] (xml-int (xml/text-content a)) 0)
        octave (xml-int (xml/text-content (xml/find-child pitch-el "octave")))]
    (pitch/pitch {:step step :alter alter :octave octave})))

(defn- parse-articulations [note-el]
  (if-let [notations (xml/find-child note-el "notations")]
    (if-let [arts (xml/find-child notations "articulations")]
      (into #{} (keep (fn [c] (and (map? c) (tag->articulation (:tag c))))) (:children arts))
      #{})
    #{}))

(defn- note-el->raw
  [note-el]
  (let [rest? (some? (xml/find-child note-el "rest"))
        chord? (some? (xml/find-child note-el "chord"))
        pitch-el (xml/find-child note-el "pitch")
        voice (if-let [v (xml/find-child note-el "voice")] (xml-int (xml/text-content v)) 1)
        type (keyword (xml/text-content (xml/find-child note-el "type")))
        dots (count (xml/find-children note-el "dot"))
        tie-el (xml/find-child note-el "tie")
        tie (when tie-el (keyword (get-in tie-el [:attrs "type"])))]
    {:rest? rest? :chord? chord?
     :pitch (when pitch-el (parse-pitch pitch-el))
     :voice voice :type type :dots dots :tie tie
     :articulations (parse-articulations note-el)}))

(defn- direction-dynamic [direction-el]
  (some->> direction-el
           (#(xml/find-child % "direction-type"))
           (#(xml/find-child % "dynamics"))
           :children
           (filter map?)
           first
           :tag
           keyword))

(defn- measure-el->raw-events
  "Walk a <measure>'s children in document order, folding <chord/>-flagged
  notes into the preceding event's pitch list and attaching the nearest
  preceding <direction><dynamics> to the note event that follows it."
  [measure-el]
  (loop [children (:children measure-el) pending-dynamic nil events []]
    (if-let [c (first children)]
      (cond
        (and (map? c) (= (:tag c) "direction"))
        (recur (rest children) (or (direction-dynamic c) pending-dynamic) events)

        (and (map? c) (= (:tag c) "note"))
        (let [raw (note-el->raw c)]
          (if (:chord? raw)
            (recur (rest children) nil
                   (conj (pop events) (update (peek events) :pitches conj (:pitch raw))))
            (recur (rest children) nil
                   (conj events
                         (cond-> {:type (:type raw) :dots (:dots raw) :voice (:voice raw)
                                  :pitches (if (:rest? raw) [] [(:pitch raw)])
                                  :articulations (:articulations raw)}
                           (:tie raw) (assoc :tie (:tie raw))
                           pending-dynamic (assoc :dynamic pending-dynamic))))))

        :else (recur (rest children) pending-dynamic events))
      events)))

(defn- measure-el->measure [measure-el]
  (let [attrs-el (xml/find-child measure-el "attributes")
        ks (when-let [k (some-> attrs-el (xml/find-child "key"))]
             {:fifths (xml-int (xml/text-content (xml/find-child k "fifths")))
              :mode (keyword (or (some-> (xml/find-child k "mode") xml/text-content) "major"))})
        ts (when-let [t (some-> attrs-el (xml/find-child "time"))]
             {:beats (xml-int (xml/text-content (xml/find-child t "beats")))
              :beat-type (xml-int (xml/text-content (xml/find-child t "beat-type")))})
        tempo-el (some-> measure-el (xml/find-child "direction") (xml/find-child "direction-type") (xml/find-child "metronome"))
        tempo (when tempo-el {:bpm (xml-int (xml/text-content (xml/find-child tempo-el "per-minute")))})
        notes (mapv notation/note (measure-el->raw-events measure-el))
        number (xml-int (get-in measure-el [:attrs "number"]))]
    (notation/measure (cond-> {:number number :notes notes}
                         ts (assoc :time-sig ts)
                         ks (assoc :key-sig ks)
                         tempo (assoc :tempo tempo)))))

(defn- part-el->part [part-el name-by-id]
  (let [id (get-in part-el [:attrs "id"])]
    (notation/part {:id id
                     :name (name-by-id id)
                     :measures (mapv measure-el->measure (xml/find-children part-el "measure"))})))

(defn musicxml->score
  "MusicXML document string -> score IR."
  [xml-str]
  (let [root (xml/parse xml-str)
        name-by-id (into {}
                          (map (fn [sp] [(get-in sp [:attrs "id"])
                                         (xml/text-content (xml/find-child sp "part-name"))]))
                          (xml/find-children (xml/find-child root "part-list") "score-part"))]
    (notation/score {:parts (mapv #(part-el->part % name-by-id) (xml/find-children root "part"))})))
