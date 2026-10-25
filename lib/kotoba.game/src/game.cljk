(ns game
  "KAMI Game — game systems: physics, input, NPC AI, inventory, economy,
  triggers, prediction, arena, addons (C5-C15), gameshell, island
  generation, W Protocol CQRS. Restored from the legacy kami-engine/
  kami-game Rust crate (17874 lines across 30 files, deleted in
  kotoba-lang/kami-engine PR #82 'Remove Rust workspace from
  kami-engine') as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Restored as a 7-cluster parallel restoration (owner decision
  2026-07-02) — each cluster's agent worked in isolation on its own
  git branch (`game-cluster-a` .. `game-cluster-g`) against a disjoint
  set of source files, then all 7 branches were merged server-side
  into `main`. Because clusters worked without visibility into each
  other's in-progress code, several files inline small locally
  duck-typed stand-ins for types that are 'really' owned by another
  cluster's module (e.g. `game.trigger`/`game.arena` duck-type
  `physics.rs`/`scene.rs` shapes; `game.island-gen` duck-types
  `scene.rs`/`brainrot-mesh.rs` shapes) — each such case is documented
  with a comment at its point of use. These are NOT reconciled into a
  single shared type in this assembly pass; each namespace's
  duck-typed shape is compatible with (a structural subset of) the
  namespace that 'owns' the concept, so cross-namespace calls that
  pass plain maps work correctly, but two duck-typed versions of the
  'same' concept are not `=`-identical Clojure records.

  One namespace per original Rust `pub mod` (mirroring `lib.rs`'s
  module list; alphabetized here for readability):
    game.addons          - C5-C15 grab-bag (leaderboard/daily-bonus/missions/gacha/energy/telemetry)
    game.animation       - clip/preset animation system
    game.arena           - Arena demo scene
    game.battle-royale   - storm/bus/weapons/building/match state machine
    game.brainrot-mesh   - procedural brainrot character mesh generation
    game.common          - deterministic xorshift32 PRNG + shared helpers
    game.economy         - gems wallet/economy
    game.gameshell       - HUD state
    game.input           - keyboard input -> movement velocity
    game.inventory       - stack/remove/equip inventory
    game.island-gen      - Godot game catalog -> KAMI island scene generation
    game.ketsu           - 'Goriketsu Dash!!' chase minigame
    game.npc             - behavior tree + brainrot NPC behaviors
    game.physics         - game-glue AABB rigid-body physics
    game.platform        - platform detection (iOS/Android/Web)
    game.pokoa           - Pokemon-style 'brainrot meme' creature battler
    game.pokoa-mesh      - Pokoa creature mesh generation
    game.prediction      - client-side prediction + server reconciliation
    game.quality         - Nintendo-grade game quality scorer
    game.quarry-scene    - procedural humanoid mesh + player physics/camera
    game.ranked          - rank tiers/MMR/matchmaking
    game.sabiotoshi      - 'Sabi-Otoshi!!' rust-restoration minigame
    game.scene           - JSON-LD IslandScene data model
    game.sprite          - 2D sprites
    game.terrain         - heightmap -> LOD mesh pipeline (game-tuning variant)
    game.trigger         - sensor triggers
    game.voxel           - chunked voxel world (game-tuning variant)
    game.voxel-mesh      - naive + greedy voxel meshing
    game.wproto          - W Protocol CQRS wire types

  Zero-dep portable CLJC - pure data + pure functions, no IO/GPU."
  (:require [game.addons]
            [game.analytics]
            [game.cloud-save]
            [game.animation]
            [game.arena]
            [game.battle-royale]
            [game.battle-pass]
            [game.brainrot-mesh]
            [game.common]
            [game.economy]
            [game.gameshell]
            [game.input]
            [game.inventory]
            [game.island-gen]
            [game.ketsu]
            [game.missions]
            [game.npc]
            [game.physics]
            [game.platform]
            [game.push]
            [game.pokoa]
            [game.pokoa-mesh]
            [game.prediction]
            [game.quality]
            [game.quarry-scene]
            [game.ranked]
            [game.sabiotoshi]
            [game.scene]
            [game.sprite]
            [game.subscription]
            [game.terrain]
            [game.trigger]
            [game.voxel]
            [game.voxel-mesh]
            [game.wproto]))
