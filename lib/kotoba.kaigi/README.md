# kaigi 会議

Online meetings (Zoom / Google Meet 相当) for this workspace: a portable CLJC
**meeting** model, a media-topology planner, a Cloudflare Realtime SFU binding,
and a Durable Object signaling room.

Sibling of the other workspace surfaces — `kotoba-lang/kaisha` (chat),
`calendar` (events), `mail` / `contacts` (correspondence), `slides` (decks).
Like those, the core stays pure data and pure functions; the host renders it,
persists it, and moves the bytes.

> **What this is not.** `kotoba-lang/gijiroku` is the *record* side — it reads
> Zoom / Meet / Teams recording APIs and drafts minutes. `kaigi` is the
> *hosting* side. They are complementary: gijiroku consumes other vendors'
> meetings, kaigi holds our own.

## Status

| Layer | State | Evidence |
|---|---|---|
| `kaigi.model` / `validate` / `plan` / `invite` / `sfu` / `signal` | **implemented** | 97 tests / 336 assertions green on **both** JVM and nbb |
| DO signaling room (`kaigi.worker.*`) | **implemented, deployed** | 22/22 end-to-end checks against a real Worker |
| Invitation flow (landing → code → link → pre-join) | **implemented** | 9/9 browser checks: `e2e-invite.cljs` |
| Cloudflare **RealtimeKit** path | **wired, deployed, exercised against the real service** | 5/5 in production: SDK joined both sides, each saw the other, **a remote video painting frames** |
| Cloudflare Realtime **SFU** path | **implemented, retained, not the chosen path** | kept deliberately; see "Two media planes" |
| Browser console (`kaigi.ui` + `kaigi.app`) | **implemented, deployed** | rendered page scores **100.00 / 0 findings** on the deterministic HIG/WCAG audit |
| Real call (mesh) | **works** | two headless Chromium instances, ICE connected, **~190 KB of inbound RTP measured on each side** |

So: **you can send someone a link and be in a call with them.** That is the
claim `e2e-invite.cljs` exists to hold to, because every other harness here
addresses a meeting whose id it invented and none of them would notice if
there were no way for a person to get one.

### The outage this document previously did not mention

Between the RealtimeKit secrets landing on the live Worker and 2026-08-01, the
deployment **carried no media at all**. `plan/transport` read `:realtimekit`
because the secrets were present; the browser bundle could only drive the mesh
and no-opped on every other plane. The result had a complete roster, working
controls and mute propagating between tabs — and zero PeerConnections, zero
RTP, and nothing in any log naming the cause.

Two things came out of it, and both are in the code rather than in this
paragraph: clients now **declare which planes they can drive** and the room
negotiates across them (`kaigi.plan/negotiate`), and `e2e.cljs` now asserts
that a mesh-only client gets mesh from a RealtimeKit-configured room.

## What it composes rather than reimplements

- `kotoba-lang/webrtc` — `kotoba.webrtc.room` holds participants, published
  tracks and subscriptions; `kotoba.webrtc.session` is the offer/answer
  reducer; `kotoba.webrtc` is ICE/SDP as data.
- `kotoba-lang/org-w3-webrtc-signaling` — `kotoba.rt.core/route-message`
  decides who receives a relayed frame.

`kaigi` adds the layer a *meeting* has and a *room* does not.

## The model

```clojure
(require '[kaigi.model :as k])

(def m
  (-> (k/meeting "m-1" "jun" {:title "週次" :lobby :approval-required})
      (k/start)
      (k/request-admission (k/participant "rin" {:name "Rin"}))))

(k/waiting-ids m)                      ;; => #{"rin"}  — the host's lobby queue
(k/admitted? m "rin")                  ;; => false
(-> m (k/admit "jun" "rin") (k/join "rin") (k/admitted? "rin"))  ;; => true
```

Four invariants are worth stating because they are the ones that are easy to
get wrong and expensive to get wrong:

