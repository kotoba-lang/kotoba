# com-prolific-app

Prolific (`prolific.com`) integration for the fleet: recruit identity-verified
human participants through an API instead of a vendor UI, so a study is a
reproducible command rather than a form somebody filled in once.

Unlike the clean-room `com-*` actors in this org, this is **not** a
reimplementation of Prolific's API — it is a client for the real one. Prolific
sells access to a pool of real people; there is nothing to clean-room.

## Why it exists here

Extracted from `network-awai/cloud-itonami`'s `scripts/prolific-study.cljs`,
which was the first consumer. The same argument as the nexus-x402 extraction:
the reward arithmetic, the audience filter resolution and the submission
triage are not cloud-itonami concerns, and a second product wanting user
testing should not fork a copy of the money code.

## One source, not the panel

cloud-itonami's ADR-0035 decided the platform runs **its own** two-sided
research panel (ISIC 7320 demand / ISCO 4227 supply) rather than buying a
vendor's. This client is therefore **one recruitment source that can feed
that panel**, never the panel itself.

That is why the panel's join key is `{{PARTICIPANT_REF}}` and not
`{{%PROLIFIC_PID%}}` — invariant 2 in that ADR names it in the platform's own
vocabulary precisely to keep studies portable off any one vendor. A caller
wiring this client into a study is responsible for mapping Prolific's
participant id onto a panel ref; this library deliberately does not assume it
owns that identity.

## Layout

```
src/prolific/core.cljk      pure: rewards, filters, study payload, triage
src/prolific/evidence.cljk  pure: did the write actually land?
src/prolific/channel.cljk   pure: which automation channel may be used at all
src/prolific/signup.cljk    pure: the researcher signup as steps and fields
src/prolific/client.cljk    HTTP: fetch/post against api.prolific.com
src/prolific/browser.cljk   CDP: drive a form through agent-browser
```

The split is the point. Everything that decides **what a participant is paid**,
**which population is recruited** and **which submissions get money** is pure
and runs on both hosts with no network and no token. `client.cljs` only moves
bytes.

## Getting an account is part of the integration

The API client above assumes a token, and a token assumes a researcher
account. Registering one is a browser form, so the form is modelled here too —
as data and as a verified driver, not as a runbook somebody follows by hand.

### An actuator's return value is not evidence

`evidence.cljc` exists because of three measured lies. Driving the signup form
through desktop synthetic input on 2026-07-30 produced:

```
type   -> "Typed"               4 characters silently dropped
key    -> "Pressed tab"         focus never moved, so the next value was
                                concatenated onto the previous field
resize -> "after=622,-1049,…"   the window had not moved one pixel; the tool
                                echoed back the bounds it was asked for
```

Each was indistinguishable from success at the call site. Only reading the
target's own state back afterwards caught them. So `verdict` takes intent,
the value **before** acting, and the value read back after — and every verdict
carries its own repair, because picking the wrong repair is how the form got
worse instead of better:

| verdict | means | repair |
|---|---|---|
| `:match` | read-back equals intent | — |
| `:unchanged` | actuator claimed success, value did not move | **change channel** — retrying is superstition |
| `:truncated` | observed is a prefix of intent | refill **whole**, never append the tail |
| `:appended` | intent landed on top of the old value | clear, then refill |
| `:absent` | no such field | re-snapshot |
| `:mismatch` | none of the above | halt |

The `:truncated` row is the one that cost real damage: typing the missing
suffix is the obvious repair and it corrupted the field a second time.

### A channel that cannot be verified is refused

`channel.cljc` decides this **before** touching a form, which is the check
whose absence produced a half-filled one. Three channels were unavailable that
day and each was discovered a field at a time:

- **accessibility** — Chrome's web content was an `AXGroup` 500x547 with zero
  children (renderer accessibility is off by default), so no field could be
  addressed by label
- **coordinate** — the window sat on a second display at `y=-1049` while the
  click space was the primary display only
- **keystroke** — the only one left, and structurally unverifiable: it cannot
  read a field back, so it can never produce the evidence above

There is deliberately no fallback. Refusing stops the run with the form
untouched, which is strictly better than the half-filled form best-effort
actually produced.

### Choosing CDP removes two failure modes outright

