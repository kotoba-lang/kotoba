(ns kotobase.storage.pack-plan
  "The pure half of a packed read: which ranges to ask for, and how to turn a
  window of bytes back into blocks.

  It is a separate namespace because there are two drivers — a synchronous
  one for the JVM and a Promise-returning one for a Worker — and the only
  thing that differs between them is the fetch. Everything that decides
  *what* to fetch, and everything that verifies what came back, is here and
  is shared. Two copies of a coalescing rule is two coalescing rules."
  (:require [ipld.car.bytes :as b]
            [ipld.car.v2 :as v2]))

(def zero-stats
  "The counters a store starts with, and the shape `reset-stats!` restores.

  `:blocks-served` is the evidence floor. Without it `{:requests 0}` is what
  a perfectly efficient read and a read that never happened both look like,
  and the second is the one that happens when a catalog lookup silently
  returns nothing. A reader that has served no blocks has not proved
  anything about round trips, whatever the request count says — so the
  denominator is reported next to the numerator, always.

  `:packs-missing` and `:frames-short` are the same floor for the two ways
  the object store can under-deliver. Both used to be invisible: a pack that
  was not there and a pack that was there but ended early both produced a
  read that simply returned fewer blocks, which is also what a correct read
  of a catalog holding fewer entries produces. Counting them is what makes
  `:evidence` able to say `:degraded` — the reading that says these numbers
  are not a measurement of anything."
  {:requests 0 :bytes-fetched 0 :cache-hits 0 :blocks-served 0
   :packs-missing 0 :frames-short 0})

(defn summarise
  "Add the derived reading to raw counters, including the two cases a caller
  must not mistake for a good result.

  `:evidence` is `:degraded` whenever the object store failed to deliver
  something the catalog said was there, EVEN IF blocks were served. A read
  that returned 99 of 100 blocks and one truncated pack is not a 99-block
  success — it is a read whose request count means nothing, because the
  missing round trip was never made."
  [counters]
  (let [under-delivered? (or (pos? (:packs-missing counters 0))
                             (pos? (:frames-short counters 0)))]
    (assoc counters
           :requests-per-block (when (pos? (:blocks-served counters))
                                 (/ (:requests counters)
                                    (:blocks-served counters)))
           :evidence (cond under-delivered? :degraded
                           (pos? (:blocks-served counters)) :served
                           :else :nothing-served))))

(def default-options
  {:window-bytes 1048576   ; read-ahead ceiling for one request
   :max-gap-bytes 65536    ; coalesce two wanted frames across a gap this big
   :cache-bytes 8388608})  ; total held windows before the oldest is dropped

(defn plan-runs
  "Group located entries of ONE pack into coalesced runs.

  `[{:file-offset n :frame-length n} ...]` →
  `[{:run-start n :run-end n :wanted [...]} ...]`"
  [located max-gap]
  (let [sorted (sort-by :file-offset located)]
    (reduce
     (fn [acc {:keys [file-offset frame-length] :as e}]
       (let [end (+ file-offset frame-length)
             {:keys [run-end] :as last-run} (peek acc)]
         (if (and last-run (<= (- file-offset run-end) max-gap))
           (conj (pop acc) (-> last-run
                               (assoc :run-end (max run-end end))
                               (update :wanted conj e)))
           (conj acc {:run-start file-offset :run-end end :wanted [e]}))))
     []
     sorted)))

(defn window-request
  "The byte range to actually ask for, given a run and a read-ahead ceiling.

  The window extends the request FORWARD — never backward — because the
  chain this exists for runs forward, and extending backward would fetch
  what the caller has already passed."
  [{:keys [run-start run-end]} window-bytes]
  (let [want (- run-end run-start)]
    {:start run-start
     :end (max run-end (+ run-start (max want window-bytes)))}))

