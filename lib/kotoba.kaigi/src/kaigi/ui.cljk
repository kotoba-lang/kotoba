(ns kaigi.ui
  "The meeting console as pure `.cljc` hiccup.

  Takes plain data — a `kaigi.model` meeting value and the local participant's
  id — and returns hiccup. Nothing here touches the DOM, a clock, or
  `getUserMedia`, so the same fn renders server-side via `kotoba-ui.core/->page`
  and in the browser from `kaigi.app`, which re-invokes it with each new roster
  and swaps the result in. That is the dual-render contract, and it is why the
  markup is not written twice (once as hiccup and once as JS template strings,
  which then drift).

  ## Video elements are deliberately NOT rendered here

  `participant-tile` emits an empty container carrying
  `data-kaigi-participant`. `kaigi.app` creates one `<video>` per participant
  and moves it into that container, and never re-creates it.

  This split is not incidental. A `<video>` whose element is replaced loses its
  `srcObject` and restarts playback — so a roster update as small as someone
  toggling their microphone would make everyone's video flicker. Keeping media
  elements out of the re-rendered tree makes that impossible rather than
  merely avoided.

  ## Design system

  `kotoba-ui.core` + `appkit.core` only (agent-guide rule 1). No raw hex, no
  px font-size, no font-family (rule 2) — every value is a `--hig-*` token or
  an HIG text style. Layout from `kotoba-ui.shell` (rule 4). Interaction is
  expressed as `data-act` values that `kaigi.app` dispatches on, so no
  handlers are baked into the hiccup and the SSR and browser output are
  identical for identical data."
  (:require [kotoba.lang.text :as str]
            [kaigi.invite :as invite]
            [kaigi.model :as m]
            [kaigi.plan :as plan]
            [kotoba-ui.core :as ui]))

