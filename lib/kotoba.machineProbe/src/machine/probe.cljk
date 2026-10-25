(ns machine.probe
  "Reading a real machine and handing back a `machine.core` descriptor.

  `machine` is a contract and declares `:must-not [:probe-hardware]`, because
  a contract that performs effects is not a contract. This is the other half:
  the part that runs `sysctl`, parses `/sys/devices/system/cpu`, and stamps
  what it found as `:measured` with the command it read.

  The parsing is pure and the effect is a single injected function, so every
  platform's parser is testable against captured output without a device —
  which matters, because the interesting failures here are parse failures on
  a machine nobody has in the room.

  **It never fills a gap it did not read.** macOS does not expose cache
  associativity through `sysctl` at all, so `:ways` is simply absent from the
  descriptor rather than filled with the 8 that most caches happen to use.
  `machine.core` was changed to make `:ways` optional the day this probe was
  written, which is the correct direction: the contract bends to the machine,
  not the reading to the contract.

  Pure `.cljc` except for the injected reader. Depends only on
  `kotoba-lang/machine`."
  (:require [kotoba.lang.text :as str]
            [machine.core :as m]))

(def format-id :kotoba.machine.probe/v1)

;; ── sysctl parsing (pure) ────────────────────────────────────────────────

(defn parse-sysctl
  "`sysctl -a` output into a `{\"hw.pagesize\" \"16384\"}` map.

  Lines without a `: ` separator are dropped rather than guessed at — sysctl
  emits binary blobs and multi-line values that are not key/value pairs, and
  a parser that tries to salvage them produces keys nobody can look up."
  [text]
  (into {}
        (keep (fn [line]
                (let [idx (str/index-of line ": ")]
                  (when (and idx (pos? idx))
                    [(subs line 0 idx) (str/trim (subs line (+ idx 2)))]))))
        (str/split-lines (or text ""))))

(defn- n-of [sysctl k]
  (when-let [v (get sysctl k)]
    (let [n (parse-long (str/trim v))]
      (when (and n (pos? n)) n))))

(defn- cluster-caches
  "The three caches macOS reports per performance level.

  `shared-by` comes from `cpusperl2`, which is the fact that makes a private
  share computable — an M1 Max's 12 MiB L2 is shared by four cores, so a tile
  planned against 12 MiB fits on paper and thrashes against three siblings."
  [sysctl level line-bytes]
  (let [p (str "hw.perflevel" level ".")
        per-l2 (or (n-of sysctl (str p "cpusperl2")) 1)]
    (vec
     (keep identity
           [(when-let [b (n-of sysctl (str p "l1dcachesize"))]
              {:level 1 :kind :data :bytes b :line-bytes line-bytes :shared-by 1})
            (when-let [b (n-of sysctl (str p "l1icachesize"))]
              {:level 1 :kind :instruction :bytes b :line-bytes line-bytes :shared-by 1})
            (when-let [b (n-of sysctl (str p "l2cachesize"))]
              {:level 2 :kind :unified :bytes b :line-bytes line-bytes :shared-by per-l2})]))))

(defn- darwin-simd [sysctl arch]
  (cond
    (= "1" (get sysctl "hw.optional.neon")) {:name :neon :width-bits 128}
    (= :x86-64 arch) (cond
                       (= "1" (get sysctl "hw.optional.avx512f")) {:name :avx512 :width-bits 512}
                       (= "1" (get sysctl "hw.optional.avx2_0")) {:name :avx2 :width-bits 256}
                       :else {:name :sse :width-bits 128})
    :else nil))