**Admission is a path, not a boolean.** `:requested -> :admitted | :denied`,
and onward to `:removed`. A removed participant is kept (not deleted) so a
re-join is distinguishable from a first knock — and re-knocking lands at
`:requested` even under an `:open` lobby, because otherwise ejecting someone
accomplishes nothing.

**Recording consent is unanimous and explicit.** `recording-allowed?` is true
only when *every* admitted participant has consented. Silence is not consent, a
majority is not consent, and an empty meeting is not consent. Revoking mid-call
stops an in-progress recording. This is `gijiroku`'s charter rule G3, enforced
here rather than in the host, because the host is the layer under pressure to
skip it. Only an `:asset-ref` is ever stored — never media (G4).

**Screen share is exclusive by construction.** `start-share` clears the
previous sharer in the same update, so no state exists in which two
participants are sharing and the grid has to guess.

**Mute is asymmetric.** A moderator may mute someone; only its owner may
unmute. Opening a live microphone in someone else's room is not a moderation
action.

## Getting in

A meeting is a link and nothing else. `kaigi.invite` owns the two decisions
that makes possible, as pure functions with no I/O:

```clojure
(invite/meeting-code (range 10))            ;; => "abc-defg-hij"
(invite/normalize-code "ABC DEFG HIJ")      ;; => "abc-defg-hij"
(invite/join-url "https://kaigi.example" "abc-defg-hij")
;; => "https://kaigi.example/?meeting=abc-defg-hij"
```

**Ten lowercase letters, grouped 3-4-3.** A code gets read aloud on a phone
call and typed by someone not looking at it, so it is grouped; and it carries
no digits, because the pairs a listener confuses (`0`/`O`, `1`/`l`) are exactly
the ones a spoken code produces. 26^10 ≈ 1.4e14, so guessing one is not a way
in — which is the same bargain Meet makes, and why `:approval-required` still
exists for meetings that want a door as well as a key.

**The randomness is an argument.** `meeting-code` takes the numbers rather
than calling `rand-int`, so the browser can hand it `crypto.getRandomValues`
and the function stays testable. A short read returns nil instead of padding,
because a code with a predictable tail is worse than no code.

Three screens, one swap target (`#kaigi-console`, dispatched by `:view`):

- **landing** — what a bare URL shows. It used to join a meeting literally
  called `lobby`, so every visitor with no query string landed in one shared
  room together.
- **pre-join** — camera preview and a name field, remembered in
  `localStorage`. Nothing ever asked for a name before, so the client sent the
  random per-tab id as the display name and rosters read `u-a1b2c3`.
- **meeting** — the console, with the invitation and a copy button in it,
  because the moment you notice someone is missing is a moment you are already
  in the call.

Two details that are load-bearing:

**`render!` folds the text fields back into state before it swaps.** The
console subtree is replaced wholesale, so anything typed and not yet folded in
is destroyed by the next render — and the join screen ships in the SSR'd
document, so the name field is typeable *before the bundle boots*. Measured
2026-08-01: the invitation harness typed a name, `init` rendered a moment
later, and the participant joined under the random id the name was supposed to
replace.

**`join!` awaits `capture!` before opening the socket.** The join button is
also on screen from the first paint, so it gets pressed before `getUserMedia`
resolves. Connecting then produces an offer with no tracks in it: zero
m-lines, ICE never runs, and both tabs sit at one PeerConnection each with
nothing flowing — which is exactly what the media harness reported while this
screen was being built.

## Media topology

`kaigi.plan` decides who subscribes to whom, and returns *diffs* — re-pulling
tracks a participant already has renegotiates their PeerConnection on every
roster change, which everyone sees as a video freeze.

```clojure
(plan/plan-for meeting sessions "jun" subscribed config)
;; :sfu  => {:kaigi.plan/pull [{:session-id … :track-name …}] :kaigi.plan/close ["3"]}
;; :mesh => {:kaigi.plan/peers [{:kaigi.plan/peer-id "rin" :kaigi.plan/role :offerer}]}
```

