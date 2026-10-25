# kotoba-lang/fsm

**SSoT for `kami.fsm`** — EDN animation/behaviour state machines.

`kotoba.fsm` is a thin facade. See ADR-2607102200 addendum 7.

The generic map-driven API remains in `.cljc`. The canonical bounded
`player-v1` transition profile is implemented as the multi-module Kotoba graph
`src/kami/fsm.kotoba` → `src/kotoba/fsm.kotoba`. It deliberately does not
reinterpret arbitrary legacy maps as the closed player profile.

## The profile is what RUNS

For `default-player-fsm`, `advance` does not compute the transition here. It
converts its arguments into the guest ABI and executes
`resources/kami/fsm/oracle/player.kir.edn` — `src/kami/fsm.kotoba` compiled —
through `kami.fsm-oracle`. The KIR interpreter (`io.github.kotoba-lang/kotoba-kir`)
is therefore a **runtime** dependency; the compiler stays **test-only** and
never reaches a consumer.

Delegation is conditional, because this namespace is a generic engine and the
profile is a bounded slice of one machine. The shipped core answers when the
machine IS `default-player-fsm`, the state is a case the shipped variant
declares, and the events are a set of keywords no larger than the interpreter
accepts (32; the profile's alphabet is three). Everything else — any other
machine, an undeclared state, a vector of events, an oversized set — is
answered by the generic engine with exactly its previous behaviour. Which path
runs is decided by the **values**, never by whether the artifact loaded: a
missing artifact throws rather than falling back.

On ClojureScript there is no classpath, so a host must call
`kami.fsm-oracle/register-kir!` before `advance` will answer for
`default-player-fsm`. Other machines are unaffected.

Regenerate the artifact after editing the `.kotoba`:

```sh
kbb -M:test:gen
```

## Tests

```sh
kbb -M:test
```

- `test/fsm_parity_test.cljk` — the generic engine against the Kotoba profile
  over every state crossed with every subset of the declared alphabet, plus
  out-of-alphabet events and two-step sequences. Its oracle is now a *marked
  copy* of the machine, so that the comparison stays engine-vs-profile rather
  than artifact-vs-itself.
- `test/kami/fsm_oracle_test.cljk` — the two checks a parity test structurally
  cannot make: that the shipped artifact **is** the current source compiled,
  and that the host **runs** it (a deliberately-wrong core is registered and
  the host is required to follow it — and required *not* to, for every call
  outside the profile).