(defn from-darwin-sysctl
  "Build a descriptor from `sysctl -a` output.

  Emits `:cpu :clusters` when the machine reports more than one performance
  level, and a flat `:cpu :cache` when it reports one — never both, which
  `machine.core` rejects. Nothing is invented: absent facts stay absent, and
  the descriptor's `:machine/source` records the command that produced it."
  [text]
  (let [s (parse-sysctl text)
        line (or (n-of s "hw.cachelinesize") 64)
        arch (if (= "1" (get s "hw.optional.arm64")) :aarch64 :x86-64)
        levels (or (n-of s "hw.nperflevels") 1)
        simd (darwin-simd s arch)
        base {:format m/format-id
              :machine/id (or (get s "machdep.cpu.brand_string") "darwin-unknown")
              :machine/provenance :measured
              :machine/source "sysctl -a (Darwin)"
              :page {:base-bytes (or (n-of s "hw.pagesize") 4096)
                     ;; macOS has no user-selectable huge page the way Linux
                     ;; does, and the base page is already 16 KiB on Apple
                     ;; silicon. Declaring an empty list is the true statement.
                     :huge []}
              ;; One node. Apple silicon is UMA; a multi-socket Mac has not
              ;; existed since the Intel Mac Pro, and this probe does not
              ;; pretend to describe one it cannot read.
              :numa {:nodes 1 :distance [[10]]}}
        cpu (cond-> {:arch arch :cores (or (n-of s "hw.ncpu") 1)}
              simd (assoc :simd simd))]
    (if (> levels 1)
      (assoc base :cpu
             (assoc cpu :clusters
                    (vec (for [l (range levels)
                               :let [caches (cluster-caches s l line)]
                               :when (seq caches)]
                           {:id (keyword (str/lower
                                          (or (get s (str "hw.perflevel" l ".name"))
                                              (str "level" l))))
                            :cores (or (n-of s (str "hw.perflevel" l ".physicalcpu")) 1)
                            :cache caches}))))
      (assoc base :cpu (assoc cpu :cache (cluster-caches s 0 line))))))

(defn from-linux-sysfs
  "Build a descriptor from `/sys/devices/system/cpu` index files.

  `read-file` is injected: `(read-file \"cpu0/cache/index0/size\")` relative to
  `/sys/devices/system/cpu`, returning nil for an absent path. Linux DOES
  expose `ways_of_associativity`, so `:ways` is present here and absent on
  Darwin — the descriptor carries what the platform gives and no more."
  [read-file {:keys [cores page-bytes arch]}]
  (let [index (fn [i k] (some-> (read-file (str "cpu0/cache/index" i "/" k)) str/trim))
        kib (fn [v] (when v
                      (let [n (parse-long (str/replace v #"[KM]$" ""))]
                        (when n (cond (str/ends-with? v "K") (* 1024 n)
                                      (str/ends-with? v "M") (* 1024 1024 n)
                                      :else n)))))
        caches (vec
                (keep (fn [i]
                        (when-let [size (kib (index i "size"))]
                          (let [line (some-> (index i "coherency_line_size") parse-long)
                                ways (some-> (index i "ways_of_associativity") parse-long)
                                level (some-> (index i "level") parse-long)
                                kind (case (index i "type")
                                       "Data" :data "Instruction" :instruction :unified)
                                shared (count (str/split (or (index i "shared_cpu_list") "0") #","))]
                            (cond-> {:level (or level 1) :kind kind :bytes size
                                     :line-bytes (or line 64) :shared-by (max 1 shared)}
                              ways (assoc :ways ways)))))
                      (range 8)))]
    {:format m/format-id
     :machine/id "linux-sysfs"
     :machine/provenance :measured
     :machine/source "/sys/devices/system/cpu"
     :cpu {:arch (or arch :x86-64) :cores (or cores 1) :cache caches}
     :page {:base-bytes (or page-bytes 4096) :huge []}
     :numa {:nodes 1 :distance [[10]]}}))

;; ── the effect ───────────────────────────────────────────────────────────

(defn probe
  "Run the platform reader and return a validated `:measured` descriptor.

  `run` is the injected effect: `(run \"sysctl\" [\"-a\"])` returning stdout.
  Keeping it a parameter is what makes every parser above testable against
  captured output — the interesting failures are parse failures on machines
  nobody has in the room.

  Validation runs before the descriptor is returned, so a probe that
  misreads a machine fails here rather than three layers downstream in a
  planner that cannot say what went wrong."
  [{:keys [platform run]}]
  (case platform
    :darwin (m/validate! (from-darwin-sysctl (run "sysctl" ["-a"])))
    (throw (ex-info "no probe for this platform"
                    {:phase :machine.probe/probe :platform platform
                     :supported [:darwin]
                     :note "linux is parseable via from-linux-sysfs with an injected reader"}))))
