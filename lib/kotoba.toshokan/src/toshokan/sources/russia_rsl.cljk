(ns toshokan.sources.russia-rsl
  "Russian State Library (Российская государственная библиотека, РГБ /
  \"Ленинка\", rsl.ru) and National Library of Russia (nlr.ru) --
  INTENTIONALLY NOT IMPLEMENTED. `:spec` tier only.

  Research (2026-07-19) found no official public API, OAI-PMH endpoint, or
  SRU service at either institution. rsl.ru's catalog runs on Ex Libris
  ALEPH; a Z39.50 \"gateway\" is referenced in passing
  (lbc.rsl.ru/bib4md5/zg/zg.php) but that page itself was unreachable and
  no host:port/database/terms were ever published anywhere findable --
  informal at best, not a documented public service. nlr.ru runs Ex Libris
  Primo; an NLR<->LIBNET OAI-PMH pilot is mentioned in one source but as a
  library-to-library integration, not a public endpoint. Records use
  RUSMARC, not MARC21. The existence of third-party HTML scrapers
  (github.com/OnlyFart/RslParser against search.rsl.ru) is itself evidence
  there is no official channel.

  Neither institution turned up on an OFAC SDN check in this research pass
  (not independently verified via direct SDN list lookup), and the Berman
  Amendment's informational-materials exemption plausibly covers pure
  bibliographic metadata import the same as it would for Iran. The more
  concrete blocker is technical, not legal: there is no real API, only an
  unofficial HTML scrape of a foreign institution's public search UI. That
  is out of scope for this repo.

  If either institution ever publishes an official API this namespace is
  where a real harvester would go, using the same `search` / `->quads`
  shape as toshokan.sources.ndl / toshokan.sources.loc."
  )

(def ^:const source-key :russia-rsl)

(defn search [& _]
  (throw (ex-info
          "toshokan.sources.russia-rsl: no official API exists; harvesting intentionally not implemented (spec-only, see repo ADR)"
          {:source source-key :status :spec})))

(defn ->quads [& _]
  (throw (ex-info "toshokan.sources.russia-rsl: spec-only, no data to convert" {:source source-key :status :spec})))
