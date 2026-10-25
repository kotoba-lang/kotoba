(ns kotoba.eda.sdc-adapter
  "Adapts org-synopsys-sdc's parsed SDC (Synopsys Design Constraints)
  `create_clock` commands into `kotoba.eda.core/analyze-timing` job
  input, so a timing job can be driven by a real SDC script instead of
  only a hand-built :eda.timing/clock-period-ns number. Same alpha
  evidence-pipeline maturity level as kotoba.eda.core -- see
  eda/README.md."
  (:require [sdc.parser :as sdc-parser]
            [kotoba.eda.core :as eda-core]))

(defn create-clock-command?
  "True if `cmd` (one entry from `sdc.parser/parse-script`) is a
  create_clock command. create_clock is the only sdc.parser command
  builder whose result map carries a `:period` key -- io-delay entries
  key on `:direction` (sdc.io-delay) and path-exception entries key on
  `:type` (sdc.path-exception) -- so presence of `:period`/`:waveform`
  unambiguously discriminates it without needing a dedicated
  `:command`/`:type` tag on the clock map itself."
  [cmd]
  (and (map? cmd) (contains? cmd :period) (contains? cmd :waveform)))

(defn clock-commands
  "Filters `parsed-commands` (the vector returned by
  `sdc.parser/parse-script`) down to just the create_clock entries,
  preserving script order."
  [parsed-commands]
  (filterv create-clock-command? parsed-commands))

(defn primary-clock-period-ns
  "Returns the clock period (nanoseconds) of the FIRST create_clock
  command in `parsed-commands`, or nil when no create_clock command is
  present.

  Unit note: sdc.parser's `-period` value is a bare double -- this
  simplified SDC subset does not model `set_units -time ...`, so no
  unit is attached during parsing (see sdc.parser/parse-num and
  sdc.clock/create-clock). By convention in sdc.clock's own docs/tests
  and in this adapter, `-period` is authored directly in
  nanosecond-scale numbers (e.g. `-period 10` for a 100MHz clock),
  which is exactly the unit `kotoba.eda.core/analyze-timing` expects
  for :eda.timing/clock-period-ns. Consequently this function performs
  no unit conversion -- it passes the parsed :period value straight
  through. If a future script declares a different SDC time unit, that
  conversion belongs in a `set_units` model, not here."
  [parsed-commands]
  (:period (first (clock-commands parsed-commands))))

(defn sdc-script->timing-job
  "Parses `sdc-script-text` via `sdc.parser/parse-script` and merges its
  primary clock period into `base-job` as
  :eda.timing/clock-period-ns, ready for
  `kotoba.eda.core/analyze-timing`. `base-job` must already carry
  :eda.timing/corners, :eda.timing/nodes, :eda.timing/edges, and
  :eda.timing/endpoints -- everything analyze-timing needs besides the
  clock period.

  Throws ex-info when the script has no create_clock command: a timing
  job genuinely needs a clock period, so this never silently defaults
  to 0."
  [sdc-script-text base-job]
  (let [parsed (sdc-parser/parse-script sdc-script-text)
        period (primary-clock-period-ns parsed)]
    (when (nil? period)
      (throw (ex-info "SDC script has no create_clock command; analyze-timing requires a clock period"
                       {:kotoba.eda.sdc-adapter/error :missing-create-clock
                        :sdc-script sdc-script-text})))
    (assoc base-job :eda.timing/clock-period-ns period)))

(defn analyze-timing-from-sdc
  "Convenience entry point: parses `sdc-script-text`, merges its primary
  clock period into `base-job`, and runs
  `kotoba.eda.core/analyze-timing` on the result."
  [sdc-script-text base-job]
  (eda-core/analyze-timing (sdc-script->timing-job sdc-script-text base-job)))
