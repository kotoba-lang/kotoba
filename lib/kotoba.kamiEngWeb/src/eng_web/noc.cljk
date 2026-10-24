(ns eng-web.noc
  "Network-on-Chip topology parsing + config defaults, restored from
  `kami-eng-web/src/lib.rs` (`ip_generate_noc` wasm entry point), part of the
  legacy `kami-engine` Rust workspace deleted in kotoba-lang/kami-engine
  PR #82. See ADR-2607010930 (`com-junkawasaki/root`).

  Portable: the `topology` string -> `kami_ip::NocTopology` construction and
  the fixed `NocConfig` defaults (`data_width`/`flit_size`/routing).
  Excluded: the actual `kami_ip::noc::generate_noc` router/link synthesis,
  which lives in the unported `kami-ip` crate."
  (:require [kotoba.lang.text :as str]))

(defn parse-topology
  "Parse a NoC topology string (\"mesh\"/\"ring\"/\"crossbar\", case
  insensitive) plus a `rows`/`cols` grid size into a `NocTopology` map,
  mirroring the original Rust match arms 1:1. Returns nil for unknown
  topologies."
  [topology rows cols]
  (case (str/lower (str topology))
    "mesh"     {:type :mesh :rows rows :cols cols}
    "ring"     {:type :ring :nodes (* rows cols)}
    "crossbar" {:type :crossbar :ports (* rows cols)}
    nil))

(defn noc-config
  "Build the `NocConfig` used by `ip_generate_noc`, with the original Rust's
  fixed `data_width`/`flit_size`/XY-routing defaults."
  [topology]
  {:topology topology
   :data-width 64
   :flit-size 128
   :routing :xy})
