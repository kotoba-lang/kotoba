(ns game.platform
  "Platform detection for KAMI Engine SDK.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/platform.rs`.
  Detects iOS, Android, and Web (desktop browser) at runtime; used by
  input systems to decide touch vs keyboard controls."
  (:require [kotoba.lang.text]))

(def platforms
  "Rust `Platform` enum values."
  #{:ios :android :web})

(defn mobile?
  "True if running on a mobile device (iOS or Android)."
  [platform]
  (contains? #{:ios :android} platform))

(defn touch?
  "True if touch input should be the primary input method."
  [platform]
  (mobile? platform))

(defn detect-from-user-agent
  "Detect the current platform from a user-agent string."
  [ua]
  (let [ua-lower (kotoba.lang.text/lower ua)]
    (cond
      (or (kotoba.lang.text/includes? ua-lower "iphone")
          (kotoba.lang.text/includes? ua-lower "ipad")
          (kotoba.lang.text/includes? ua-lower "ipod")
          (and (kotoba.lang.text/includes? ua-lower "macintosh")
               (kotoba.lang.text/includes? ua-lower "mobile")))
      :ios

      (kotoba.lang.text/includes? ua-lower "android")
      :android

      :else :web)))
