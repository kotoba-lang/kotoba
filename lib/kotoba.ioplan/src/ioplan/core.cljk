(ns ioplan.core
  "Turning a list of I/O requests into the list the device actually wants.

  Four transformations, and which of them apply is a property of the device
  rather than a preference:

  1. **align** every request to whole device blocks, because a device cannot
     transfer half a block and pretending otherwise hides the amplification;
  2. **merge** adjacent requests, up to the device's maximum transfer, so one
     command carries what several would have;
  3. **order** them — or, on a device with no seek cost, deliberately do not;
  4. **batch** them to the device's queue depth.

  The third is where most of the wrong intuition lives. An elevator sort is
  the canonical I/O optimization and on an NVMe device it is *harmful*: it
  spends CPU and latency to reduce a cost that is zero, and it destroys the
  submission order the caller chose. `machine.core/reorderable?` answers the
  question from the device descriptor, so a plan cannot apply a rotating-disk
  optimization to flash by inheritance.

  Everything is a pure function of requests plus a device descriptor. No I/O
  happens here; the output is a plan a host executes.

  Pure `.cljc`. Depends only on `kotoba-lang/machine`."
  (:require [machine.core :as m]))

(def format-id :kotoba.ioplan/v1)

;; ── requests ─────────────────────────────────────────────────────────────