`transport` picks `:sfu` when an app id and token are configured and `:mesh`
otherwise — a function of configuration, not of headcount, so a deployment
does not switch topology mid-meeting.

In mesh mode `mesh-initiator` gives a total order over participant ids so
**exactly one side offers**. Both peers computing it independently arrive at
the same answer with no extra message, which is the fix for signaling glare —
both sides offering, neither able to answer, failing in a way that looks like a
network problem.

Above `mesh-participant-ceiling` (4) the plan carries a `:kaigi.plan/warning`
**as data**, so the UI can say the meeting outgrew the transport. A limit the
operator only learns from server logs is a limit participants experience as
"the app is broken".

## Two media planes, and why both are here

`kaigi.plan/transport` returns `:realtimekit`, `:sfu` or `:mesh` — decided by
configuration **and by what the connected clients say they can drive**, never
by headcount, so a deployment behaves the same on every join instead of
switching topology mid-meeting.

### The client gets a vote

Configuration alone decided this once. A client declares its planes in
`hello`; `kaigi.plan/negotiate` intersects those declarations with what the
deployment holds credentials for and takes the best survivor, falling back to
mesh. `nil` from a client that has not declared anything means "no opinion"
and is dropped from the intersection rather than emptying it — otherwise one
socket mid-connect would drop a whole room to mesh.

The intersection is over the **room**, not per participant: mesh needs both
ends to agree before either can offer, so a plane held by only some of the
room is not a plane the room can use. One client with a stale bundle therefore
moves everyone — which is a different thing from switching on headcount.
Headcount changes constantly and predicts nothing; a participant who literally
cannot drive the current plane is a meeting that is about to be silent for
them.

`?transport=mesh` narrows what a single tab declares. It is a field diagnostic
("does this work without RealtimeKit?") and the seam that lets
`e2e-media.cljs` prove the mesh still carries RTP on a Worker configured for
RealtimeKit. Narrowing only — a tab cannot claim a plane the bundle has no
code for.

**RealtimeKit is the chosen path** (owner decision, 2026-07-31). It is a
different product from the SFU with a different API and different credentials,
and the two are not interchangeable: measured that day, the RealtimeKit app id
returns exactly the same `not_found` from `rtc.live.cloudflare.com` as an
all-zeros UUID does.

|  | SFU | RealtimeKit |
|---|---|---|
| host | `rtc.live.cloudflare.com/v1/apps/{app}` | `api.cloudflare.com/client/v4/accounts/{acct}/realtime/kit/{app}` |
| credential | app secret | Cloudflare API token |
| abstraction | sessions and tracks, no rooms | meetings and participants |

**`kaigi.sfu` is retained rather than deleted.** The binding is written and
tested against the published OpenAPI, the SFU stays the lower-level option for
raw track control, and removing it would mean rediscovering the wire format the
next time anyone wants it.

### The SDK is vendored, not compiled

`kaigi.app` loads `@cloudflare/realtimekit` with a `<script>` tag from
`/js/realtimekit.js`, put there by `vendor-realtimekit.cljs`. Not a
`:require`, and not a preference: the package's CommonJS entry contains
`super()` inside an arrow function, which the Closure compiler refuses
outright — measured 2026-08-01, `amu compile --target wasm32-browser app` fails with
`closure-compiler does not allow calls to super() in arrow functions` at
`dist/index.cjs.js:8`. The package also ships `dist/browser.js`, a prebuilt
IIFE assigning the client to a global, which needs no bundler at all.

It is the better arrangement anyway. A 650 KB third-party blob is not source
this repo compiles, the version stays pinned by `package.json`, and a
deployment running on the mesh never downloads a client it will not use. The
vendor step asserts the global is still called `RealtimeKitClient` rather than
copying blindly — a rename would otherwise ship a file that loads cleanly and
defines nothing.

### One RealtimeKit meeting per room, created exactly once

