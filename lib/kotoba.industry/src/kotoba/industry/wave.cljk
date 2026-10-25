(ns kotoba.industry.wave
  "Reverse-topological rollout waves over ISIC Rev.4 (ADR-2607121000).

  Edge definition: u -> v means \"operating division v consumes
  division u's output as a required operating input\". A reverse
  topological sort of that dependency DAG orders divisions from the
  most-depended-upon roots (settlement/finance, information, then
  governance/energy) outward to the consumer-facing leaves (health,
  education, personal services). Every wave N+1 transaction settles,
  communicates and complies through wave N, so value capture is
  on-order only when lower-numbered waves become agent-operable
  first. The wave number is therefore a rollout priority, not a
  quality tier: it composes with (not replaces) the :spec ->
  :blueprint -> :implemented maturity ladder.

  Pure data + fns (.cljc, no registry IO): codes come in as strings
  (section letter, 2-digit division, 3-digit group or 4-digit class).
  `kotoba.industry/execution-plan`, `maturity-roadmap` and
  `wave-maturity-summary` attach :wave from here."
  (:require [kotoba.lang.text :as str]))

(def waves
  "Wave metadata, ordered by reverse-topological depth (root first)."
  {0 {:wave/name "settlement-information-root"
      :wave/title-ja "貨幣・情報の根"
      :wave/sections "J(61-63) K(64-66)"
      :wave/thesis (str "Money, settlement, risk transfer and communication are "
                        "required operating inputs of all 21 ISIC sections "
                        "(maximal transitive fan-out). kotoba-lang/treasury + the "
                        "murakumo lattice are the substitute implementation, so "
                        "this wave is substrate-native, LLM-automatable now, and "
                        "already holds the fleet's only compiled-wasm actors "
                        "(6492 credit, 6511 insurance).")
      :wave/substrate [:kotoba-lang/treasury :murakumo :kotobase :itonami.cloud]}
   1 {:wave/name "governance-energy"
      :wave/title-ja "統治・専門職・エネルギー"
      :wave/sections "M(69-74) O(84) U(99) D(35) E36 B06/09 C19"
      :wave/thesis (str "Incorporation, accounting, compliance, public-interface "
                        "and energy gate every cross-border expansion of waves "
                        "2-4. The iso3166 x 223-country compliance fleet plus the "
                        "6910 global-incorporation actor and 8291 compliance "
                        "intelligence form the market-entry gateway moat.")
      :wave/substrate [:cloud-itonami-iso3166-fleet :isic-6910 :isic-8291]}
   2 {:wave/name "coordination"
      :wave/title-ja "流通・調整・労働市場"
      :wave/sections "G(45-47) H(49-53) L(68) N78/80/81/82"
      :wave/thesis (str "Trade, logistics, real estate and the labour market "
                        "(7810 bridges to all 436 ISCO-08 unit groups) are the "
                        "coordination layer every production and consumer wave "
                        "moves through; agent orchestration is the wedge, "
                        "robotics optional.")
      :wave/substrate [:isic-7810 :kotoba-lang/occupation]}
   3 {:wave/name "production-robotics"
      :wave/title-ja "生産・建設 (robotics)"
      :wave/sections "A(01-03) B05/07/08 C(10-33 ex.19) E(37-39) F(41-43)"
      :wave/thesis (str "Physical production consumes waves 0-2 as operating "
                        "inputs and is robotics-gated (ADR-2607011000 Governor + "
                        "human sign-off), so it lands after the coordination "
                        "layers are agent-native.")
      :wave/substrate [:robotics-premise-adr-2607011000]}
   4 {:wave/name "human-services"
      :wave/title-ja "対人サービス"
      :wave/sections "I(55-56) P(85) Q(86-88) R(90-93) S(94-96) T(97-98) J58-60 M75 N77/79"
      :wave/thesis (str "Deepest dependency chains and the highest trust/"
                        "regulatory sensitivity; last in reverse-topological "
                        "order but the largest long-run TAM (health/aged care "
                        "with the Japan demographic wedge).")
      :wave/substrate [:isic-86-88-fleet]}})

(def section-wave
  "ISIC Rev.4 section letter -> wave (coarse default; divisions refine)."
  {"A" 3 "B" 3 "C" 3 "D" 1 "E" 3 "F" 3 "G" 2 "H" 2 "I" 4 "J" 0 "K" 0
   "L" 2 "M" 1 "N" 2 "O" 1 "P" 4 "Q" 4 "R" 4 "S" 4 "T" 4 "U" 1})

(def division-wave
  "ISIC Rev.4 division (first 2 digits) -> wave. Total over all 88
  Rev.4 divisions; `kotoba.industry-test` asserts totality over the
  live registry. Deviations from the section default are the point:
  06/09 (oil & gas) + 19 (refining) + 35/36 (power/water) belong to
  the energy root (wave 1) even though B/C/E default to production;
  75 (veterinary) + 77/79 (rental/travel) are consumer-facing leaves
  even though M/N default to governance/coordination."
  {"01" 3 "02" 3 "03" 3
   "05" 3 "06" 1 "07" 3 "08" 3 "09" 1
   "10" 3 "11" 3 "12" 3 "13" 3 "14" 3 "15" 3 "16" 3 "17" 3 "18" 3
   "19" 1 "20" 3 "21" 3 "22" 3 "23" 3 "24" 3 "25" 3 "26" 3 "27" 3
   "28" 3 "29" 3 "30" 3 "31" 3 "32" 3 "33" 3
   "35" 1 "36" 1 "37" 3 "38" 3 "39" 3
   "41" 3 "42" 3 "43" 3
   "45" 2 "46" 2 "47" 2
   "49" 2 "50" 2 "51" 2 "52" 2 "53" 2
   "55" 4 "56" 4
   "58" 4 "59" 4 "60" 4 "61" 0 "62" 0 "63" 0
   "64" 0 "65" 0 "66" 0
   "68" 2
   "69" 1 "70" 1 "71" 1 "72" 1 "73" 1 "74" 1 "75" 4
   "77" 4 "78" 2 "79" 4 "80" 2 "81" 2 "82" 2
   "84" 1
   "85" 4
   "86" 4 "87" 4 "88" 4
   "90" 4 "91" 4 "92" 4 "93" 4
   "94" 4 "95" 4 "96" 4
   "97" 4 "98" 4
   "99" 1})

(def code-overrides
  "Class-level exceptions to their division's wave: 5820 software
  publishing is substrate-adjacent (division 58 is otherwise media,
  wave 4); 8291 compliance intelligence is a governance root
  (division 82 is otherwise office support, wave 2)."
  {"5820" 0
   "8291" 1})

(defn wave-of
  "Wave number (0-4) for an ISIC code: section letter, 2-digit
  division, 3-digit group or 4-digit class. nil for unknown codes."
  [isic]
  (let [s (str/upper (str isic))]
    (or (get code-overrides s)
        (get section-wave s)
        (when (>= (count s) 2)
          (get division-wave (subs s 0 2))))))

(defn wave-info
  "Full wave metadata map for an ISIC code, with :wave assoc'd.
  nil for unknown codes."
  [isic]
  (when-let [w (wave-of isic)]
    (assoc (get waves w) :wave w)))
