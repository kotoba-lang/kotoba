# kotoba-lang/game-production

**The craft layer of game making: a gameSpec, checked, costed, and turned into
the constants and audio requests a build needs.**

Zero-dependency portable `.cljc`. No IO, no generation fleet, no runtime — the
same code runs on the JVM and under nbb, which is what lets a `-ka` repo split
across both without keeping a second copy.

This is the *craft* (技芸) layer of the three-layer split in
[ADR-2607023000](https://github.com/com-junkawasaki/root): the vocabulary is
here, the business — prompts, catalog, serving, keys — stays in
[`cloud-itonami/gameka`](https://github.com/cloud-itonami/gameka), and the
occupation blueprint is
[`cloud-itonami-jsic-3914`](https://github.com/cloud-itonami/cloud-itonami-jsic-3914).

> **Not `kotoba-lang/game`.** That repo is the KAMI *engine* — physics, NPC AI,
> inventory, minigames: the systems a game runs on. This one never runs
> anything. It reads the design and answers questions about it.

## The four namespaces

| ns | question it answers |
|---|---|
| `game-production.spec` | is this design internally consistent? |
| `game-production.balance` | what does it cost the player? |
| `game-production.knobs` | what constants does the runtime need? |
| `game-production.audio` | what does it need to stop being silent? |

```clojure
(require '[game-production.spec :as spec]
         '[game-production.balance :as bal]
         '[game-production.knobs :as k]
         '[game-production.audio :as audio])

(spec/problems design)          ;; => [] when consistent, one map per finding
(bal/report design)             ;; => weapons / evolutions / enemies / pressure / bosses
(k/knobs design 60)             ;; => tuning constants, each with its provenance
(audio/plan design)             ;; => {:beds [...] :cues [...] :unmapped-shapes [...]}
```

## Why each of these is a library function and not a code review

**`spec/problems` catches what playing catches five minutes later.** A weapon
whose `:weapon/evolves-to` names a weapon that does not exist reads fine, loads
fine, and simply never evolves. So does a boss move summoning `"ghost"`, a
coop synergy naming a weapon that was renamed, and a phase list whose
thresholds do not descend to zero — that last one is a boss that cannot be
killed in its final phase. All of them are `nil` lookups at runtime, none of
them throw. The check returns *every* finding rather than the first, because a
proposal with three broken references should come back with three facts.

**`balance` is integer, in milli-units.** `dps-milli` is damage per second
times 1000, so `17142` reads as 17.142 dps. The spec forbids fractional
literals and the runtime plays in fixed point; producing a float here would
reintroduce exactly the drift that rule exists to prevent.

Two numbers in it are worth naming:

- `enemy-contact-dps-milli` divides by the player's invulnerability window.
  Without that divisor a 6-damage shambler reads as instantly lethal and every
  conclusion drawn from it is wrong.
- `clear-rate-required-milli` is the sustained dps at which the alive count
  stops growing at the terminal spawn rate. Below it the field fills to
  `:waves/max-alive` and the run ends by attrition no matter how the player
  moves. It is the one number that decides whether a build has an endgame.

**`balance` deliberately does not model the wave curve.**
`:waves/density-curve "exp"` names a behaviour the *runtime* owns. A second
interpolation here would produce a number that looks authoritative and
disagrees with the game. Every pressure figure uses only quantities the spec
states outright — the interval bounds, the alive cap, the night-rage
multipliers — so it is a bound the spec guarantees, not a guess about the
curve between them.

**`knobs` makes the tick rate an argument.** The survivors runtime template
does not state one. Baking in 60 would be silently wrong against a runtime
built at another rate, so `ticks-per-second` is a parameter and every derived
period is reported next to the millisecond figure it came from — a mismatch
shows up in the output instead of as a game running at the wrong speed.
`render` returns the placeholders it could not fill rather than emitting a
literal `{{ammo_cap}}` into a source file.

**`audio` produces requests, not audio.** A survivors game is unplayable in
silence for a reason no screenshot shows: the weapon cue is the only feedback
that auto-fire is working, and the boss telegraph is the only warning that a
dodgeable attack is coming. Both are already stated in the spec —
`:weapon/shape` says what a shot sounds like, `:move/telegraph-ms` says exactly
how long the warning lasts — so the cue list is derived, and a telegraph cue is
exactly as long as its dodge window. Keeping the fleet out of this namespace is
what lets the same plan be rendered by murakumo, by a local model, or by a
person with a microphone.

`plan` carries `:unmapped-shapes` with it instead of logging it. A caller that
renders the plan and reports a clean run while three weapons had no timbre is
reporting the wrong thing.

## One thing this cannot enforce

`spec/problems` rejects fractional numerics on the JVM. Under ClojureScript it
cannot: JavaScript has one number type, so `400.0` and `400` are the same
value and no runtime check separates them. The rule holds where specs are
authored and reviewed. It is unenforceable in the browser, and the test that
covers it is `#?(:clj ...)` rather than green on a guarantee that does not
hold.

## Tests

```bash
kbb -M:test     # 32 tests, 100 assertions
kbb -M:lint
```

Apache-2.0.
