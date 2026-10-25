(ns kaigi.turn
  "ICE server configuration, including ephemeral TURN credentials.

  ## Why credentials are minted per participant and not configured

  A TURN server needs to authenticate its clients, and the obvious way — put a
  username and password in the Worker's environment and hand the same pair to
  every browser — publishes a permanent relay credential to anyone who opens
  devtools. Whoever finds it can relay arbitrary traffic through the server for
  as long as nobody rotates it, and nothing in the meeting will look wrong.

  So this namespace mints the coturn `use-auth-secret` form instead (the
  de-facto WebRTC standard, `kotoba.turn.credential`):

      username   = \"<expiry-unix-seconds>:<participant-id>\"
      credential = base64(HMAC-SHA1(shared-secret, username))

  The shared secret never leaves the server; each browser receives a credential
  that expires, is bound to one participant id, and is useless to anyone else.
  `org-ietf-turn` verifies exactly this form, so the relay needs no user
  database.

  ## Why TURN's absence is returned as data

  Without a relay, participants behind symmetric NAT or a corporate firewall
  fail to connect — and the failure looks identical to a hung connection.
  `turn-configured?` lets the console say so on screen instead of leaving
  someone watching a spinner. That distinction is the whole reason this returns
  a value rather than logging.

  Pure: `now` and the secret are supplied by the caller. No clock, no I/O."
  (:require [kotoba.lang.text :as str]
            [kotoba.turn.credential :as cred]))

(def default-stun
  "Cloudflare's public STUN. Enough for the majority of networks — which is
  exactly why a missing TURN server is easy to ship and hard to notice."
  {:urls ["stun:stun.cloudflare.com:3478"]})

(def default-ttl-seconds
  "How long a minted TURN credential stays valid.

  Ten minutes: long enough that a participant joining and negotiating never
  races the expiry, short enough that a leaked credential is worthless before
  anyone could use it. It does NOT need to cover the meeting's duration — ICE
  authenticates when the allocation is created, and a long call keeps using the
  allocation it already has."
  600)

(defn turn-configured?
  "True when a relay URL and a shared secret are both present.

  Both halves are required: a URL without a secret cannot be authenticated
  against, and a secret without a URL points nowhere. Treating a half
  configuration as 'TURN present' would make the console claim relay coverage
  it does not have."
  [{:keys [turn-url turn-secret]}]
  (boolean (and (string? turn-url) (seq turn-url)
                (string? turn-secret) (seq turn-secret))))

(defn ice-servers
  "The ICE server list to hand `participant-id`'s browser.

  Always includes STUN. Adds the TURN entry — with a freshly minted, expiring,
  participant-bound credential — only when both halves are configured.

  `now` is unix seconds."
  [{:keys [turn-url turn-secret ttl-seconds] :as config} participant-id now]
  (let [stun [default-stun]]
    (if-not (turn-configured? config)
      stun
      (let [{:keys [username credential]}
            (cred/mint-credential turn-secret
                                  (str participant-id)
                                  (or ttl-seconds default-ttl-seconds)
                                  now)]
        (conj stun {:urls [turn-url]
                    :username username
                    :credential credential})))))

(defn relay-available?
  "Whether an ICE server list (as sent to a client) contains a relay.

  Reads the list rather than the config because this is the question the UI
  has: the console is handed servers, not configuration. `kaigi.ui/ice-notice`
  uses it to decide whether to warn."
  [servers]
  (boolean (some (fn [s] (some #(str/starts-with? (str %) "turn") (:urls s)))
                 servers)))

(defn config-from-env
  "Read TURN configuration out of a Worker `env`-shaped lookup.

  Takes a `get` function rather than the env object so this stays `.cljc` and
  testable: the Worker passes `#(aget env %)`.

  `TURN_USERNAME` / `TURN_CREDENTIAL` are deliberately NOT read. Supporting
  static credentials alongside minted ones would mean the safe path and the
  leaky path are one config change apart, and the leaky one is the easier thing
  to paste in."
  [get-env]
  {:turn-url    (some-> (get-env "TURN_URL") str)
   :turn-secret (some-> (get-env "TURN_SECRET") str)})
