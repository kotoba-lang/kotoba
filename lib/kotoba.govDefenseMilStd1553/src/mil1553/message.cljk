(ns mil1553.message
  "The message-transfer formats a Bus Controller and Remote Terminal(s)
  exchange: BC-to-RT, RT-to-BC, RT-to-RT, and Mode Commands with and
  without an accompanying data word.

  This namespace builds and validates the SEQUENCE OF WORDS each format
  is made of — it has no bus, no timing, no gap enforcement (the real
  1553B response-time and inter-message-gap requirements are physical/
  timing properties this pure codec does not model, same 'no timing' the
  README states up front).

  Word-count handling everywhere routes through `mil1553.command`'s
  00000-means-32 remapping — callers of this namespace always see and
  supply the real count (1..32), never the raw 5-bit field."
  (:require [mil1553.command :as cmd]
            [mil1553.mode :as mode]))

(defn- command-fields
  "`cmd/pack` a Command Word's fields, then immediately `cmd/unpack` the
  result back into canonical field form (never a raw 16-bit payload) —
  every builder in this namespace works with fields maps throughout,
  never bare integers, and this round trip both produces that canonical
  map and doubles as a self-consistency check on `mil1553.command`
  itself."
  [fields]
  (let [result (cmd/pack fields)]
    (if (= :error (first result))
      result ;; pass the whole [:error kw data] through — do not truncate it via 2-element destructuring
      (cmd/unpack (second result)))))

;; ── BC-to-RT (Receive Command) ──────────────────────────────────────────────