(defn window-mismatch
  "Why a range response cannot be the range that was asked for, or nil.

  Only certain answers live here — this never guesses. A short response is
  NOT a mismatch: `IRangeRead` says a store returns the overlap when the
  object ends first, exactly as HTTP 206 does, and the read-ahead window
  routinely asks past the end of a pack.

  - `:over-fetch` — more bytes than the range is wide. Arithmetic.
  - `:range-ignored` — a non-zero start whose body begins with the CARv2
    pragma, which is the object from byte 0. A provider that answers 200
    instead of 206 does this, and it is the failure worth naming precisely:
    the bytes are perfectly good, they are simply not the bytes that were
    asked for, so every offset computed from them is wrong. Measured before
    this check existed, that produced `car: unsupported CID version`
    {:version 13217} — a real error, blaming the pack for the store's bug.
    A frame cannot begin with the pragma: a frame starts with a varint
    length that is at least 36 (the smallest CIDv1 alone is 36 bytes) and
    the pragma's first byte is 10."
  [start requested-end bytes]
  (let [n (b/bcount bytes)]
    (cond
      (> n (- requested-end start)) :over-fetch
      (and (pos? start) (>= n (b/bcount v2/pragma))
           (b/equal? v2/pragma (b/slice bytes 0 (b/bcount v2/pragma))))
      :range-ignored)))

(defn read-frames
  "Parse and CID-verify every wanted frame that `window` actually covers.

  Returns `{:frames {cid bytes} :short n}`.

  There is one line here and it is worth stating, because the two sides of
  it look identical from a caller counting blocks:

  - **Bytes we did not get are omitted, and counted.** `window-request`
    always asks for a range covering the whole run, so a wanted frame the
    window does not reach means the object ended before the catalog said it
    would. `-get-blocks` omits what is missing — a short block would be a
    wrong answer rather than a missing one — but omitting it without
    counting it makes a truncated pack indistinguishable from a pack that
    never held the block. `:short` is that count, and it is what turns
    `:evidence` to `:degraded`.
  - **Bytes we did get that are wrong throw.** A frame that fails to parse,
    or whose contents do not hash to the CID in its own header, is caught by
    `v2/read-frame`. A frame that parses cleanly but announces a different
    CID than the catalog located is caught here: the catalog and the pack
    disagree about where a block is, and answering with the block that
    happens to live at that offset would be a wrong answer to a question
    nobody asked. It used to be merged into the result under its own CID,
    so the caller saw its own CID missing and every counter healthy.

  This is the same distinction `a-tampered-pack-fails-closed` rests on. The
  store does not trust the object store; it trusts the hashes."
  [window base wanted]
  (reduce (fn [acc {:keys [cid file-offset frame-length]}]
            (let [rel (- file-offset base)]
              (if (or (neg? rel) (> (+ rel frame-length) (b/bcount window)))
                (update acc :short inc)
                (let [frame (v2/read-frame window rel)]
                  (when (and cid (not= cid (:cid frame)))
                    (throw (ex-info "pack: the frame at that offset is a different block"
                                    {:type :kotobase.storage.pack/frame-misplaced
                                     :located cid :found (:cid frame)
                                     :file-offset file-offset})))
                  (assoc-in acc [:frames (:cid frame)] (:bytes frame))))))
          {:frames {} :short 0}
          wanted))

;; ── held windows ────────────────────────────────────────────────────────────
;; Packs are immutable, so a held window is never stale. Cache invalidation is
;; not a problem this layer has.