(defn- initials
  "Two-letter avatar seed. `subs` rather than `first` so a name whose first
  character is outside the BMP is not cut mid-surrogate-pair and rendered as a
  replacement glyph."
  [s]
  (let [parts (remove str/blank? (str/split (str s) #"\s+"))]
    (->> (take 2 parts)
         (map #(subs % 0 (min 1 (count %))))
         (apply str)
         str/upper)))

(defn- display-name
  [p]
  (let [n (:kaigi.participant/name p)]
    (if (str/blank? (str n)) (str (:kaigi.participant/id p)) (str n))))

(defn- role-badge
  [p]
  (case (:kaigi.participant/role p)
    :host   [:span {:class "hig-caption2 kaigi-badge"} "host"]
    :cohost [:span {:class "hig-caption2 kaigi-badge"} "cohost"]
    nil))

;; ---------------------------------------------------------------------------
;; lobby
;; ---------------------------------------------------------------------------

(defn lobby-queue
  "The host's admission queue. Renders nothing when nobody is waiting — an
  always-present empty panel trains people to ignore the area where the one
  thing that needs their attention will appear."
  [mtg me]
  (let [waiting (sort (m/waiting-ids mtg))]
    (when (and (seq waiting) (m/moderator? mtg me))
      (ui/panel
       (into [[:h3 "入室リクエスト"]]
             (for [id waiting
                   :let [p (m/participant-by-id mtg id)]]
               (ui/stack
                {:direction :horizontal :gap :3 :class "kaigi-queue-row"}
                [:span {:class "hig-body"} (display-name p)]
                (ui/spacer)
                ;; The target is encoded INTO the act value ("admit:rin")
                ;; rather than passed as a data attribute: `button` supports
                ;; only :class/:act/:disabled/:title/:type and silently drops
                ;; anything else, so `:attrs {:data-target id}` rendered a
                ;; button with no target at all — every admit would have
                ;; applied to nobody, with no error. Strings pass through
                ;; `act->str` unchanged, so this needs no upstream change.
                (ui/button "許可" {:act (str "admit:" id)})
                (ui/button "拒否" {:act (str "deny:" id)}))))))))

(defn waiting-notice
  "What a participant sees while they are held at `:requested`.

  Says which of the two situations they are in, because they are not
  interchangeable: waiting for a host is a state that resolves, and being
  denied is not. A single 'cannot join' message for both leaves someone
  staring at a screen that will never change."
  [mtg me]
  (let [admission (m/admission-of mtg me)]
    (when (contains? #{:requested :denied :removed} admission)
      (ui/panel
       [[:h3 (case admission
               :requested "ホストの許可を待っています"
               :denied    "入室を許可されませんでした"
               :removed   "この会議から退出させられました")]
        [:p {:class "hig-callout"}
         (case admission
           :requested "ホストが承認すると自動的に参加します。このままお待ちください。"
           :denied    "ホストに直接ご連絡ください。"
           :removed   "再入室するにはもう一度リクエストしてください。")]]))))

;; ---------------------------------------------------------------------------
;; participants
;; ---------------------------------------------------------------------------

(defn participant-tile
  "One participant. The video element is attached by `kaigi.app`; see the ns
  docstring for why it is not rendered here."
  [mtg me id]
  (let [p        (m/participant-by-id mtg id)
        self?    (= id me)
        muted?   (:kaigi.participant/muted? p)
        cam-off? (:kaigi.participant/camera-off? p)
        sharing? (:kaigi.participant/sharing? p)]
    ;; The data hook and the state class live on a wrapper div, NOT in the
    ;; panel's opts: `panel` -> `shitsuke.components/card` supports only
    ;; `:class` (a STRING) and `:id`, and silently drops anything else. Passing
    ;; `:attrs {:data-kaigi-tile id}` produced markup that looked right and had
    ;; no data attributes at all, so the browser found zero tiles to attach
    ;; video to — a failure with no error anywhere.
    [:div {:class (str "kaigi-tile" (when sharing? " kaigi-tile--sharing"))
           :data-kaigi-tile id}
     (ui/panel
      [[:div {:class "kaigi-tile__media" :data-kaigi-participant id}
       ;; Shown when there is no video to show. The avatar is the fallback,
       ;; not an overlay: a black rectangle is indistinguishable from a
       ;; broken connection.
       (when cam-off?
         [:div {:class "kaigi-tile__avatar" :aria-hidden "true"}
          (initials (display-name p))])]
      ;; sibling of the media container, not a child of it
      (ui/stack
       {:direction :horizontal :gap :2 :class "kaigi-tile__bar"}
       [:span {:class "hig-subheadline"} (display-name p)]
       (when self? [:span {:class "hig-caption2 kaigi-badge"} "あなた"])
       (role-badge p)
       (ui/spacer)
       (when muted? [:span {:class "hig-caption1" :aria-label "ミュート中"} "🔇"])
       (when sharing? [:span {:class "hig-caption1" :aria-label "画面共有中"} "🖥"])
       (when (and (m/moderator? mtg me) (not self?))
         (ui/icon-button "⋯" {:act (str "remove:" id)})))])]))

(defn participant-grid
  [mtg me]
  (let [ids (sort (m/admitted-ids mtg))]
    (if (seq ids)
      (apply ui/grid {:class "kaigi-grid"}
             (map #(participant-tile mtg me %) ids))
      (ui/panel [[:p {:class "hig-callout"} "まだ誰も参加していません。"]]))))

;; ---------------------------------------------------------------------------
;; controls
;; ---------------------------------------------------------------------------

(defn controls
  [mtg me]
  (let [p        (m/participant-by-id mtg me)
        muted?   (:kaigi.participant/muted? p)
        cam-off? (:kaigi.participant/camera-off? p)
        sharing? (= me (m/sharing-id mtg))]
    (ui/toolbar
     ;; No `aria-pressed`: `button` has no way to carry an arbitrary
     ;; attribute, and hand-rolling a `<button>` to add one is the failure the
     ;; agent-guide names explicitly. The label already states the current
     ;; state ("ミュート" vs "ミュート解除"), so the control is not ambiguous to a
     ;; screen reader — but a toggle SHOULD expose pressed state, and that is
     ;; an upstream gap recorded in the README rather than worked around here.
     [(ui/button (if muted? "ミュート解除" "ミュート") {:act :toggle-mute})
      (ui/button (if cam-off? "カメラをオン" "カメラをオフ") {:act :toggle-camera})
      (ui/button (if sharing? "共有を停止" "画面を共有") {:act :toggle-share})
      (ui/spacer)
      (when (m/moderator? mtg me)
        (ui/button "会議を終了" {:act :end}))]
     {:class "kaigi-controls"})))

;; ---------------------------------------------------------------------------
;; recording
;; ---------------------------------------------------------------------------

(defn recording-panel
  "Recording state and the consent it requires.

  When consent is not unanimous the panel NAMES who has not consented rather
  than showing a disabled button. A control that is greyed out with no reason
  is read as a bug; the missing names are the only actionable information
  here."
  [mtg me]
  (let [state    (get-in mtg [:kaigi/recording :kaigi.recording/state])
        missing  (sort (m/missing-recording-consents mtg))
        consented? (contains? (get-in mtg [:kaigi/recording :kaigi.recording/consents]) me)]
    (ui/panel
     (cond
       (= :on state)
       [[:h3 "録画中"]
        [:p {:class "hig-callout"} "全員の同意が得られています。同意はいつでも撤回できます。"]
        (ui/stack {:direction :horizontal :gap :3}
                  (ui/button "同意を撤回" {:act :revoke-consent})
                  (when (m/moderator? mtg me)
                    (ui/button "録画を停止" {:act :stop-recording})))]

       (= :requested state)
       [[:h3 "録画の同意"]
        (if (seq missing)
          [:p {:class "hig-callout"}
           (str "未同意: " (str/join "、" (map #(display-name (m/participant-by-id mtg %)) missing)))]
          [:p {:class "hig-callout"} "全員が同意しました。"])
        (ui/stack {:direction :horizontal :gap :3}
                  (if consented?
                    (ui/button "同意を撤回" {:act :revoke-consent})
                    (ui/button "録画に同意する" {:act :consent-recording}))
                  (when (and (m/moderator? mtg me) (m/recording-allowed? mtg))
                    (ui/button "録画を開始" {:act :start-recording})))]

       :else
       [[:h3 "録画"]
        [:p {:class "hig-callout"}
         "録画は参加者全員の明示的な同意が必要です。沈黙は同意として扱いません。"]
        (when (m/moderator? mtg me)
          (ui/button "同意を求める" {:act :request-recording}))])
     {:class "kaigi-recording"})))

;; ---------------------------------------------------------------------------
;; status
;; ---------------------------------------------------------------------------

(defn transport-notice
  "Which transport is carrying media, and — when it matters — that the meeting
  has outgrown it.

  The mesh ceiling is surfaced here because a limit the operator only learns
  from server logs is a limit the participants experience as \"the app is
  broken\"."
  [transport warning]
  (when (or (= :mesh transport) warning)
    (ui/panel
     (if warning
       [[:h3 "この人数には mesh は不向きです"]
        [:p {:class "hig-callout"}
         (str "参加者 " (:kaigi.plan/count warning) " 人に対し mesh の目安は "
              (:kaigi.plan/ceiling warning)
              " 人までです。各参加者が全員分を個別に送信するため、"
              "映像が乱れる場合があります。SFU を設定すると解消します。")]]
       [[:p {:class "hig-footnote"}
         "mesh 接続（SFU 未設定）。少人数向けです。"]])
     {:class "kaigi-transport"})))

(defn ice-notice
  "Warn when there is no TURN server, since the failure it produces is
  indistinguishable from a hung connection.

  `ice-servers` is the list the room reported. A list with only STUN entries
  works for most networks and fails silently on symmetric NAT — so the notice
  states the condition instead of leaving a participant watching a spinner."
  [ice-servers]
  (let [turn? (some (fn [s] (some #(str/starts-with? (str %) "turn") (:urls s)))
                    ice-servers)]
    (when-not turn?
      (ui/panel
       [[:p {:class "hig-footnote"}
         "TURN 未設定: 一部のネットワーク（対称 NAT・企業ファイアウォール）では接続できません。"]]
       {:class "kaigi-ice"}))))

;; ---------------------------------------------------------------------------
;; getting in: landing, the invitation, and the pre-join check
;; ---------------------------------------------------------------------------

(def name-field-id "kaigi-name")
(def code-field-id "kaigi-code")

(defn landing
  "What a bare URL shows: start a meeting, or type a code someone read out.

  The bare URL used to join a meeting literally called `lobby`, so everyone
  who opened the site with no query string was dropped into one shared room
  together. Two strangers in the same call is the worst possible default, and
  it happened silently."
  [{:keys [code-error code-input]}]
  (ui/stack
   {:gap :5}
   (ui/hero {:title "kaigi 会議"
             :tagline "リンクを送るだけで会議が始まります。アカウントは要りません。"
             :actions [(ui/button "新しい会議を開始" {:act :new-meeting})]})
   (ui/panel
    [[:h3 "会議コードで参加"]
     (ui/stack
      {:direction :horizontal :gap :3 :class "kaigi-code-row"}
      (ui/text-field {:id code-field-id
                      ;; Re-rendering the landing (to show a refusal) would
                      ;; otherwise clear the code that was just refused, so the
                      ;; error would appear next to an empty field and fixing a
                      ;; typo would mean typing the whole thing again.
                      :value (str code-input)
                      :placeholder "abc-defg-hij"
                      :aria-label "会議コード"
                      :autocomplete "off"
                      :spellcheck "false"})
      (ui/button "参加" {:act :join-code}))
     (if code-error
       ;; `role="alert"` so a screen reader hears the refusal: this message
       ;; appears in place, without focus moving to it, which is silence to
       ;; anyone not looking at that corner of the screen.
       [:p {:class "hig-footnote kaigi-error" :role "alert"} code-error]
       [:p {:class "hig-footnote"}
        "ハイフンは省略できます。大文字・小文字は区別しません。"])])))

(defn invitation
  "The shareable link for this meeting, and one button that copies it.

  Shown inside the meeting rather than only before it: the moment someone
  realises a person is missing is the moment they are already in the call, and
  a link they have to leave to find is a link they send from a different app
  with a typo in it."
  [{:keys [code url copied?]}]
  (when (seq (str url))
    (ui/panel
     [[:h3 "この会議に招待"]
      [:p {:class "hig-body kaigi-invite__url"} (str url)]
      (ui/stack
       {:direction :horizontal :gap :3}
       (ui/button (if copied? "コピーしました" "リンクをコピー") {:act :copy-link})
       (ui/spacer)
       (when (seq (str code))
         [:span {:class "hig-footnote"} (str "会議コード: " code)]))]
     {:class "kaigi-invite"})))

(defn prejoin
  "The check before joining: how you will look and what you will be called.

  This screen is why the roster stopped reading `u-a1b2c3`. A name was always
  accepted by `hello` — nothing ever asked for one, so the client sent the
  random per-tab id as the display name and every participant appeared as a
  string of hex.

  The camera preview shares `data-kaigi-participant` with the meeting tiles,
  so `kaigi.app` moves the same `<video>` element from here into the grid
  rather than creating a second one — the preview and the call are the same
  stream, and the transition costs no renegotiation."
  [{:keys [me display-name code url copied? media-refused?]}]
  (ui/stack
   {:gap :4}
   (ui/panel
    [[:h3 "参加の準備"]
     [:div {:class "kaigi-tile__media kaigi-preview" :data-kaigi-participant (str me)}
      (when media-refused?
        [:div {:class "kaigi-tile__avatar" :aria-hidden "true"} "🎥"])]
     (when media-refused?
       [:p {:class "hig-footnote"}
        "カメラとマイクを使えません。音声・映像なしでも参加できます。"])
     (ui/text-field {:id name-field-id
                     :value (str display-name)
                     :placeholder "名前"
                     :aria-label "表示名"
                     :autocomplete "name"})
     (ui/button "今すぐ参加" {:act :join})])
   (invitation {:code code :url url :copied? copied?})))

;; ---------------------------------------------------------------------------
;; page
;; ---------------------------------------------------------------------------

(def theme
  "The one place a hex color is legitimate in app code (agent-guide rule 5)."
  {:accent "#2D7FF9" :appearance :auto})

(def console-root-id
  "The element both renderers own. The browser replaces exactly this element
  with the output of `console`, so `console` must render this element and
  nothing outside it — an earlier version returned the whole `app-shell` while
  the browser swapped only the inner stack, which nested a second shell (and a
  second nav bar) inside the first on the very first live render."
  "kaigi-console")

(defn in-meeting
  "One participant's view of one meeting."
  [{:keys [meeting me transport ice-servers warning] :as opts}]
  (let [mtg meeting]
    (ui/stack
     {:gap :4}
     (waiting-notice mtg me)
     (lobby-queue mtg me)
     (transport-notice transport warning)
     (ice-notice ice-servers)
     (when (m/admitted? mtg me)
       (ui/stack {:gap :4}
                 (participant-grid mtg me)
                 (controls mtg me)
                 (recording-panel mtg me)
                 (invitation opts))))))

(defn console
  "The re-rendered region, whichever of the three screens it is showing.

  Returns the `#kaigi-console` element itself. `render-page` wraps it in the
  page shell for SSR; the browser swaps this element in place.

  One swap target for all three views rather than three: `kaigi.app` replaces
  this element's `outerHTML` wholesale, and a second target would mean a
  second place that has to be kept in sync with which view is current — which
  is how you get two screens rendered at once.

  `:view` defaults to `:meeting` so every existing caller — the tests and
  anything that passes only a meeting — keeps its old behaviour."
  [{:keys [view] :as opts}]
  (ui/stack
   {:gap :4 :id console-root-id}
   (case (or view :meeting)
     :landing (landing opts)
     :prejoin (prejoin opts)
     :loading (ui/panel [[:p {:class "hig-callout"} "接続しています…"]])
     (in-meeting opts))))

(defn page-shell
  "The static frame around `console`: nav and app chrome.

  Rendered once, server-side. The recording indicator lives in
  `recording-panel` rather than up here precisely because this frame is not
  re-rendered."
  [opts]
  (ui/app-shell
   ;; `:trailing` takes hiccup directly, NOT a vector of hiccup: wrapping a
   ;; `when` in a vector yields `[nil]`, whose first element is then parsed as
   ;; the tag name and throws.
   {:nav (ui/nav-bar (or (:kaigi/title (:meeting opts)) "会議") nil)}
   (console opts)))

(def app-css
  "Unlayered app CSS: it always wins over the library's `@layer` rules, so no
  compound selectors are needed (agent-guide rule 3). Only the things the
  design system has no opinion about — the aspect ratio of a video tile and
  how a stream fills it."
  (str
   ".kaigi-tile__media{position:relative;aspect-ratio:16/9;overflow:hidden;"
   "border-radius:var(--hig-radius-medium);background:var(--hig-fill-tertiary);}"
   ".kaigi-tile__media video{width:100%;height:100%;object-fit:cover;display:block;}"
   ".kaigi-tile__avatar{position:absolute;inset:0;display:flex;align-items:center;"
   "justify-content:center;font:var(--hig-text-title1);color:var(--hig-label-secondary);}"
   ".kaigi-tile--sharing .kaigi-tile__media{outline:var(--hig-hairline) solid var(--hig-palette-blue);}"
   ".kaigi-badge{padding:0 var(--hig-spacing-1);border-radius:var(--hig-radius-small);"
   "background:var(--hig-fill-secondary);color:var(--hig-label-secondary);}"
   ".kaigi-queue-row{align-items:center;}"
   ;; The pre-join preview is the same tile geometry as a grid tile, capped so
   ;; it does not fill a desktop viewport — it is a mirror to check yourself
   ;; in, not the meeting.
   ".kaigi-preview{max-width:32rem;margin-inline:auto;}"
   ;; A URL is one unbroken token, so it overflows every container it is put
   ;; in unless told otherwise. `anywhere` rather than `break-all` so it still
   ;; prefers to break at the slashes.
   ".kaigi-invite__url{overflow-wrap:anywhere;color:var(--hig-label-secondary);}"
   ".kaigi-code-row{align-items:center;}"
   ".kaigi-code-row>*:first-child{flex:1 1 auto;}"
   ".kaigi-error{color:var(--hig-palette-red);}"))

(defn render-page
  "The complete SSR document. `opts` as `console`."
  [opts]
  (ui/->page {:title (str (or (:kaigi/title (:meeting opts)) "会議") " — kaigi")
              :description "会議 — online meeting"
              :lang "ja"
              :theme theme
              ;; An inline data-URI icon rather than a /favicon.ico file: the
              ;; browser requests a favicon unconditionally, and without one
              ;; every page load logs a console 404. Real errors are then one
              ;; line down from permanent noise, which is how real errors get
              ;; ignored. A data URI makes the request disappear entirely
              ;; rather than answering it.
              :head [[:style app-css]
                     [:link {:rel "icon"
                             :href (str "data:image/svg+xml,"
                                        "%3Csvg xmlns='http://www.w3.org/2000/svg' "
                                        "viewBox='0 0 16 16'%3E%3Crect width='16' height='16' "
                                        "rx='4' fill='%232D7FF9'/%3E%3Ccircle cx='8' cy='6' r='2.4' "
                                        "fill='white'/%3E%3Cpath d='M3 14c0-2.8 2.2-4.4 5-4.4"
                                        "s5 1.6 5 4.4z' fill='white'/%3E%3C/svg%3E")}]]}
             (page-shell opts)))