(defn bc-to-rt
  "`{:rt-address :subaddress :data-words [16-bit values]}` -> `[:ok
  {:command-word {...} :data-words [...]}]`, the Receive Command word
  plus the data words that follow it on the bus. `[:error
  :mil1553/data-word-count-out-of-range n]` if `data-words` is empty or
  has more than 32 elements."
  [{:keys [rt-address subaddress data-words]}]
  (let [n (count data-words)]
    (if-not (<= 1 n 32)
      [:error :mil1553/data-word-count-out-of-range n]
      (let [result (command-fields {:rt-address rt-address :tr :receive
                                    :subaddress-mode subaddress :word-count-or-mode n})]
        (if (= :error (first result))
          result
          [:ok {:command-word (second result) :data-words (vec data-words)}])))))

(defn validate-bc-to-rt-response
  "The RT's response to a `bc-to-rt` command is just its Status Word.
  `{:command-word (from bc-to-rt) :status-word {...}}` -> `[:ok
  status-word]` if `:rt-address` matches, else `[:error
  :mil1553/status-rt-address-mismatch {:expected :actual}]`."
  [{:keys [command-word status-word]}]
  (if (= (:rt-address command-word) (:rt-address status-word))
    [:ok status-word]
    [:error :mil1553/status-rt-address-mismatch
     {:expected (:rt-address command-word) :actual (:rt-address status-word)}]))

;; ── RT-to-BC (Transmit Command) ─────────────────────────────────────────────

(defn rt-to-bc-command
  "`{:rt-address :subaddress :word-count}` -> `[:ok command-word]`, the
  Transmit Command the BC sends; the RT's response (status + data words)
  is checked separately by `validate-rt-to-bc-response`, since this
  library does not simulate an RT."
  [{:keys [rt-address subaddress word-count]}]
  (if-not (<= 1 word-count 32)
    [:error :mil1553/data-word-count-out-of-range word-count]
    (command-fields {:rt-address rt-address :tr :transmit
                     :subaddress-mode subaddress :word-count-or-mode word-count})))

(defn validate-rt-to-bc-response
  "`{:command-word (from rt-to-bc-command) :status-word {...} :data-words
  [...]}` -> `[:ok {:status-word :data-words}]`.

  `[:error :mil1553/status-rt-address-mismatch ...]` if the Status
  Word's RT address does not match the command. If `:message-error?` is
  set on the Status Word, the RT is understood to have aborted the
  transfer, and `:data-words` is expected to be empty — `[:error
  :mil1553/data-words-present-after-message-error n]` if it is not.
  Otherwise `:data-words` must have exactly `command-word`'s word count —
  `[:error :mil1553/data-word-count-mismatch {:expected :actual}]`."
  [{:keys [command-word status-word data-words]}]
  (cond
    (not= (:rt-address command-word) (:rt-address status-word))
    [:error :mil1553/status-rt-address-mismatch
     {:expected (:rt-address command-word) :actual (:rt-address status-word)}]

    (:message-error? status-word)
    (if (empty? data-words)
      [:ok {:status-word status-word :data-words []}]
      [:error :mil1553/data-words-present-after-message-error (count data-words)])

    (not= (:word-count-or-mode command-word) (count data-words))
    [:error :mil1553/data-word-count-mismatch
     {:expected (:word-count-or-mode command-word) :actual (count data-words)}]

    :else
    [:ok {:status-word status-word :data-words (vec data-words)}]))

;; ── RT-to-RT ─────────────────────────────────────────────────────────────────

(defn rt-to-rt
  "`{:receive-rt :receive-subaddress :transmit-rt :transmit-subaddress
  :word-count}` -> `[:ok {:receive-command {...} :transmit-command
  {...}}]`. The two Command Words the BC sends back-to-back, in wire
  order: the RECEIVE command (to the RT that will accept the data)
  first, then the TRANSMIT command (to the RT that will send it) — the
  transmitting RT answers first (status + data), then the receiving RT
  answers with its own status, once it has consumed the data."
  [{:keys [receive-rt receive-subaddress transmit-rt transmit-subaddress word-count]}]
  (if-not (<= 1 word-count 32)
    [:error :mil1553/data-word-count-out-of-range word-count]
    (let [receive-result (command-fields {:rt-address receive-rt :tr :receive
                                          :subaddress-mode receive-subaddress
                                          :word-count-or-mode word-count})
          transmit-result (command-fields {:rt-address transmit-rt :tr :transmit
                                           :subaddress-mode transmit-subaddress
                                           :word-count-or-mode word-count})]
      (cond
        (= :error (first receive-result)) receive-result
        (= :error (first transmit-result)) transmit-result
        :else [:ok {:receive-command (second receive-result)
                    :transmit-command (second transmit-result)}]))))

(defn validate-rt-to-rt-response
  "`{:transmit-command :receive-command :transmitting-status
  :data-words :receiving-status}` -> `[:ok {...}]`, checking the
  transmitting RT's Status Word address + data word count (reusing
  `validate-rt-to-bc-response`'s rule against `:transmit-command`) and
  the receiving RT's Status Word address against `:receive-command`."
  [{:keys [transmit-command receive-command transmitting-status data-words receiving-status]}]
  (let [tresult (validate-rt-to-bc-response
                 {:command-word transmit-command :status-word transmitting-status
                  :data-words data-words})]
    (cond
      (= :error (first tresult)) tresult
      (not= (:rt-address receive-command) (:rt-address receiving-status))
      [:error :mil1553/status-rt-address-mismatch
       {:expected (:rt-address receive-command) :actual (:rt-address receiving-status)}]
      :else
      [:ok {:transmitting-status transmitting-status :data-words (:data-words (second tresult))
            :receiving-status receiving-status}])))

;; ── Mode commands ────────────────────────────────────────────────────────────

(defn mode-command
  "`{:rt-address :mode-code :tr :data-word (optional)}` -> `[:ok
  {:command-word {...} :data-word (or nil)}]`.

  `:tr` is required from the caller (see `mil1553.mode`'s docstring: this
  library does not confidently derive T/R from the mode code). If the
  mode code's `mil1553.mode/data-word-direction` is `:bc-to-rt` or
  `:rt-to-bc`, `:data-word` must be supplied (`[:error
  :mil1553/mode-code-requires-data-word code]` if missing); if `:none`,
  `:data-word` must be absent (`[:error
  :mil1553/mode-code-forbids-data-word code]` if present). A mode code
  this library marks `:reserved`/`:unknown` (see `mil1553.mode`) fails
  closed with `[:error :mil1553/mode-code-data-word-unknown code]` rather
  than guessing."
  [{:keys [rt-address mode-code tr data-word]}]
  (let [direction-result (mode/data-word-direction mode-code)
        direction (second direction-result)]
    (cond
      (= :error (first direction-result)) direction-result

      (and (#{:bc-to-rt :rt-to-bc} direction) (nil? data-word))
      [:error :mil1553/mode-code-requires-data-word mode-code]

      (and (= :none direction) (some? data-word))
      [:error :mil1553/mode-code-forbids-data-word mode-code]

      :else
      (let [result (command-fields {:rt-address rt-address :tr tr
                                    :subaddress-mode 0 :word-count-or-mode mode-code})]
        (if (= :error (first result))
          result
          [:ok {:command-word (second result) :data-word data-word}])))))
