(ns kotoba.insurance.us
  "United States insurance/claims identifiers -- pure format validation.

  Two identifiers are addressed here, and they are *not* symmetric in how
  well-specified they turned out to be after primary-source research
  (2026-07-08) -- this namespace implements exactly as much as each
  identifier's actual sourcing supports, rather than treating them alike.

  ## NAIC company code (structural validation only -- no check digit)

  The **NAIC company code** (also called the \"NAIC number\") is a 5-digit
  numeric identifier the National Association of Insurance Commissioners
  assigns to every insurance company that files financial data with it. The
  primary source is NAIC's own official Glossary of Insurance Terms:

  > \"Company Code - a five-digit identifying number assigned by NAIC,
  > assigned to all insurance companies filing financial data with NAIC.\"
  > -- https://content.naic.org/glossary-insurance-terms, retrieved
  > 2026-07-08 (direct `curl`, no JS/WAF block -- unlike EUR-Lex; verbatim
  > excerpt archived at
  > orgs/kotoba-lang/emr-claims-primary-sources/us-naic/naic-glossary-company-code-excerpt.md).

  Independently corroborated by HL7 Terminology's own registered NamingSystem
  for this code system (`NAICCompanyCodes`, OID `2.16.840.1.113883.6.300`),
  which cites the same NAIC glossary page as its source and likewise
  describes it as a five-digit identifier with no check-digit mention.

  **No check-digit algorithm is documented anywhere in either source** (nor
  in any other NAIC publication surfaced during this research -- a search of
  the full glossary page's raw HTML for \"check digit\" also returns zero
  hits). Per this namespace's operating rule (see `kotoba.insurance.jp`'s
  precedent), an undocumented algorithm is not guessed at: `valid-naic-company-code?`
  and `validate-naic-company-code` check *only* that the value is exactly 5
  decimal digits (numeric range \"00000\"-\"99999\", leading zeros
  significant/allowed) -- there is no `naic-company-code-check-digit`
  function in this namespace, unlike `jp`'s `hokensha-bangou-check-digit` /
  `iryokikan-bangou-check-digit`, because there is nothing here to
  recompute.

  Known gap, not implemented: some secondary sources (encountered only as
  search-result summaries, never confirmed by directly reading a full
  primary document) suggest NAIC company codes below 10000 map to older
  companies filing a combined property/casualty statement. The one NAIC PDF
  found that might have confirmed or refuted this
  (`publication-loc-zu-listing-companies-summary.pdf`) could not be read as
  text (it fetched as an undecodable font-subset/compressed stream), so this
  namespace does **not** encode any numeric-range-to-category mapping for
  NAIC company codes -- `valid-naic-company-code?` treats the full
  \"00000\"-\"99999\" range uniformly.

  ## Payer ID (structural validation only -- deliberately not a registry check)

  A **Payer ID** is the code a clearinghouse assigns to an insurance payer
  (or third-party administrator/self-insured employer) so that an electronic
  claim (ASC X12 837, loop 2010BB `NM1` segment, `NM108` = \"PI\") can be
  routed to the right destination via `NM109`. Unlike the NAIC company code,
  **there is no single official registry or issuing authority for Payer ID
  values** -- this absence-of-a-standard is itself the primary finding, not
  an oversight in this namespace's research:

  - Every clearinghouse (Availity, Change Healthcare, Stedi, Jopari, Data
    Dimensions, Carisk, etc.) assigns its own Payer ID values independently,
    and the *same* payer routinely has *different* Payer IDs at different
    clearinghouses (and sometimes several \"client-specific\" Payer IDs at
    the same clearinghouse) -- see the industry writeup at
    https://blog.daisybill.com/how-to-e-bill-clearinghouse-payer-ids
    (retrieved 2026-07-08), which documents both numeric (e.g. \"35076\",
    \"33600\") and alphanumeric (e.g. \"WX867\", \"E0679\", \"TP057\")
    real-world examples, and one TPA (CorVel) alone maintaining 409 distinct
    Payer IDs.
  - Real-world companion guides show `NM109` payer-identifier values of
    varying length and shape in practice -- e.g. a 9-digit numeric TIN-like
    value (AHCCCS: \"866004791\") alongside more typical 5-character
    alphanumeric codes -- confirming there is no fixed digit-width either.
  - The one structural constraint that *does* come from an accredited
    standards body is ASC X12's own data-element type for `NM109`: element
    67 (\"Identification Code\") is defined as data type `AN` (alphanumeric
    string), minimum length 2, maximum length 80 (\"AN 2/80\"). ASC X12's
    own Technical Report Type 3 (TR3) implementation guides are a paid
    subscription product (x12.org did not serve this detail on direct
    fetch), so this figure is corroborated here only via three independent
    third-party EDI-standard reference mirrors of the same X12 element
    dictionary entry (Stedi, and two legacy ASC X12 004010 element-dictionary
    mirrors) rather than read directly from x12.org's own TR3 -- flagged
    honestly as secondary corroboration of a standards-body figure, not a
    primary-source fetch.

  Given that, `valid-payer-id-shape?` / `validate-payer-id-shape` check only
  the X12 `AN 2/80` structural envelope (2-80 characters) plus an
  alphanumeric-only charset -- the latter is *not* itself a documented X12
  rule (X12's \"AN\" type is broader than bare alphanumerics) but matches
  every real-world Payer ID example found during this research, none of
  which contained spaces, hyphens or other punctuation. A true result here
  means only \"shape a Payer ID could plausibly have\" -- it is **not** a
  claim that the value is a real, currently-issued Payer ID for any specific
  clearinghouse, and there is deliberately no check-digit or registry-lookup
  function, because no such algorithm or public registry exists to
  implement.")

;; ---------------------------------------------------------------------
;; NAIC company code (5-digit numeric, no documented check digit)
;; ---------------------------------------------------------------------

(defn valid-naic-company-code?
  "True when s is exactly 5 decimal digits (the NAIC company code's only
  documented structural constraint -- see namespace docstring for why there
  is no check-digit function to pair with this predicate)."
  [s]
  (boolean (re-matches #"\d{5}" (str s))))

(defn validate-naic-company-code
  "Return a validation result for a NAIC company code, in the same
  {:insurance/valid? ... :insurance/error ...} shape used elsewhere in this
  library (see kotoba.insurance.jp). The only failure mode recognized is
  :not-5-digits -- there is no :bad-check-digit case here, unlike jp's
  validators, because NAIC does not document a check digit for this
  identifier."
  [s]
  (if (valid-naic-company-code? s)
    {:insurance/valid? true :us/naic-company-code (str s)}
    {:insurance/valid? false :insurance/error :not-5-digits}))

;; ---------------------------------------------------------------------
;; Payer ID (X12 element-67 "AN 2/80" structural envelope only)
;; ---------------------------------------------------------------------

(defn valid-payer-id-shape?
  "True when s is a 2-80 character alphanumeric string -- the ASC X12
  element 67 (\"Identification Code\") structural envelope that the 837
  claim's NM109 Payer ID field uses, narrowed to an alphanumeric-only
  charset matching every real-world Payer ID example found during this
  namespace's research (see docstring). This is a shape check only: it does
  not and cannot confirm the value is a real, currently-assigned Payer ID
  for any specific clearinghouse -- no such universal registry exists."
  [s]
  (boolean
    (when (string? s)
      (re-matches #"[A-Za-z0-9]{2,80}" s))))

(defn validate-payer-id-shape
  "Return a shape-only validation result for a Payer ID, in the same
  {:insurance/valid? ... :insurance/error ...} shape used elsewhere in this
  library. Failure modes: :not-a-string, :non-alphanumeric, :bad-length
  (outside the X12 element-67 2-80 character bound). A true result means
  only \"shape a Payer ID could plausibly have\" -- see namespace docstring."
  [s]
  (cond
    (not (string? s))
    {:insurance/valid? false :insurance/error :not-a-string}

    (not (re-matches #"[A-Za-z0-9]*" s))
    {:insurance/valid? false :insurance/error :non-alphanumeric}

    (not (<= 2 (count s) 80))
    {:insurance/valid? false :insurance/error :bad-length}

    :else
    {:insurance/valid? true :us/payer-id s}))
