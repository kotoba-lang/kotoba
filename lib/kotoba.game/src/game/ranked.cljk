(ns game.ranked
  "Ranked system: ELO/MMR for KAMI Battle Royale.

  Restored from kami-game's `ranked.rs` (kotoba-lang/kami-engine, Rust workspace
  deleted in PR #82; recoverable at commit a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa)
  as zero-dependency portable CLJC per ADR-2607010930.

  Placement-based scoring (kills + placement) with seasonal ranks:
  Bronze -> Silver -> Gold -> Platinum -> Diamond -> Champion -> Unreal.
  Ported 1:1 as pure data + pure functions; mutating `&mut self` Rust methods
  become functions that return updated state maps.")

;; ── Rank Tiers ──────────────────────────────────────────────────────────

(def rank-tier-order
  "Ordinal ordering of rank tiers, lowest to highest (mirrors Rust's derived Ord)."
  [:bronze :silver :gold :platinum :diamond :champion :unreal])

(def rank-tier-rank
  "Map from tier keyword to its ordinal index, for `tier>`/`tier<` comparisons."
  (into {} (map-indexed (fn [i t] [t i]) rank-tier-order)))

(defn tier-compare
  "Compare two rank tiers by ordinal position. Returns neg/0/pos like `compare`."
  [a b]
  (compare (rank-tier-rank a) (rank-tier-rank b)))

(defn tier>
  [a b]
  (pos? (tier-compare a b)))

(defn tier<
  [a b]
  (neg? (tier-compare a b)))

(defn rank-tier-from-mmr
  "Determine rank tier from raw MMR value."
  [mmr]
  (cond
    (<= mmr 499) :bronze
    (<= mmr 999) :silver
    (<= mmr 1499) :gold
    (<= mmr 1999) :platinum
    (<= mmr 2999) :diamond
    (<= mmr 4999) :champion
    :else :unreal))

(def rank-tier-display-name
  {:bronze "Bronze"
   :silver "Silver"
   :gold "Gold"
   :platinum "Platinum"
   :diamond "Diamond"
   :champion "Champion"
   :unreal "Unreal"})

(defn rank-tier-division-count
  [tier]
  (case tier
    (:bronze :silver :gold :platinum :diamond) 3
    (:champion :unreal) 1))

;; ── Rank Division ───────────────────────────────────────────────────────

(defn rank-division-from-mmr
  "Determine {:tier :division} from raw MMR. division is 1-3 (III,II,I),
  0 for Champion/Unreal."
  [mmr]
  (let [tier (rank-tier-from-mmr mmr)
        division (case tier
                   :bronze (cond (<= mmr 166) 3 (<= mmr 333) 2 :else 1)
                   :silver (cond (<= mmr 666) 3 (<= mmr 833) 2 :else 1)
                   :gold (cond (<= mmr 1166) 3 (<= mmr 1333) 2 :else 1)
                   :platinum (cond (<= mmr 1666) 3 (<= mmr 1833) 2 :else 1)
                   :diamond (cond (<= mmr 2333) 3 (<= mmr 2666) 2 :else 1)
                   (:champion :unreal) 0)]
    {:tier tier :division division}))

(defn rank-division-display
  "Human-readable display string, e.g. \"Bronze III\" or \"Champion\"."
  [{:keys [tier division]}]
  (if (zero? division)
    (rank-tier-display-name tier)
    (let [div-str (case division 3 "III" 2 "II" 1 "I" "")]
      (str (rank-tier-display-name tier) " " div-str))))

(defn rank-division>
  "True if division `a` outranks division `b` (higher tier, or same tier +
  lower division number, since division I > II > III)."
  [a b]
  (or (tier> (:tier a) (:tier b))
      (and (= (:tier a) (:tier b)) (< (:division a) (:division b)))))

(defn rank-division<
  [a b]
  (or (tier< (:tier a) (:tier b))
      (and (= (:tier a) (:tier b)) (> (:division a) (:division b)))))

;; ── Player Ranked Profile ───────────────────────────────────────────────

