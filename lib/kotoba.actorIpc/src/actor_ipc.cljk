(ns actor-ipc
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-core Rust crate
  (deleted in kotoba-lang/kami-engine PR #82 \"Remove Rust workspace from kami-engine\")
  as part of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root). Native
  execution stays substrate; this namespace owns the CLJC contracts / data
  interpreters / EDN IR for the domain.

  Mirrors the original crate root `kami-core/src/lib.rs`, whose doc comment reads:
  \"kami-core: Actor + hecs ECS + KAMI Interface (columnar zero-copy)\".

  The original crate declared three type aliases and re-exported the `glam` and
  `hecs` crates:

    pub type EntityId = u64;   // Entity ID (globally unique within an island)
    pub type IslandId = u64;   // Island ID
    pub type Tick = u32;       // Network tick counter
    pub use glam;
    pub use hecs;

  In CLJC there is no static type system, so `EntityId` / `IslandId` / `Tick` are
  represented as plain (non-negative) integers — documented here rather than
  declared as types. `glam` (vector math) and `hecs` (ECS) have no re-export
  equivalent: `glam`-shaped math is expected to live in a sibling portable math
  namespace when needed, and `hecs`'s raw entity-storage internals are NOT ported
  — per ADR-2607010930 and the sibling `kotoba-lang/scene-graph` restoration,
  entities are represented as plain integer/keyword IDs keyed into ordinary CLJC
  maps rather than a native archetype-storage ECS.

  Sub-namespaces (mirroring the original `pub mod` declarations in lib.rs):
    actor-ipc.actor — actor identity / authority / ECS component shapes (actor.rs)
    actor-ipc.ipc   — columnar zero-copy KAMI Interface frame/delta format (ipc.rs)
    actor-ipc.time  — fixed-timestep game clock (time.rs)")

;; EntityId: a plain non-negative integer, globally unique within an island.
;; (Rust: `pub type EntityId = u64;`)
(def entity-id? "Predicate: valid EntityId shape (non-negative integer)." integer?)

;; IslandId: a plain non-negative integer.
;; (Rust: `pub type IslandId = u64;`)
(def island-id? "Predicate: valid IslandId shape (non-negative integer)." integer?)

;; Tick: a plain non-negative integer network tick counter.
;; (Rust: `pub type Tick = u32;`)
(def tick? "Predicate: valid Tick shape (non-negative integer)." integer?)