(defn cache-put [cache pack-cid start bytes limit]
  (let [entry {:pack-cid pack-cid :start start
               :end (+ start (b/bcount bytes)) :bytes bytes}
        held (conj (vec cache) entry)]
    (loop [held held total (reduce + 0 (map #(b/bcount (:bytes %)) held))]
      (if (and (> total limit) (seq (rest held)))
        (recur (vec (rest held)) (- total (b/bcount (:bytes (first held)))))
        held))))

(defn cache-hit
  "A held window covering `[start, end)` of `pack-cid`, or nil."
  [cache pack-cid start end]
  (some (fn [e]
          (when (and (= pack-cid (:pack-cid e))
                     (<= (:start e) start)
                     (<= end (:end e)))
            e))
        cache))

;; ── bootstrap: a pack locates its own blocks ────────────────────────────────

(defn entries-of
  "Every block in a pack, located, from the pack's own bytes — no catalog.

  This is what makes the catalog a projection rather than a premise. A
  catalog that had to be consulted to read the blocks it is stored in would
  be circular; because a pack carries a CARv2 index, its contents can always
  be recovered from the pack alone, and a lost catalog costs a scan rather
  than the data."
  [pack-cid bytes]
  (let [hdr (v2/parse-header bytes)
        records (v2/read-index bytes)]
    (if records
      (mapv (fn [{:keys [payload-offset]}]
              ;; The index stores where a frame starts, not how long it is,
              ;; so the length comes from parsing the frame itself.
              (let [file-offset (+ (:data-offset hdr) payload-offset)
                    frame (v2/read-frame bytes file-offset)]
                {:cid (:cid frame) :pack-cid pack-cid
                 :file-offset file-offset
                 :frame-length (:frame-length frame)}))
            records)
      ;; No index: fall back to a full walk, which is the same answer at the
      ;; cost of reading every frame.
      (mapv (fn [{:keys [cid frame-offset frame-length]}]
              {:cid cid :pack-cid pack-cid
               :file-offset frame-offset :frame-length frame-length})
            (:entries (v2/read-all bytes))))))

(defn prev-of
  "The pack this one links back to, or nil at the start of a chain.

  A pack's CARv2 roots are where the link lives, and putting it there rather
  than in a side-car is what makes the chain need nothing outside itself: a
  reader holding one pack CID can reach every earlier pack without a
  catalog, a manifest, or a signature.

  It needs no signature for the same reason no other pointer here does —
  every block that comes out of a pack is rehashed against the CID that was
  asked for, so a forged or corrupted link costs a lookup that fails, never
  an answer that is wrong."
  [bytes]
  (first (:roots (v2/read-all bytes))))

(defn chain-step
  "One pack of a chain, read from its own bytes: `{:entries [...] :prev cid}`,
  or `{:problem {...}}` when the pack cannot be parsed.

  A corrupt pack used to throw out of the middle of a walk, which threw away
  every pack already recovered along with it. One bad index in a chain of a
  hundred is a recovery that loses ninety-nine readable packs — and the
  exception did not say which pack it was, so the operator could not even
  skip it. Turning it into a value is not swallowing it: `bootstrap-report`
  reports `:terminated :unreadable-pack` with this problem attached, and
  `bootstrap-catalog!`, which has nowhere to put a reason, refuses to return
  entries at all."
  [pack-cid bytes]
  (try {:entries (entries-of pack-cid bytes)
        :prev (prev-of bytes)}
       (catch #?(:clj Throwable :cljs :default) t
         {:problem {:pack-cid pack-cid
                    :error #?(:clj (ex-message t) :cljs (.-message t))
                    :data (ex-data t)}})))

(defn chain-stop
  "Why a walk cannot step from `cid`, or nil when it can.

  Shared by both drivers so that a chain that ended and a chain that was cut
  short cannot be classified two different ways by the two of them."
  [cid n max-packs seen]
  (cond (nil? cid) :chain-start
        (>= n max-packs) :budget-exhausted
        (contains? seen cid) :cycle))

(def entries-only-terminations
  "The terminations an entries-only return value can honestly represent.

  `:chain-start` is a complete walk. `:budget-exhausted` is a truncation the
  CALLER asked for, and only the caller knows whether that is what it meant
  — note that `bootstrap-catalog!`'s default budget is one the caller did
  not choose, so a walk that actually reaches 4096 packs should be read
  through `bootstrap-report` instead.

  The rest — a pack that is gone, a pack that will not parse, a cycle — are
  states where the recovered entries are a fragment of a catalog wearing the
  shape of a whole one. That is the failure this whole plane keeps finding:
  a thing that could not be measured returning the value of a thing that
  measured fine."
  #{:chain-start :budget-exhausted})

(defn bootstrap-summary
  "The report shape both drivers return from a chain walk."
  [entries packs terminated stopped-at problem]
  {:entries entries
   :packs packs
   :terminated terminated
   :stopped-at (when-not (= :chain-start terminated) stopped-at)
   :complete? (= :chain-start terminated)
   :problem problem})