(defn request-errors [requests]
  (vec
   (concat
    (when-not (vector? requests) [{:error :requests-not-a-vector}])
    (when (vector? requests)
      (concat
       (for [[i r] (map-indexed vector requests)
             e (cond-> []
                 (not (#{:read :write} (:op r)))     (conj :invalid-op)
                 (not (and (integer? (:offset r)) (<= 0 (:offset r)))) (conj :invalid-offset)
                 (not (pos-int? (:bytes r)))         (conj :invalid-bytes))]
         {:error e :index i :request r})
       (let [ids (keep :id requests)]
         (when-not (= (count ids) (count (set ids)))
           [{:error :duplicate-request-id :ids (vec ids)}])))))))

(defn- check! [requests]
  (let [errs (request-errors requests)]
    (when (seq errs)
      (throw (ex-info "invalid request list" {:phase :ioplan/requests :errors errs})))
    requests))

(defn- device! [machine id]
  (or (m/storage-device machine id)
      (throw (ex-info "machine declares no such storage device"
                      {:phase :ioplan/device :device id
                       :known (mapv :id (:storage machine))}))))

;; ── align ────────────────────────────────────────────────────────────────

(defn align
  "Expand each request to whole device blocks.

  The expansion is not overhead being added, it is overhead being *made
  visible*: the device was always going to move whole blocks. A 100-byte read
  from a 4 KiB-block device transfers 4096 bytes, and a plan that reports 100
  is lying about the bandwidth it will consume."
  [device requests]
  (let [b (:block-bytes device)]
    (mapv (fn [r]
            (let [start (* b (quot (:offset r) b))
                  end (* b (quot (+ (:offset r) (:bytes r) (dec b)) b))]
              (assoc r
                     :aligned-offset start
                     :aligned-bytes (- end start)
                     :covers [(:id r)])))
          requests)))

;; ── merge ────────────────────────────────────────────────────────────────

(defn default-merge-gap
  "How far apart two requests may be and still be worth merging.

  On a seeking device, skipping a gap costs a seek and reading through it
  costs only bandwidth, so merging across a block-sized hole wins. On a device
  with no seek cost there is nothing to buy, so the gap is zero and only
  genuinely adjacent requests combine."
  [device]
  (if (m/reorderable? device) (:block-bytes device) 0))

(defn merge-adjacent
  "Combine requests that touch, or nearly touch, into single transfers.

  Requests must already be aligned. Merging never crosses an op boundary — a
  read absorbed into a write would return bytes that were never read — and
  never exceeds the device's maximum transfer, because a command the device
  cannot express is not a plan."
  ([device requests] (merge-adjacent device requests (default-merge-gap device)))
  ([device requests gap]
   (let [maxb (:max-transfer-bytes device)
         ;; On a seeking device the whole list may be sorted first, so any two
         ;; requests that touch will find each other. On a zero-seek device
         ;; that sort would be a reordering by the back door — merging must
         ;; not undo the ordering decision `order` is about to decline to
         ;; make — so only neighbours in SUBMISSION order combine, which
         ;; still catches the sequential reader that produced them.
         sorted (if (m/reorderable? device)
                  (vec (sort-by (juxt :aligned-offset (comp name :op)) requests))
                  (vec requests))]
     (reduce
      (fn [acc r]
        (let [prev (peek acc)
              end (when prev (+ (:aligned-offset prev) (:aligned-bytes prev)))
              new-end (+ (:aligned-offset r) (:aligned-bytes r))
              mergeable? (and prev
                              (= (:op prev) (:op r))
                              ;; Both bounds. Only checking the upper one
                              ;; merges a request that lies BEFORE prev --
                              ;; harmless on a sorted list and silently wrong
                              ;; on the unsorted one a zero-seek device gets.
                              (>= (:aligned-offset r) (:aligned-offset prev))
                              (<= (:aligned-offset r) (+ end gap))
                              (<= (- (max end new-end) (:aligned-offset prev)) maxb))]
          (if mergeable?
            (conj (pop acc)
                  (assoc prev
                         :aligned-bytes (- (max end new-end) (:aligned-offset prev))
                         :covers (into (:covers prev) (:covers r))
                         :merged? true))
            (conj acc r))))
      []
      sorted))))

;; ── order ────────────────────────────────────────────────────────────────

(defn split-oversized
  "Break any transfer larger than the device's maximum into ones it can run.

  Merging refuses to GROW a command past `:max-transfer-bytes`, which is not
  the same as ensuring none exceeds it — a single request larger than the
  maximum arrives that way and used to pass straight through. A 1 MiB read
  against a 128 KiB device produced one 1 MiB command, which the device cannot
  execute, and which `benefit` correctly said should have been eight. The plan
  was worse than its own stated floor.

  Chunks are floored to whole blocks so every piece stays aligned."
  [device requests]
  (let [block (:block-bytes device)
        maxt (* block (quot (:max-transfer-bytes device) block))]
    (vec (mapcat (fn [r]
                   (if (<= (:aligned-bytes r) maxt)
                     [r]
                     (mapv (fn [off]
                             (assoc r
                                    :aligned-offset (+ (:aligned-offset r) off)
                                    :aligned-bytes (min maxt (- (:aligned-bytes r) off))
                                    :split-of (:id r)))
                           (range 0 (:aligned-bytes r) maxt))))
                 requests))))

(defn head-travel
  "Total head movement visiting these requests in this order from `start`."
  [requests start]
  (first
   (reduce (fn [[total at] r]
             [(+ total (Math/abs (- (:aligned-offset r) at))) (:aligned-offset r)])
           [0 start]
           requests)))

(defn order
  "Sequence the requests the way this device is actually paid to receive them.

  `:high` — C-SCAN: one ascending sweep. Ascending-only rather than
  back-and-forth because a bidirectional sweep starves whichever end the head
  is walking away from, and the starved request is usually the interactive
  one.

  That fairness is not free, and `benefit` prices it. From a head above the
  span, C-SCAN walks down to the lowest request and then sweeps back up over
  the same ground, paying `(head - lo) + span` against an optimum of
  `(head - lo)` — a ratio of `1 + span/(head - lo)`, which is **exactly 2 when
  the head sits on the top of the span** and decays toward 1 as it moves
  further away. From a head below or inside the span it is optimal. Trading up
  to 2x travel for bounded latency at the far end is a defensible choice;
  making it without knowing the factor is not.

  `:low` — sorted, but no sweep discipline. There is a cost to locality but
  no head to walk.

  `:none` — **submission order, untouched**. Reordering buys nothing here and
  costs the ordering the caller chose. This is the branch that stops an
  elevator sort from being applied to flash out of habit."
  [device requests]
  (case (:seek-cost device)
    :none requests
    :low (vec (sort-by (juxt (comp name :op) :aligned-offset) requests))
    :high (vec (sort-by :aligned-offset requests))))

;; ── batch ────────────────────────────────────────────────────────────────

(defn batch
  "Split into waves the device can have in flight at once.

  On a zero-seek device this is the *only* thing that matters — throughput
  comes from keeping the queue full, not from the order within it."
  [device requests]
  (mapv vec (partition-all (:queue-depth device) requests)))

;; ── the plan ─────────────────────────────────────────────────────────────

(def plan-model
  {:model/id :kotoba.ioplan/block-transfers-v1
   :model/counts [:bytes-requested :bytes-transferred :read-amplification
                  :head-travel :commands]
   :model/assumes
   ["a request costs one block-aligned transfer plus, on a seeking device, the
     head movement to reach it"
    "merging is free once the bytes are already being moved"
    "queue depth bounds concurrency, not bandwidth"]
   :model/does-not-model
   [:controller-queueing :garbage-collection :thermal-throttling :cache-on-device
    :rotational-latency :parallelism-across-channels]})

(defn plan
  "Align, merge, order and batch, reporting what each step bought.

  `:read-amplification` is bytes the device will move divided by bytes the
  caller asked for. Below 1.0 means merging removed duplicate coverage;
  above means block alignment is dominating, which on a 4 KiB device with
  100-byte reads is a factor of 40 and worth seeing before optimising
  anything else."
  [machine device-id requests & [{:keys [head merge-gap] :or {head 0}}]]
  (check! requests)
  (let [device (device! machine device-id)
        aligned (align device requests)
        merged (merge-adjacent device aligned (or merge-gap (default-merge-gap device)))
        ;; After merging, because merging is what can produce a command at the
        ;; limit; before ordering, because the pieces are separate commands the
        ;; device visits in sequence.
        sized (split-oversized device merged)
        ordered (order device sized)
        batches (batch device ordered)
        requested (reduce + 0 (map :bytes requests))
        transferred (reduce + 0 (map :aligned-bytes merged))
        writes (filterv #(= :write (:op %)) requests)
        write-requested (reduce + 0 (map :bytes writes))
        write-transferred (reduce + 0 (map :aligned-bytes
                                           (filter #(= :write (:op %)) merged)))]
    {:format format-id
     :device device
     :batches batches
     :order (mapv :aligned-offset ordered)
     :stats
     (cond-> {:requests-in (count requests)
              :commands (count sized)
              :merges (- (count aligned) (count merged))
              :splits (- (count sized) (count merged))
              :batches (count batches)
              :bytes-requested requested
              :bytes-transferred transferred
              :read-amplification (if (pos? requested)
                                    (double (/ transferred requested))
                                    0.0)
              ;; Did the pipeline emit commands out of submission order?
              ;; Comparing offset lists cannot answer this once merging has
              ;; changed the command count, so rank each command by where its
              ;; first covered request was submitted.
              :reordered? (let [rank (into {} (map-indexed (fn [i r] [(:id r) i]) requests))
                                ranks (mapv #(get rank (first (:covers %))) ordered)]
                            (not= ranks (vec (sort ranks))))
              :head-travel (when (m/reorderable? device) (head-travel ordered head))
              ;; The baseline is submission order — what the device would have
              ;; been handed with no planner at all. Comparing against the
              ;; post-merge list would flatter the elevator, since merging has
              ;; already sorted.
              :head-travel-submitted (when (m/reorderable? device)
                                       (head-travel aligned head))}
       (seq writes)
       (assoc :write-amplification
              ;; Bytes the device must actually write for the bytes the caller
              ;; wanted written. A sub-block write is a read-modify-write, and
              ;; on flash that costs an erase block somewhere later.
              (if (pos? write-requested)
                (double (/ write-transferred write-requested))
                0.0)))
     :model plan-model
     :machine (:machine/id machine)}))

(defn explain
  "One line per decision the plan made, for a human reading a slow trace."
  [p]
  (let [{:keys [device stats]} p]
    [(str "device " (:id device) " (" (name (:kind device))
          ", block " (:block-bytes device) "B, queue " (:queue-depth device)
          ", seek-cost " (name (:seek-cost device)) ")")
     (str (:requests-in stats) " requests -> " (:commands stats) " commands ("
          (:merges stats) " merged) in " (:batches stats) " batches")
     (str "moved " (:bytes-transferred stats) "B for " (:bytes-requested stats)
          "B asked (amplification " (:read-amplification stats) ")")
     (if (m/reorderable? device)
       (str "reordered: head travel " (:head-travel stats) "B against "
            (:head-travel-submitted stats) "B as submitted")
       "not reordered: this device charges nothing for seeking, so submission order stands")]))

;; ── how much is there to win? ────────────────────────────────────────────
;;
;; The other three T5 libraries each gained a bound you can compute before
;; running anything: `layout/achievable-ratio`, `traversal/tiling-benefit`,
;; `paging/headroom`. This is that bound for I/O planning, and it exists for
;; the same reason — merging and ordering are only worth doing when there is
;; something for them to remove, and whether there is depends on the request
;; list rather than on the planner.
;;
;; Both floors are exact rather than estimated, which is unusual and worth
;; saying: the byte floor is the measure of the union of the aligned ranges,
;; and no plan moves fewer bytes than the bytes it was asked for. The travel
;; floor is the classic shortest walk visiting every point on a line from a
;; starting position, which has a closed form.

(defn- union-runs
  "Maximal non-overlapping runs covering every aligned request. Adjacent runs
  are fused, because a device does not charge extra to cross the join."
  [aligned]
  (->> (sort-by :aligned-offset aligned)
       (reduce (fn [runs r]
                 (let [start (:aligned-offset r)
                       end (+ start (:aligned-bytes r))
                       prev (peek runs)]
                   (if (and prev (<= start (:end prev)))
                     (conj (pop runs) (assoc prev :end (max (:end prev) end)))
                     (conj runs {:start start :end end}))))
               [])))

(defn optimal-travel
  "Shortest head movement that visits every point, starting from `head`.

  Closed form, not a heuristic. Outside the span you walk it once. Inside it,
  you must double back over one side, so the cheaper choice is to cover the
  nearer side first and the further side last."
  [points head]
  (if (empty? points)
    0
    (let [lo (apply min points) hi (apply max points)]
      (cond
        (<= head lo) (- hi head)
        (>= head hi) (- head lo)
        :else (min (+ (* 2 (- head lo)) (- hi head))
                   (+ (* 2 (- hi head)) (- head lo)))))))

(defn bridging-floor
  "Fewest commands achievable while transferring `extra-bytes` beyond the byte
  floor, by bridging gaps.

  `benefit`'s floors bound merging and ordering and deliberately say nothing
  about this lever -- `plan` bridges gaps smaller than a seek by default,
  buying a command with bytes nobody asked for, and measured against a
  union-of-ranges floor that looks like beating the bound. Calling it a
  separate lever with a separate ceiling, and then not providing the ceiling,
  leaves the comparison exactly as unanswerable as before. So here it is.

  The accounting is exact rather than heuristic. Bridging one gap fuses two
  runs, and

      ceil((a + g + b) / m) >= ceil(a/m) + ceil(b/m) - 1

  so a bridged gap saves AT MOST one command, whatever the sizes. The best any
  planner can do with a byte budget is therefore to spend it on the cheapest
  gaps: sort ascending, take the longest prefix that fits, and subtract that
  count from the merge-and-order floor. No planner beats it, and unlike a
  greedy plan this is a bound rather than a strategy.

  Returns `nil` for a device that does not reward bridging -- on zero-seek
  hardware the default gap is already 0, and a budget spent there buys
  nothing rather than buying a little."
  [machine device-id requests {:keys [extra-bytes] :or {extra-bytes 0}}]
  (check! requests)
  (let [device (device! machine device-id)]
    (when (m/reorderable? device)
      (let [aligned (align device requests)
            runs (union-runs aligned)
            maxt (:max-transfer-bytes device)
            ceil-div (fn [n d] (quot (+ n (dec d)) d))
            base (reduce + 0 (map #(max 1 (ceil-div (- (:end %) (:start %)) maxt)) runs))
            gaps (sort (map (fn [[a b]] (- (:start b) (:end a))) (partition 2 1 runs)))
            afford (loop [gs gaps spent 0 n 0]
                     (if (and (seq gs) (<= (+ spent (first gs)) extra-bytes))
                       (recur (next gs) (+ spent (first gs)) (inc n))
                       {:bridged n :bytes-spent spent}))]
        {:format format-id
         :device (:id device)
         :bounds :gap-bridging
         :extra-bytes-allowed extra-bytes
         :commands-without-bridging base
         :gaps-available (count gaps)
         :gaps-bridged (:bridged afford)
         :bytes-spent (:bytes-spent afford)
         :commands-floor (- base (:bridged afford))
         :note "one bridged gap saves at most one command, so this is a floor
                no planner beats -- not a plan to imitate"}))))

(defn benefit
  "What planning can buy on this request list, before planning it.

  Three comparisons, each against a floor no planner can beat:

  - **bytes** — the union of the aligned ranges. Overlapping requests are the
    only thing merging removes here; alignment overhead is not removable at
    all, so a plan already at this floor cannot be improved by merging.
  - **commands** — one per union run, split at the device's maximum transfer.
  - **travel** — `optimal-travel`, and only for a device that charges for
    seeking. On a zero-seek device this is `nil` rather than zero, because the
    quantity does not apply rather than being minimal.

  `:worth-planning?` is the summary: is the unplanned submission meaningfully
  worse than the floor? When it is false, `plan` will return something correct
  and pointless, and the honest report is that the request list was already
  good.

  **These floors bound MERGING AND ORDERING, not gap bridging, and the
  `:planned` figures here are measured with bridging switched off so the two
  sides describe the same lever.** `plan` bridges gaps smaller than a seek by
  default: it buys a command by transferring bytes nobody asked for, which a
  union-of-ranges floor cannot see and does not bound. Measured on a real
  packfile layout, the default plan issued 73 commands against a floor of 82
  and `:captured :commands` came out at **1.05** — a plan reported as removing
  105% of the removable excess. The floor was not wrong; the comparison was,
  in the same way that running a prefetching cache against a demand-paging
  bound makes LRU beat Belady.

  So `:planned` here is deliberately NOT what `plan` returns by default. To
  reproduce it, pass `{:merge-gap 0}`. To see what bridging buys, compare that
  against the default plan — it is a separate lever with a separate ceiling
  and it belongs in a separate comparison."
  [machine device-id requests & [{:keys [head] :or {head 0}}]]
  (check! requests)
  (let [device (device! machine device-id)
        aligned (align device requests)
        runs (union-runs aligned)
        floor-bytes (reduce + 0 (map #(- (:end %) (:start %)) runs))
        maxt (:max-transfer-bytes device)
        floor-commands (reduce + 0 (map #(max 1 (quot (+ (- (:end %) (:start %)) (dec maxt)) maxt))
                                        runs))
        submitted-bytes (reduce + 0 (map :aligned-bytes aligned))
        offsets (mapv :aligned-offset aligned)
        seeking? (m/reorderable? device)
        floor-travel (when seeking? (optimal-travel (mapv :start runs) head))
        submitted-travel (when seeking? (head-travel aligned head))
        ;; merge-gap 0: the floors below bound merging and ordering. Letting
        ;; the internal plan bridge gaps measures a different lever against
        ;; them and produced :captured :commands of 1.05 on real offsets.
        p (plan machine device-id requests {:head head :merge-gap 0})
        planned (:stats p)]
    {:format format-id
     :device (:id device)
     ;; Which lever these floors bound, stated rather than assumed. A caller
     ;; comparing them against a default `plan` is comparing two levers.
     :bounds :merging-and-ordering
     :gap-bridging :disabled-for-this-comparison
     :floors {:bytes floor-bytes :commands floor-commands :travel floor-travel}
     :submitted {:bytes submitted-bytes :commands (count aligned) :travel submitted-travel}
     :planned {:bytes (:bytes-transferred planned)
               :commands (:commands planned)
               :travel (:head-travel planned)}
     ;; Fraction of the removable excess the plan actually removed. `nil` when
     ;; there was no excess to remove — reporting 1.0 there would claim credit
     ;; for a request list that was already minimal.
     :captured
     {:bytes (when (> submitted-bytes floor-bytes)
               (double (/ (- submitted-bytes (:bytes-transferred planned))
                          (- submitted-bytes floor-bytes))))
      :commands (when (> (count aligned) floor-commands)
                  (double (/ (- (count aligned) (:commands planned))
                             (- (count aligned) floor-commands))))
      :travel (when (and seeking? (> submitted-travel floor-travel))
                (double (/ (- submitted-travel (:head-travel planned))
                           (- submitted-travel floor-travel))))}
     :worth-planning? (boolean (or (> submitted-bytes floor-bytes)
                                   (> (count aligned) floor-commands)
                                   (and seeking? (> submitted-travel floor-travel))))
     :machine (:machine/id machine)}))
