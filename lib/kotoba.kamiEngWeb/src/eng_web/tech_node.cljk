(ns eng-web.tech-node
  "Technology-node name parsing, restored from `kami-eng-web/src/lib.rs`
  (`parse_tech_node` helper + the `TechNode` string branches used by
  `pdk_tech_info`/`pdk_stdcell_library`/`pdk_compile_memory`), part of the
  legacy `kami-engine` Rust workspace deleted in kotoba-lang/kami-engine
  PR #82 (\"Remove Rust workspace from kami-engine\"). See ADR-2607010930
  (`com-junkawasaki/root`).

  This is the only piece of `kami-eng-web::parse_tech_node` that is portable:
  the actual `kami_pdk::TechFile`/`stdcell`/`memory` compilation this keyword
  feeds into lives in the unported `kami-pdk` crate."
  (:require [kotoba.lang.text :as str]))

(def tech-nodes
  "Ordered from oldest to newest process node, mirroring the original Rust
  match arms (`N180` .. `N2`)."
  [:n180 :n130 :n90 :n65 :n45 :n28 :n22 :n16 :n14 :n10 :n7 :n5 :n3 :n2])

(def ^:private name->node
  (into {} (map (fn [k] [(str/upper (name k)) k]) tech-nodes)))

(defn parse-tech-node
  "Parse a technology-node name (e.g. \"N7\", \"n5\") into a keyword
  (`:n7`, `:n5`, ...). Case-insensitive, matching the original Rust
  `node.to_uppercase().as_str()` dispatch. Returns nil for unknown nodes."
  [node]
  (get name->node (str/upper (str node))))