A Durable Object is single-threaded but not single-*task*, and the difference
is where this broke. The two `hello` frames of a two-person meeting land
microseconds apart; both found `:rk-meeting-id` still nil while the first
`create` was in the air, and both created one. Measured against production
2026-08-01: **both tabs joined RealtimeKit successfully and each saw zero
other participants**, because they were in two different RealtimeKit meetings.

`rk-creating` memoizes the in-flight *promise* — an id cannot be memoized
before it exists — in its own atom rather than in `room-states`, because that
map is rewritten wholesale by `handle-frame` from a snapshot taken before
`broadcast-state!` ran. It is cleared on rejection too: one transient error
from the Cloudflare API must not leave every later join awaiting a promise
that will never resolve.

### RealtimeKit does not replace `kaigi.model`

RealtimeKit has its own meetings and participants, and adopting them wholesale
would put two authorities in one system — its presets deciding who may speak
while `kaigi.model` decides who is admitted, disagreeing the first time a host
denies someone.

So `kaigi.model` stays the authority for admission, roles and consent, and
RealtimeKit carries media. The seam is `kaigi.realtimekit/token-refusal`: the
room mints a participant token only for someone the model says is `:admitted`.
RealtimeKit never learns about the lobby and does not need to — a meeting you
cannot get a token for is one you cannot join. That check is the *only* place
the gate exists, because a token already issued is a join already possible.

## SFU binding

`kaigi.sfu` shapes requests and parses responses; it holds no HTTP client and
no secret. Field names are transcribed from Cloudflare's published OpenAPI
document (`realtime-api-2024-05-21.yaml`, `servers: https://rtc.live.cloudflare.com/v1`),
and the tests assert those literal shapes — a misspelled `trackName` would
otherwise round-trip through the constructor and back unnoticed.

Two details that are load-bearing:

- **The app secret is not in a request descriptor.** `authorize` is the only
  function that attaches it, so descriptors can be logged and asserted on.
- **A per-track `errorCode` fails the whole response.** The SFU reports partial
  failures inside a 200; a caller that checks only the HTTP status records a
  subscription that was refused, and the participant sees a black tile with no
  error anywhere.

## Signaling room

`worker/` is a Cloudflare Worker whose `KaigiRoom` Durable Object serializes
one meeting. A meeting needs exactly one writer, and a DO is globally unique
and single-threaded per id — so "one writer" is a property of where the code
runs, not something the code implements with leases or fencing tokens. Live
room state lives in the DO; anything cross-meeting belongs in D1, because each
DO's storage is private and would split a cross-meeting query plane into one
island per room.

The class is a ClojureScript `deftype`, not a JavaScript shim: `deftype` emits
a positional constructor and writes `Object` protocol methods to the prototype
un-munged, which is exactly what the DO runtime calls by name.

The wire format is EDN. The model uses sets (`consents`, `tracks`) and keywords
(admission, roles); JSON round-trips neither, so every frame would need a
translation layer whose only job is undoing the format.

```
GET /api/kaigi/ws?meeting=<id>   WebSocket into the room
GET /api/kaigi/health            liveness + which transport is active
```

`health` reports the transport because "is the SFU configured" is the one
operational question whose wrong answer is invisible: a deployment missing
`REALTIME_APP_ID` works fine, in mesh, until the fifth participant joins.

## Recording

Every participant records their own stream while recording is armed; parts land
in R2 under `kaigi/<meeting>/<participant>/<zero-padded-seq>.webm`, and the
meeting carries only a prefix.

**The client holds no "am I recording" flag.** `kaigi.recording/capturing?` is a
function of the meeting value — armed, live, admitted, in the room — and the
browser re-evaluates it on every roster update. That is the entire mechanism by
which a consent withdrawal stops capture: `kaigi.model/revoke-recording-consent`
turns recording off in the shared value, and every recorder stops on the next
frame without anyone sending a stop. A client with its own boolean would leave
microphones running while the model said off.

