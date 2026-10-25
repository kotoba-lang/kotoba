# kotoba-hls

**Watching a live HLS broadcast — the decisions as pure data, the player
once.** A [kotoba-lang](https://github.com/kotoba-lang) capability library.

A live-video page answers the same three questions over and over: is anything
broadcasting, is it the same thing already attached, and what should the viewer
be told. All three are decided from data; only the attaching needs a DOM. So
this library splits them — the same split
[`kotoba-lang/webrtc`](https://github.com/kotoba-lang/webrtc)'s
`kotoba.webrtc.whip` makes between WHIP's decisions and its transport.

```text
kotoba.hls         pure .cljc reducer — no I/O, no DOM, no HLS library
kotoba.hls.view    hiccup over kotoba-ui's shell + HIG tokens
kotoba.hls.player  ClojureScript: fetch loop + <video> + hls.js
```

## Why it exists

Two sites were showing the same broadcast through two implementations of this
logic — one ClojureScript, one JavaScript embedded in a Clojure string, with
two different ways of shipping hls.js. That is the shape of thing that gets
fixed in one copy.

## Contract

```clojure
(require '[kotoba.hls :as hls])

(def s0 (hls/create-state))                       ; :unknown

(hls/apply-event s0 {:type :broadcasts :broadcasts listing})
;; => {:state {:hls/state :live :hls/playing "https://…/playlist.m3u8"}
;;     :effects [[:attach "https://…/playlist.m3u8"]]}

(hls/status state :ja)   ; => "配信中" / "配信していません" / an error message
(hls/mode state)         ; => "live" — the container's data-mode, so nothing
                         ;    ever writes an inline style
```

Three behaviours worth stating, because getting each wrong is a real bug:

- **The newest live broadcast wins.** The plane lists oldest-first, so the
  *last* live entry is the one someone opening the page now means to watch.
- **Re-attaching the same URL emits no effect.** Without that check every poll
  tears down and rebuilds a perfectly healthy player.
- **Idle is a state, not an error.** Nobody is broadcasting most of the time; a
  page that renders that as a failure trains people to ignore real failures.

## Browser

```clojure
(require '[kotoba.hls.player :as player])
(player/boot #js {:base "https://live.example" :locale "ja"})
```

Native HLS is preferred and hls.js is the fallback, **in that order**. iOS
Safari has no Media Source Extensions, so hls.js cannot work there at all —
preferring it is how an HLS page ends up working on the author's Mac and
showing a black rectangle on every phone.

## View

`kotoba.hls.view/player` returns a body *fragment*, not a document: a static
site wraps it in its own page shell with a cached stylesheet link, a Worker
wraps it in `kotoba-ui.shell/page`. Those are different hosting models and the
component should not care which it is in. `view/css` gives the handful of rules
a `<video>` needs that no shell scaffold covers.

## Test

```sh
kbb -M:test    # kotoba.hls — 7 tests, 39 assertions
kbb -M:lint
```

`kotoba.hls` has no dependencies at all, so the part with the tests is portable
across JVM / ClojureScript / SCI / GraalVM. The view pulls in `kotoba-ui`; the
player pulls in `hls.js`.

## License

Apache License 2.0.
