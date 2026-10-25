(ns kotoba.sarutahiko-factory.prod-order
  "Production line (station schedule) — ported from `scene.rs`'s
  `ProdOrder` / `ProdStation`. The physical flow of a truck body through
  these stations (`ProductionLine` in `lib.rs`: kami-genesis position-PD
  stepping between station coordinates, paint recolour, hand-off to the
  loader) is unported host-adapter physics; this namespace keeps only the
  station schedule data and its pure validation.

  A `prod-order` value is a plain EDN map:

    :prod-order/of        string (subject factory name)
    :prod-order/takt-s    any (opaque takt-time value, mirrors the Rust
                           `serde_json::Value` catch-all field)
    :prod-order/stations  [{:station/seq :station/id :station/name
                             :station/layer :station/op :station/x
                             :station/y :station/cell :station/cycle-s} ...]

  `:station/op` is one of receive | frame-weld | cab-weld | paint |
  marriage | eol-test | stage | ship (per the Rust doc-comment); this
  namespace treats it as an opaque string and only validates presence/
  ordering, not the vocabulary.

  Pure: no I/O. See `kotoba.sarutahiko-factory.fixtures/prod-order` for
  this repo's synthetic test fixture."
  (:require [kotoba.lang.text :as str]))

(defn stations [order] (:prod-order/stations order))

(defn seq-contiguous?
  "True when station `:station/seq` values are exactly `1..n` in order."
  [order]
  (= (mapv :station/seq (stations order))
     (vec (range 1 (inc (count (stations order)))))))

(defn first-op [order] (:station/op (first (stations order))))
(defn last-op [order] (:station/op (last (stations order))))

(defn has-op?
  "True when any station's `:station/op` equals `op`."
  [order op]
  (boolean (some #(= op (:station/op %)) (stations order))))

(defn cells-used
  "The set of non-blank `:station/cell` ids referenced by the line."
  [order]
  (into #{} (remove str/blank?) (map :station/cell (stations order))))

(defn stations-resolve-cells?
  "True when every non-blank `:station/cell` is a member of `known-cell-ids`
  (e.g. the union of factory cell ids and loader ids)."
  [order known-cell-ids]
  (let [known (set known-cell-ids)]
    (every? known (cells-used order))))
