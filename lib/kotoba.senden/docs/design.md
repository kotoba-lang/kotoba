# senden — design

Marketing domain library on chobo.ledger (lane `:marketing`) + shitsuke.

## senden.campaign
`Campaign{:id :name :channel :status :start :end :budget :metrics}`. Status statechart: `:draft → :scheduled → :running → :paused → :completed | :cancelled`. `(campaign m)`, `(schedule/start/pause/complete/cancel c)`, `(spend c amt)`, `(record-conversion c n)`, `(cpa c)`, `(marketing-activity c opts)` → chobo.ledger activity (lane :marketing).

## senden.funnel
Stages `[:awareness :interest :consideration :purchase :retention]`. `Funnel{:counts {stage→n}}`. `(funnel)`, `(set-stage f stage n)`, `(add-to-stage ...)`, `(stage-count f stage)`, `(conversion-rate f stage)` (next/prev), `(overall-conversion-rate f)` (retention/awareness).

## senden.attribution
`Touch{:channel :campaign :timestamp :customer}`. `(first-touch/last-touch touches)`, `(linear-attribution touches)` → {campaign→1/N}, `(multi-touch-credits touches)` → {campaign→count}, `(attribute model touches)` for `:first/:last/:linear/:multi`.

## senden.events / views / ssr
re-frame portable 7-fn subset (via shitsuke.re-frame.core). app-db `{:campaigns [] :funnel}`. events: `:senden/init`, `:campaign/add`, `:campaign/transition`, `:campaign/spend`, `:campaign/convert`, `:funnel/set`. subs: `:senden/campaigns`, `:senden/funnel`, `:senden/campaign-by-id`. Views: `campaign-card`, `funnel-bar`, `root`. SSR: `sample-db`, `root-html`.
