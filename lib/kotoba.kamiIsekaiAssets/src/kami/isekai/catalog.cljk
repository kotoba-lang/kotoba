(ns kami.isekai.catalog
  "One-stop introspection over everything the library knows how to compose —
   for a caller building a character-creator UI, a `bb` script that wants to
   sanity-check an id before calling compose-character, or just someone
   exploring the library at a REPL without opening every namespace. Every
   other module is authoritative for its own ids (this just aggregates
   them, read-only, no new data)."
  (:require [kami.isekai.races :as races]
            [kami.isekai.classes :as classes]
            [kami.isekai.skills :as skills]))

(defn race-ids [] (set (keys races/races)))
(defn class-ids [] (set (keys classes/classes)))
(defn skill-ids [] (set (keys skills/skills)))

;; monster/structure/tensei composers are functions, not a data map (each
;; has its own arity/args — a slime takes an optional hue, a goblin-raider
;; takes a seed), so there's no single registry to introspect the way
;; races/classes/skills are; this documents the known ids as data anyway so
;; a caller (or a test) can validate an id string without importing every
;; monsters/structures/tensei fn.
(def monster-ids
  #{:slime :slime-fire :slime-ice :slime-poison :goblin-raider :orc-brute
    :kobold-scout :troll :wyvern :dragon :skeleton :ghost :wolf})

(def structure-ids #{:castle :guild-hall :summoning-circle})

(defn known-race?    [id] (contains? (race-ids) id))
(defn known-class?   [id] (contains? (class-ids) id))
(defn known-skill?   [id] (contains? (skill-ids) id))
(defn known-monster?   [id] (contains? monster-ids id))
(defn known-structure? [id] (contains? structure-ids id))

(defn summary
  "A plain-data snapshot of the whole catalog's size — what bb test's final
   println already reports per-run, exposed as a callable fn too."
  []
  {:races (count (race-ids)) :classes (count (class-ids))
   :monsters (count monster-ids) :skills (count (skill-ids))
   :structures (count structure-ids)})
