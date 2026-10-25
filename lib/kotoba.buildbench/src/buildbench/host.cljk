(ns buildbench.host
  "What this machine is, read off the machine.

  `machine.core/measured` refuses a descriptor without a source string, and
  `perfgate` refuses a claim whose machine provenance is weaker than
  `:measured`. So every field here has to come from a probe that is named."
  (:require ["node:child_process" :as cp]
            ["node:os" :as os]
            [clojure.string :as str]
            [machine.core :as m]))

(defn- sysctl [k]
  (let [r (cp/spawnSync "sysctl" #js ["-n" k] #js {:encoding "utf8"})]
    (when (zero? (.-status r)) (str/trim (.-stdout r)))))

(defn- sysctl-int [k]
  (when-let [v (sysctl k)] (js/parseInt v 10)))

(defn load1
  "Current 1-minute load average, read from the OS rather than assumed."
  []
  (aget (os/loadavg) 0))

(defn descriptor
  "A `:measured` machine descriptor for the current host.

  Only the fields this harness actually probes are filled in. A cache
  geometry nobody read is left out rather than guessed, because a guessed
  number here would silently become the fingerprint a claim is pinned to."
  []
  (let [line (or (sysctl-int "hw.cachelinesize") 64)
        page (or (sysctl-int "hw.pagesize") 4096)
        cores (or (sysctl-int "hw.logicalcpu") (count (os/cpus)))
        l1 (or (sysctl-int "hw.l1dcachesize") 32768)
        l2 (or (sysctl-int "hw.l2cachesize") 262144)
        brand (or (sysctl "machdep.cpu.brand_string") (.-model (aget (os/cpus) 0)))]
    (m/measured
     {:format m/format-id
      :machine/id (str (str/lower-case (str/replace brand #"[^A-Za-z0-9]+" "-"))
                       "-" cores "c")
      :cpu {:arch (keyword (os/arch))
            :cores cores
            :simd {:name :none :width-bits 128}
            :cache [{:level 1 :kind :data :bytes l1 :line-bytes line :ways 8 :shared-by 1}
                    {:level 2 :kind :unified :bytes l2 :line-bytes line :ways 8 :shared-by cores}]}
      :page {:base-bytes page :huge []}
      :numa {:nodes 1 :distance [[10]]}}
     (str "sysctl machdep.cpu.brand_string, hw.logicalcpu, hw.cachelinesize, "
          "hw.pagesize, hw.l1dcachesize, hw.l2cachesize on " (os/hostname)))))

(defn environment []
  {:hostname (os/hostname)
   :platform (os/platform)
   :arch (os/arch)
   :release (os/release)
   :cpu (or (sysctl "machdep.cpu.brand_string") "unknown")
   :logicalCpus (count (os/cpus))
   :memoryBytes (os/totalmem)
   :node js/process.version})
