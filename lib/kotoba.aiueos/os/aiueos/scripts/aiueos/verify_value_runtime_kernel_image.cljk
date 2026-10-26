(ns aiueos.verify-value-runtime-kernel-image
  (:require [clojure.edn :as edn]
            [kotoba.compiler.core :as compiler]))

(defn- fail! [message data]
  (throw (ex-info message (assoc data :phase :aiueos-value-runtime-kernel-image))))

(defn- flattened [value]
  (tree-seq coll? seq value))

(defn- read-le [bytes offset width]
  (reduce (fn [value index]
            (+ value (bit-shift-left (long (nth bytes (+ offset index)))
                                     (* index 8))))
          0 (range width)))

(defn -main
  [& [arena-source transport-source dispatch-source entry-source syscall-source domain-source capability-source provider-source
      sha-source digest-source cas-source kernel-source root-source contract-path]]
  (when-not (and arena-source transport-source dispatch-source entry-source kernel-source
                 syscall-source domain-source capability-source provider-source
                 sha-source digest-source cas-source root-source contract-path)
    (fail! "usage: <arena> <transport> <dispatch> <entry> <syscall> <domain> <capability> <provider> <sha> <digest> <cas> <kernel> <root> <contract>" {}))
  (let [contract (edn/read-string (slurp contract-path))
        sources {'aiueos.value-handle-arena (slurp arena-source)
                 'aiueos.value-runtime-provider-transport (slurp transport-source)
                 'aiueos.value-runtime-dispatch (slurp dispatch-source)
                 'aiueos.value-runtime-entry (slurp entry-source)
                 'aiueos.value-runtime-syscall-plan (slurp syscall-source)
                 'aiueos.value-runtime-domain (slurp domain-source)
                 'aiueos.value-runtime-capability-table (slurp capability-source)
                 'aiueos.value-runtime-provider-policy (slurp provider-source)
                 'aiueos.sha256 (slurp sha-source)
                 'aiueos.digest-equal (slurp digest-source)
                 'aiueos.value-runtime-cas-verify (slurp cas-source)
                 'aiueos.native.kernel (slurp kernel-source)
                 'aiueos.native.value-runtime-kernel (slurp root-source)}
        result (compiler/compile-project
                sources 'aiueos.native.value-runtime-kernel
                :x86_64-aiueos-kernel-v1)
        binary (:binary result)
        binary-bytes (:bytes binary)
        object (:object result)
        values (flattened (:kir result))
        code (get-in result [:artifact :code])
        evidence (get contract :required-evidence)
        required-ops (set (concat (:boot evidence) (:value-runtime evidence)))
        present-ops (set (filter symbol? values))
        opcode (:atomic-opcode evidence)
        artifact-address 0x101150
        syscall-file-offset 0x1090
        planner-call-offset (+ syscall-file-offset 80)
        entry-call-offset (+ syscall-file-offset 148)
        relative-target (fn [call-offset]
                          (+ 0x101000 (- call-offset 0x1000) 5
                             (read-le binary-bytes (inc call-offset) 4)))]
    (when-not (= (:modules contract) (get-in result [:project :kotoba.module/order]))
      (fail! "closed module order mismatch"
             {:actual (get-in result [:project :kotoba.module/order])}))
    (when-not (= (:entry contract) (:entry binary))
      (fail! "native image entry mismatch" {:actual (:entry binary)}))
    (let [phoff (read-le binary-bytes 32 8)
          phentsize (read-le binary-bytes 54 2)
          data-header (+ phoff phentsize)
          data-offset (read-le binary-bytes (+ data-header 8) 8)
          data-address (read-le binary-bytes (+ data-header 16) 8)
          data-size (read-le binary-bytes (+ data-header 32) 8)
          expected-size (get-in contract [:machine-substrate :runtime-data-bytes])]
      (when-not (= expected-size data-size
                   (read-le binary-bytes (+ data-header 40) 8))
        (fail! "runtime RW segment size mismatch"
               {:expected expected-size :actual data-size}))
      (when-not (= [0x0f 0x01 0x15] (subvec binary-bytes 0x100c 0x100f))
        (fail! "boot entry lacks LGDT" {}))
      (when-not (= [0x0f 0x00 0xd8] (subvec binary-bytes 0x1033 0x1036))
        (fail! "boot entry lacks LTR" {}))
      (when-not (= 0x00af9a000000ffff (read-le binary-bytes (+ data-offset 104) 8))
        (fail! "kernel code descriptor mismatch" {}))
      (when-not (= (+ data-address expected-size)
                   (read-le binary-bytes (+ data-offset 172) 8))
        (fail! "TSS RSP0 does not name image-owned stack top" {}))
      (when-not (= 0x101090 (:syscall-entry-address binary))
        (fail! "sealed SYSCALL entry address mismatch"
               {:actual (:syscall-entry-address binary)}))
      (when-not (:value-runtime-live? binary)
        (fail! "ValueRuntime live syscall boundary is disabled" {})))
    (when-not (= (+ artifact-address
                    (get-in result [:artifact :exports
                                    'aiueos-value-runtime-syscall-plan :offset]))
                 (relative-target planner-call-offset))
      (fail! "SYSCALL shim does not call the compiled Kotoba planner" {}))
    (when-not (= (+ artifact-address
                    (get-in result [:artifact :exports
                                    'aiueos-value-runtime-entry :offset]))
                 (relative-target entry-call-offset))
      (fail! "SYSCALL shim does not call the compiled Kotoba entry" {}))
    (when-not (empty? (:imports binary))
      (fail! "native image imports foreign code" {:imports (:imports binary)}))
    (when-not (empty? (:imports object))
      (fail! "native object imports foreign code" {:imports (:imports object)}))
    (when-not (every? present-ops required-ops)
      (fail! "linked image lacks required boot/runtime operations"
             {:required required-ops
              :present (set (filter present-ops required-ops))}))
    (when-not (every? (set values) (:provider-wires evidence))
      (fail! "linked image lacks provider routes" {:required (:provider-wires evidence)}))
    (when-not (some #{opcode} (partition (count opcode) 1 code))
      (fail! "linked image lacks bounded atomic operation" {:opcode opcode}))
    (doseq [[label opcode]
            [[:lstar [0xb9 0x82 0x00 0x00 0xc0 0xb8]]
             [:save-user-rsp [0x48 0x89 0x25]]
             [:sanitize-rflags [0x41 0x81 0xe3 0xd5 0x0a 0x00 0x00]]
             [:sysretq [0x48 0x0f 0x07]]]]
      (when-not (some #{opcode} (partition (count opcode) 1 binary-bytes))
        (fail! "linked image lacks live syscall operation"
               {:operation label :opcode opcode})))
    (when-not (= #{'main 'aiueos-value-runtime-entry
                   'aiueos-value-runtime-syscall-plan
                   'aiueos-value-runtime-publish-domain
                   'aiueos-value-runtime-provider-status
                   'aiueos-value-runtime-capability-grant
                   'aiueos-value-runtime-provider-claim
                   'aiueos-value-runtime-provider-complete
                   'aiueos-value-runtime-cas-verify}
                 (set (get-in result [:kir :exports])))
      (fail! "linked image export set mismatch"
             {:exports (get-in result [:kir :exports])}))
    (println (pr-str {:format :aiueos.value-runtime-kernel-image/verification-v1
                      :modules (get-in result [:project :kotoba.module/order])
                      :entry (:entry binary) :image-bytes (count (:bytes binary))
                      :imports (:imports binary) :foreign-code false
                      :value-runtime-export "kotoba_aiueos_value_runtime_entry"
                      :status :passed}))))