The upload goes **through the Durable Object**, not to a presigned bucket URL.
The DO is the only holder of the authoritative meeting, so it is the only thing
that can answer "is this participant still allowed to be recording"; a presigned
URL moves that decision to whoever holds the URL, which is precisely the decision
that must not move. A part uploaded after a withdrawal gets 409 and the client
stops.

The handoff record for `kotoba-lang/gijiroku` carries the asset reference, the
participants and the consent set — never media, never a transcript (its charter
G4). `handoff-problems` re-checks consent rather than inferring it from the
existence of a file, which is G3: *"there is a recording, so they must have
agreed"* is the inference the charter forbids.

Measured end to end (two headless Chromium instances, fake devices, local R2):
both participants recorded, **4 objects of ~300 KB of real WebM** landed under
exactly the keys `object-key` specifies, a withdrawal turned recording off in
the shared value and stopped both recorders, in-flight parts were refused 409 by
the room, and nothing further was captured.

## Build and test

```bash
# pure core, both runtimes
kbb -M:test
kbb --backend sci --classpath "src:test:../webrtc/src:../org-w3-webrtc-signaling/src" run-tests.cljk

# worker
cd worker
npm install
kbb --backend sci vendor-realtimekit.cljk                 # SDK -> public/js/, see "vendored, not compiled"
node ../../../../scripts/resource-guard.mjs run build -- amu compile --target wasm32-browser worker
kbb --backend sci verify-bundle.cljk                      # actually import()s the artifact
npx wrangler dev --port 8799 --local &
kbb --backend sci e2e.cljk ws://127.0.0.1:8799            # two real sockets against a real DO

# console: SSR the shell, score it, build the browser bundle
kbb --backend sci --classpath "../src:../../webrtc/src:../../org-w3-webrtc-signaling/src:\
../../kotoba-ui/src:../../liquid-glass-ui/src:../../shitsuke/src:\
../../css/src:../../html/src:../../appkit/src" generate-page.cljs
(cd ../../design-quality && kbb --backend sci -m design-quality.cli score ../kaigi/worker/public/index.html --min 100)
node ../../../../scripts/resource-guard.mjs run build -- amu compile --target wasm32-browser app

# a real call: two headless Chromium instances with fake devices, asserting
# inbound RTP bytes > 0 on both sides. Pins ?transport=mesh, so it proves the
# mesh still carries media on a Worker configured for RealtimeKit.
kbb --backend sci e2e-media.cljk http://127.0.0.1:8799

# the product claim: a link is the whole of joining
kbb --backend sci e2e-invite.cljk http://127.0.0.1:8799

npx wrangler deploy

# the RealtimeKit plane needs the real service — there is no local equivalent,
# because the plane IS the service. Run against the deployment.
kbb --backend sci e2e-realtimekit.cljk https://kaigi.<subdomain>.workers.dev
```

`release`, never `compile`: a `compile` build exits 0, emits every expected
export name, and passes `node --check`, while importing a machine-local
`/tmp/cljs-runtime` path that cannot load standalone. `verify-bundle.cljs`
refuses to run against an artifact older than the newest source — added after a
failed build left the previous bundle in place and the verifier reported six
green checks against code that did not compile.

## The console

`kaigi.ui` is pure `.cljc` hiccup on `kotoba-ui.core`; `generate-page.cljs` SSRs
it to `public/index.html` and `kaigi.app` re-invokes the same fn on every roster
change and swaps it in. One markup source for both hosts.

Two structural details that are load-bearing:

**Video elements are not part of the re-rendered tree.** Tiles emit an empty
`data-kaigi-participant` container; `kaigi.app` creates one `<video>` per
participant and re-parents it after each render. A `<video>` that gets replaced
loses `srcObject` and restarts playback, so a mute toggle would flicker
everyone's video.

**Offer direction comes from the plan, not from negotiation.** The room tells
each side whether it is `:offerer` or `:answerer`, so there is no
perfect-negotiation rollback logic and no state where both peers hold a local
offer.

