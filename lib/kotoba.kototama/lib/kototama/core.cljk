(ns kototama.core
  "kototama — the common Clojure library for building CELLS and ARTIFICIAL
  ORGANISMS on kotoba. The distilled subset of the kotodama framework + the
  ibuki organism pattern, dependency-free `.cljc` so it runs on bb / JVM and
  inside the kototama Rust→WASM runtime.

  Layers (require the one you need):
    kototama.kotoba    — append-only content-addressed Datom log (the DB)
    kototama.cell      — defcell: pure solve : state -> state
    kototama.life      — joucho (mood) + metabolism, folded off the log
    kototama.gates     — unified charter membrane (leashed? / may-draft? / §2 scan
                         / no-advice / may-actuate?)
    kototama.leash     — revocable member CACAO capability (present-only)
    kototama.didkey    — self-certifying did:key encoding (Ed25519 → z6Mk…)
    kototama.identity  — Ed25519 self-key generation + non-secret identity record
    kototama.emit      — member-signed post envelope → app-aozora / com-etzhayyim
    kototama.atproto   — AT-Protocol record surface (profile / feed-post / at-uri)
    kototama.membrane  — draft / build-live outward self-publication seam
    kototama.heartbeat — pure idempotent-by-content beat decision
    kototama.organism  — the heartbeat: replay→perceive→feel→decide→narrate→act→persist

  Consumers: kototama.unspsc.* (the 18,342-actor fleet) and external actors such
  as etzhayyim kyoninka 許認可 (autonomous readiness-digest posts)."
  (:require [kototama.kotoba :as kotoba]
            [kototama.cell :as cell]
            [kototama.life :as life]
            [kototama.gates :as gates]
            [kototama.leash :as leash]
            [kototama.didkey :as didkey]
            [kototama.emit :as emit]
            [kototama.atproto :as atproto]
            [kototama.membrane :as membrane]
            [kototama.heartbeat :as heartbeat]
            [kototama.organism :as organism]))

;; thin re-exports for the common path
(def connect     kotoba/connect)
(def transact    kotoba/transact)
(def verify-chain kotoba/verify-chain)
(def fold-mood   life/fold-mood)
(def metabolism  life/metabolism)
(def make-leash  leash/leash)
(def did-key     didkey/did-key)
(def make-organism organism/organism)
(def beat        organism/beat)
(def autorun     organism/autorun)
(def scan        gates/scan)
(def feed-post   atproto/feed-post)
(def draft       membrane/draft)
