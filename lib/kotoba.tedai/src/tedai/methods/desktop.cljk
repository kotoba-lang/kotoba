(ns tedai.methods.desktop
  "tedai (手代) DesktopOp parser/planner — member-computer operation, stdlib only (ADR-2606101400).

  1:1 Clojure port of `20-actors/tedai/methods/desktop.py`.

  The uniform vocabulary is a normalized DesktopOp (the karakuri ServiceOp
  pattern lifted to the OS layer): `app` · `noun` · `verb` · classified `safety`
  (read/create/update/delete/outward) + a `destructive` flag + the selected
  adapter `tier`. A CLI string

      tedai <app> <noun>.<verb> [--flag value ...]

  parses into exactly one DesktopOp. This module does the offline-safe parts
  purely and deterministically: command parsing, app resolution against a
  :representative registry, safety classification (incl. the OS-layer-specific
  `:outward` class — a verb whose effect leaves the device: send/pay/post/upload),
  adapter-tier selection (T1 scripting/accessibility-API first), the stance gate
  (the T2 vision-pointer adapter is refused on a synthetic-input-prohibited app
  — G2; anti-cheat games and DRM players are the canonical case), the karakuri
  route (browser apps are karakuri's surface — N7), and the mutate/outward gates
  (G5). It emits a dry-run plan and never injects input or touches the network
  (G6). The T2 vision action plan is built by `t2_vision.py`.

  G1 own-device · G2 T1-preferred / stance-honest · G5 read-default/mutate-gated
  + outward-gated · G6 actuation-gated · G8 :representative registry (unknown app
  degrades honestly) · N7 browser → karakuri.

  Pure Clojure (clojure.core + clojure.string only), portable .cljc."
  (:require [kotoba.lang.text :as str]))

;; ═════════════════════════════════════════════════════════════════════════════
;; Constants
;; ═════════════════════════════════════════════════════════════════════════════

;; The T2 (vision-pointer / computer-use) engine: an ON-DEVICE vision agent
;; (baien edge, ADR-2605241900) or LAN Murakumo (G4). A screenshot never leaves
;; the device — cloud computer-use APIs are structurally unrepresentable.
(def T2-ENGINE "on-device-vision")

;; Safety classification (G5). The verb determines whether an op reads, mutates,
;; or leaves the device.
(def SAFETY-READ "read")
(def SAFETY-CREATE "create")
(def SAFETY-UPDATE "update")
(def SAFETY-DELETE "delete")
(def SAFETY-OUTWARD "outward")   ; OS-layer-specific: effect leaves the device

(def VERB-SAFETY
  {"list" SAFETY-READ, "get" SAFETY-READ, "read" SAFETY-READ, "find" SAFETY-READ,
   "search" SAFETY-READ, "show" SAFETY-READ, "export" SAFETY-READ,
   "create" SAFETY-CREATE, "add" SAFETY-CREATE, "new" SAFETY-CREATE, "save" SAFETY-CREATE,
   "update" SAFETY-UPDATE, "set" SAFETY-UPDATE, "edit" SAFETY-UPDATE,
   "move" SAFETY-UPDATE, "rename" SAFETY-UPDATE, "fill" SAFETY-UPDATE,
   "delete" SAFETY-DELETE, "remove" SAFETY-DELETE, "trash" SAFETY-DELETE,
   "empty" SAFETY-DELETE,
   "send" SAFETY-OUTWARD, "post" SAFETY-OUTWARD, "pay" SAFETY-OUTWARD,
   "purchase" SAFETY-OUTWARD, "share" SAFETY-OUTWARD, "upload" SAFETY-OUTWARD,
   "publish" SAFETY-OUTWARD})

;; Adapter tiers (G2; safest-first).
(def TIER-T1 "t1-scripting-api")
(def TIER-T2 "t2-vision-pointer")
(def TIER-T3 "t3-file-level")

;; Stance gate outcomes (G2).
(def STANCE-OK "ok")
(def STANCE-REFUSED "refused-synthetic-input-prohibited")

;; Mutate gate outcomes (G5). Outward ops carry the extra outward gate.
(def MUTATE-READ-ALLOWED "read-allowed")
(def MUTATE-AWAIT-SIG "awaiting-member-sig")
(def MUTATE-AWAIT-SIG-OUTWARD "awaiting-member-sig-and-outward-gate")

;; Honest degradations / routes (G8 / N7).
(def UNKNOWN-APP "unknown-app")
(def ROUTE-KARAKURI "route-to-karakuri")

;; ═════════════════════════════════════════════════════════════════════════════
;; :representative app capability + stance registry (mirrors
;; data/app-registry.kotoba.edn; G8). Runtime source of truth is the EDN
;; registry; operator MUST verify a stance before live use.
;;
;; Axes:
;;   "t1"     — the app's official automation surface (AppleScript/JXA +
;;              AXUIElement, Windows UI Automation, AT-SPI2/D-Bus, or the app's
;;              own CLI). True → T1 is selected.
;;   "t2"     — the SYNTHETIC-INPUT stance: "permitted" / "restricted" /
;;              "prohibited"; a "prohibited" stance refuses the T2
;;              vision-pointer adapter by construction (G2), EVEN where T2
;;              would technically work. Missing → "prohibited" (default-deny
;;              input injection — safest). ("restricted" treated as
;;              "permitted" at R0 — reserved for a future per-app scope limit.)
;;   "route"  — surface owned by a sibling actor; "karakuri" routes browser
;;              apps to karakuri by construction (N7 — one owner per surface).
;; Anti-cheat games + DRM players are the canonical :prohibited case (the
;; desktop analogue of karakuri's Google/Facebook api-ok/browser-prohibited
;; case).
;; ═════════════════════════════════════════════════════════════════════════════

