(ns kotoba.occupation.wave
  "Reverse-topological rollout waves over ISCO-08 (ADR-2607121000).

  Occupation counterpart of `kotoba.industry.wave`: the edge u -> v
  means \"occupation v's work depends on occupation u's work product\".
  The occupations that build and operate the substrate (ICT, finance,
  legal, clerical -- the LLM-first cognitive wave) are the roots every
  later occupation's agent-substitution depends on; physical trades
  ride the robotics wave; care/teaching/personal service are the
  trust-gated leaves. Wave numbers align 1:1 with the ISIC waves so a
  `cloud-itonami-isco-{code}` blueprint and its industry vertical
  advance together.

  Pure data + fns (.cljc, no registry IO): unit-group codes come in
  as 4-digit strings; sub-major = first 2 digits, minor = first 3.
  `kotoba.occupation/execution-plan`, `maturity-roadmap` and
  `wave-maturity-summary` attach :wave from here.")

(def waves
  "Wave metadata, ordered by reverse-topological depth (root first)."
  {0 {:wave/name "cognitive-substrate-root"
      :wave/title-ja "認知基盤の根 (LLM 第一波)"
      :wave/thesis (str "ICT professionals build the substrate every other "
                        "occupation's automation depends on; finance/admin "
                        "professionals, legal professionals and clerical work "
                        "are the purely-cognitive occupations LLM agents "
                        "substitute first.")
      :wave/sub-majors ["24" "25" "35" "41" "42" "43" "44"]}
   1 {:wave/name "design-governance"
      :wave/title-ja "設計・統制"
      :wave/thesis (str "Executives, managers, engineers and technicians "
                        "produce the designs and control structures that "
                        "coordination and production occupations execute.")
      :wave/sub-majors ["01" "02" "03" "11" "12" "13" "21" "31"]}
   2 {:wave/name "coordination-logistics"
      :wave/title-ja "調整・物流"
      :wave/thesis (str "Drivers, warehouse/material-recording work, labourers "
                        "and protective services move everything the production "
                        "and consumer waves need; agent orchestration plus "
                        "early robotics.")
      :wave/sub-majors ["33" "54" "83" "93"]}
   3 {:wave/name "physical-production"
      :wave/title-ja "生産技能 (robotics)"
      :wave/thesis (str "Craft trades, plant/machine operators and agricultural "
                        "work are robotics-gated (ADR-2607011000 Governor + "
                        "human sign-off).")
      :wave/sub-majors ["61" "62" "63" "71" "72" "73" "74" "75" "81" "82" "92" "96"]}
   4 {:wave/name "human-trust-services"
      :wave/title-ja "対人・信頼サービス"
      :wave/thesis (str "Health, teaching, care and personal services carry the "
                        "highest trust sensitivity; last in reverse-topological "
                        "order, largest long-run displacement value.")
      :wave/sub-majors ["14" "22" "23" "26" "32" "34" "51" "52" "53" "91" "94" "95"]}})

(def sub-major-wave
  "ISCO-08 sub-major group (first 2 digits of a unit group) -> wave.
  Total over all ISCO-08 sub-majors incl. armed forces (01-03, which
  are registry-only per ADR-2607012000 and slot with governance);
  `kotoba.occupation-test` asserts totality over the live registry."
  {"01" 1 "02" 1 "03" 1
   "11" 1 "12" 1 "13" 1 "14" 4
   "21" 1 "22" 4 "23" 4 "24" 0 "25" 0 "26" 4
   "31" 1 "32" 4 "33" 2 "34" 4 "35" 0
   "41" 0 "42" 0 "43" 0 "44" 0
   "51" 4 "52" 4 "53" 4 "54" 2
   "61" 3 "62" 3 "63" 3
   "71" 3 "72" 3 "73" 3 "74" 3 "75" 3
   "81" 3 "82" 3 "83" 2
   "91" 4 "92" 3 "93" 2 "94" 4 "95" 4 "96" 3})

(def minor-overrides
  "Minor-group exceptions to their sub-major's wave: 261 legal
  professionals are a cognitive root (sub-major 26 is otherwise
  social/cultural, wave 4); 432 material-recording clerks are
  physical warehouse coordination (sub-major 43 is otherwise
  LLM-first clerical, wave 0) -- this keeps the curated 4321 stock-
  clerk blueprint on the same wave as its ISIC logistics vertical."
  {"261" 0
   "432" 2})

(defn wave-of
  "Wave number (0-4) for an ISCO-08 code: 4-digit unit group, 3-digit
  minor or 2-digit sub-major. nil for unknown codes."
  [isco]
  (let [s (str isco)]
    (or (when (>= (count s) 3)
          (get minor-overrides (subs s 0 3)))
        (when (>= (count s) 2)
          (get sub-major-wave (subs s 0 2))))))

(defn wave-info
  "Full wave metadata map for an ISCO-08 code, with :wave assoc'd.
  nil for unknown codes."
  [isco]
  (when-let [w (wave-of isco)]
    (assoc (get waves w) :wave w)))
