# uptime

**Observations of a service → a statement about its availability.** Pure
`.cljc`, zero runtime dependencies.

Written because the alternative is a status page that *asserts*. A page saying
"all systems operational" with nothing behind it is worse than no page: it is
read as a measurement, quoted back in a contract dispute, and right by
construction — it says the same thing during an outage.

## Three distinctions an assertion-based status page does not have

**Unobserved is not up.** A window nobody probed produces `:unobserved`, never
100%. A prober that dies quietly otherwise reads as perfect availability —
the moment you can least trust the number is the moment it looks best.

**A prober that could not run is not an outage.** Three outcomes, not two.
`:up` and `:down` are claims about the service; `:inconclusive` is a claim
about the probe (DNS failed on the prober's own network, the laptop slept, a
token expired). Counting those as downtime understates the service and teaches
everyone to ignore the number; counting them as uptime is the lie in the other
direction. They are excluded from the ratio and reported separately.

**Coverage is part of the statement.** 100% over 4% coverage is not a good
month, it is an unmonitored one, and `describe` says so in the same sentence
as the number.

```clojure
(require '[uptime.core :as up])

(up/statement "https://authn.kotobase.net/health" observations from to
              {:expected 1440})
;; => {:availability/status :available
;;     :availability/ratio 0.9993  :availability/coverage 0.97
;;     :availability/observed 1398 :availability/inconclusive 6
;;     :availability/incidents [{:incident/from … :incident/probes 1
;;                               :incident/detail "502 from origin"}]}

(up/slo-verdict stmt 0.999)
;; => {:slo/verdict :met :slo/ratio 0.9993 :slo/target 0.999}
```

`slo-verdict` returns **three** answers. `:cannot-say` is what a month with
four probes in it gets, because a ratio computed from four probes is not
evidence about that month — and reporting it as `:met` is how an SLO becomes
decoration. The failure this prevents is specific: a prober quietly stops, the
handful of probes that did land all succeeded, and the month reports as met.
Every incentive points at not noticing.

Consecutive failures fold into one incident, with the first probe's detail
attached: three failures a minute apart are one thing a reader can act on, and
three lines are not.

## Build

```bash
kbb -M:test    # 10 tests / 41 assertions
```
