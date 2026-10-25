# KAMI Waves — a CLJ gameplay reference

Behaviour authored entirely in the kami-clj subset (`logic.clj`), compiled to WASM by
`kami-engine-clj` and driven by the Rust host — the host holds none of the game logic (ADR-0036/0038).
The visual profile (colours/sizes/arena) is data in `scene.edn`.

This game exists to exercise the expanded compiler forms in real gameplay: `->` + `clamp` for the
difficulty ramp (`burst-size`), `dotimes` for the wave burst, `even?` + `case` for the per-wave spawn
pattern, and `max` for the fire-rate floor. Compile it with:

    cargo run -p kami-engine-clj --bin kamiclj -- kami-clj-play/games/waves/logic.clj -o /tmp/waves.wasm