### Design-system findings worth knowing before extending this

The console is built on `kotoba-ui.core` + shell only, and the rendered page
scores **100.00** with zero findings. Two upstream gaps were hit and are
recorded here rather than worked around:

- **`panel` / `button` silently drop unknown opts.** They resolve to
  `shitsuke.components/card` / `button`, which read only `:class` (a **string**)
  and `:id` / `:act`. Passing `:attrs {:data-kaigi-tile id}` rendered markup
  that looked correct and carried no data attributes at all, so the browser
  found zero tiles to attach video to — with no error anywhere. Data hooks
  therefore live on plain wrapper elements, and targeted actions encode their
  target in the `:act` string (`"admit:rin"`).
- **A toggle cannot expose `aria-pressed`** for the same reason, and
  hand-rolling a `<button>` is the failure the agent-guide names explicitly. The
  labels state the current state instead. Adding `:attrs` support to the
  liquid-glass components would close both.

## What is missing, precisely

1. **~~The RealtimeKit path is not wired past the binding.~~ Wired.** The room
   creates the RealtimeKit meeting, mints a token per admitted participant and
   sends it with the plan; the browser loads the vendored SDK, joins with that
   token, and re-parents the tracks it hands back into the tiles the roster
   already rendered. `e2e-realtimekit.cljs` is the gate. What remains is
   **screen share on this plane** — `start-share` still moves the model value
   and the mesh path, and nothing calls the SDK's screen-share API.
2. **The SFU path is untested against the real service.** No Cloudflare
   Realtime app exists for this account — the wrangler OAuth session carries no
   `calls`/`realtime` scope, and minting an app token needs the dashboard.
   Provisioning is one owner action and no code change:

   ```bash
   wrangler secret put REALTIME_APP_ID   --name kaigi
   wrangler secret put REALTIME_APP_TOKEN --name kaigi
   ```

   Until then `transport` reads `:mesh` and small meetings work.
3. **TURN is wired but the relay path is NOT verified end to end.** What is
   done: `kaigi.turn` mints coturn-style ephemeral credentials
   (`username = "<expiry>:<participant-id>"`, HMAC-SHA1 under a server-only
   secret) so no standing relay password is ever handed to a browser; the room
   sends a fresh one per participant; `/api/kaigi/health` reports whether
   minting actually works (`"turn":"ok"|"absent"|"error: …"`); the console warns
   on screen when no relay is present; `?ice=relay` forces relay-only ICE and
   `e2e-media.cljs --relay` asserts the selected candidate type is `relay`.

   What is NOT done: **Chromium never contacts the relay.** Measured
   2026-07-30 — with a valid minted credential, under both
   `iceTransportPolicy: "relay"` and `"all"`, against both a loopback-bound and
   a LAN-bound relay, and with both the headless shell and the full
   Chrome-for-Testing build, Chromium gathered **zero** candidates from the
   TURN server and emitted **zero** `icecandidateerror`, and the relay received
   no datagrams at all.

   The relay is not the problem: `org-ietf-turn`'s own `listener_demo.cljs`
   passes 3/3 over real UDP (Allocate, ChannelBind + bidirectional ChannelData,
   wrong-credential rejection), and `kaigi.turn`'s tests show the minted form is
   exactly what that listener's verifier accepts. One real upstream bug was
   found and fixed on the way (`org-ietf-turn` `ede5921`: the listener dropped
   STUN Binding requests, which an ICE agent sends *before* it will attempt
   Allocate) — necessary, but not sufficient. The remaining blocker is in the
   browser's acceptance of the ICE-server configuration and is unresolved.
4. **~~No recording pipeline.~~ Built.** See "Recording" below. What remains is
   the consuming side: `gijiroku` does not yet read the handoff record.
5. **Not wired to `kaisha` or `calendar`.** `:kaigi/channel` exists so a meeting
   can name the chat channel it was called from; nothing reads it yet.
