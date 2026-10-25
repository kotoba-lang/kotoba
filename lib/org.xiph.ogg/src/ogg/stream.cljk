(ns ogg.stream
  "Logical bitstreams: packet reassembly across pages, and page generation.

   An Ogg *physical* stream carries one or more *logical* streams, distinguished
   by serial number and interleaved page by page — that is how one file holds
   video and audio, and how chained streams work. Reassembly is therefore per
   serial, not per file.

   A packet may span pages, so the bytes of an unfinished packet (a page's
   `:tail`) are carried forward and joined with the next page of the *same
   serial*, which must set the continued flag. A pending tail followed by a page
   that does not set that flag means pages were lost, and the partial packet is
   dropped rather than handed to a codec as if it were whole."
  (:require [ogg.page :as page]))

(defn- reassemble
  "Join the packets of one serial's pages, carrying tails across page
   boundaries."
  [own]
  (loop [pgs (seq own) pending [] packets [] granules []]
    (if-not pgs
      {:packets packets :granules granules}
      (let [p (first pgs)
            complete (:packets p)
            joined (if (and (:continued? p) (seq pending) (seq complete))
                     (into [(into pending (first complete))] (subvec complete 1))
                     complete)
            pending' (if (and (:continued? p) (empty? complete))
                       (into pending (:tail p))
                       (vec (:tail p)))]
        (recur (next pgs)
               pending'
               (into packets joined)
               (if (= :none (:granule p)) granules (conj granules (:granule p))))))))

(defn logical-streams
  "Group `data`'s pages by serial number, in first-appearance order →

       [{:serial n :packets [[bytes] ...] :granules [...] :pages n
         :bos? bool :eos? bool} ...]"
  ([data] (logical-streams data {}))
  ([data opts]
   (let [ps (page/pages data opts)]
     (mapv (fn [serial]
             (let [own (filterv #(= serial (:serial %)) ps)
                   {:keys [packets granules]} (reassemble own)]
               {:serial serial
                :packets packets
                :granules granules
                :pages (count own)
                :bos? (boolean (:bos? (first own)))
                :eos? (boolean (:eos? (last own)))}))
           (distinct (map :serial ps))))))

(defn packets
  "Every packet of the first logical stream, or of `serial` when given."
  ([data] (packets data nil))
  ([data serial]
   (let [ls (logical-streams data)
         s (if serial (first (filter #(= serial (:serial %)) ls)) (first ls))]
     (when-not s
       (throw (ex-info "ogg: no such logical stream"
                       {:reason :no-such-stream :serial serial
                        :available (mapv :serial ls)})))
     (:packets s))))

(def ^:private max-lacing 255)

(defn build
  "Serialise `packets` as one logical stream → a vector of unsigned bytes.

       (build {:serial 1 :packets [[..] [..]] :granules [0 960]})

   Packets are packed into pages up to the 255-lacing-value limit, and a packet
   too large for the remaining budget is **split across pages** — the page ends
   on a 255 segment with no terminator and the next page sets the continued flag.
   Without that, no packet above 65,025 bytes could be written at all, and a
   Vorbis setup header can exceed it.

   A page whose last packet is incomplete carries the reserved granule -1, as
   the format requires: the granule position means *a packet ends here*.

   `:granules` gives the granule position of the page each packet ends on,
   positionally. The first page is marked bos and the last eos.

   `:flush-after` is a set of packet indices after which a page must end.
   **Codec mappings, not the container, decide where pages break** — Opus (RFC
   7845 §3) requires its ID header alone on the first page and its comment header
   on its own page, and a muxer that packs greedily produces a file ffmpeg
   refuses. This layer does not know those rules, so it exposes the control
   rather than guessing."
  [{:keys [serial packets granules flush-after]
    :or {serial 1 granules [] flush-after #{}}}]
  (let [n (count packets)]
    (loop [i 0                    ; next packet index
           offset 0               ; bytes of packet i already written
           out []
           seq-no 0
           segments []            ; this page's lacing values
           body []                ; this page's bytes
           granule 0              ; granule of the last packet that ended here
           complete? true         ; did a packet end on this page?
           continued? false]      ; does this page continue one?
      (letfn [(emit [eos?]
                (page/build-raw {:segments segments :body body
                                 :serial serial :sequence seq-no
                                 ;; -1 when no packet ends on this page
                                 :granule (if complete? granule :none)
                                 :bos? (zero? seq-no) :eos? eos?
                                 :continued? continued?}))]
        (cond
          (= i n)
          (cond
            (seq segments) (into out (emit true))
            ;; a stream with no packets at all still needs one page to exist
            (zero? seq-no) (into out (page/build-raw {:segments [0] :body []
                                                      :serial serial :sequence 0
                                                      :granule 0 :bos? true :eos? true}))
            :else out)

          ;; no room left for even one more segment
          (= (count segments) max-lacing)
          (recur i offset (into out (emit false)) (inc seq-no)
                 [] [] granule false (pos? offset))

          :else
          (let [pkt (nth packets i)
                remaining (- (count pkt) offset)
                budget (- max-lacing (count segments))
                needed (inc (quot remaining 255))]
            (if (<= needed budget)
              ;; the rest of this packet fits, terminator included
              (let [granule' (if (< i (count granules)) (nth granules i) granule)
                    segments' (into segments (concat (repeat (quot remaining 255) 255)
                                                     [(rem remaining 255)]))
                    body' (into body (subvec pkt offset))]
                (if (contains? flush-after i)
                  (recur (inc i) 0
                         (into out (page/build-raw
                                    {:segments segments' :body body'
                                     :serial serial :sequence seq-no
                                     :granule granule'
                                     :bos? (zero? seq-no) :eos? (= (inc i) n)
                                     :continued? continued?}))
                         (inc seq-no) [] [] granule' true false)
                  (recur (inc i) 0 out seq-no segments' body' granule' true continued?)))
              ;; split: fill the page with whole 255-byte segments and continue
              (let [take-bytes (* 255 budget)]
                (recur i (+ offset take-bytes)
                       (into out (page/build-raw
                                  {:segments (into segments (repeat budget 255))
                                   :body (into body (subvec pkt offset (+ offset take-bytes)))
                                   :serial serial :sequence seq-no
                                   :granule (if complete? granule :none)
                                   :bos? (zero? seq-no) :eos? false
                                   :continued? continued?}))
                       (inc seq-no) [] [] granule false true)))))))))
