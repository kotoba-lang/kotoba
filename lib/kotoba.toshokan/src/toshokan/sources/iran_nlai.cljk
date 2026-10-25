(ns toshokan.sources.iran-nlai
  "National Library and Archives of Iran (سازمان اسناد و کتابخانه ملی ایران,
  nlai.ir) -- INTENTIONALLY NOT IMPLEMENTED. `:spec` tier only.

  Research (2026-07-19) found no official API, OAI-PMH endpoint, SRU/Z39.50
  service, or bulk bibliographic export published by nlai.ir. The only
  public interface is a legacy Persian-only JSP OPAC (opac.nlai.ir), whose
  reachability from outside Iran could not even be confirmed (WebFetch got
  ECONNREFUSED, consistent with but not proof of geo/IP blocking). The
  existence of an unofficial third-party scraper
  (github.com/ketabchi/melli, \"getting data from opac.nlai.ir\") is itself
  evidence there is no sanctioned channel to harvest from.

  Separately, NLAI is an Iranian government body, so any automated access
  sits inside OFAC's Iran sanctions regime (31 CFR Part 560 / ITSR). The
  Berman Amendment (31 CFR 560.210(c)) plausibly exempts pure
  informational/bibliographic materials, but no on-point OFAC guidance for
  a public government OPAC was found, and this has not been reviewed by
  counsel -- treat as unresolved, not cleared.

  Given both (a) no real ingest path exists today and (b) the access
  question that does exist is legal/sanctions-sensitive rather than
  technical, this is left as a documented gap rather than an
  implementation. Building an unofficial HTML scraper against a
  geo-restricted foreign government system is out of scope for this
  repo -- see the ADR this namespace's docstring is dated to for the full
  writeup. If NLAI ever publishes an official API this namespace is where
  a real harvester would go, using the same `search` / `->quads` shape as
  toshokan.sources.ndl / toshokan.sources.loc."
  )

(def ^:const source-key :iran-nlai)

(defn search [& _]
  (throw (ex-info
          "toshokan.sources.iran-nlai: no official API exists; harvesting intentionally not implemented (spec-only, see repo ADR)"
          {:source source-key :status :spec})))

(defn ->quads [& _]
  (throw (ex-info "toshokan.sources.iran-nlai: spec-only, no data to convert" {:source source-key :status :spec})))