(defn new-ranked-profile
  "Construct a fresh ranked profile for a player entering a season."
  [player-did display-name season]
  {:player-did player-did
   :display-name display-name
   :mmr 0
   :peak-mmr 0
   :rank (rank-division-from-mmr 0)
   :season season
   :matches-played 0
   :wins 0
   :top5 0
   :top10 0
   :top25 0
   :total-kills 0
   :total-damage 0
   :total-builds 0
   :avg-placement 0.0
   :kd-ratio 0.0
   :win-rate 0.0
   :current-streak 0
   :best-streak 0
   :demotion-shield false})

(defn update-rank
  "Recompute :rank from :mmr and bump :peak-mmr if a new peak was reached."
  [profile]
  (let [profile (assoc profile :rank (rank-division-from-mmr (:mmr profile)))]
    (if (> (:mmr profile) (:peak-mmr profile))
      (assoc profile :peak-mmr (:mmr profile))
      profile)))

;; ── Match Scoring ────────────────────────────────────────────────────────

(defn placement-points
  "Points awarded by placement (100-player lobby)."
  [placement _total-players]
  (cond
    (= placement 1) 120
    (= placement 2) 85
    (= placement 3) 70
    (= placement 4) 60
    (= placement 5) 55
    (<= 6 placement 10) 40
    (<= 11 placement 15) 25
    (<= 16 placement 20) 15
    (<= 21 placement 25) 10
    (<= 26 placement 30) 5
    (<= 31 placement 40) 2
    (<= 41 placement 50) 0
    :else (- (- 10) (min 20 (quot (- placement 50) 10))))) ; bus fee: -10 - min((p-50)/10, 20)

(defn kill-points
  "Points per elimination, scaled by current rank tier."
  [kills current-rank]
  (let [base (case current-rank
               (:bronze :silver) 20
               (:gold :platinum) 18
               :diamond 15
               :champion 12
               :unreal 10)]
    (* kills base)))

(defn entry-fee
  "Entry fee (bus fee) — higher ranks pay more (negative points)."
  [rank]
  (case rank
    :bronze 0
    :silver -10
    :gold -20
    :platinum -30
    :diamond -50
    :champion -60
    :unreal -70))

(def tier-floor
  "MMR floor for demotion protection, keyed by tier."
  {:bronze 0
   :silver 480
   :gold 980
   :platinum 1480
   :diamond 1980
   :champion 2980
   :unreal 4980})

(defn calculate-mmr-change
  "Calculate the total MMR change for a match result (pure; profile unmodified)."
  [profile result]
  (let [old-rank (:rank profile)
        old-tier (:tier old-rank)
        bus-fee (entry-fee old-tier)
        placement-pts (placement-points (:placement result) (:total-players result))
        kill-pts (kill-points (:kills result) old-tier)
        damage-bonus (quot (:damage-dealt result) 500)
        assist-bonus (* (:assists result) 5)
        bonus (+ damage-bonus assist-bonus)
        total (+ bus-fee placement-pts kill-pts bonus)
        new-mmr-raw (+ (:mmr profile) total)
        floor (tier-floor old-tier)
        new-mmr (if (and (:demotion-shield profile) (< new-mmr-raw floor))
                  floor
                  (max new-mmr-raw 0))
        new-rank (rank-division-from-mmr new-mmr)
        promoted (or (tier> (:tier new-rank) old-tier)
                     (and (= (:tier new-rank) old-tier)
                          (< (:division new-rank) (:division old-rank))))
        demoted (or (tier< (:tier new-rank) old-tier)
                    (and (= (:tier new-rank) old-tier)
                         (> (:division new-rank) (:division old-rank))))]
    {:placement-points placement-pts
     :kill-points kill-pts
     :bus-fee bus-fee
     :bonus bonus
     :total total
     :new-mmr new-mmr
     :old-rank old-rank
     :new-rank new-rank
     :promoted promoted
     :demoted demoted}))

