(ns ethercat.wkc
  "Working Counter (WKC) increment rules, ETG.1000. The WKC is the last
  two bytes of every datagram (see `ethercat.datagram`) and is the ONLY
  acknowledgement EtherCAT has — there is no per-slave ack frame, no
  response/request pairing beyond the `Idx` tag. Every slave a datagram
  addresses increments the SAME 16-bit counter in place as the frame
  passes through, and the master's entire notion of 'did this succeed,
  and how many slaves participated' comes from comparing the returned
  WKC against what it expected.

  The increment rule depends on which of the three *kinds* of command
  (see `ethercat.datagram/command-addressing-mode` for the orthogonal
  read/write... this is a different axis: read-only vs write-only vs
  read-then-write) was used, and — this is the detail that is easy to
  get wrong — **the two halves of a read-write command are NOT weighted
  equally**:

    read command   (APRD/FPRD/BRD/LRD/ARMW/FRMW)
      +1  if the slave was able to read the data successfully
      +0  otherwise

    write command  (APWR/FPWR/BWR/LWR)
      +1  if the slave was able to write the data successfully
      +0  otherwise

    read-write command (APRW/FPRW/BRW/LRW)
      +1  if the slave's read succeeded
      +2  if the slave's write succeeded   (NOT +1 — see below)
      so: 0 (both failed), 1 (read only), 2 (write only), 3 (both) — four
      DISTINCT values, each diagnosable on its own. Had the write half
      also contributed +1, 'write only' (1) would be indistinguishable
      from 'read only' (1) in the returned counter — the +2 weighting is
      exactly what makes the four outcomes separable from the WKC alone,
      without the master needing to inspect the Data payload itself.

  For a multi-slave command (BRD/BWR/BRW, or any AP*/FP* frame more than
  one slave answers to, or an LRD/LWR/LRW whose logical address range
  spans several FMMU-mapped slaves), the master's *expected* WKC is the
  SUM of each slave's contribution — `expected-wkc` below takes a
  collection of per-slave `{:read-ok? :write-ok?}` outcomes rather than
  a single one, for exactly that reason.

  Source: the +1 read / +1 write / +1+2 read-write split is reproduced
  identically in SOEM's slave-count verification helpers
  (`soem/ethercatconfig.c`, comments on `expectedWKC`), the IgH EtherCAT
  Master documentation (etherlab.org FAQ, 'Working Counter'), and is
  widely explained in vendor application notes (e.g. Beckhoff InfoSys
  'Working Counter' pages) since ETG.1000 itself is a paywalled EtherCAT
  Technology Group membership document not quoted here from memory.")

(def command-kinds
  "command keyword (from `ethercat.datagram/commands`) -> `:read`,
  `:write`, or `:read-write`. `:nop` maps to nil — it carries no data and
  contributes nothing to WKC."
  {:aprd :read :fprd :read :brd :read :lrd :read :armw :read :frmw :read
   :apwr :write :fpwr :write :bwr :write :lwr :write
   :aprw :read-write :fprw :read-write :brw :read-write :lrw :read-write
   :nop nil})

(defn slave-contribution
  "`command` + `{:read-ok? bool :write-ok? bool}` -> the WKC increment
  (0..3) ONE slave contributes for that command. Pure — no notion of
  'the' counter, just the arithmetic rule."
  [command {:keys [read-ok? write-ok?]}]
  (case (get command-kinds command)
    :read (if read-ok? 1 0)
    :write (if write-ok? 1 0)
    :read-write (+ (if read-ok? 1 0) (if write-ok? 2 0))
    nil 0))

(defn expected-wkc
  "`command` + a collection of per-slave outcome maps -> the WKC value
  the master should see if every slave's outcome is exactly as given.
  Sums `slave-contribution` across slaves — the rule for BRD/BWR/BRW and
  any multi-slave LRD/LWR/LRW."
  [command outcomes]
  (reduce + (map #(slave-contribution command %) outcomes)))

(defn classify-single-slave-wkc
  "For a command addressed to exactly ONE slave (APRD/APWR/APRW/FPRD/
  FPWR/FPRW/ARMW/FRMW), the observed WKC value (0..3, for a read-write
  command) -> `[:ok {:read-ok? :write-ok?}]`, the inverse of
  `slave-contribution`, or `[:error :ethercat/wkc-out-of-range wkc]` for
  a value the command kind cannot produce (e.g. WKC=3 from a plain read
  command, which only ever yields 0 or 1)."
  [command wkc]
  (case (get command-kinds command)
    :read (cond (= wkc 0) [:ok {:read-ok? false :write-ok? nil}]
                (= wkc 1) [:ok {:read-ok? true :write-ok? nil}]
                :else [:error :ethercat/wkc-out-of-range wkc])
    :write (cond (= wkc 0) [:ok {:read-ok? nil :write-ok? false}]
                 (= wkc 1) [:ok {:read-ok? nil :write-ok? true}]
                 :else [:error :ethercat/wkc-out-of-range wkc])
    :read-write (case wkc
                  0 [:ok {:read-ok? false :write-ok? false}]
                  1 [:ok {:read-ok? true :write-ok? false}]
                  2 [:ok {:read-ok? false :write-ok? true}]
                  3 [:ok {:read-ok? true :write-ok? true}]
                  [:error :ethercat/wkc-out-of-range wkc])
    nil [:error :ethercat/nop-has-no-wkc-semantics command]))