(def APP-REGISTRY
  {"finder"      {"t1" true,  "t1_surface" "applescript+ax", "t2" "permitted"}
   "mail"        {"t1" true,  "t1_surface" "applescript+ax", "t2" "permitted"}
   "calendar"    {"t1" true,  "t1_surface" "applescript+ax", "t2" "permitted"}
   "excel"       {"t1" true,  "t1_surface" "applescript+uia", "t2" "permitted"}
   "terminal"    {"t1" true,  "t1_surface" "cli",            "t2" "permitted"}
   "keynote"     {"t1" true,  "t1_surface" "applescript",    "t2" "permitted"}
   "legacy-win-app" {"t1" false, "t1_surface" "", "t2" "permitted"}
   "kiosk-tool"     {"t1" false, "t1_surface" "", "t2" "permitted"}
   "anticheat-game" {"t1" false, "t1_surface" "", "t2" "prohibited"}
   "drm-player"     {"t1" false, "t1_surface" "", "t2" "prohibited"}
   "banking-app"    {"t1" false, "t1_surface" "", "t2" "prohibited"}
   "chrome"  {"t1" false, "t1_surface" "", "t2" "prohibited", "route" "karakuri"}
   "safari"  {"t1" false, "t1_surface" "", "t2" "prohibited", "route" "karakuri"}
   "firefox" {"t1" false, "t1_surface" "", "t2" "prohibited", "route" "karakuri"}})

;; ═════════════════════════════════════════════════════════════════════════════
;; Records
;; ═════════════════════════════════════════════════════════════════════════════

;; DesktopOp is a plain map in Clojure, preserving the Python dataclass field
;; names as kebab keywords.

(defn make-desktop-op
  [app noun verb safety destructive adapter-tier & {:keys [args app-known dry-run
                                                            stance-gate mutate-gate
                                                            t2-engine route note]
                                                     :or {args {}
                                                          app-known true
                                                          dry-run true
                                                          stance-gate STANCE-OK
                                                          mutate-gate MUTATE-READ-ALLOWED
                                                          t2-engine ""
                                                          route ""
                                                          note ""}}]
  {:app app
   :noun noun
   :verb verb
   :safety safety
   :destructive destructive
   :adapter-tier adapter-tier
   :args args
   :app-known app-known
   :dry-run dry-run
   :stance-gate stance-gate
   :mutate-gate mutate-gate
   :t2-engine t2-engine
   :route route
   :note note})

;; ═════════════════════════════════════════════════════════════════════════════
;; Public API
;; ═════════════════════════════════════════════════════════════════════════════

(defn classify-safety
  "Map a verb to its op safety. Unknown verbs are treated conservatively as :update (mutating)."
  [verb]
  (get VERB-SAFETY (str/trim (str/lower (or verb ""))) SAFETY-UPDATE))

(defn is-destructive
  "G5: delete is the irreversible class; flagged for explicit member confirmation."
  [safety]
  (= safety SAFETY-DELETE))

(defn resolve-app
  "Look the app up in the :representative registry. nil → honest :unknown-app (G8)."
  [app-id]
  (get APP-REGISTRY (str/trim (str/lower (or app-id "")))))

(defn t2-stance
  "The synthetic-input stance for an app. Missing → 'prohibited' (default-deny; G2)."
  [rec]
  (get rec "t2" "prohibited"))

