(ns kotoba.capability.link.frame
  "Importable contract for link/frame.")

(def manifest
  {:schema "kotoba.capability.repository.v1", :capability/version 1, :capability/hash-contract-cid "bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi", :capability/definition-cid "bafyreigozrpzqrltjlmc4kfzhxrrc7e5noquzcjmzkzoy4tiusa7d43hii", :capability/dependencies #{}, :capability/imports #{:frame-send :frame-receive}, :authority "kotoba-lang/kotoba-core-contracts", :capability/default-policy :approval-required, :capability/artifact {:format :wasm-component, :digest-required? true, :signature-required? true}, :capability/radicle-rid "rad:z4LnHVR6NKbSTsuWxF8HxExmBct72", :capability/repository "kotoba-lang/capability-link-frame", :capability/id "link/frame", :capability/effects #{:data-egress :no-addressing-boundary :network-read :network-write :device-control}, :capability/provider-status :contract-only})

(def ethernet-header-bytes 14)
(def ethernet-min-frame-bytes 60)
(def ethernet-max-frame-bytes 1514)

(defn tx-wire-length
  "Return the pre-FCS Ethernet length a provider must publish, or nil when the
  caller did not supply a standard untagged Ethernet frame. Short valid frames
  are padded to 60 bytes; payload length fields remain unchanged."
  [frame-length]
  (when (<= ethernet-header-bytes frame-length ethernet-max-frame-bytes)
    (max ethernet-min-frame-bytes frame-length)))

(defn ipv4-datagram-fits?
  "True when an IPv4 total-length is wholly present in FRAME-LENGTH. Ethernet
  padding after the datagram is intentionally accepted."
  [frame-length ipv4-total-length]
  (and (<= 20 ipv4-total-length)
       (<= (+ ethernet-header-bytes ipv4-total-length) frame-length)))
