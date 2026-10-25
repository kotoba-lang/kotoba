(ns actor-ipc.actor
  "Actor model: network-authoritative entity state. Restored from the legacy
  kami-engine/kami-core Rust crate's `src/actor.rs` (82 lines), deleted in
  kotoba-lang/kami-engine PR #82 \"Remove Rust workspace from kami-engine\", as
  part of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Original doc comment: \"Each Actor owns a hecs::World partition. Authority
  determines who is canonical. Actors communicate via Mailbox (KNP
  transport-agnostic).\"

  hecs-ECS-to-plain-map adaptation: the original `ActorId` referenced a
  `hecs::World`-partitioned `EntityId`. hecs's raw archetype/entity-storage
  internals are NOT ported (no CLJC equivalent) — per ADR-2607010930 and the
  sibling `kotoba-lang/scene-graph` restoration, entities are represented as
  plain integer IDs (`actor-ipc/entity-id?`) keyed into ordinary CLJC maps rather than
  a native ECS. The `components` submodule below (originally `#[repr(C)]`
  `bytemuck::Pod` GPU-layout structs) becomes plain CLJC maps with keyword keys;
  there is no GPU-buffer memory layout to preserve in portable CLJC.")

;; --- Authority -------------------------------------------------------------
;; Rust: `pub enum Authority { Server, Client, Predicted }`
;; Who owns the canonical state for this actor.
(def authority-values
  "Valid Authority keywords.
  :server    — Server is canonical (economy, HP, inventory).
  :client    — Client is canonical (camera, input).
  :predicted — Client predicts, server reconciles (position, animation)."
  #{:server :client :predicted})

;; --- ActorType ---------------------------------------------------------
;; Rust: `#[repr(u8)] pub enum ActorType { Player = 0, Npc = 1, Item = 2,
;;         Projectile = 3, Vehicle = 4, Trigger = 5, World = 6 }`
;; Actor type determines which components are attached.
(def actor-type-codes
  "ActorType keyword -> original Rust `#[repr(u8)]` discriminant, preserved for
  wire-format parity with any consumer still expecting the numeric code."
  {:player 0
   :npc 1
   :item 2
   :projectile 3
   :vehicle 4
   :trigger 5
   :world 6})

(def actor-type-values
  "Valid ActorType keywords."
  (set (keys actor-type-codes)))

(defn actor-type->code
  "ActorType keyword -> numeric discriminant. Mirrors the Rust `#[repr(u8)]` cast."
  [actor-type]
  (get actor-type-codes actor-type))

(defn code->actor-type
  "Numeric discriminant -> ActorType keyword (inverse of `actor-type->code`)."
  [code]
  (some (fn [[k v]] (when (= v code) k)) actor-type-codes))

;; --- ActorId -----------------------------------------------------------
;; Rust:
;;   pub struct ActorId {
;;       pub entity_id: EntityId,
;;       pub island_id: IslandId,
;;       pub actor_type: ActorType,
;;       pub authority: Authority,
;;   }
;; Actor identity on the network, as a plain CLJC map.
(defn make-actor-id
  "Construct an ActorId map: {:entity-id :island-id :actor-type :authority}.
  Mirrors the Rust `ActorId` struct fields 1:1."
  [entity-id island-id actor-type authority]
  {:entity-id entity-id
   :island-id island-id
   :actor-type actor-type
   :authority authority})

;; --- components ----------------------------------------------------------
;; Rust `pub mod components`: standard ECS components for game actors, all
;; originally `#[repr(C)] #[derive(Pod, Zeroable)]` GPU-layout structs. Ported
;; as plain CLJC maps with keyword keys (no GPU memory layout in portable CLJC);
;; each `make-*` constructor mirrors the original struct's field shape.

(defn make-position
  "Rust: `pub struct Position(pub [f32; 3]);`"
  [x y z]
  {:position [x y z]})

(defn make-rotation
  "Rust: `pub struct Rotation(pub [f32; 4]); // quaternion xyzw`"
  [x y z w]
  {:rotation [x y z w]})

(defn make-velocity
  "Rust: `pub struct Velocity(pub [f32; 3]);`"
  [x y z]
  {:velocity [x y z]})

(defn make-scale
  "Rust: `pub struct Scale(pub [f32; 3]);`"
  [x y z]
  {:scale [x y z]})

(defn make-animation-state
  "Rust: `pub struct AnimationState { pub clip_id: u16, pub frame: u16 }`"
  [clip-id frame]
  {:clip-id clip-id :frame frame})

(defn make-health
  "Rust: `pub struct Health { pub current: u16, pub max: u16 }`"
  [current max]
  {:current current :max max})

(defn make-mesh-id
  "Rust: `pub struct MeshId(pub u32);`"
  [id]
  {:mesh-id id})

(defn make-material-id
  "Rust: `pub struct MaterialId(pub u32);`"
  [id]
  {:material-id id})