(defn select-tier
  "Safest-first (G2): scripting/accessibility API > permitted vision-pointer > file-level."
  [rec]
  (cond
    (get rec "t1") TIER-T1
    (#{"permitted" "restricted"} (t2-stance rec)) TIER-T2
    :else TIER-T3))

(defn stance-gate
  "G2: a T2 vision-pointer op on an app whose synthetic-input stance is
  'prohibited' is refused by construction — anti-cheat games, DRM players,
  banking apps."
  [rec tier]
  (if (and (= tier TIER-T2) (= (t2-stance rec) "prohibited"))
    STANCE-REFUSED
    STANCE-OK))

(defn t2-engine
  "The on-device vision engine for a permitted T2 op; '' otherwise (G2/G4)."
  [rec tier gate]
  (if (and (= tier TIER-T2)
           (= gate STANCE-OK)
           (#{"permitted" "restricted"} (t2-stance rec)))
    T2-ENGINE
    ""))

(defn mutate-gate
  "G5: reads allowed at R0; mutations await member-sig; outward ops add the outward gate."
  [safety]
  (cond
    (= safety SAFETY-READ) MUTATE-READ-ALLOWED
    (= safety SAFETY-OUTWARD) MUTATE-AWAIT-SIG-OUTWARD
    :else MUTATE-AWAIT-SIG))

(defn parse-command
  "Parse `[tedai] <app> <noun>.<verb> [--flag value ...]` → [app noun verb args].

  Raises ex-info on a malformed command (G8 — never guesses the shape)."
  [line]
  (let [tokens (str/split (str/trim (or line "")) #"\s+")
        tokens (if (and (seq tokens) (= (str/lower (first tokens)) "tedai"))
                 (rest tokens)
                 tokens)]
    (when (< (count tokens) 2)
      (throw (ex-info (str "malformed command (need '<app> <noun>.<verb>'): " (pr-str line))
                      {:line line})))
    (let [app (first tokens)
          nv (second tokens)]
      (when-not (str/includes? nv ".")
        (throw (ex-info (str "malformed op (need '<noun>.<verb>'): " (pr-str nv))
                        {:line line :nv nv})))
      (let [[noun verb] (str/split nv #"\." 2)]
        (when (or (str/blank? noun) (str/blank? verb))
          (throw (ex-info (str "malformed op (empty noun or verb): " (pr-str nv))
                          {:line line :nv nv})))
        (let [args (loop [j 0
                          rest (drop 2 tokens)
                          acc {}]
                     (if (>= j (count rest))
                       acc
                       (let [tok (nth rest j)]
                         (if (str/starts-with? tok "--")
                           (let [key (subs tok 2)]
                             (if (and (< (inc j) (count rest))
                                      (not (str/starts-with? (nth rest (inc j)) "--")))
                               (recur (+ j 2) rest (assoc acc key (nth rest (inc j))))
                               (recur (inc j) rest (assoc acc key true))))
                           (recur (inc j) rest acc)))))]
          [app (str/lower noun) (str/lower verb) args])))))

(defn plan
  "Parse a command into a dry-run DesktopOp plan with all gates applied (no input injection).

  `prefer-tier` lets a caller request a specific adapter (e.g. force T2) so the
  G2 stance gate can be demonstrated; by default the safest tier is selected."
  [line & {:keys [prefer-tier]}]
  (when (and (some? prefer-tier)
             (not (#{TIER-T1 TIER-T2 TIER-T3} prefer-tier)))
    (throw (ex-info (str "unknown prefer_tier " (pr-str prefer-tier) " (expected one of T1/T2/T3 constants)")
                    {:prefer-tier prefer-tier})))

  (let [[app noun verb args] (parse-command line)
        safety (classify-safety verb)
        rec (resolve-app app)]
    (cond
      (nil? rec)
      ;; G8: unknown app degrades honestly — no tier, no guess.
      (make-desktop-op
       app noun verb safety (is-destructive safety) ""
       :args args :app-known false :stance-gate STANCE-OK
       :mutate-gate (mutate-gate safety) :note UNKNOWN-APP)

      (= (get rec "route") "karakuri")
      ;; N7: the browser surface belongs to karakuri — tedai refuses to re-implement it.
      (make-desktop-op
       app noun verb safety (is-destructive safety) ""
       :args args :app-known true :route "karakuri" :note ROUTE-KARAKURI)

      :else
      (let [tier (or prefer-tier (select-tier rec))
            gate (stance-gate rec tier)
            engine (t2-engine rec tier gate)
            note (if (= gate STANCE-REFUSED)
                   (str "G2: synthetic input prohibited on this app; T2 vision-pointer refused — "
                        "use the scripting API (T1) or T3 file-level")
                   "")]
        (make-desktop-op
         app noun verb safety (is-destructive safety) tier
         :args args :app-known true :dry-run true
         :stance-gate gate :mutate-gate (mutate-gate safety)
         :t2-engine engine :note note)))))
