(ns pnr.upf-adapter
  "Bridges org-ieee-upf (UPF, IEEE 1801 power intent: domains/supplies/
  states/isolation) into pnr.placement / pnr.floorplan. Neither pnr
  namespace previously knew anything about power intent -- `pnr.placement`
  had no notion that two cells might belong to different power domains,
  and `pnr.floorplan` blocks carried no domain tag at all -- so
  power-domain-aware floorplanning/placement (a standard EDA requirement:
  cells in different power domains must not violate domain boundaries, and
  level-shifters/isolation cells are needed at domain crossings) was
  simply not possible. This namespace is that missing bridge: it resolves
  each placed cell's UPF power domain via longest-prefix instance-path
  matching (`upf.domain/instance-domain`), partitions a placement by
  domain, finds nets that cross domain boundaries (exactly where a real
  UPF flow needs isolation cells / level shifters, per
  `upf.strategy/applicable-strategies`), and validates that placed cells
  respect the power-domain boundaries a floorplan block declares."
  (:require [upf.domain :as upf-domain]
            [upf.strategy :as upf-strategy]))

(defn cell-power-domain
  "Resolve one `pnr.placement/place-cells` output cell's
  (`{:cell-name :instance-name :x :y :orientation :row-idx}`) UPF power
  domain: looks up `(:instance-name placed-cell)` as the instance path
  against `domain-registry` (a collection of
  `upf.domain/create-power-domain` maps) via `upf.domain/instance-domain`'s
  longest-prefix match. Returns the domain name string, or nil when no
  domain in `domain-registry` covers the instance (unscoped)."
  [domain-registry placed-cell]
  (upf-domain/instance-domain domain-registry (:instance-name placed-cell)))

(defn partition-by-domain
  "Group `placed-cells` (a `pnr.placement/place-cells` `:cells` seq) by
  their resolved UPF power domain (`cell-power-domain`). Returns a map
  `{domain-name [cells...] ... :unscoped [cells...]}` -- cells whose
  instance path isn't covered by any domain in `domain-registry` land
  under the `:unscoped` key rather than being dropped or erroring."
  [domain-registry placed-cells]
  (group-by #(or (cell-power-domain domain-registry %) :unscoped) placed-cells))

(defn- instance->domain-map
  "Precompute `{instance-name resolved-domain-or-nil ...}` once for
  `placed-cells`, so `domain-crossing-nets` doesn't re-run longest-prefix
  matching per net per pin."
  [domain-registry placed-cells]
  (into {}
        (map (fn [c] [(:instance-name c) (cell-power-domain domain-registry c)]))
        placed-cells))

(defn domain-crossing-nets
  "Identify nets that connect cells in more than one resolved UPF power
  domain -- exactly the nets a real UPF flow needs isolation cells or
  level shifters on, per `upf.strategy/applicable-strategies`.

  `net->pins` is a map `{net-name [instance-name ...] ...}`: net name to
  the vector of placed-cell instance names it connects. `pnr.placement`
  has no per-pin/per-port connectivity model of its own (only placed
  instances), so instance-name-level connectivity is the natural shape to
  bridge from here; a future finer-grained (per-pin) net model can layer
  on top without changing this contract. Instance names that aren't among
  `placed-cells`, or that resolve to no domain, don't contribute a domain
  to the net -- an unplaced or unscoped endpoint can't be the *other side*
  of a domain crossing.

  `strategies` is an optional collection of `upf.strategy/set-isolation` /
  `set-level-shifter` maps (defaults to `[]`, in which case crossings are
  still detected/reported but `:required-strategies` is always empty).
  For each crossing net, `:required-strategies` is the concatenation, in
  domain order, of `upf.strategy/applicable-strategies` called once per
  domain the net touches -- a crossing needs whatever strategies either
  side of the boundary declares (e.g. an isolation cell driven by the
  source domain's strategy, a level shifter required by the destination
  domain's).

  Returns a vector of `{:net net-name :domains #{domain-a domain-b ...}
  :required-strategies [...]}`, one entry per crossing net. Nets that
  resolve to zero or one distinct domain (fully unscoped, or fully inside
  one domain) are omitted."
  ([domain-registry placed-cells net->pins]
   (domain-crossing-nets domain-registry placed-cells net->pins []))
  ([domain-registry placed-cells net->pins strategies]
   (let [instance->domain (instance->domain-map domain-registry placed-cells)]
     (vec
      (keep (fn [[net-name instance-names]]
              (let [domains (into #{} (keep instance->domain) instance-names)]
                (when (> (count domains) 1)
                  {:net net-name
                   :domains domains
                   :required-strategies (vec (mapcat #(upf-strategy/applicable-strategies strategies %)
                                                      domains))})))
            net->pins)))))

(defn- point-in-block?
  "Whether placed-cell point `(x, y)` falls within `block`'s bounds
  (`pnr.floorplan` block: `:x :y :width :height`), half-open interval on
  both axes -- matches `pnr.floorplan/overlaps?`'s own convention, so a
  cell sitting exactly on a shared edge between two abutting blocks
  belongs to at most one of them."
  [block x y]
  (and (>= x (:x block)) (< x (+ (:x block) (:width block)))
       (>= y (:y block)) (< y (+ (:y block) (:height block)))))

(defn validate-domain-placement
  "Validate that placed cells respect the power-domain boundaries declared
  on `floorplan-blocks` (a `pnr.floorplan` `:blocks` seq, each already
  placed -- i.e. carrying `:x`/`:y`/`:width`/`:height`, as produced by
  `pnr.floorplan/auto-floorplan` or `add-block`).

  POLICY -- a block declares its power domain via an optional
  `:power-domain` key (a domain name string matching
  `upf.domain/create-power-domain`'s `:name`); `pnr.floorplan` itself has
  no built-in notion of power domains, so this key is this adapter's own
  convention layered on top. Blocks without `:power-domain` are treated as
  unscoped and are skipped entirely -- no domain policy to check placed
  cells inside them against. For every domain-scoped block, every placed
  cell whose `(:x :y)` falls within the block's bounds
  (`point-in-block?`) must resolve, via `cell-power-domain`, to that
  *same* domain. An unscoped cell (resolves to nil) placed inside a
  domain-scoped block IS a violation: the block asserts a domain
  boundary, so a cell of undeclared power intent inside it can't be
  verified consistent with that boundary. A cell inside a block that
  itself declares no power domain is never flagged, regardless of the
  cell's own resolved domain.

  Returns a vector of `{:cell instance-name :expected-domain
  block's-:power-domain :actual-domain (resolved domain or nil) :block
  block-name}` violation maps (empty vector = no violations)."
  [domain-registry placed-cells floorplan-blocks]
  (vec
   (for [block floorplan-blocks
         :when (:power-domain block)
         cell placed-cells
         :when (point-in-block? block (:x cell) (:y cell))
         :let [actual-domain (cell-power-domain domain-registry cell)]
         :when (not= actual-domain (:power-domain block))]
     {:cell (:instance-name cell)
      :expected-domain (:power-domain block)
      :actual-domain actual-domain
      :block (:name block)})))
