(ns iso-8583.fields
  "The ISO 8583 data element (field) table: for each field number, its
  content type (`:n` numeric, `:a` alpha, `:an` alphanumeric, `:ans`
  alphanumeric+special, `:b` binary, `:z` track-2), its length discipline
  (`:fixed`, `:llvar`, `:lllvar`) and, for `:fixed`, the length itself.

  **This table is deliberately data, and every encode/decode function in
  `iso-8583.codec` takes it as a parameter rather than closing over a
  built-in one.** ISO 8583 the standard fixed almost nothing about which
  fields carry what -- the 1987, 1993 and 2003 editions renumber and
  retype fields against each other, and acquirers customise further on
  top of whichever edition they nominally follow. A codec that hardcodes
  'the' field table is really hardcoding one bank's table and calling it
  the standard; this module ships `default-1987-fields` as a working,
  documented example and a thing to test against, not as the answer.

  `:encoding` (`:bcd` or `:ascii`) says how a field's *content* sits on
  the wire and only applies to `:n` and `:z` (an `:an`/`:ans`/`:b` field
  is always its own bytes, one byte per character for `:an`/`:ans`, raw
  for `:b`). `:len-encoding` (`:bcd` or `:ascii`) says how an `:llvar`/
  `:lllvar` field's own length prefix sits on the wire, independently of
  how the content is encoded -- a common real combination is a BCD length
  prefix in front of ASCII content, or vice versa.")

(def content-types #{:n :a :an :ans :b :z})
(def length-types #{:fixed :llvar :lllvar})
(def encodings #{:bcd :ascii})

(defn valid-spec?
  [{:keys [content-type length-type length encoding len-encoding]}]
  (and (contains? content-types content-type)
       (contains? length-types length-type)
       (or (not= length-type :fixed) (pos-int? length))
       (or (nil? encoding) (contains? encodings encoding))
       (or (= length-type :fixed) (contains? encodings len-encoding))))

;; A representative subset of the ISO 8583:1987 data element table, the
;; edition most acquirer/processor implementations still trace their
;; numbering from even when they call themselves 1993. Field numbers,
;; content types and fixed lengths below are transcribed from widely
;; published ISO 8583 field reference tables (e.g. the field
;; specifications reproduced across processor/switch integration guides
;; and the `iso8583.info`-style public references); this is a working
;; example table, not the authoritative standard text, and is exactly
;; the kind of thing a real integration replaces with its counterparty's
;; own specification.
(def default-1987-fields
  {2  {:content-type :n   :length-type :llvar  :encoding :bcd   :len-encoding :bcd
       :name "Primary account number"}
   3  {:content-type :n   :length-type :fixed  :length 6  :encoding :bcd
       :name "Processing code"}
   4  {:content-type :n   :length-type :fixed  :length 12 :encoding :bcd
       :name "Amount, transaction"}
   6  {:content-type :n   :length-type :fixed  :length 12 :encoding :bcd
       :name "Amount, cardholder billing"}
   7  {:content-type :n   :length-type :fixed  :length 10 :encoding :bcd
       :name "Transmission date & time"}
   11 {:content-type :n   :length-type :fixed  :length 6  :encoding :bcd
       :name "System trace audit number (STAN)"}
   12 {:content-type :n   :length-type :fixed  :length 6  :encoding :bcd
       :name "Time, local transaction"}
   13 {:content-type :n   :length-type :fixed  :length 4  :encoding :bcd
       :name "Date, local transaction"}
   14 {:content-type :n   :length-type :fixed  :length 4  :encoding :bcd
       :name "Expiration date"}
   18 {:content-type :n   :length-type :fixed  :length 4  :encoding :bcd
       :name "Merchant category code"}
   22 {:content-type :n   :length-type :fixed  :length 3  :encoding :bcd
       :name "POS entry mode"}
   23 {:content-type :n   :length-type :fixed  :length 3  :encoding :bcd
       :name "Card sequence number"}
   25 {:content-type :n   :length-type :fixed  :length 2  :encoding :bcd
       :name "POS condition code"}
   32 {:content-type :n   :length-type :llvar  :encoding :bcd   :len-encoding :bcd
       :name "Acquiring institution ID code"}
   35 {:content-type :z   :length-type :llvar  :len-encoding :bcd
       :name "Track 2 data"}
   37 {:content-type :an  :length-type :fixed  :length 12
       :name "Retrieval reference number"}
   38 {:content-type :an  :length-type :fixed  :length 6
       :name "Authorization ID response"}
   39 {:content-type :an  :length-type :fixed  :length 2
       :name "Response code"}
   41 {:content-type :ans :length-type :fixed  :length 8
       :name "Card acceptor terminal ID"}
   42 {:content-type :ans :length-type :fixed  :length 15
       :name "Card acceptor ID code"}
   43 {:content-type :ans :length-type :fixed  :length 40
       :name "Card acceptor name/location"}
   49 {:content-type :n   :length-type :fixed  :length 3  :encoding :bcd
       :name "Currency code, transaction"}
   52 {:content-type :b   :length-type :fixed  :length 8
       :name "PIN data"}
   53 {:content-type :n   :length-type :fixed  :length 16 :encoding :bcd
       :name "Security related control information"}
   54 {:content-type :an  :length-type :lllvar :len-encoding :ascii
       :name "Additional amounts"}
   55 {:content-type :b   :length-type :lllvar :len-encoding :bcd
       :name "ICC data (EMV)"}
   62 {:content-type :ans :length-type :lllvar :len-encoding :ascii
       :name "Reserved private (network use)"}
   63 {:content-type :ans :length-type :lllvar :len-encoding :ascii
       :name "Reserved private (network use)"}
   64 {:content-type :b   :length-type :fixed  :length 8
       :name "MAC field (primary bitmap)"}
   90 {:content-type :n   :length-type :fixed  :length 42 :encoding :bcd
       :name "Original data elements"}
   102 {:content-type :ans :length-type :llvar :len-encoding :ascii
        :name "Account identification 1"}
   128 {:content-type :b  :length-type :fixed  :length 8
        :name "MAC field (secondary bitmap)"}})
