(ns kotoba.capability.dma.map
  "Importable contract for dma/map.")

(def manifest
  {:schema "kotoba.capability.repository.v1", :capability/version 1, :capability/hash-contract-cid "bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi", :capability/definition-cid "bafyreies4n3abl6d5ei6mfmcel3xsn7lcjqzyn43hboqgk54wsccudtf6u", :capability/dependencies #{}, :capability/imports #{:dma-map}, :authority "kotoba-lang/kotoba-core-contracts", :capability/default-policy :autonomous, :capability/artifact {:format :wasm-component, :digest-required? true, :signature-required? true}, :capability/radicle-rid "rad:zR1KKTVy51jQ9vHzLw6RoCfYi43K", :capability/repository "kotoba-lang/capability-dma-map", :capability/id "dma/map", :capability/effects #{:memory-access :device-control}, :capability/provider-status :contract-only})

(def descriptor-owned 0x80000000)
(def descriptor-end-of-ring 0x40000000)
(def descriptor-first-fragment 0x20000000)
(def descriptor-last-fragment 0x10000000)

(def tx-publication-order
  [:write-extension :write-address :release-fence :set-owner
   :release-fence :doorbell])

(def rx-publication-order
  [:write-extension :write-address :release-fence :set-owner :release-fence])

(defn tx-command [length]
  (bit-or descriptor-owned descriptor-end-of-ring
          descriptor-first-fragment descriptor-last-fragment length))

(defn rx-command [capacity]
  (bit-or descriptor-owned descriptor-end-of-ring capacity))

(defn device-owned? [command]
  (not (zero? (bit-and command descriptor-owned))))
