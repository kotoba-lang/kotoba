(ns ooyake.methods.social
  "social.cljc — 公 (ooyake) DRY-RUN self-publication projection. ADR-2606272355.

  Projects ooyake's own HISTORY (the gov-units it has atlased — which 省庁/庁/局/課/窓口
  are mirrored, and the aggregate coverage) and PROCEDURES (the civic 手続き wayfinding it
  provides — how a citizen finds the 窓口/書式/手続き for a public service) into social
  posts (app.bsky.feed.post-shaped), enforcing the publication invariants in their
  projection home (mirror of gov-atlas-ontology + the social_post membrane state-machine):

    G3 — every post opens with the civic-wayfinding-mirror disclaimer (isMirror=true),
         is NEVER the government, NEVER an official channel, never adjudicates
         (nonAdjudicatingNotice=true), is person-excluded (no official's personal
         contact, no target-list). It maps the state for citizens to find services.
    no-server-key — serverHeldKey=false; the actor self-custodies its key in its
         kotoba-mesh WASM runtime and signs THERE; the server never does (ADR-2605231525).
    R0-gate — status is 'dry-run' only; `published` is unrepresentable. A live post
         needs Council Lv6+ + operator + a member/actor signature (build-live raises).
    G5 — the post carries ≥2 public official-source citations (provenance URLs /
         Wikidata QIDs); :representative/:unverified-seed rows are never published as
         coverage.

  Pure fns; deterministic; string-keyed post records (house style). Stdlib only —
  the growth (live signing/broadcast) happens actor-side on the mesh, not here."
  (:require [kotoba.lang.text :as str]))

(def DISCLAIMER
  (str "【観測ミラー / civic wayfinding map — NOT the government, NOT an official channel, 非裁定】 "
       "公的機関が既に公開した一次情報から編んだ市民導線マップです。政府を名乗らず、公式チャネルでもありません。"))

(defn- lstrip-colon-id [s]
  (str/replace (str s) #"^:+" ""))

;; ── private helpers (defined before use — Clojure gotcha) ──────────────────
(defn- enough-sources
  "G5 — a post needs ≥2 non-blank public-source citations (provenance URLs / Wikidata QIDs)."
  [sources]
  (let [s (vec (filter #(seq (str/trim (str %))) (or sources [])))]
    (when (< (count s) 2)
      (throw (ex-info "G5: a post needs ≥2 public official-source citations (provenance URL / Wikidata QID)" {})))
    s))

(defn- post
  "Assemble a networkPost record with every invariant pinned. status is ALWAYS dry-run."
  [subject body sources author]
  {":post/subject" subject
   ":post/body" body
   ":post/status" ":dry-run"             ;; R0-gate — published is unrepresentable
   ":post/is-mirror" true                ;; G3
   ":post/non-adjudicating-notice" true  ;; G3
   ":post/server-held-key" false         ;; no-server-key (ADR-2605231525)
   ":post/author" author                 ;; member/actor DID (required only for a gated live post)
   ":post/sources" sources})             ;; G5

(def ^:private level-ja
  {:supranational "超国家機関" :country "国" :region "地域/州" :prefecture "都道府県"
   :municipality "市区町村" :ward "特別区" :ministry "省" :agency "庁" :bureau "局"
   :division "課" :section "係" :window "窓口"})

(defn draft-unit-post
  "HISTORY post — a single gov-unit ooyake has atlased (which 省庁/庁/局/課/窓口 is mirrored).
  Mirror record of a real public body — NEVER claims to BE it."
  ([unit sources] (draft-unit-post unit sources ""))
  ([unit sources author]
   (let [srcs (enough-sources sources)
         lvl  (get unit :gov.unit/level)
         body (str DISCLAIMER "\n\n"
                   "【行政単位】" (get unit :gov.unit/name-local) " (" (get unit :gov.unit/name-en) ") "
                   "[" (get level-ja lvl (str lvl)) "] "
                   "管轄: " (get unit :gov.unit/jurisdiction "—") "。"
                   "ooyake が公式情報からミラーした行政単位の記録(政府を名乗りません)。"
                   "出典 " (count srcs) " 件。")]
     (post (str "unit:" (lstrip-colon-id (get unit :gov.unit/id))) body srcs author))))

(defn draft-coverage-post
  "HISTORY post — aggregate coverage of the atlas (how many units mapped, factual,
  source-cited). Only :authoritative/:maintainer-verified rows count (G5)."
  ([coverage sources] (draft-coverage-post coverage sources ""))
  ([coverage sources author]
   (let [srcs (enough-sources sources)
         body (str DISCLAIMER "\n\n"
                   "【網羅状況】" (get coverage "label") ": "
                   "行政単位 " (get coverage "units_mapped") " 件をミラー"
                   (when-let [j (get coverage "jurisdictions")] (str " (" j " 管轄)")) "。"
                   ":authoritative/:maintainer-verified のみ計上(:representative は非計上)。"
                   "出典 " (count srcs) " 件。")]
     (post (str "coverage:" (get coverage "id")) body srcs author))))

(defn draft-procedure-post
  "PROCEDURE post — civic 手続き wayfinding: how a citizen finds the 窓口/書式/手続き for a
  public service. Cataloging only — ooyake never files/submits (that is toritsugi)."
  ([proc sources] (draft-procedure-post proc sources ""))
  ([proc sources author]
   (let [srcs (enough-sources sources)
         wins (get proc :gov.procedure/window [])
         forms (get proc :gov.procedure/form [])
         body (str DISCLAIMER "\n\n"
                   "【手続き導線】" (get proc :gov.procedure/title-local)
                   " (" (get proc :gov.procedure/title-en) "): "
                   "根拠 " (get proc :gov.procedure/legal-basis "—") "。"
                   "窓口 " (count wins) " / 書式 " (count forms) " 件。"
                   "手数料 " (get proc :gov.procedure/fee "—") "。"
                   "市民導線の案内のみ — 申請・提出は ooyake ではなく toritsugi(gated)。"
                   "出典 " (count srcs) " 件。")]
     (post (str "procedure:" (lstrip-colon-id (get proc :gov.procedure/id))) body srcs author))))

(defn build-live
  "live posting is outward-gated. Refuses by construction at R0; the live signature is
  the actor's own mesh-runtime key, presented (never server-held) under Council Lv6+ +
  operator gate (§1.12 / G10)."
  [& _args]
  (throw (ex-info (str "ooyake R0: live social posting is Council Lv6+ + operator + member/actor-signature "
                       "gated (§1.12/G10). Only dry-run posts are producible offline; the live signature "
                       "happens actor-side in the kotoba-mesh runtime, never with a server key.") {})))
