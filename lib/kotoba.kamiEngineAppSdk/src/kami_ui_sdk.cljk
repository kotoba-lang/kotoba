(ns kami-ui-sdk
  "KAMI Engine app chrome SDK — browser-side helpers for kami-engine WebGPU apps.

   Merged surfaces (ADR-2607102200 addendum 2):
   - `kami-ui-sdk.*` — portable CLJC ports of kami-engine's live kami-ui-sdk JS
     (ui/motion/effect/sound/engine-audio/rtc/widgets)
   - `kotoba.ui` — hiccup HUD over the game canvas (:panel/:bar/:minimap/:text,
     mount!/render!), formerly standalone `kami-engine-hud`

   One package owns \"what the DOM overlay shows\" and \"how chrome behaves\"
   (easing, particles, audio cues, RTC spatialize). Distinct from
   `kami-engine-sdk` (ECS/scene/render-IR) and from `kotoba-ui` (product design system).

   | Namespace                   | Role |
   |------------------------------|------|
   | `kotoba.ui`                  | EDN HUD overlay (ex-kami-engine-hud) |
   | `kami-ui-sdk.ui`             | theme / LabelOverlay projection math |
   | `kami-ui-sdk.motion`         | easing / spring / tween |
   | `kami-ui-sdk.effect`         | particle trajectories |
   | `kami-ui-sdk.sound`          | UI sound presets |
   | `kami-ui-sdk.engine-audio`   | engine synth params |
   | `kami-ui-sdk.rtc`            | RTC spatialize mapping |
   | `kami-ui-sdk.widgets`        | DOM Slider/ColorSwatch/Carousel |")