(defn apply-match-result
  "Apply match result to player profile, returning [updated-profile mmr-change]."
  [profile result]
  (let [change (calculate-mmr-change profile result)
        placement (:placement result)
        profile (-> profile
                    (assoc :mmr (:new-mmr change))
                    (update :matches-played inc)
                    (update :total-kills + (:kills result))
                    (update :total-damage + (:damage-dealt result))
                    (update :total-builds + (:builds-placed result)))
        profile (cond-> profile
                  (= placement 1) (update :wins inc)
                  (<= placement 5) (update :top5 inc)
                  (<= placement 10) (update :top10 inc)
                  (<= placement 25) (update :top25 inc))
        n (double (:matches-played profile))
        profile (assoc profile :avg-placement
                       (/ (+ (* (:avg-placement profile) (- n 1.0)) (double placement)) n))
        deaths (- (:matches-played profile) (:wins profile))
        profile (assoc profile :kd-ratio
                       (if (pos? deaths)
                         (/ (double (:total-kills profile)) (double deaths))
                         (double (:total-kills profile))))
        profile (assoc profile :win-rate
                        (* (/ (double (:wins profile)) (double (:matches-played profile))) 100.0))
        profile (cond
                  (= placement 1)
                  (update profile :current-streak
                          (fn [s] (if (>= s 0) (inc s) 1)))
                  (> placement 50)
                  (update profile :current-streak
                          (fn [s] (if (<= s 0) (dec s) -1)))
                  :else profile)
        profile (if (pos? (:current-streak profile))
                  (update profile :best-streak max (:current-streak profile))
                  profile)
        profile (assoc profile :demotion-shield (:promoted change))
        profile (update-rank profile)]
    [profile change]))

;; ── Matchmaking ──────────────────────────────────────────────────────────

(defn matchmake
  "Group players into lobbies by MMR proximity. `queue` is a vector of
  {:player-did :mmr :rank :queue-time} maps. Returns a vector of vectors of
  indices into `queue`."
  [queue target-size max-mmr-spread]
  (if (empty? queue)
    []
    (let [sorted-indices (sort-by #(:mmr (nth queue %)) (range (count queue)))]
      (loop [indices sorted-indices
             lobbies []
             current-lobby []
             lobby-min-mmr (:mmr (nth queue (first sorted-indices)))]
        (if (empty? indices)
          (if (and (seq current-lobby) (>= (count current-lobby) (quot target-size 2)))
            (conj lobbies current-lobby)
            lobbies)
          (let [idx (first indices)
                entry (nth queue idx)
                spread (if (> (:queue-time entry) 60.0)
                         (* max-mmr-spread 2)
                         max-mmr-spread)]
            ;; When the entry doesn't fit `spread` (or the lobby is already
            ;; full), close the current lobby and start a new one with this
            ;; entry -- regardless of whether current-lobby has reached the
            ;; target-size/2 floor. Force-adding an out-of-spread entry just
            ;; to avoid an under-sized lobby (the old :else branch) violated
            ;; max-mmr-spread outright -- e.g. mixing MMR-0 and MMR-5000
            ;; players into one lobby because the lobby only had 4 members.
            ;; An under-sized-but-in-spread lobby is already an accepted
            ;; outcome of this algorithm (the end-of-queue tail below drops
            ;; the FINAL lobby if it's under target-size/2, but every
            ;; mid-stream close here has always been unconditional on size).
            (if (and (<= (- (:mmr entry) lobby-min-mmr) spread)
                     (< (count current-lobby) target-size))
              (recur (rest indices) lobbies (conj current-lobby idx) lobby-min-mmr)
              (recur (rest indices)
                     (conj lobbies current-lobby)
                     [idx]
                     (:mmr entry)))))))))

;; ── Season ───────────────────────────────────────────────────────────────

(defn soft-reset-mmr
  "Apply a season's soft-reset ratio to an old MMR value, e.g. ratio 0.5 halves it."
  [season old-mmr]
  (int (* (double old-mmr) (double (:soft-reset-ratio season)))))

;; ── Ranked Leaderboard ───────────────────────────────────────────────────
;; LeaderboardEntry is a plain map:
;; {:rank-position :player-did :display-name :mmr :rank :wins :kills
;;  :kd-ratio :matches-played}
