(ns kami-app-giemon-factory.robots
  "The construction-robot roster (`Robots`/`Robot` in `scene.rs`), generated
  in the original crate from `robots.edn` into `robots.json` and
  deserialized via serde. That JSON is not present anywhere in this monorepo
  checkout, so `Robots::load` is not ported — callers supply the parsed
  roster map.

  A roster map: `{:robots/robots [robot ...]}`. Each robot:
  `{:id .. :name .. :kind .. :reach-m .. :base [x y] :cycle-min .. :mobile ..
  :process .. :maturity ..}` — 1:1 with the Rust `Robot` fields (`kind` is
  the Rust `#[serde(rename = \"type\")] kind`; `process` is
  \"deposition\" | \"thermal-weld\" | \"none\")."
  )

(defn by-id
  "Look up a robot by id (the Rust `Robots::get`)."
  [robots id]
  (some #(when (= (:id %) id) %) (:robots/robots robots)))
