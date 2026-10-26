(ns kotoba.capability.net.transport
  "Importable contract for net/transport.")

(def manifest
  {:schema "kotoba.capability.repository.v1", :capability/version 1, :capability/hash-contract-cid "bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi", :capability/definition-cid "bafyreicau5taerbqprf56lozef43vgiqygffa6muiuniati2ejmrkrpwzm", :capability/dependencies #{}, :capability/imports #{:transport-write :transport-close :transport-read}, :authority "kotoba-lang/kotoba-core-contracts", :capability/default-policy :approval-required, :capability/artifact {:format :wasm-component, :digest-required? true, :signature-required? true}, :capability/radicle-rid "rad:zmDR3paxbM73DcNvH2ssmZjidhDb", :capability/repository "kotoba-lang/capability-net-transport", :capability/id "net/transport", :capability/effects #{:data-egress :network-read :network-write}, :capability/provider-status :contract-only})

(defn tcp-header-length [data-offset-byte]
  (let [length (* 4 (bit-shift-right (bit-and data-offset-byte 0xf0) 4))]
    (when (<= 20 length 60) length)))

(defn syn-ack-shape?
  "Accept SYN-ACK with a valid TCP option area and no payload. IPv4-TOTAL is
  the IPv4 total length for an IHL=20 packet."
  [ipv4-total tcp-header flags]
  (and (<= 40 ipv4-total)
       (<= 20 tcp-header 60)
       (= tcp-header (- ipv4-total 20))
       (= flags 0x12)))