`browser.cljs` drives the form through [`agent-browser`](https://agent-browser.dev)
over the Chrome DevTools Protocol. `fill` clears and writes atomically and
`get value` reads back, so `:truncated` and `:appended` cannot occur — measured
against the same strings that had just failed:

```
fill "Research Operations"        -> read back "Research Operations"
fill "User Research" over it      -> read back "User Research"
```

It also reads a `<select>`'s real options, which is what the desktop channel
could not do at all — the run stalled on **Sector** because the option list was
unreadable. `select-verified!` resolves a visible label to the underlying
option value and reports the available labels when one does not match.

```sh
kbb --backend sci -m prolific.browser profile.edn professional-profile
# channel: cdp
# coverage: 5/11 fields fillable now; closable gaps [:country-of-residence]
# step professional-profile — Tell us about your work
#   match  sector             "industry"
#   match  organization-name  "AWAI Network, L.L.C."
#   match  job-role           "Research Operations"
#   match  department         "User Research"
```

### Four reasons a human is needed, not one

`signup.cljc` splits the blocked fields, because lumping them together hides
the only distinction worth acting on:

```
:human/credential    passwords              permanent boundary
:human/captcha       bot-detection          permanent boundary
:human/consent       terms, marketing,      permanent boundary — a consent is
                     cookie banners         given by a person
:human/unknown-fact  country of residence   NOT a boundary: nobody had stated
                                            the value, and it becomes
                                            machine-fillable once configured
```

Conflating the fourth with the first three makes a runner look permanently 60%
manual when it is 80% automatable with two more lines of config. `gaps` reports
that split and `coverage` reports the keys that would close it, so the number
is actionable rather than decorative.

`browser.cljs` has **no function that clicks Continue, Next or Submit**, and
that is not an omission — advancing the signup is what creates the account.
It fills the step in front of it and stops.

## Money is integer cents

`reward-cents` and `cost-breakdown` never touch floating point beyond one
conversion of the configured hourly rate.

This is load-bearing, not stylistic. The first version computed
`(* 100 hourly (/ minutes 60))`; the JVM evaluated that to `200.00000000000006`
where JS got exactly `200`, so `Math/ceil` crossed to the next 5c bracket on
one host and not the other — **the same study paid $2.05 under `clojure` and
$2.00 under `nbb`**. The test suite pins the values both hosts must produce.

## Rates

- `default-hourly-usd` is **12.00**, Prolific's recommended rate, not the 8.00
  floor. A study whose entire output is written answers is the wrong place to
  save 30%: underpaying buys rushed participants and unusable free text.
- `default-fee-rate` is **0.428**, the corporate platform fee (academic and
  non-profit is 0.333).

## Audience filters

Choice ids are account-scoped and opaque (`"0"`, `"13"`, …), so
`resolve-languages` reads them from a live `GET /filters/` response rather
than hardcoding. It prefers the *fluent languages* filter over *first
language*: what decides whether someone can do the task is whether they can
read the screen, not what they grew up speaking.

An unmatched request is returned as `{:error :unmatched :missing [...]}` and
never silently dropped — dropping one would recruit a population nobody asked
for.

## Paying people

`triage` separates submissions awaiting review into those that carry a
completion code and those that do not. The second group are the participants
who abandoned the task: an auto-approval rule keyed on the completion code
cannot reach them, and they are owed payment all the same. They are also the
people a usability study most needs to hear from.

```clojure
(require '[prolific.core :as p] '[prolific.client :as c])

(p/usd (:total-cents (p/cost-breakdown 30 10)))   ;=> "$85.68"

(-> (c/resolve-languages ["English" "Hindi" "Chinese" "Spanish" "Arabic"])
    (.then #(c/create-study (p/study-payload task {:places 5 :language-filter %
                                                   :completion-code "…"
                                                   :external-url "…"}))))

(c/approve-all study-id)   ;=> {:total 30 :approved 4 :failed []}
```

## Endpoints, as documented

`/submissions/?study={id}` — **not** `/studies/{id}/submissions/`, which does
not exist and which the first draft of the caller used.

## Test

```sh
npm test          # nbb / JS host
kbb -M:test   # JVM host — must agree exactly
```

53 tests, 160 assertions, both hosts. The signup and evidence tests carry the
real strings from the failed run, so a regression reads as the original bug.

`browser.cljs` is nbb-only and not in the suite; it was exercised against a
fixture form, including the paths that matter — an absent label, an unmatched
`<select>` option, and the refusal, which exits 1 without touching the page.

## Status

Scaffolded 2026-07-28. **The client has never been run against the live API** —
every test here uses fixtures shaped like the documented responses. Before
trusting it with money, confirm the real filter ids with
`GET /filters/` and compare against `filters-fixture` in the test.

The signup model is transcribed from a real traversal on 2026-07-30 that
reached the third step. **The `:credentials` step was never seen** — its fields
are the three that must be human anyway, so they are modelled from the
boundary rather than from observation, and the step's field labels may be
wrong. `agent-browser` launches its own Chrome and therefore cannot resume a
signup started in the user's logged-in profile; that is what the `:extension`
channel is for.
