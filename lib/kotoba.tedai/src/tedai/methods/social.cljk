(ns tedai.methods.social
  "social.cljc — tedai DRY-RUN self-publication seed (ADR-2606272355, auto-seeded R0).

  This is a GENERIC self-publication projection (draft-observation-post below builds an
  app.bsky.feed.post-shaped record), mechanically derived from tedai's own
  manifest (:actor/purpose). It is an R0 SEED, not a bespoke domain projection (contrast
  danjo/keizu/monosashi, which hand-author their own draft-*-post shapes) — a future actor
  evolution pass MAY replace draft-observation-post with domain-specific post types, same as
  danjo did for its tax-revenue-ledger domain. Until then this seed satisfies the same
  invariants every sibling social_post membrane enforces:

    non-adjudicating mirror — every post opens with the observational disclaimer; narrates,
      never asserts a verdict.
    source-provenance — a post needs ≥2 cited sources (mirrors the common G5-class gate).
    no-server-key — :post/server-held-key is always false; the actor would self-custody its
      own key in its mesh-runtime WASM (ADR-2605231525), never a server-held key.
    R0-gate — status is 'dry-run' only; a live post needs Council Lv6+ + operator + a
      member/actor signature (build-live raises unconditionally at R0).

  Pure fns; deterministic; string-keyed post records (house style). Stdlib only."
  (:require [kotoba.lang.text :as str]))

(def DISCLAIMER
  (str "【観測ミラー / accountability map — NOT a verdict, NOT advice, 非断定】 "
       "tedai が既知の観測から編んだ事実の要約です。"))

(defn- enough-sources
  "≥2 non-blank source citations, mirroring the common G5-class source-provenance gate."
  [sources]
  (let [s (vec (filter #(seq (str/trim (str %))) (or sources [])))]
    (when (< (count s) 2)
      (throw (ex-info "source-provenance: a post needs \u2265 2 citations" {})))
    s))

(defn draft-observation-post
  "A dry-run observation post over tedai's own domain (Member-computer operation (手代 = the Edo merchant-house clerk who operates the house's affairs on the master's instruction and under the…)."
  ([subject body sources] (draft-observation-post subject body sources ""))
  ([subject body sources author]
   (let [srcs (enough-sources sources)
         full (str DISCLAIMER "\n\n" body " 出典 " (count srcs) " 件。")]
     {":post/subject" subject
       ":post/body" full
       ":post/status" ":dry-run"
       ":post/is-mirror" true
       ":post/non-adjudicating-notice" true
       ":post/server-held-key" false
       ":post/author" author
       ":post/sources" srcs})))

(defn build-live
  "live posting is outward-gated. Refuses by construction at R0; the live signature is the
  actor's own mesh-runtime key, presented (never server-held) under Council Lv6+ + operator
  gate. Only dry-run posts are producible offline."
  [& _args]
  (throw (ex-info (str "tedai R0: live social posting is Council Lv6+ + operator + "
                       "member/actor-signature gated. Only dry-run posts are producible "
                       "offline; the live signature happens actor-side in the kotoba-mesh "
                       "runtime, never with a server key.") {})))
