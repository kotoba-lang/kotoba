(ns kotoba.insurance.eu
  "EU/EEA European Health Insurance Card (EHIC) -- pure structural field
  validation only, researched from primary sources 2026-07-08.

  ## Headline finding: there is no single EU-wide EHIC \"number\" format

  Unlike `kotoba.insurance.jp`'s 保険者番号 (a single MHLW-defined 8-digit
  number with a documented check digit) or even `kotoba.insurance.us`'s
  5-digit NAIC company code, the EHIC does **not** carry one unified,
  EU-wide-standardized identification number. What primary-source research
  actually confirms is the opposite: the card's *personal identification
  number* field is explicitly left to each issuing EU/EEA Member State to
  define, and in practice equals (or derives from) that country's own
  national social-security/personal-identification number -- there is no
  common digit count, check-digit algorithm, or character scheme shared
  across Member States. This is not a research gap being reported as a
  negative finding out of caution; it is what the EU's own primary source
  says in so many words (quoted below).

  The **primary source** is Decision No S2 of 12 June 2009 concerning the
  technical specifications of the European Health Insurance Card
  (Administrative Commission for the Coordination of Social Security
  Systems, adopted under Article 72(a) of Regulation (EC) No 883/2004 and
  Regulation (EC) No 987/2009; published Official Journal of the European
  Union C 106, 24.4.2010, p. 26-39; CELEX 32010D0424(09)). Retrieved
  2026-07-08 via a real Chrome browser session -- like `eu-ehds/` in
  `kotoba-lang/emr-claims-primary-sources`, EUR-Lex's `legal-content`
  endpoint serves this page behind an AWS WAF JS challenge that blocks
  automated `curl`/headless fetch (verified: both the modern
  `TXT/HTML/?uri=CELEX:...` endpoint and the legacy
  `LexUriServ.do?uri=OJ:...` PDF endpoint return an empty/202-challenge
  response to a direct request; only a real browser navigation renders the
  text). The rendered page's text was extracted and archived verbatim (the
  operationally relevant clauses) at
  orgs/kotoba-lang/emr-claims-primary-sources/eu-ehic/s2-decision-2009-annex1-excerpt.md.

  Annex I 3.4.3 (\"Issuing state\", Field 2) and 3.5 (\"Personal data
  elements\", Fields 3-9) define the card's data model. The four fields
  this namespace implements, and exactly what is and is not standardized
  about each one, per Annex I:

  ### Field 2 -- Issuing state ID number (`issuing-state-code`)

  > \"Values: The 2 digit ISO country code (ISO 3166-1) ... Length: 2
  > characters ... Remark: The code 'UK' will be used instead of 'GB', the
  > standard ISO code for United Kingdom. One single code will be used for
  > each Member State.\"

  (The Decision's own English text says \"2 digit\" but the values are
  letters, e.g. \"UK\"/\"FR\" -- read here as \"2-character\", not literally
  numeric-digit.) This namespace validates only the **2-uppercase-Latin-
  letter shape** confirmed by this clause, plus documents (but does not
  algorithmically special-case) the UK-for-GB exception. It does **not**
  validate full ISO 3166-1 alpha-2 membership or maintain a list of
  \"currently EHIC-issuing\" states -- both would require additional primary
  sources (a maintained ISO 3166-1 table, and a current confirmation of
  which countries still issue EHICs post-Brexit) not fetched in this cycle.

  ### Field 6 -- Personal identification number of card holder

  > \"Description: The personal identification number detail used by the
  > issuing Member State ... Values: See applicable Personal identification
  > number ... Length: Up to 20 characters for the ID code ... Remark: The
  > personal identification number of the card holder or, when no such
  > number exists, the number of the insured person from whom the rights of
  > the card holder derive. Personal attributes, such as gender, status of
  > family member, cannot be assigned a dedicated field on the card. They
  > can, however, be included within the personal identification number.\"

  This is the field colloquially called \"the EHIC number\", and the primary
  source is explicit that its *value* is nation-specific (\"the personal
  identification number detail used by the issuing Member State\") with no
  documented cross-Member-State digit count or check digit. The
  independent EHIC usage report (Pacolet & De Wispelaere 2016, \"The
  European Health Insurance Card -- Reference year 2015\", European
  Commission DG EMPL, retrieved 2026-07-08 via direct `curl` -- unlike
  EUR-Lex, `ec.europa.eu/social/BlobServlet` is not WAF-blocked) corroborates
  this from the operational side: its footnote 12 records that Luxembourg
  had to reissue every EHIC in 2014 \"due to a change of the composition of
  **the national personal identification number**\" -- i.e. the EHIC's
  personal-ID field tracks whatever Luxembourg's own national ID scheme is,
  not a fixed EU format. The only EU-standardized fact about this field is
  its **structural envelope**: at most 20 characters. This namespace
  implements exactly that bound (and non-blank, per the Remark's clear
  implication that some real identifying value is always present) and
  nothing else -- there is no `personal-identification-number-check-digit`
  function here because no such algorithm exists to recompute.

  ### Field 7, part 2 -- Identification number of the institution

  > \"Description: Identification code awarded nationally to the
  > 'institution', viz. the competent institution of insurance ... Values:
  > See national code list of competent institutions ... Length: Between 4
  > and 10 characters.\"

  Same shape as the personal identification number: nationally assigned,
  no cross-Member-State algorithm, but the Decision does fix a **length
  range** (4-10 characters inclusive). Implemented as a length-only
  structural check.

  ### Field 8 -- Logical identification number of the card

  > \"Description: Logical individual number aiming at uniquely identifying
  > the card ... made up of two parts, the issuer identifier number and the
  > serial number of the card ... Values: The first 10 characters identify
  > the card issuer in compliance with the standard EN 1867 of 1997 ... The
  > last 10 digits constitute the unique serial number ... Length: 20
  > characters (with leading 0 as needed in the 10 digits used for the
  > unique serial number of the card).\"

  This is the most precisely specified field in the whole card: exactly 20
  characters, split into a 10-character issuer-identifier sub-field
  (registered per the external standard EN 1867:1997, \"Machine readable
  cards -- Health care application -- Numbering system and registration
  procedure for issuer identifiers\" -- an ISO/CEN standard cited in Annex I
  section 2's normative-reference table but not itself fetched here; EN
  1867's own content is not free-access, so this namespace treats the
  issuer-identifier sub-field as an opaque 10-character span rather than
  guessing at its internal structure) and a 10-*digit* (decimal, per the
  Decision's own explicit \"digits\" wording, unlike the looser \"digit\"
  used for the issuing-state field above) serial-number sub-field. Both
  constraints -- total length 20, and the trailing 10 characters being
  decimal digits -- are implemented and checked.

  ## Known gap, not implemented: printing character set

  Section 3.5's preamble (covering all of Fields 3-9, including every field
  this namespace validates) states: \"Compliance with EN 1387 with regard to
  the character set: Latin alphabet Nos 1-4 (ISO 8859-1 to 4)\". This is a
  real, EU-standardized constraint, but it is **not implemented** here: EN
  1387 is itself a separate, non-free standard (not fetched), and
  approximating \"ISO 8859-1 to 4\" as a portable regex across
  JVM/ClojureScript/SCI/GraalVM (this namespace's target platforms, per the
  rest of `kotoba.insurance`) would trade a precise, sourced length check
  for an imprecise, invented charset check -- exactly the kind of guess this
  library's operating rule (see `kotoba.insurance.jp`, `kotoba.insurance.us`)
  says not to make. Every predicate in this namespace therefore checks
  length/shape only, never character-set membership beyond \"decimal digit\"
  where the source explicitly says \"digit\".

  ## Also known, not modelled: Decision No S1 vs. No S2, and dates

  Decision No S1 of 12 June 2009 (OJ C 106, 24.4.2010, p. 23-25) is the
  companion decision defining *that* an EHIC must exist and *when* a
  Provisional Replacement Certificate is issued instead (procedural rules,
  not the card's data model) -- this namespace implements only Decision No
  S2 (the technical/data-model specification). Fields 5 (date of birth) and
  9 (expiry date) are both specified as `DD/MM/YYYY`, 10 characters, but are
  general date fields rather than insurance-specific identifiers, so (like
  `kotoba.insurance.jp`/`kotoba.insurance.us`'s scope) they are left
  unimplemented here rather than folded into an identifier-shaped namespace
  that does not otherwise touch dates.")

;; ---------------------------------------------------------------------
;; Field 2 -- Issuing state ID number (2-letter shape only; see docstring
;; for why full ISO 3166-1 alpha-2 membership is not validated)
;; ---------------------------------------------------------------------

(defn valid-issuing-state-code?
  "True when s is exactly 2 uppercase Latin letters -- the shape Annex I
  Field 2 documents for the issuing-state code (nominally \"the 2 digit ISO
  country code (ISO 3166-1)\", with the Decision's own documented exception
  that 'UK' is used instead of the ISO code 'GB'). Does not check ISO 3166-1
  alpha-2 membership -- see namespace docstring."
  [s]
  (boolean
    (when (string? s)
      (re-matches #"[A-Z]{2}" s))))

(defn validate-issuing-state-code
  "Return a shape-only validation result for an EHIC issuing-state code, in
  the same {:insurance/valid? ... :insurance/error ...} shape used
  elsewhere in this library. Failure modes: :not-a-string, :not-2-letters."
  [s]
  (cond
    (not (string? s))
    {:insurance/valid? false :insurance/error :not-a-string}

    (not (valid-issuing-state-code? s))
    {:insurance/valid? false :insurance/error :not-2-letters}

    :else
    {:insurance/valid? true :eu/issuing-state-code s}))

;; ---------------------------------------------------------------------
;; Field 6 -- Personal identification number (structural envelope only;
;; value is nation-specific, no documented cross-Member-State algorithm)
;; ---------------------------------------------------------------------

(defn valid-personal-identification-number-shape?
  "True when s is a non-blank string of at most 20 characters -- Annex I
  Field 6's only documented structural constraint (\"Length: Up to 20
  characters for the ID code\"). This is *not* a claim that s is a real,
  currently-issued personal identification number for any Member State --
  the value itself is nation-specific and this namespace has no algorithm
  to check it against (see namespace docstring)."
  [s]
  (boolean
    (when (string? s)
      (let [n (count s)]
        (and (pos? n) (<= n 20))))))

(defn validate-personal-identification-number-shape
  "Return a shape-only validation result for an EHIC personal
  identification number, in the same {:insurance/valid? ...
  :insurance/error ...} shape used elsewhere in this library. Failure
  modes: :not-a-string, :blank, :too-long (over 20 characters). A true
  result means only \"shape an EHIC personal identification number could
  plausibly have\" -- see namespace docstring."
  [s]
  (cond
    (not (string? s))
    {:insurance/valid? false :insurance/error :not-a-string}

    (zero? (count s))
    {:insurance/valid? false :insurance/error :blank}

    (> (count s) 20)
    {:insurance/valid? false :insurance/error :too-long}

    :else
    {:insurance/valid? true :eu/personal-identification-number s}))

;; ---------------------------------------------------------------------
;; Field 7, part 2 -- Institution identification number (structural
;; envelope only; value is nationally assigned, no documented algorithm)
;; ---------------------------------------------------------------------

(defn valid-institution-identification-number-shape?
  "True when s is a string of 4 to 10 characters (inclusive) -- Annex I
  Field 7 part 2's only documented structural constraint (\"Length: Between
  4 and 10 characters\"). Value is nationally assigned per Member State
  (\"see national code list of competent institutions\"); this namespace
  has no registry or algorithm to check it against -- see namespace
  docstring."
  [s]
  (boolean
    (when (string? s)
      (<= 4 (count s) 10))))

(defn validate-institution-identification-number-shape
  "Return a shape-only validation result for an EHIC competent-institution
  identification number, in the same {:insurance/valid? ...
  :insurance/error ...} shape used elsewhere in this library. Failure
  modes: :not-a-string, :bad-length (outside the 4-10 character bound)."
  [s]
  (cond
    (not (string? s))
    {:insurance/valid? false :insurance/error :not-a-string}

    (not (<= 4 (count s) 10))
    {:insurance/valid? false :insurance/error :bad-length}

    :else
    {:insurance/valid? true :eu/institution-identification-number s}))

;; ---------------------------------------------------------------------
;; Field 8 -- Logical identification number of the card (20 chars: 10-char
;; opaque issuer identifier (EN 1867) + 10-digit serial number)
;; ---------------------------------------------------------------------

(defn parse-card-identification-number
  "Split a 20-character EHIC card logical-identification-number string
  into its two Annex I Field 8 sub-fields: the first 10 characters (the
  EN-1867-registered issuer identifier -- opaque here, see namespace
  docstring for why its internal structure is not modelled) and the last
  10 characters (the numeric serial number). Returns nil unless s is
  exactly 20 characters *and* its last 10 characters are decimal digits --
  both are explicit Annex I constraints, not this namespace's invention."
  [s]
  (when (and (string? s) (= 20 (count s)))
    (let [issuer (subs s 0 10)
          serial (subs s 10 20)]
      (when (re-matches #"\d{10}" serial)
        {:eu/issuer-identifier issuer
         :eu/serial-number     serial}))))

(defn valid-card-identification-number?
  "True when s is a 20-character EHIC card logical-identification number
  whose last 10 characters are decimal digits (Annex I Field 8: \"The last
  10 digits constitute the unique serial number\"). The first 10
  characters are accepted as-is (any content) -- see
  parse-card-identification-number and the namespace docstring for why the
  EN 1867 issuer-identifier sub-field is treated as opaque."
  [s]
  (boolean (parse-card-identification-number s)))

(defn validate-card-identification-number
  "Return a validation result for an EHIC card logical-identification
  number, in the same {:insurance/valid? ... :insurance/error ...} shape
  used elsewhere in this library. Failure modes: :not-a-string,
  :not-20-characters, :serial-not-10-digits. A true result merges in the
  parsed :eu/issuer-identifier / :eu/serial-number sub-fields."
  [s]
  (cond
    (not (string? s))
    {:insurance/valid? false :insurance/error :not-a-string}

    (not= 20 (count s))
    {:insurance/valid? false :insurance/error :not-20-characters}

    (not (re-matches #"\d{10}" (subs s 10 20)))
    {:insurance/valid? false :insurance/error :serial-not-10-digits}

    :else
    (merge {:insurance/valid? true} (parse-card-identification-number s))))
